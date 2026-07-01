<template>
  <div class="tasks-page">
    <header class="tasks-header">
      <div>
        <h1>任务中心</h1>
        <p>查看 Canvas 生成历史、任务状态和失败原因。</p>
      </div>
      <div class="tasks-header__actions">
        <el-button :loading="loading" @click="loadTasks">刷新</el-button>
      </div>
    </header>

    <section class="tasks-filters">
      <button
        v-for="filter in typeFilters"
        :key="filter.value"
        type="button"
        :class="{ active: filters.type === filter.value }"
        @click="setType(filter.value)"
      >
        {{ filter.label }}
      </button>
      <span class="tasks-filters__divider"></span>
      <button
        v-for="filter in statusFilters"
        :key="filter.value"
        type="button"
        :class="{ active: filters.status === filter.value }"
        @click="setStatus(filter.value)"
      >
        {{ filter.label }}
      </button>
    </section>

    <section v-if="loading" class="tasks-state">正在加载任务历史...</section>
    <section v-else-if="!tasks.length" class="tasks-state">暂无任务记录</section>

    <section v-else class="tasks-list" data-testid="tasks-history-list">
      <article
        v-for="task in tasks"
        :key="task.id"
        class="task-card"
        :data-task-type="task.type"
        :data-task-status="task.status"
      >
        <div class="task-card__preview">
          <img
            v-if="task.type === 'image' && task.preview_url"
            :src="task.preview_url"
            :alt="task.title"
            loading="lazy"
          />
          <video
            v-else-if="task.type === 'video' && (task.stream_url || task.preview_url)"
            :src="task.stream_url || task.preview_url"
            preload="metadata"
            muted
          ></video>
          <span v-else>{{ typeLabel(task.type) }}</span>
        </div>

        <div class="task-card__body">
          <div class="task-card__topline">
            <span class="task-type">{{ typeLabel(task.type) }}</span>
            <span class="task-status" :data-status="task.status">
              {{ statusLabel(task.status) }}
            </span>
          </div>
          <h2>{{ task.title || '未命名任务' }}</h2>
          <p class="task-meta">
            <span>{{ task.canvas_title || task.canvas_id }}</span>
            <span v-if="task.provider">Provider：{{ task.provider }}</span>
            <span v-if="task.model">模型：{{ task.model }}</span>
            <span v-if="formatTaskParams(task)">参数：{{ formatTaskParams(task) }}</span>
            <span v-if="task.result_summary">结果：{{ task.result_summary }}</span>
            <span>{{ formatTime(task.updated_at || task.created_at) }}</span>
          </p>
          <p v-if="task.error_message" class="task-error">
            {{ task.error_message }}
          </p>
          <p v-else-if="task.status === 'failed'" class="task-error">
            任务失败，但没有返回具体原因。
          </p>

          <div class="task-card__actions">
            <el-button size="small" @click="openDetail(task)">查看</el-button>
            <el-button size="small" @click="jumpToCanvas(task)">跳转 Canvas 节点</el-button>
            <el-button
              v-if="task.preview_url || task.stream_url"
              size="small"
              @click="openMedia(task)"
            >
              预览
            </el-button>
            <el-button
              v-if="task.download_url"
              size="small"
              @click="downloadMedia(task)"
            >
              下载
            </el-button>
            <el-button
              v-if="task.preview_url || task.stream_url || task.download_url"
              size="small"
              @click="copyTaskUrl(task)"
            >
              复制 URL
            </el-button>
            <el-button
              v-if="task.status === 'failed'"
              size="small"
              type="warning"
              @click="retryTask(task)"
            >
              回到节点重试
            </el-button>
          </div>
        </div>
      </article>
    </section>

    <el-dialog v-model="detailVisible" title="任务详情" width="720px">
      <pre class="task-detail-json">{{ prettyDetail }}</pre>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { taskHistoryService } from '@/services/taskHistory'

const route = useRoute()
const router = useRouter()

const tasks = ref([])
const total = ref(0)
const loading = ref(false)
const detailVisible = ref(false)
const selectedDetail = ref(null)

const filters = reactive({
  type: String(route.query.type || ''),
  status: String(route.query.status || ''),
  canvasId: String(route.query.canvas_id || '')
})

const typeFilters = [
  { label: '全部', value: '' },
  { label: '图片', value: 'image' },
  { label: '视频', value: 'video' },
  { label: '文本', value: 'text' },
  { label: '助手', value: 'assistant' }
]

const statusFilters = [
  { label: '全部状态', value: '' },
  { label: '已完成', value: 'completed' },
  { label: '处理中', value: 'processing' },
  { label: '失败', value: 'failed' }
]

const prettyDetail = computed(() =>
  JSON.stringify(selectedDetail.value || {}, null, 2)
)

