<template>
  <section class="assets-library-page">
    <header class="assets-library-header">
      <div>
        <h1>素材库</h1>
        <p>图片、视频、Prompt 与生成结果的轻量工作台入口</p>
      </div>
      <button
        class="assets-library-refresh"
        type="button"
        :disabled="loading"
        data-testid="assets-refresh"
        @click="loadAssets"
      >
        刷新
      </button>
    </header>

    <div class="assets-library-toolbar">
      <el-input
        v-model="searchText"
        class="assets-search"
        clearable
        placeholder="搜索文件名、Prompt、object_key"
        data-testid="assets-search"
        @keyup.enter="loadAssets"
        @clear="loadAssets"
      />
      <div class="assets-segmented" data-testid="assets-type-filter">
        <button
          v-for="option in typeOptions"
          :key="option.value"
          type="button"
          :class="{ active: typeFilter === option.value }"
          @click="typeFilter = option.value"
        >
          {{ option.label }}
        </button>
      </div>
      <div class="assets-segmented" data-testid="assets-source-filter">
        <button
          v-for="option in sourceOptions"
          :key="option.value"
          type="button"
          :class="{ active: sourceFilter === option.value }"
          @click="sourceFilter = option.value"
        >
          {{ option.label }}
        </button>
      </div>
    </div>

    <div class="assets-library-meta">
      <span>{{ total }} 个素材</span>
      <span v-if="loading">正在加载...</span>
      <span v-else-if="selectedAsset">已选中：{{ assetTitle(selectedAsset) }}</span>
    </div>

    <div v-if="loading" class="assets-state">正在加载素材...</div>
    <div v-else-if="!assets.length" class="assets-state">暂无匹配素材</div>
    <div v-else class="assets-library-shell">
      <main class="assets-grid" data-testid="assets-grid">
        <article
          v-for="asset in assets"
          :key="asset.id || asset.object_key"
          class="asset-card"
          :class="{ selected: selectedAssetId === (asset.id || asset.object_key) }"
          :data-media-type="asset.media_type"
          @click="selectAsset(asset)"
        >
          <div class="asset-card__preview">
            <img
              v-if="asset.media_type === 'image'"
              :src="asset.preview_url"
              :alt="assetTitle(asset)"
              loading="lazy"
              draggable="false"
            />
            <video
              v-else-if="asset.media_type === 'video'"
              :src="asset.stream_url || asset.preview_url"
              controls
              playsinline
              preload="metadata"
            />
            <div v-else class="asset-card__text-preview">
              {{ asset.summary || asset.text || '文本素材' }}
            </div>
          </div>
          <div class="asset-card__body">
            <div class="asset-card__title">{{ assetTitle(asset) }}</div>
            <div class="asset-card__meta">
              <span class="asset-label" :data-tone="asset.labels.typeTone">
                {{ asset.labels.typeLabel }}
              </span>
              <span class="asset-label" :data-tone="asset.labels.sourceTone">
                {{ asset.labels.sourceLabel }}
              </span>
              <span
                v-if="asset.labels.finalLabel"
                class="asset-label"
                data-tone="final"
              >
                {{ asset.labels.finalLabel }}
              </span>
              <span v-if="asset.size_mb">{{ asset.size_mb }} MB</span>
            </div>
            <div class="asset-card__actions">
              <button type="button" @click.stop="previewAsset(asset)">预览</button>
              <button
                v-if="asset.media_type !== 'text'"
                type="button"
                @click.stop="downloadAsset(asset)"
              >
                下载
              </button>
              <button type="button" @click.stop="copyAssetUrl(asset)">复制 URL</button>
              <button class="primary" type="button" @click.stop="addAssetToCanvas(asset)">
                加入 Canvas
              </button>
            </div>
          </div>
        </article>
      </main>

      <aside class="asset-detail" data-testid="asset-detail">
        <template v-if="selectedAsset">
          <div class="asset-detail__head">
            <div class="asset-detail__labels">
              <span class="asset-label" :data-tone="selectedAsset.labels.typeTone">
                {{ selectedAsset.labels.typeLabel }}
              </span>
              <span class="asset-label" :data-tone="selectedAsset.labels.sourceTone">
                {{ selectedAsset.labels.sourceLabel }}
              </span>
            </div>
            <strong>{{ assetTitle(selectedAsset) }}</strong>
          </div>
          <div class="asset-detail__preview">
            <img
              v-if="selectedAsset.media_type === 'image'"
              :src="selectedAsset.preview_url"
              :alt="assetTitle(selectedAsset)"
            />
            <video
              v-else-if="selectedAsset.media_type === 'video'"
              :src="selectedAsset.stream_url || selectedAsset.preview_url"
              controls
              playsinline
            />
            <pre v-else>{{ selectedAsset.text || selectedAsset.summary }}</pre>
          </div>
          <dl class="asset-detail__meta">
            <div>
              <dt>来源</dt>
              <dd>{{ selectedAsset.labels.sourceLabel }}</dd>
            </div>
            <div v-if="selectedAsset.last_modified">
              <dt>时间</dt>
              <dd>{{ formatDate(selectedAsset.last_modified) }}</dd>
            </div>
            <div v-if="selectedAsset.object_key">
              <dt>对象</dt>
              <dd>{{ selectedAsset.object_key }}</dd>
            </div>
            <div v-if="selectedAsset.canvas_id">
              <dt>Canvas</dt>
              <dd>
                <button type="button" class="link-button" @click="openSourceCanvas(selectedAsset)">
                  跳转来源节点
                </button>
              </dd>
            </div>
          </dl>
        </template>
        <div v-else class="asset-detail__empty">选择一个素材查看详情</div>
      </aside>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { canvasService } from '@/services/canvas'
