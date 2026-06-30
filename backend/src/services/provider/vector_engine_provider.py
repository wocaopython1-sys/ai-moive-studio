import httpx
from typing import List, Optional, Dict, Any
from src.core.logging import get_logger
from src.services.provider.base import log_provider_call

logger = get_logger(__name__)

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
            if images:
                payload["image_url"] = images[0]

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                try:
                    response = await client.post(url, headers=self.headers, json=payload)
                    response.raise_for_status()
                    return self._parse_json_response(response, "BigModel Create")
                except httpx.HTTPStatusError as e:
                    logger.error(f"BigModel Create Failed: {e.response.text}")
                    raise
                except Exception as e:
                    logger.error(f"BigModel Create Error: {e}")
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
