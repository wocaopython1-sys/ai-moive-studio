"""
数据模型模块
"""

from src.models.api_key import APIKey, APIKeyProvider, APIKeyStatus
from src.models.base import Base, BaseModel
from src.models.bgm import BGM, BGMStatus
from src.models.canvas import (
    CanvasConnection,
    CanvasDocument,
    CanvasGenerationType,
    CanvasItem,
    CanvasItemGeneration,
    CanvasItemType,
    CanvasRunStatus,
)
from src.models.chapter import Chapter, ChapterStatus
from src.models.paragraph import Paragraph, ParagraphAction
from src.models.project import Project, ProjectStatus
from src.models.publish_task import BilibiliAccount, PublishTask, PublishStatus, PublishPlatform
from src.models.sentence import Sentence, SentenceStatus
from src.models.user import User
from src.models.movie import MovieCharacter, MovieScript, MovieScene, MovieShot, ScriptStatus
from src.models.video_task import VideoTask, VideoTaskStatus
from src.models.work import Work, WorkItem, WorkItemRole, WorkMediaType, WorkStatus

__all__ = [
    "Base",
    "BaseModel",
    "User",
    "Project",
    "ProjectStatus",
    "Chapter",
    "ChapterStatus",
    "Paragraph",
    "ParagraphAction",
    "Sentence",
    "SentenceStatus",
    "APIKey",
    "APIKeyStatus",
    "APIKeyProvider",
    "VideoTask",
    "VideoTaskStatus",
    "Work",
    "WorkItem",
    "WorkItemRole",
    "WorkMediaType",
    "WorkStatus",
    "BGM",
    "BGMStatus",
    "CanvasDocument",
    "CanvasItem",
    "CanvasConnection",
    "CanvasItemGeneration",
    "CanvasItemType",
    "CanvasRunStatus",
    "CanvasGenerationType",
    "PublishTask",
    "PublishStatus",
    "PublishPlatform",
    "BilibiliAccount",
    "MovieCharacter",
    "MovieScript",
    "MovieScene",
    "MovieShot",
    "ScriptStatus",
]
