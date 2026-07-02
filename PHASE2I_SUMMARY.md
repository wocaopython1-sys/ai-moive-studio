# PHASE2I_SUMMARY

## 1. 阶段目标

阶段 2I 是“一键工作流编排 / 从分镜到成片的最小流水线”。

目标是把阶段 2E 到 2H 已打通的分散能力串成一个最小闭环：

1. 用户选择 2 个 Prompt / 分镜文本节点。
2. 工作流复用已有 TextNode -> ImageNode -> VideoNode 链路。
3. 调用阶段 2H 的异步 compose 能力合成最终 MP4。
4. Canvas 保留 TextNode -> ImageNode -> VideoNode -> FinalVideoNode 连接。
5. 任务中心可看到 workflow_id / workflow_stage。
6. 素材库可见最终成片。
7. 保存刷新后仍可恢复。

## 2. 阶段定位说明

本阶段不是全自动 workflow engine。

本阶段采用“前端轻量编排 + 复用已有结果 + 异步合成”的最小闭环：

1. 前端生成 workflow_id。
2. 前端选择 Prompt 节点。
3. 前端检查已有 completed ImageNode / VideoNode。
4. 前端调用已有异步 compose API。
5. workflow 元数据写入 generation options / params summary。

本阶段没有新增后端 workflow engine，没有新增数据库字段，没有新增独立后端 API。

## 3. 只读梳理结果

| 检查项 | 当前结果 | 是否可复用 |
|---|---|---|
| Prompt 批量生成图片 | 阶段 2E 入口仍存在 | 是 |
| ImageNode 批量图生视频 | 阶段 2F 入口仍存在 | 是 |
| 视频异步合成 | 阶段 2H compose async 继续复用 | 是 |
| connection 链路 | Text -> Image 2 条、Image -> Video 2 条、Video -> Final 2 条 | 是 |
| 任务中心 params 展示 | 已增加 workflow 字段展示 | 是 |
| batch_id / batch_index | 原有 batch 展示保留 | 是 |
| retry / refresh / resume | 阶段 2D 按钮仍存在 | 是 |
| workflow_id | 本阶段新增到 options / params summary | 是 |

## 4. 工作流入口说明

Canvas 增加“分镜成片”入口。

入口位于 Canvas 顶部轻量操作区域，和“批量生成图片”“批量生成视频”“合成视频”并列。打开后显示分镜成片面板。

## 5. Prompt 节点选择说明

分镜成片面板列出当前 Canvas 中可用的 Prompt / Text 节点。

本阶段限制一次选择 2 个 Prompt 节点，避免把阶段 2I 扩大成重型队列系统。

面板提供：

1. Prompt 节点列表。
2. 当前 Prompt 的链路状态。
3. “检查链路” dry-run 操作。
4. “生成成片”执行入口。
5. reuse / fill_missing 模式选择。

## 6. 复用已有 ImageNode 结果

本轮验收采用“复用已有结果”模式。

已复用 2 个 completed ImageNode：

1. `dae8f28b-2549-4993-8461-d005eb5454f8`
2. `d1794b24-e273-4eac-9695-f29f054ef750`

本阶段没有触发图片模型生成。

## 7. 复用已有 VideoNode 结果

本轮验收复用 2 个 completed VideoNode：

1. `4e977938-9971-4f4c-9645-fdcce7c987f9`
2. `e346cec2-c0fb-44c6-a847-8e516d3eed41`

本阶段没有触发图生视频模型生成。

## 8. 异步合成调用结果

分镜成片工作流调用阶段 2H 已有异步合成能力：

`POST /api/v1/canvas-documents/{document_id}/videos/compose`

调用参数包含：

1. `async: true`
2. `mode: concat`
3. `options.order`
4. `workflow_id`
5. `workflow_label`
6. `workflow_stage`
7. `workflow_stage_index`
8. `workflow_prompt_item_ids`
9. `workflow_image_item_ids`
10. `workflow_video_item_ids`

本阶段没有新增后端 API。

## 9. workflow_id / workflow_stage 标记结果

验收 workflow：

`phase2i-smoke-1782987186`

任务中心可见：

1. `workflow_id=phase2i-smoke-1782987186`
2. `workflow_label=分镜成片`
3. `workflow_stage=compose`
4. `workflow_stage_index=3`
5. `workflow_prompts=2`
6. `workflow_images=2`
7. `workflow_videos=2`
8. `clip_count=2`

## 10. 最终成片生成结果

最终 VideoNode：

`011c4998-0893-4a92-9416-747e6093f94d`

状态：

`completed`

最终 MP4 object key：

`uploads/e25665b8-8b5f-441a-8f3c-ac0df7884653/20260702/fa52ffb3-a912-4193-9ac3-4b9f7c32f142.mp4`

本阶段实际生成内容是复用已有图片 / 视频，只通过异步 ffmpeg compose 合成 1 个最终 MP4。

## 11. Text -> Image -> Video -> Final connection 链路结果

DB / graph 已确认：

| 链路 | 数量 |
|---|---:|
| TextNode -> ImageNode | 2 |
| ImageNode -> VideoNode | 2 |
| VideoNode -> FinalVideoNode | 2 |

