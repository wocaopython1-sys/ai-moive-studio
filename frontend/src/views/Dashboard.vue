<template>
  <section class="dashboard-page">
    <header class="dashboard-header">
      <div>
        <p class="dashboard-eyebrow">创作大厅</p>
        <h1>AICON AI 创作工作台</h1>
        <p class="dashboard-subtitle">
          图片、视频、Prompt、素材和任务都从这里开始。
        </p>
      </div>
      <div class="dashboard-header__actions">
        <input
          ref="uploadInput"
          class="hidden-upload"
          type="file"
          accept=".png,.jpg,.jpeg,.webp,.gif,.bmp,.mp4,.webm,.mov,image/*,video/mp4,video/webm,video/quicktime"
          @change="handleUploadChange"
        />
        <el-button :loading="refreshing" @click="loadDashboardData">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-button :loading="creating" type="primary" @click="createCanvas('blank')">
          <el-icon><Plus /></el-icon>
          新建 Canvas
        </el-button>
      </div>
    </header>

    <section class="quick-start-grid" aria-label="快速开始">
      <button
        v-for="action in quickActions"
        :key="action.key"
        class="quick-card"
        type="button"
        @click="action.run"
      >
        <span class="quick-card__icon">
          <el-icon><component :is="action.icon" /></el-icon>
        </span>
        <span class="quick-card__content">
          <strong>{{ action.title }}</strong>
          <small>{{ action.description }}</small>
        </span>
        <el-icon class="quick-card__arrow"><ArrowRight /></el-icon>
      </button>
    </section>

    <section class="stats-grid" aria-label="工作台概览">
      <article class="stat-card">
        <span>素材</span>
        <strong>{{ stats.assets }}</strong>
      </article>
      <article class="stat-card">
        <span>任务</span>
        <strong>{{ stats.tasks }}</strong>
      </article>
      <article class="stat-card">
        <span>失败任务</span>
        <strong>{{ stats.failedTasks }}</strong>
      </article>
      <article class="stat-card">
        <span>图片 / 视频</span>
        <strong>{{ stats.images }} / {{ stats.videos }}</strong>
      </article>
    </section>

    <main class="dashboard-content">
      <section class="dashboard-panel">
        <div class="panel-header">
          <div>
            <h2>最近 Canvas</h2>
            <p>继续编辑已有工作台，或新建一张画布。</p>
          </div>
          <el-button link @click="router.push('/canvas')">全部 Canvas</el-button>
        </div>

        <div v-if="loadingCanvas" class="panel-state">
          <el-skeleton :rows="3" animated />
        </div>
        <div v-else-if="!recentCanvas.length" class="panel-state">
          暂无 Canvas，先从新建 Canvas 开始。
        </div>
        <div v-else class="canvas-list">
          <button
            v-for="document in recentCanvas"
            :key="document.id"
            class="canvas-row"
            type="button"
            @click="openCanvas(document)"
          >
            <span>
              <strong>{{ document.title || '未命名 Canvas' }}</strong>
              <small>{{ document.description || '继续编辑节点、媒体和生成结果' }}</small>
            </span>
            <em>{{ formatTime(document.updated_at || document.created_at) }}</em>
          </button>
        </div>
      </section>

      <section class="dashboard-panel">
        <div class="panel-header">
          <div>
            <h2>最近素材</h2>
            <p>图片、视频和 Prompt 可以直接加入最近 Canvas。</p>
          </div>
          <el-button link @click="router.push('/library')">打开素材库</el-button>
        </div>

        <div v-if="loadingAssets" class="panel-state">
          <el-skeleton :rows="3" animated />
        </div>
        <div v-else-if="!recentAssets.length" class="panel-state">
          暂无素材。可以先上传一张图片或一个 MP4。
        </div>
        <div v-else class="asset-grid">
          <article
            v-for="asset in recentAssets"
            :key="asset.id || asset.object_key"
            class="asset-tile"
          >
            <div class="asset-preview">
              <img
                v-if="asset.media_type === 'image'"
                :src="asset.preview_url"
                :alt="assetTitle(asset)"
                loading="lazy"
              />
              <video
                v-else-if="asset.media_type === 'video'"
                :src="asset.stream_url || asset.preview_url"
                muted
                preload="metadata"
              />
              <pre v-else>{{ asset.summary || asset.text || assetTitle(asset) }}</pre>
            </div>
            <div class="asset-body">
              <strong>{{ assetTitle(asset) }}</strong>
              <span>{{ mediaTypeLabel(asset.media_type) }} · {{ sourceLabel(asset.source) }}</span>
              <div class="asset-actions">
                <button type="button" @click="previewAsset(asset)">预览</button>
                <button
                  v-if="asset.media_type !== 'text'"
                  type="button"
                  @click="downloadAsset(asset)"
                >
                  下载
                </button>
                <button type="button" @click="addAssetToCanvas(asset)">加入 Canvas</button>
              </div>
            </div>
          </article>
        </div>
      </section>

      <section class="dashboard-panel task-panel">
        <div class="panel-header">
          <div>
            <h2>最近任务</h2>
            <p>查看生成状态、失败原因，或回到对应 Canvas 节点。</p>
          </div>
          <el-button link @click="router.push('/tasks')">任务中心</el-button>
        </div>

        <div v-if="loadingTasks" class="panel-state">
          <el-skeleton :rows="3" animated />
        </div>
        <div v-else-if="!recentTasks.length" class="panel-state">
          暂无任务历史。
        </div>
        <div v-else class="task-list">
          <button
            v-for="task in recentTasks"
            :key="task.id"
            class="task-row"
            type="button"
            @click="openTask(task)"
          >
            <span class="task-kind">{{ typeLabel(task.type) }}</span>
            <span class="task-main">
              <strong>{{ task.title || '未命名任务' }}</strong>
              <small>{{ task.canvas_title || task.canvas_id || '未关联 Canvas' }}</small>
            </span>
            <span class="task-status" :data-status="task.status">
              {{ statusLabel(task.status) }}
            </span>
          </button>
        </div>
      </section>
    </main>
  </section>
