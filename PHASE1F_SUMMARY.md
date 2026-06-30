# AICON 阶段 1F 总结：真实使用体验打磨 / 内测可用性修补

## 阶段目标

阶段 1F 是真实使用体验打磨，不是新功能阶段。本阶段从内测用户视角检查 Canvas 创作入口和节点操作路径，只修影响使用体验的 P1 问题，不进入 Dify、作品库大重构、社区首页、模型广场或安全专项。

## 已修复体验问题

1. 主生成按钮只有箭头图标，用户不知道这是生成入口。
2. 文本节点下游按钮只写“图片 / 视频”，容易误解为直接生成。
3. 左侧 Canvas 工具栏 icon-only，素材入口和任务入口不清楚。
4. 关系面板压住节点操作区，容易点错。
5. 720 高度下 Studio 操作面板会跑出视口，按钮不够稳定可见。
6. 文本创建下游 ImageNode 后只选中不聚焦，新节点可能靠右或靠边。

## 改动文件清单

| 文件 | 改动内容 |
|---|---|
| `frontend/src/components/canvas/CanvasTextStudio.vue` | 文本节点下游按钮改为“创建图片节点 / 创建视频节点”；文本生成按钮增加文字、title、aria-label；调整按钮宽度和间距。 |
| `frontend/src/components/canvas/CanvasImageStudio.vue` | 图片生成按钮增加“生成图片 / 生成中”文案、title、aria-label；调整按钮间距和最小宽度。 |
| `frontend/src/components/canvas/CanvasVideoStudio.vue` | 视频生成按钮增加“生成视频 / 生成中”文案、title、aria-label；调整按钮间距和最小宽度。 |
| `frontend/src/components/canvas/CanvasWorkbenchLayout.vue` | 左侧工具栏按钮补充 title / aria-label，包括新建节点、文本、图片、视频、最近素材、任务中心。 |
| `frontend/src/views/canvas/CanvasEditor.vue` | Studio 面板定位纳入真实 viewport 高度；关系面板移动到左上侧并缩小；创建下游节点后复用 `focusCanvasItem` 聚焦新节点。 |

## 验证结果

1. `docker compose -f docker-compose.demo.yml build frontend` 通过。
2. frontend 已重建并 healthy。
3. `/dashboard` 200。
4. `/library` 200。
5. `/tasks` 200。
6. `/health/` 200。
7. `/api/v1/files/list` 200。
8. `/api/v1/files/library` 200。
9. `/api/v1/tasks/history` 200。
10. graph API 200。
11. 图片 preview/download 200。
12. 视频 stream/download 200。
13. PNG 上传 200。
14. MP4 上传 200。
15. Canvas 页面不白屏。
16. 生成按钮文字可见。
17. 左侧工具栏 title / aria-label 存在。
18. 关系面板不再遮挡主要操作区。
19. 文本创建下游 ImageNode 后能聚焦新节点。
20. 后端最近日志无新增 500 / Traceback。

## 未完成但不阻塞的问题

1. 图片/视频 Studio 面板在 720 高度下虽然按钮已可见，但整体仍偏紧，后续可以做更系统的响应式布局微调。
2. 本阶段没有重跑文本/图片/视频模型生成，因为阶段目标是体验修补和轻量回归，不消耗模型。

## 明确边界

- 未触发模型生成。
- 未改后端 API。
- 未新增数据库字段。
- 未改 Cloudflare / Nginx / Basic Auth / Dify / New API / media-gateway。
- 未进入作品库大重构、社区首页或模型广场。
- Basic Auth URL 中带 `user:pass` 导致的 Vue Router `replaceState` 报错不是 AICON 功能问题；正常通过浏览器 Basic Auth 后使用干净 URL 即可。

## 回滚方式

本阶段只修改 5 个前端文件。可通过以下方式回滚：

1. 若已创建 commit：`git revert <phase1f_commit_id>`。
2. 若只应用 patch：在 `/opt/backups/aicon-demo-20260630-phase1f-patches` 中使用 `phase1f-all.diff` 反向应用，或从 Git 恢复上述 5 个文件。
3. 回滚后重新构建前端并启动：`sudo docker compose -f docker-compose.demo.yml build frontend && sudo docker compose -f docker-compose.demo.yml up -d frontend`。

## 下一阶段建议

下一阶段只建议进入阶段 1G：继续做内测反馈闭环和响应式细节整理。不要直接进入 Dify、完整作品库、社区首页或模型广场。
