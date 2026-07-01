# AICON Phase 2D Summary

## 1. 阶段目标

阶段 2D 是“生成任务重试 / 失败恢复 / 继续轮询”。目标是在不引入新生成系统、不改动外部网关、不新增数据库字段的前提下，让任务中心支持失败任务重试、provider 状态刷新、以及 provider 已完成但本地未拉回媒体时的继续同步。

## 2. 已完成功能

- 增强 failed 任务 retry 能力，基于原任务信息重建新的 generation。
- 新增 provider_task_id 的 refresh status 能力，用于查询上游任务真实状态。
- 新增 resume sync 能力，用于 provider 已 completed 但本地媒体未同步时补拉回。
- 历史 failed 视频任务已通过 refresh/resume 拉回 mp4，并恢复为 completed。
- VideoNode 已回写 object_key。
- 视频 stream/download 已验证 200。
- ImageNode 回写恢复逻辑复用原图片生成链路。
- 失败原因 error_message 保留，并继续在任务中心展示。
- 任务中心新增“重试 / 刷新状态 / 继续同步”按钮和 loading 状态。
- 跳转 Canvas 节点原逻辑保留。

## 3. retry 行为说明

retry 只适用于 failed 任务。它不覆盖原 failed 历史记录，而是读取原任务保存的 prompt、model、provider、params、source_item_id、canvas_id 等信息，重新创建一条 pending generation，并复用现有 Celery 生成任务派发逻辑。原 failed 任务保留，便于追溯失败原因。

不可恢复类错误，例如余额不足、模型不存在、endpoint 不兼容，会保留原因展示；用户可以手动重试，但系统不会把这类错误误判为已恢复。

## 4. refresh status 行为说明

refresh 用于有 provider_task_id 的任务。它会查询上游 provider 状态：

- 如果上游仍在 processing，则保持任务处理中或返回“仍在处理”的状态。
- 如果上游 completed，则拉回结果媒体、保存本地对象、更新任务记录，并回写 Canvas 节点。
- 如果上游 failed，则保留并展示 provider 失败原因。

refresh 是查询 provider_task_id 上游状态，不触发新的模型生成。

## 5. resume sync 行为说明

resume 用于 provider 已 completed 但本地未拉回媒体、object_key 为空或 Canvas 结果未完成的场景。它会基于 provider_task_id 再次查询上游结果，下载媒体，保存到本地对象存储，更新 Canvas item 和任务记录，补齐 stream/download 所需的 object_key。

resume 是在 provider 已 completed 但本地未拉回媒体时补同步，不创建新的 provider 任务。

## 6. 历史 failed 视频恢复 completed 验证结果

历史 failed 视频任务 `24de6625-e6c8-4217-8246-38323b69272c` 已通过 refresh/resume 恢复：

- provider_task_id: `202606291643456fcd9f09667d44c1`
- status: completed
- result video object_key: 已存在
- VideoNode: 已回写
- connection: 已保留

## 7. VideoNode object_key 回写结果

恢复后的 VideoNode 已写入视频 object_key，可通过现有媒体接口访问。该逻辑复用现有 Canvas 生成结果回写路径，避免重复创建错误节点。

## 8. stream/download 验证结果

恢复视频的 stream/download 已验证 200。常规视频 stream/download 回归也通过。

## 9. 失败原因展示说明

任务历史继续保留 error_message。余额不足、模型不存在、endpoint 不兼容、provider failed 等不可自动恢复错误不会被吞掉，任务中心继续展示明确原因，并允许用户按需手动重试。

## 10. 任务中心按钮说明

任务中心增加以下操作：

- 重试：failed 任务可见，调用 retry 接口并创建新的 generation。
- 刷新状态：有 provider_task_id 的任务可见，用于查询上游最新状态。
- 继续同步：有 provider_task_id 且可能存在本地媒体未同步的任务可见，用于补拉回 provider completed 结果。

按钮点击时有 per-task loading 状态，成功后刷新任务列表；跳转 Canvas 节点逻辑保持不变。

## 11. 改动文件清单

- `backend/src/api/v1/tasks.py`
  - 增强任务历史 retry 接口。
  - 增加 refresh/resume 操作入口。
- `backend/src/services/canvas.py`
  - 增加任务 action 加载、retry 派发、provider_task_id 解析、refresh/resume 同步逻辑。
  - 任务历史返回增加 provider_task_id 与可操作状态字段。
- `frontend/src/services/taskHistory.js`
  - 增加 refresh/resume 请求方法。
- `frontend/src/views/TasksHistory.vue`
  - 增加“重试 / 刷新状态 / 继续同步”按钮。
  - 增加 per-task loading 状态和操作后刷新列表。

## 12. 验证结果

- `/dashboard` 200。
- `/canvas` 200。
- `/library` 200。
- `/tasks` 200。
- `/health/` 200。
- `/api/v1/tasks/history` 200。
- 任务中心可显示“重试 / 刷新状态 / 继续同步”按钮。
- 历史恢复视频 stream/download 200。
- graph API 可看到恢复后的 VideoNode。
- graph API 可看到相关 connection。
- `/api/v1/files/library` 200。
- 图片 preview/download 200。
- 视频 stream/download 200。
- PNG 上传 200。
- MP4 上传 200。
- 多图 n=2 记录仍存在。
- 候选图 -> 图生视频记录仍存在。
- 后端日志无新增 500 / Traceback。

## 13. 未完成但不阻塞的问题

- 不可恢复类 provider 错误不会自动修复，只展示原因或允许用户手动重试。
- retry 会创建新的 generation，后续 commit 前仍应避免误点 retry 造成额外模型消耗。
- 本阶段没有做复杂任务状态机重构，也没有做全量 provider 失败类型归因系统。

## 14. 回滚方式

- 未 commit 前：使用 `git restore backend/src/api/v1/tasks.py backend/src/services/canvas.py frontend/src/services/taskHistory.js frontend/src/views/TasksHistory.vue` 回滚代码改动，并删除 `PHASE2D_SUMMARY.md`。
- 已 commit 后：使用 `git revert <phase2d_commit_id>` 回滚阶段 2D 改动。
- `.env.demo` 和 `PHASE0_BASIC_AUTH.txt` 不进入 patch / commit。

## 15. 下一步建议

等待用户确认后再创建阶段 2D commit。提交前应再次检查 git 状态，确保只添加阶段 2D 相关代码和 `PHASE2D_SUMMARY.md`，不要提交 `.env.demo`、`PHASE0_BASIC_AUTH.txt`、htpasswd、真实 key、临时测试脚本或临时结果文件。

## 16. 固化状态

- 本阶段没有触发新的模型生成。
- 本阶段没有新增数据库字段。
- 当前没有 commit。
- `.env.demo` 和 `PHASE0_BASIC_AUTH.txt` 不进入 patch / commit。