</template>

<script setup>
import { computed, markRaw, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ArrowRight,
  Collection,
  MagicStick,
  Picture,
  Plus,
  Refresh,
  Share,
  Timer,
  Upload,
  VideoCamera,
  VideoPlay
} from '@element-plus/icons-vue'
import { canvasService } from '@/services/canvas'
import { taskHistoryService } from '@/services/taskHistory'
import { fileService } from '@/services/upload'

defineOptions({
  name: 'Dashboard'
})

const router = useRouter()
const uploadInput = ref(null)
const refreshing = ref(false)
const creating = ref(false)
const uploading = ref(false)
const loadingCanvas = ref(false)
const loadingAssets = ref(false)
const loadingTasks = ref(false)
const recentCanvas = ref([])
const recentAssets = ref([])
const recentTasks = ref([])
const assetTotal = ref(0)
const taskTotal = ref(0)

const quickActions = [
  {
    key: 'canvas',
    title: '新建 Canvas',
    description: '从空白工作台开始组织节点',
    icon: markRaw(Share),
    run: () => createCanvas('blank')
  },
  {
    key: 'image',
    title: '图片创作',
    description: '创建 Canvas，进入文生图流程',
    icon: markRaw(Picture),
    run: () => createCanvas('image')
  },
  {
    key: 'video',
    title: '视频创作',
    description: '创建 Canvas，进入文生视频流程',
    icon: markRaw(VideoPlay),
    run: () => createCanvas('video')
  },
  {
    key: 'i2v',
    title: '图生视频',
    description: '用图片节点作为参考生成视频',
    icon: markRaw(VideoCamera),
    run: () => createCanvas('i2v')
  },
  {
    key: 'assistant',
    title: 'Prompt / 分镜助手',
    description: '创建 Canvas，使用右侧助手整理创意',
    icon: markRaw(MagicStick),
    run: () => createCanvas('assistant')
  },
  {
    key: 'upload',
    title: '上传素材',
    description: uploading.value ? '正在上传...' : '上传 PNG / MP4 到素材库',
    icon: markRaw(Upload),
    run: () => triggerUpload()
  },
  {
    key: 'library',
    title: '打开素材库',
    description: '筛选、预览、下载和加入 Canvas',
    icon: markRaw(Collection),
    run: () => router.push('/library')
  },
  {
    key: 'tasks',
    title: '任务中心',
    description: '查看生成历史和失败原因',
    icon: markRaw(Timer),
    run: () => router.push('/tasks')
  }
]

