# AICON Phase 2L-A Summary

## 阶段目标

2L-A 聚焦素材库素材类型 / 来源可靠标签收口，只做最小前端实现。

本阶段不是素材库 final 回跳 Canvas，不是作品库重构，不是 UI 美化，不触发模型，不新增 API，不新增数据库字段。

## 阶段边界

当前素材库媒体记录没有可靠 final 字段，因此本阶段不展示“最终成片”。

`object_key` 只代表存储对象，不能可靠代表 Canvas 来源，也不能用于判断 final。普通图片 / 视频素材通常没有可靠 `canvas_id` / `canvas_item_id`。素材库媒体记录没有可靠 `generation_id`。

对无法可靠识别 final 的视频，本阶段继续显示为“视频素材”。不通过文件名、路径或 `object_key` 猜测“最终成片”。

## 完成内容

新增 `frontend/src/utils/assetLibraryLabels.js`，提供 `buildAssetLibraryLabels(asset)`。

该 helper 根据可靠字段输出：

- 图片素材
- 视频素材
- 文本素材
- 素材
- Canvas 来源
- 来源未标注

Canvas 来源只基于 `canvas_id` / `canvas_item_id` 存在时展示。不从 `object_key` 推断来源，不从 `object_key`、文件名或路径推断 final。

`frontend/src/views/AssetsLibrary.vue` 已接入标签展示：素材卡片和详情面板展示类型与来源标签。预览、下载、复制 URL、加入 Canvas 等入口保持存在，未改变上传 / 删除 / 回跳逻辑。

## 测试内容

新增 `frontend/src/tests/unit/utils/assetLibraryLabels.test.js`，覆盖：

- image -> 图片素材
- video -> 视频素材，且不输出 final 标签
- text -> 文本素材
- 有 `canvas_id` -> Canvas 来源
- 有 `canvas_item_id` -> Canvas 来源
- 只有 `object_key` -> 不推断 Canvas 来源
- 无可靠 final 字段 -> `canIdentifyFinal` 为 false
- 不输出“最终成片”
- 不从文件名或 `object_key` 猜 final

验证结果：

- `node --check src/utils/assetLibraryLabels.js` 通过
- Node 原生断言通过：`assetLibraryLabels native assertions passed`
- Vitest 未成功运行，原因是宿主机缺少 `vitest` 命令；本阶段已用 Node 原生断言覆盖 helper 关键行为

## 运行态验收

本阶段已 rebuild frontend，并只 restart frontend。backend / celery / db 未重启。

HTTP 验证结果：

- `/library` 200
- `/canvas` 200
- `/tasks` 200
- `/dashboard` 200
- `/health/` 200

Chrome DOM 验收命中：

- 图片素材
- 视频素材
- 文本素材
- Canvas 来源
- 来源未标注

Chrome DOM 未出现“最终成片”。页面中预览 / 下载 / 复制 URL / 加入 Canvas 入口仍存在。验收时未点击危险动作，未触发生成 / retry / refresh / resume / compose。

## 安全与范围

本阶段未触发模型，未新增 API，未新增 DB，未修改后端，未修改 Dockerfile，未修改 migration，未修改 Nginx / Cloudflare / New API / media-gateway。

未提交截图，未提交临时脚本。`.env.demo` 与 `PHASE0_BASIC_AUTH.txt` 仍为未跟踪文件，禁止提交，也未读取其内容。

敏感扫描范围覆盖本次待提交文件和 summary；未发现凭据类泄露、长编码内容、私钥片段、Basic Auth 内容、真实对象 key、硬编码用户标识或截图路径。

## 改动文件

- `frontend/src/views/AssetsLibrary.vue`
- `frontend/src/utils/assetLibraryLabels.js`
- `frontend/src/tests/unit/utils/assetLibraryLabels.test.js`
- `PHASE2L_A_SUMMARY.md`

## 未完成但不阻塞

- 不做素材库 final 回跳 Canvas
- 不做素材库 final 标识，因为当前没有可靠 final 字段
- 不做作品库重构
- 不做上传 / 删除逻辑变更
- 不新增后端反查接口
- 不做 Canvas workflow summary 改造
- 不做任务中心改造
- 2L-B / 2L-C 后续再单独规划

## 回滚方式

本次 commit 后可回退该 commit，恢复到 `523c19e phase2k: add final summary` 后的状态；也可使用 `/opt/backups/aicon-demo-20260704-phase2l-a-patches` 中 patch 反向回滚。

## 下一步建议

先做提交前闭合审计。审计通过后再 commit。后续再讨论 2L-B：素材库回跳 Canvas 的只读审计，不建议直接进入作品库重构。