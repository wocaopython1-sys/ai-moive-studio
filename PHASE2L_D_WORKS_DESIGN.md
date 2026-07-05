# AICON Phase 2L-D Works Library Design

## 1. 设计背景

阶段 2L 已完成素材库标签、素材库回跳 Canvas、Canvas 跳素材库搜索三个方向：

- 2L-A：素材库显示图片素材 / 视频素材 / 文本素材，以及 Canvas 来源 / 来源未标注。
- 2L-B：素材库中有 `canvas_id` 的素材可以跳回 Canvas；有 `canvas_item_id` 时可以定位节点。
- 2L-C：Canvas 中有可靠 `object_key` 的媒体节点可以跳到素材库搜索同一文件。

当前项目没有真正作品库：没有 works 页面、没有 works 路由、没有 works API、没有 works DB 表。当前素材库是文件级素材入口，不是作品级实体。它聚合 MinIO 文件、Canvas 文本素材和少量 Canvas 来源字段，但没有作品 ID、作品状态、归档时间、封面、最终文件、来源 Canvas、来源 final 节点、来源 generation 的稳定业务关系。

当前 final MP4 可能进入 MinIO，并可能被素材库列出，但这不是作品库归档。`object_key` 只能定位同一文件，不能代表作品关系、来源关系或 final 语义。继续把作品逻辑硬塞进素材库，会把文件级入口和作品级实体混在一起，后续会导致普通视频素材被误标成作品、来源关系不可追踪、删除语义不清、权限边界不清。

因此，2L-D 的正确方向不是弱聚合入口，而是先设计真正作品库的 DB / API / 前端入口 / migration / rollback / validation 边界。

## 2. 目标与非目标

### 目标

- 定义真正作品库实体。
- 支持从 Canvas final 节点明确归档作品。
- 支持作品列表。
- 支持作品详情。
- 支持作品标题、描述、封面、状态。
- 支持来源关系：`source_canvas_id`、`source_canvas_item_id`、`source_generation_id`。
- 支持最终文件关系：`final_object_key`。
- 支持作品附属素材：`work_items`。
- 支持 `user_id` 权限隔离。
- 支持删除作品记录时不误删原始素材文件。
- 支持 migration 回滚。
- 支持不影响现有 `/library`、`/canvas`、`/tasks`。

### 非目标

- 不从 `object_key` / 文件名 / 路径猜 final。
- 不把普通视频自动判定为作品。
- 不把素材库改造成作品库。
- 不替代素材库。
- 不替代任务历史。
- 不做 UI 美化。
- 不做模型生成能力。
- 不触发模型。
- 不直接删除 MinIO 原始文件。
- 不自动发布作品。
- 不做分享广场 / 社区功能。
- 不做复杂审核流。
- 不做多租户商业权限系统。

## 3. 核心原则

1. 作品是业务实体，不是 `object_key`。
2. `object_key` 只是文件指针。
3. `final_object_key` 指向最终媒体文件。
4. `source_canvas_id` 指向来源 Canvas。
5. `source_canvas_item_id` 指向来源 final VideoNode。
6. `source_generation_id` 指向生成任务或 `CanvasItemGeneration`。
7. 只有明确用户动作或明确后端 final 节点规则才能创建 `works`。
8. 普通视频素材不能自动成为作品。
9. 删除作品记录不默认删除文件。
10. 权限必须按 `user_id` 隔离。
11. 新 API 不能破坏旧 `/library`、`/canvas`、`/tasks`。
12. migration 必须可 downgrade。
13. 历史数据回填必须保守，不能乱猜。

## 4. 推荐数据模型

### works 表

| 字段 | 类型建议 | 是否必填 | 说明 |
|---|---|---|---|
| id | uuid / text | 是 | 作品 ID |
| user_id | uuid / text | 是 | 所属用户 |
| title | text | 是 | 作品标题 |
| description | text | 否 | 作品描述 |
| cover_object_key | text | 否 | 封面文件 |
| final_object_key | text | 是 | 最终作品文件 |
| source_canvas_id | uuid / text | 否 | 来源 Canvas |
| source_canvas_item_id | uuid / text | 否 | 来源 final 节点 |
| source_generation_id | uuid / text | 否 | 来源生成记录 |
| status | text | 是 | draft / archived / published / hidden / deleted |
| metadata | json/jsonb/text | 否 | 扩展元数据 |
| created_at | datetime | 是 | 创建时间 |
| updated_at | datetime | 是 | 更新时间 |
| archived_at | datetime | 否 | 归档时间 |
| deleted_at | datetime | 否 | 软删除时间 |

说明：

- `final_object_key` 不等于作品来源关系，它只指向最终媒体文件。
- `source_canvas_id`、`source_canvas_item_id`、`source_generation_id` 才是来源关系。
- `status` 首版建议只使用 `draft` / `archived` / `hidden` / `deleted`，暂不做 `published`。
- `deleted_at` 表示软删除，不默认删除 MinIO 原始文件。