const stats = computed(() => {
  const images = recentAssets.value.filter((asset) => asset.media_type === 'image').length
  const videos = recentAssets.value.filter((asset) => asset.media_type === 'video').length
  const failedTasks = recentTasks.value.filter((task) => task.status === 'failed').length
  return {
    assets: assetTotal.value || recentAssets.value.length,
    tasks: taskTotal.value || recentTasks.value.length,
    failedTasks,
    images,
    videos
  }
})

const createCanvas = async (mode = 'blank') => {
  creating.value = true
  try {
    const titleMap = {
      blank: '新建创作 Canvas',
      image: '图片创作 Canvas',
      video: '视频创作 Canvas',
      i2v: '图生视频 Canvas',
      assistant: 'Prompt 分镜 Canvas'
    }
    const response = await canvasService.create({
      title: `${titleMap[mode] || '新建 Canvas'} ${shortDateTime()}`,
      description: mode === 'blank'
        ? '从创作大厅创建'
        : `从创作大厅进入 ${titleMap[mode] || '创作'}`
    })
    ElMessage.success('Canvas 已创建')
    await router.push({
      name: 'CanvasEditor',
      params: { canvasId: response.id },
      query: mode === 'blank' ? {} : { mode }
    })
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || error?.message || '创建 Canvas 失败')
  } finally {
    creating.value = false
  }
}

const loadDashboardData = async () => {
  refreshing.value = true
  await Promise.allSettled([
    loadCanvas(),
    loadAssets(),
    loadTasks()
  ])
  refreshing.value = false
}

const loadCanvas = async () => {
  loadingCanvas.value = true
  try {
    const response = await canvasService.list({ page: 1, size: 6 })
    recentCanvas.value = response?.documents || []
  } catch (error) {
    recentCanvas.value = []
    console.warn('加载最近 Canvas 失败:', error)
  } finally {
    loadingCanvas.value = false
  }
}

const loadAssets = async () => {
  loadingAssets.value = true
  try {
    const response = await fileService.listLibrary({
      page: 1,
      size: 8,
      media_type: 'all',
      source: 'all'
    })
    const entries = response?.items || response?.files || []
    recentAssets.value = entries.map(normalizeAsset)
    assetTotal.value = Number(response?.total || entries.length || 0)
  } catch (error) {
    recentAssets.value = []
    assetTotal.value = 0
    console.warn('加载最近素材失败:', error)
  } finally {
    loadingAssets.value = false
  }
}

const loadTasks = async () => {
  loadingTasks.value = true
  try {
    const response = await taskHistoryService.list({ limit: 8, offset: 0 })
    recentTasks.value = response?.items || []
    taskTotal.value = Number(response?.total || recentTasks.value.length || 0)
  } catch (error) {
    recentTasks.value = []
    taskTotal.value = 0
    console.warn('加载最近任务失败:', error)
  } finally {
    loadingTasks.value = false
  }
}

const openCanvas = (document) => {
  if (!document?.id) return
  router.push({ name: 'CanvasEditor', params: { canvasId: document.id } })
}

const openTask = (task) => {
  if (task?.canvas_id && task?.canvas_item_id) {
    router.push({
      name: 'CanvasEditor',
      params: { canvasId: task.canvas_id },
      query: { item_id: task.canvas_item_id }
    })
    return
  }
  router.push('/tasks')
}

