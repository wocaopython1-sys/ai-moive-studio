# AICON 阶段 2A 总结：模型 / Provider / 生成参数功能闭环

## 1. 阶段目标

阶段 2A 的目标是打通 Canvas 生成链路中的模型选择、Provider 选择和生成参数传递闭环，让文本、图片、视频生成任务都能在任务中心看到 provider / model / params，并确认不同 Provider 的可用边界。

本阶段不是 UI 美化阶段，不接入 Dify，不重构作品库，不修改 New API / media-gateway / Cloudflare / Nginx / Basic Auth。

## 2. 已完成功能

- 文本模型选择已接入 Canvas 生成链路。
- 图片模型选择已接入 Canvas 生成链路。
- 图片尺寸 / 比例 / 数量参数已传入生成请求并记录。
- 视频比例 / 时长 / 参考图参数已传入生成请求并记录。
- 任务中心展示 provider / model / params。
- `/api/v1/canvas-model-catalog` 可返回当前 Canvas 可用模型目录。
- 视频 provider endpoint 根因已定位。
- 视频生成已通过 `cogvideox-3 + BigModel direct` 验证成功。
- 文生视频 completed，VideoNode 回写成功。
- 图生视频 completed，VideoNode 回写成功。
- 图生视频 `reference_images=1` 已记录。
- 图片 -> 视频 connection 已保存。
- 视频 stream/download 200。

## 3. 文本参数结果

- 已验证模型：`gpt-5.5`。
- 文本模型真实生成成功。
- 文本生成结果可写回 Canvas 节点。
- 任务中心可展示文本任务的 provider / model / params。

## 4. 图片参数结果

- 已验证模型：`gpt-image-2`。
- 图片真实生成成功。
- 图片尺寸 / 比例参数已传入生成链路。
- 已验证参数示例：`1024x1024`、`1:1`。
- 图片数量 `n=1` 已传入并记录。
- 图片任务在任务中心可展示 provider / model / params。
- 图片 preview/download 200。

## 5. 视频参数结果

- 已验证视频模型：`cogvideox-3`。
- 已验证 provider：BigModel direct，通过 AICON custom provider 分流。
- 已验证文生视频参数：`aspect_ratio=16:9`、`duration=5`、`duration_seconds=5`。
- 已验证图生视频参数：`aspect_ratio=16:9`、`duration=5`、`duration_seconds=5`、`reference_images=1`。
- 文生视频 completed，视频 object_key 已回写。
- 图生视频 completed，视频 object_key 已回写。
- 视频 stream/download 200。

## 6. 可用视频模型确认

当前真正可用的视频链路：

- model: `cogvideox-3`
- provider: BigModel direct
- create endpoint: `/api/paas/v4/videos/generations`
- status endpoint: `/api/paas/v4/async-result/{task_id}`

`/api/v1/canvas-model-catalog` 当前 video catalog 只暴露 `cogvideox-3`。

## 7. 不可用 / 未验证视频模型说明

`veo3.1-fast` 当前不是 AICON 默认可用模型，因为 New API video endpoint 未验证。

已确认：

- New API `/video/create` 返回 HTML，不是 JSON。
- New API `/v1/video/create` 返回 Invalid URL。
- 这不是 Canvas 参数没传，而是上游 video endpoint 兼容问题。

因此阶段 2A 不把 `veo3.1-fast` 作为默认视频模型，也不通过普通 New API compatible custom key 暴露未验证的视频模型。

## 8. 改动文件清单

