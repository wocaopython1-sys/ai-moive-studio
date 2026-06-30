from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class CanvasAssistantChatRequest(BaseModel):
    document_id: str = Field(..., description="当前画布文档 id")
    message: str = Field(..., min_length=1, description="用户输入的自然语言请求")
    session_id: str | None = Field(default=None, description="已有会话 id；为空时后端自动创建")
    api_key_id: str | None = Field(default=None, description="本轮 assistant 对话显式选择的 API key id")
    chat_model_id: str | None = Field(default=None, description="本轮 assistant 对话显式选择的文本模型 id")


class CanvasAssistantResumeRequest(BaseModel):
    document_id: str = Field(..., description="当前画布文档 id")
    session_id: str = Field(..., description="assistant 会话 id")
    interrupt_id: str = Field(..., description="待恢复的 interrupt id")
    decision: Literal["approve", "reject"] = Field(..., description="用户对 interrupt 的决策")
    selected_model_id: str | None = Field(default=None, description="用户在 interrupt 卡片里选择的模型 id")


class CanvasAssistantTurnResponse(BaseModel):
    session_id: str
    message: str = ""
    events: list[dict[str, Any]] = Field(default_factory=list)
    pending_interrupt: dict[str, Any] | None = None


class CanvasAssistantSuggestRequest(BaseModel):
    canvas_id: str = Field(..., description="当前画布文档 id")
    selected_item_id: str | None = Field(default=None, description="当前选中节点 id")
    action: Literal["optimize_prompt", "image_to_video_prompt", "storyboard"] = Field(..., description="助手动作")
    user_input: str | None = Field(default=None, description="用户额外输入")
    api_key_id: str | None = Field(default=None, description="文本模型 API key id")
    chat_model_id: str | None = Field(default=None, description="文本模型 id")


class CanvasAssistantSuggestResponse(BaseModel):
    action: str
    text: str
    suggested_title: str
    target: str = "new_text_node"
    selected_item: dict[str, Any] | None = None
    canvas_summary: dict[str, Any] = Field(default_factory=dict)


class CanvasAssistantApplyRequest(BaseModel):
    canvas_id: str = Field(..., description="当前画布文档 id")
    selected_item_id: str | None = Field(default=None, description="当前选中节点 id")
    mode: Literal["create_text_node", "update_selected_text_node"] = Field(..., description="写回模式")
    title: str | None = Field(default=None, description="节点标题")
    content: str = Field(..., min_length=1, description="写回文本")
    relation_source_item_id: str | None = Field(default=None, description="可选来源节点 id")
    position_x: float | None = None
    position_y: float | None = None


class CanvasAssistantApplyResponse(BaseModel):
    item: dict[str, Any]
    connection: dict[str, Any] | None = None
