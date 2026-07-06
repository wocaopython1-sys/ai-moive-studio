"""Works library service."""

from __future__ import annotations

import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import desc, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from src.core.exceptions import BusinessLogicError, NotFoundError
from src.models.canvas import (
    CanvasDocument,
    CanvasGenerationType,
    CanvasItem,
    CanvasItemGeneration,
    CanvasRunStatus,
    ensure_canvas_uuid,
)
from src.models.work import Work, WorkItem, WorkItemRole, WorkMediaType, WorkStatus
from src.services.base import BaseService


class WorkService(BaseService):
    async def list_works(
        self,
        user_id: str,
        *,
        page: int = 1,
        size: int = 20,
        status: Optional[str] = None,
        q: Optional[str] = None,
        source_canvas_id: Optional[str] = None,
    ) -> Tuple[List[Work], int]:
        user_uuid = self._uuid(user_id)
        filters = [Work.user_id == user_uuid, Work.deleted_at.is_(None)]
        if status:
            filters.append(Work.status == status)
        if q and q.strip():
            keyword = f"%{q.strip()}%"
            filters.append(or_(Work.title.ilike(keyword), Work.description.ilike(keyword)))
        if source_canvas_id:
            filters.append(Work.source_canvas_id == self._uuid(source_canvas_id))

        count_stmt = select(func.count(Work.id)).where(*filters)
        total = (await self.execute(count_stmt)).scalar() or 0
        stmt = (
            select(Work)
            .where(*filters)
            .order_by(desc(Work.updated_at), desc(Work.created_at))
            .offset((page - 1) * size)
            .limit(size)
        )
        result = await self.execute(stmt)
        return list(result.scalars().all()), total

    async def get_work(self, user_id: str, work_id: str, *, include_deleted: bool = False) -> Work:
        filters = [Work.id == self._uuid(work_id), Work.user_id == self._uuid(user_id)]
        if not include_deleted:
            filters.append(Work.deleted_at.is_(None))
        stmt = select(Work).options(selectinload(Work.items)).where(*filters)
        work = (await self.execute(stmt)).scalar_one_or_none()
        if not work:
            raise NotFoundError("作品不存在或无权限访问", resource_type="work", resource_id=work_id)
        return work

    async def get_work_item_media(
        self,
        *,
        user_id: str,
        work_id: str,
        item_id: str,
    ) -> Tuple[Work, WorkItem, str, str, str]:
        user_uuid = self._uuid(user_id)
        work = await self.get_work(str(user_uuid), work_id)
        item_uuid = self._uuid(item_id)

        stmt = select(WorkItem).where(
            WorkItem.id == item_uuid,
            WorkItem.work_id == work.id,
            WorkItem.user_id == user_uuid,
        )
        item = (await self.execute(stmt)).scalar_one_or_none()
        if not item:
            raise NotFoundError("作品媒体不存在或无权限访问", resource_type="work_item", resource_id=item_id)

        object_key = str(item.object_key or "").strip()
        if not object_key:
            raise NotFoundError("作品媒体不存在", resource_type="work_item", resource_id=item_id)

        media_type = str(item.media_type or "").strip()
        filename = Path(object_key).name or str(item.role or media_type or "media").strip() or "media"
        return work, item, object_key, media_type, filename

    async def create_from_canvas_final(
        self,
        *,
        user_id: str,
        canvas_id: str,
        canvas_item_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        cover_object_key: Optional[str] = None,
    ) -> Work:
        user_uuid = self._uuid(user_id)
        canvas_uuid = self._uuid(canvas_id)
        item_uuid = self._uuid(canvas_item_id)

        document = await self._get_owned_canvas(canvas_uuid, user_uuid)
        item = await self._get_canvas_item_in_document(item_uuid, document.id)
        generations = await self._list_completed_generations(item.id, document.id, user_uuid)
        final_object_key = self._validate_compose_final(item, generations)

        source_generation = self._select_source_generation(generations, final_object_key)
        duplicate_stmt = select(Work).where(
            Work.user_id == user_uuid,
            Work.source_canvas_item_id == item.id,
            Work.final_object_key == final_object_key,
        )
        if (await self.execute(duplicate_stmt)).scalar_one_or_none():
            raise BusinessLogicError("该 Canvas final 已归档为作品")

        resolved_cover_object_key = str(cover_object_key or final_object_key).strip()
        if resolved_cover_object_key != final_object_key:
            raise BusinessLogicError("cover_object_key 首版只能为空或等于 final_object_key")

        metadata = self._build_metadata(item, source_generation)
        if source_generation is None:
            metadata["reason"] = "source_generation_missing"

        work = Work(
            user_id=user_uuid,
            title=(title or item.title or "未命名作品")[:200],
            description=description,
            status=WorkStatus.ARCHIVED.value,
            cover_object_key=resolved_cover_object_key,
            final_object_key=final_object_key,
            source_canvas_id=document.id,
            source_canvas_item_id=item.id,
            source_generation_id=source_generation.id if source_generation else None,
            metadata_json=metadata,
            deleted_at=None,
        )
        self.add(work)
        try:
            await self.flush()
        except IntegrityError as exc:
            await self.rollback()
            raise BusinessLogicError("该 Canvas final 已归档为作品") from exc

        final_item = WorkItem(
            work_id=work.id,
            user_id=user_uuid,
            role=WorkItemRole.FINAL.value,
            object_key=final_object_key,
            media_type=WorkMediaType.VIDEO.value,
            source_canvas_id=document.id,
            source_canvas_item_id=item.id,
            source_generation_id=source_generation.id if source_generation else None,
            sort_order=0,
            metadata_json={"source": "canvas_compose_final"},
        )
        self.add(final_item)
        await self.flush()
        return await self.get_work(str(user_uuid), str(work.id))

    async def update_work(self, *, user_id: str, work_id: str, updates: Dict[str, Any]) -> Work:
        work = await self.get_work(user_id, work_id)
        allowed_fields = {"title", "description", "status", "cover_object_key"}
        unexpected_fields = set(updates.keys()) - allowed_fields
        if unexpected_fields:
            raise BusinessLogicError("作品仅允许更新标题、描述、状态和封面")

        if "title" in updates and updates["title"] is not None:
            work.title = str(updates["title"])[:200]
        if "description" in updates:
            work.description = updates["description"]
        if "status" in updates and updates["status"] is not None:
            next_status = str(updates["status"])
            if next_status not in {WorkStatus.ARCHIVED.value, WorkStatus.HIDDEN.value}:
                raise BusinessLogicError("status 只能通过 PATCH 设置为 archived 或 hidden")
            work.status = next_status
        if "cover_object_key" in updates:
            next_cover = updates["cover_object_key"]
            if next_cover in (None, ""):
                work.cover_object_key = None
            else:
                next_cover = str(next_cover).strip()
                allowed_object_keys = {work.final_object_key, *[item.object_key for item in list(work.items or [])]}
                if next_cover not in allowed_object_keys:
                    raise BusinessLogicError("cover_object_key 必须为空、等于 final_object_key，或等于作品已关联素材")
                work.cover_object_key = next_cover

        await self.flush()
        await self.refresh(work)
        return await self.get_work(user_id, str(work.id))

    async def delete_work(self, *, user_id: str, work_id: str) -> Work:
        work = await self.get_work(user_id, work_id)
        now = datetime.now(timezone.utc)
        work.status = WorkStatus.DELETED.value
        work.deleted_at = now
        work.updated_at = now
        await self.flush()
        await self.refresh(work)
        return work

    async def _get_owned_canvas(self, canvas_id: uuid.UUID, user_id: uuid.UUID) -> CanvasDocument:
        stmt = select(CanvasDocument).where(CanvasDocument.id == canvas_id, CanvasDocument.user_id == user_id)
        document = (await self.execute(stmt)).scalar_one_or_none()
        if not document:
            raise NotFoundError("画布不存在或无权限访问", resource_type="canvas_document", resource_id=str(canvas_id))
        return document

    async def _get_canvas_item_in_document(self, item_id: uuid.UUID, canvas_id: uuid.UUID) -> CanvasItem:
        stmt = select(CanvasItem).where(CanvasItem.id == item_id, CanvasItem.document_id == canvas_id)
        item = (await self.execute(stmt)).scalar_one_or_none()
        if not item:
            raise NotFoundError("画布节点不存在", resource_type="canvas_item", resource_id=str(item_id))
        return item

    async def _list_completed_generations(
        self,
        item_id: uuid.UUID,
        document_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> List[CanvasItemGeneration]:
        stmt = (
            select(CanvasItemGeneration)
            .where(
                CanvasItemGeneration.item_id == item_id,
                CanvasItemGeneration.document_id == document_id,
                CanvasItemGeneration.user_id == user_id,
                CanvasItemGeneration.generation_type == CanvasGenerationType.VIDEO.value,
                CanvasItemGeneration.status == CanvasRunStatus.COMPLETED.value,
            )
            .order_by(desc(CanvasItemGeneration.created_at))
        )
        return list((await self.execute(stmt)).scalars().all())

    def _validate_compose_final(self, item: CanvasItem, generations: Iterable[CanvasItemGeneration]) -> str:
        if item.item_type != "video":
            raise BusinessLogicError("只有视频节点可以归档为作品")
        if item.last_run_status != CanvasRunStatus.COMPLETED.value:
            raise BusinessLogicError("只有已完成视频节点可以归档为作品")
        final_object_key = self._result_video_object_key(item)
        if not final_object_key:
            raise BusinessLogicError("Canvas final 缺少 result_video_object_key")

        payloads: List[Dict[str, Any]] = [item.content_json or {}, item.last_output_json or {}]
        for generation in generations:
            payloads.append(generation.result_payload_json or {})
            payloads.append(generation.request_payload_json or {})
        if not any(self._payload_has_compose_trace(payload) for payload in payloads):
            raise BusinessLogicError("只有 Canvas compose final 可以归档为作品")
        return final_object_key

    def _select_source_generation(
        self,
        generations: Iterable[CanvasItemGeneration],
        final_object_key: str,
    ) -> Optional[CanvasItemGeneration]:
        for generation in generations:
            result_payload = generation.result_payload_json or {}
            request_payload = generation.request_payload_json or {}
            if str(result_payload.get("result_video_object_key") or "").strip() == final_object_key:
                return generation
            if self._payload_has_compose_trace(result_payload) or self._payload_has_compose_trace(request_payload):
                return generation
        return None

    def _result_video_object_key(self, item: CanvasItem) -> str:
        content = item.content_json or {}
        output = item.last_output_json or {}
        return str(content.get("result_video_object_key") or output.get("result_video_object_key") or "").strip()

    def _payload_has_compose_trace(self, payload: Dict[str, Any]) -> bool:
        if not isinstance(payload, dict):
            return False
        if self._has_list_like_value(payload.get("compose_source_item_ids")):
            return True
        if str(payload.get("compose_mode") or "").strip().lower() == "concat":
            return True
        if self._int_value(payload.get("clip_count")) >= 2:
            return True
        if str(payload.get("model") or "").strip().lower() == "ffmpeg-concat":
            return True

        provider_response = payload.get("provider_response") if isinstance(payload.get("provider_response"), dict) else {}
        if (
            str(payload.get("provider") or provider_response.get("provider") or "").strip().lower() == "local"
            and str(payload.get("tool") or provider_response.get("tool") or "").strip().lower() == "ffmpeg"
        ):
            return True

        options = payload.get("options") if isinstance(payload.get("options"), dict) else {}
        if str(options.get("mode") or "").strip().lower() == "concat":
            return True
        if self._int_value(options.get("clip_count")) >= 2:
            return True
        if self._has_list_like_value(options.get("source_item_ids")):
            return True
        return False

    def _build_metadata(self, item: CanvasItem, source_generation: Optional[CanvasItemGeneration]) -> Dict[str, Any]:
        content = item.content_json or {}
        output = item.last_output_json or {}
        metadata: Dict[str, Any] = {"source": "canvas_compose_final"}
        for payload in (content, output):
            if self._has_list_like_value(payload.get("compose_source_item_ids")):
                metadata["compose_source_item_ids"] = payload.get("compose_source_item_ids")
                break
        clip_count = content.get("clip_count") or output.get("clip_count")
        if clip_count is not None:
            metadata["clip_count"] = clip_count
        if source_generation is not None:
            metadata["source_generation_status"] = source_generation.status
        return metadata

    def _has_list_like_value(self, value: Any) -> bool:
        if isinstance(value, (list, tuple)):
            return len(value) > 0
        if isinstance(value, str):
            return bool(value.strip())
        return False

    def _int_value(self, value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _uuid(self, value: Any) -> uuid.UUID:
        return ensure_canvas_uuid(value)


__all__ = ["WorkService"]
