# AICON Phase 2J Summary

## 1. 阶段目标

阶段 2J 是 **fill_missing 缺失项补齐单独验收**。目标是在阶段 2I “前端轻量编排 + 复用已有结果 + 异步合成”的基础上，单独验证并修通缺失图片 / 缺失视频补齐链路，最终完成从 Prompt 到最终 MP4 的最小闭环。

本阶段不是全自动 workflow engine，不做复杂时间线，不做字幕、转场、配乐，不接 Dify，不做作品库重构。

## 2. 阶段定位说明

本阶段聚焦 2I 遗留的 `fill_missing` 路径：

- 缺图时只补齐缺失 Prompt 的图片。
- 缺视频时只补齐缺失 ImageNode 的视频。
- 已有结果不重复生成。
- 补齐后复用阶段 2H async compose 生成最终 MP4。
- 使用 CanvasItem / CanvasConnection / CanvasItemGeneration 现有结构，不新增数据库字段。

## 3. fill_missing 缺失项补齐链路说明

验证链路：

- Prompt A -> Image A -> Video A -> Final Video：完成。
- Prompt C -> Image C -> Video C -> Final Video：完成。

Prompt C 缺失项补齐路径：

1. Prompt C 缺图补齐生成 ImageNode。
2. Prompt C ImageNode 使用 BigModel `cogvideox-3` 图生视频补齐。
3. Prompt A completed VideoNode + Prompt C completed VideoNode 调用 2H async compose。
4. 生成最终 Final VideoNode 和最终 MP4。

## 4. 缺图补齐结果

Prompt C 缺图补齐完成：

- Prompt C id：`2d7a4363-eafc-4c9d-b266-a9bdf4db6612`
- ImageNode id：`84846ab5-8a19-47b5-bebd-ca6f369a1fc3`
- 图片 object_key：`uploads/e25665b8-8b5f-441a-8f3c-ac0df7884653/20260702/bc762cdd-05be-4f40-945f-d0c867a3dd32.png`
- 图片状态：`completed`
- 图片格式：PNG
- 图片大小：1,680,474 bytes，未超过 5MB

## 5. 视频补齐失败排查过程

旧 public URL 视频任务失败：

- generation id：`2b906f62-b767-481f-895b-44bf1241f368`
- VideoNode id：`eec0f9e1-a1a6-43f0-b5ae-0ba339fd6b99`
- provider task id：`20260702192136d3210555d63749e2`
- BigModel async-result：HTTP 400
- error code：`1210`
- task_status：`FAIL`
- message：`API 调用参数有误，请检查文档`

判断：

- 不是余额不足：没有 429、余额不足、资源包相关错误。
- 不是真实鉴权失败：使用后端解密路径查询后拿到 BigModel 业务错误。
- 不是 AICON 后端 500。
- 更像 BigModel 图生视频 create payload 的参考图传输方式不符合当前规则，public URL 方式可能被上游判定为不可用或参数错误。

中间 data URL base64 任务也未完成：

- generation id：`1ff58831-9b2b-4775-8bc8-761a0719e89d`
- VideoNode id：`ac000d9c-fcce-440e-8688-3a643dc8ac41`
- provider_task_id：空
- create 阶段约 62 秒失败，无有效上游 body

## 6. BigModel public URL 失败原因判断

阶段 2J 没有把旧 public URL 任务判断为余额问题，也没有判断为后端 500。证据显示旧任务已成功创建 provider_task_id，但 BigModel 状态查询返回 `task_status=FAIL` 和 `code=1210`。

结合 BigModel 参数规则和历史成功任务对比，最可疑点是参考图 `image_url` 使用公网 URL 时，上游不能按预期读取或校验该图片。阶段 2J 因此改为优先从 object_key 读取图片内容，并以 raw base64 形式提交给 BigModel。

## 7. raw base64 修补说明

后端修补点：

- BigModel 图生视频参考图优先使用 `reference_image_object_keys`。
- 对 `uploads/...` object_key 下载图片内容。
- 对 BigModel 分支构造 raw base64，不再优先提交 public URL。
- 支持从 data URL 中剥离 raw base64。
- 校验参考图 mime：`image/png`、`image/jpeg`、`image/jpg`。
- 校验参考图大小不超过 5MB。
- 不向 BigModel payload 透传 workflow / batch 等业务元数据。