### work_items 表

| 字段 | 类型建议 | 是否必填 | 说明 |
|---|---|---|---|
| id | uuid / text | 是 | item ID |
| work_id | uuid / text | 是 | 所属作品 |
| object_key | text | 是 | 文件对象 |
| media_type | text | 是 | image / video / text / audio |
| role | text | 是 | final / cover / source / reference / intermediate |
| source_canvas_item_id | uuid / text | 否 | 来源 Canvas 节点 |
| source_generation_id | uuid / text | 否 | 来源生成记录 |
| sort_order | int | 是 | 排序 |
| metadata | json/jsonb/text | 否 | 扩展元数据 |
| created_at | datetime | 是 | 创建时间 |

说明：

- `role=final` 的 `work_item` 应与 `works.final_object_key` 对应。
- cover 可以独立于 final。
- intermediate / reference 不代表 final。
- `object_key` 仍然只是文件指针。

## 5. 索引与约束建议

建议索引：

- `works.user_id` index。
- `works.status` index。
- `works.source_canvas_id` index。
- `works.source_canvas_item_id` index。
- `works.source_generation_id` index。
- `works.final_object_key` index。
- `work_items.work_id` index。
- `work_items.object_key` index。
- `work_items.source_canvas_item_id` index。
- `work_items.source_generation_id` index。

可选 unique：

- `user_id + source_canvas_item_id + final_object_key`。

不建议全局 unique `final_object_key`，因为未来可能复制作品，也可能出现多用户隔离、导入、迁移或人工复制作品的需求。

外键是否强约束要谨慎。如果当前 Canvas / generation 表结构仍在演进，首版可以先做逻辑关联：保存 ID 字段、按 `user_id` 做权限校验、在 API 读取时尝试解析来源。等 Canvas schema 稳定后，再考虑强外键。

## 6. 推荐 API 设计

### GET /api/v1/works

用途：获取当前用户作品列表。

查询参数：

- `page`
- `page_size`
- `status`
- `q`
- `source_canvas_id`
- `media_type`
- `created_from`
- `created_to`

返回字段：

- `id`
- `title`
- `description`
- `cover_url` 或 `cover_object_key`
- `final_url` 或 `final_object_key`
- `status`
- `source_canvas_id`
- `source_canvas_item_id`
- `created_at`
- `updated_at`

### GET /api/v1/works/{work_id}

用途：获取作品详情。

返回：

- `works` 主表字段。
- `work_items`。
- source canvas 信息。
- final 文件下载 / 预览信息。

### POST /api/v1/works/from-canvas-final

用途：从明确 Canvas final 节点归档作品。

请求字段：

- `canvas_id`
- `canvas_item_id`
- `title`
- `description`
- `cover_object_key` 可选
- `include_sources` 可选

后端必须校验：

- 当前用户有 Canvas 权限。
- `canvas_item_id` 属于 `canvas_id`。
- item 是明确 final VideoNode。
- 能拿到 `result_video_object_key` 或 `final_object_key`。
- 不从 filename/path 猜 final。
- 不能把普通视频节点自动归档为作品。

### PATCH /api/v1/works/{work_id}

用途：修改标题、描述、封面、状态。

限制：

- 只能修改当前用户自己的作品。
- 不能随意改 `source_canvas_id` / `source_canvas_item_id`。
- 如果要改 `final_object_key`，必须另开明确动作。

### DELETE /api/v1/works/{work_id}

用途：删除作品记录。

首版建议软删除：

- 不默认删除 MinIO 原始文件。
- 不删除素材库文件。
- 不删除 Canvas 节点。
- 不删除任务历史。

## 7. 前端页面建议

- 新增 `/works` 或 `/portfolio` 路由，建议统一叫 `/works`。
- 新增 `WorksLibrary.vue` 或 `WorksList.vue`。
- 作品卡片显示：
  - 封面。
  - 标题。
  - 状态。
  - 创建时间。
  - 来源 Canvas。
  - 预览 / 下载 / 回到 Canvas。
- Canvas final 节点增加“归档为作品”入口。
- 归档弹窗字段：
  - 标题。
  - 描述。
  - 封面选择。
  - 是否包含来源素材。
- 素材库不直接变作品库。
- 素材库可以有“用于作品封面 / 添加到作品”的后续入口，但不是首版必须。
- 任务历史可以显示“已归档为作品”状态，但不是首版必须。

## 8. 归档流程

1. 用户在 Canvas 中选中 final VideoNode。
2. 前端判断该节点是明确 final。
3. 用户点击“归档为作品”。
4. 前端提交 `canvas_id` + `canvas_item_id` + `title`。
5. 后端校验用户权限。
6. 后端校验节点属于该 Canvas。
7. 后端校验节点是明确 final。
8. 后端读取 `result_video_object_key`。
9. 后端创建 `works` 记录。
10. 后端创建 `work_items`：
    - final item。
    - cover item 可选。
    - source / reference / intermediate items 可选。
