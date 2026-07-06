"""Works library models."""

import uuid
from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from src.models.base import BaseModel
from src.models.canvas import CanvasGUID


class WorkStatus(str, Enum):
    ARCHIVED = "archived"
    HIDDEN = "hidden"
    DELETED = "deleted"


class WorkItemRole(str, Enum):
    FINAL = "final"
    COVER = "cover"
    SOURCE = "source"
    REFERENCE = "reference"
    INTERMEDIATE = "intermediate"


class WorkMediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    TEXT = "text"
    AUDIO = "audio"


class Work(BaseModel):
    __tablename__ = "works"

    id = Column(CanvasGUID(), primary_key=True, default=uuid.uuid4, nullable=False, comment="主键ID")
    user_id = Column(CanvasGUID(), nullable=False, index=True, comment="所属用户ID")
    title = Column(String(200), nullable=False, comment="作品标题")
    description = Column(Text, nullable=True, comment="作品描述")
    status = Column(String(30), nullable=False, default=WorkStatus.ARCHIVED.value, index=True, comment="作品状态")
    cover_object_key = Column(String(500), nullable=True, comment="封面对象键")
    final_object_key = Column(String(500), nullable=False, index=True, comment="最终作品对象键")
    source_canvas_id = Column(CanvasGUID(), ForeignKey("canvas_documents.id", ondelete="SET NULL"), nullable=True, index=True, comment="来源Canvas ID")
    source_canvas_item_id = Column(CanvasGUID(), ForeignKey("canvas_items.id", ondelete="SET NULL"), nullable=True, index=True, comment="来源Canvas节点ID")
    source_generation_id = Column(CanvasGUID(), ForeignKey("canvas_item_generations.id", ondelete="SET NULL"), nullable=True, index=True, comment="来源生成记录ID")
    metadata_json = Column(JSON, nullable=False, default=dict, comment="作品扩展元数据")
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True, comment="软删除时间")

    items = relationship("WorkItem", back_populates="work", cascade="all, delete-orphan", order_by="WorkItem.sort_order")

    __table_args__ = (
        UniqueConstraint("user_id", "source_canvas_item_id", "final_object_key", name="uq_works_user_canvas_item_final"),
    )


class WorkItem(BaseModel):
    __tablename__ = "work_items"

    id = Column(CanvasGUID(), primary_key=True, default=uuid.uuid4, nullable=False, comment="主键ID")
    work_id = Column(CanvasGUID(), ForeignKey("works.id", ondelete="CASCADE"), nullable=False, index=True, comment="所属作品ID")
    user_id = Column(CanvasGUID(), nullable=False, index=True, comment="所属用户ID")
    role = Column(String(30), nullable=False, index=True, comment="作品素材角色")
    object_key = Column(String(500), nullable=False, index=True, comment="对象键")
    media_type = Column(String(20), nullable=False, index=True, comment="媒体类型")
    source_canvas_id = Column(CanvasGUID(), ForeignKey("canvas_documents.id", ondelete="SET NULL"), nullable=True, index=True, comment="来源Canvas ID")
    source_canvas_item_id = Column(CanvasGUID(), ForeignKey("canvas_items.id", ondelete="SET NULL"), nullable=True, index=True, comment="来源Canvas节点ID")
    source_generation_id = Column(CanvasGUID(), ForeignKey("canvas_item_generations.id", ondelete="SET NULL"), nullable=True, index=True, comment="来源生成记录ID")
    sort_order = Column(Integer, nullable=False, default=0, comment="排序")
    metadata_json = Column(JSON, nullable=False, default=dict, comment="素材扩展元数据")

    work = relationship("Work", back_populates="items")

    __table_args__ = (
        Index("idx_work_items_work_role", "work_id", "role"),
    )


__all__ = ["Work", "WorkItem", "WorkItemRole", "WorkMediaType", "WorkStatus"]
