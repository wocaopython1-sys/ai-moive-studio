# AICON 阶段 1A 总结

日期：2026-06-30

## 阶段目标

阶段 1A 的目标是把 AICON Canvas 从“节点能看到”推进到“真实创作工作流能连续使用”：

- 素材可以进入 Canvas。
- 图片/视频节点可以预览、下载、播放。
- Canvas 节点和关系可以保存、刷新恢复。
- 右侧助手可以读取 Canvas/选中节点，生成 Prompt/视频 Prompt/分镜建议，并写回节点。
- 助手结果可以继续作为图片/视频生成 Prompt，生成结果回写为 ImageNode/VideoNode，并建立 connection。

## 最终完成能力

1. PNG / MP4 上传可用。
2. `/api/v1/files/list` 文件列表 / 最近素材可用。
3. 图片 `preview/download` 可用，视频 `stream/download` 可用。
4. 图片/视频素材可以加入 Canvas。
5. 新增素材节点后自动定位、自动选中，右侧 Inspector 显示当前节点。
6. Canvas 节点保存刷新恢复可用。
7. 复用 CanvasConnection，文本 -> 图片、图片 -> 视频关系可保存恢复。
8. 右侧助手已降级为 REST + 普通文本模型调用，不再依赖复杂 tool calling。
9. 助手能读取 Canvas / 选中节点。
10. 助手能生成 Prompt 优化、视频 Prompt、分镜建议。
11. 助手结果能写回新文本节点或更新当前节点。
12. 助手 Prompt -> 图片生成 -> ImageNode 回写已通过。
13. 助手视频 Prompt -> 图生视频 -> VideoNode 回写已通过。
14. 分镜建议 -> 多 Prompt 节点已通过。
15. graph/API/DB 已确认节点和 connection 持久化。

## 改动文件清单

