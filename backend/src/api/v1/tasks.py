"""
Task management APIs.
"""

from __future__ import annotations

from typing import Any

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user_required
from src.api.schemas.task import TaskStatusResponse
from src.core.database import get_db
from src.core.logging import get_logger
from src.models.user import User
from src.services.canvas import CanvasTaskHistoryService
from src.tasks.app import celery_app

logger = get_logger(__name__)

router = APIRouter()


def safe_result(task_result: AsyncResult):
    """
    Convert Celery result to a serializable shape.
    """
    status = task_result.status
    result = task_result.result

    if status in ["SUCCESS", "PROGRESS"]:
        return result

    if status == "FAILURE":
        if isinstance(result, Exception):
            return {
                "error": result.__class__.__name__,
                "message": str(result),
            }
        return {"message": str(result)}

    return None


@router.get("/history")
async def list_task_history(
    canvas_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    service = CanvasTaskHistoryService(db)
    items, total = await service.list_history(
        str(current_user.id),
        canvas_id=canvas_id,
        status=status,
        task_type=type,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "total": total}


@router.get("/history/{history_id}")
async def get_task_history_detail(
    history_id: str,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    service = CanvasTaskHistoryService(db)
    return await service.get_history_detail(history_id, str(current_user.id))


@router.post("/history/{history_id}/retry")
async def retry_task_history_item(
    history_id: str,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    service = CanvasTaskHistoryService(db)
    detail: dict[str, Any] = await service.get_history_detail(history_id, str(current_user.id))
    return {
        "success": False,
        "message": "当前阶段不做复杂重试调度，请回到对应 Canvas 节点重新生成。",
        "canvas_id": detail.get("canvas_id"),
        "canvas_item_id": detail.get("canvas_item_id"),
    }


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user_required),
):
    task_result = AsyncResult(task_id, app=celery_app)

    result = safe_result(task_result)
    statistics = None

    if isinstance(result, dict) and ("total" in result or "success" in result or "failed" in result):
        statistics = result

    return TaskStatusResponse(
        task_id=task_id,
        status=task_result.status,
        result=result,
        statistics=statistics,
    )


@router.post("/{task_id}/terminate")
async def terminate_task(
    task_id: str,
    current_user: User = Depends(get_current_user_required),
):
    task_result = AsyncResult(task_id, app=celery_app)
    task_result.revoke(terminate=True, signal="SIGTERM")
    return {"message": "任务终止请求已发送"}


__all__ = ["router"]