import { fileService } from '@/services/upload'
import { buildAssetLibraryLabels } from '@/utils/assetLibraryLabels'

const router = useRouter()
const loading = ref(false)
const assets = ref([])
const total = ref(0)
const selectedAssetId = ref('')
const searchText = ref('')
const typeFilter = ref('all')
const sourceFilter = ref('all')

const typeOptions = [
  { label: '全部', value: 'all' },
  { label: '图片', value: 'image' },
  { label: '视频', value: 'video' },
  { label: '文本/Prompt', value: 'text' }
]

const sourceOptions = [
  { label: '全部来源', value: 'all' },
  { label: '上传', value: 'upload' },
  { label: '生成结果', value: 'generated' },
  { label: 'Canvas', value: 'canvas' }
]

const selectedAsset = computed(
  () => assets.value.find((asset) => (asset.id || asset.object_key) === selectedAssetId.value) || null
)

const normalizeAsset = (asset = {}) => {
  const objectKey = String(asset.object_key || asset.storage_key || '').trim()
  const mediaType = String(asset.media_type || '').trim() || mediaTypeFromObjectKey(objectKey) || 'text'
  const normalized = {
    ...asset,
    object_key: objectKey,
    media_type: mediaType
  }
  const labels = buildAssetLibraryLabels(normalized)
  return {
    ...normalized,
    id: asset.id || objectKey,
    filename: asset.filename || asset.title || objectKey.split('/').pop() || '素材',
    title: asset.title || asset.filename || '',
    preview_url: asset.preview_url || (objectKey && mediaType !== 'text' ? mediaPathForObjectKey(objectKey, 'preview') : ''),
    download_url: asset.download_url || (objectKey && mediaType !== 'text' ? mediaPathForObjectKey(objectKey, 'download') : ''),
    stream_url: asset.stream_url || (mediaType === 'video' && objectKey ? mediaPathForObjectKey(objectKey, 'stream') : ''),
    labels
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

const formatDate = (value = '') => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString()
}

const loadAssets = async () => {
  loading.value = true
  try {
    const response = await fileService.listLibrary({
      page: 1,
      size: 100,
      media_type: typeFilter.value,
      source: sourceFilter.value,
      q: searchText.value || undefined
    })
    const entries = response?.items || response?.files || []
    assets.value = entries.map(normalizeAsset)
    total.value = Number(response?.total || assets.value.length || 0)
    if (!assets.value.some((asset) => (asset.id || asset.object_key) === selectedAssetId.value)) {
      selectedAssetId.value = assets.value[0]?.id || assets.value[0]?.object_key || ''
    }
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || error?.message || '加载素材库失败')
  } finally {
    loading.value = false
  }
}

const selectAsset = (asset) => {
  selectedAssetId.value = asset.id || asset.object_key
}

const previewAsset = (asset) => {
  selectAsset(asset)
  if (asset.media_type === 'text') return
  const url = asset.media_type === 'video'
    ? asset.stream_url || asset.preview_url
    : asset.preview_url
  if (url) {
    window.open(toAbsoluteUrl(url), '_blank', 'noopener,noreferrer')
  }
}

