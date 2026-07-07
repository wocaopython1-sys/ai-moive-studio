"""Works library APIs."""

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
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
from src.core.config import settings
from src.core.database import get_db
from src.models.user import User
from src.services.work import WorkService
from src.utils.storage import get_storage_client

router = APIRouter()

WORK_STREAM_TOKEN_TTL_SECONDS = 300
_STREAM_TOKEN_PAYLOAD_KEYS = {"user_id", "work_id", "item_id", "exp"}


@dataclass(frozen=True)
class _RangeSpec:
    start: int
    end: int
    length: int


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


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    try:
        padded = value + "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(padded.encode("ascii"))
    except Exception as exc:
        raise _stream_token_exception() from exc


def _stream_token_secret() -> bytes:
    return str(settings.JWT_SECRET_KEY).encode("utf-8")


def _stream_token_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效或过期的作品媒体访问凭据",
    )


def _sign_work_stream_payload(payload: dict[str, Any]) -> str:
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_part = _b64url_encode(payload_json)
    signature = hmac.new(
        _stream_token_secret(),
        payload_part.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{payload_part}.{_b64url_encode(signature)}"


def _decode_work_stream_token(token: str) -> dict[str, Any]:
    try:
        payload_part, signature_part = str(token or "").split(".", 1)
    except ValueError as exc:
        raise _stream_token_exception() from exc

    expected_signature = hmac.new(
        _stream_token_secret(),
        payload_part.encode("ascii"),
        hashlib.sha256,
    ).digest()
    try:
        provided_signature = _b64url_decode(signature_part)
    except HTTPException as exc:
        raise exc
    if not hmac.compare_digest(provided_signature, expected_signature):
        raise _stream_token_exception()

    try:
        payload = json.loads(_b64url_decode(payload_part).decode("utf-8"))
    except Exception as exc:
        raise _stream_token_exception() from exc

    if not isinstance(payload, dict) or set(payload.keys()) != _STREAM_TOKEN_PAYLOAD_KEYS:
        raise _stream_token_exception()
    try:
        expires_at = int(payload["exp"])
    except (TypeError, ValueError) as exc:
        raise _stream_token_exception() from exc
    if expires_at < int(time.time()):
        raise _stream_token_exception()
    for key in ("user_id", "work_id", "item_id"):
        if not str(payload.get(key) or "").strip():
            raise _stream_token_exception()
    return payload


def _range_not_satisfiable(size: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
        detail="Range Not Satisfiable",
        headers={
            "Accept-Ranges": "bytes",
            "Content-Range": f"bytes */{size}",
        },
    )


def _parse_range_header(range_header: str | None, size: int) -> _RangeSpec | None:
    if not range_header:
        return None
    header = range_header.strip()
    if size <= 0 or not header.startswith("bytes=") or "," in header:
        raise _range_not_satisfiable(size)

    value = header.removeprefix("bytes=").strip()
    if "-" not in value:
        raise _range_not_satisfiable(size)
    start_text, end_text = value.split("-", 1)
    if not start_text and not end_text:
        raise _range_not_satisfiable(size)

    try:
        if not start_text:
            suffix_length = int(end_text)
            if suffix_length <= 0:
                raise ValueError
            start = max(size - suffix_length, 0)
            end = size - 1
        else:
            start = int(start_text)
            end = size - 1 if not end_text else int(end_text)
    except ValueError as exc:
        raise _range_not_satisfiable(size) from exc

    if start < 0 or end < start or start >= size or end >= size:
        raise _range_not_satisfiable(size)
    return _RangeSpec(start=start, end=end, length=end - start + 1)


async def _stream_work_item_media(
    object_key: str,
    filename: str,
    *,
    download: bool,
    range_header: str | None = None,
    support_range: bool = False,
) -> StreamingResponse:
    clean_key = str(object_key or "").strip().lstrip("/")
    if not clean_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作品媒体不存在")

    storage_client = await get_storage_client()
    headers = {}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{_safe_download_filename(filename)}"'

    if support_range:
        try:
            stat_result = storage_client.client.stat_object(storage_client.bucket_name, clean_key)
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作品媒体文件不存在") from exc

        size = int(getattr(stat_result, "size", 0) or 0)
        range_spec = _parse_range_header(range_header, size)
        content_type = str(getattr(stat_result, "content_type", "") or "").strip() or "application/octet-stream"
        if range_spec is None:
            status_code = status.HTTP_200_OK
            offset = 0
            length = 0
            headers.update({"Accept-Ranges": "bytes", "Content-Length": str(size)})
        else:
            status_code = status.HTTP_206_PARTIAL_CONTENT
            offset = range_spec.start
            length = range_spec.length
            headers.update(
                {
                    "Accept-Ranges": "bytes",
                    "Content-Range": f"bytes {range_spec.start}-{range_spec.end}/{size}",
                    "Content-Length": str(range_spec.length),
                }
            )
    else:
        status_code = status.HTTP_200_OK
        offset = 0
        length = 0
        content_type = _content_type_for_key(clean_key)

    try:
        response = storage_client.client.get_object(
            storage_client.bucket_name,
            clean_key,
            offset=offset,
            length=length,
        )
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

    return StreamingResponse(body_iter(), media_type=content_type, headers=headers, status_code=status_code)


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


@router.post("/{work_id}/items/{item_id}/stream-token")
async def create_work_item_stream_token(
    work_id: str,
    item_id: str,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    service = WorkService(db)
    await service.get_work_item_media(
        user_id=str(current_user.id),
        work_id=work_id,
        item_id=item_id,
    )
    expires_at = int(time.time()) + WORK_STREAM_TOKEN_TTL_SECONDS
    token = _sign_work_stream_payload(
        {
            "user_id": str(current_user.id),
            "work_id": work_id,
            "item_id": item_id,
            "exp": expires_at,
        }
    )
    return {
        "stream_url": (
            f"/api/v1/works/{quote(work_id, safe='')}/items/"
            f"{quote(item_id, safe='')}/stream?token={quote(token, safe='')}"
        ),
        "expires_in": WORK_STREAM_TOKEN_TTL_SECONDS,
    }


@router.get("/{work_id}/items/{item_id}/stream")
async def stream_work_item_media(
    work_id: str,
    item_id: str,
    request: Request,
    token: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    if not token:
        raise _stream_token_exception()
    payload = _decode_work_stream_token(token)
    if str(payload["work_id"]) != work_id or str(payload["item_id"]) != item_id:
        raise _stream_token_exception()

    service = WorkService(db)
    _work, _item, object_key, _media_type, filename = await service.get_work_item_media(
        user_id=str(payload["user_id"]),
        work_id=work_id,
        item_id=item_id,
    )
    return await _stream_work_item_media(
        object_key,
        filename,
        download=False,
        range_header=request.headers.get("range"),
        support_range=True,
    )


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
