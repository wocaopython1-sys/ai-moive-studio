# AICON Phase 2E Summary

## 1. 阶段目标

阶段 2E 是“分镜 / Prompt 批量生成图片”。目标是在 Canvas 中从多个 Prompt / 分镜文本节点出发，选择多个 Prompt 节点，批量生成对应图片，并让每个 TextNode 与生成的 ImageNode 建立连接，任务中心和素材库都能看到结果，保存刷新后可恢复。

本阶段不是重构 Canvas 多选系统，不是 UI 美化阶段，不是 Dify 接入，不是作品库重构，也不是 Provider 框架重构。

## 2. 已完成功能

- 增加轻量“批量生成图片”入口。
- 增加轻量批量面板，用于选择当前 Canvas 中的 Prompt / 文本节点。
- 支持选择多个 Prompt 节点后逐项生成图片。
- 每个 Prompt 节点生成对应 ImageNode。
- 每个 TextNode -> ImageNode connection 已保存。
- 批量任务会写入 batch 元信息。
- 任务中心展示 batch 信息。
- 单项失败不会阻断后续项。
- 失败项可通过阶段 2D retry 能力补齐。

## 3. Prompt 节点选择方式

本阶段采用轻量批量面板选择 Prompt 节点，不重构 Canvas 多选系统。

面板会列出当前 Canvas 中的 text 类型节点，用户可以勾选要参与批量生成的 Prompt。默认会优先使用当前选中的文本节点；若没有当前选中文本节点，则默认取前 2 个 Prompt 节点，避免误触发大批量消耗。

## 4. 批量生成入口说明

Canvas 中存在文本节点时，会显示“批量生成图片”入口。点击后打开批量面板，可选择：

- Prompt 节点
- 图片模型
- 图片尺寸
- 图片数量

本阶段默认验证模型为 gpt-image-2，尺寸为 1024x1024，数量 n=1。

## 5. 前端循环还是后端批量接口

本阶段采用前端循环调用现有单 Prompt 图片生成接口的方案。

没有新增后端批量接口。每个 Prompt 节点对应一次现有图片生成请求，复用已有生成、任务记录、媒体保存、Canvas 回写和 retry 能力。

## 6. 批量参数说明

每次单项生成都会带入原有图片参数和 batch 参数：

- model: gpt-image-2
- image_size: 1024x1024
- aspect_ratio: 1:1
- n: 1
- source_item_id: 来源 TextNode id

同时修复了批量图片生成时 API Key 选择问题：图片生成节点现在优先使用 image 类型 Key，而不是错误沿用当前用户第一个 Key 或 video Key。

## 7. batch_id / batch_index / batch_total 说明

批量生成请求会在 options 中写入：

- batch_id: 同一次批量操作的前端批次标识
- batch_index: 当前 Prompt 在批量中的序号
- batch_total: 本次批量总数
- batch_label: 分镜图片
- source_item_id: 来源 Prompt / TextNode id

任务中心会合并 request_payload.options 与 params，并展示批量标识和批次信息。

## 8. 2 个 Prompt 批量生成结果

真实测试 Canvas:

- canvas_id: 60aaebb2-1eed-44e7-b718-e6015b2d4c2d
- batch_id: 699a76bf-61c9-4e00-b884-9cc7bac94b06

最终验收结果：

- Prompt A -> ImageNode: completed
- Prompt B -> ImageNode: completed
- 两个 ImageNode 均有 object_key
- 两张图片 preview/download 均 200
- 两条 TextNode -> ImageNode connection 均存在

## 9. 第一次 1 completed + 1 failed 的原因

第一次真实批量结果为 1 completed + 1 failed。

失败项错误为上游返回：

- Error code: 500
- type: bad_response_body
- message: invalid character 'e' looking for beginning of value

用户确认近期中转不稳定。该失败项来自上游 500 bad_response_body，不是 AICON 批量编排错误。相同 Prompt、model、options 通过 retry 后成功，进一步说明 Canvas 批量参数和编排链路可用。

## 10. retry 补齐 failed 项验证结果

使用阶段 2D 已有 retry 能力，仅对 failed 项执行一次 retry。

- original generation id: 334d775c-f0be-44f5-ab94-0ec695dae492
- retry generation id: a3f8e606-a133-4943-bc93-0c30208724c3
- retry result: completed
- retry_of 已保留
- 原 ImageNode 已更新为 completed
- object_key 已写入

