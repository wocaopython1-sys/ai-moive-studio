# AICON 阶段 1C 总结：轻量作品/素材库体验升级

## 1. 阶段目标

阶段 1C 的目标是把原本“文件列表型素材库”升级为最小可用的“作品/素材库体验”，服务于当前 AI 图片/视频创作工作台闭环。

本阶段不是完整作品库系统，不是社区作品流，不是公开分享页，不是模型广场，也不是商业化资产系统。当前实现是轻量素材库体验。

## 2. 已完成功能

- 新增 `/library` 素材库页面。
- 新增侧边栏“素材库”入口。
- 新增轻量素材聚合接口 `/api/v1/files/library`。
- 图片素材、视频素材、Prompt/文本素材统一展示。
- 支持类型筛选：全部、图片、视频、文本/Prompt。
- 支持来源筛选：全部来源、上传、生成结果、Canvas。
- 支持按文件名、object_key、标题、Prompt 文本进行轻量搜索。
- 素材卡片支持预览、下载、复制 URL、加入 Canvas。
- 图片/视频从 `/library` 页面点击“加入 Canvas”后可真实创建节点并跳转聚焦。
- 文本/Prompt 从 `/library` 页面点击“加入 Canvas”后可真实创建文本节点并跳转聚焦。
- Canvas 关系面板新增“保存到素材库”按钮。
- Canvas 文本节点保存后可作为 Prompt/文本素材被 `/files/library` 聚合展示。
- 图片/视频节点保存到素材库采用最小标记方式；媒体对象本身继续来自 MinIO 文件对象。
- 阶段 1A Canvas、媒体、connection、助手入口未破坏。
- 阶段 1B 任务中心页面和跳转入口未破坏。

## 3. 新增 API

- `GET /api/v1/files/library`

请求参数：

- `media_type=all|image|video|text|prompt`
- `source=all|upload|generated|canvas`
- `q=关键词`
- `page`
- `size`
- `limit`
- `offset`

返回结构复用 `FileListResponse`，同时提供 `files` 与 `items` 字段。

## 4. 新增前端页面

- `/library`：素材库页面。

注意：`/assets` 路由会撞前端静态资源目录 `/assets/`，Nginx 会返回 403，所以阶段 1C 使用 `/library`。

## 5. 改动文件清单

| 文件 | 改动内容 |
|---|---|
| `backend/src/api/schemas/file.py` | 为 `FileInfo` 增加素材库展示字段，`FileListResponse` 增加 `items` 别名 |
| `backend/src/api/v1/files.py` | 增强 `/files/list` 过滤字段；新增 `/files/library` 聚合接口；增加 Canvas 文本素材聚合逻辑 |
| `frontend/src/views/AssetsLibrary.vue` | 新增素材库页面 |
| `frontend/src/router/index.js` | 增加 `/library` 路由 |
| `frontend/src/components/layout/AppSidebar.vue` | 增加“素材库”导航入口 |
| `frontend/src/services/upload.js` | 增加 `listLibrary` 方法 |
| `frontend/src/views/canvas/CanvasEditor.vue` | 增加“保存到素材库”按钮与最小保存标记逻辑 |

## 6. 验证结果

### UI smoke

- `/library` 页面 200。
- 浏览器 smoke 显示素材库页面、搜索框、筛选按钮、素材网格和详情面板。
- 图片素材从 `/library` 点击“加入 Canvas”成功，创建 ImageNode 并跳转聚焦。
- 视频素材从 `/library` 点击“加入 Canvas”成功，创建 VideoNode 并跳转聚焦。
- 文本素材从 `/library` 点击“加入 Canvas”成功，创建 TextNode 并跳转聚焦。
- 保存/刷新后 graph API 仍能看到新增节点。

### API 和媒体

- 首页 200。
- `/health/` 200。
- `/library` 200。
- `/api/v1/files/library` 200。
- `/tasks` 200。
- graph API 200。
- 图片 preview/download 200。
- 视频 stream/download 200。
- PNG 上传 200，上传后素材库可见。
- MP4 上传 200，上传后素材库可见。

### 回归

- Canvas 页面不白屏。
- 右侧助手入口、优化 Prompt、视频 Prompt、分镜建议按钮仍存在。
- 任务中心页面可打开，“跳转 Canvas 节点”按钮仍存在。
- 最近后端日志没有 Traceback / ERROR / Exception / 500。

## 7. 未完成但不阻塞的问题

- 当前不是完整作品库系统。
- 当前没有新增复杂资产表。
- 没有 collection/tag/favorite/album 等正式资产库能力。
- 图片/视频素材来自 MinIO 文件对象和 files/list；来源识别是轻量规则。
- Prompt/文本素材来自 Canvas 文本节点聚合。
- 上传后文件名由存储层改为 UUID，因此不能按原始上传文件名搜索，只能按返回后的文件名/object_key 搜索。
- 图片/视频“保存到素材库”当前是标记保存和提示，因为媒体对象本来已经在 MinIO 素材列表中可见。
- 从素材库加入 Canvas 的节点是导入节点，状态可能为 `idle`，不是生成任务完成状态。

## 8. 回滚方式

如果只回滚阶段 1C 代码改动：

```bash
cd /opt/aicon-demo
git reset --hard 94ee46f
sudo docker compose -f docker-compose.demo.yml build backend frontend
sudo docker compose -f docker-compose.demo.yml up -d backend frontend celery-worker celery-beat
```

如果使用 patch 反向回滚：

```bash
cd /opt/aicon-demo
git apply -R /opt/backups/aicon-demo-20260630-phase1c-patches/phase1c-all.diff
sudo docker compose -f docker-compose.demo.yml build backend frontend
sudo docker compose -f docker-compose.demo.yml up -d backend frontend celery-worker celery-beat
```

不要删除 `.env.demo`、`PHASE0_BASIC_AUTH.txt` 或任何线上旧系统文件。

## 9. 下一阶段建议

下一阶段可以进入任务中心之后的“资产库持久化模型”或“作品库正式化”设计，但建议先保持最小步幅：

1. 明确定义轻量 asset 表是否需要。
2. 决定收藏/标签/作品归档是否进入 1D。
3. 再考虑公开分享、团队协作、作品库重构。

不要在没有产品边界的情况下直接扩成完整社区/广场系统。