const downloadAsset = (asset) => {
  const url = asset.download_url || asset.preview_url || asset.stream_url
  if (!url) {
    ElMessage.warning('没有可下载的 URL')
    return
  }
  window.open(toAbsoluteUrl(url), '_blank', 'noopener,noreferrer')
}

const copyAssetUrl = async (asset) => {
  const url =
    asset.media_type === 'video'
      ? asset.stream_url || asset.preview_url || asset.download_url
      : asset.preview_url || asset.download_url
  const text = asset.media_type === 'text'
    ? asset.text || asset.summary || assetTitle(asset)
    : toAbsoluteUrl(url)
  if (!text) {
    ElMessage.warning('没有可复制的内容')
    return
  }
  if (navigator.clipboard?.writeText && window.isSecureContext) {
    await navigator.clipboard.writeText(text)
  } else {
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.setAttribute('readonly', 'readonly')
    textarea.style.position = 'fixed'
    textarea.style.left = '-9999px'
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
  }
  ElMessage.success(asset.media_type === 'text' ? '文本已复制' : '素材 URL 已复制')
}

const getRecentCanvas = async () => {
  const response = await canvasService.list({ page: 1, size: 1 })
  const canvas = response?.documents?.[0]
  if (canvas?.id) return canvas
  return await canvasService.create({
    title: `素材库导入 ${new Date().toLocaleString()}`,
    description: '阶段 1C 自动创建的素材导入画布'
  })
}

const buildCanvasPayloadFromAsset = (asset, canvasItemCount = 0) => {
  const mediaType = asset.media_type || 'text'
  const offset = 80 + canvasItemCount * 28
  if (mediaType === 'image') {
    return {
      item_type: 'image',
      title: assetTitle(asset),
      position_x: offset,
      position_y: offset,
      width: 360,
      height: 260,
      content: {
        result_image_object_key: asset.object_key,
        prompt: asset.filename || asset.title || '',
        promptTokens: assetTitle(asset) ? [{ type: 'text', text: assetTitle(asset) }] : [],
        source_library_id: asset.id || asset.object_key
      },
      last_run_status: 'completed',
      last_output: { result_image_object_key: asset.object_key }
    }
  }
  if (mediaType === 'video') {
    return {
      item_type: 'video',
      title: assetTitle(asset),
      position_x: offset,
      position_y: offset,
      width: 420,
      height: 260,
      content: {
        result_video_object_key: asset.object_key,
        prompt: asset.filename || asset.title || '',
        promptTokens: assetTitle(asset) ? [{ type: 'text', text: assetTitle(asset) }] : [],
        source_library_id: asset.id || asset.object_key
      },
      last_run_status: 'completed',
      last_output: { result_video_object_key: asset.object_key }
    }
  }
  const text = String(asset.text || asset.summary || assetTitle(asset)).trim()
  return {
    item_type: 'text',
    title: assetTitle(asset) || 'Prompt 素材',
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

const addAssetToCanvas = async (asset) => {
  try {
    const canvas = await getRecentCanvas()
    const graph = await canvasService.getLite(canvas.id)
    const payload = buildCanvasPayloadFromAsset(asset, graph?.items?.length || 0)
    const item = await canvasService.createItem(canvas.id, payload)
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

const openSourceCanvas = (asset) => {
  if (!asset?.canvas_id) return
  router.push({
    name: 'CanvasEditor',
    params: { canvasId: asset.canvas_id },
    query: asset.canvas_item_id ? { item_id: asset.canvas_item_id } : {}
  })
}

watch([typeFilter, sourceFilter], () => {
  void loadAssets()
})

onMounted(loadAssets)
</script>

<style scoped>
.assets-library-page {
  min-height: 100%;
  padding: 24px;
  background: var(--bg-primary);
}

.assets-library-header,
.assets-library-toolbar,
.assets-library-meta {
  max-width: 1480px;
  margin: 0 auto;
}

.assets-library-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
}

.assets-library-header h1 {
  margin: 0;
  color: var(--text-primary);
  font-size: 28px;
  line-height: 1.25;
}

.assets-library-header p,
.assets-library-meta {
  color: var(--text-secondary);
  font-size: 13px;
}

.assets-library-refresh,
.asset-card__actions button,
.link-button {
  min-height: 32px;
  border: 1px solid var(--border-primary);
  border-radius: 8px;
  background: var(--bg-secondary);
  color: var(--text-primary);
  cursor: pointer;
  font-weight: 700;
}

.assets-library-refresh {
  padding: 0 14px;
}

.assets-library-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-top: 18px;
}

.assets-search {
  width: min(420px, 100%);
}

.assets-segmented {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding: 4px;
  border: 1px solid var(--border-primary);
  border-radius: 8px;
  background: var(--bg-secondary);
}

.assets-segmented button {
  min-height: 30px;
  padding: 0 11px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 12px;
  font-weight: 800;
}

.assets-segmented button.active {
  background: var(--primary-color);
  color: white;
}

.assets-library-meta {
  display: flex;
  gap: 12px;
  margin-top: 12px;
}

.assets-library-shell {
  max-width: 1480px;
  margin: 18px auto 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: 18px;
  align-items: start;
}

.assets-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 14px;
}

.asset-card {
  min-width: 0;
  overflow: hidden;
  border: 1px solid var(--border-primary);
  border-radius: 8px;
  background: var(--bg-secondary);
  cursor: pointer;
}

.asset-card.selected {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.14);
}