11. 前端跳转 `/works/{id}` 或提示归档成功。
12. 原 Canvas / 素材库 / 任务历史不被破坏。

## 9. 权限与安全

- 所有 works 查询必须按 `user_id` 隔离。
- `from-canvas-final` 必须校验 Canvas owner。
- `work_items` 只能通过 `work_id` 间接访问并校验 `work.user_id`。
- 下载 / 预览仍然需要沿用现有文件权限策略。
- 不把 `object_key` 当作授权依据。
- 不泄露其他用户作品。
- 不打印 key/token/password/object_key 真实值到日志。
- 删除作品不删除原始文件，避免误删共享素材。

## 10. Migration 设计与回滚

- migration 新增 `works` 表。
- migration 新增 `work_items` 表。
- migration 新增必要索引。
- downgrade 顺序必须先删除 `work_items`，再删除 `works`。
- 如果使用 SQLite / Postgres 兼容，需要注意 UUID / JSON 类型差异。
- 首版不要自动回填历史作品，避免误判普通视频。
- 历史回填如需做，必须单独写只读评估和迁移脚本设计。
- migration 前必须先备份 DB。
- migration 必须可在测试环境验证。

## 11. 与现有模块关系

### 与素材库关系

- 素材库是文件级入口。
- 作品库是作品级实体。
- 素材库不承担作品状态。
- 作品库引用 `object_key`，但 `object_key` 不代表作品。

### 与 Canvas 关系

- Canvas 是创作过程。
- 作品库是归档结果。
- `source_canvas_id` / `source_canvas_item_id` 连接来源。
- Canvas 删除或修改后的影响需要定义：首版建议作品记录保留，来源链接可显示“来源已删除或不可访问”。

### 与任务历史关系

- 任务历史是生成过程日志。
- 作品库不是任务历史。
- `source_generation_id` 可连接生成记录。
- 任务重试不应自动覆盖已归档作品。

### 与 MinIO / Storage 关系

- MinIO 存文件。
- `works` 存作品关系。
- 删除 `works` 不默认删 MinIO 文件。
- `object_key` 不可直接暴露为权限凭证。

## 12. 验收标准

### 功能验收

- 能从明确 final Canvas 节点创建作品。
- 普通视频节点不能直接伪装成作品。
- 作品列表能显示作品。
- 作品详情能显示 final 视频。
- 作品能跳回来源 Canvas。
- 作品删除只删除记录，不删除原始文件。
- 素材库原功能不受影响。
- Canvas 原功能不受影响。
- 任务历史原功能不受影响。

### 安全验收

- 用户只能看到自己的作品。
- 非 owner 无法通过 `work_id` 访问作品。
- 非 owner 无法从别人的 Canvas 归档作品。
- 不泄露 `.env` / Basic Auth / key / token。

### 回归验收

- `/library` 200。
- `/canvas` 200。
- `/tasks` 200。
- `/dashboard` 200。
- `/works` 200。
- `/health/` 200。
- backend / celery / frontend 无 ERROR / Traceback / Exception。

## 13. 分阶段实施建议

### 2L-D1 设计文档

本轮只做设计文档。文档描述 DB、API、前端入口、migration、回滚、验收边界，不创建 API、不创建 DB、不写 migration、不实现页面。

### 2L-D2 后端 schema / migration 只读审计

实现前再审：检查当前 SQLAlchemy BaseModel、UUID 类型、JSON 类型、migration 命名、现有权限依赖、现有 files/canvas/tasks API response shape。此阶段不直接 migration。

### 2L-D3 DB + API 最小实现

最小实现范围：

- `works` / `work_items`。
- `GET /works`。
- `GET /works/{id}`。
- `POST /works/from-canvas-final`。

### 2L-D4 前端作品库最小页面

最小页面范围：

- `/works` 列表。
- `/works/{id}` 详情。
- Canvas “归档为作品”。

### 2L-D5 验收与回滚

验收范围：

- 页面验收。
- 权限验收。
- DB 备份。
- downgrade 演练。

不要跳过设计和 DB 备份直接开发。

## 14. 当前不建议做的事

- 不建议用 `object_key` 搜索结果冒充作品库。
- 不建议把普通视频素材标成最终成片。
- 不建议在素材库里直接加“最终成片”猜测标签。
- 不建议没有 DB 就做作品状态。
- 不建议没有 owner 校验就做 works API。
- 不建议自动回填历史 final。
- 不建议直接 push。
- 不建议把 Basic Auth 凭据写进文档。

## 15. 最终结论

当前可以继续做 2L-D，但必须先设计后实现。真作品库推荐路线 C：新增 DB + API + migration。

下一步建议：对 `PHASE2L_D_WORKS_DESIGN.md` 做 patch / summary / 提交前闭合审计，再决定是否 commit。不建议直接进入实现。
