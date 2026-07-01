import asyncio
import base64
import html
import inspect
import io
import json
import re
import uuid
from urllib.parse import urlparse, unquote
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

import httpx
from fastapi import UploadFile
from sqlalchemy import delete, desc, func, select

from src.core.config import settings
from src.core.exceptions import BusinessLogicError, NotFoundError
from src.core.logging import get_logger
from src.models.api_key import APIKey
from src.models.canvas import (
    CanvasConnection,
    CanvasDocument,
    CanvasGenerationType,
    CanvasItem,
    CanvasItemGeneration,
    CanvasItemType,
    CanvasRunStatus,
    ensure_canvas_uuid,
)
from src.services.api_key import APIKeyService
from src.services.base import BaseService
from src.services.provider.factory import ProviderFactory
from src.services.provider.vector_engine_provider import VectorEngineProvider
from src.utils.media_urls import media_url_for_object_key
from src.utils.storage import get_storage_client

logger = get_logger(__name__)

PROMPT_BREAK_TAG_PATTERN = re.compile(r"(?i)<br\s*/?>")
PROMPT_LIST_ITEM_PATTERN = re.compile(r"(?i)<li\b[^>]*>")
PROMPT_LIST_ITEM_CLOSE_PATTERN = re.compile(r"(?i)</li>")
PROMPT_BLOCK_TAG_PATTERN = re.compile(r"(?i)</?(p|div|h[1-6]|ul|ol|blockquote|section|article|hr)\b[^>]*>")
PROMPT_HTML_TAG_PATTERN = re.compile(r"(?is)<[^>]+>")
PROMPT_SPACE_PATTERN = re.compile(r"[ \t]+")
PROMPT_BLANK_LINE_PATTERN = re.compile(r"\n{3,}")
REFERENCE_TEXT_LIMIT = 1500
REFERENCE_IMAGE_LIMIT = 2
MEDIA_URL_TO_OBJECT_KEY_FIELDS = {
    "result_image_url": "result_image_object_key",
    "reference_image_url": "reference_image_object_key",
    "result_video_url": "result_video_object_key",
}


def absolute_public_media_url_for_object_key(object_key: str) -> str:
    base_url = str(settings.PUBLIC_BASE_URL or "").strip().rstrip("/")
    media_path = media_url_for_object_key(object_key)
    if base_url and media_path:
        return f"{base_url}{media_path}"
    return media_path