| 文件 | 改动内容 |
|---|---|
| `backend/src/services/api_key.py` | custom provider 的模型目录按 base_url 分流；BigModel 视频只返回 `cogvideox-3`，非 BigModel custom key 不暴露未验证视频模型。 |
| `backend/src/services/canvas.py` | 增加文本/图片/视频 provider 参数整理；任务历史 params 摘要；视频 custom provider BigModel 校验；图生视频参考图 object_key 转公开媒体 URL；生成结果记录 provider/model/options。 |
| `backend/src/services/provider/custom_provider.py` | 适配图片/文本 provider 参数传递与返回解析。 |
| `backend/src/services/provider/vector_engine_provider.py` | 增加 BigModel 视频路径分流；ratio 转 size；duration 限制；非 JSON 响应给出清晰错误。 |
| `frontend/src/components/canvas/CanvasImageStudio.vue` | 图片生成参数输入与事件传递。 |
| `frontend/src/components/canvas/CanvasVideoStudio.vue` | 视频比例、时长、参考图相关参数传递。 |
| `frontend/src/composables/useCanvasEditor.js` | Canvas 生成 payload 中保留模型、key、参数。 |
| `frontend/src/utils/canvasGenerationPayload.js` | 生成 payload 参数规范化。 |
| `frontend/src/tests/unit/utils/canvasGenerationPayload.test.js` | 参数 payload 单元测试补充。 |
| `frontend/src/views/TasksHistory.vue` | 任务中心展示 provider / model / params。 |
| `frontend/src/views/canvas/CanvasEditor.vue` | 加载 Canvas 模型目录；选择 BigModel/video key 作为视频默认 key；传递文本/图片/视频参数。 |

## 9. 验证结果

已验证且不再额外触发模型生成：

- 文本模型 `gpt-5.5` 真实生成成功。
- 图片模型 `gpt-image-2` 真实生成成功。
- 文生视频 `cogvideox-3 + BigModel direct` completed。
- 图生视频 `cogvideox-3 + BigModel direct` completed。
- 图生视频记录 `reference_images=1`。
- 图片 -> 视频 connection 存在。
- 视频 stream/download 200。
- 图片 preview/download 200。
- PNG 上传 200。
- MP4 上传 200。
- `/dashboard`、`/canvas`、`/library`、`/tasks` 可访问。
- `/health/` 200。
- `/api/v1/canvas-model-catalog` 200。
- `/api/v1/tasks/history` 200。
- graph API 200。
- 后端最近日志无新增 500 / Traceback。

## 10. 未完成但不阻塞的问题

- `veo3.1-fast` 仍未通过 New API video endpoint 验证，不作为默认可用视频模型。
- New API 视频兼容路径需要后续单独确认，不在阶段 2A 内修改 New API 服务本身。
- 当前阶段只完成模型 / Provider / 参数闭环，不做模型广场、完整 Provider 管理后台或额度体系。

## 11. 回滚方式

当前阶段 2A 尚未 commit。可用 patch 反向回滚：

```bash
cd /opt/aicon-demo
git apply -R /opt/backups/aicon-demo-20260630-phase2a-patches/phase2a-all.diff
```

也可在 commit 前直接丢弃 tracked 改动，但必须注意不要误删未跟踪配置文件：

```bash
cd /opt/aicon-demo
git checkout -- backend/src/services/api_key.py \
  backend/src/services/canvas.py \
  backend/src/services/provider/custom_provider.py \
  backend/src/services/provider/vector_engine_provider.py \
  frontend/src/components/canvas/CanvasImageStudio.vue \
  frontend/src/components/canvas/CanvasVideoStudio.vue \
  frontend/src/composables/useCanvasEditor.js \
  frontend/src/tests/unit/utils/canvasGenerationPayload.test.js \
  frontend/src/utils/canvasGenerationPayload.js \
  frontend/src/views/TasksHistory.vue \
  frontend/src/views/canvas/CanvasEditor.vue
```

`.env.demo` 和 `PHASE0_BASIC_AUTH.txt` 是未跟踪文件，不进入阶段 2A patch / commit。

## 12. 下一步建议

下一步只建议在用户确认后执行阶段 2A 本地 commit 固化。不要进入新阶段，不要继续 UI 美化，不要接 Dify，不要重构作品库。

## 13. 明确边界

- 阶段 2A 是模型 / Provider / 生成参数功能闭环。
- 文本和图片参数链路已验证成功。
- 视频参数链路已通过 `cogvideox-3 + BigModel direct` 验证成功。
- `veo3.1-fast` 当前不是 AICON 默认可用模型，因为 New API video endpoint 未验证。
- New API `/video/create` 返回 HTML，不是 JSON。
- New API `/v1/video/create` 返回 Invalid URL。
- 这不是 Canvas 参数没传，而是上游 video endpoint 兼容问题。
- 本阶段没有新增后端 API。
- 本阶段没有新增数据库字段。
- 本阶段没有 commit。
- `.env.demo` 和 `PHASE0_BASIC_AUTH.txt` 不进入 patch / commit。
