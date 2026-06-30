# 阶段 1D 总结：工作台首页 / 创作入口最小产品化

## 1. 阶段目标

阶段 1D 的目标是把 AICON 的默认入口整理成一个内部可用的 AI 创作工作台首页，让用户打开系统后能清楚进入 Canvas、素材库、任务中心、上传素材和 Prompt / 图片 / 视频创作流程。

当前是“内部创作大厅”，不是官网首页。
当前不是社区首页。
当前不是模型广场。
当前不复刻 Liblib 首页。
当前目的只是把 Canvas / 素材库 / 任务中心 / 助手串成用户可理解的入口。

## 2. 已完成功能

- `/dashboard` 已替换为创作大厅。
- `/` 保持既定行为，继续重定向到 `/dashboard`。
- 快速开始卡片可用：
  - 新建 Canvas
  - 图片创作
  - 视频创作
  - 图生视频
  - Prompt / 分镜助手
  - 上传素材
  - 打开素材库
  - 任务中心
- 新建 Canvas 可用，点击后创建 Canvas 并跳转 `/canvas/{id}`。
- 最近 Canvas 可显示，并可继续编辑。
- 最近素材可显示图片、视频、文本 / Prompt。
- 最近素材可预览、下载并加入最近 Canvas。
- 最近任务可显示，并可跳转 Canvas 节点，带 `item_id`。
- 素材库入口可进入 `/library`。
- 任务中心入口可进入 `/tasks`。
- 侧边栏“控制台”已改为“创作大厅”。
- 首页标题已改为 `AICON AI 创作工作台`。
- 移除了不存在的 Vite favicon 噪音，并使用空 data favicon 避免 `/favicon.ico` 404 干扰日志。

## 3. 改动文件清单

| 文件 | 改动内容 |
|---|---|
| `frontend/src/views/Dashboard.vue` | 将旧控制台替换为创作大厅；前端聚合 Canvas、素材库、任务中心 API；增加快速入口、最近 Canvas、最近素材、最近任务、上传素材入口。 |
| `frontend/src/components/layout/AppSidebar.vue` | 将侧边栏“控制台”入口改为“创作大厅”。 |
| `frontend/index.html` | 页面标题改为 `AICON AI 创作工作台`；移除默认 Vite favicon；增加空 data favicon。 |

## 4. 验证结果

本阶段没有触发文本、图片或视频模型生成。

| 验证项 | 结果 |
|---|---|
| Docker 前端构建 | 通过 |
| frontend 容器 | healthy |
| backend `/health/` | 200 |
| `/dashboard` | 200 |
| `/` | 继续进入 `/dashboard` |
| 新建 Canvas | 通过，点击后跳转 `/canvas/{id}` |
| 素材库入口 | 通过，进入 `/library` |
| 任务中心入口 | 通过，进入 `/tasks` |
| 最近素材显示 | 通过，浏览器 smoke 显示图片、视频、文本素材 |
| 最近任务显示 | 通过，显示 8 条任务 |
| 最近任务跳转 | 通过，进入 Canvas 并带 `item_id` |
| 图片 preview/download | 200 |
| 视频 stream/download | 200 |
| PNG 上传 | 200 |
| MP4 上传 | 200 |
| 浏览器 console | 无阻塞错误 |

## 5. 未完成但不阻塞的问题

- Canvas 暂未消费 `mode` 参数，只作为入口标记，不阻塞当前创作大厅使用。
- Dashboard 的统计仍是轻量聚合，不是复杂数据大屏。
- 素材库仍是阶段 1C 的轻量素材库，不是完整作品库系统。
- 快速入口会创建 Canvas 并进入已有 Canvas 流程，不新增独立生成系统。

## 6. 回滚方式

如果需要回滚阶段 1D：

```bash
cd /opt/aicon-demo
git revert <phase1d_commit_id>
sudo docker compose -f docker-compose.demo.yml build frontend
sudo docker compose -f docker-compose.demo.yml up -d frontend
```

如果只想临时回滚工作区改动，且尚未提交：

```bash
cd /opt/aicon-demo
git restore frontend/index.html frontend/src/components/layout/AppSidebar.vue frontend/src/views/Dashboard.vue PHASE1D_SUMMARY.md
```

注意不要删除或提交 `.env.demo`、`PHASE0_BASIC_AUTH.txt`。

## 7. 下一阶段建议

下一阶段建议只做阶段 1E：围绕 Canvas 入口参数和创作模板做最小体验增强，例如让 `mode=image`、`mode=video`、`mode=i2v` 在 Canvas 内打开对应面板或创建起始节点。

不要直接进入 Dify。
不要进入作品库大重构。
不要进入社区首页。
不要进入模型广场。
不要重构 Provider。

## 8. 明确边界

- 没有新增后端 API。
- 没有新增数据库字段。
- 没有触发模型生成。
- 没有改 Cloudflare。
- 没有改 Nginx。
- 没有改 Basic Auth。
- 没有碰 Dify / New API / media-gateway。