完整链路保留在 Canvas graph 中，保存刷新后可恢复。

## 12. 任务中心展示结果

任务中心能看到本次 workflow 合成记录：

1. workflow history matches = 1
2. status = completed
3. mode = concat
4. clip_count = 2
5. workflow_id / workflow_stage / workflow counts 可见

`backend/src/services/canvas.py` 增强了任务 params summary，使 workflow metadata 能进入任务中心摘要。

`frontend/src/views/TasksHistory.vue` 增强了展示格式，显示工作流、阶段、Prompt / 图片 / 视频数量。

## 13. 素材库成片可见结果

`/api/v1/files/library` 返回 200。

最终 MP4 在素材库可见。

最终 MP4 媒体入口验证：

1. preview 200
2. stream 200
3. download 200
4. Content-Type = video/mp4

## 14. 阶段 1A-2H 回归结果

已完成轻量回归：

1. `/dashboard` 200
2. `/canvas` 200
3. `/library` 200
4. `/tasks` 200
5. `/health/` 200
6. `/api/v1/tasks/history` 200
7. `/api/v1/files/library` 200
8. 图片 preview / download 200
9. 视频 preview / stream / download 200
10. 阶段 2E 批量 Prompt 图片入口仍存在
11. 阶段 2F 批量图生视频入口仍存在
12. 阶段 2G 同步 compose API 仍存在，并对 1 clip 返回预期 400
13. 阶段 2H async compose 仍存在
14. 阶段 2D retry / refresh / resume 按钮仍存在
15. 后端日志无新增 AICON 代码级 500 / Traceback
16. Celery 日志无新增 AICON 代码级 Exception

PNG / MP4 上传能力沿用前一轮轻量回归结果，本轮没有再次制造上传素材，避免污染 2I 固化结果。

## 15. 改动文件清单

| 文件 | 改动 |
|---|---|
| `frontend/src/views/canvas/CanvasEditor.vue` | 新增“分镜成片”轻量面板、Prompt 选择、链路检查、reuse 编排、workflow metadata、异步 compose 调用与轮询状态衔接 |
| `frontend/src/views/TasksHistory.vue` | 任务中心展示 workflow label/id、stage、Prompt / image / video counts |
| `backend/src/services/canvas.py` | 任务 params summary 增加 workflow / batch / source 字段摘要 |

## 16. 验证结果

| 项目 | 结果 |
|---|---|
| git diff --check | 通过 |
| Python py_compile | `backend/src/services/canvas.py` 通过 |
| Docker build | backend / frontend 构建通过 |
| 页面入口 | dashboard / canvas / library / tasks 均 200 |
| 业务 API | tasks/history / files/library / graph 带 token 均 200 |
| 媒体访问 | 图片 preview/download 200，最终 MP4 preview/stream/download 200 |
| 任务中心 | workflow_id / workflow_stage=compose 可见 |
| graph | final VideoNode completed，Text -> Image -> Video -> Final 链路存在 |
| 日志 | backend / celery 无新增 AICON 代码级 Traceback / 500 / Exception |

## 17. 未完成但不阻塞的问题

1. 本阶段不是全自动 workflow engine。
2. 本阶段不做复杂后端 workflow run 表。
3. 本阶段不做复杂进度条、自动回滚、并发队列调度。
4. 本阶段不做字幕、转场、配乐、高级时间线。
5. 本阶段没有完整浏览器点击截图。

## 18. fill_missing 未真实模型验证说明

`fill_missing` 路径已有前端代码：

1. 缺图片时可调用已有图片生成链路。
2. 缺视频时可调用已有图生视频链路。
3. 调用时会带 workflow metadata。

但本轮没有真实触发图片 / 视频模型生成。

因此 `fill_missing` 不能算完成，需要后续单独验收。

本阶段验收只覆盖 reuse existing results + async compose 的最小闭环。

## 19. 回滚方式

当前没有 commit。

如需回滚阶段 2I 未提交改动，可在确认后执行：

```bash
cd /opt/aicon-demo
git restore backend/src/services/canvas.py frontend/src/views/TasksHistory.vue frontend/src/views/canvas/CanvasEditor.vue
rm -f PHASE2I_SUMMARY.md
```

注意：不要删除 `.env.demo` 和 `PHASE0_BASIC_AUTH.txt`，它们是未跟踪文件且禁止提交。

## 20. 下一步建议

下一步只建议做阶段 2I commit 固化。

建议 commit message：

`phase2i: add storyboard workflow orchestration`

commit 前必须再次确认：

1. `.env.demo` 未提交。
2. `PHASE0_BASIC_AUTH.txt` 未提交。
3. 没有真实 key / token / htpasswd 进入 diff。
4. 没有 Dockerfile 改动。
5. 没有数据库 migration。

## 21. 当前状态

1. 当前分支：`phase2h-async-video-compose`
2. 当前未 commit。
3. 当前未 push。
4. `.env.demo` 和 `PHASE0_BASIC_AUTH.txt` 不进入 patch / commit。
5. 本阶段没有改 Provider / New API / media-gateway。
6. 本阶段没有新增数据库字段。
7. 本阶段没有新增后端 API。