const absoluteUrl = (url = '') => {
  const value = String(url || '').trim()
  if (!value) return ''
  if (/^https?:\/\//i.test(value)) return value
  return `${window.location.origin}${value.startsWith('/') ? value : `/${value}`}`
}

const loadTasks = async () => {
  loading.value = true
  try {
    const params = {
      limit: 100,
      offset: 0
    }
    if (filters.type) params.type = filters.type
    if (filters.status) params.status = filters.status
    if (filters.canvasId) params.canvas_id = filters.canvasId
    const response = await taskHistoryService.list(params)
    tasks.value = response.items || []
    total.value = response.total || 0
  } finally {
    loading.value = false
  }
}

const syncRouteQuery = () => {
  const query = {}
  if (filters.type) query.type = filters.type
  if (filters.status) query.status = filters.status
  if (filters.canvasId) query.canvas_id = filters.canvasId
  router.replace({ name: 'TasksHistoryPage', query })
}

const setType = (type) => {
  filters.type = type
  syncRouteQuery()
  void loadTasks()
}

const setStatus = (status) => {
  filters.status = status
  syncRouteQuery()
  void loadTasks()
}

const typeLabel = (type) =>
  ({
    image: '图片',
    video: '视频',
    text: '文本',
    assistant: '助手'
  })[type] || type || '任务'

const statusLabel = (status) =>
  ({
    pending: '排队中',
    processing: '处理中',
    completed: '已完成',
    failed: '失败'
  })[status] || status || '未知'

const formatTime = (value) => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

const formatTaskParams = (task) => {
  const params = task?.params || task?.request_payload?.options || {}
  if (!params || typeof params !== 'object') return ''
  const parts = []
  const size = params.image_size || params.size
  const ratio = params.aspect_ratio
  const count = params.n
  const duration = params.duration || params.duration_seconds
  if (size) parts.push(`尺寸 ${size}`)
  if (ratio) parts.push(`比例 ${ratio}`)
  if (count) parts.push(`数量 ${count}`)
  if (duration) parts.push(`时长 ${duration}s`)
  if (params.reference_images) parts.push(`参考图 ${params.reference_images}`)
  return parts.join(' / ')
}

const openDetail = async (task) => {
  selectedDetail.value = await taskHistoryService.detail(task.id)
  detailVisible.value = true
}

const jumpToCanvas = (task) => {
  if (!task.canvas_id || !task.canvas_item_id) {
    ElMessage.warning('该任务没有关联 Canvas 节点')
    return
  }
  router.push({
    name: 'CanvasEditor',
    params: { canvasId: task.canvas_id },
    query: { item_id: task.canvas_item_id }
  })
}

const openMedia = (task) => {
  const url = absoluteUrl(task.stream_url || task.preview_url)
  if (!url) return
  window.open(url, '_blank', 'noopener,noreferrer')
}

const downloadMedia = (task) => {
  const url = absoluteUrl(task.download_url)
  if (!url) return
  const link = document.createElement('a')
  link.href = url
  link.download = ''
  document.body.appendChild(link)
  link.click()
  link.remove()
}

const copyTaskUrl = async (task) => {
  const url = absoluteUrl(task.stream_url || task.preview_url || task.download_url)
  if (!url) return
  try {
    await navigator.clipboard.writeText(url)
    ElMessage.success('URL 已复制')
  } catch {
    ElMessage.warning(url)
  }
}

const retryTask = (task) => {
  ElMessage.info('当前阶段请回到对应 Canvas 节点重新生成')
  jumpToCanvas(task)
}

watch(
  () => route.query.canvas_id,
  (value) => {
    filters.canvasId = String(value || '')
    void loadTasks()
  }
)

onMounted(loadTasks)
</script>

<style scoped>
.tasks-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 24px;
}

.tasks-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.tasks-header h1 {
  margin: 0;
  color: #1d2b46;
  font-size: 24px;
  line-height: 1.25;
}

.tasks-header p {
  margin: 6px 0 0;
  color: #6b7894;
}

.tasks-filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.tasks-filters button {
  min-height: 34px;
  padding: 0 13px;
  border: 1px solid rgba(31, 49, 88, 0.12);
  border-radius: 8px;
  background: #fff;
  color: #304260;
  cursor: pointer;
}

.tasks-filters button.active {
  border-color: #2f68ff;
  background: #edf3ff;
  color: #1c55e6;
  font-weight: 700;
}

.tasks-filters__divider {
  width: 1px;
  height: 24px;
  background: rgba(31, 49, 88, 0.12);
}

.tasks-state {
  padding: 32px;
  border: 1px dashed rgba(31, 49, 88, 0.16);
  border-radius: 8px;
  color: #6b7894;
  text-align: center;
}

.tasks-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-card {
  display: grid;
  grid-template-columns: 132px minmax(0, 1fr);
  gap: 16px;
  padding: 14px;
  border: 1px solid rgba(31, 49, 88, 0.1);
  border-radius: 8px;
  background: #fff;
}

.task-card__preview {
  min-height: 96px;
  display: grid;
  place-items: center;
  overflow: hidden;
  border-radius: 8px;
  background: #eef2f7;
  color: #61708e;
  font-weight: 700;
}

.task-card__preview img,
.task-card__preview video {
  width: 100%;
  height: 100%;
  min-height: 96px;
  object-fit: cover;
}

.task-card__body {
  min-width: 0;
}

.task-card__topline,
.task-meta,
.task-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.task-type,
.task-status {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.task-type {
  background: #eef2f7;
  color: #304260;
}

.task-status {
  background: #edf3ff;
  color: #1c55e6;
}

.task-status[data-status='failed'] {
  background: #fff0f0;
  color: #c03535;
}

.task-status[data-status='completed'] {
  background: #eefaf3;
  color: #1e824c;
}

.task-card h2 {
  margin: 8px 0 6px;
  color: #1d2b46;
  font-size: 16px;
}

.task-meta {
  color: #71809c;
  font-size: 12px;
}

.task-error {
  margin: 8px 0 0;
  padding: 8px 10px;
  border-radius: 8px;
  background: #fff5f5;
  color: #a53a3a;
  font-size: 13px;
}

.task-card__actions {
  margin-top: 12px;
}

.task-detail-json {
  max-height: 60vh;
  overflow: auto;
  padding: 12px;
  border-radius: 8px;
  background: #0f172a;
  color: #dbeafe;
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 720px) {
  .tasks-page {
    padding: 16px;
  }

  .task-card {
    grid-template-columns: 1fr;
  }
}
</style>
