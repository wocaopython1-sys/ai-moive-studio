# AICON 阶段 2H Summary

## 1. 阶段目标

阶段 2H 是“合成导出异步化 / 防 HTTP 超时”。目标是在阶段 2G 已打通同步视频片段排序与 ffmpeg concat 导出的基础上，把合成导出改为异步任务：前端提交后后端快速返回 processing，Celery 后台执行 ffmpeg concat，任务中心追踪 processing / completed / failed，完成后回写最终 VideoNode、保存 source VideoNode -> final VideoNode connection，并保证最终 MP4 可 preview / stream / download、素材库可见、保存刷新恢复。

本阶段不是高级时间线；本阶段不做字幕、转场、配乐；本阶段不触发模型生成。

## 2. 异步环境检查结果

- Celery worker 可复用，`canvas.compose_video` 已注册并执行成功。
- backend 容器内保留阶段 2G 已验证的 ffmpeg 环境，本阶段没有修改 Dockerfile。
- 本阶段复用现有 CanvasItem / CanvasItemGeneration / CanvasConnection，不新增数据库字段。
- 当前用 `processing` 表示 composing，不新增状态枚举。

## 3. Celery worker 复用说明

阶段 2H 复用已有 Celery worker，而不是新增独立任务系统。compose API 在 `async: true` 时创建 processing generation 与 processing final VideoNode，然后投递 Celery 任务 `canvas.compose_video`，由 worker 后台执行合成与回写。

## 4. canvas.compose_video 注册说明

新增 Celery task：`canvas.compose_video`。该任务接收 `generation_id`，调用 `CanvasService.process_video_compose(generation_id)`，完成 ffmpeg concat、上传最终 MP4、回写 final VideoNode、创建 source -> final connections，并更新 generation 状态。

## 5. compose API async 参数说明

复用现有接口：

```http
POST /api/v1/canvas-documents/{document_id}/videos/compose
```

新增请求参数：

```json
{
  "async": true
}
```

- `async: true`：异步模式，API 立即返回 `status=processing`、`generation_id`、`task_id`、`created_item`。
- `async: false` 或未传：保留阶段 2G 同步 compose 路径，避免破坏既有能力。

本阶段增强现有 compose API，没有新增独立新 API。

## 6. 异步任务创建结果

真实验证中，async compose API 约 0.444s 返回 processing，没有等待完整 ffmpeg 合成完成。

验证记录：

- Canvas ID：`60aaebb2-1eed-44e7-b718-e6015b2d4c2d`
- Generation ID：`efec7d85-1854-4962-9fde-1aa66d09a48e`
- Celery task ID：`7f5e96ec-b4a3-4f7c-b154-88a3d7c8a4e7`
- Final VideoNode ID：`9d61fed9-0fe8-4d15-b463-74a44a5fde82`

## 7. final VideoNode processing 创建结果

异步请求返回时已创建 final VideoNode，初始状态为 `processing`，前端可立即在 Canvas 中显示合成中节点，不需要长时间阻塞 HTTP 请求。

## 8. ffmpeg 后台合成结果

Celery 后台执行 ffmpeg concat，约 3.28s 完成。合成完成后最终 MP4 上传到媒体存储。

最终 object_key：

```text
uploads/e25665b8-8b5f-441a-8f3c-ac0df7884653/20260702/a936bb4f-a78c-482e-969c-0b62dd05bbdf.mp4
```

## 9. final VideoNode completed 回写结果

后台任务完成后，final VideoNode 已从 `processing` 更新为 `completed`，并写入 `result_video_object_key`。graph API 和 DB 均可看到最终 VideoNode 为 completed。

## 10. source -> final connection 保存结果

两个 source VideoNode 到 final VideoNode 的 connection 已保存，DB / graph 均确认 2 条 connection。

## 11. 任务中心状态展示结果

任务中心能看到本次异步合成记录：

- status：`completed`
- mode：`concat`
- clip_count：`2`
- source_videos：`2`

任务中心展示复用已有 generation history 与 params 展示逻辑。本阶段没有直接修改 `frontend/src/views/TasksHistory.vue` 或 `frontend/src/services/taskHistory.js`。

## 12. preview / stream / download 验证结果

最终 MP4 三个入口均验证通过：

- preview：200，Content-Type `video/mp4`
- stream：200，Content-Type `video/mp4`
- download：200，Content-Type `video/mp4`

## 13. 素材库最终视频可见结果

`/api/v1/files/library` 返回 200，素材库能看到最终 MP4 object_key。

## 14. 保存刷新恢复结果

graph API 能看到 final VideoNode completed、object_key 和 2 条 source -> final connection；刷新后仍可恢复最终节点和连接关系。