| 文件 | 改动内容 | 所属能力 | 验证状态 |
|---|---|---|---|
| `docker-compose.demo.yml` | 新增/维护隔离 demo compose，端口绑定 127.0.0.1 | 调试部署 | 已验证容器运行 |
| `.env.demo` | demo 环境配置 | 调试部署 | 已验证服务启动 |
| `frontend/Dockerfile` | demo 前端构建适配 | 调试部署 | 已验证前端 healthy |
| `frontend/nginx.conf` | 前端容器内 API 转发/构建适配 | 调试部署 | 已验证首页 200 |
| `backend/src/api/v1/media.py` | 新增媒体 proxy 路由：preview/download/stream | 媒体访问 | GET 已验证 200 |
| `backend/src/utils/media_urls.py` | 统一生成 `/api/v1/media/...` 媒体 URL | 媒体访问 | 图片/视频已验证 |
| `backend/src/api/v1/__init__.py` | 注册 media/canvas assistant 等路由 | API 路由 | 已验证 API 可访问 |
| `backend/src/api/schemas/file.py` | 文件列表增加 media_type、mime_type、preview/download/stream URL 字段 | 文件列表/素材 | 已验证 files/list 200 |
| `backend/src/api/v1/files.py` | 支持 MP4/MOV/WEBM 类型识别和上传后列表字段 | MP4 上传/素材列表 | PNG/MP4 已验证 |
| `backend/src/utils/file_handlers.py` | 扩展视频 MIME/扩展名识别 | MP4 上传 | 已验证 |
| `frontend/src/services/upload.js` | 文件列表/上传前端服务适配 | 上传/素材 | 已验证 |
| `frontend/src/components/canvas/CanvasAssetDrawer.vue` | 新增最近素材抽屉，支持图片/视频加入 Canvas | 素材加入 Canvas | 图片/视频各 2 次已验证 |
| `frontend/src/views/canvas/CanvasEditor.vue` | 接入素材抽屉、节点定位/选中、媒体节点创建、connection、助手生成动作 | Canvas 主闭环 | 已验证 |
| `frontend/src/components/canvas/KonvaCanvasStage.vue` | Canvas 节点/连接显示、视口/选择相关适配 | Canvas 显示 | 已验证不白屏 |
| `frontend/src/composables/useCanvasEditor.js` | Canvas items/connections 状态、保存恢复、连接创建适配 | Canvas 状态 | 已验证 |
| `frontend/src/components/canvas/CanvasWorkbenchLayout.vue` | 布局接入素材/助手/Inspector 交互 | Canvas 工作台 | 已验证 |
| `frontend/src/components/canvas/CanvasImageStudio.vue` | 图片节点预览/下载/媒体 URL 适配 | 图片节点 | 已验证 |
| `frontend/src/components/canvas/CanvasVideoStudio.vue` | 视频节点播放/下载/媒体 URL 适配 | 视频节点 | 已验证 |
| `frontend/src/components/canvas/CanvasTextStudio.vue` | 文本/Prompt 节点内容和助手写回适配 | 文本节点 | 已验证 |
| `backend/src/api/schemas/canvas_assistant.py` | 新增 suggest/apply 请求响应字段 | 右侧助手 | 已验证 |
| `backend/src/api/v1/canvas_assistant.py` | 新增 REST suggest/apply，调用普通文本模型，支持写回节点和 connection | 右侧助手 | 已验证 |
| `frontend/src/services/canvasAssistant.js` | 新增 assistant suggest/apply 前端 API | 右侧助手 | 已验证 |
| `frontend/src/composables/useCanvasAssistant.js` | 助手状态、动作、结果处理 | 右侧助手 | 已验证 |
| `frontend/src/components/canvas/assistant/CanvasAssistant.vue` | 新增优化 Prompt、视频 Prompt、分镜、写回、用作图片/视频 Prompt、拆分节点按钮 | 右侧助手闭环 | 已验证 |
| `frontend/src/components/canvas/assistant/CanvasAssistantTimeline.vue` | 助手时间线/结果展示适配 | 右侧助手 | 已验证 |
| `backend/src/api/v1/canvas.py` | connection/API/graph 返回与生成流适配 | Canvas graph/connection | 已验证 |
| `backend/src/services/canvas.py` | Canvas items/connections 保存读取、生成结果写回、视频下载保存适配 | Canvas/生成回写 | 已验证 |
| `backend/src/services/api_key.py` | BigModel 自定义模型列表包含 `glm-image`、`cogvideox-3`、文本模型 | 模型选择 | 已验证 |
| `backend/src/services/provider/custom_provider.py` | 自定义 provider 请求字段小适配 | Provider | 已验证生成链路 |
| `backend/src/services/provider/vector_engine_provider.py` | 视频 provider 适配 `cogvideox-3` / 图生视频结果 | 视频生成 | 已验证 |
| `backend/src/core/config.py` | demo 配置项小适配 | 部署/服务 | 已验证 |

## 已验证流程

1. 首页可打开，frontend 200。
2. backend `/health/` 200。
3. frontend/backend/Postgres/Redis/MinIO healthy，worker/beat running。
4. `/api/v1/files/list` 200。
5. PNG 上传 1 次回归通过。
6. MP4 上传 2 次通过。
7. 图片素材加入 Canvas 2 次通过。
8. 视频素材加入 Canvas 2 次通过。
9. 新增节点自动定位、自动选中、Inspector 显示通过。
10. 图片 preview/download GET 200。
11. 视频 stream/download GET 200。
12. Canvas graph API 返回节点和 connections。
13. 文本 -> 图片 connection 保存刷新恢复 2 次通过。
14. 图片 -> 视频 connection 保存刷新恢复 2 次通过。
15. 助手读取 Canvas / 选中节点通过。
16. 助手 Prompt 优化、视频 Prompt、分镜建议通过。
17. 助手写回新文本节点 / 更新当前节点通过。
18. 助手 Prompt -> 图片生成 -> ImageNode 回写通过。
19. 助手视频 Prompt -> 图生视频 -> VideoNode 回写 2 次通过。
20. 分镜建议 -> 多 Prompt 节点 2 次通过。

## 轻量回归证据

阶段 1A 冻结时的备份目录：

`/opt/backups/aicon-demo-20260630-121311-phase1a-final`

