"""Works library API schemas."""

from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from .base import PaginatedResponse, SuccessResponse, UUIDMixin

WorkStatusValue = Literal["archived", "hidden", "deleted"]


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


class WorkCreateFromCanvasFinalRequest(BaseModel):
    canvas_id: UUID
    canvas_item_id: UUID
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    cover_object_key: Optional[str] = Field(None, max_length=500)


class WorkUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    status: Optional[WorkStatusValue] = None
    cover_object_key: Optional[str] = Field(None, max_length=500)

    model_config = {"extra": "forbid"}


class WorkItemResponse(UUIDMixin):
    id: UUID
    work_id: UUID
    user_id: UUID
    role: str
    object_key: str
    media_type: str
    source_canvas_id: Optional[UUID] = None
    source_canvas_item_id: Optional[UUID] = None
    source_generation_id: Optional[UUID] = None
    sort_order: int
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str

    @classmethod
    def from_model(cls, item):
        return cls(
            id=item.id,
            work_id=item.work_id,
            user_id=item.user_id,
            role=item.role,
            object_key=item.object_key,
            media_type=item.media_type,
            source_canvas_id=item.source_canvas_id,
            source_canvas_item_id=item.source_canvas_item_id,
            source_generation_id=item.source_generation_id,
            sort_order=item.sort_order,
            metadata_json=item.metadata_json or {},
            created_at=_iso(item.created_at) or "",
            updated_at=_iso(item.updated_at) or "",
        )


class WorkResponse(UUIDMixin):
    id: UUID
    user_id: UUID
    title: str
    description: Optional[str] = None
    status: str
    cover_object_key: Optional[str] = None
    final_object_key: str
    source_canvas_id: Optional[UUID] = None
    source_canvas_item_id: Optional[UUID] = None
    source_generation_id: Optional[UUID] = None
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    deleted_at: Optional[str] = None
    created_at: str
    updated_at: str

    @classmethod
    def from_model(cls, work):
        return cls(
            id=work.id,
            user_id=work.user_id,
            title=work.title,
            description=work.description,
            status=work.status,
            cover_object_key=work.cover_object_key,
            final_object_key=work.final_object_key,
            source_canvas_id=work.source_canvas_id,
            source_canvas_item_id=work.source_canvas_item_id,
            source_generation_id=work.source_generation_id,
            metadata_json=work.metadata_json or {},
            deleted_at=_iso(work.deleted_at),
            created_at=_iso(work.created_at) or "",
            updated_at=_iso(work.updated_at) or "",
        )


class WorkDetailResponse(WorkResponse):
    items: List[WorkItemResponse] = Field(default_factory=list)

    @classmethod
    def from_model(cls, work):
        base = WorkResponse.from_model(work).model_dump()
        base["items"] = [WorkItemResponse.from_model(item) for item in list(work.items or [])]
        return cls(**base)


class WorkListResponse(PaginatedResponse):
    works: List[WorkResponse] = Field(default_factory=list)


class WorkDeleteResponse(SuccessResponse):
    work_id: UUID