BigModel 最终 payload 仍保持最小字段：

- `model`
- `prompt`
- `size`
- `duration`
- `image_url`

## 8. BigModel create timeout 说明

BigModel video create timeout 已从默认 60s 调整为 180s：

- `BIGMODEL_VIDEO_CREATE_TIMEOUT_SECONDS = 180.0`
- connect timeout：20s
- status query timeout 仍保持 60s

本次 raw base64 create 实测约 8.5s 返回 provider task id。

## 9. 错误日志摘要增强说明

BigModel create 日志增加脱敏摘要：

- endpoint
- model
- timeout seconds
- connect timeout seconds
- image transport
- image encoding
- image mime
- image size bytes
- base64 length
- payload json bytes
- response status code
- response body 摘要
- exception type / message 摘要

日志不打印完整 API key，不打印完整 base64。

## 10. raw base64 retry 结果

Prompt C 单项 raw base64 图生视频 retry 完成：

- generation id：`1224dada-d194-4118-b73e-fe2192331264`
- provider task id：`202607022209373eb9f2558ec44574`
- VideoNode id：`4b4e908e-ada6-46fb-ba70-e4a06f001873`
- create response：`PROCESSING`
- status refresh：`SUCCESS`
- resume 拉回：成功
- result object_key：`uploads/e25665b8-8b5f-441a-8f3c-ac0df7884653/20260702/13e4bcd5-4ef2-4153-b78c-dd76b5457819.mp4`
- 视频 preview / stream / download：均 200
- Content-Type：`video/mp4`
- ImageNode -> VideoNode connection：`8cd6c2f8-6275-4aec-a54e-a92240ec0519`

本次补齐没有重新生成图片，没有二次视频 retry。

## 11. status refresh / resume 结果

对 generation `1224dada-d194-4118-b73e-fe2192331264` 只执行 1 次 status refresh：

- BigModel 返回 `task_status=SUCCESS`
- AICON 归一化状态为 `completed`
- 随后执行 1 次 resume 拉回视频
- VideoNode 更新为 `completed`
- object_key 写入成功

## 12. async compose 结果

使用阶段 2H async compose 合成 Prompt A 视频 + Prompt C 视频：

- Prompt A VideoNode：`4e977938-9971-4f4c-9645-fdcce7c987f9`
- Prompt C VideoNode：`4b4e908e-ada6-46fb-ba70-e4a06f001873`
- compose generation id：`9fee7e95-616c-4d5c-8f50-aa6216f1fcac`
- Celery task id：`4d0d237d-9a94-4713-b445-a4b512d4cfc7`
- final VideoNode id：`bbdd4c41-dfbf-4de7-96df-e80cdbe81985`
- Celery `canvas.compose_video` 约 2.97s completed

本阶段只调用 1 次 async compose，没有触发模型生成。

## 13. final MP4 结果

最终 MP4：

- object_key：`uploads/e25665b8-8b5f-441a-8f3c-ac0df7884653/20260702/a63521cb-5b87-4fd2-ae1a-573fa8a7c05d.mp4`
- size：约 4.21 MB
- preview：200
- stream：200
- download：200
- Content-Type：`video/mp4`

## 14. connection 链路结果

Final VideoNode 持久存在两条 source VideoNode -> Final VideoNode connection：

- Prompt A VideoNode -> Final VideoNode
- Prompt C VideoNode -> Final VideoNode

完整链路验证：

- Prompt A `b9042edb-2dd9-4de5-88de-896f8e846f04` -> Image A `dae8f28b-2549-4993-8461-d005eb5454f8` -> Video A `4e977938-9971-4f4c-9645-fdcce7c987f9` -> Final Video `bbdd4c41-dfbf-4de7-96df-e80cdbe81985`
- Prompt C `2d7a4363-eafc-4c9d-b266-a9bdf4db6612` -> Image C `84846ab5-8a19-47b5-bebd-ca6f369a1fc3` -> Video C `4b4e908e-ada6-46fb-ba70-e4a06f001873` -> Final Video `bbdd4c41-dfbf-4de7-96df-e80cdbe81985`

## 15. 任务中心展示结果

任务中心 compose 任务可见：

- `workflow_id`
- `workflow_stage=compose`
- `workflow_mode=fill_missing`
- `workflow_action=fill_missing_compose`
- `fill_missing=true`
- `mode=concat`
- `clip_count=2`
- `completed`