const triggerUpload = () => {
  uploadInput.value?.click()
}

const handleUploadChange = async (event) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return

  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    await fileService.uploadFile(formData)
    ElMessage.success('素材已上传')
    await loadAssets()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || error?.message || '上传素材失败')
  } finally {
    uploading.value = false
  }
}

const getRecentCanvas = async () => {
  if (recentCanvas.value[0]?.id) return recentCanvas.value[0]
  const response = await canvasService.list({ page: 1, size: 1 })
  if (response?.documents?.[0]?.id) return response.documents[0]
  return await canvasService.create({
    title: `素材导入 Canvas ${shortDateTime()}`,
    description: '从创作大厅自动创建'
  })
}

const addAssetToCanvas = async (asset) => {
  try {
    const canvas = await getRecentCanvas()
    const graph = await canvasService.getLite(canvas.id)
    const item = await canvasService.createItem(
      canvas.id,
      buildCanvasPayloadFromAsset(asset, graph?.items?.length || 0)
    )
    ElMessage.success('已加入最近 Canvas')
    await router.push({
      name: 'CanvasEditor',
      params: { canvasId: canvas.id },
      query: item?.id ? { item_id: item.id } : {}
    })
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || error?.message || '加入 Canvas 失败')
  }
}

const buildCanvasPayloadFromAsset = (asset, canvasItemCount = 0) => {
  const mediaType = asset.media_type || 'text'
  const offset = 100 + canvasItemCount * 32
  const title = assetTitle(asset)
  if (mediaType === 'image') {
    return {
      item_type: 'image',
      title,
      position_x: offset,
      position_y: offset,
      width: 360,
      height: 260,
      content: {
        result_image_object_key: asset.object_key,
        prompt: title,
        promptTokens: title ? [{ type: 'text', text: title }] : [],
        source_library_id: asset.id || asset.object_key
      },
      last_run_status: 'completed',
      last_output: { result_image_object_key: asset.object_key }
    }
  }
  if (mediaType === 'video') {
    return {
      item_type: 'video',
      title,
      position_x: offset,
      position_y: offset,
      width: 420,
      height: 260,
      content: {
        result_video_object_key: asset.object_key,
        prompt: title,
        promptTokens: title ? [{ type: 'text', text: title }] : [],
        source_library_id: asset.id || asset.object_key
      },
      last_run_status: 'completed',
      last_output: { result_video_object_key: asset.object_key }
    }
  }
  const text = String(asset.text || asset.summary || title).trim()
  return {
    item_type: 'text',
    title: title || 'Prompt 素材',
    position_x: offset,
    position_y: offset,
    width: 360,
    height: 220,
    content: {
      text,
      prompt: text,
      promptTokens: text ? [{ type: 'text', text }] : [],
      source_library_id: asset.id || asset.object_key,
      saved_to_library: true
    },
    last_run_status: 'completed',
    last_output: { text }
  }
}

const previewAsset = (asset) => {
  if (asset.media_type === 'text') {
    router.push('/library')
    return
  }
  const url = asset.media_type === 'video'
    ? asset.stream_url || asset.preview_url
    : asset.preview_url
  if (url) window.open(toAbsoluteUrl(url), '_blank', 'noopener,noreferrer')
}

const downloadAsset = (asset) => {
  const url = asset.download_url || asset.stream_url || asset.preview_url
  if (url) window.open(toAbsoluteUrl(url), '_blank', 'noopener,noreferrer')
}

