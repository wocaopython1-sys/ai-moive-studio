"""Canvas agent streaming API."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user_required
from src.api.schemas.canvas_assistant import (
    CanvasAssistantApplyRequest,
    CanvasAssistantApplyResponse,
    CanvasAssistantChatRequest,
    CanvasAssistantResumeRequest,
    CanvasAssistantSuggestRequest,
    CanvasAssistantSuggestResponse,
)
from src.api.v1.canvas import dispatch_canvas_image_generation, dispatch_canvas_text_generation, dispatch_canvas_video_generation
from src.assistant.agent_factory import CanvasAssistantAgentFactory
from src.assistant.service import CanvasAssistantService
from src.assistant.session_store import InMemoryCanvasAssistantSessionStore, RedisCanvasAssistantSessionStore
from src.assistant.sse import encode_sse_event
from src.assistant.workflow_service import CanvasAssistantWorkflowService
from src.assistant.tools.canvas_tools import CanvasAssistantCanvasExecutionTools, CanvasAssistantCanvasInspectionTools
from src.assistant.tools.generation_tools import CanvasAssistantGenerationTools
from src.core.config import settings
from src.core.database import get_db
from src.models.user import User
from src.services.api_key import APIKeyService
from src.services.canvas import CanvasGenerationService, CanvasService
from src.services.provider.factory import ProviderFactory

router = APIRouter()
_redis_client = None


def _get_redis_client():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis.asyncio as redis  # type: ignore
    except Exception:
        return None
    _redis_client = redis.from_url(settings.REDIS_URL)
    return _redis_client


def get_canvas_assistant_service(db: AsyncSession = Depends(get_db)) -> CanvasAssistantService:
    canvas_service = CanvasService(db)
    generation_service = CanvasGenerationService(db)
    inspection_tools = CanvasAssistantCanvasInspectionTools(canvas_service)
    redis_client = _get_redis_client()
    generation_tools = CanvasAssistantGenerationTools(
        generation_service=generation_service,
        dispatch_text=dispatch_canvas_text_generation,
        dispatch_image=dispatch_canvas_image_generation,
        dispatch_video=dispatch_canvas_video_generation,
    )
    workflow_service = CanvasAssistantWorkflowService(
        canvas_service=canvas_service,
        generation_service=generation_service,
        api_key_service=APIKeyService(db),
        dispatch_text=dispatch_canvas_text_generation,
        dispatch_image=dispatch_canvas_image_generation,
        dispatch_video=dispatch_canvas_video_generation,
    )
    agent_factory = CanvasAssistantAgentFactory(
        db_session=db,
        inspection_tools=inspection_tools,
        canvas_execution_tools=CanvasAssistantCanvasExecutionTools(canvas_service),
        generation_tools=generation_tools,
        workflow_service=workflow_service,
    )
    return CanvasAssistantService(
        session_store=RedisCanvasAssistantSessionStore(redis_client) if redis_client is not None else InMemoryCanvasAssistantSessionStore(),
        inspection_tools=inspection_tools,
        canvas_execution_tools=CanvasAssistantCanvasExecutionTools(canvas_service),
        generation_tools=generation_tools,
        agent_factory=agent_factory,
    )


def _iter_turn_events(result) -> Iterable[str]:
    for event in result.events:
        yield encode_sse_event(str(event.get("type") or ""), event.get("data") or {})


def _string(value: Any) -> str:
    return str(value or "").strip()


def _model_text(response: Any) -> str:
    choices = getattr(response, "choices", None) or []
    if choices:
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content.strip()
    if isinstance(response, dict):
        choices = response.get("choices") or []
        if choices:
            content = ((choices[0] or {}).get("message") or {}).get("content")
            if isinstance(content, str):
                return content.strip()
    return _string(response)


def _item_to_dict(item: Any) -> dict[str, Any]:
    content = dict(getattr(item, "content_json", {}) or {})
    return {
        "id": str(getattr(item, "id", "") or ""),
        "item_type": _string(getattr(item, "item_type", "")),
        "title": _string(getattr(item, "title", "")),
        "position_x": float(getattr(item, "position_x", 0) or 0),
        "position_y": float(getattr(item, "position_y", 0) or 0),
        "width": float(getattr(item, "width", 0) or 0),
        "height": float(getattr(item, "height", 0) or 0),
        "z_index": int(getattr(item, "z_index", 0) or 0),
        "content": content,
        "generation_config": dict(getattr(item, "generation_config_json", {}) or {}),
        "last_run_status": _string(getattr(item, "last_run_status", "")),
        "last_run_error": getattr(item, "last_run_error", None),
        "last_output": dict(getattr(item, "last_output_json", {}) or {}),
    }


def _item_text(item: Any) -> str:
    content = dict(getattr(item, "content_json", {}) or {})
    return _string(
        content.get("text")
        or content.get("prompt")
        or content.get("text_preview")
        or content.get("draft_text")
        or getattr(item, "title", "")
    )


def _media_summary(item: Any) -> str:
    content = dict(getattr(item, "content_json", {}) or {})
    return _string(
        content.get("result_image_object_key")
        or content.get("reference_image_object_key")
        or content.get("result_video_object_key")
        or content.get("result_image_url")
        or content.get("result_video_url")
        or ""
    )


def _graph_summary(graph: dict[str, Any]) -> dict[str, Any]:
    items = list(graph.get("items") or [])
    connections = list(graph.get("connections") or [])
    return {
        "item_count": len(items),
        "connection_count": len(connections),
        "items": [
            {
                "id": str(getattr(item, "id", "") or ""),
                "type": _string(getattr(item, "item_type", "")),
                "title": _string(getattr(item, "title", "")),
            }
            for item in items[:20]
        ],
    }


def _resolve_selected_item(graph: dict[str, Any], selected_item_id: str | None) -> Any | None:
    normalized_id = _string(selected_item_id)
    if not normalized_id:
        return None
    for item in list(graph.get("items") or []):
        if str(getattr(item, "id", "")) == normalized_id:
            return item
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="选中节点不存在")


def _suggest_title(action: str) -> str:
    return {
        "optimize_prompt": "优化后的 Prompt",
        "image_to_video_prompt": "视频 Prompt",
        "storyboard": "分镜建议",
    }.get(action, "助手建议")


def _suggest_target(action: str, selected_item: Any | None) -> str:
    if action == "optimize_prompt" and selected_item and _string(getattr(selected_item, "item_type", "")) == "text":
        return "update_selected_node"
    return "new_text_node"


def _fallback_suggestion(action: str, selected_item: Any | None, user_input: str) -> str:
    source = _item_text(selected_item) or user_input or "当前创作内容"
    if action == "image_to_video_prompt":
        title = _string(getattr(selected_item, "title", "")) or "参考图片"
        return (
            f"基于图片《{title}》生成 5 秒电影感视频：镜头缓慢推进，主体保持清晰，"
            "背景产生轻微视差运动，光影自然流动，画面稳定，无文字，无水印。"
        )
    if action == "storyboard":
        return (
            "1. 建立环境：用一个中远景交代空间、光线和主体位置。\n"
            "2. 强化主体：切到近景展示角色/物体的关键细节和情绪。\n"
            "3. 推进行动：加入一次明确运动或事件变化，形成节奏推进。\n"
            "4. 收束画面：用稳定构图留下结果、悬念或下一步生成方向。"
        )
    return (
        f"{source}\n\n优化方向：画面主体明确，镜头语言具体，风格、光线、构图、材质和负面约束清晰；"
        "适合直接用于图片或视频生成。"
    )


def _build_suggest_messages(
    *,
    action: str,
    selected_item: Any | None,
    graph: dict[str, Any],
    user_input: str,
) -> list[dict[str, str]]:
    selected_type = _string(getattr(selected_item, "item_type", "")) if selected_item else ""
    selected_title = _string(getattr(selected_item, "title", "")) if selected_item else ""
    source_text = _item_text(selected_item)
    media = _media_summary(selected_item)
    summary = _graph_summary(graph)

    action_instruction = {
        "optimize_prompt": (
            "把输入整理成可以直接用于 AI 图片/视频生成的高质量中文 Prompt。"
            "保留原意，补充主体、镜头、构图、光线、风格、细节和必要负面约束。"
        ),
        "image_to_video_prompt": (
            "根据当前图片节点信息生成适合图生视频的中文 Prompt。"
            "必须包含镜头运动、主体动作、画面稳定性、时长建议、风格和避免事项。"
        ),
        "storyboard": (
            "基于当前 Canvas 或选中节点生成 3 到 5 条分镜建议。"
            "每条包含镜头目的、画面内容、镜头运动和可继续生成的提示。"
        ),
    }.get(action, "给出适合写回画布节点的创作建议。")

    context_payload = {
        "canvas_summary": summary,
        "selected_item": {
            "id": str(getattr(selected_item, "id", "") or "") if selected_item else "",
            "type": selected_type,
            "title": selected_title,
            "text": source_text[:3000],
            "media": media,
        },
        "user_input": user_input,
    }
    return [
        {
            "role": "system",
            "content": (
                "你是 AICON Canvas 右侧创作助手。只输出可以写回画布文本节点的正文，"
                "不要输出 markdown 包裹，不要解释你做了什么。"
            ),
        },
        {
            "role": "user",
            "content": f"{action_instruction}\n\n上下文：{context_payload}",
        },
    ]


async def _generate_suggestion_text(
    *,
    api_key_service: APIKeyService,
    user_id: str,
    request: CanvasAssistantSuggestRequest,
    graph: dict[str, Any],
    selected_item: Any | None,
) -> str:
    api_key_id = _string(request.api_key_id)
    chat_model_id = _string(request.chat_model_id)
    if not api_key_id or not chat_model_id:
        return _fallback_suggestion(request.action, selected_item, _string(request.user_input))

    api_key = await api_key_service.get_api_key_by_id(api_key_id, user_id)
    provider = ProviderFactory.create(
        provider=api_key.provider,
        api_key=api_key.get_api_key(),
        base_url=api_key.base_url,
    )
    response = await provider.completions(
        model=chat_model_id,
        messages=_build_suggest_messages(
            action=request.action,
            selected_item=selected_item,
            graph=graph,
            user_input=_string(request.user_input),
        ),
        temperature=0.45,
    )
    text = _model_text(response)
    return text or _fallback_suggestion(request.action, selected_item, _string(request.user_input))


@router.post("/canvas-assistant/chat")
async def chat_canvas_assistant(
    payload: CanvasAssistantChatRequest,
    current_user: User = Depends(get_current_user_required),
    service: CanvasAssistantService = Depends(get_canvas_assistant_service),
):
    result = await service.chat(payload, user_id=str(current_user.id))
    return StreamingResponse(_iter_turn_events(result), media_type="text/event-stream")


@router.post("/canvas-assistant/resume")
async def resume_canvas_assistant(
    payload: CanvasAssistantResumeRequest,
    current_user: User = Depends(get_current_user_required),
    service: CanvasAssistantService = Depends(get_canvas_assistant_service),
):
    result = await service.resume(payload, user_id=str(current_user.id))
    return StreamingResponse(_iter_turn_events(result), media_type="text/event-stream")


@router.post("/canvas-assistant/suggest", response_model=CanvasAssistantSuggestResponse)
async def suggest_canvas_assistant(
    payload: CanvasAssistantSuggestRequest,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    canvas_service = CanvasService(db)
    graph = await canvas_service.get_graph(payload.canvas_id, str(current_user.id))
    selected_item = _resolve_selected_item(graph, payload.selected_item_id)
    text = await _generate_suggestion_text(
        api_key_service=APIKeyService(db),
        user_id=str(current_user.id),
        request=payload,
        graph=graph,
        selected_item=selected_item,
    )
    return CanvasAssistantSuggestResponse(
        action=payload.action,
        text=text,
        suggested_title=_suggest_title(payload.action),
        target=_suggest_target(payload.action, selected_item),
        selected_item=_item_to_dict(selected_item) if selected_item else None,
        canvas_summary=_graph_summary(graph),
    )


@router.post("/canvas-assistant/apply", response_model=CanvasAssistantApplyResponse)
async def apply_canvas_assistant(
    payload: CanvasAssistantApplyRequest,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    canvas_service = CanvasService(db)
    graph = await canvas_service.get_graph(payload.canvas_id, str(current_user.id))
    selected_item = _resolve_selected_item(graph, payload.selected_item_id)
    content_text = _string(payload.content)
    if not content_text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="写回内容不能为空")

    if payload.mode == "update_selected_text_node":
        if not selected_item or _string(getattr(selected_item, "item_type", "")) != "text":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前选中节点不是文本节点")
        item = await canvas_service.update_item(
            payload.canvas_id,
            str(getattr(selected_item, "id")),
            str(current_user.id),
            {
                "title": _string(payload.title) or _string(getattr(selected_item, "title", "")) or "助手建议",
                "content": {
                    "text": content_text,
                    "prompt": content_text,
                    "promptTokens": [{"type": "text", "text": content_text}],
                    "assistant_writeback": True,
                },
                "last_run_status": "completed",
                "last_output": {"text": content_text},
            },
        )
        await db.commit()
        return CanvasAssistantApplyResponse(item=_item_to_dict(item), connection=None)

    source_item = None
    if _string(payload.relation_source_item_id):
        source_item = _resolve_selected_item(graph, payload.relation_source_item_id)
    elif selected_item is not None:
        source_item = selected_item

    source_x = float(getattr(source_item, "position_x", 180) or 180) if source_item else 180
    source_y = float(getattr(source_item, "position_y", 180) or 180) if source_item else 180
    source_width = float(getattr(source_item, "width", 320) or 320) if source_item else 320
    item = await canvas_service.create_item(
        payload.canvas_id,
        str(current_user.id),
        {
            "item_type": "text",
            "title": _string(payload.title) or "助手建议",
            "position_x": float(payload.position_x) if payload.position_x is not None else source_x + source_width + 120,
            "position_y": float(payload.position_y) if payload.position_y is not None else source_y,
            "width": 360,
            "height": 240,
            "z_index": 0,
            "content": {
                "text": content_text,
                "prompt": content_text,
                "promptTokens": [{"type": "text", "text": content_text}],
                "assistant_writeback": True,
            },
            "last_run_status": "completed",
            "last_output": {"text": content_text},
        },
    )

    connection_payload = None
    if source_item is not None and str(getattr(source_item, "id", "")) != str(getattr(item, "id", "")):
        connection = await canvas_service.create_connection(
            payload.canvas_id,
            str(current_user.id),
            {
                "source_item_id": str(getattr(source_item, "id")),
                "target_item_id": str(getattr(item, "id")),
                "source_handle": "right",
                "target_handle": "left",
            },
        )
        connection_payload = {
            "id": str(connection.id),
            "source_item_id": str(connection.source_item_id),
            "target_item_id": str(connection.target_item_id),
            "source_handle": connection.source_handle,
            "target_handle": connection.target_handle,
        }

    await db.commit()
    return CanvasAssistantApplyResponse(item=_item_to_dict(item), connection=connection_payload)
