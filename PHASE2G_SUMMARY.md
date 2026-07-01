# AICON Phase 2G Summary

## 1. 阶段目标

阶段 2G 是“视频片段排序 / 合成导出最小闭环”。目标是让用户从多个已完成的 VideoNode / 视频素材中选择片段，设置顺序，合成为一个最终 MP4，并回写 Canvas、素材库和任务中心。

本阶段不是高级时间线，不做字幕、转场、配乐，不触发任何模型生成。

## 2. 合成环境检查结果

- backend 容器内已存在 ffmpeg。
- ffmpeg 路径：`/usr/bin/ffmpeg`。
- ffmpeg 版本：`ffmpeg version 7.1.5-0+deb13u1`。
- Dockerfile 原本已包含 ffmpeg，本阶段没有修改 Dockerfile。
- 后端适合执行当前最小闭环的短视频 concat 合成；长视频或复杂导出后续建议迁移到后台任务队列。

## 3. 后端合成 API

本阶段新增最小后端 API：

`POST /api/v1/canvas-documents/{document_id}/videos/compose`

请求核心字段：

- `source_item_ids`：待合成的 VideoNode ID 列表。
- `title`：最终 VideoNode 标题。
- `mode`：当前为 `concat`。
- `options.order`：前端排序后的 VideoNode 顺序。

接口行为：

1. 校验至少 2 个、最多 5 个视频。
2. 校验来源节点均为 completed VideoNode。
3. 校验每个 VideoNode 有可用 `object_key`。
4. 从媒体存储下载源 MP4 到临时目录。
5. 使用 ffmpeg concat demuxer 合成最终 MP4。
6. 上传最终 MP4 到 MinIO / 媒体存储。
7. 创建最终 VideoNode。
8. 创建 source VideoNode -> final VideoNode connections。
9. 创建 completed generation 记录，供任务中心展示。

## 4. VideoNode 选择说明

前端在 Canvas 中新增轻量“合成视频”入口，不重构整体 UI，不引入复杂时间线。

面板能力：

- 列出当前 Canvas 中的 VideoNode。
- 仅允许选择 completed 且有可用视频结果的 VideoNode。
- 支持选择 2-5 个视频。
- 不可用节点显示为不可选。

## 5. 视频排序说明

合成面板支持“上移 / 下移”调整顺序。最终顺序写入 `options.order`，并作为后端合成顺序使用。

## 6. ffmpeg concat 合成方案

本阶段采用后端同步执行的最小 MP4 concat 方案：

1. 后端下载多个源 MP4 到临时目录。
2. 写入 ffmpeg concat list。
3. 使用 ffmpeg concat demuxer 读取多个片段。
4. 使用 `libx264` 重新编码，输出 `yuv420p`、`faststart` 的 MP4。
5. 上传最终 MP4 到媒体存储。

该方案满足当前 2G 最小闭环，不等同于完整剪辑器或高级导出系统。

## 7. 最终 VideoNode 回写结果

本阶段实际合成了 2 个视频片段为 1 个 MP4。

最终 VideoNode：

- ID：`5ef301f3-d4e8-4753-bd90-55c2298d2d08`
- 标题：`2G 合成视频验收`
- 状态：`completed`
- object_key：`uploads/e25665b8-8b5f-441a-8f3c-ac0df7884653/20260701/04c06b40-11d4-4a2a-951c-06f7ec29840f.mp4`

## 8. source VideoNode -> final VideoNode connection 保存结果

DB 已确认保存 2 条 source VideoNode -> final VideoNode connection。

来源视频：

- `4e977938-9971-4f4c-9645-fdcce7c987f9`
- `e346cec2-c0fb-44c6-a847-8e516d3eed41`

最终视频：

- `5ef301f3-d4e8-4753-bd90-55c2298d2d08`

## 9. preview / stream / download 验证结果

最终 MP4 三个入口均已验证：

- preview：200，Content-Type `video/mp4`
- stream：200，Content-Type `video/mp4`
- download：200，Content-Type `video/mp4`

## 10. 素材库最终视频可见结果

`/api/v1/files/library` 可访问，素材库能看到最终合成 MP4。

## 11. 任务中心合成记录结果

任务中心能看到本次合成 generation：