const normalizeAsset = (asset = {}) => {
  const objectKey = String(asset.object_key || asset.storage_key || '').trim()
  const mediaType = String(asset.media_type || '').trim() || mediaTypeFromObjectKey(objectKey) || 'text'
  return {
    ...asset,
    id: asset.id || objectKey,
    object_key: objectKey,
    media_type: mediaType,
    filename: asset.filename || asset.title || objectKey.split('/').pop() || '素材',
    title: asset.title || asset.filename || '',
    preview_url: asset.preview_url || (objectKey && mediaType !== 'text' ? mediaPathForObjectKey(objectKey, 'preview') : ''),
    download_url: asset.download_url || (objectKey && mediaType !== 'text' ? mediaPathForObjectKey(objectKey, 'download') : ''),
    stream_url: asset.stream_url || (mediaType === 'video' && objectKey ? mediaPathForObjectKey(objectKey, 'stream') : '')
  }
}

const mediaTypeFromObjectKey = (objectKey = '') => {
  const suffix = String(objectKey || '').split('?')[0].split('.').pop()?.toLowerCase()
  if (['png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp'].includes(suffix)) return 'image'
  if (['mp4', 'webm', 'mov'].includes(suffix)) return 'video'
  return ''
}

const mediaPathForObjectKey = (objectKey = '', mode = 'preview') => {
  const cleanKey = String(objectKey || '').trim().replace(/^\/+/, '')
  return cleanKey ? `/api/v1/media/${mode}/${cleanKey}` : ''
}

const toAbsoluteUrl = (url = '') => {
  const value = String(url || '').trim()
  if (!value) return ''
  if (/^https?:\/\//i.test(value)) return value
  return `${window.location.origin}${value.startsWith('/') ? value : `/${value}`}`
}

const assetTitle = (asset = {}) =>
  String(asset.title || asset.filename || asset.summary || asset.object_key || '素材').trim()

const mediaTypeLabel = (type = '') => {
  if (type === 'image') return '图片'
  if (type === 'video') return '视频'
  if (type === 'text') return '文本/Prompt'
  return '素材'
}

const sourceLabel = (source = '') => {
  if (source === 'canvas') return 'Canvas'
  if (source === 'generated') return '生成结果'
  if (source === 'upload') return '上传'
  return '未知'
}

const typeLabel = (type = '') =>
  ({
    image: '图片',
    video: '视频',
    text: '文本',
    assistant: '助手'
  })[type] || type || '任务'

const statusLabel = (status = '') =>
  ({
    pending: '排队中',
    processing: '处理中',
    completed: '已完成',
    failed: '失败'
  })[status] || status || '未知'

const formatTime = (value = '') => {
  if (!value) return '刚刚'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  }).format(date)
}

const shortDateTime = () =>
  new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).format(new Date())

onMounted(loadDashboardData)
</script>

<style scoped>
.dashboard-page {
  min-height: 100%;
  padding: 24px;
  background: var(--bg-primary);
}

.dashboard-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  margin: 0 auto 18px;
  max-width: 1480px;
}

.dashboard-eyebrow {
  margin: 0 0 6px;
  color: var(--primary-color);
  font-size: 12px;
  font-weight: 800;
}

.dashboard-header h1 {
  margin: 0;
  color: var(--text-primary);
  font-size: 28px;
  line-height: 1.2;
}

.dashboard-subtitle {
  margin: 8px 0 0;
  color: var(--text-secondary);
  font-size: 14px;
}

.dashboard-header__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}

.hidden-upload {
  display: none;
}

.quick-start-grid,
.stats-grid,
.dashboard-content {
  max-width: 1480px;
  margin-right: auto;
  margin-left: auto;
}

.quick-start-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.quick-card,
.canvas-row,
.task-row,
.asset-actions button {
  border: 1px solid var(--border-primary);
  border-radius: 8px;
  background: var(--bg-secondary);
  color: var(--text-primary);
  cursor: pointer;
}

.quick-card {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr) 18px;
  align-items: center;
  gap: 12px;
  min-height: 86px;
  padding: 14px;
  text-align: left;
  transition: border-color 0.18s ease, transform 0.18s ease, box-shadow 0.18s ease;
}

.quick-card:hover {
  transform: translateY(-2px);
  border-color: var(--primary-color);
  box-shadow: 0 12px 24px rgba(31, 49, 88, 0.08);
}