## 15. 失败场景验证结果

轻量失败场景已验证：只选择 1 个视频时返回 400，错误信息为“至少选择 2 个视频才能合成”。没有制造复杂失败，也没有触发模型生成。

## 16. 阶段 1A-2G 回归结果

不消耗模型的轻量回归通过：

- `/dashboard` 200
- `/canvas` 200
- `/library` 200
- `/tasks` 200
- `/health/` 200
- `/api/v1/tasks/history` 200
- `/api/v1/files/library` 200
- 任务中心能看到本次异步合成 completed 记录
- 任务中心能看到 `mode=concat / clip_count=2 / completed`
- 最终 MP4 preview / stream / download 均 200
- graph API 能看到 final VideoNode completed
- graph API 能看到 2 条 source VideoNode -> final VideoNode connection
- 素材库能看到最终 MP4
- PNG 上传 200
- MP4 上传 200
- 阶段 2E 批量 Prompt 图片仍存在
- 阶段 2F 批量图生视频记录仍存在
- 阶段 2G 同步 compose API 仍存在并保留校验
- 阶段 2D retry / refresh / resume 按钮仍存在
- 后端日志无新增 AICON 代码级 500 / Traceback

## 17. 改动文件清单

- `backend/src/api/schemas/canvas.py`
  - `CanvasComposeVideosRequest` 增加 `async` alias 参数。
  - `CanvasComposeVideosResponse` 增加 `generation_id`、`task_id`，并支持 processing 返回时媒体 URL 为空。

- `backend/src/api/v1/canvas.py`
  - compose API 增加 async 分支。
  - async 模式创建 processing 记录后投递 `canvas.compose_video`。
  - 同步模式保留阶段 2G 路径。

- `backend/src/services/canvas.py`
  - 将 2G 同步 compose 逻辑拆分为可复用 helper。
  - 新增 `prepare_video_compose` 创建 processing final VideoNode 和 processing generation。
  - 新增 `process_video_compose` 供 Celery 后台执行 ffmpeg concat 并回写结果。
  - 失败时写入 failed 与 error_message。

- `backend/src/tasks/canvas.py`
  - 注册 Celery task `canvas.compose_video`。

- `frontend/src/views/canvas/CanvasEditor.vue`
  - compose 请求增加 `async: true`。
  - 提交后立即提示任务已提交。
  - 轮询 graph，把 processing final VideoNode 更新为 completed / failed。

## 18. 验证结果

- `python3 -m py_compile backend/src/api/schemas/canvas.py backend/src/api/v1/canvas.py backend/src/services/canvas.py backend/src/tasks/canvas.py` 通过。
- `git diff --check` 通过。
- backend / frontend / celery-worker / celery-beat 部署后运行正常。
- Celery task `canvas.compose_video` 已注册。
- async compose 真实验证通过。
- 不消耗模型轻量回归通过。
- diff 边界检查通过：没有 Dockerfile、Provider、New API、media-gateway、htpasswd、临时测试文件进入 diff。
- 敏感信息扫描未发现真实 key / token 进入 diff。

## 19. 未完成但不阻塞的问题

- 当前没有进度百分比，只显示 processing / completed / failed，符合本阶段最小闭环边界。
- 当前没有高级时间线、字幕、转场、配乐，符合本阶段边界。
- `phase2h-task-history-compose-status.diff` 为空，因为任务中心展示复用既有 params 展示能力，本阶段没有直接改任务中心文件。

## 20. 回滚方式

如需回滚阶段 2H，可在当前分支上回退本阶段未提交 diff，或在 commit 后通过 `git revert <phase2h_commit>` 回滚。回滚范围应包含：

- `backend/src/api/schemas/canvas.py`
- `backend/src/api/v1/canvas.py`
- `backend/src/services/canvas.py`
- `backend/src/tasks/canvas.py`
- `frontend/src/views/canvas/CanvasEditor.vue`
- `PHASE2H_SUMMARY.md`

回滚后阶段 2G 同步 compose 能力应恢复为稳定基线。

## 21. 下一步建议

下一步只建议在用户确认后提交阶段 2H 本地 commit，固化“异步合成导出 / 防 HTTP 超时”稳定基线。

## 22. 明确边界

- 本阶段不触发模型生成。
- 本阶段复用 Celery。
- 本阶段增强现有 compose API，没有新增独立新 API。
- 本阶段新增 `async: true` 参数。
- 本阶段没有新增数据库字段。
- 本阶段没有修改 Dockerfile。
- 本阶段没有改 Provider / New API / media-gateway。
- 当前没有 commit。
- `.env.demo` 和 `PHASE0_BASIC_AUTH.txt` 不进入 patch / commit。