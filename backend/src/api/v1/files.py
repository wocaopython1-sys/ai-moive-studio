"""
文件管理API - 重构后使用schemas模块中的Pydantic模型
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user_required
from src.core.database import get_db
from src.core.logging import get_logger
from src.models.canvas import CanvasDocument, CanvasItem, CanvasItemType, CanvasRunStatus
from src.models.user import User
from src.services.project import ProjectService
from src.utils.file_handlers import FileHandler, FileProcessingError
from src.utils.media_urls import media_url_for_object_key
from src.utils.storage import get_storage_client
from src.api.schemas.file import (
    FileUploadResult,
    FileInfo,
    FileListResponse,
    FileCleanupResponse,
    FileStorageUsageResponse,
    FileBatchDeleteResponse,
    FileIntegrityCheckResponse,
    FileType,
)

logger = get_logger(__name__)

router = APIRouter()


def _media_type_from_object_key(object_key: str) -> Optional[str]:
    suffix = str(object_key or "").split("?")[0].rsplit(".", 1)[-1].lower()
    if suffix in {"png", "jpg", "jpeg", "webp", "gif", "bmp"}:
        return "image"
    if suffix in {"mp4", "webm", "mov"}:
        return "video"
    return None


def _mime_type_from_object_key(object_key: str, fallback: Optional[str] = None) -> str:
    suffix = str(object_key or "").split("?")[0].rsplit(".", 1)[-1].lower()
    mime_map = {
        "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "webp": "image/webp", "gif": "image/gif", "bmp": "image/bmp",
        "mp4": "video/mp4", "webm": "video/webm", "mov": "video/quicktime",
    }
    return mime_map.get(suffix) or fallback or "application/octet-stream"


def _source_from_object_key(object_key: str, metadata: Optional[Dict[str, Any]] = None) -> str:
    metadata = metadata or {}
    metadata_source = str(metadata.get("source") or metadata.get("x-amz-meta-source") or "").strip().lower()
    if metadata_source:
        return metadata_source
    filename = str(object_key or "").split("/")[-1].lower()
    if any(token in filename for token in ("generated", "phase1a", "assistant")):
        return "generated"
    return "upload"


def _normalize_file_info(file_info: Dict[str, Any]) -> Dict[str, Any]:
    object_key = file_info["object_key"]
    media_type = _media_type_from_object_key(object_key)
    preview_url = media_url_for_object_key(object_key, "preview") if media_type else file_info.get("url")
    download_url = media_url_for_object_key(object_key, "download") if media_type else file_info.get("url")
    stream_url = media_url_for_object_key(object_key, "stream") if media_type == "video" else None
    filename = object_key.split("/")[-1]
    return {
        "id": object_key,
        "object_key": object_key,
        "filename": filename,
        "title": filename,
        "size": file_info.get("size") or 0,
        "size_mb": round((file_info.get("size") or 0) / (1024 * 1024), 2),
        "last_modified": file_info.get("last_modified"),
        "url": file_info.get("url"),
        "media_type": media_type,
        "mime_type": _mime_type_from_object_key(object_key, file_info.get("content_type")),
        "preview_url": preview_url,
        "download_url": download_url,
        "stream_url": stream_url,
        "source": _source_from_object_key(object_key, file_info.get("metadata")),
        "is_orphaned": True,
    }


def _matches_library_filters(entry: Dict[str, Any], *, q: Optional[str], media_type: Optional[str], source: Optional[str]) -> bool:
    normalized_type = str(media_type or "all").strip().lower()
    normalized_source = str(source or "all").strip().lower()
    query = str(q or "").strip().lower()

    if normalized_type and normalized_type != "all":
        if normalized_type in {"prompt", "text"}:
            if entry.get("media_type") != "text":
                return False
        elif entry.get("media_type") != normalized_type:
            return False

    if normalized_source and normalized_source != "all":
        if entry.get("source") != normalized_source:
            return False

    if query:
        haystack = " ".join(
            str(entry.get(field) or "")
            for field in ("filename", "title", "object_key", "text", "summary", "canvas_id", "canvas_item_id")
        ).lower()
        if query not in haystack:
            return False

    return True


def _paginate_entries(entries: List[Dict[str, Any]], *, page: int, size: int) -> tuple[List[Dict[str, Any]], int, int]:
    total = len(entries)
    start_index = (page - 1) * size
    end_index = start_index + size
    total_pages = (total + size - 1) // size if total else 0
    return entries[start_index:end_index], total, total_pages


def _stringify_datetime(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return str(value)


def _extract_canvas_text(content: Dict[str, Any], last_output: Dict[str, Any]) -> str:
    content = content or {}
    last_output = last_output or {}
    prompt_tokens = content.get("promptTokens")
    token_text = ""
    if isinstance(prompt_tokens, list):
        token_text = "".join(
            str(token.get("text") or "")
            for token in prompt_tokens
            if isinstance(token, dict) and str(token.get("type") or "text") == "text"
        ).strip()
    return str(
        content.get("text")
        or content.get("draft_text")
        or content.get("promptPlainText")
        or content.get("prompt")
        or last_output.get("text")
        or token_text
        or ""
    ).strip()


def _canvas_text_item_to_file_info(item: CanvasItem, document: CanvasDocument) -> Optional[Dict[str, Any]]:
    text = _extract_canvas_text(item.content_json or {}, item.last_output_json or {})
    saved_to_library = bool((item.content_json or {}).get("saved_to_library"))
    if not text and not saved_to_library:
        return None

    title = str(
        item.title
        or (item.content_json or {}).get("library_title")
        or (text[:24] if text else "Canvas 文本素材")
    ).strip()
    summary = text[:180] + ("..." if len(text) > 180 else "")
    object_key = f"canvas-item:{item.id}"
    updated_at = getattr(item, "updated_at", None) or getattr(document, "updated_at", None)
    return {
        "id": object_key,
        "object_key": object_key,
        "filename": title,
        "title": title,
        "size": len(text.encode("utf-8")),
        "size_mb": round(len(text.encode("utf-8")) / (1024 * 1024), 4),
        "last_modified": _stringify_datetime(updated_at),
        "url": None,
        "is_orphaned": False,
        "media_type": "text",
        "mime_type": "text/plain",
        "preview_url": None,
        "download_url": None,
        "stream_url": None,
        "source": "canvas",
        "canvas_id": str(document.id),
        "canvas_item_id": str(item.id),
        "text": text,
        "summary": summary,
    }


async def _list_canvas_text_assets(
        db: AsyncSession,
        user_id: str,
) -> List[Dict[str, Any]]:
    stmt = (
        select(CanvasItem, CanvasDocument)
        .join(CanvasDocument, CanvasItem.document_id == CanvasDocument.id)
        .where(
            CanvasDocument.user_id == current_user_uuid(user_id),
            CanvasItem.item_type == CanvasItemType.TEXT.value,
        )
        .order_by(desc(CanvasItem.updated_at))
        .limit(200)
    )
    result = await db.execute(stmt)
    entries = []
    for item, document in result.all():
        entry = _canvas_text_item_to_file_info(item, document)
        if entry:
            entries.append(entry)
    return entries


def current_user_uuid(user_id: str):
    from src.models.canvas import ensure_canvas_uuid

    return ensure_canvas_uuid(user_id)


@router.post("/upload", response_model=FileUploadResult)
async def upload_file(
        *,
        current_user: User = Depends(get_current_user_required),
        file: UploadFile = File(..., description="上传的文件")
):
    """
    纯文件上传，返回文件ID和信息

    Args:
        current_user: 当前用户
        file: 上传的文件

    Returns:
        文件上传结果和文件信息
    """
    # 验证文件
    file_type, file_info = await FileHandler.validate_file(file)
    logger.info(f"文件验证成功: {file_info}")

    # 生成唯一的文件ID
    import uuid
    file_id = str(uuid.uuid4())

    # 获取存储客户端
    storage_client = await get_storage_client()

    # 上传到MinIO
    storage_result = await storage_client.upload_file(
        user_id=current_user.id,
        file=file,
        metadata={
            "user_id": current_user.id,
            "file_id": file_id,
            "file_type": file_type,
            "original_filename": file.filename,
        }
    )

    logger.info(f"文件上传到存储成功: {storage_result}")

    return FileUploadResult(
        success=True,
        message="文件上传成功",
        data={
            "file_id": file_id,
            "original_filename": file.filename,
            "file_size": file.size,
            "file_type": file_type,
            "storage_key": storage_result["object_key"],
        },
        file_info=file_info,
        storage_info=storage_result,
    )


@router.delete("/cleanup/orphaned", response_model=FileCleanupResponse)
async def cleanup_orphaned_files(
        *,
        current_user: User = Depends(get_current_user_required),
        db: AsyncSession = Depends(get_db),
        dry_run: bool = Query(True, description="是否为试运行"),
        older_than_days: int = Query(7, ge=1, description="清理多少天前的孤立文件")
):
    """
    清理孤立文件（没有关联项目的文件）

    Args:
        current_user: 当前用户
        db: 数据库会话
        dry_run: 是否为试运行
        older_than_days: 清理多少天前的文件

    Returns:
        清理结果
    """
    from datetime import datetime, timedelta, timezone

    storage_client = await get_storage_client()
    project_service = ProjectService(db)

    # 获取用户的所有项目
    projects, _ = await project_service.get_owner_projects(
        owner_id=current_user.id,
        page=1,
        size=1000  # 获取大量项目以检查关联
    )

    # 收集所有项目关联的文件对象键
    project_object_keys = set()
    for project in projects:
        if project.file_path:
            project_object_keys.add(project.file_path)

    # 获取用户上传目录下的所有文件
    user_prefix = f"uploads/{current_user.id}/"
    all_files = await storage_client.list_files(prefix=user_prefix, limit=1000)

    # 找出孤立文件
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    orphaned_files = []

    for file_info in all_files:
        object_key = file_info['object_key']

        # 跳过项目关联的文件
        if object_key in project_object_keys:
            continue

        # 检查文件时间
        if file_info.get('last_modified'):
            try:
                file_date = datetime.fromisoformat(file_info['last_modified'].replace('Z', '+00:00'))
                if file_date >= cutoff_date:
                    continue
            except ValueError:
                logger.warning(f"无法解析文件时间: {file_info['last_modified']}")

        orphaned_files.append(file_info)

    # 如果不是试运行，执行删除
    deleted_files = []
    deleted_keys = []
    if not dry_run:
        for file_info in orphaned_files:
            try:
                success = await storage_client.delete_file(file_info['object_key'])
                if success:
                    deleted_files.append(file_info['object_key'])
                    deleted_keys.append(file_info['object_key'])
            except Exception as e:
                logger.error(f"删除文件失败 {file_info['object_key']}: {e}")

    total_size = sum(f.get('size', 0) for f in orphaned_files)
    deleted_size = sum(f.get('size', 0) for f in orphaned_files if f['object_key'] in deleted_files)

    # 格式化文件详情
    files_details = [
        {
            "object_key": f['object_key'],
            "size": f.get('size'),
            "size_mb": round(f.get('size', 0) / (1024 * 1024), 2),
            "last_modified": f.get('last_modified')
        }
        for f in orphaned_files
    ]

    return FileCleanupResponse(
        success=True,
        dry_run=dry_run,
        found_orphaned_files=len(orphaned_files),
        deleted_files=len(deleted_files),
        total_size_mb=round(total_size / (1024 * 1024), 2),
        deleted_size_mb=round(deleted_size / (1024 * 1024), 2),
        files=files_details,
    )


@router.get("/storage/usage", response_model=FileStorageUsageResponse)
async def get_storage_usage(
        *,
        current_user: User = Depends(get_current_user_required),
        db: AsyncSession = Depends(get_db)
):
    """
    获取用户存储使用情况

    Args:
        current_user: 当前用户
        db: 数据库会话

    Returns:
        存储使用统计
    """
    storage_client = await get_storage_client()
    project_service = ProjectService(db)

    # 获取项目统计信息
    stats = await project_service.get_project_statistics(current_user.id)

    # 获取存储文件列表
    user_prefix = f"uploads/{current_user.id}/"
    files = await storage_client.list_files(prefix=user_prefix, limit=1000)

    # 按文件类型统计
    file_type_stats = {}
    total_size = 0

    for file_info in files:
        file_size = file_info.get('size', 0)
        total_size += file_size

        # 从对象键推断文件类型
        object_key = file_info['object_key']
        if '.' in object_key.split('/')[-1]:
            ext = object_key.split('.')[-1].lower()
            if ext in file_type_stats:
                file_type_stats[ext] += 1
            else:
                file_type_stats[ext] = 1

    quota_limit_gb = 10.0  # 示例：10GB限制
    quota_usage_percent = round((total_size / (quota_limit_gb * 1024 * 1024 * 1024)) * 100, 2)

    return FileStorageUsageResponse(
        success=True,
        total_files=len(files),
        total_size_mb=round(total_size / (1024 * 1024), 2),
        total_size_gb=round(total_size / (1024 * 1024 * 1024), 2),
        file_type_distribution=file_type_stats,
        project_stats=stats,
        quota_limit_gb=quota_limit_gb,
        quota_usage_percent=quota_usage_percent,
    )


@router.get("/list", response_model=FileListResponse)
async def list_user_files(
        *,
        current_user: User = Depends(get_current_user_required),
        db: AsyncSession = Depends(get_db),
        prefix: Optional[str] = Query(None, description="文件前缀过滤"),
        media_type: Optional[str] = Query("all", description="素材类型过滤：all/image/video/text"),
        q: Optional[str] = Query(None, description="关键词搜索"),
        source: Optional[str] = Query("all", description="来源过滤：all/upload/generated"),
        page: int = Query(1, ge=1, description="页码"),
        size: int = Query(50, ge=1, le=200, description="每页大小"),
        limit: Optional[int] = Query(None, ge=1, le=200, description="兼容素材库limit"),
        offset: int = Query(0, ge=0, description="兼容素材库offset")
):
    """
    列出用户的文件

    Args:
        current_user: 当前用户
        db: 数据库会话
        prefix: 文件前缀过滤
        page: 页码
        size: 每页大小

    Returns:
        文件列表
    """
    storage_client = await get_storage_client()

    # 构建搜索前缀
    user_prefix = f"uploads/{current_user.id}/"
    search_prefix = user_prefix + (prefix or "")

    effective_size = limit or size

    # 获取文件列表。MinIO list 没有总数接口，阶段 1C 仍采用轻量拉取后过滤。
    files = await storage_client.list_files(prefix=search_prefix, limit=200)
    all_files = [
        _normalize_file_info(file_info)
        for file_info in files
    ]
    filtered_files = [
        file_info
        for file_info in all_files
        if _matches_library_filters(file_info, q=q, media_type=media_type, source=source)
    ]

    if limit is not None:
        total_files = len(filtered_files)
        start_index = offset
        end_index = offset + effective_size
        cleaned_files = filtered_files[start_index:end_index]
        total_pages = (total_files + effective_size - 1) // effective_size if total_files else 0
        page = (offset // effective_size) + 1
        size = effective_size
    else:
        cleaned_files, total_files, total_pages = _paginate_entries(filtered_files, page=page, size=size)

    # 检查哪些文件是孤立的
    project_service = ProjectService(db)
    projects, _ = await project_service.get_owner_projects(
        owner_id=current_user.id,
        page=1,
        size=1000
    )

    project_object_keys = set()
    for project in projects:
        if project.file_path:
            project_object_keys.add(project.file_path)

    # 更新孤立状态
    for file_info in cleaned_files:
        file_info['is_orphaned'] = file_info['object_key'] not in project_object_keys

    orphaned_count = sum(1 for f in cleaned_files if f['is_orphaned'])
    file_items = [FileInfo(**f) for f in cleaned_files]

    return FileListResponse(
        files=file_items,
        items=file_items,
        total=total_files,
        page=page,
        size=size,
        total_pages=total_pages,
        orphaned_count=orphaned_count,
    )


@router.get("/library", response_model=FileListResponse)
async def list_asset_library(
        *,
        current_user: User = Depends(get_current_user_required),
        db: AsyncSession = Depends(get_db),
        media_type: Optional[str] = Query("all", description="素材类型：all/image/video/text/prompt"),
        q: Optional[str] = Query(None, description="关键词搜索"),
        source: Optional[str] = Query("all", description="来源：all/upload/generated/canvas"),
        page: int = Query(1, ge=1, description="页码"),
        size: int = Query(48, ge=1, le=200, description="每页大小"),
        limit: Optional[int] = Query(None, ge=1, le=200, description="limit/offset兼容"),
        offset: int = Query(0, ge=0, description="limit/offset兼容")
):
    """
    轻量素材库聚合接口。

    阶段 1C 不新增资产表：图片/视频来自 MinIO 文件列表，文本/Prompt 来自 Canvas 文本节点。
    """
    storage_client = await get_storage_client()
    user_prefix = f"uploads/{current_user.id}/"
    effective_size = limit or size

    storage_files = await storage_client.list_files(prefix=user_prefix, limit=200)
    media_entries = [
        _normalize_file_info(file_info)
        for file_info in storage_files
    ]
    text_entries = await _list_canvas_text_assets(db, str(current_user.id))

    all_entries = [
        entry
        for entry in [*media_entries, *text_entries]
        if _matches_library_filters(entry, q=q, media_type=media_type, source=source)
    ]
    all_entries.sort(key=lambda entry: str(entry.get("last_modified") or ""), reverse=True)

    if limit is not None:
        total_files = len(all_entries)
        start_index = offset
        end_index = offset + effective_size
        page_items = all_entries[start_index:end_index]
        total_pages = (total_files + effective_size - 1) // effective_size if total_files else 0
        page = (offset // effective_size) + 1
        size = effective_size
    else:
        page_items, total_files, total_pages = _paginate_entries(all_entries, page=page, size=size)

    file_items = [FileInfo(**entry) for entry in page_items]
    return FileListResponse(
        files=file_items,
        items=file_items,
        total=total_files,
        page=page,
        size=size,
        total_pages=total_pages,
        orphaned_count=0,
    )


@router.post("/batch-delete", response_model=FileBatchDeleteResponse)
async def batch_delete_files(
        *,
        current_user: User = Depends(get_current_user_required),
        db: AsyncSession = Depends(get_db),
        object_keys: List[str]
):
    """
    批量删除文件

    Args:
        current_user: 当前用户
        db: 数据库会话
        object_keys: 要删除的文件对象键列表

    Returns:
        删除结果
    """
    if not object_keys:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件对象键列表不能为空"
        )

    if len(object_keys) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="单次批量删除文件数量不能超过100个"
        )

    storage_client = await get_storage_client()
    project_service = ProjectService(db)

    # 检查权限并过滤
    user_prefix = f"uploads/{current_user.id}/"
    valid_keys = []
    protected_keys = []

    for object_key in object_keys:
        # 检查文件是否属于当前用户
        if not object_key.startswith(user_prefix):
            logger.warning(f"用户 {current_user.id} 尝试删除不属于自己的文件: {object_key}")
            continue

        # 检查文件是否关联到项目
        projects, _ = await project_service.get_owner_projects(
            owner_id=current_user.id,
            page=1,
            size=1000
        )

        is_protected = False
        for project in projects:
            if project.file_path == object_key:
                is_protected = True
                protected_keys.append(object_key)
                break

        if not is_protected:
            valid_keys.append(object_key)

    # 执行删除
    deleted_keys = []
    failed_keys = []

    for object_key in valid_keys:
        try:
            success = await storage_client.delete_file(object_key)
            if success:
                deleted_keys.append(object_key)
            else:
                failed_keys.append(object_key)
        except Exception as e:
            logger.error(f"删除文件失败 {object_key}: {e}")
            failed_keys.append(object_key)

    return FileBatchDeleteResponse(
        success=True,
        requested_files=len(object_keys),
        valid_files=len(valid_keys),
        protected_files=len(protected_keys),
        deleted_files=len(deleted_keys),
        failed_files=len(failed_keys),
        deleted_keys=deleted_keys,
        failed_keys=failed_keys,
        protected_keys=protected_keys,
    )


@router.get("/integrity/check", response_model=FileIntegrityCheckResponse)
async def check_file_integrity(
        *,
        current_user: User = Depends(get_current_user_required),
        db: AsyncSession = Depends(get_db),
        project_id: Optional[str] = Query(None, description="指定项目ID检查")
):
    """
    检查文件完整性

    Args:
        current_user: 当前用户
        db: 数据库会话
        project_id: 可选的项目ID

    Returns:
        完整性检查结果
    """
    from src.api.schemas.file import FileIntegrityCheckResult

    storage_client = await get_storage_client()
    project_service = ProjectService(db)

    if project_id:
        # 检查单个项目
        project = await project_service.get_project_by_id(project_id, current_user.id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="项目不存在"
            )

        projects = [project]
    else:
        # 检查用户所有项目
        projects, _ = await project_service.get_owner_projects(
            owner_id=current_user.id,
            page=1,
            size=1000
        )

    results = []
    for project in projects:
        if not project.file_path:
            results.append(FileIntegrityCheckResult(
                project_id=project.id,
                project_title=project.title,
                file_exists=False,
                file_size_match=None,
                file_hash_match=None,
                error="项目没有关联的文件"
            ))
            continue

        try:
            # 检查文件是否存在
            file_info = await storage_client.get_file_info(project.file_path)
            file_exists = file_info is not None

            if file_exists:
                # 检查文件大小是否匹配
                storage_size = file_info.get('size', 0)
                project_size = project.file_size or 0
                size_match = storage_size == project_size

                # 检查文件哈希是否匹配
                hash_match = file_info.get('metadata', {}).get('file_hash') == project.file_hash

                results.append(FileIntegrityCheckResult(
                    project_id=project.id,
                    project_title=project.title,
                    file_exists=file_exists,
                    file_size_match=size_match,
                    file_hash_match=hash_match,
                    storage_size=storage_size,
                    project_size=project_size,
                    error=None
                ))
            else:
                results.append(FileIntegrityCheckResult(
                    project_id=project.id,
                    project_title=project.title,
                    file_exists=False,
                    file_size_match=None,
                    file_hash_match=None,
                    error="文件在存储中不存在"
                ))

        except Exception as e:
            results.append(FileIntegrityCheckResult(
                project_id=project.id,
                project_title=project.title,
                file_exists=False,
                file_size_match=None,
                file_hash_match=None,
                error=f"检查失败: {str(e)}"
            ))

    # 统计结果
    total_checked = len(results)
    files_exist = sum(1 for r in results if r.file_exists)
    size_mismatch = sum(1 for r in results if r.file_exists and not r.file_size_match)
    hash_mismatch = sum(1 for r in results if r.file_exists and not r.file_hash_match)

    integrity_score = round(((files_exist - size_mismatch - hash_mismatch) / total_checked * 100) if total_checked > 0 else 0, 2)

    return FileIntegrityCheckResponse(
        success=True,
        project_id=project_id,
        total_checked=total_checked,
        files_exist=files_exist,
        files_missing=total_checked - files_exist,
        size_mismatch=size_mismatch,
        hash_mismatch=hash_mismatch,
        integrity_score=integrity_score,
        results=results,
    )


__all__ = ["router"]