.quick-card__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  border-radius: 8px;
  background: #eef3ff;
  color: var(--primary-color);
  font-size: 20px;
}

.quick-card__content {
  min-width: 0;
}

.quick-card__content strong,
.asset-body strong,
.canvas-row strong,
.task-main strong {
  display: block;
  overflow: hidden;
  color: var(--text-primary);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.quick-card__content small,
.canvas-row small,
.task-main small {
  display: block;
  margin-top: 4px;
  overflow: hidden;
  color: var(--text-secondary);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.quick-card__arrow {
  color: var(--text-tertiary);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.stat-card {
  min-height: 74px;
  padding: 14px;
  border: 1px solid var(--border-primary);
  border-radius: 8px;
  background: var(--bg-secondary);
}

.stat-card span {
  color: var(--text-secondary);
  font-size: 12px;
}

.stat-card strong {
  display: block;
  margin-top: 6px;
  color: var(--text-primary);
  font-size: 24px;
  line-height: 1;
}

.dashboard-content {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr);
  gap: 16px;
  align-items: start;
}

.dashboard-panel {
  min-width: 0;
  padding: 16px;
  border: 1px solid var(--border-primary);
  border-radius: 8px;
  background: var(--bg-secondary);
}

.task-panel {
  grid-column: 1 / -1;
}

.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.panel-header h2 {
  margin: 0;
  color: var(--text-primary);
  font-size: 18px;
}

.panel-header p {
  margin: 5px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
}

.panel-state {
  padding: 24px;
  border: 1px dashed var(--border-primary);
  border-radius: 8px;
  color: var(--text-secondary);
  text-align: center;
}

.canvas-list,
.task-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.canvas-row,
.task-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 64px;
  padding: 12px;
  text-align: left;
}

.canvas-row span,
.task-main {
  min-width: 0;
  flex: 1;
}

.canvas-row em {
  flex-shrink: 0;
  color: var(--text-tertiary);
  font-size: 12px;
  font-style: normal;
}

.asset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
  gap: 12px;
}

.asset-tile {
  min-width: 0;
  overflow: hidden;
  border: 1px solid var(--border-primary);
  border-radius: 8px;
  background: #fff;
}

.asset-preview {
  height: 132px;
  overflow: hidden;
  background: #eef2f6;
}

.asset-preview img,
.asset-preview video {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.asset-preview pre {
  height: 100%;
  margin: 0;
  padding: 12px;
  overflow: hidden;
  color: var(--text-primary);
  font-family: inherit;
  font-size: 13px;
  line-height: 1.55;
  white-space: pre-wrap;
}

.asset-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
}

.asset-body span {
  color: var(--text-secondary);
  font-size: 12px;
}

.asset-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.asset-actions button {
  min-height: 30px;
  padding: 0 10px;
  font-size: 12px;
  font-weight: 700;
}

.asset-actions button:last-child {
  border-color: var(--primary-color);
  background: var(--primary-color);
  color: white;
}

.task-kind {
  width: 58px;
  flex-shrink: 0;
  color: var(--primary-color);
  font-size: 12px;
  font-weight: 800;
}

.task-status {
  flex-shrink: 0;
  min-width: 66px;
  padding: 5px 8px;
  border-radius: 8px;
  background: #eef2f6;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 800;
  text-align: center;
}

.task-status[data-status='completed'] {
  background: #e8f7ee;
  color: #227447;
}

.task-status[data-status='processing'],
.task-status[data-status='pending'] {
  background: #fff5dc;
  color: #8a5b00;
}

.task-status[data-status='failed'] {
  background: #ffecec;
  color: #b72d2d;
}

@media (max-width: 1100px) {
  .dashboard-content,
  .stats-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .dashboard-page {
    padding: 16px;
  }

  .dashboard-header {
    flex-direction: column;
  }

  .dashboard-header__actions {
    justify-content: flex-start;
    width: 100%;
  }
}
</style>
