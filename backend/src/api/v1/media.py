from pathlib import Path
from typing import Iterator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

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


async def _stream_object(object_key: str, *, download: bool) -> StreamingResponse:
    storage_client = await get_storage_client()
    clean_key = str(object_key or "").strip().lstrip("/")
    if not clean_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="媒体文件不存在")

    try:
        response = storage_client.client.get_object(storage_client.bucket_name, clean_key)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"媒体文件读取失败: {exc}") from exc

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
        filename = Path(clean_key).name or "media"
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'

    return StreamingResponse(body_iter(), media_type=_content_type_for_key(clean_key), headers=headers)


@router.get("/media/preview/{object_key:path}")
async def preview_media(object_key: str):
    return await _stream_object(object_key, download=False)


@router.get("/media/download/{object_key:path}")
async def download_media(object_key: str):
    return await _stream_object(object_key, download=True)


@router.get("/media/stream/{object_key:path}")
async def stream_media(object_key: str):
    return await _stream_object(object_key, download=False)
