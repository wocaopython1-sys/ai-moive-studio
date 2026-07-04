# AICON Phase 2K Round 2 P2-A Summary

## 1. 阶段目标

阶段 2K 第二轮 P2-A 目标是为 Canvas Workflow 摘要卡片增加只读链路文字摘要。

本轮定位：
- 2K 第二轮 P2-A：Canvas 链路文字摘要。
- 只做最小实现。
- 不是 workflow engine。
- 不是复杂流程图。
- 不是 UI 美化。
- 不是任务中心回跳。
- 不是素材库回跳。
- 不触发图片或视频模型。

## 2. 完成内容

本轮扩展 frontend/src/utils/canvasWorkflowSummary.js，在 buildCanvasWorkflowSummary(items, connections) 中新增只读链路摘要能力。

新增输出字段：
- workflowLinks
- reliableLinkCount
- hiddenLinkCount
- hasWorkflowLinks
- linkSummaryLabel
- linkWarnings

实现范围：
- 基于现有 canvas_items / canvas_connections 只读推导可靠链路。
- 支持 Prompt -> Image -> Video -> Final 等简版文字链路。
- 多分支最多展示 5 条，超出部分记录到 hiddenLinkCount 和 linkWarnings。
- 断裂 connection 会被忽略，不报错。
- cycle 有最大深度保护，不死循环。
- failed / processing 状态可进入链路摘要。
- 不展示 reused，不猜复用项。

Canvas 展示：
- frontend/src/views/canvas/CanvasEditor.vue 在现有 Workflow 摘要卡片内新增 链路摘要文本段。
- 不新增按钮。
- 不改变生成 / 合成 / retry / refresh / resume 行为。
- P1 已有计数和 warning 保持。

## 3. 测试内容

更新 frontend/src/tests/unit/utils/canvasWorkflowSummary.test.js，覆盖：
- 空数据安全返回。
- Prompt -> Image -> Video -> Final 可靠链路。
- 多分支链路展示与 hiddenLinkCount。
- failed / processing 链路状态。
- 断裂 connection 不生成假链路。
- cycle 深度保护。
- 不输出 reusedCount / reusedItems。
- 不从 reuse_compose 推断 reused。

验证结果：
- 宿主机缺 node_modules / vitest，npm run test:run -- src/tests/unit/utils/canvasWorkflowSummary.test.js 返回 vitest: not found，不阻塞本阶段。
- node --check src/utils/canvasWorkflowSummary.js 通过。
- Node 原生断言通过，覆盖空数据、可靠链路、failed/processing、断裂 connection、cycle、reused 不推断。

## 4. 运行态验收

构建与重启：
- frontend Docker build 成功。
- 只执行 frontend recreate：sudo docker compose -f docker-compose.demo.yml up -d --no-deps frontend。
- backend / celery / db 未重启。

入口检查：
- /dashboard 200。
- /canvas 200。
- /library 200。
- /tasks 200。
- /health/ 200。

Bundle marker 命中：
- Workflow 摘要
- 链路摘要
- 暂无可可靠推导链路
- 另有
- Prompt
- Image
- Video
- Final

浏览器页面验收：
- 验收页面：https://aicon.geminiproo.shop/canvas/60aaebb2-1eed-44e7-b718-e6015b2d4c2d
- DOM 显示 5 条 Prompt -> Image -> Video -> Final。
- DOM 显示 另有 4 条链路未展示。
- DOM 未出现 reused / 复用。
- Chrome 刷新后链路摘要仍存在。
- P1 摘要计数仍保持：图片、视频、已完成、处理中、失败、补齐、最终成片。
- 关键入口仍存在且未触发：批量生成图片、批量生成视频、合成视频、分镜成片、补齐、retry / refresh / resume。

## 5. 安全与范围

本阶段确认：
- 未触发模型。
- 未新增 API。
- 未新增 DB。
- 未修改后端。
- 未修改 Dockerfile。
- 未修改 migration。
- 未修改 Nginx / Cloudflare / New API / media-gateway。
- 未提交截图。
- 未提交临时脚本。
- .env.demo 仍未跟踪，禁止提交。
- PHASE0_BASIC_AUTH.txt 仍未跟踪，禁止提交。
- diff 扫描无 key/token/password/base64。
- diff 扫描无 UUID/object_key/user_id 硬编码。

## 6. 未完成但不阻塞

以下内容不属于 P2-A，后续单独规划：
- 不做任务中心回跳 Canvas。
- 不做素材库 final 回跳 Canvas。
- 不做 reused 可靠展示。
- 不做复杂链路树。
- 不做 workflow engine。
- 不做作品库重构。
- P2-B / P2-C / P2-D 后续再单独规划。

## 7. 改动文件

本阶段应提交文件：
- frontend/src/utils/canvasWorkflowSummary.js
- frontend/src/tests/unit/utils/canvasWorkflowSummary.test.js
- frontend/src/views/canvas/CanvasEditor.vue
- PHASE2K_ROUND2_P2A_SUMMARY.md

禁止提交文件：
- .env.demo
- PHASE0_BASIC_AUTH.txt
- 截图
- 临时脚本
- key/token/base64/password
- Dockerfile
- migration
- 后端文件

## 8. 回滚方式

推荐回滚方式：
- 如果本阶段已 commit，回退本次 commit 可恢复到 bd950b6 phase2k: add canvas workflow summary。
- 或使用 /opt/backups/aicon-demo-20260704-phase2k-round2-p2a-patches 中的 patch 反向回滚。

## 9. 下一步建议

下一步建议：
- 先做提交前闭合审计。
- 审计通过后再 commit。
- 后续再讨论 P2-B：任务中心最小回跳 Canvas。
- P2-C 素材库 final 回跳暂缓。
- P2-D reused 继续不展示。
