# AICON Phase 2C Summary

## 1. 阶段目标

阶段 2C 是“候选图片继续图生视频 / 批量结果选择工作流”。目标是在阶段 2B 多图生成已经能回写多个 ImageNode 的基础上，让用户从候选 ImageNode 中选择一张图片，继续发起图生视频，并形成完整闭环：ImageNode -> VideoNode、任务中心可追踪、素材库可见、保存刷新可恢复。

本阶段不是批量视频生成，不做多张候选图同时生成视频；当前只做“选一张候选图继续生成视频”。

## 2. 候选 ImageNode 操作入口

ImageNode 操作区已提供“用这张图生成视频”入口。该入口会基于当前选中的 ImageNode 创建图生视频节点，并把当前图片作为 reference image 绑定到后续视频生成 payload。

## 3. 第 1 / 第 2 张候选图 payload 绑定结果

阶段 2B 的 n=2 多图结果中，第 1 张候选图和第 2 张候选图均已验证：选中不同 ImageNode 时，图生视频 payload 会指向对应的图片 item，不会固定到错误候选图。

## 4. 参考图 URL 外部可访问性验证

参考图 URL 已验证可被外部访问：不带 Cookie / 不带 Basic Auth 请求返回 200，Content-Type 为 image/png。该结果说明 BigModel 可以直接拉取参考图 URL，不需要由 AICON 将图片下载并转成 base64 后再提交。

## 5. BigModel 图生视频 URL 透传说明

之前真实图生视频失败的直接原因是 BigModel create 请求写入大量 base64 payload 导致 WriteTimeout。阶段 2C 已做最小修复：当参考图是公网 http/https URL，且 provider 请求偏好 public URL 时，后端直接透传 URL，不再转成巨大 base64，从而规避请求体过大导致的 WriteTimeout。

## 6. 真实图生视频 completed 验收结果

真实图生视频已 completed：

- model: cogvideox-3
- provider: custom
- provider task id: 202607010933584fafe62b0e4c4be4
- duration: 5
- aspect_ratio: 16:9
- reference_images: 1
- VideoNode id: 1a8335c5-2c97-4e0c-a275-17ae8be2c31e
- video object_key: uploads/e25665b8-8b5f-441a-8f3c-ac0df7884653/20260701/932fde23-4963-4a7a-8172-c56475cd367d.mp4

新视频 stream / download / preview 均返回 200。

## 7. VideoNode 回写结果

图生视频完成后，Canvas 已回写 VideoNode，状态为 completed，视频 object_key 已保存，可用于后续 stream、download、preview 和素材库展示。

## 8. ImageNode -> VideoNode connection 保存结果

ImageNode -> VideoNode connection 已保存：

- source ImageNode: 64a42c72-0e4d-45dc-97d9-c19144dc5ef8
- target VideoNode: 1a8335c5-2c97-4e0c-a275-17ae8be2c31e

保存刷新后 connection 仍存在。

## 9. 任务中心 reference_images 展示结果

任务中心已显示本次图生视频任务参数：

- model: cogvideox-3
- provider: custom
- duration: 5
- aspect_ratio: 16:9
- reference_images: 1

## 10. 素材库视频可见结果

素材库能看到新生成的 mp4 文件。MinIO 文件对象存在，大小约 596328 bytes。

## 11. 保存刷新恢复结果

保存刷新恢复已验证：VideoNode 和 ImageNode -> VideoNode connection 均保持存在，Canvas 图结构没有丢失。

## 12. 改动文件清单

- backend/src/services/canvas.py
  - BigModel 图生视频参考图在 prefer_public_urls=true 且为 http/https URL 时直接透传，避免公网参考图被下载并转成大 base64。
- frontend/src/components/canvas/CanvasImageStudio.vue
  - ImageNode 操作按钮文案改为“用这张图生成视频”，并补充 title / aria-label。
- frontend/src/views/canvas/CanvasEditor.vue
  - 从 ImageNode 创建图生视频节点时写入默认可编辑视频 prompt，并保留 image mention token，保证后续 payload 能绑定当前候选图。

## 13. 验证结果

- 候选 ImageNode 操作入口可见。
- 第 1 / 第 2 张候选图 payload 绑定正确。
- 参考图 URL 外部可访问，不需要 Cookie / Basic Auth。
- 真实图生视频 completed。
- VideoNode 回写完成。
- ImageNode -> VideoNode connection 保存完成。
- 新视频 stream / download / preview 均 200。
- 任务中心显示 reference_images=1。
- 素材库可见新视频。
- 保存刷新恢复后 VideoNode 和 connection 仍存在。
- 阶段 2B 多图 ImageNode 仍存在。

## 14. 未完成但不阻塞的问题

- 本阶段未做批量视频生成，仅支持从候选图中选择一张继续图生视频。
- 未对 n=4 的全部候选图逐一真实图生视频，以避免额外模型消耗；当前逻辑复用单张候选图路径。
- 未做复杂 reference image 压缩系统；当未来遇到非公网或超大参考图时，需要单独设计压缩 / 临时公开 URL 策略。

这些问题不阻塞阶段 2C 固化。

## 15. 回滚方式

如需回滚阶段 2C，可在未 commit 状态下执行：

```bash
git restore backend/src/services/canvas.py frontend/src/components/canvas/CanvasImageStudio.vue frontend/src/views/canvas/CanvasEditor.vue
rm -f PHASE2C_SUMMARY.md
```

如果后续已 commit，可使用对应 commit 的 revert 操作回滚代码变更。不要提交 .env.demo 或 PHASE0_BASIC_AUTH.txt。

## 16. 下一步建议

下一步只建议在用户确认后执行阶段 2C 本地 commit 固化。固化后再进入下一阶段。当前不要接 Dify，不要做作品库重构，不要做 UI 美化，不要改 New API / media-gateway。

## 17. 固化状态说明

- 本阶段没有新增后端 API。
- 本阶段没有新增数据库字段。
- 当前没有 commit。
- .env.demo 和 PHASE0_BASIC_AUTH.txt 不进入 patch / commit。
