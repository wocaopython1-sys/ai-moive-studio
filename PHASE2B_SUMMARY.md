# AICON 阶段 2B 总结：多图生成 / 批量结果回写

## 1. 阶段目标

阶段 2B 的目标是实现图片生成数量 `n=2 / n=4` 时的最小闭环：后端接收数量参数，Provider 返回或聚合多张图片，AICON 保存每张图片，Canvas 回写多个 ImageNode，原 Prompt/Text 节点到多个 ImageNode 的 connection 能持久化，任务中心能展示多图结果，素材库能看到生成出的图片。

本阶段不是 UI 美化阶段，不接入 Dify，不做作品库重构，不改 Cloudflare / Nginx / Basic Auth / New API / media-gateway。

## 2. 已完成功能

1. 图片数量选项从 `1 / 2 / 3 / 4` 调整为 `1 / 2 / 4`。
2. 前端 Image Studio 的 `imageCount` 会进入生成 payload，并落到后端 `options.n`。
3. 后端 generation 记录会保存 `options.n`、`result_images`、`result_count`、`batch_id`、`created_item_ids`、`created_connection_ids`。
4. 图片生成结果支持多图解析，不再只取第一张。
5. n > 1 时会创建多个普通 ImageNode，不新增 batch node。
6. 额外 ImageNode 会按 2 列网格排列在首个 ImageNode 附近。
7. 如果首个 ImageNode 已有上游 Prompt/Text connection，额外 ImageNode 会继承同一个上游 TextNode connection。
8. 生成完成 SSE 会返回 `created_items` 和 `created_connections`。
9. 前端会合并后端返回的新 ImageNode 和 connection，避免随后保存 graph 时覆盖掉后端新建 connection。
10. 任务中心显示 `result_count` 和 `result_summary`，例如“生成 2 张图片”。

## 3. n 参数链路

前端：

- `frontend/src/utils/canvasGenerationPayload.js` 暴露图片数量选项 `1 / 2 / 4`。
- `CanvasImageStudio.vue` 继续使用该选项更新 `draft.imageCount`。
- `buildCanvasGenerationPayload` 将图片数量写入 `options.n`。

后端：

- `CanvasGenerationService._image_provider_options()` 已接收 `options.n`。
- `CanvasGenerationService.process_image_generation()` 将生成请求中的 `options.n` 记录到 generation 的 request / result payload。
- 任务中心从 request / result payload 中展示 `params.n`、`result_count` 和 `result_summary`。

## 4. Provider 多图返回兼容

后端多图解析兼容以下格式：

1. OpenAI-compatible `data: [{url: ...}, {url: ...}]`。
2. OpenAI-compatible `data: [{b64_json: ...}, {b64_json: ...}]`。
3. Provider 已包装后的 `list[str]`。
4. Provider 已包装后的 `list[dict]`。
5. 单个 string URL。
6. 单个 base64 / dict 图片对象。
7. JSON 字符串形式的列表或对象。

每张图片都会单独保存为媒体文件，并生成独立 object_key。

## 5. fan-out 方案说明

实际测试发现：`gpt-image-2` 经当前 New API / OpenAI-compatible image endpoint 直接传 `n>1` 会返回 400：`Unknown parameter: tools[0].n`。

因此阶段 2B 采用最小兼容方案：

1. 当 `requested_count > 1` 时，AICON 不再把 `n` 直接传给上游。
2. AICON fan-out 发起多次单图请求。
3. 将多次单图结果聚合为一个列表。
4. 后续统一走多图保存、批量 ImageNode 回写、connection 保存和任务中心展示逻辑。

这个方案不修改 New API，不修改 media-gateway，不新增 Provider 框架，也不新增数据库字段。

注意：fan-out 会让 n=2 消耗 2 次单图请求，n=4 消耗 4 次单图请求。

## 6. 多 ImageNode 回写说明

1. 第一张图继续回写当前 ImageNode。
2. 第二张及后续图片创建新的普通 ImageNode。
3. 新节点标题使用“图片结果 2 / 图片结果 3 ...”。
4. 新节点内容写入 `result_image_object_key`、`batch_id`、`batch_index`。
5. 生成记录写入 `result_images` 和 `created_item_ids`。
6. 前端收到 `created_items` 后合并到当前 Canvas 状态。

## 7. 多 connection 保存说明

