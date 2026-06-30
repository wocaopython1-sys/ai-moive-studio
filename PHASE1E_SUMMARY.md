# 阶段 1E 总结：创作流程模式入口

## 1. 阶段目标

阶段 1E 的目标是把阶段 1D 的创作大厅快捷入口接到真实 Canvas 创作流程，让用户从 Dashboard 进入不同创作模式时能看到明确的起始状态，而不是只进入空白 Canvas。

本阶段是“创作流程模式入口”，不是新的生成系统，不是 Provider 重构，也不是完整工作流引擎。

## 2. 已完成功能

- 空白 Canvas：Dashboard 新建后保持空白，不创建 starter node。
- 图片创作入口：`mode=image` 创建“图片 Prompt”文本节点，自动选中并聚焦。
- 视频创作入口：`mode=video` 创建“视频 Prompt”文本节点，自动选中并聚焦。
- 图生视频入口：`mode=i2v` 自动打开最近素材 / 上传面板，可加入图片，图片节点选中后 Inspector 保留生成视频入口。
- Prompt / 分镜助手入口：`mode=storyboard` 创建“故事 / 分镜输入”文本节点，右侧助手可见。
- 上传素材入口：`mode=upload` 自动打开最近素材 / 上传面板，支持 PNG / MP4 上传。
- 防重复初始化：初始化完成后清理 `mode` / `force`，刷新不重复创建 starter node。
- 任务中心回归：`item_id` 跳转优先级高于 mode 初始化，不干扰任务中心聚焦节点。

## 3. 改动文件清单

| 文件 | 改动内容 |
|---|---|
| `frontend/src/views/Dashboard.vue` | Prompt / 分镜入口从 `assistant` 改为 `storyboard`；上传素材快捷卡改为创建 Canvas 并跳转 `mode=upload`；补充 `storyboard` / `upload` 标题映射。 |
| `frontend/src/views/canvas/CanvasEditor.vue` | 读取 `mode` query；为 image/video/storyboard 创建 starter 文本节点；为 i2v/upload 打开素材面板；初始化后清理 `mode` / `force`；保护 `item_id` 跳转；素材面板增加最小上传按钮并复用现有 `/files/upload`。 |

## 4. 验证结果

- `/dashboard` 200。
- `/library` 200。
- `/tasks` 200。
- `/health/` 200。
- 空白 Canvas 新建后 0 节点，刷新仍 0。
- 图片创作入口创建“图片 Prompt”，刷新后不重复。
- 视频创作入口创建“视频 Prompt”，刷新后不重复。
- 图生视频入口打开素材面板，可加入图片，图片节点选中，Inspector 有生成视频入口。
- Prompt / 分镜助手入口创建“故事 / 分镜输入”，右侧助手可见，刷新后不重复。
- 上传素材入口打开素材面板，PNG 上传 200，MP4 上传 200。
- 任务中心 `item_id` 跳转仍能聚焦节点。
- 图片 preview/download 200。
- 视频 stream/download 200。
- Canvas 页面不白屏，浏览器 console 无阻塞错误。
- 前端构建 `sudo docker compose -f docker-compose.demo.yml build frontend` 通过。

## 5. 未完成但不阻塞的问题

- 当前 mode 入口只做起始引导，不自动触发文本、图片或视频模型生成。
- 当前不是完整工作流引擎，不做多步骤自动编排。
- 当前不是社区首页、模型广场或完整作品库系统。

## 6. 已知小问题

- `mode` 初始化后 URL 会被清理，这是防止刷新重复创建节点的设计，不是入口丢失。
- `mode=image/video/i2v/storyboard/upload` 只是入口引导参数，不代表生成任务状态。
- 如果用户在已有节点的 Canvas 上手动带 `mode` 进入，默认不会创建 starter node；需要测试强制入口时可使用 `force=1`。

## 7. 回滚方式

只回滚阶段 1E 文件：

```bash
cd /opt/aicon-demo
git revert <phase1e_commit_id>
sudo docker compose -f docker-compose.demo.yml build frontend
sudo docker compose -f docker-compose.demo.yml up -d frontend
```

如果尚未 commit，也可以使用 patch 反向回滚：

```bash
cd /opt/aicon-demo
git apply -R /opt/backups/aicon-demo-20260630-phase1e-patches/phase1e-all.diff
sudo docker compose -f docker-compose.demo.yml build frontend
sudo docker compose -f docker-compose.demo.yml up -d frontend
```

## 8. 下一阶段建议

下一阶段只建议进入“创作模式内的细化体验”，例如不同模式下默认打开更贴近任务的面板、提示和示例模板。不要在下一阶段直接扩大到 Dify、社区首页、模型广场或完整作品库重构。

## 9. 不要误判的点

- 阶段 1E 是“创作流程模式入口”，不是新生成系统。
- `mode=image/video/i2v/storyboard/upload` 只是入口引导。
- 初始化后清理 `mode` 是防重复创建节点的设计。
- 空白 Canvas 不创建 starter node。
- `item_id` 跳转优先级高于 mode 初始化，任务中心跳转不能被破坏。
- 没有新增后端 API。
- 没有新增数据库字段。
- 没有触发模型生成。