def is_likely_celery_task_id(value: Any, generation_id: str) -> bool:
    task_id = str(value or "").strip()
    if not task_id:
        return False
    if task_id == str(generation_id):
        return False
    if task_id.startswith("20"):
        return False
    return bool(re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", task_id))


def extract_object_key_from_media_url(media_url: Any) -> str:
    value = str(media_url or "").strip()
    if not value:
        return ""
    if value.startswith("uploads/"):
        return value
    parsed = urlparse(value)
    path = unquote(parsed.path or "").lstrip("/")
    bucket_prefix = f"{settings.MINIO_BUCKET_NAME}/"
    if path.startswith(bucket_prefix):
        path = path[len(bucket_prefix):]
    if path.startswith("uploads/"):
        return path
    return ""


def sanitize_prompt_tokens_for_storage(prompt_tokens: Any) -> List[Dict[str, Any]]:
    if not isinstance(prompt_tokens, list):
        return []

    sanitized_tokens: List[Dict[str, Any]] = []
    for token in prompt_tokens:
        if not isinstance(token, dict):
            continue
        sanitized_token = dict(token)
        if str(sanitized_token.get("type") or "").strip() == "mention":
            object_key = str(
                sanitized_token.get("nodePreviewObjectKeySnapshot")
                or extract_object_key_from_media_url(sanitized_token.get("nodePreviewUrlSnapshot"))
                or ""
            ).strip()
            if object_key:
                sanitized_token["nodePreviewObjectKeySnapshot"] = object_key
                sanitized_token.pop("nodePreviewUrlSnapshot", None)
        sanitized_tokens.append(sanitized_token)
    return sanitized_tokens


def sanitize_resolved_mentions_for_storage(resolved_mentions: Any) -> List[Dict[str, Any]]:
    if not isinstance(resolved_mentions, list):
        return []

    sanitized_mentions: List[Dict[str, Any]] = []
    for mention in resolved_mentions:
        if not isinstance(mention, dict):
            continue
        sanitized_mention = dict(mention)
        resolved_content = sanitized_mention.get("resolvedContent")
        if isinstance(resolved_content, dict):
            sanitized_content = dict(resolved_content)
            object_key = str(
                sanitized_content.get("object_key")
                or sanitized_content.get("objectKey")
                or extract_object_key_from_media_url(sanitized_content.get("url"))
                or ""
            ).strip()
            if object_key:
                sanitized_content["object_key"] = object_key
                sanitized_content.pop("objectKey", None)
                sanitized_content.pop("url", None)
            sanitized_mention["resolvedContent"] = sanitized_content
        sanitized_mentions.append(sanitized_mention)
    return sanitized_mentions


class CanvasService(BaseService):
    def _extract_object_key_from_media_url(self, media_url: Any) -> str:
        return extract_object_key_from_media_url(media_url)

    async def list_documents(self, user_id: str, page: int = 1, size: int = 20) -> Tuple[List[CanvasDocument], int]:
        count_stmt = select(func.count(CanvasDocument.id)).where(CanvasDocument.user_id == ensure_canvas_uuid(user_id))
        total = (await self.execute(count_stmt)).scalar() or 0
        stmt = (
            select(CanvasDocument)
            .where(CanvasDocument.user_id == ensure_canvas_uuid(user_id))
            .order_by(desc(CanvasDocument.updated_at))
            .offset((page - 1) * size)
            .limit(size)
        )
        result = await self.execute(stmt)
        return list(result.scalars().all()), total

    async def create_document(self, user_id: str, title: str, description: Optional[str] = None) -> CanvasDocument:
        document = CanvasDocument(user_id=ensure_canvas_uuid(user_id), title=title, description=description)
        self.add(document)
        await self.flush()
        await self.refresh(document)
        return document

    async def get_document(self, document_id: str, user_id: str) -> CanvasDocument:
        stmt = select(CanvasDocument).where(
            CanvasDocument.id == ensure_canvas_uuid(document_id),
            CanvasDocument.user_id == ensure_canvas_uuid(user_id),
        )
        result = await self.execute(stmt)
        document = result.scalar_one_or_none()
        if not document:
            raise NotFoundError("画布不存在", resource_id=document_id, resource_type="canvas_document")
        return document

    async def update_document(self, document_id: str, user_id: str, title: Optional[str], description: Optional[str]) -> CanvasDocument:
        document = await self.get_document(document_id, user_id)
        if title is not None:
            document.title = title
        if description is not None:
            document.description = description
        await self.flush()
        await self.refresh(document)
        return document

    async def delete_document(self, document_id: str, user_id: str) -> None:
        document = await self.get_document(document_id, user_id)
        await self.db_session.delete(document)
        await self.flush()

    async def create_item(self, document_id: str, user_id: str, payload: Dict[str, Any]) -> CanvasItem:
        document = await self.get_document(document_id, user_id)
        item = CanvasItem(
            document_id=document.id,
            item_type=payload["item_type"],
            title=payload.get("title", ""),
            position_x=payload.get("position_x", 0),
            position_y=payload.get("position_y", 0),
            width=payload.get("width", 320),
            height=payload.get("height", 220),
            z_index=payload.get("z_index", 0),
            content_json=self._sanitize_media_content(payload.get("content", {})),
            generation_config_json=payload.get("generation_config", {}),
            last_run_status=payload.get("last_run_status") or CanvasRunStatus.IDLE.value,
            last_run_error=payload.get("last_run_error"),
            last_output_json=self._sanitize_media_result_payload(payload.get("last_output", {})),
        )
        self.add(item)
        await self.flush()
        await self.refresh(item)
        return item

    async def update_item(self, document_id: str, item_id: str, user_id: str, payload: Dict[str, Any]) -> CanvasItem:
        await self.get_document(document_id, user_id)
        item = await self.get_item(item_id, user_id)
        if str(item.document_id) != str(ensure_canvas_uuid(document_id)):
            raise NotFoundError("画布节点不存在", resource_id=item_id, resource_type="canvas_item")

        scalar_fields = ("title", "position_x", "position_y", "width", "height", "z_index", "last_run_status", "last_run_error")
        for field in scalar_fields:
            if field in payload and payload[field] is not None:
                setattr(item, field, payload[field])

        if "content" in payload and payload["content"] is not None:
            item.content_json = self._sanitize_media_content({**(item.content_json or {}), **payload["content"]})
        if "generation_config" in payload and payload["generation_config"] is not None:
            item.generation_config_json = {**(item.generation_config_json or {}), **payload["generation_config"]}
        if "last_output" in payload and payload["last_output"] is not None:
            item.last_output_json = self._sanitize_media_result_payload(
                {**(item.last_output_json or {}), **payload["last_output"]}
            )

        await self.flush()
        await self.refresh(item)
        return item

    async def delete_item(self, document_id: str, item_id: str, user_id: str) -> None:
        await self.get_document(document_id, user_id)
        item = await self.get_item(item_id, user_id)
        if str(item.document_id) != str(ensure_canvas_uuid(document_id)):
            raise NotFoundError("画布节点不存在", resource_id=item_id, resource_type="canvas_item")
        await self.db_session.delete(item)
        await self.flush()

    async def delete_items(self, document_id: str, item_ids: List[str], user_id: str) -> None:
        document = await self.get_document(document_id, user_id)
        normalized_item_ids = [ensure_canvas_uuid(item_id) for item_id in item_ids if str(item_id).strip()]
        if not normalized_item_ids:
            return

        item_stmt = select(CanvasItem.id).where(
            CanvasItem.document_id == document.id,
            CanvasItem.id.in_(normalized_item_ids),
        )
        existing_item_ids = list((await self.execute(item_stmt)).scalars().all())
        existing_item_id_set = {str(item_id) for item_id in existing_item_ids}
        missing_item_ids = [item_id for item_id in normalized_item_ids if str(item_id) not in existing_item_id_set]
        if missing_item_ids:
            raise NotFoundError(
                "画布节点不存在",
                resource_id=str(missing_item_ids[0]),
                resource_type="canvas_item",
            )

        await self.execute(
            delete(CanvasConnection).where(
                CanvasConnection.document_id == document.id,
                (CanvasConnection.source_item_id.in_(normalized_item_ids))
                | (CanvasConnection.target_item_id.in_(normalized_item_ids))
            )
        )
        await self.execute(
            delete(CanvasItem).where(
                CanvasItem.document_id == document.id,
                CanvasItem.id.in_(normalized_item_ids),
            )
        )
        await self.flush()

    async def create_connection(self, document_id: str, user_id: str, payload: Dict[str, Any]) -> CanvasConnection:
        document = await self.get_document(document_id, user_id)
        source_item = await self.get_item(str(payload["source_item_id"]), user_id)
        target_item = await self.get_item(str(payload["target_item_id"]), user_id)
        if source_item.document_id != document.id or target_item.document_id != document.id:
            raise BusinessLogicError("连线节点不属于当前画布")

        connection = CanvasConnection(
            document_id=document.id,
            source_item_id=source_item.id,
            target_item_id=target_item.id,
            source_handle=payload["source_handle"],
            target_handle=payload["target_handle"],
        )
        self.add(connection)
        await self.flush()
        await self.refresh(connection)
        return connection

    async def delete_connection(self, document_id: str, connection_id: str, user_id: str) -> None:
        document = await self.get_document(document_id, user_id)
        stmt = select(CanvasConnection).where(
            CanvasConnection.id == ensure_canvas_uuid(connection_id),
            CanvasConnection.document_id == document.id,
        )
        connection = (await self.execute(stmt)).scalar_one_or_none()
        if not connection:
            raise NotFoundError("画布连线不存在", resource_id=connection_id, resource_type="canvas_connection")
        await self.db_session.delete(connection)
        await self.flush()

    async def save_graph(self, document_id: str, user_id: str, items: List[Dict[str, Any]], connections: List[Dict[str, Any]]) -> CanvasDocument:
        document = await self.get_document(document_id, user_id)

        existing_items_stmt = select(CanvasItem).where(CanvasItem.document_id == document.id)
        existing_items = list((await self.execute(existing_items_stmt)).scalars().all())
        existing_by_id = {str(item.id): item for item in existing_items}
        incoming_ids = {str(ensure_canvas_uuid(item["id"])) for item in items}

        for existing_item in existing_items:
            if str(existing_item.id) not in incoming_ids:
                await self.db_session.delete(existing_item)

        for item_payload in items:
            item_id = str(ensure_canvas_uuid(item_payload["id"]))
            item = existing_by_id.get(item_id)
            if item is None:
                item = CanvasItem(
                    id=ensure_canvas_uuid(item_payload["id"]),
                    document_id=document.id,
                )
                self.add(item)

            item.item_type = item_payload["item_type"]
            item.title = item_payload.get("title", "")
            item.position_x = item_payload.get("position_x", 0)
            item.position_y = item_payload.get("position_y", 0)
            item.width = item_payload.get("width", 320)
            item.height = item_payload.get("height", 220)
            item.z_index = item_payload.get("z_index", 0)
            item.content_json = self._sanitize_media_content(item_payload.get("content", {}))
            item.generation_config_json = item_payload.get("generation_config", {})
            item.last_run_status = item_payload.get("last_run_status") or item.last_run_status or CanvasRunStatus.IDLE.value
            item.last_run_error = item_payload.get("last_run_error")
            item.last_output_json = self._sanitize_media_result_payload(
                item_payload.get("last_output", item.last_output_json or {})
            )

        await self.execute(delete(CanvasConnection).where(CanvasConnection.document_id == document.id))
        await self.flush()

        for connection in connections:
            self.add(
                CanvasConnection(
                    id=ensure_canvas_uuid(connection["id"]),
                    document_id=document.id,
                    source_item_id=ensure_canvas_uuid(connection["source_item_id"]),
                    target_item_id=ensure_canvas_uuid(connection["target_item_id"]),
                    source_handle=connection["source_handle"],
                    target_handle=connection["target_handle"],
                )
            )

        await self.flush()
        await self.refresh(document)
        return document

    async def get_graph(self, document_id: str, user_id: str) -> Dict[str, Any]:
        document = await self.get_document(document_id, user_id)
        item_stmt = select(CanvasItem).where(CanvasItem.document_id == document.id).order_by(CanvasItem.z_index, CanvasItem.created_at)
        connection_stmt = select(CanvasConnection).where(CanvasConnection.document_id == document.id).order_by(CanvasConnection.created_at)
        items = list((await self.execute(item_stmt)).scalars().all())
        connections = list((await self.execute(connection_stmt)).scalars().all())
        return {"document": document, "items": items, "connections": connections}

    async def get_stage_snapshot(self, document_id: str, user_id: str) -> Dict[str, Any]:
        graph = await self.get_graph(document_id, user_id)
        projected_items = [self._project_stage_item(item) for item in graph["items"]]
        return {
            "document": graph["document"],
            "items": projected_items,
            "connections": graph["connections"],
        }

    async def get_item_previews(self, document_id: str, user_id: str, item_ids: List[str]) -> List[CanvasItem]:
        document = await self.get_document(document_id, user_id)
        if not item_ids:
            return []

        stmt = select(CanvasItem).where(
            CanvasItem.document_id == document.id,
            CanvasItem.id.in_([ensure_canvas_uuid(item_id) for item_id in item_ids]),
        )
        items = list((await self.execute(stmt)).scalars().all())
        return [self._serialize_item(item, content=self._project_preview_content(item)) for item in items]

    async def get_item(self, item_id: str, user_id: str) -> CanvasItem:
        stmt = (
            select(CanvasItem)
            .join(CanvasDocument, CanvasDocument.id == CanvasItem.document_id)
            .where(CanvasItem.id == ensure_canvas_uuid(item_id), CanvasDocument.user_id == ensure_canvas_uuid(user_id))
        )
        result = await self.execute(stmt)
        item = result.scalar_one_or_none()
        if not item:
            raise NotFoundError("画布节点不存在", resource_id=item_id, resource_type="canvas_item")
        return item

    async def get_item_by_id(self, item_id: str) -> CanvasItem:
        stmt = select(CanvasItem).where(CanvasItem.id == ensure_canvas_uuid(item_id))
        item = (await self.execute(stmt)).scalar_one_or_none()
        if not item:
            raise NotFoundError("画布节点不存在", resource_id=item_id, resource_type="canvas_item")
        return item

    async def get_generation(self, generation_id: str) -> CanvasItemGeneration:
        stmt = select(CanvasItemGeneration).where(CanvasItemGeneration.id == ensure_canvas_uuid(generation_id))
        generation = (await self.execute(stmt)).scalar_one_or_none()
        if not generation:
            raise NotFoundError("节点生成记录不存在", resource_id=generation_id, resource_type="canvas_generation")
        return generation

    async def get_item_generation(self, item_id: str, generation_id: str, user_id: str) -> Tuple[CanvasItem, CanvasItemGeneration]:
        item = await self.get_item(item_id, user_id)
        stmt = select(CanvasItemGeneration).where(
            CanvasItemGeneration.id == ensure_canvas_uuid(generation_id),
            CanvasItemGeneration.item_id == item.id,
        )
        generation = (await self.execute(stmt)).scalar_one_or_none()
        if not generation:
            raise NotFoundError("节点生成记录不存在", resource_id=generation_id, resource_type="canvas_generation")
        return item, generation

    async def list_generations(self, item_id: str, user_id: str, page: int = 1, size: int = 20) -> Tuple[List[CanvasItemGeneration], int]:
        item = await self.get_item(item_id, user_id)
        count_stmt = select(func.count(CanvasItemGeneration.id)).where(CanvasItemGeneration.item_id == item.id)
        total = (await self.execute(count_stmt)).scalar() or 0
        stmt = (
            select(CanvasItemGeneration)
            .where(CanvasItemGeneration.item_id == item.id)
            .order_by(desc(CanvasItemGeneration.created_at))
            .offset((page - 1) * size)
            .limit(size)
        )
        generations = list((await self.execute(stmt)).scalars().all())
        return generations, total

    async def apply_generation(self, item_id: str, generation_id: str, user_id: str) -> Tuple[CanvasItem, CanvasItemGeneration]:
        item = await self.get_item(item_id, user_id)
        stmt = select(CanvasItemGeneration).where(
            CanvasItemGeneration.id == ensure_canvas_uuid(generation_id),
            CanvasItemGeneration.item_id == item.id,
        )
        generation = (await self.execute(stmt)).scalar_one_or_none()
        if not generation:
            raise NotFoundError("节点生成记录不存在", resource_id=generation_id, resource_type="canvas_generation")
        item.last_output_json = generation.result_payload_json or {}
        item.content_json = self._apply_generation_output(item.item_type, item.content_json or {}, generation.result_payload_json or {})
        item.last_run_status = generation.status
        item.last_run_error = generation.error_message
        await self.flush()
        await self.refresh(item)
        return item, generation

    async def create_pending_generation(
        self,
        item: CanvasItem,
        user_id: str,
        generation_type: str,
        request_payload: Dict[str, Any],
        result_payload: Optional[Dict[str, Any]] = None,
    ) -> CanvasItemGeneration:
        sanitized_result_payload = self._sanitize_media_result_payload(result_payload or {})
        generation = CanvasItemGeneration(
            item_id=item.id,
            document_id=item.document_id,
            user_id=ensure_canvas_uuid(user_id),
            generation_type=generation_type,
            request_payload_json=request_payload,
            status=CanvasRunStatus.PENDING.value,
            result_payload_json=sanitized_result_payload,
            error_message=None,
        )
        self.add(generation)
        item.last_run_status = CanvasRunStatus.PENDING.value
        item.last_run_error = None
        item.last_output_json = sanitized_result_payload
        await self.flush()
        await self.refresh(generation)
        await self.refresh(item)
        return generation

    async def update_generation(
        self,
        generation: CanvasItemGeneration,
        item: CanvasItem,
        status: str,
        result_payload: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> CanvasItemGeneration:
        merged_payload = dict(generation.result_payload_json or {})
        if result_payload:
            merged_payload.update(self._sanitize_media_result_payload(result_payload))

        generation.status = status
        generation.result_payload_json = merged_payload
        generation.error_message = error_message

        item.last_run_status = status
        item.last_run_error = error_message
        item.last_output_json = merged_payload
        if status == CanvasRunStatus.COMPLETED.value:
            item.content_json = self._apply_generation_output(item.item_type, item.content_json or {}, merged_payload)

        await self.flush()
        await self.refresh(generation)
        await self.refresh(item)
        return generation

    def _has_successful_video_result(self, generation: CanvasItemGeneration) -> bool:
        payload = generation.result_payload_json or {}
        return bool(payload.get("result_video_object_key"))

    def _apply_generation_output(self, item_type: str, content: Dict[str, Any], result_payload: Dict[str, Any]) -> Dict[str, Any]:
        next_content = dict(content or {})
        if item_type == CanvasItemType.TEXT.value and result_payload.get("text"):
            next_content["text"] = result_payload["text"]
        if item_type == CanvasItemType.IMAGE.value and result_payload.get("result_image_object_key"):
            next_content["result_image_object_key"] = result_payload["result_image_object_key"]
        if item_type == CanvasItemType.VIDEO.value and result_payload.get("result_video_object_key"):
            next_content["result_video_object_key"] = result_payload["result_video_object_key"]
        if result_payload.get("provider_task_id"):
            next_content["provider_task_id"] = result_payload["provider_task_id"]
        if result_payload.get("task_id"):
            next_content["task_id"] = result_payload["task_id"]
        return self._sanitize_media_content(next_content)

    def _project_stage_item(self, item: CanvasItem) -> CanvasItem:
        return self._serialize_item(item, content=self._project_stage_content(item))

    def _project_stage_content(self, item: CanvasItem) -> Dict[str, Any]:
        content = dict(item.content_json or {})
        if item.item_type == CanvasItemType.TEXT.value:
            text = str(content.get("text") or content.get("value") or "").strip()
            preview = text[:240] + ("..." if len(text) > 240 else "")
            return {"text_preview": preview}
        if item.item_type == CanvasItemType.IMAGE.value:
            return self._project_preview_content(item)
        if item.item_type == CanvasItemType.VIDEO.value:
            return self._project_preview_content(item)
        return content

    def _project_preview_content(self, item: CanvasItem) -> Dict[str, Any]:
        content = dict(item.content_json or {})
        if item.item_type == CanvasItemType.IMAGE.value:
            return {
                "result_image_object_key": content.get("result_image_object_key", ""),
                "reference_image_object_key": content.get("reference_image_object_key", ""),
            }
        if item.item_type == CanvasItemType.VIDEO.value:
            return {
                "result_video_object_key": content.get("result_video_object_key", ""),
                "provider_task_id": content.get("provider_task_id", ""),
            }
        return content

    def _serialize_item(self, item: CanvasItem, *, content: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "id": item.id,
            "item_type": item.item_type,
            "title": item.title or "",
            "position_x": float(item.position_x or 0),
            "position_y": float(item.position_y or 0),
            "width": float(item.width or 0),
            "height": float(item.height or 0),
            "z_index": int(item.z_index or 0),
            "content": content if content is not None else dict(item.content_json or {}),
            "generation_config": dict(item.generation_config_json or {}),
            "last_run_status": item.last_run_status,
            "last_run_error": item.last_run_error,
            "last_output": dict(item.last_output_json or {}),
        }

    def _sanitize_media_content(self, content: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(content, dict):
            return {}
        sanitized = dict(content)
        if "promptTokens" in sanitized:
            sanitized["promptTokens"] = sanitize_prompt_tokens_for_storage(sanitized.get("promptTokens"))
        if "resolvedMentions" in sanitized:
            sanitized["resolvedMentions"] = sanitize_resolved_mentions_for_storage(sanitized.get("resolvedMentions"))
        if "resolved_mentions" in sanitized:
            sanitized["resolved_mentions"] = sanitize_resolved_mentions_for_storage(sanitized.get("resolved_mentions"))
        for url_field, object_key_field in MEDIA_URL_TO_OBJECT_KEY_FIELDS.items():
            if not sanitized.get(object_key_field):
                extracted_object_key = self._extract_object_key_from_media_url(sanitized.get(url_field))
                if extracted_object_key:
                    sanitized[object_key_field] = extracted_object_key
            if sanitized.get(object_key_field):
                sanitized.pop(url_field, None)
        return sanitized

    def _sanitize_media_result_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            return {}
        sanitized = dict(payload)
        for url_field, object_key_field in MEDIA_URL_TO_OBJECT_KEY_FIELDS.items():
            if not sanitized.get(object_key_field):
                extracted_object_key = self._extract_object_key_from_media_url(sanitized.get(url_field))
                if extracted_object_key:
                    sanitized[object_key_field] = extracted_object_key
            if sanitized.get(object_key_field):
                sanitized.pop(url_field, None)
        return sanitized


class CanvasTaskHistoryService(BaseService):
    def _normalize_status(self, status_value: Any) -> str:
        status_text = str(status_value or "").strip().lower()
        if status_text in {"pending", "queued"}:
            return "pending"
        if status_text in {"processing", "running", "started"}:
            return "processing"
        if status_text in {"completed", "success", "succeeded", "done"}:
            return "completed"
        if status_text in {"failed", "error", "cancelled", "canceled"}:
            return "failed"
        return status_text or "pending"

    def _task_type_from_generation(self, generation: CanvasItemGeneration, item: CanvasItem) -> str:
        generation_type = str(generation.generation_type or item.item_type or "").strip()
        result_payload = generation.result_payload_json or {}
        request_payload = generation.request_payload_json or {}
        if generation_type == CanvasGenerationType.VIDEO.value and (
            result_payload.get("provider_task_id")
            or request_payload.get("options", {}).get("reference_image_urls")
            or item.content_json.get("reference_image_urls")
        ):
            return "video"
        return generation_type or item.item_type or "text"

    def _media_payload(self, item_type: str, result_payload: Dict[str, Any], item_content: Dict[str, Any]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "media_url": "",
            "preview_url": "",
            "download_url": "",
            "stream_url": "",
            "object_key": "",
        }
        if item_type == CanvasItemType.IMAGE.value:
            object_key = str(
                result_payload.get("result_image_object_key")
                or item_content.get("result_image_object_key")
                or item_content.get("reference_image_object_key")
                or ""
            ).strip()
            if object_key:
                payload.update(
                    {
                        "media_url": media_url_for_object_key(object_key, "preview"),
                        "preview_url": media_url_for_object_key(object_key, "preview"),
                        "download_url": media_url_for_object_key(object_key, "download"),
                        "object_key": object_key,
                    }
                )
        elif item_type == CanvasItemType.VIDEO.value:
            object_key = str(
                result_payload.get("result_video_object_key")
                or item_content.get("result_video_object_key")
                or ""
            ).strip()
            if object_key:
                payload.update(
                    {
                        "media_url": media_url_for_object_key(object_key, "stream"),
                        "preview_url": media_url_for_object_key(object_key, "preview"),
                        "download_url": media_url_for_object_key(object_key, "download"),
                        "stream_url": media_url_for_object_key(object_key, "stream"),
                        "object_key": object_key,
                    }
                )
        return payload

    def _model_from_payloads(self, request_payload: Dict[str, Any], item: CanvasItem) -> str:
        return str(
            request_payload.get("model")
            or (item.generation_config_json or {}).get("model")
            or ""
        ).strip()

    def _provider_from_payloads(self, request_payload: Dict[str, Any], result_payload: Dict[str, Any]) -> str:
        provider_response = result_payload.get("provider_response")
        if isinstance(provider_response, dict):
            provider = provider_response.get("provider") or provider_response.get("provider_name")
            if provider:
                return str(provider)
        provider = result_payload.get("provider")
        if provider:
            return str(provider)
        return str(request_payload.get("provider") or "").strip()

    def _params_summary_from_payloads(self, request_payload: Dict[str, Any]) -> Dict[str, Any]:
        options = request_payload.get("options") or {}
        if not isinstance(options, dict):
            options = {}
        summary: Dict[str, Any] = {}
        for key in (
            "image_size",
            "size",
            "aspect_ratio",
            "n",
            "duration",
            "duration_seconds",
        ):
            value = options.get(key)
            if value not in (None, "", []):
                summary[key] = value
        if options.get("reference_image_urls"):
            summary["reference_images"] = len(options.get("reference_image_urls") or [])
        if options.get("reference_image_object_keys"):
            summary["reference_images"] = len(options.get("reference_image_object_keys") or [])
        return summary

    def _result_count_from_payload(self, result_payload: Dict[str, Any]) -> int:
        images = result_payload.get("result_images") if isinstance(result_payload, dict) else None
        if isinstance(images, list):
            return len([entry for entry in images if isinstance(entry, dict) and entry.get("object_key")])
        if isinstance(result_payload, dict) and result_payload.get("result_image_object_key"):
            return 1
        return 0

    def _result_summary_from_payload(self, result_payload: Dict[str, Any]) -> str:
        result_count = self._result_count_from_payload(result_payload)
        if result_count > 1:
            return f"生成 {result_count} 张图片"
        if result_count == 1:
            return "生成 1 张图片"
        return ""

    def _generation_to_history_item(self, generation: CanvasItemGeneration, item: CanvasItem, document: CanvasDocument) -> Dict[str, Any]:
        request_payload = generation.request_payload_json or {}
        result_payload = generation.result_payload_json or {}
        content = item.content_json or {}
        task_type = self._task_type_from_generation(generation, item)
        media_payload = self._media_payload(item.item_type, result_payload, content)
        source_item_id = ""
        prompt_tokens = request_payload.get("prompt_tokens") or content.get("promptTokens") or []
        if isinstance(prompt_tokens, list):
            for token in prompt_tokens:
                if isinstance(token, dict) and token.get("type") == "mention" and token.get("nodeId"):
                    source_item_id = str(token.get("nodeId"))
                    break
        return {
            "id": str(generation.id),
            "type": task_type,
            "status": self._normalize_status(generation.status),
            "title": item.title or f"{task_type} 生成任务",
            "canvas_id": str(document.id),
            "canvas_title": document.title or "",
            "canvas_item_id": str(item.id),
            "source_item_id": source_item_id,
            "media_url": media_payload["media_url"],
            "preview_url": media_payload["preview_url"],
            "download_url": media_payload["download_url"],
            "stream_url": media_payload["stream_url"],
            "object_key": media_payload["object_key"],
            "error_message": generation.error_message or item.last_run_error or "",
            "provider": self._provider_from_payloads(request_payload, result_payload),
            "model": self._model_from_payloads(request_payload, item),
            "params": self._params_summary_from_payloads(request_payload),
            "result_count": self._result_count_from_payload(result_payload),
            "result_summary": self._result_summary_from_payload(result_payload),
            "created_at": generation.created_at.isoformat() if generation.created_at else "",
            "updated_at": generation.updated_at.isoformat() if generation.updated_at else "",
            "request_payload": request_payload,
            "result_payload": result_payload,
        }

    def _assistant_item_to_history_item(self, item: CanvasItem, document: CanvasDocument) -> Dict[str, Any]:
        content = item.content_json or {}
        output = item.last_output_json or {}
        return {
            "id": f"item:{item.id}",
            "type": "assistant" if content.get("assistant_writeback") else "text",
            "status": self._normalize_status(item.last_run_status),
            "title": item.title or "文本节点",
            "canvas_id": str(document.id),
            "canvas_title": document.title or "",
            "canvas_item_id": str(item.id),
            "source_item_id": "",
            "media_url": "",
            "preview_url": "",
            "download_url": "",
            "stream_url": "",
            "object_key": "",
            "error_message": item.last_run_error or "",
            "provider": "",
            "model": str((item.generation_config_json or {}).get("model") or "").strip(),
            "created_at": item.created_at.isoformat() if item.created_at else "",
            "updated_at": item.updated_at.isoformat() if item.updated_at else "",
            "request_payload": {},
            "result_payload": output or {"text": content.get("text") or content.get("prompt") or ""},
        }

    def _matches_filters(self, entry: Dict[str, Any], *, status: str | None, task_type: str | None) -> bool:
        normalized_status = str(status or "").strip().lower()
        normalized_type = str(task_type or "").strip().lower()
        if normalized_status and entry.get("status") != normalized_status:
            return False
        if normalized_type:
            if normalized_type == "image_to_video":
                return entry.get("type") == "video" and bool((entry.get("result_payload") or {}).get("provider_task_id"))
            return entry.get("type") == normalized_type
        return True

    async def list_history(
        self,
        user_id: str,
        *,
        canvas_id: str | None = None,
        status: str | None = None,
        task_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        normalized_user_id = ensure_canvas_uuid(user_id)
        conditions = [CanvasDocument.user_id == normalized_user_id]
        if canvas_id:
            conditions.append(CanvasDocument.id == ensure_canvas_uuid(canvas_id))

        generation_stmt = (
            select(CanvasItemGeneration, CanvasItem, CanvasDocument)
            .join(CanvasItem, CanvasItem.id == CanvasItemGeneration.item_id)
            .join(CanvasDocument, CanvasDocument.id == CanvasItemGeneration.document_id)
            .where(*conditions)
            .order_by(desc(CanvasItemGeneration.created_at))
        )
        generation_rows = list((await self.execute(generation_stmt)).all())
        entries = [
            self._generation_to_history_item(generation, item, document)
            for generation, item, document in generation_rows
        ]

        item_conditions = [
            CanvasDocument.user_id == normalized_user_id,
            CanvasItem.item_type == CanvasItemType.TEXT.value,
            CanvasItem.last_run_status.in_([CanvasRunStatus.COMPLETED.value, CanvasRunStatus.FAILED.value]),
        ]
        if canvas_id:
            item_conditions.append(CanvasDocument.id == ensure_canvas_uuid(canvas_id))
        item_stmt = (
            select(CanvasItem, CanvasDocument)
            .join(CanvasDocument, CanvasDocument.id == CanvasItem.document_id)
            .where(*item_conditions)
            .order_by(desc(CanvasItem.created_at))
        )
        item_rows = list((await self.execute(item_stmt)).all())
        generation_item_ids = {str(generation.item_id) for generation, _, _ in generation_rows}
        for item, document in item_rows:
            if str(item.id) in generation_item_ids:
                continue
            content = item.content_json or {}
            if not content.get("assistant_writeback") and not (item.last_output_json or {}).get("text"):
                continue
            entries.append(self._assistant_item_to_history_item(item, document))

        filtered = [
            entry
            for entry in entries
            if self._matches_filters(entry, status=status, task_type=task_type)
        ]
        filtered.sort(key=lambda entry: entry.get("created_at") or "", reverse=True)
        total = len(filtered)
        return filtered[offset : offset + limit], total

    async def get_history_detail(self, history_id: str, user_id: str) -> Dict[str, Any]:
        if history_id.startswith("item:"):
            item_id = history_id.split(":", 1)[1]
            item_stmt = (
                select(CanvasItem, CanvasDocument)
                .join(CanvasDocument, CanvasDocument.id == CanvasItem.document_id)
                .where(
                    CanvasItem.id == ensure_canvas_uuid(item_id),
                    CanvasDocument.user_id == ensure_canvas_uuid(user_id),
                )
            )
            row = (await self.execute(item_stmt)).first()
            if not row:
                raise NotFoundError("任务历史不存在", resource_id=history_id, resource_type="task_history")
            return self._assistant_item_to_history_item(row[0], row[1])

        stmt = (
            select(CanvasItemGeneration, CanvasItem, CanvasDocument)
            .join(CanvasItem, CanvasItem.id == CanvasItemGeneration.item_id)
            .join(CanvasDocument, CanvasDocument.id == CanvasItemGeneration.document_id)
            .where(
                CanvasItemGeneration.id == ensure_canvas_uuid(history_id),
                CanvasDocument.user_id == ensure_canvas_uuid(user_id),
            )
        )
        row = (await self.execute(stmt)).first()
        if not row:
            raise NotFoundError("任务历史不存在", resource_id=history_id, resource_type="task_history")
        return self._generation_to_history_item(row[0], row[1], row[2])


class CanvasGenerationService(BaseService):
    def _text_provider_options(self, request: Dict[str, Any]) -> Dict[str, Any]:
        options = request.get("options") or {}
        if not isinstance(options, dict):
            return {}
        provider_options: Dict[str, Any] = {}
        temperature = options.get("temperature")
        if temperature not in (None, ""):
            try:
                provider_options["temperature"] = float(temperature)
            except (TypeError, ValueError):
                raise BusinessLogicError("temperature 参数必须是数字")
        max_tokens = options.get("max_tokens")
        if max_tokens not in (None, ""):
            try:
                provider_options["max_tokens"] = int(max_tokens)
            except (TypeError, ValueError):
                raise BusinessLogicError("max_tokens 参数必须是整数")
        return provider_options

    def _image_provider_options(self, request: Dict[str, Any], api_key: APIKey) -> Dict[str, Any]:
        options = request.get("options") or {}
        if not isinstance(options, dict):
            options = {}
        model = str(request.get("model") or "").lower()
        base_url = str(api_key.base_url or "").lower()
        provider_name = str(api_key.provider or "").lower()
        provider_options: Dict[str, Any] = {}

        aspect_ratio = str(options.get("aspect_ratio") or "").strip()
        image_size = str(options.get("image_size") or options.get("size") or "").strip()
        image_count = options.get("n")
        if provider_name == "custom" and aspect_ratio:
            provider_options["aspect_ratio"] = aspect_ratio
        if image_size:
            provider_options["size"] = image_size
            if provider_name == "custom":
                provider_options["image_size"] = image_size
        if image_count not in (None, ""):
            try:
                provider_options["n"] = max(1, min(int(image_count), 4))
            except (TypeError, ValueError):
                raise BusinessLogicError("图片数量 n 必须是整数")

        if "bigmodel.cn" in base_url or model.startswith(("glm-image", "cogview")):
            if image_size:
                provider_options["size"] = image_size
            provider_options.pop("aspect_ratio", None)
            provider_options.pop("image_size", None)
        return provider_options

    def _video_provider_options(self, request: Dict[str, Any]) -> Dict[str, Any]:
        options = request.get("options") or {}
        if not isinstance(options, dict):
            return {}
        provider_options: Dict[str, Any] = {}
        aspect_ratio = str(options.get("aspect_ratio") or "").strip()
        if aspect_ratio:
            provider_options["aspect_ratio"] = aspect_ratio
        duration = options.get("duration") or options.get("duration_seconds")
        if duration not in (None, ""):
            try:
                duration_seconds = int(duration)
            except (TypeError, ValueError):
                raise BusinessLogicError("视频时长参数必须是整数秒")
            provider_options["duration"] = duration_seconds
            provider_options["duration_seconds"] = duration_seconds
        return provider_options

    def _extract_object_key_from_media_url(self, media_url: Any) -> str:
        return extract_object_key_from_media_url(media_url)

    def _has_successful_video_result(self, generation: CanvasItemGeneration) -> bool:
        payload = generation.result_payload_json or {}
        return bool(payload.get("result_video_object_key"))

    async def prepare_text_generation(self, item_id: str, user_id: str, request: Dict[str, Any]) -> Tuple[CanvasItem, CanvasItemGeneration]:
        return await self._prepare_generation(item_id, user_id, CanvasGenerationType.TEXT.value, request)

    async def prepare_image_generation(self, item_id: str, user_id: str, request: Dict[str, Any]) -> Tuple[CanvasItem, CanvasItemGeneration]:
        return await self._prepare_generation(item_id, user_id, CanvasGenerationType.IMAGE.value, request)

    async def prepare_video_generation(self, item_id: str, user_id: str, request: Dict[str, Any]) -> Tuple[CanvasItem, CanvasItemGeneration]:
        return await self._prepare_generation(item_id, user_id, CanvasGenerationType.VIDEO.value, request)

    async def attach_task(self, generation_id: str, task_id: str) -> Tuple[CanvasItem, CanvasItemGeneration]:
        canvas_service = CanvasService(self.db_session)
        generation = await canvas_service.get_generation(generation_id)
        item = await canvas_service.get_item_by_id(str(generation.item_id))
        await canvas_service.update_generation(
            generation,
            item,
            generation.status or CanvasRunStatus.PENDING.value,
            result_payload={"task_id": task_id},
        )
        return item, generation

    async def process_text_generation(self, generation_id: str) -> Dict[str, Any]:
        generation, item = await self._load_generation_and_item(generation_id, CanvasGenerationType.TEXT.value)
        canvas_service = CanvasService(self.db_session)
        try:
            await canvas_service.update_generation(generation, item, CanvasRunStatus.PROCESSING.value)
            request = generation.request_payload_json or {}
            api_key = await self._resolve_api_key(str(generation.user_id), request, item)
            provider = self._build_provider(api_key)
            text_kwargs = self._text_provider_options(request)
            response = await provider.completions(
                model=request.get("model") or "gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "你是一个专业的中文创作助手。请直接输出适合写入画布节点的正文内容。"},
                    {"role": "user", "content": request["prompt"]},
                ],
                **text_kwargs,
            )
            text = self._extract_completion_text(response).strip()
            if not text:
                raise BusinessLogicError("文本模型未返回可写入内容")
            await canvas_service.update_generation(
                generation,
                item,
                CanvasRunStatus.COMPLETED.value,
                result_payload={
                    "text": text,
                    "provider": api_key.provider,
                    "model": request.get("model"),
                    "options": request.get("options") or {},
                },
            )
            await self.commit()
            return {"generation_id": generation_id, "status": CanvasRunStatus.COMPLETED.value, "text": text}
        except Exception as exc:
            await canvas_service.update_generation(
                generation,
                item,
                CanvasRunStatus.FAILED.value,
                error_message=str(exc),
            )
            await self.commit()
            logger.exception("Canvas text generation failed: %s", generation_id)
            raise

    async def stream_text_generation(self, item_id: str, user_id: str, request: Dict[str, Any]) -> AsyncIterator[str]:
        item, generation = await self.prepare_text_generation(item_id, user_id, request)
        canvas_service = CanvasService(self.db_session)
        accumulated_text = ""

        try:
            await canvas_service.update_generation(generation, item, CanvasRunStatus.PROCESSING.value)
            await self.commit()
            yield self._encode_sse_event(
                "start",
                {
                    "item_id": str(item.id),
                    "generation_id": str(generation.id),
                    "status": CanvasRunStatus.PROCESSING.value,
                },
            )

            request_payload = generation.request_payload_json or {}
            api_key = await self._resolve_api_key(str(generation.user_id), request_payload, item)
            provider = self._build_provider(api_key)
            text_kwargs = self._text_provider_options(request_payload)
            stream = await provider.completions(
                model=request_payload.get("model") or "gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "你是一个专业的中文创作助手。请直接输出适合写入画布节点的正文内容。"},
                    {"role": "user", "content": request_payload["prompt"]},
                ],
                stream=True,
                **text_kwargs,
            )

            async for delta in self._iterate_text_stream(stream):
                if not delta:
                    continue
                accumulated_text += delta
                yield self._encode_sse_event(
                    "delta",
                    {
                        "item_id": str(item.id),
                        "generation_id": str(generation.id),
                        "status": CanvasRunStatus.PROCESSING.value,
                        "delta": delta,
                        "text": accumulated_text,
                    },
                )

            final_text = accumulated_text.strip()
            await canvas_service.update_generation(
                generation,
                item,
                CanvasRunStatus.COMPLETED.value,
                result_payload={
                    "text": final_text,
                    "provider": api_key.provider,
                    "model": request_payload.get("model"),
                    "options": request_payload.get("options") or {},
                },
            )
            await self.commit()
            await self.refresh(item)
            await self.refresh(generation)
            yield self._encode_sse_event(
                "complete",
                {
                    "item_id": str(item.id),
                    "generation_id": str(generation.id),
                    "status": CanvasRunStatus.COMPLETED.value,
                    "text": final_text,
                    "item": canvas_service._serialize_item(item),
                    "generation": self._serialize_generation(generation),
                },
            )
        except Exception as exc:
            await canvas_service.update_generation(
                generation,
                item,
                CanvasRunStatus.FAILED.value,
                error_message=str(exc),
            )
            await self.commit()
            logger.exception("Canvas text stream generation failed: %s", item_id)
            yield self._encode_sse_event(
                "fail",
                {
                    "item_id": str(item.id),
                    "generation_id": str(generation.id),
                    "status": CanvasRunStatus.FAILED.value,
                    "error_message": str(exc),
                },
            )

    async def stream_generation_events(self, generation_id: str, *, poll_interval_seconds: float = 1.0, timeout_seconds: float = 1800.0) -> AsyncIterator[str]:
        generation, item = await self._reload_generation_and_item(generation_id)
        start_payload = await self._resolve_media_urls_in_mapping(
            {
                "item_id": str(item.id),
                "generation_id": str(generation.id),
                "status": generation.status or CanvasRunStatus.PENDING.value,
                "task_id": (generation.result_payload_json or {}).get("task_id"),
            }
        )
        yield self._encode_sse_event(
            "start",
            start_payload,
        )

        last_signature = self._generation_stream_signature(generation)
        elapsed = 0.0
        heartbeat_elapsed = 0.0
        final_statuses = {CanvasRunStatus.COMPLETED.value, CanvasRunStatus.FAILED.value}

        while elapsed <= timeout_seconds:
            if generation.status in final_statuses:
                break

            await asyncio.sleep(poll_interval_seconds)
            elapsed += poll_interval_seconds
            heartbeat_elapsed += poll_interval_seconds
            generation, item = await self._reload_generation_and_item(generation_id)
            signature = self._generation_stream_signature(generation)
            if signature == last_signature and heartbeat_elapsed < 15:
                continue

            heartbeat_elapsed = 0.0
            last_signature = signature
            payload = await self._build_generation_stream_payload(generation, item)
            if generation.status == CanvasRunStatus.COMPLETED.value:
                yield self._encode_sse_event("complete", payload)
                return
            if generation.status == CanvasRunStatus.FAILED.value:
                yield self._encode_sse_event("fail", payload)
                return
            yield self._encode_sse_event("progress", payload)

        generation, item = await self._reload_generation_and_item(generation_id)
        payload = await self._build_generation_stream_payload(generation, item)
        if generation.status == CanvasRunStatus.COMPLETED.value:
            yield self._encode_sse_event("complete", payload)
            return
        if generation.status == CanvasRunStatus.FAILED.value:
            yield self._encode_sse_event("fail", payload)
            return
        yield self._encode_sse_event(
            "fail",
            {
                **payload,
                "status": CanvasRunStatus.FAILED.value,
                "error_message": "生成任务状态流超时，请稍后查看任务状态",
            },
        )

    async def process_image_generation(self, generation_id: str) -> Dict[str, Any]:
        generation, item = await self._load_generation_and_item(generation_id, CanvasGenerationType.IMAGE.value)
        canvas_service = CanvasService(self.db_session)
        try:
            await canvas_service.update_generation(generation, item, CanvasRunStatus.PROCESSING.value)
            request = generation.request_payload_json or {}
            api_key = await self._resolve_api_key(str(generation.user_id), request, item)
            provider = self._build_provider(api_key)
            image_kwargs: Dict[str, Any] = self._image_provider_options(request, api_key)
            if api_key.provider.lower() == "custom":
                options = request.get("options") or {}
                aspect_ratio = str(options.get("aspect_ratio") or "").strip()
                if aspect_ratio and "aspect_ratio" not in image_kwargs:
                    image_kwargs["aspect_ratio"] = aspect_ratio
                reference_images = self._resolve_image_reference_inputs(
                    options.get("style_reference_image_object_key")
                    or options.get("style_reference_image_url")
                    or item.content_json.get("reference_image_object_key")
                    or item.content_json.get("reference_image_url"),
                    options.get("reference_image_object_keys")
                    or options.get("reference_image_urls")
                    or [],
                )
                if reference_images:
                    image_kwargs["reference_images"] = reference_images
            response = await provider.generate_image(
                prompt=request["prompt"],
                model=request.get("model"),
                **image_kwargs,
            )
            image_assets = await self._resolve_image_results(response, str(generation.user_id))
            batch_id = str(uuid.uuid4())
            result_images = [
                {
                    "object_key": asset.get("object_key"),
                    "index": index + 1,
                    "batch_id": batch_id,
                }
                for index, asset in enumerate(image_assets)
                if asset.get("object_key")
            ]
            if not result_images:
                raise BusinessLogicError("No usable image found in generation result")
            created_items, created_connections = await self._create_batch_image_items(
                canvas_service,
                item,
                result_images,
                request,
                str(generation.user_id),
            )
            await canvas_service.update_generation(
                generation,
                item,
                CanvasRunStatus.COMPLETED.value,
                result_payload={
                    "result_image_object_key": result_images[0].get("object_key"),
                    "result_images": result_images,
                    "result_count": len(result_images),
                    "batch_id": batch_id,
                    "provider": api_key.provider,
                    "model": request.get("model"),
                    "options": request.get("options") or {},
                    "created_item_ids": [str(created.id) for created in created_items],
                    "created_connection_ids": [str(created.id) for created in created_connections],
                },
            )
            await self.commit()
            return {
                "generation_id": generation_id,
                "status": CanvasRunStatus.COMPLETED.value,
                "result_image_object_key": result_images[0].get("object_key"),
                "result_images": result_images,
                "created_item_ids": [str(created.id) for created in created_items],
                "created_connection_ids": [str(created.id) for created in created_connections],
            }
        except Exception as exc:
            await canvas_service.update_generation(
                generation,
                item,
                CanvasRunStatus.FAILED.value,
                error_message=str(exc),
            )
            await self.commit()
            logger.exception("Canvas image generation failed: %s", generation_id)
            raise

    async def process_video_generation(self, generation_id: str) -> Dict[str, Any]:
        generation, item = await self._load_generation_and_item(generation_id, CanvasGenerationType.VIDEO.value)
        canvas_service = CanvasService(self.db_session)
        try:
            await canvas_service.update_generation(generation, item, CanvasRunStatus.PROCESSING.value)
            request = generation.request_payload_json or {}
            api_key = await self._resolve_api_key(str(generation.user_id), request, item)
            provider_name = api_key.provider.lower()
            base_url = str(api_key.base_url or "").lower()
            if provider_name not in {"vectorengine", "custom"}:
                raise BusinessLogicError("当前 API Key 不支持视频生成")
            if provider_name == "custom" and "bigmodel.cn" not in base_url:
                raise BusinessLogicError("当前自定义 API Key 的视频 endpoint 未验证：返回 HTML 通常表示路径/上游不兼容。请使用 BigModel direct 视频 Key。")

            provider = VectorEngineProvider(
                api_key=api_key.get_api_key(),
                base_url=api_key.base_url or "https://api.vectorengine.ai/v1",
            )
            options = request.get("options") or {}
            reference_images = options.get("reference_image_urls") or item.content_json.get("reference_image_urls") or []
            provider_images = await self._resolve_video_reference_images(
                reference_images,
                prefer_public_urls=provider._is_bigmodel(),
            )
            provider_options = {
                key: value
                for key, value in self._video_provider_options(request).items()
                if key not in {"reference_image_urls", "reference_text_ids"}
            }
            response = await provider.create_video(
                prompt=request["prompt"],
                images=provider_images,
                model=request.get("model") or "veo_3_1-fast",
                **provider_options,
            )

            provider_task_id = response.get("id") or response.get("task_id")
            direct_video_url = self._extract_video_url(response)
            if direct_video_url:
                stored_video_asset = await self._store_remote_video(direct_video_url, str(generation.user_id))
                await canvas_service.update_generation(
                    generation,
                    item,
                    CanvasRunStatus.COMPLETED.value,
                    result_payload={
                        "provider_task_id": provider_task_id,
                        "provider_response": response,
                        "result_video_object_key": stored_video_asset.get("object_key"),
                        "provider": api_key.provider,
                        "model": request.get("model"),
                        "options": request.get("options") or {},
                    },
                )
                await self.commit()
                return {"generation_id": generation_id, "status": CanvasRunStatus.COMPLETED.value, "result_video_object_key": stored_video_asset.get("object_key")}

            if not provider_task_id:
                raise BusinessLogicError("视频任务已提交，但未返回 provider task id")

            await canvas_service.update_generation(
                generation,
                item,
                CanvasRunStatus.PROCESSING.value,
                result_payload={
                    "provider_task_id": provider_task_id,
                    "provider_response": response,
                    "provider": api_key.provider,
                    "model": request.get("model"),
                    "options": request.get("options") or {},
                },
            )
            await self.commit()

            try:
                video_url = await self._poll_video_result(provider, provider_task_id)
            except BusinessLogicError as exc:
                if "超时" not in str(exc):
                    raise
                logger.warning("Canvas video generation kept processing after provider timeout: %s", generation_id)
                await canvas_service.update_generation(
                    generation,
                    item,
                    CanvasRunStatus.PROCESSING.value,
                    result_payload={
                        "provider_task_id": provider_task_id,
                        "provider_response": response,
                        "timeout_waiting": True,
                        "provider": api_key.provider,
                        "model": request.get("model"),
                        "options": request.get("options") or {},
                    },
                    error_message=None,
                )
                await self.commit()
                return {
                    "generation_id": generation_id,
                    "status": CanvasRunStatus.PROCESSING.value,
                    "provider_task_id": provider_task_id,
                    "timeout_waiting": True,
                }
            stored_video_asset = await self._store_remote_video(video_url, str(generation.user_id))
            await canvas_service.update_generation(
                generation,
                item,
                CanvasRunStatus.COMPLETED.value,
                result_payload={
                    "provider_task_id": provider_task_id,
                    "result_video_object_key": stored_video_asset.get("object_key"),
                    "provider": api_key.provider,
                    "model": request.get("model"),
                    "options": request.get("options") or {},
                },
            )
            await self.commit()
            return {"generation_id": generation_id, "status": CanvasRunStatus.COMPLETED.value, "result_video_object_key": stored_video_asset.get("object_key")}
        except Exception as exc:
            if self._has_successful_video_result(generation):
                logger.warning("Canvas video generation error ignored because result already exists: %s", generation_id)
                await canvas_service.update_generation(
                    generation,
                    item,
                    CanvasRunStatus.COMPLETED.value,
                    error_message=None,
                )
                await self.commit()
                return {
                    "generation_id": generation_id,
                    "status": CanvasRunStatus.COMPLETED.value,
                    "result_video_object_key": (generation.result_payload_json or {}).get("result_video_object_key"),
                }
            await canvas_service.update_generation(
                generation,
                item,
                CanvasRunStatus.FAILED.value,
                error_message=str(exc),
            )
            await self.commit()
            logger.exception("Canvas video generation failed: %s", generation_id)
            raise

    async def get_video_task_status(self, document_id: str, item_id: str, generation_id: str, user_id: str) -> Dict[str, Any]:
        canvas_service = CanvasService(self.db_session)
        item, generation = await canvas_service.get_item_generation(item_id, generation_id, user_id)
        if str(item.document_id) != str(ensure_canvas_uuid(document_id)):
            raise NotFoundError("画布节点不存在", resource_id=item_id, resource_type="canvas_item")
        self._ensure_item_type_matches(item, CanvasGenerationType.VIDEO.value)

        request = generation.request_payload_json or {}
        result_payload = generation.result_payload_json or {}
        provider_task_id = str(result_payload.get("provider_task_id") or "").strip()
        if not provider_task_id:
            local_task_id = str(result_payload.get("task_id") or "").strip()
            if local_task_id and not is_likely_celery_task_id(local_task_id, generation_id):
                provider_task_id = local_task_id

        result_video_object_key = str((generation.result_payload_json or {}).get("result_video_object_key") or "").strip()
        if generation.status == CanvasRunStatus.COMPLETED.value and result_video_object_key:
            return {
                "task_id": str(generation.id),
                "provider_task_id": provider_task_id or None,
                "status": generation.status,
                "result_video_object_key": result_video_object_key,
                "error_message": generation.error_message,
                "provider_payload": generation.result_payload_json or {},
                "item": item,
            }

        if not provider_task_id:
            return {
                "task_id": str(generation.id),
                "provider_task_id": None,
                "status": generation.status,
                "result_video_object_key": result_video_object_key or None,
                "error_message": generation.error_message,
                "provider_payload": generation.result_payload_json or {},
                "item": item,
            }

        api_key = await self._resolve_api_key(user_id, request, item)
        provider = VectorEngineProvider(
            api_key=api_key.get_api_key(),
            base_url=api_key.base_url or "https://api.vectorengine.ai/v1",
        )
        try:
            status_payload = await self._fetch_video_status_payload(provider, provider_task_id)
        except Exception as exc:
            logger.warning("Canvas video status fetch failed but generation is kept alive: %s", exc)
            provider_payload = dict(generation.result_payload_json or {})
            provider_payload.update(
                {
                    "transient_status_issue": True,
                    "status_fetch_error": str(exc),
                }
            )
            return {
                "task_id": str(generation.id),
                "provider_task_id": provider_task_id,
                "status": generation.status,
                "result_video_object_key": result_video_object_key or None,
                "error_message": generation.error_message,
                "provider_payload": provider_payload,
                "item": item,
            }
        provider_status = str(status_payload.get("status") or status_payload.get("state") or generation.status or "").lower()
        provider_video_url = self._extract_video_url(status_payload)
        if not provider_video_url and provider_status in {"completed", "succeeded", "success", "done"}:
            try:
                content_payload = await self._fetch_video_content_payload(provider, provider_task_id)
            except Exception as exc:
                logger.warning("Canvas video content fetch failed after completion (task=%s): %s", provider_task_id, exc)
                content_payload = None
            if content_payload:
                provider_video_url = self._extract_video_url(content_payload)
                if provider_video_url:
                    status_payload = {**status_payload, "content": content_payload}

        normalized_status = self._normalize_video_provider_status(provider_status)
        if provider_video_url and normalized_status == CanvasRunStatus.COMPLETED.value:
            stored_video_asset = await self._store_remote_video(provider_video_url, user_id)
            await canvas_service.update_generation(
                generation,
                item,
                CanvasRunStatus.COMPLETED.value,
                result_payload={
                    "provider_task_id": provider_task_id,
                    "provider_response": status_payload,
                    "result_video_object_key": stored_video_asset.get("object_key"),
                },
            )
            await self.commit()
            result_video_object_key = stored_video_asset.get("object_key")
        elif normalized_status == CanvasRunStatus.FAILED.value:
            await canvas_service.update_generation(
                generation,
                item,
                CanvasRunStatus.FAILED.value,
                result_payload={
                    "provider_task_id": provider_task_id,
                    "provider_response": status_payload,
                },
                error_message=status_payload.get("message") or status_payload.get("error") or generation.error_message,
            )
            await self.commit()
        elif normalized_status != generation.status:
            await canvas_service.update_generation(
                generation,
                item,
                normalized_status,
                result_payload={
                    "provider_task_id": provider_task_id,
                    "provider_response": status_payload,
                },
            )
            await self.commit()

        await self.refresh(item)
        await self.refresh(generation)
        return {
            "task_id": str(generation.id),
            "provider_task_id": provider_task_id,
            "status": generation.status,
            "result_video_object_key": (generation.result_payload_json or {}).get("result_video_object_key"),
            "error_message": generation.error_message,
            "provider_payload": generation.result_payload_json or {},
            "item": item,
        }

    async def upload_video_override(self, document_id: str, item_id: str, user_id: str, file: UploadFile) -> Dict[str, Any]:
        canvas_service = CanvasService(self.db_session)
        item = await canvas_service.get_item(item_id, user_id)
        if str(item.document_id) != str(ensure_canvas_uuid(document_id)):
            raise NotFoundError("画布节点不存在", resource_id=item_id, resource_type="canvas_item")
        self._ensure_item_type_matches(item, CanvasGenerationType.VIDEO.value)

        storage_client = await get_storage_client()
        storage_result = await storage_client.upload_file(
            user_id=user_id,
            file=file,
            metadata={
                "user_id": user_id,
                "canvas_document_id": document_id,
                "canvas_item_id": item_id,
                "file_type": "video",
            },
        )

        object_key = storage_result["object_key"]
        item.content_json = {
            **(item.content_json or {}),
            "result_video_object_key": object_key,
        }
        item.last_run_status = CanvasRunStatus.COMPLETED.value
        item.last_run_error = None
        item.last_output_json = {
            **(item.last_output_json or {}),
            "result_video_object_key": object_key,
        }
        await self.flush()
        await self.refresh(item)
        return {"item": item, "storage_info": storage_result}

    async def _prepare_generation(
        self,
        item_id: str,
        user_id: str,
        generation_type: str,
        request: Dict[str, Any],
    ) -> Tuple[CanvasItem, CanvasItemGeneration]:
        canvas_service = CanvasService(self.db_session)
        item = await canvas_service.get_item(item_id, user_id)
        self._ensure_item_type_matches(item, generation_type)
        normalized_request = await self._normalize_request(item, user_id, generation_type, request)
        generation = await canvas_service.create_pending_generation(
            item,
            user_id,
            generation_type,
            normalized_request,
        )
        return item, generation

    async def _normalize_request(
        self,
        item: CanvasItem,
        user_id: str,
        generation_type: str,
        request: Dict[str, Any],
    ) -> Dict[str, Any]:
        prompt_tokens = sanitize_prompt_tokens_for_storage(
            self._normalize_prompt_tokens(request.get("prompt_tokens") or item.content_json.get("promptTokens") or [])
        )
        resolved_mentions = self._normalize_resolved_mentions(
            request.get("resolved_mentions")
            or item.content_json.get("resolvedMentions")
            or item.content_json.get("resolved_mentions")
            or []
        )
        prompt_plain_text = (
            request.get("prompt_plain_text")
            or item.content_json.get("promptPlainText")
            or item.content_json.get("prompt_plain_text")
            or request.get("prompt")
            or item.content_json.get("prompt")
            or ""
        ).strip()
        prompt = self._build_prompt_text(prompt_tokens, resolved_mentions, fallback=prompt_plain_text)
        if not prompt:
            type_label = {
                CanvasGenerationType.TEXT.value: "文本",
                CanvasGenerationType.IMAGE.value: "图片",
                CanvasGenerationType.VIDEO.value: "视频",
            }[generation_type]
            raise BusinessLogicError(f"{type_label}节点缺少 prompt")

        api_key_id = request.get("api_key_id") or item.generation_config_json.get("api_key_id")
        if not api_key_id:
            raise BusinessLogicError("缺少 api_key_id")

        model = request.get("model") or item.generation_config_json.get("model")
        options = dict(item.content_json.get("options") or {})
        options.update(request.get("options") or {})

        resolved_mentions = self._sanitize_resolved_mentions_for_storage(resolved_mentions)
        normalized = {
            "prompt": prompt,
            "prompt_plain_text": prompt_plain_text,
            "prompt_tokens": prompt_tokens,
            "resolved_mentions": resolved_mentions,
            "api_key_id": str(api_key_id),
            "model": model,
            "options": options,
        }

        reference_image_object_keys = self._collect_reference_image_object_keys(prompt_tokens, resolved_mentions)
        reference_text_ids = self._collect_reference_text_ids(resolved_mentions)
        style_reference_image_object_key = self._resolve_style_reference_image_object_key(item, request, options)

        if generation_type == CanvasGenerationType.IMAGE.value:
            if reference_image_object_keys:
                normalized["options"]["reference_image_object_keys"] = reference_image_object_keys
            if style_reference_image_object_key:
                normalized["options"]["style_reference_image_object_key"] = style_reference_image_object_key

        if generation_type == CanvasGenerationType.VIDEO.value:
            video_reference_object_keys = (
                options.get("reference_image_object_keys")
                or reference_image_object_keys
                or []
            )
            reference_image_urls = (
                options.get("reference_image_urls")
                or self._collect_reference_image_urls(prompt_tokens, resolved_mentions)
                or item.content_json.get("reference_image_urls")
                or []
            )
            if video_reference_object_keys:
                normalized["options"]["reference_image_object_keys"] = video_reference_object_keys
                reference_image_urls = [
                    absolute_public_media_url_for_object_key(object_key)
                    for object_key in video_reference_object_keys
                ]
            normalized["options"]["reference_image_urls"] = reference_image_urls
            normalized["options"]["reference_text_ids"] = (
                options.get("reference_text_ids")
                or reference_text_ids
                or item.content_json.get("reference_text_ids")
                or []
            )

        return normalized

    def _normalize_prompt_tokens(self, raw_tokens: Any) -> List[Dict[str, Any]]:
        if not isinstance(raw_tokens, list):
            return []
        return [dict(token) for token in raw_tokens if isinstance(token, dict)]

    def _normalize_resolved_mentions(self, raw_mentions: Any) -> List[Dict[str, Any]]:
        if not isinstance(raw_mentions, list):
            return []
        return [dict(mention) for mention in raw_mentions if isinstance(mention, dict)]

    def _build_prompt_text(
        self,
        prompt_tokens: List[Dict[str, Any]],
        resolved_mentions: List[Dict[str, Any]],
        *,
        fallback: str = "",
    ) -> str:
        if not prompt_tokens:
            return self._normalize_prompt_spacing(fallback)

        mention_by_id = {}
        mention_by_node_key = {}
        for mention in resolved_mentions:
            if str(mention.get("status") or "").strip() != "resolved":
                continue
            mention_id = str(mention.get("mentionId") or "").strip()
            if mention_id:
                mention_by_id[mention_id] = mention
            node_key = self._build_node_key(mention.get("nodeType"), mention.get("nodeId"))
            if node_key != ":" and node_key not in mention_by_node_key:
                mention_by_node_key[node_key] = mention

        sections: List[str] = []
        for token in prompt_tokens:
            token_type = str(token.get("type") or "").strip()
            if token_type == "text":
                sections.append(str(token.get("text") or ""))
                continue
            if token_type != "mention":
                continue

            mention = None
            mention_id = str(token.get("mentionId") or "").strip()
            if mention_id:
                mention = mention_by_id.get(mention_id)
            if mention is None:
                mention = mention_by_node_key.get(self._build_node_key(token.get("nodeType"), token.get("nodeId")))
            if mention is None:
                sections.append(self._format_raw_mention_title(token))
                continue

            node_type = str(mention.get("nodeType") or "").strip()
            if node_type == CanvasItemType.IMAGE.value:
                continue
            if node_type == CanvasItemType.TEXT.value:
                inline_text = self._build_resolved_text_inline_content(mention)
                if inline_text:
                    sections.append(inline_text)
                continue
            sections.append(self._format_raw_mention_title(token))

        return self._normalize_prompt_spacing("".join(sections))

    def _collect_reference_image_urls(
        self,
        prompt_tokens: List[Dict[str, Any]],
        resolved_mentions: List[Dict[str, Any]],
        *,
        limit: int = REFERENCE_IMAGE_LIMIT,
    ) -> List[str]:
        if not prompt_tokens or not resolved_mentions:
            return []

        mention_by_id = {}
        mention_by_node_key = {}
        for mention in resolved_mentions:
            if str(mention.get("status") or "").strip() != "resolved":
                continue
            mention_id = str(mention.get("mentionId") or "").strip()
            if mention_id:
                mention_by_id[mention_id] = mention
            node_key = self._build_node_key(mention.get("nodeType"), mention.get("nodeId"))
            if node_key != ":" and node_key not in mention_by_node_key:
                mention_by_node_key[node_key] = mention

        results: List[str] = []
        seen_node_ids = set()
        for token in prompt_tokens:
            if str(token.get("type") or "").strip() != "mention":
                continue
            mention = None
            mention_id = str(token.get("mentionId") or "").strip()
            if mention_id:
                mention = mention_by_id.get(mention_id)
            if mention is None:
                mention = mention_by_node_key.get(self._build_node_key(token.get("nodeType"), token.get("nodeId")))
            if mention is None:
                continue
            if str(mention.get("nodeType") or "").strip() != CanvasItemType.IMAGE.value:
                continue

            node_id = str(mention.get("nodeId") or "").strip()
            if node_id and node_id in seen_node_ids:
                continue

            resolved_content = mention.get("resolvedContent") or {}
            if not isinstance(resolved_content, dict):
                resolved_content = {}
            image_ref = str(
                resolved_content.get("object_key")
                or resolved_content.get("objectKey")
                or resolved_content.get("url")
                or ""
            ).strip()
            if not image_ref:
                continue

            results.append(image_ref)
            if node_id:
                seen_node_ids.add(node_id)
            if len(results) >= limit:
                break
        return results

    def _collect_reference_image_object_keys(
        self,
        prompt_tokens: List[Dict[str, Any]],
        resolved_mentions: List[Dict[str, Any]],
        *,
        limit: int = REFERENCE_IMAGE_LIMIT,
    ) -> List[str]:
        if not prompt_tokens or not resolved_mentions:
            return []

        mention_by_id = {}
        mention_by_node_key = {}
        for mention in resolved_mentions:
            if str(mention.get("status") or "").strip() != "resolved":
                continue
            mention_id = str(mention.get("mentionId") or "").strip()
            if mention_id:
                mention_by_id[mention_id] = mention
            node_key = self._build_node_key(mention.get("nodeType"), mention.get("nodeId"))
            if node_key != ":" and node_key not in mention_by_node_key:
                mention_by_node_key[node_key] = mention

        results: List[str] = []
        seen_node_ids = set()
        for token in prompt_tokens:
            if str(token.get("type") or "").strip() != "mention":
                continue
            mention = None
            mention_id = str(token.get("mentionId") or "").strip()
            if mention_id:
                mention = mention_by_id.get(mention_id)
            if mention is None:
                mention = mention_by_node_key.get(self._build_node_key(token.get("nodeType"), token.get("nodeId")))
            if mention is None:
                continue
            if str(mention.get("nodeType") or "").strip() != CanvasItemType.IMAGE.value:
                continue

            node_id = str(mention.get("nodeId") or "").strip()
            if node_id and node_id in seen_node_ids:
                continue

            resolved_content = mention.get("resolvedContent") or {}
            if not isinstance(resolved_content, dict):
                resolved_content = {}
            object_key = str(
                resolved_content.get("object_key")
                or resolved_content.get("objectKey")
                or ""
            ).strip()
            if not object_key:
                continue

            results.append(object_key)
            if node_id:
                seen_node_ids.add(node_id)
            if len(results) >= limit:
                break
        return results

    def _collect_reference_text_ids(self, resolved_mentions: List[Dict[str, Any]]) -> List[str]:
        text_ids: List[str] = []
        seen = set()
        for mention in resolved_mentions:
            if str(mention.get("status") or "").strip() != "resolved":
                continue
            if str(mention.get("nodeType") or "").strip() != CanvasItemType.TEXT.value:
                continue
            node_id = str(mention.get("nodeId") or "").strip()
            if not node_id or node_id in seen:
                continue
            text_ids.append(node_id)
            seen.add(node_id)
        return text_ids

    def _build_node_key(self, node_type: Any, node_id: Any) -> str:
        return f"{str(node_type or '').strip()}:{str(node_id or '').strip()}"

    def _format_raw_mention_title(self, token: Dict[str, Any]) -> str:
        title = str(token.get("nodeTitleSnapshot") or token.get("nodeId") or "").strip()
        return f"@{title}" if title else ""

    def _build_resolved_text_inline_content(self, mention: Dict[str, Any]) -> str:
        resolved_content = mention.get("resolvedContent") or {}
        if not isinstance(resolved_content, dict):
            resolved_content = {}
        return self._sanitize_reference_text(str(resolved_content.get("text") or ""))

    def _sanitize_resolved_mentions_for_storage(self, resolved_mentions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return sanitize_resolved_mentions_for_storage(resolved_mentions)

    def _resolve_style_reference_image_object_key(
        self,
        item: CanvasItem,
        request: Dict[str, Any],
        options: Dict[str, Any],
    ) -> str:
        candidates = (
            options.get("style_reference_image_object_key"),
            options.get("style_reference_image_url"),
            request.get("style_reference_image_object_key"),
            request.get("style_reference_image_url"),
            item.content_json.get("reference_image_object_key"),
            item.content_json.get("reference_image_url"),
            item.content_json.get("reference_image_key"),
        )
        for candidate in candidates:
            value = str(candidate or "").strip()
            if value:
                return value
        return ""

    def _resolve_image_reference_inputs(self, style_reference: Any, references: List[str]) -> List[str]:
        resolved: List[str] = []
        for candidate in [style_reference, *(references or [])]:
            value = str(candidate or "").strip()
            if not value or value in resolved:
                continue
            resolved.append(value)
        return resolved

    def _sanitize_reference_text(self, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = PROMPT_BREAK_TAG_PATTERN.sub("\n", text)
        text = PROMPT_LIST_ITEM_PATTERN.sub("- ", text)
        text = PROMPT_LIST_ITEM_CLOSE_PATTERN.sub("\n", text)
        text = PROMPT_BLOCK_TAG_PATTERN.sub("\n", text)
        text = PROMPT_HTML_TAG_PATTERN.sub("", text)
        text = html.unescape(text)

        normalized_lines: List[str] = []
        for line in text.split("\n"):
            trimmed_line = PROMPT_SPACE_PATTERN.sub(" ", line).strip()
            if not trimmed_line:
                if normalized_lines and normalized_lines[-1] != "":
                    normalized_lines.append("")
                continue
            normalized_lines.append(trimmed_line)

        normalized = "\n".join(normalized_lines).strip()
        normalized = PROMPT_BLANK_LINE_PATTERN.sub("\n\n", normalized)
        if len(normalized) <= REFERENCE_TEXT_LIMIT:
            return normalized
        return normalized[:REFERENCE_TEXT_LIMIT].rstrip() + "..."

    def _normalize_prompt_spacing(self, value: str) -> str:
        text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
        text = PROMPT_SPACE_PATTERN.sub(" ", text)
        text = text.replace(" \n", "\n").replace("\n ", "\n")
        text = PROMPT_BLANK_LINE_PATTERN.sub("\n\n", text)
        return text.strip()

    def _ensure_item_type_matches(self, item: CanvasItem, generation_type: str) -> None:
        expected = {
            CanvasGenerationType.TEXT.value: CanvasItemType.TEXT.value,
            CanvasGenerationType.IMAGE.value: CanvasItemType.IMAGE.value,
            CanvasGenerationType.VIDEO.value: CanvasItemType.VIDEO.value,
        }[generation_type]
        if item.item_type != expected:
            raise BusinessLogicError(f"该节点不是{generation_type}节点")

    async def _load_generation_and_item(self, generation_id: str, generation_type: str) -> Tuple[CanvasItemGeneration, CanvasItem]:
        canvas_service = CanvasService(self.db_session)
        generation = await canvas_service.get_generation(generation_id)
        item = await canvas_service.get_item_by_id(str(generation.item_id))
        if generation.generation_type != generation_type:
            raise BusinessLogicError("节点生成记录类型不匹配")
        return generation, item

    async def _reload_generation_and_item(self, generation_id: str) -> Tuple[CanvasItemGeneration, CanvasItem]:
        generation_stmt = (
            select(CanvasItemGeneration)
            .where(CanvasItemGeneration.id == ensure_canvas_uuid(generation_id))
            .execution_options(populate_existing=True)
        )
        generation = (await self.execute(generation_stmt)).scalar_one_or_none()
        if not generation:
            raise NotFoundError("节点生成记录不存在", resource_id=generation_id, resource_type="canvas_generation")

        item_stmt = (
            select(CanvasItem)
            .where(CanvasItem.id == generation.item_id)
            .execution_options(populate_existing=True)
        )
        item = (await self.execute(item_stmt)).scalar_one_or_none()
        if not item:
            raise NotFoundError("画布节点不存在", resource_id=str(generation.item_id), resource_type="canvas_item")
        return generation, item

    async def _resolve_api_key(self, user_id: str, request: Dict[str, Any], item: CanvasItem) -> APIKey:
        api_key_id = request.get("api_key_id") or item.generation_config_json.get("api_key_id")
        if not api_key_id:
            raise BusinessLogicError("缺少 api_key_id")
        service = APIKeyService(self.db_session)
        return await service.get_api_key_by_id(str(api_key_id), str(user_id))

    def _build_provider(self, api_key: APIKey):
        return ProviderFactory.create(
            provider=api_key.provider,
            api_key=api_key.get_api_key(),
            max_concurrency=5,
            base_url=api_key.base_url if api_key.base_url else None,
        )

    async def _iterate_text_stream(self, stream: Any) -> AsyncIterator[str]:
        if hasattr(stream, "__aiter__"):
            async for chunk in stream:
                delta = self._extract_text_delta(chunk)
                if delta:
                    yield delta
            return

        fallback_text = self._extract_completion_text(stream)
        if fallback_text:
            yield fallback_text

    def _extract_text_delta(self, chunk: Any) -> str:
        if isinstance(chunk, str):
            return chunk
        choices = chunk.get("choices") if isinstance(chunk, dict) else getattr(chunk, "choices", None)
        if not choices:
            return ""
        choice = choices[0]
        delta = choice.get("delta") if isinstance(choice, dict) else getattr(choice, "delta", None)
        if delta is None:
            return ""
        content = delta.get("content") if isinstance(delta, dict) else getattr(delta, "content", None)
        return self._normalize_completion_content(content)

    def _extract_completion_text(self, response: Any) -> str:
        if isinstance(response, str):
            return response
        choices = response.get("choices") if isinstance(response, dict) else getattr(response, "choices", None)
        if not choices:
            return ""
        choice = choices[0]
        message = choice.get("message") if isinstance(choice, dict) else getattr(choice, "message", None)
        if message is None:
            return ""
        content = message.get("content") if isinstance(message, dict) else getattr(message, "content", None)
        return self._normalize_completion_content(content).strip()

    def _normalize_completion_content(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: List[str] = []
            for entry in content:
                if isinstance(entry, str):
                    parts.append(entry)
                    continue
                if not isinstance(entry, dict):
                    continue
                text_value = entry.get("text")
                if isinstance(text_value, dict):
                    text_value = text_value.get("value") or text_value.get("text")
                if text_value:
                    parts.append(str(text_value))
                    continue
                nested_content = entry.get("content")
                if nested_content:
                    parts.append(str(nested_content))
            return "".join(parts)
        return str(content or "")

    def _serialize_generation(self, generation: CanvasItemGeneration) -> Dict[str, Any]:
        return {
            **generation.to_dict(),
            "request_payload": generation.request_payload_json,
            "result_payload": generation.result_payload_json,
        }

    def _generation_stream_signature(self, generation: CanvasItemGeneration) -> str:
        return json.dumps(
            {
                "status": generation.status,
                "result_payload": generation.result_payload_json or {},
                "error_message": generation.error_message,
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )

    async def _build_generation_stream_payload(self, generation: CanvasItemGeneration, item: CanvasItem) -> Dict[str, Any]:
        result_payload = generation.result_payload_json or {}
        payload = {
            "item_id": str(item.id),
            "generation_id": str(generation.id),
            "status": generation.status,
            "task_id": result_payload.get("task_id"),
            "provider_task_id": result_payload.get("provider_task_id"),
            "provider_payload": result_payload.get("provider_response") or result_payload,
            "error_message": generation.error_message,
        }

        if generation.status == CanvasRunStatus.COMPLETED.value:
            payload.update(
                {
                    "item": await self._serialize_item_for_response(item),
                    "generation": await self._serialize_generation_for_response(generation),
                }
            )

        if result_payload.get("result_image_object_key"):
            payload["result_image_object_key"] = result_payload["result_image_object_key"]
        if result_payload.get("result_images"):
            payload["result_images"] = result_payload["result_images"]
            payload["result_count"] = result_payload.get("result_count") or len(result_payload.get("result_images") or [])
        if result_payload.get("created_item_ids"):
            created_items = await self._load_items_by_ids(result_payload.get("created_item_ids") or [])
            payload["created_items"] = [
                await self._serialize_item_for_response(created_item)
                for created_item in created_items
            ]
        if result_payload.get("created_connection_ids"):
            created_connections = await self._load_connections_by_ids(result_payload.get("created_connection_ids") or [])
            payload["created_connections"] = [
                self._serialize_connection_for_response(created_connection)
                for created_connection in created_connections
            ]
        if result_payload.get("result_video_object_key"):
            payload["result_video_object_key"] = result_payload["result_video_object_key"]
        if result_payload.get("text"):
            payload["text"] = result_payload["text"]

        return await self._resolve_media_urls_in_mapping(payload)

    async def _load_items_by_ids(self, item_ids: List[str]) -> List[CanvasItem]:
        normalized_ids = [ensure_canvas_uuid(item_id) for item_id in item_ids if str(item_id or "").strip()]
        if not normalized_ids:
            return []
        stmt = select(CanvasItem).where(CanvasItem.id.in_(normalized_ids))
        rows = list((await self.execute(stmt)).scalars().all())
        by_id = {str(row.id): row for row in rows}
        return [by_id[str(item_id)] for item_id in normalized_ids if str(item_id) in by_id]

    async def _load_connections_by_ids(self, connection_ids: List[str]) -> List[CanvasConnection]:
        normalized_ids = [ensure_canvas_uuid(connection_id) for connection_id in connection_ids if str(connection_id or "").strip()]
        if not normalized_ids:
            return []
        stmt = select(CanvasConnection).where(CanvasConnection.id.in_(normalized_ids))
        rows = list((await self.execute(stmt)).scalars().all())
        by_id = {str(row.id): row for row in rows}
        return [by_id[str(connection_id)] for connection_id in normalized_ids if str(connection_id) in by_id]

    def _serialize_connection_for_response(self, connection: CanvasConnection) -> Dict[str, Any]:
        return {
            "id": str(connection.id),
            "source_item_id": str(connection.source_item_id),
            "target_item_id": str(connection.target_item_id),
            "source_handle": connection.source_handle,
            "target_handle": connection.target_handle,
        }

    def _encode_sse_event(self, event_name: str, payload: Dict[str, Any]) -> str:
        return f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"

    async def _serialize_item_for_response(self, item: CanvasItem) -> Dict[str, Any]:
        serialized = CanvasService(self.db_session)._serialize_item(item)
        serialized["content"] = await self._resolve_media_urls_in_mapping(serialized.get("content") or {})
        serialized["last_output"] = await self._resolve_media_urls_in_mapping(serialized.get("last_output") or {})
        return serialized

    async def _serialize_generation_for_response(self, generation: CanvasItemGeneration) -> Dict[str, Any]:
        serialized = self._serialize_generation(generation)
        serialized["result_payload"] = await self._resolve_media_urls_in_mapping(serialized.get("result_payload") or {})
        return serialized

    async def _resolve_media_urls_in_mapping(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            return {}
        resolved = dict(payload)
        field_pairs = (
            ("result_image_object_key", "result_image_url"),
            ("reference_image_object_key", "reference_image_url"),
            ("result_video_object_key", "result_video_url"),
        )
        for object_key_field, url_field in field_pairs:
            object_key = str(resolved.get(object_key_field) or "").strip()
            if object_key:
                resolved[url_field] = media_url_for_object_key(object_key)
        if isinstance(resolved.get("result_images"), list):
            resolved["result_images"] = [
                {
                    **entry,
                    "preview_url": media_url_for_object_key(entry.get("object_key"), "preview"),
                    "download_url": media_url_for_object_key(entry.get("object_key"), "download"),
                }
                if isinstance(entry, dict) and entry.get("object_key")
                else entry
                for entry in resolved["result_images"]
            ]
        return resolved

    async def _create_batch_image_items(
        self,
        canvas_service: CanvasService,
        source_item: CanvasItem,
        result_images: List[Dict[str, Any]],
        request: Dict[str, Any],
        user_id: str,
    ) -> Tuple[List[CanvasItem], List[CanvasConnection]]:
        created_items = [source_item]
        created_connections: List[CanvasConnection] = []
        if len(result_images) <= 1:
            return created_items, created_connections

        source_connection_stmt = select(CanvasConnection).where(
            CanvasConnection.document_id == source_item.document_id,
            CanvasConnection.target_item_id == source_item.id,
        ).order_by(CanvasConnection.created_at)
        source_connection = (await self.execute(source_connection_stmt)).scalars().first()
        relation_source_id = source_connection.source_item_id if source_connection else None
        base_x = float(source_item.position_x or 0)
        base_y = float(source_item.position_y or 0)
        width = float(source_item.width or 360)
        height = float(source_item.height or 260)
        gap_x = 56
        gap_y = 44
        columns = 2

        for index, image_entry in enumerate(result_images[1:], start=2):
            offset_index = index - 1
            column = offset_index % columns
            row = offset_index // columns
            object_key = image_entry.get("object_key")
            item = await canvas_service.create_item(
                str(source_item.document_id),
                user_id,
                {
                    "item_type": CanvasItemType.IMAGE.value,
                    "title": f"图片结果 {index}",
                    "position_x": base_x + column * (width + gap_x),
                    "position_y": base_y + row * (height + gap_y),
                    "width": width,
                    "height": height,
                    "z_index": int(source_item.z_index or 0) + index,
                    "content": {
                        "prompt": request.get("prompt") or "",
                        "promptTokens": request.get("prompt_tokens") or [],
                        "result_image_object_key": object_key,
                        "batch_id": image_entry.get("batch_id"),
                        "batch_index": index,
                    },
                    "generation_config": dict(source_item.generation_config_json or {}),
                    "last_run_status": CanvasRunStatus.COMPLETED.value,
                    "last_output": {
                        "result_image_object_key": object_key,
                        "batch_id": image_entry.get("batch_id"),
                        "batch_index": index,
                    },
                },
            )
            created_items.append(item)
            if relation_source_id:
                created_connection = await canvas_service.create_connection(
                    str(source_item.document_id),
                    user_id,
                    {
                        "source_item_id": str(relation_source_id),
                        "target_item_id": str(item.id),
                        "source_handle": "right",
                        "target_handle": "left",
                    },
                )
                created_connections.append(created_connection)
        return created_items, created_connections

    async def _resolve_image_results(self, response: Any, user_id: str) -> List[Dict[str, Any]]:
        image_results = self._image_results(response)
        if not image_results:
            raise BusinessLogicError("No usable image found in generation result")
        assets = []
        for index, image_data in enumerate(image_results, start=1):
            try:
                assets.append(await self._store_image_result(image_data, user_id))
            except Exception as exc:
                raise BusinessLogicError(f"Image {index} save failed: {exc}") from exc
        return assets

    async def _resolve_image_result(self, response: Any, user_id: str) -> Dict[str, Any]:
        image_data = self._first_image_result(response)
        return await self._store_image_result(image_data, user_id)

    async def _store_image_result(self, image_data: Any, user_id: str) -> Dict[str, Any]:
        image_url = self._image_result_url(image_data)
        if image_url:
            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=20.0)) as client:
                remote_response = await client.get(image_url)
                remote_response.raise_for_status()
            storage_client = await get_storage_client()
            file_id = str(uuid.uuid4())
            upload_file = UploadFile(filename=f"{file_id}.png", file=io.BytesIO(remote_response.content))
            storage = await storage_client.upload_file(
                user_id=user_id,
                file=upload_file,
                metadata={"user_id": user_id, "file_id": file_id, "file_type": remote_response.headers.get("content-type", "image/png")},
            )
            return {"object_key": storage["object_key"], "url": storage["url"]}
        b64_value, content_type = self._image_result_b64(image_data)
        if b64_value:
            raw = base64.b64decode(b64_value)
            ext = "png" if "png" in content_type else "jpg"
            storage_client = await get_storage_client()
            file_id = str(uuid.uuid4())
            upload_file = UploadFile(filename=f"{file_id}.{ext}", file=io.BytesIO(raw))
            storage = await storage_client.upload_file(
                user_id=user_id,
                file=upload_file,
                metadata={"user_id": user_id, "file_id": file_id, "file_type": content_type},
            )
            return {"object_key": storage["object_key"], "url": storage["url"]}
        raise BusinessLogicError("图片生成结果不包含可用图片")

    def _image_results(self, response: Any) -> List[Any]:
        if isinstance(response, str):
            stripped = response.strip()
            if not stripped:
                return []
            if stripped.startswith("{") or stripped.startswith("["):
                try:
                    return self._image_results(json.loads(stripped))
                except json.JSONDecodeError:
                    return [stripped]
            return [stripped]
        if isinstance(response, list):
            return response
        if isinstance(response, dict):
            data = response.get("data")
            if isinstance(data, list):
                return data
            for key in ("url", "b64_json", "base64", "image", "image_url"):
                if response.get(key):
                    return [response]
            return []
        data = getattr(response, "data", None)
        if isinstance(data, list):
            return data
        if data:
            return [data]
        return [response] if response else []

    def _first_image_result(self, response: Any) -> Any:
        if isinstance(response, str):
            stripped = response.strip()
            if not stripped:
                return response
            if stripped.startswith("{") or stripped.startswith("["):
                try:
                    return self._first_image_result(json.loads(stripped))
                except json.JSONDecodeError:
                    return stripped
            return stripped
        if isinstance(response, dict):
            data = response.get("data")
            if isinstance(data, list) and data:
                return data[0]
            for key in ("url", "b64_json", "base64", "image", "image_url"):
                if response.get(key):
                    return response
        data = getattr(response, "data", None)
        if isinstance(data, list) and data:
            return data[0]
        return response

    def _image_result_url(self, image_data: Any) -> str:
        if isinstance(image_data, str):
            value = image_data.strip()
            if value.startswith(("http://", "https://")):
                return value
            return ""
        if isinstance(image_data, dict):
            return str(image_data.get("url") or image_data.get("image_url") or "").strip()
        return str(getattr(image_data, "url", "") or "").strip()

    def _image_result_b64(self, image_data: Any) -> Tuple[str, str]:
        if isinstance(image_data, str):
            value = image_data.strip()
            if value.startswith("data:image/") and "," in value:
                header, payload = value.split(",", 1)
                content_type = header.split(";", 1)[0].replace("data:", "") or "image/png"
                return payload.strip(), content_type
            if value and not value.startswith(("http://", "https://")):
                return value, "image/png"
            return "", "image/png"
        if isinstance(image_data, dict):
            value = str(image_data.get("b64_json") or image_data.get("base64") or image_data.get("image") or "").strip()
            content_type = str(image_data.get("mime") or image_data.get("mime_type") or "image/png")
            return value, content_type
        value = str(getattr(image_data, "b64_json", "") or "").strip()
        content_type = str(getattr(image_data, "mime", "image/png") or "image/png")
        return value, content_type

    async def _store_remote_video(self, video_url: str, user_id: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=20.0)) as client:
            response = await client.get(video_url)
            response.raise_for_status()

        storage_client = await get_storage_client()
        upload_file = UploadFile(filename=f"{uuid.uuid4()}.mp4", file=io.BytesIO(response.content))
        storage = await storage_client.upload_file(
            user_id=user_id,
            file=upload_file,
            metadata={"user_id": user_id, "file_type": "video/mp4"},
        )
        return {"object_key": storage["object_key"], "url": storage["url"]}

    async def _resolve_video_reference_images(self, references: List[str], *, prefer_public_urls: bool = False) -> List[str]:
        resolved: List[str] = []
        for reference in references or []:
            normalized = str(reference or "").strip()
            if not normalized:
                continue
            if normalized.startswith("data:image/"):
                resolved.append(normalized)
                continue
            if normalized.startswith("uploads/"):
                if prefer_public_urls:
                    public_url = absolute_public_media_url_for_object_key(normalized)
                    if public_url:
                        resolved.append(public_url)
                        continue
                storage_client = await get_storage_client()
                image_bytes = await storage_client.download_file(normalized)
                resolved.append(self._build_image_data_url(image_bytes))
                continue
            if prefer_public_urls and normalized.startswith(("http://", "https://")):
                resolved.append(normalized)
                continue

            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
                response = await client.get(normalized)
                response.raise_for_status()
                resolved.append(self._build_image_data_url(response.content, response.headers.get("content-type")))
        return resolved

    def _build_image_data_url(self, image_bytes: bytes, content_type: Optional[str] = None) -> str:
        mime_type = self._detect_image_mime_type(image_bytes, content_type)
        encoded = base64.b64encode(image_bytes).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"

    def _detect_image_mime_type(self, image_bytes: bytes, content_type: Optional[str] = None) -> str:
        normalized_type = str(content_type or "").strip().lower()
        if normalized_type.startswith("image/"):
            return normalized_type.split(";", 1)[0]
        if image_bytes.startswith(b"\x89PNG"):
            return "image/png"
        if image_bytes.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if image_bytes.startswith((b"GIF87a", b"GIF89a")):
            return "image/gif"
        if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
            return "image/webp"
        return "image/jpeg"

    def _sanitize_media_content(self, content: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(content, dict):
            return {}
        sanitized = dict(content)
        for url_field, object_key_field in MEDIA_URL_TO_OBJECT_KEY_FIELDS.items():
            if not sanitized.get(object_key_field):
                extracted_object_key = self._extract_object_key_from_media_url(sanitized.get(url_field))
                if extracted_object_key:
                    sanitized[object_key_field] = extracted_object_key
            if sanitized.get(object_key_field):
                sanitized.pop(url_field, None)
        return sanitized

    def _sanitize_media_result_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            return {}
        sanitized = dict(payload)
        for url_field, object_key_field in MEDIA_URL_TO_OBJECT_KEY_FIELDS.items():
            if not sanitized.get(object_key_field):
                extracted_object_key = self._extract_object_key_from_media_url(sanitized.get(url_field))
                if extracted_object_key:
                    sanitized[object_key_field] = extracted_object_key
            if sanitized.get(object_key_field):
                sanitized.pop(url_field, None)
        return sanitized

    async def _fetch_video_status_payload(self, provider: VectorEngineProvider, provider_task_id: str, *, attempts: int = 3) -> Dict[str, Any]:
        last_error = None
        for attempt_index in range(attempts):
            try:
                return await provider.get_task_status(provider_task_id)
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Canvas video status request failed (task=%s attempt=%s/%s): %s",
                    provider_task_id,
                    attempt_index + 1,
                    attempts,
                    exc,
                )
                if attempt_index < attempts - 1:
                    await asyncio.sleep(2)
        raise last_error

    async def _fetch_video_content_payload(self, provider: VectorEngineProvider, provider_task_id: str, *, attempts: int = 3) -> Dict[str, Any]:
        last_error = None
        for attempt_index in range(attempts):
            try:
                return await provider.get_video_content(provider_task_id)
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Canvas video content request failed (task=%s attempt=%s/%s): %s",
                    provider_task_id,
                    attempt_index + 1,
                    attempts,
                    exc,
                )
                if attempt_index < attempts - 1:
                    await asyncio.sleep(2)
        raise last_error

    async def _poll_video_result(self, provider: VectorEngineProvider, provider_task_id: str) -> str:
        for _ in range(60):
            try:
                status_payload = await self._fetch_video_status_payload(provider, provider_task_id)
            except Exception as exc:
                logger.warning("Canvas video status fetch transient failure (task=%s): %s", provider_task_id, exc)
                await asyncio.sleep(5)
                continue

            state = str(status_payload.get("status") or status_payload.get("state") or "").lower()
            if state in {"completed", "succeeded", "success", "done"}:
                video_url = self._extract_video_url(status_payload)
                if video_url:
                    return video_url
                try:
                    content_payload = await self._fetch_video_content_payload(provider, provider_task_id)
                except Exception as exc:
                    logger.warning(
                        "Canvas video content fetch transient failure after completion (task=%s): %s",
                        provider_task_id,
                        exc,
                    )
                    await asyncio.sleep(5)
                    continue
                video_url = self._extract_video_url(content_payload)
                if video_url:
                    return video_url
                logger.warning("Canvas video task completed without video_url yet (task=%s)", provider_task_id)
                await asyncio.sleep(5)
                continue
            if state in {"failed", "error", "cancelled", "canceled"}:
                raise BusinessLogicError(status_payload.get("message") or status_payload.get("error") or "视频生成失败")
            await asyncio.sleep(5)
        raise BusinessLogicError("视频生成超时，请稍后查看任务状态")

    def _extract_video_url(self, payload: Dict[str, Any]) -> Optional[str]:
        if not isinstance(payload, dict):
            return None
        direct_candidates = [
            payload.get("video_url"),
            payload.get("url"),
        ]
        detail = payload.get("detail") or payload.get("data") or {}
        if isinstance(detail, dict):
            direct_candidates.extend([detail.get("video_url"), detail.get("url")])
        for candidate in direct_candidates:
            if candidate:
                return candidate
        return None

    def _normalize_video_provider_status(self, provider_status: str) -> str:
        normalized = str(provider_status or "").strip().lower()
        if normalized in {"completed", "succeeded", "success", "done"}:
            return CanvasRunStatus.COMPLETED.value
        if normalized in {"failed", "error", "cancelled", "canceled"}:
            return CanvasRunStatus.FAILED.value
        if normalized in {"processing", "running", "pending", "queued", "submitted"}:
            return CanvasRunStatus.PROCESSING.value if normalized in {"processing", "running"} else CanvasRunStatus.PENDING.value
        return CanvasRunStatus.PROCESSING.value


__all__ = ["CanvasGenerationService", "CanvasService", "CanvasTaskHistoryService"]
