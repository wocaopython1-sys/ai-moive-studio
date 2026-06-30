# AICON 阶段 1B 总结：任务中心 / 生成历史最小闭环

## 1. 阶段目标

阶段 1B 的目标是在不进入作品库大重构、不新增复杂资产表、不重构 Provider / Celery / Dify 的前提下，补齐 AI 工作台最小可用的“任务中心 / 生成历史”能力。

目标能力：

1. 用户可以看到文本、图片、视频、助手写回等生成历史。
2. 用户可以看到任务状态、结果媒体、失败原因。
3. 已完成图片可预览 / 下载。
4. 已完成视频可 stream / 下载。
5. 失败任务可看到错误原因，并提示回到 Canvas 节点重新生成。
6. 用户可以从任务中心跳回对应 Canvas 节点，并自动带上 `item_id` 聚焦目标节点。

## 2. 已完成功能

1. 新增任务历史 API：`GET /api/v1/tasks/history`。
2. 新增任务详情 API：`GET /api/v1/tasks/history/{history_id}`。
3. 新增最小 retry 提示 API：`POST /api/v1/tasks/history/{history_id}/retry`，本阶段不做复杂重试调度，只返回 Canvas / item 定位信息和提示。
4. 复用现有 `canvas_item_generations`、`canvas_items`、`canvas_documents` 数据，不新增数据库字段。
5. 聚合图片、视频、助手写回文本节点、失败记录。
6. 新增前端 `/tasks` 任务中心页面。
7. 任务中心支持按类型筛选：全部 / 图片 / 视频 / 文本 / 助手。
8. 任务中心支持按状态筛选：全部状态 / 已完成 / 处理中 / 失败。
9. 任务卡片显示类型、状态、标题、模型、时间、失败原因。
10. 任务卡片支持查看详情、跳转 Canvas 节点、预览、下载、复制 URL。
11. Canvas 工具栏新增任务中心入口，进入当前 Canvas 的任务历史过滤视图。
12. Canvas 编辑页支持读取路由 `item_id` / `itemId` 并聚焦对应节点。

## 3. 新增 API

| API | 方法 | 作用 |
|---|---|---|
| `/api/v1/tasks/history` | GET | 查询任务历史，支持 `canvas_id`、`status`、`type`、`limit`、`offset` |
| `/api/v1/tasks/history/{history_id}` | GET | 查询单条任务详情 |
| `/api/v1/tasks/history/{history_id}/retry` | POST | 本阶段返回“回到 Canvas 节点重新生成”的提示，不做复杂调度 |

返回字段包含：

- `id`
- `type`
- `status`
- `title`
- `canvas_id`
- `canvas_title`
- `canvas_item_id`
- `source_item_id`
- `media_url`
- `preview_url`
- `download_url`
- `stream_url`
- `object_key`
- `error_message`
- `provider`
- `model`
- `created_at`
- `updated_at`
- `request_payload`
- `result_payload`

## 4. 新增前端页面

| 页面 | 路由 | 作用 |
|---|---|---|
| 任务中心 | `/tasks` | 查看全局或指定 Canvas 的任务历史、状态、结果媒体和失败原因 |

入口：

1. 左侧导航新增“任务中心”。
2. Canvas 工具栏新增任务中心按钮。
3. 从任务卡片点击“跳转 Canvas 节点”进入 `/canvas/{canvas_id}?item_id={canvas_item_id}`。

## 5. 改动文件清单

| 文件 | 改动内容 |
|---|---|
| `backend/src/api/v1/tasks.py` | 新增任务历史列表、详情、retry 提示接口；保留原 Celery task 状态接口 |
| `backend/src/services/canvas.py` | 新增 `CanvasTaskHistoryService`，从 generation / item / document 聚合任务历史 |
| `frontend/src/views/TasksHistory.vue` | 新增任务中心页面、筛选、详情、跳转、预览、下载、复制 URL |
| `frontend/src/services/taskHistory.js` | 新增任务历史 API service |
| `frontend/src/router/index.js` | 注册 `/tasks` 路由 |
| `frontend/src/components/layout/AppSidebar.vue` | 左侧导航新增任务中心入口 |
| `frontend/src/components/canvas/CanvasWorkbenchLayout.vue` | Canvas 工具栏新增任务中心按钮 |
| `frontend/src/views/canvas/CanvasEditor.vue` | 支持打开当前 Canvas 任务中心；支持根据 `item_id` 聚焦节点 |
| `frontend/src/services/canvas.js` | 增加 `listTaskHistory(params)` 轻量封装 |