重要限制：

- `reference_image_transport` / `reference_image_encoding` 已进入 request options。
- 当前任务中心 params 摘要未展开显示 `reference_image_transport` / `reference_image_encoding`。
- 当前只显示 `reference_images=1`。
- 该展示限制不阻塞 2J 验收。
- 后续如要完整展示，需要单独小改任务中心 params 展示。

## 16. 素材库可见结果

素材库聚合逻辑能看到最终 MP4：

- object_key：`uploads/e25665b8-8b5f-441a-8f3c-ac0df7884653/20260702/a63521cb-5b87-4fd2-ae1a-573fa8a7c05d.mp4`
- media_type：`video`
- mime_type：`video/mp4`
- size：约 4.21 MB

## 17. 保存刷新恢复结果

DB / graph 复核：

- final VideoNode 状态：`completed`
- final VideoNode object_key 已写入
- 两条 VideoNode -> Final connection 持久存在
- graph 查询能看到 Prompt A / Prompt C 两条完整链路

## 18. 阶段 1A-2I 回归结果

轻量回归通过：

- `/dashboard` 200
- `/canvas` 200
- `/library` 200
- `/tasks` 200
- `/health/` 200
- final MP4 preview / stream / download 均 200
- 2D retry / refresh / resume 按钮仍存在
- 2E 批量 Prompt 图片入口仍存在
- 2F 批量图生视频入口仍存在
- 2H async compose 仍存在
- 2I 分镜成片入口仍存在

日志说明：

- compose 后近 6 分钟后端 / Celery 日志无新增业务链路 Traceback / ERROR / Exception。
- 本轮早些时候出现过一次只读临时脚本字段误用 Traceback，原因是临时检查脚本错误读取 `CanvasItem.user_id`。该错误未改数据、未触发模型、非业务接口，不属于 AICON 业务链路错误，已如实记录。

## 19. 改动文件清单

Tracked 改动：

- `backend/src/services/canvas.py`
- `backend/src/services/provider/vector_engine_provider.py`
- `frontend/src/views/TasksHistory.vue`
- `frontend/src/views/canvas/CanvasEditor.vue`

新增文档：

- `PHASE2J_SUMMARY.md`

未跟踪且禁止提交：

- `.env.demo`
- `PHASE0_BASIC_AUTH.txt`

## 20. 未完成但不阻塞的问题

1. 任务中心 params 摘要未展开显示 `reference_image_transport` / `reference_image_encoding`，只显示 `reference_images=1`。
2. 该展示限制不阻塞 2J 验收；如果后续需要完整展示，需要单独小改任务中心 params 展示。
3. 阶段 2J 不是全自动 workflow engine，自动化调度能力仍以后续阶段为准。

## 21. 回滚方式

当前尚未 commit。如需回滚阶段 2J 代码改动：

1. 使用 patch 目录中的反向 patch，或在提交前丢弃以下文件改动：
   - `backend/src/services/canvas.py`
   - `backend/src/services/provider/vector_engine_provider.py`
   - `frontend/src/views/TasksHistory.vue`
   - `frontend/src/views/canvas/CanvasEditor.vue`
2. 删除 `PHASE2J_SUMMARY.md`。
3. 不处理 `.env.demo` / `PHASE0_BASIC_AUTH.txt`，它们不属于阶段 2J 提交内容。

patch 目录：

- `/opt/backups/aicon-demo-20260702-phase2j-patches`

## 22. 下一步建议

下一步只建议做阶段 2J commit 固化。不要进入 UI 美化，不要接 Dify，不要做作品库重构，不要做字幕 / 转场 / 配乐。

## 23. 明确结论

- 阶段 2J 完成了缺图补齐。
- 阶段 2J 完成了 raw base64 图生视频补齐。
- 阶段 2J 完成了补齐后 async compose。
- 阶段 2J 完成了最终 MP4 生成。
- 本阶段新增后端 API：否。
- 本阶段新增数据库字段：否。
- 本阶段修改 Dockerfile：否。
- 本阶段修改 New API / media-gateway：否。
- 本阶段没有提交 `.env.demo` / `PHASE0_BASIC_AUTH.txt`。
- 临时脚本本地、服务器 `/tmp`、容器 `/tmp` 均已删除。
- 当前没有 commit。