.asset-card__preview {
  height: 164px;
  overflow: hidden;
  background: #eef2f6;
}

.asset-card__preview img,
.asset-card__preview video {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.asset-card__text-preview {
  height: 100%;
  padding: 14px;
  overflow: hidden;
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.55;
  white-space: pre-wrap;
}

.asset-card__body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
}

.asset-card__title {
  min-height: 36px;
  overflow: hidden;
  color: var(--text-primary);
  font-weight: 800;
  font-size: 13px;
  line-height: 1.35;
  word-break: break-word;
}

.asset-card__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  color: var(--text-secondary);
  font-size: 12px;
}

.asset-label {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 0 8px;
  border: 1px solid var(--border-primary);
  border-radius: 999px;
  background: var(--bg-primary);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
}

.asset-label[data-tone="image"] {
  border-color: rgba(34, 197, 94, 0.35);
  color: #15803d;
}

.asset-label[data-tone="video"] {
  border-color: rgba(59, 130, 246, 0.35);
  color: #1d4ed8;
}

.asset-label[data-tone="text"] {
  border-color: rgba(168, 85, 247, 0.35);
  color: #7e22ce;
}

.asset-label[data-tone="canvas"] {
  border-color: rgba(14, 165, 233, 0.35);
  color: #0369a1;
}

.asset-label[data-tone="unknown"] {
  border-color: rgba(100, 116, 139, 0.28);
  color: #64748b;
}

.asset-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.asset-card__actions button {
  padding: 0 10px;
  font-size: 12px;
}

.asset-card__actions .primary {
  border-color: var(--primary-color);
  background: var(--primary-color);
  color: white;
}

.asset-detail {
  position: sticky;
  top: 18px;
  border: 1px solid var(--border-primary);
  border-radius: 8px;
  background: var(--bg-secondary);
}

.asset-detail__head {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px;
  border-bottom: 1px solid var(--border-primary);
}

.asset-detail__labels {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.asset-detail__head strong {
  color: var(--text-primary);
  font-size: 15px;
  line-height: 1.35;
  word-break: break-word;
}

.asset-detail__preview {
  max-height: 360px;
  overflow: auto;
  border-bottom: 1px solid var(--border-primary);
  background: #f6f8fb;
}

.asset-detail__preview img,
.asset-detail__preview video {
  display: block;
  width: 100%;
}

.asset-detail__preview pre {
  margin: 0;
  padding: 14px;
  color: var(--text-primary);
  font-family: inherit;
  font-size: 13px;
  line-height: 1.55;
  white-space: pre-wrap;
}

.asset-detail__meta {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 0;
  padding: 14px;
}

.asset-detail__meta div {
  min-width: 0;
}

.asset-detail__meta dt {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 800;
}

.asset-detail__meta dd {
  margin: 3px 0 0;
  color: var(--text-primary);
  font-size: 12px;
  line-height: 1.45;
  word-break: break-all;
}

.link-button {
  padding: 0 10px;
  color: var(--primary-color);
}

.assets-state,
.asset-detail__empty {
  padding: 28px;
  color: var(--text-secondary);
  text-align: center;
}

@media (max-width: 1080px) {
  .assets-library-shell {
    grid-template-columns: 1fr;
  }

  .asset-detail {
    position: static;
  }
}
</style>