其中保存：

- `evidence/docker-compose-ps.txt`
- `evidence/backend-health.txt`
- `evidence/frontend-home.txt`
- `evidence/phase1a-final-api-evidence.json`
- `evidence/phase1a-final-canvas-smoke.json`
- `evidence/phase1a-final-canvas-smoke.png`

冻结时轻量回归结果：

- frontend 首页：200。
- backend `/health/`：200。
- files/list：200。
- graph API：200，返回节点和 connection。
- 图片 preview/download：GET 200。
- 视频 stream/download：GET 200。
- Canvas 页面：非白屏，Konva stage 和助手按钮存在。

## 没有完成但暂不阻塞的问题

1. 作品库仍是“文件列表/最近素材”形态，不是完整作品库系统。
2. 右侧助手没有继续使用复杂 Agent/tool calling，当前是可用优先的 REST + 普通文本模型。
3. Dify 未接入，当前 AICON 是独立调试环境。
4. 阶段 1A 没有做任务中心、批量任务管理、队列 UI。
5. Canvas 关系已经能保存和展示来源，但还不是完整可视化工作流编排器。

## 已知小问题

1. 对媒体接口使用 HEAD 会返回 405，这是接口方法不支持，不代表媒体失败；验收以 GET 200 为准。
2. 模型 429 表示账户余额/资源包/Key/模型账户问题，不等于 AICON 软件断链。
3. 公网入口仍有 Basic Auth；本阶段未改 Cloudflare/Nginx/Basic Auth。
4. 当前 AICON 调试反代配置实际位于 Dify nginx 配置目录：`/opt/dify/docker/nginx/conf.d/zz-aicon-debug.conf`，不是系统 `/etc/nginx`。
5. demo 使用 `.env.demo`，不要把它当生产配置。

## 下一阶段建议

阶段 1B 之前建议先做一次代码整理：

1. 将阶段 1A 改动按能力拆分成清晰 commit 或补丁包。
2. 给 Canvas 关键闭环补 3 到 5 个自动化回归脚本。
3. 再进入阶段 1B，不要一边大改作品库一边继续改 Canvas 主闭环。

阶段 1B 的候选方向：

1. 任务中心 / 生成历史 UI。
2. 作品库从文件列表升级为轻量资产库。
3. 视频任务状态 UI 和批量轮询体验。
4. Canvas 关系可视化增强。

## 回滚方式

只回滚 AICON demo，不影响 Dify/New API/media-gateway：

```bash
cd /opt/aicon-demo

# 停止 demo 容器，保留卷。
sudo docker compose -f docker-compose.demo.yml down

# 如需回滚代码到仓库原始状态：
git restore .
git clean -fd

# 如需从阶段 1A 备份恢复文件：
BACKUP=/opt/backups/aicon-demo-20260630-121311-phase1a-final
rsync -a "$BACKUP/files/" /opt/aicon-demo/

# 恢复后重启 demo：
cd /opt/aicon-demo
sudo docker compose -f docker-compose.demo.yml up -d --build
```

如需回滚 AICON 调试域名反代配置：

```bash
BACKUP=/opt/backups/aicon-demo-20260630-121311-phase1a-final
sudo cp "$BACKUP/nginx/zz-aicon-debug.conf" /opt/dify/docker/nginx/conf.d/zz-aicon-debug.conf
sudo cp "$BACKUP/nginx/.aicon_debug_htpasswd" /opt/dify/docker/nginx/conf.d/.aicon_debug_htpasswd

# 注意：当前服务器未安装系统 nginx，AICON 反代配置属于 Dify nginx 容器。
# 需要按当时 Dify nginx 的实际 compose/service 名称 reload 或重启对应 nginx 容器。
```

## 不要误判的点

1. HEAD 405 不是媒体失败，GET 200 才是媒体验收标准。
2. 模型 429 是账户/资源包/Key/模型账户问题，不等于软件断链。
3. tool calling 未使用，当前助手是 REST + 普通文本模型。
4. Dify 未接入，后续再说。
5. 作品库仍是文件列表型，后续阶段处理。