1. 如果当前 ImageNode 已有上游 TextNode / Prompt connection，额外 ImageNode 会连接到同一个 TextNode。
2. 后端生成完成时记录 `created_connection_ids`。
3. SSE payload 返回 `created_connections`。
4. 前端 `mergeConnections` 合并新增 connection。
5. 这样可以避免前端随后保存 graph 时用旧 connection 列表覆盖后端新 connection。

## 8. 任务中心多图展示说明

任务中心新增结果摘要字段：

- `result_count`：成功生成并保存的图片数量。
- `result_summary`：例如“生成 2 张图片”。

任务中心继续显示 provider / model / params，其中 params 包含 `n`、`size`、`aspect_ratio`。

## 9. 素材库可见说明

阶段 1C 的素材库不是完整资产表系统，图片 / 视频素材来自 MinIO 文件对象和 files/list 聚合。

阶段 2B 生成的每张图片都会保存到 MinIO 用户目录，因此会被 `/api/v1/files/library` 聚合到素材库中。

## 10. 验证结果

已完成验证：

1. `n=2` 真实图片生成成功。
2. Provider 返回并聚合 2 张图。
3. 2 张图均保存到 MinIO。
4. Canvas 生成 2 个 ImageNode，状态均为 `completed`。
5. TextNode -> 2 个 ImageNode 均有 connection。
6. 2 张图 preview/download 均 200。
7. 任务中心显示 `params.n=2`、`result_count=2`、`result_summary=生成 2 张图片`。
8. graph API / DB 中存在 2 个 ImageNode + 2 条 connection。
9. MinIO 用户前缀下能找到 2 张新图，素材库聚合可见。
10. `/dashboard`、`/canvas`、`/library`、`/tasks`、`/health/` 均 200。
11. 视频 stream/download 200。
12. 后端日志无新增 500 / Traceback。

## 11. 未完成但不阻塞的问题

1. `n=4` 未真实测试，原因是避免额外消耗；功能路径复用 n=2 的 fan-out 聚合逻辑。
2. fan-out 是兼容方案，不是上游原生批量生成；n=4 会产生 4 次单图请求。
3. 如果用户直接在没有上游 TextNode connection 的 ImageNode 上执行 n>1，额外 ImageNode 不会凭空创建 TextNode connection；当前设计只继承已有上游 connection。
4. 上传 200 在阶段 2B 未重新真实上传验证，原因是本阶段未改上传链路，且本轮要求不扩展测试；阶段 1A-1F 基线已覆盖上传。

## 12. 回滚方式

当前阶段 2B 未 commit。可通过以下方式回滚工作区改动：

```bash
cd /opt/aicon-demo
git restore backend/src/api/schemas/canvas.py \
  backend/src/services/canvas.py \
  backend/src/services/provider/custom_provider.py \
  frontend/src/composables/useCanvasEditor.js \
  frontend/src/composables/useCanvasGeneration.js \
  frontend/src/utils/canvasGenerationPayload.js \
  frontend/src/views/TasksHistory.vue \
  frontend/src/views/canvas/CanvasEditor.vue
```

不要删除或提交 `.env.demo`、`PHASE0_BASIC_AUTH.txt`。

也可以使用 patch 目录中的 `phase2b-all.diff` 作为阶段 2B 改动快照。

## 13. 下一步建议

下一步只建议做阶段 2B 本地分支和 commit 固化：

1. 从当前工作区新建 `phase2b-multimage-batch-writeback` 分支。
2. 只 add 阶段 2B 相关 tracked 文件和 `PHASE2B_SUMMARY.md`。
3. 不 add `.env.demo`、`PHASE0_BASIC_AUTH.txt`、htpasswd、真实 key、临时测试文件。
4. commit message 建议：`phase2b: add mult-image batch writeback`。

## 14. 明确边界

- 阶段 2B 是多图生成 / 批量结果回写。
- `gpt-image-2` 上游不支持直接 n>1。
- 当前使用 fan-out 单图请求聚合多图结果。
- n=2 已真实验证成功。
- n=4 未测，避免额外消耗；功能路径理论复用 n=2。
- 当前没有新增后端 API。
- 当前没有新增数据库字段。
- 当前没有 commit。
- `.env.demo` 和 `PHASE0_BASIC_AUTH.txt` 不进入 patch / commit。