已通过阶段 2D retry 成功补齐为 2 个 Prompt -> 2 张 completed 图片。

## 11. ImageNode 回写结果

最终 graph 中有 2 个 completed ImageNode：

- dae8f28b-2549-4993-8461-d005eb5454f8
- d1794b24-e273-4eac-9695-f29f054ef750

两者均已写入 result_image_object_key / object_key，媒体接口可访问。

## 12. TextNode -> ImageNode connection 保存结果

最终 graph 中有 2 条 connection：

- b9042edb-2dd9-4de5-88de-896f8e846f04 -> dae8f28b-2549-4993-8461-d005eb5454f8
- 8f6012b6-bda8-4ac8-a551-6f1ab0d9c3ea -> d1794b24-e273-4eac-9695-f29f054ef750

保存刷新后仍存在。

## 13. 任务中心 batch 展示结果

任务中心能看到：

- batch_label: 分镜图片
- batch_index: 1 / 2
- batch_index: 2 / 2
- batch_total: 2
- retry 后 completed 任务
- retry_of 原失败任务 id
- model: gpt-image-2
- params: image_size / aspect_ratio / n

原 failed 历史保留，不删除历史。

## 14. 素材库图片可见结果

两张 completed 图片均已保存为媒体对象，并可在素材库中看到。

两张图片的 preview/download 均返回 200。

## 15. 保存刷新恢复结果

浏览器刷新 Canvas 后，两个图片节点均显示“图片已生成”。

Graph API 能看到 2 个 completed ImageNode 和 2 条 TextNode -> ImageNode connection。

## 16. 单项失败隔离说明

批量执行中，单项失败不会阻断后续项。

本轮真实测试中，第 1 个 Prompt 初次生成失败后，第 2 个 Prompt 继续执行并成功 completed。随后 failed 项通过 retry 补齐。

## 17. 改动文件清单

- frontend/src/views/canvas/CanvasEditor.vue
- frontend/src/views/TasksHistory.vue
- PHASE2E_SUMMARY.md

## 18. 验证结果

已验证：

- /dashboard 200
- /canvas 200
- /library 200
- /tasks 200
- /health/ 200
- /api/v1/tasks/history 200
- /api/v1/files/library 200
- graph API 200
- 两张图片 preview/download 200
- 素材库能看到 retry 成功图片
- 视频 stream/download/preview 200
- PNG 上传 200
- MP4 上传 200
- 浏览器刷新后 Canvas 节点和 connection 恢复
- Browser console 无阻塞错误
- 后端最近日志无新增 AICON 代码级 500 / Traceback

## 19. 未完成但不阻塞的问题

- 当前 Prompt 选择采用轻量批量面板，不是 Canvas 原生多选系统重构。
- API Key 与模型能力的前端匹配仍是轻量启发式，当前 image_gpt 配置可用；后续更稳的方式是后端返回 API Key 支持的模型能力，用显式映射代替名称判断。
- 原 failed 任务历史仍存在，这是阶段 2D 历史保留策略，非阻塞。

## 20. 回滚方式

如需回滚阶段 2E 代码改动，可在对应分支上执行：

```bash
git restore frontend/src/views/canvas/CanvasEditor.vue frontend/src/views/TasksHistory.vue
rm -f PHASE2E_SUMMARY.md
```

如果已 commit，则使用对应 commit 的 revert，而不是直接 reset 共享分支。

## 21. 下一步建议

下一步只建议生成阶段 2E 本地 commit 固化，commit 前继续确认：

- .env.demo 不提交
- PHASE0_BASIC_AUTH.txt 不提交
- patch 目录仅作为备份，不进入 commit
- 不 push GitHub

## 明确声明

- 阶段 2E 是“分镜 / Prompt 批量生成图片”。
- 本阶段不是重构 Canvas 多选系统。
- 本阶段采用轻量批量面板选择 Prompt 节点。
- 本阶段没有新增后端 API。
- 本阶段没有新增数据库字段。
- 批量执行中单项失败不会阻断后续项。
- 本轮失败项来自上游 500 bad_response_body，不是 AICON 批量编排错误。
- 已通过阶段 2D retry 成功补齐为 2 个 Prompt -> 2 张 completed 图片。
- 当前没有 commit。
- .env.demo 和 PHASE0_BASIC_AUTH.txt 不进入 patch / commit。
