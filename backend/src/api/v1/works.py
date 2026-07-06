"""Works library APIs."""

from pathlib import Path
from typing import Iterator

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
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
from src.utils.storage import get_storage_client

router = APIRouter()


def _content_type_for_key(object_key: str) -> str:
    suffix = Path(str(object_key or "")).suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mov": "video/quicktime",
    }.get(suffix, "application/octet-stream")


def _safe_download_filename(filename: str) -> str:
    base = Path(str(filename or "")).name.strip() or "media"
    safe = "".join(
        char if char.isascii() and (char.isalnum() or char in "._-") else "_"
        for char in base
    ).strip("._")
    return safe or "media"


async def _stream_work_item_media(object_key: str, filename: str, *, download: bool) -> StreamingResponse:
    clean_key = str(object_key or "").strip().lstrip("/")
    if not clean_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作品媒体不存在")

    storage_client = await get_storage_client()
    try:
        response = storage_client.client.get_object(storage_client.bucket_name, clean_key)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作品媒体文件不存在") from exc

    def body_iter() -> Iterator[bytes]:
        try:
            for chunk in response.stream(1024 * 1024):
                if chunk:
                    yield chunk
        finally:
            response.close()
            response.release_conn()

    headers = {}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{_safe_download_filename(filename)}"'

    return StreamingResponse(body_iter(), media_type=_content_type_for_key(clean_key), headers=headers)


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


@router.get("/{work_id}/items/{item_id}/preview")
async def preview_work_item_media(
    work_id: str,
    item_id: str,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    service = WorkService(db)
    _work, _item, object_key, _media_type, filename = await service.get_work_item_media(
        user_id=str(current_user.id),
        work_id=work_id,
        item_id=item_id,
    )
    return await _stream_work_item_media(object_key, filename, download=False)


@router.get("/{work_id}/items/{item_id}/download")
async def download_work_item_media(
    work_id: str,
    item_id: str,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    service = WorkService(db)
    _work, _item, object_key, _media_type, filename = await service.get_work_item_media(
        user_id=str(current_user.id),
        work_id=work_id,
        item_id=item_id,
    )
    return await _stream_work_item_media(object_key, filename, download=True)


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
