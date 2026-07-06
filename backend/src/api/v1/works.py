"""Works library APIs."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user_required
from src.api.schemas.work import (
    WorkCreateFromCanvasFinalRequest,
    WorkDeleteResponse,
    WorkDetailResponse,
    WorkListResponse,
    WorkResponse,
    WorkUpdateRequest,
)
from src.core.database import get_db
from src.models.user import User
from src.services.work import WorkService

router = APIRouter()


@router.get("", response_model=WorkListResponse)
async def list_works(
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    q: str | None = Query(None),
    source_canvas_id: str | None = Query(None),
):
    service = WorkService(db)
    works, total = await service.list_works(
        str(current_user.id),
        page=page,
        size=size,
        status=status_filter,
        q=q,
        source_canvas_id=source_canvas_id,
    )
    return WorkListResponse(
        works=[WorkResponse.from_model(work) for work in works],
        total=total,
        page=page,
        size=size,
        total_pages=(total + size - 1) // size if total else 0,
    )


@router.post("/from-canvas-final", response_model=WorkDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_work_from_canvas_final(
    payload: WorkCreateFromCanvasFinalRequest,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    service = WorkService(db)
    work = await service.create_from_canvas_final(
        user_id=str(current_user.id),
        canvas_id=str(payload.canvas_id),
        canvas_item_id=str(payload.canvas_item_id),
        title=payload.title,
        description=payload.description,
        cover_object_key=payload.cover_object_key,
    )
    await db.commit()
    work = await service.get_work(str(current_user.id), str(work.id))
    return WorkDetailResponse.from_model(work)


@router.get("/{work_id}", response_model=WorkDetailResponse)
async def get_work(
    work_id: str,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    service = WorkService(db)
    work = await service.get_work(str(current_user.id), work_id)
    return WorkDetailResponse.from_model(work)


@router.patch("/{work_id}", response_model=WorkDetailResponse)
async def update_work(
    work_id: str,
    payload: WorkUpdateRequest,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    service = WorkService(db)
    work = await service.update_work(
        user_id=str(current_user.id),
        work_id=work_id,
        updates=payload.model_dump(exclude_unset=True),
    )
    await db.commit()
    work = await service.get_work(str(current_user.id), str(work.id))
    return WorkDetailResponse.from_model(work)


@router.delete("/{work_id}", response_model=WorkDeleteResponse)
async def delete_work(
    work_id: str,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    service = WorkService(db)
    work = await service.delete_work(user_id=str(current_user.id), work_id=work_id)
    await db.commit()
    return WorkDeleteResponse(success=True, message="作品删除成功", work_id=work.id)


__all__ = ["router"]
