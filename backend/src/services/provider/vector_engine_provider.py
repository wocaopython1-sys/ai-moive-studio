import base64
import json

import httpx
from typing import List, Optional, Dict, Any
from src.core.logging import get_logger
from src.services.provider.base import log_provider_call

logger = get_logger(__name__)
BIGMODEL_VIDEO_CREATE_TIMEOUT_SECONDS = 180.0
BIGMODEL_CONNECT_TIMEOUT_SECONDS = 20.0

class VectorEngineProvider:
    """
    Vector Engine API 提供商 (api.vectorengine.ai)
    专门用于视频生成任务
    """

    def __init__(self, api_key: str, base_url: str = "https://api.vectorengine.ai/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        self.timeout = httpx.Timeout(60.0, connect=20.0)
        self.bigmodel_video_create_timeout = httpx.Timeout(
            BIGMODEL_VIDEO_CREATE_TIMEOUT_SECONDS,
            connect=BIGMODEL_CONNECT_TIMEOUT_SECONDS,
        )

    def _is_bigmodel(self) -> bool:
        return "bigmodel.cn" in str(self.base_url or "").lower()

    def _bigmodel_root(self) -> str:
        base = str(self.base_url or "https://open.bigmodel.cn/api/paas/v4").rstrip("/")
        if base.endswith("/api/paas/v4"):
            return base
        return f"{base}/api/paas/v4"

    def _normalize_bigmodel_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            return {}
        normalized = dict(payload)
        task_status = str(
            normalized.get("task_status")
            or normalized.get("status")
            or normalized.get("state")
            or ""
        ).strip()
        status_map = {
            "SUCCESS": "success",
            "SUCCEEDED": "success",
            "COMPLETED": "success",
            "PROCESSING": "processing",
            "RUNNING": "processing",
            "PENDING": "pending",
            "QUEUED": "pending",
            "FAIL": "failed",
            "FAILED": "failed",
            "ERROR": "failed",
        }
        if task_status:
            normalized["status"] = status_map.get(task_status.upper(), task_status.lower())

        video_result = normalized.get("video_result")
        if isinstance(video_result, list) and video_result:
            first_video = video_result[0] if isinstance(video_result[0], dict) else {}
            if first_video.get("url"):
                normalized["video_url"] = first_video["url"]
            if first_video.get("cover_image_url"):
                normalized["cover_image_url"] = first_video["cover_image_url"]
        return normalized

    def _bigmodel_size_from_aspect_ratio(self, aspect_ratio: str) -> str:
        ratio = str(aspect_ratio or "").strip()
        if ratio == "9:16":
            return "720x1280"
        if ratio == "1:1":
            return "1024x1024"
        return "1280x720"

    def _parse_json_response(self, response: httpx.Response, label: str) -> Dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            snippet = response.text[:300].strip()
            raise ValueError(f"{label} 返回非 JSON 响应: HTTP {response.status_code} {snippet}") from exc
        if self._is_bigmodel():
            return self._normalize_bigmodel_payload(payload)
        return payload

    def _detect_image_mime_type(self, image_bytes: bytes, fallback: Optional[str] = None) -> str:
        normalized = str(fallback or "").strip().lower()
        if normalized.startswith("image/"):
            return normalized.split(";", 1)[0]
        if image_bytes.startswith(b"\x89PNG"):
            return "image/png"
        if image_bytes.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if image_bytes.startswith((b"GIF87a", b"GIF89a")):
            return "image/gif"
        if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
            return "image/webp"
        return normalized or ""

    def _summarize_base64_image(self, raw_base64: str, mime_type: Optional[str] = None) -> Dict[str, Any]:
        summary: Dict[str, Any] = {
            "image_transport": "base64",
            "image_encoding": "raw_base64",
            "image_mime": mime_type or "",
            "base64_length": len(raw_base64 or ""),
        }
        try:
            image_bytes = base64.b64decode(raw_base64 or "", validate=True)
            summary["image_size_bytes"] = len(image_bytes)
            summary["image_mime"] = self._detect_image_mime_type(image_bytes, mime_type)
        except Exception:
            summary["image_size_bytes"] = None
        return summary

    def _normalize_bigmodel_image_url(self, image_value: Any) -> tuple[str, Dict[str, Any]]:
        normalized = str(image_value or "").strip()
        if not normalized:
            return "", {"image_transport": "empty", "image_encoding": "", "base64_length": 0}
        if normalized.startswith(("http://", "https://")):
            return normalized, {
                "image_transport": "public_url",
                "image_encoding": "url",
                "image_mime": "",
                "image_size_bytes": None,
                "base64_length": 0,
            }
        if normalized.startswith("data:image/") and "," in normalized:
            header, raw_base64 = normalized.split(",", 1)
            mime_type = header.split(":", 1)[-1].split(";", 1)[0]
            return raw_base64, self._summarize_base64_image(raw_base64, mime_type)
        return normalized, self._summarize_base64_image(normalized)

    def _payload_json_size(self, payload: Dict[str, Any]) -> int:
        try:
            return len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        except Exception:
            return 0

    def _safe_text(self, value: Any, limit: int = 500) -> str:
        text = str(value or "").strip()
        return text[:limit]

    def _bigmodel_create_log_summary(
        self,
        *,
        endpoint: str,
        payload: Dict[str, Any],
        image_summary: Dict[str, Any],
        exc: Optional[Exception] = None,
        response: Optional[httpx.Response] = None,
    ) -> Dict[str, Any]:
        response_body = response.text if response is not None else ""
        summary = {
            "exception_type": type(exc).__name__ if exc else "",
            "exception_message": self._safe_text(exc),
            "model": payload.get("model"),
            "endpoint": endpoint,
            "timeout_seconds": BIGMODEL_VIDEO_CREATE_TIMEOUT_SECONDS,
            "connect_timeout_seconds": BIGMODEL_CONNECT_TIMEOUT_SECONDS,
            "image_transport": image_summary.get("image_transport"),
            "image_encoding": image_summary.get("image_encoding"),
            "image_mime": image_summary.get("image_mime"),
            "image_size_bytes": image_summary.get("image_size_bytes"),
            "base64_length": image_summary.get("base64_length"),
            "payload_json_bytes": self._payload_json_size(payload),
            "has_response_body": bool(response_body),
            "response_status_code": response.status_code if response is not None else None,
            "response_body": self._safe_text(response_body),
        }
        return summary

    @log_provider_call("create_video")
    async def create_video(
        self, 
        prompt: str, 
        images: Optional[List[str]] = None, 
        model: str = "veo_3_1-fast", 
        aspect_ratio: str = "16:9",
        enable_upsample: bool = True,
        enhance_prompt: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        创建视频生成任务
        """
        if self._is_bigmodel():
            url = f"{self._bigmodel_root()}/videos/generations"
            duration_value = kwargs.get("duration") or kwargs.get("duration_seconds")
            size_value = kwargs.get("size") or self._bigmodel_size_from_aspect_ratio(aspect_ratio)
            payload = {
                "model": model or "cogvideox-3",
                "prompt": prompt,
                "size": size_value,
            }
            if duration_value:
                try:
                    payload["duration"] = max(5, min(int(duration_value), 10))
                except (TypeError, ValueError):
                    pass
            image_summary = {
                "image_transport": "none",
                "image_encoding": "",
                "image_mime": "",
                "image_size_bytes": None,
                "base64_length": 0,
            }
            if images:
                payload["image_url"], image_summary = self._normalize_bigmodel_image_url(images[0])

            async with httpx.AsyncClient(timeout=self.bigmodel_video_create_timeout) as client:
                try:
                    logger.info(
                        "BigModel Create payload summary: %s",
                        json.dumps(
                            self._bigmodel_create_log_summary(
                                endpoint=url,
                                payload=payload,
                                image_summary=image_summary,
                            ),
                            ensure_ascii=False,
                        ),
                    )
                    response = await client.post(url, headers=self.headers, json=payload)
                    response.raise_for_status()
                    return self._parse_json_response(response, "BigModel Create")
                except httpx.HTTPStatusError as e:
                    logger.error(
                        "BigModel Create Failed: %s",
                        json.dumps(
                            self._bigmodel_create_log_summary(
                                endpoint=url,
                                payload=payload,
                                image_summary=image_summary,
                                exc=e,
                                response=e.response,
                            ),
                            ensure_ascii=False,
                        ),
                    )
                    raise
                except Exception as e:
                    logger.error(
                        "BigModel Create Error: %s",
                        json.dumps(
                            self._bigmodel_create_log_summary(
                                endpoint=url,
                                payload=payload,
                                image_summary=image_summary,
                                exc=e,
                            ),
                            ensure_ascii=False,
                        ),
                    )
                    raise

        url = f"{self.base_url}/video/create"
        payload = {
            "prompt": prompt,
            "images": images or [],
            "model": model,
            "aspect_ratio": aspect_ratio,
            "enable_upsample": enable_upsample,
            "enhance_prompt": enhance_prompt
        }
        payload.update(kwargs)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, headers=self.headers, json=payload)
                response.raise_for_status()
                return self._parse_json_response(response, "Vector Engine Create")
            except httpx.HTTPStatusError as e:
                logger.error(f"Vector Engine Create Failed: {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Vector Engine Create Error: {e}")
                raise

    @log_provider_call("get_task_status")
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        查询任务状态
        """
        if self._is_bigmodel():
            url = f"{self._bigmodel_root()}/async-result/{task_id}"
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                try:
                    response = await client.get(url, headers=self.headers)
                    response.raise_for_status()
                    return self._normalize_bigmodel_payload(response.json())
                except Exception as e:
                    logger.error(f"BigModel Query Status Failed: {e}")
                    raise

        url = f"{self.base_url}/videos/{task_id}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Vector Engine Query Status Failed: {e}")
                raise

    @log_provider_call("get_video_content")
    async def get_video_content(self, task_id: str) -> Dict[str, Any]:
        """
        获取视频内容（包含下载链接）
        """
        if self._is_bigmodel():
            return await self.get_task_status(task_id)

        url = f"{self.base_url}/videos/{task_id}/content"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Vector Engine Get Content Failed: {e}")
                raise