## 6. 验证结果

### 6.1 公网任务中心跳转 smoke

公网入口：`http://aicon.geminiproo.shop`

结果：

| 流程 | 结果 |
|---|---|
| `/tasks` 页面加载 | 200，页面渲染 16 条任务 |
| 图片 completed 任务跳转 Canvas | 通过，URL 带 `item_id`，Canvas 渲染，右侧助手显示当前图片节点 |
| 视频 completed 任务跳转 Canvas | 通过，URL 带 `item_id`，Canvas 渲染，右侧助手显示当前视频节点 |
| assistant/text 记录跳转 Canvas | 通过，URL 带 `item_id`，Canvas 渲染，右侧助手显示当前文本节点 |

说明：公网 smoke 中屏蔽了媒体大文件加载，避免视频流拖慢页面验证。媒体接口另行用 API 回归验证。

### 6.2 轻量回归

不触发模型生成。

| 项目 | 结果 |
|---|---|
| frontend 首页 | 200 |
| backend `/health/` | 200 |
| files/list | 200 |
| PNG 上传 | 200，识别为 `image` |
| MP4 上传 | 200，识别为 `video` |
| `/api/v1/tasks/history` | 200，total 16 |
| 图片历史 | 200，total 7 |
| 视频历史 | 200，total 2 |
| 助手历史 | 200，total 7 |
| 失败历史 | 200，total 2 |
| 429 失败原因 | 正常展示：余额不足或无可用资源包 |
| 图片 preview/download | 200 / 200 |
| 视频 stream/download | 200 / 200 |
| graph API | 200，样例 Canvas 均返回节点和 connection |

备注：阶段 1B 回归脚本上传了测试 PNG / MP4，因此 files/list 数量从 16 增加到 18。这不消耗模型，也不影响任务历史数据。

## 7. 未完成但不阻塞的问题

1. retry 当前只是最小提示，不做自动重试调度。
2. 任务中心当前是最小卡片列表，不是完整作品库 / 资产库。
3. 任务历史数据来自现有 generation / Canvas item 聚合，不是独立任务流水表。
4. 本地 SSH tunnel 曾多次断开，不能作为 AICON 功能失败证据；最终公网 smoke 已补测通过。
5. `/tasks` 页面媒体缩略预览在 smoke 中屏蔽了媒体加载，媒体接口本身已通过 API 验证。

## 8. 回滚方式

当前阶段 1B 改动已在本地分支 `phase1b-task-history` 固化。

如果需要回滚阶段 1B：

```bash
cd /opt/aicon-demo
git log --oneline -5
# 找到 phase1b commit 的前一个 commit，例如阶段 1A commit 566fe3d
git checkout phase1b-task-history
git reset --hard 566fe3d
sudo docker compose -f docker-compose.demo.yml build frontend backend
sudo docker compose -f docker-compose.demo.yml up -d backend frontend celery-worker celery-beat
```

如果只想查看或手工回滚改动，可使用 patch 目录：

```bash
ls -lh /opt/backups/aicon-demo-20260630-phase1b-patches
```

patch 文件：

- `phase1b-all.diff`
- `phase1b-backend.diff`
- `phase1b-frontend.diff`
- `phase1b-task-history.diff`

## 9. 下一阶段建议

下一阶段只建议做：

1. 将任务中心和 Canvas 生成入口进一步联动：从失败任务回到节点后，能更明确地提示用户“重新生成”。
2. 再进入作品 / 素材库最小增强前，先保持当前任务历史 API 稳定。
3. 不建议马上重构数据库；等任务中心使用稳定后，再决定是否需要独立任务流水表。

## 10. 不要误判的点

1. 429 是模型账户 / 资源包问题，不等于 AICON 软件断链。
2. 本阶段 retry 不是完整队列重试系统，只是最小回到节点重试提示。
3. 任务中心不是完整作品库。
4. Dify 未接入，本阶段不处理。
5. 本地 SSH tunnel 断链不等于公网调试环境或 AICON 容器失败。