- generation ID：`768c2901-e05d-42a9-afa2-a01d2ee42eb0`
- status：`completed`
- mode：`concat`
- clip_count：`2`
- provider/model：本地 `ffmpeg-concat`

任务中心参数展示已增强，支持显示 `mode`、`clip_count`、`source_videos`。

## 12. 保存刷新恢复结果

graph / DB 能看到最终 VideoNode 和 2 条 source -> final connections。保存刷新后最终 VideoNode 和连接关系可恢复。

## 13. 阶段 1A-2F 回归结果

本阶段轻量回归不消耗模型，已确认：

- `/dashboard` 200
- `/canvas` 200
- `/library` 200
- `/tasks` 200
- `/health/` 200
- `/api/v1/tasks/history` 200
- `/api/v1/files/library` 200
- 最终 MP4 preview / stream / download 200
- graph API 能看到最终 VideoNode
- graph API 能看到 2 条 source VideoNode -> final VideoNode connection
- 阶段 2E 批量 Prompt 图片仍存在
- 阶段 2F 批量图生视频记录仍存在
- 阶段 2D retry / refresh / resume 按钮仍存在
- PNG 上传 200
- MP4 上传 200
- 后端日志无新增 AICON 代码级 500 / Traceback

## 14. 改动文件清单

- `backend/src/api/schemas/canvas.py`
  - 新增 `CanvasComposeVideosRequest`。
  - 新增 `CanvasComposeVideosResponse`。

- `backend/src/api/v1/canvas.py`
  - 新增 `/videos/compose` API route。
  - 返回最终 VideoNode、generation、connections、preview/stream/download URL。

- `backend/src/services/canvas.py`
  - 新增 `_video_object_key_from_item`。
  - 新增 `compose_videos`。
  - 实现源视频下载、ffmpeg concat、结果上传、最终 VideoNode 创建、connections 创建、generation 记录创建。
  - 增强任务参数摘要，支持 `mode`、`clip_count`、`source_videos`。

- `frontend/src/services/canvas.js`
  - 新增 `composeVideos(documentId, payload)`。

- `frontend/src/views/canvas/CanvasEditor.vue`
  - 新增“合成视频”入口。
  - 新增轻量 VideoNode 选择/排序面板。
  - 支持 2-5 个视频排序合成。
  - 调用 compose API，成功后回写最终 VideoNode、connections，并聚焦最终节点。

- `frontend/src/views/TasksHistory.vue`
  - 增强任务参数展示，支持显示合成模式、片段数、来源视频数量。

## 15. 验证结果

- `git diff --check` 通过。
- backend/frontend 服务 healthy。
- backend 容器 ffmpeg 可用。
- 最终 MP4 preview / stream / download 均 200。
- DB 确认最终 VideoNode completed。
- DB 确认合成 generation completed。
- DB 确认 2 条 source -> final connections。
- diff 未发现真实 key / token / htpasswd。
- Dockerfile 未修改。

## 16. 未完成但不阻塞的问题

- 当前合成接口为同步执行，适合最小闭环和短视频片段；后续如果合成长视频、更多片段或加入复杂导出，应迁移到后台任务队列，避免 HTTP 请求超时。
- 本阶段不包含高级时间线、字幕、转场、配乐。
- 本阶段不做批量复杂剪辑，也不做作品库重构。

## 17. 回滚方式

如需回滚阶段 2G，可在未 commit 前直接丢弃以下文件改动：

- `backend/src/api/schemas/canvas.py`
- `backend/src/api/v1/canvas.py`
- `backend/src/services/canvas.py`
- `frontend/src/services/canvas.js`
- `frontend/src/views/TasksHistory.vue`
- `frontend/src/views/canvas/CanvasEditor.vue`
- `PHASE2G_SUMMARY.md`

也可使用 patch 目录中的 `phase2g-all.diff` 作为审阅和反向应用依据。

## 18. 下一步建议

下一步只建议等待用户确认后 commit 固化阶段 2G。

## 19. 明确边界

- 本阶段新增后端 API：`POST /api/v1/canvas-documents/{document_id}/videos/compose`。
- 本阶段没有新增数据库字段。
- 本阶段没有修改 Dockerfile。
- 本阶段没有改 Provider / New API / media-gateway。
- 本阶段没有触发模型生成。
- 当前没有 commit。
- `.env.demo` 和 `PHASE0_BASIC_AUTH.txt` 不进入 patch / commit。