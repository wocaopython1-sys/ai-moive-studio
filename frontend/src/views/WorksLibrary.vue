<template>
  <section class="works-library-page">
    <header class="works-header">
      <div>
        <h1>作品库</h1>
        <p>归档后的 Canvas final 作品元数据列表</p>
      </div>
      <el-button :loading="loading" @click="loadWorks">刷新</el-button>
    </header>

    <el-card class="works-card" shadow="never">
      <template #header>
        <div class="works-card__header">
          <div>
            <h2>我的作品</h2>
            <span>{{ total }} 个作品</span>
          </div>
        </div>
      </template>

      <div v-if="loading" class="works-state">正在加载作品...</div>
      <el-empty v-else-if="!works.length" description="暂无作品" />

      <template v-else>
        <el-table :data="works" class="works-table" row-key="id">
          <el-table-column prop="title" label="标题" min-width="180">
            <template #default="{ row }">
              <div class="work-title">{{ row.title || '未命名作品' }}</div>
              <div class="work-id">{{ shortText(row.id, 18) }}</div>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="110">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)" effect="plain">
                {{ statusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="final_object_key" label="最终对象" min-width="240">
            <template #default="{ row }">
              <span class="object-key">{{ maskObjectKey(row.final_object_key) || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="170">
            <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
          </el-table-column>
          <el-table-column prop="updated_at" label="更新时间" width="170">
            <template #default="{ row }">{{ formatDate(row.updated_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="openDetail(row)">查看详情</el-button>
              <el-button
                size="small"
                type="danger"
                :loading="deletingId === row.id"
                @click="deleteWork(row)"
              >
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="works-pagination">
          <el-pagination
            v-model:current-page="page"
            v-model:page-size="pageSize"
            background
            layout="total, sizes, prev, pager, next"
            :page-sizes="[10, 20, 50]"
            :total="total"
            @current-change="loadWorks"
            @size-change="handlePageSizeChange"
          />
        </div>
      </template>
    </el-card>

    <el-drawer
      v-model="detailVisible"
      title="作品详情"
      size="560px"
      :destroy-on-close="true"
      @closed="resetMediaPreview"
    >
      <div v-if="detailLoading" class="works-state">正在加载详情...</div>
      <div v-else-if="selectedWork" class="work-detail">
        <el-alert
          title="预览/下载使用作品权限接口，视频 seek 暂不保证。"
          type="info"
          :closable="false"
          show-icon
        />

        <dl class="work-detail__meta">
          <div>
            <dt>ID</dt>
            <dd>{{ selectedWork.id }}</dd>
          </div>
          <div>
            <dt>标题</dt>
            <dd>{{ selectedWork.title || '未命名作品' }}</dd>
          </div>
          <div>
            <dt>描述</dt>
            <dd>{{ selectedWork.description || '-' }}</dd>
          </div>
          <div>
            <dt>状态</dt>
            <dd>
              <el-tag :type="statusTagType(selectedWork.status)" effect="plain">
                {{ statusLabel(selectedWork.status) }}
              </el-tag>
            </dd>
          </div>
          <div>
            <dt>final_object_key</dt>
            <dd class="object-key">{{ maskObjectKey(selectedWork.final_object_key) || '-' }}</dd>
          </div>
          <div>
            <dt>source_canvas_id</dt>
            <dd>{{ selectedWork.source_canvas_id || '-' }}</dd>
          </div>
          <div>
            <dt>source_canvas_item_id</dt>
            <dd>{{ selectedWork.source_canvas_item_id || '-' }}</dd>
          </div>
          <div>
            <dt>source_generation_id</dt>
            <dd>{{ selectedWork.source_generation_id || '-' }}</dd>
          </div>
          <div>
            <dt>created_at</dt>
            <dd>{{ formatDate(selectedWork.created_at) }}</dd>
          </div>
          <div>
            <dt>updated_at</dt>
            <dd>{{ formatDate(selectedWork.updated_at) }}</dd>
          </div>
        </dl>

        <section class="work-items">
          <h3>关联素材</h3>
          <el-empty
            v-if="!selectedWork.items?.length"
            description="暂无关联素材"
            :image-size="80"
          />
          <el-table v-else :data="selectedWork.items" row-key="id" size="small">
            <el-table-column prop="role" label="角色" width="90" />
            <el-table-column prop="media_type" label="类型" width="90">
              <template #default="{ row }">{{ mediaTypeLabel(row.media_type) }}</template>
            </el-table-column>
            <el-table-column prop="object_key" label="对象">
              <template #default="{ row }">
                <span class="object-key">{{ maskObjectKey(row.object_key) || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <div class="work-item-actions">
                  <el-button
                    size="small"
                    :loading="previewingItemId === row.id"
                    @click="previewWorkItem(row)"
                  >
                    预览
                  </el-button>
                  <el-button
                    size="small"
                    :loading="downloadingItemId === row.id"
                    @click="downloadWorkItem(row)"
                  >
                    下载
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </section>
      </div>
    </el-drawer>

    <el-dialog
      v-model="mediaPreviewVisible"
      :title="mediaPreviewTitle"
      width="720px"
      class="work-media-preview-dialog"
      @closed="resetMediaPreview"
    >
      <div class="work-media-preview">
        <video
          v-if="mediaPreviewType === 'video' && mediaPreviewUrl"
          :src="mediaPreviewUrl"
          controls
        />
        <img
          v-else-if="mediaPreviewType === 'image' && mediaPreviewUrl"
          :src="mediaPreviewUrl"
          alt="作品媒体预览"
        />
        <audio
          v-else-if="mediaPreviewType === 'audio' && mediaPreviewUrl"
          :src="mediaPreviewUrl"
          controls
        />
        <el-empty v-else :description="mediaPreviewMessage || '不支持内联预览，请下载查看'" />
      </div>
    </el-dialog>
  </section>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { worksService } from '@/services/works'

const works = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const detailLoading = ref(false)
const detailVisible = ref(false)
const selectedWork = ref(null)
const deletingId = ref('')
const previewingItemId = ref('')
const downloadingItemId = ref('')
const mediaPreviewVisible = ref(false)
const mediaPreviewUrl = ref('')
const mediaPreviewUrlIsObjectUrl = ref(false)
const mediaPreviewTitle = ref('媒体预览')
const mediaPreviewType = ref('')
const mediaPreviewMessage = ref('')

const normalizeWorks = (response = {}) => {
  works.value = Array.isArray(response.works) ? response.works : []
  total.value = Number(response.total || 0)
}

const loadWorks = async () => {
  loading.value = true
  try {
    const response = await worksService.listWorks({
      page: page.value,
      size: pageSize.value
    })
    normalizeWorks(response)
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '作品列表加载失败')
  } finally {
    loading.value = false
  }
}

const handlePageSizeChange = () => {
  page.value = 1
  void loadWorks()
}

const openDetail = async (work) => {
  resetMediaPreview()
  detailVisible.value = true
  detailLoading.value = true
  selectedWork.value = work
  try {
    selectedWork.value = await worksService.getWork(work.id)
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '作品详情加载失败')
  } finally {
    detailLoading.value = false
  }
}

const deleteWork = async (work) => {
  await ElMessageBox.confirm(`确认删除「${work.title || '未命名作品'}」？`, '删除作品', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消'
  })

  deletingId.value = work.id
  try {
    await worksService.deleteWork(work.id)
    ElMessage.success('作品已删除')
    if (works.value.length === 1 && page.value > 1) {
      page.value -= 1
    }
    await loadWorks()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '作品删除失败')
  } finally {
    deletingId.value = ''
  }
}

const previewableMediaTypes = new Set(['video', 'image', 'audio'])

const normalizedMediaType = (item = {}) => String(item.media_type || '').trim().toLowerCase()

const mediaTypeLabel = (mediaType) =>
  ({
    video: '视频',
    image: '图片',
    audio: '音频',
    text: '文本'
  })[String(mediaType || '').trim().toLowerCase()] || mediaType || '未知'

const mediaErrorMessage = (error, action) => {
  const status = error?.response?.status
  if (status === 401) return `${action}失败：登录过期或无权限`
  if (status === 403 || status === 404) return `${action}失败：无权访问或媒体不存在`
  return `${action}失败`
}

const revokeMediaPreviewUrl = () => {
  if (mediaPreviewUrl.value && mediaPreviewUrlIsObjectUrl.value) {
    URL.revokeObjectURL(mediaPreviewUrl.value)
  }
  mediaPreviewUrl.value = ''
  mediaPreviewUrlIsObjectUrl.value = false
}

const resetMediaPreview = () => {
  revokeMediaPreviewUrl()
  mediaPreviewVisible.value = false
  mediaPreviewTitle.value = '媒体预览'
  mediaPreviewType.value = ''
  mediaPreviewMessage.value = ''
  previewingItemId.value = ''
}

const workItemTitle = (item = {}) => {
  const role = String(item.role || '').trim()
  const mediaType = mediaTypeLabel(item.media_type)
  return [role, mediaType].filter(Boolean).join(' / ') || '作品媒体'
}

const safeDownloadFilename = (item = {}) => {
  const mediaType = normalizedMediaType(item)
  const extension =
    ({
      video: 'mp4',
      image: 'png',
      audio: 'mp3',
      text: 'txt'
    })[mediaType] || 'bin'
  const workPrefix = String(selectedWork.value?.id || 'work').slice(0, 8) || 'work'
  const itemPrefix = String(item.id || 'item').slice(0, 8) || 'item'
  const role = String(item.role || mediaType || 'media').replace(/[^A-Za-z0-9_-]/g, '_')
  return `work-${workPrefix}-${role}-${itemPrefix}.${extension}`
}

const previewWorkItem = async (item = {}) => {
  const workId = selectedWork.value?.id
  const itemId = item.id
  const mediaType = normalizedMediaType(item)

  resetMediaPreview()
  mediaPreviewTitle.value = workItemTitle(item)
  mediaPreviewType.value = mediaType

  if (!workId || !itemId) {
    mediaPreviewMessage.value = '作品媒体信息不完整'
    mediaPreviewVisible.value = true
    return
  }

  if (!previewableMediaTypes.has(mediaType)) {
    mediaPreviewMessage.value = '不支持内联预览，请下载查看'
    mediaPreviewVisible.value = true
    return
  }

  previewingItemId.value = itemId
  try {
    if (mediaType === 'video') {
      const response = await worksService.createWorkItemStreamToken(workId, itemId)
      const streamUrl = String(response?.stream_url || '').trim()
      if (!streamUrl) {
        mediaPreviewMessage.value = '视频预览地址获取失败'
        mediaPreviewVisible.value = true
        return
      }
      mediaPreviewUrl.value = streamUrl
      mediaPreviewUrlIsObjectUrl.value = false
      mediaPreviewVisible.value = true
      return
    }

    const blob = await worksService.fetchWorkItemPreviewBlob(workId, itemId)
    mediaPreviewUrl.value = URL.createObjectURL(blob)
    mediaPreviewUrlIsObjectUrl.value = true
    mediaPreviewVisible.value = true
  } catch (error) {
    ElMessage.error(mediaErrorMessage(error, '预览'))
  } finally {
    previewingItemId.value = ''
  }
}

const downloadWorkItem = async (item = {}) => {
  const workId = selectedWork.value?.id
  const itemId = item.id
  if (!workId || !itemId) {
    ElMessage.error('作品媒体信息不完整')
    return
  }

  downloadingItemId.value = itemId
  try {
    await worksService.downloadWorkItemMedia(workId, itemId, safeDownloadFilename(item))
    ElMessage.success('下载已开始')
  } catch (error) {
    ElMessage.error(mediaErrorMessage(error, '下载'))
  } finally {
    downloadingItemId.value = ''
  }
}

const statusLabel = (status) =>
  ({
    archived: '已归档',
    hidden: '已隐藏',
    deleted: '已删除'
  })[status] || status || '未知'

const statusTagType = (status) =>
  ({
    archived: 'success',
    hidden: 'info',
    deleted: 'danger'
  })[status] || 'warning'

const shortText = (value, maxLength = 32) => {
  const text = String(value || '').trim()
  if (!text) return ''
  if (text.length <= maxLength) return text
  return `${text.slice(0, Math.max(0, maxLength - 3))}...`
}

const maskObjectKey = (value) => {
  const text = String(value || '').trim()
  if (!text) return ''
  if (text.length <= 4) return '***'
  if (text.length <= 12) return `${text.slice(0, 3)}...${text.slice(-3)}`

  const parts = text.split('/').filter(Boolean)
  if (parts.length < 2) return `${text.slice(0, 6)}...${text.slice(-6)}`

  const prefix = parts.slice(0, Math.min(2, parts.length - 1)).join('/')
  const filename = parts[parts.length - 1]
  const suffix = filename.length > 18 ? filename.slice(-18) : filename
  return `${prefix}/.../${suffix}`
}

const formatDate = (value) => {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

onMounted(loadWorks)
onBeforeUnmount(resetMediaPreview)
</script>

<style scoped>
.works-library-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.works-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}

.works-header h1 {
  margin: 0;
  font-size: 28px;
}

.works-header p {
  margin: 8px 0 0;
  color: var(--text-secondary);
}

.works-card {
  border-radius: 12px;
}

.works-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.works-card__header h2 {
  margin: 0;
  font-size: 18px;
}

.works-card__header span {
  display: inline-block;
  margin-top: 6px;
  color: var(--text-tertiary);
  font-size: 13px;
}

.works-state {
  padding: 48px 0;
  text-align: center;
  color: var(--text-secondary);
}

.works-table {
  width: 100%;
}

.work-title {
  font-weight: 600;
  color: var(--text-primary);
}

.work-id {
  margin-top: 4px;
  color: var(--text-tertiary);
  font-size: 12px;
}

.object-key {
  display: inline-block;
  max-width: 100%;
  color: var(--text-secondary);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  word-break: break-all;
}

.works-pagination {
  display: flex;
  justify-content: flex-end;
  padding-top: 18px;
}

.work-detail {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.work-detail__meta {
  display: grid;
  gap: 14px;
  margin: 0;
}

.work-detail__meta div {
  display: grid;
  grid-template-columns: 150px minmax(0, 1fr);
  gap: 12px;
  align-items: start;
}

.work-detail__meta dt {
  color: var(--text-tertiary);
  font-size: 13px;
}

.work-detail__meta dd {
  min-width: 0;
  margin: 0;
  color: var(--text-primary);
  word-break: break-word;
}

.work-items h3 {
  margin: 0 0 12px;
  font-size: 16px;
}

.work-item-actions {
  display: flex;
  gap: 8px;
}

.work-media-preview {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.work-media-preview video,
.work-media-preview img,
.work-media-preview audio {
  display: block;
  max-width: 100%;
}

.work-media-preview video {
  width: 100%;
  max-height: 420px;
  background: #000;
}

.work-media-preview img {
  max-height: 520px;
  object-fit: contain;
}

.work-media-preview__hint {
  margin: 0;
  color: var(--text-tertiary);
  font-size: 12px;
}

@media (max-width: 768px) {
  .works-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .work-detail__meta div {
    grid-template-columns: 1fr;
    gap: 4px;
  }
}
</style>
