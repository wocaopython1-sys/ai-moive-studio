import { computed, ref } from 'vue'
import { canvasService } from '@/services/canvas'
import {
  DEFAULT_ASPECT_RATIO,
  DEFAULT_IMAGE_ASPECT_RATIO,
  DEFAULT_IMAGE_COUNT,
  DEFAULT_IMAGE_SIZE,
  DEFAULT_VIDEO_DURATION_SECONDS
} from '@/utils/canvasGenerationPayload'

const DEFAULT_CONTENT = {
  text: () => ({ text: '', text_preview: '', prompt: '', promptTokens: [] }),
  image: () => ({
    prompt: '',
    result_image_url: '',
    reference_image_url: '',
    style_reference_image_object_key: '',
    aspectRatio: DEFAULT_IMAGE_ASPECT_RATIO,
    imageSize: DEFAULT_IMAGE_SIZE,
    imageCount: DEFAULT_IMAGE_COUNT,
    promptTokens: []
  }),
  video: () => ({
    prompt: '',
    result_video_url: '',
    reference_image_urls: [],
    reference_text_ids: [],
    promptTokens: []
  })
}

const DEFAULT_SIZE = {
  text: { width: 320, height: 220 },
  image: { width: 340, height: 280 },
  video: { width: 360, height: 300 }
}

const PERSIST_DEBOUNCE_MS = 300
const MEDIA_URL_TO_OBJECT_KEY_FIELDS = {
  result_image_url: 'result_image_object_key',
  reference_image_url: 'reference_image_object_key',
  result_video_url: 'result_video_object_key'
}

const stripTransientMediaUrls = (payload = {}) => {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return payload
  }

  const sanitized = { ...payload }
  Object.entries(MEDIA_URL_TO_OBJECT_KEY_FIELDS).forEach(
    ([urlField, objectKeyField]) => {
      if (sanitized[objectKeyField]) {
        delete sanitized[urlField]
      }
    }
  )
  return sanitized
}

export function useCanvasEditor() {
  const loading = ref(false)
  const saving = ref(false)
  const document = ref(null)
  const items = ref([])
  const connections = ref([])
  const selectedItemIds = ref([])
  const dirty = ref(false)
  const zoom = ref(1)
  const pan = ref({ x: 0, y: 0 })
  const pendingConnection = ref(null)

  let currentDocumentId = ''
  const persistTimers = new Map()
  const detailLoading = new Set()

  const selectedItemId = computed(() =>
    selectedItemIds.value.length === 1 ? selectedItemIds.value[0] : null
  )

  const selectedItem = computed(() =>
    items.value.find((item) => item.id === selectedItemId.value) || null
  )

  const maxZIndex = computed(() =>
    items.value.reduce((max, item) => Math.max(max, item.z_index || 0), 0)
  )

  const normalizeItem = (item) => ({
    id: item.id,
    item_type: item.item_type,
    title: item.title || '',
    position_x: Number(item.position_x || 0),
    position_y: Number(item.position_y || 0),
    width: Number(item.width || DEFAULT_SIZE[item.item_type]?.width || 320),
    height: Number(item.height || DEFAULT_SIZE[item.item_type]?.height || 220),
    z_index: Number(item.z_index || 0),
    content: {
      ...(DEFAULT_CONTENT[item.item_type]?.() || {}),
      ...(item.content || {})
    },
    generation_config: { ...(item.generation_config || {}) },
    last_run_status: item.last_run_status || 'idle',
    last_run_error: item.last_run_error || null,
    last_output: { ...(item.last_output || {}) },
    has_detail: Boolean(
      item.has_detail ||
        item.content?.text ||
        item.content?.prompt ||
        item.content?.promptTokens?.length
    ),
    is_persisted: true
  })

  const normalizeConnection = (connection) => ({
    id: connection.id,
    source_item_id: connection.source_item_id,
    target_item_id: connection.target_item_id,
    source_handle: connection.source_handle,
    target_handle: connection.target_handle
  })

  const mergeItem = (itemId, patch) => {
    const hasLastOutput = Object.prototype.hasOwnProperty.call(
      patch,
      'last_output'
    )
    items.value = items.value.map((item) =>
      item.id === itemId
        ? {
            ...item,
            ...patch,
            content: patch.content
              ? { ...item.content, ...patch.content }
              : item.content,
            generation_config: patch.generation_config
              ? { ...item.generation_config, ...patch.generation_config }
              : item.generation_config,
            last_output: hasLastOutput
              ? { ...(patch.last_output || {}) }
              : item.last_output
          }
        : item
    )
  }

  const clearPersistTimer = (itemId) => {
    const timer = persistTimers.get(itemId)
    if (timer) {
      window.clearTimeout(timer)
      persistTimers.delete(itemId)
    }
  }

  const persistItemNow = async (itemId) => {
    clearPersistTimer(itemId)
    if (!currentDocumentId) return
    const item = items.value.find((entry) => entry.id === itemId)
    if (!item?.is_persisted) return

    await canvasService.updateItem(currentDocumentId, itemId, {
      title: item.title,
      position_x: item.position_x,
      position_y: item.position_y,
      width: item.width,
      height: item.height,
      z_index: item.z_index,
      content: stripTransientMediaUrls(item.content),
      generation_config: item.generation_config,
      last_run_status: item.last_run_status,
      last_run_error: item.last_run_error,
      last_output: stripTransientMediaUrls(item.last_output)
    })
  }

  const schedulePersist = (itemId) => {
    if (!currentDocumentId) return
    clearPersistTimer(itemId)
    const timer = window.setTimeout(async () => {
      try {
        await persistItemNow(itemId)
        dirty.value = persistTimers.size > 0
      } catch (error) {
        console.error('Persist canvas item failed', error)
      }
    }, PERSIST_DEBOUNCE_MS)
    persistTimers.set(itemId, timer)
    dirty.value = true
  }

  const hydrateItemDetail = async (itemId) => {
    if (!currentDocumentId || !itemId || detailLoading.has(itemId)) return
    const target = items.value.find((item) => item.id === itemId)
    if (!target || target.has_detail) return

    detailLoading.add(itemId)
    try {
      const detail = normalizeItem(
        await canvasService.getItem(currentDocumentId, itemId)
      )
      mergeItem(itemId, {
        ...detail,
        has_detail: true
      })
    } finally {
      detailLoading.delete(itemId)
    }
  }

  const loadDocument = async (documentId) => {
    loading.value = true
    currentDocumentId = documentId
    try {
      const snapshot = await canvasService.getLite(documentId)
      document.value = snapshot.document
      items.value = (snapshot.items || []).map((item) =>
        normalizeItem({ ...item, has_detail: false })
      )
      connections.value = (snapshot.connections || []).map(normalizeConnection)
      selectedItemIds.value = items.value[0]?.id ? [items.value[0].id] : []
      dirty.value = false
      if (selectedItemId.value) {
        await hydrateItemDetail(selectedItemId.value)
      }
    } finally {
      loading.value = false
    }
  }

  const save = async () => {
    saving.value = true
    try {
      const itemIds = [...persistTimers.keys()]
      for (const itemId of itemIds) {
        await persistItemNow(itemId)
      }
      dirty.value = false
      return {
        document: document.value,
        items: items.value,
        connections: connections.value
      }
    } finally {
      saving.value = false
    }
  }

  const createItem = async (itemType, options = {}) => {
    if (!currentDocumentId) return null
    const position = options?.position || options || {}
    const initialGenerationConfig =
      options?.generation_config &&
      typeof options.generation_config === 'object' &&
      !Array.isArray(options.generation_config)
        ? options.generation_config
        : {}
    const initialContent =
      options?.content &&
      typeof options.content === 'object' &&
      !Array.isArray(options.content)
        ? options.content
        : {}
    const initialLastOutput =
      options?.last_output &&
      typeof options.last_output === 'object' &&
      !Array.isArray(options.last_output)
        ? options.last_output
        : {}
    const count = items.value.filter(
      (item) => item.item_type === itemType
    ).length
    const size = DEFAULT_SIZE[itemType] || DEFAULT_SIZE.text
    const payload = {
      item_type: itemType,
      title:
        String(options?.title || '').trim() ||
        (itemType === 'text'
          ? `文本节点 ${count + 1}`
          : itemType === 'image'
            ? `图片节点 ${count + 1}`
            : `视频节点 ${count + 1}`),
      position_x: Number(position.position_x ?? 120 + count * 24),
      position_y: Number(position.position_y ?? 120 + count * 24),
      width: Number(options?.width ?? size.width),
      height: Number(options?.height ?? size.height),
      z_index: maxZIndex.value + 1,
      content: {
        ...DEFAULT_CONTENT[itemType](),
        ...initialContent
      },
      generation_config: {
        ...(itemType === 'video'
          ? {
              aspectRatio: DEFAULT_ASPECT_RATIO,
              durationSeconds: DEFAULT_VIDEO_DURATION_SECONDS
            }
          : {}),
        ...initialGenerationConfig
      },
      last_run_status: options?.last_run_status || 'idle',
      last_run_error: options?.last_run_error || null,
      last_output: initialLastOutput
    }
    const created = normalizeItem(
      await canvasService.createItem(currentDocumentId, payload)
    )
    items.value = [...items.value, { ...created, has_detail: true }]
    selectedItemIds.value = [created.id]
    return created
  }

  const updateItem = (itemId, patch, options = {}) => {
    mergeItem(itemId, patch)
    if (options.persist === false) {
      return
    }
    schedulePersist(itemId)
  }

  const removeItem = async (itemId) => {
    await removeItems([itemId])
  }

  const removeItems = async (itemIds = []) => {
    if (!currentDocumentId) return
    const normalizedIds = [...new Set((itemIds || []).filter(Boolean))]
    if (!normalizedIds.length) {
      return
    }
    normalizedIds.forEach((itemId) => clearPersistTimer(itemId))
    await canvasService.deleteItems(currentDocumentId, normalizedIds)
    const removedIdSet = new Set(normalizedIds)
    items.value = items.value.filter((item) => !removedIdSet.has(item.id))
    connections.value = connections.value.filter(
      (connection) =>
        !removedIdSet.has(connection.source_item_id) &&
        !removedIdSet.has(connection.target_item_id)
    )
    selectedItemIds.value = selectedItemIds.value.filter(
      (itemId) => !removedIdSet.has(itemId)
    )
    if (selectedItemId.value) {
      void hydrateItemDetail(selectedItemId.value)
    }
    if (
      pendingConnection.value?.itemId &&
      removedIdSet.has(pendingConnection.value.itemId)
    ) {
      pendingConnection.value = null
    }
  }

  const setSelection = (itemId) => {
    selectedItemIds.value = itemId ? [itemId] : []
    void hydrateItemDetail(itemId)
  }

  const setSelections = (itemIds = []) => {
    const normalizedIds = [...new Set((itemIds || []).filter(Boolean))]
    selectedItemIds.value = normalizedIds
    if (normalizedIds.length === 1) {
      void hydrateItemDetail(normalizedIds[0])
    }
  }

  const clearSelection = () => {
    selectedItemIds.value = []
  }

  const startConnection = (itemId, handle = 'output') => {
    pendingConnection.value = { itemId, handle }
    setSelection(itemId)
  }

  const completeConnection = async (itemId, handle = 'input') => {
    if (!pendingConnection.value || !currentDocumentId) return
    if (pendingConnection.value.itemId === itemId) {
      pendingConnection.value = null
      return
    }

    const exists = connections.value.some(
      (connection) =>
        connection.source_item_id === pendingConnection.value.itemId &&
        connection.target_item_id === itemId &&
        connection.source_handle === pendingConnection.value.handle &&
        connection.target_handle === handle
    )

    if (!exists) {
      const created = normalizeConnection(
        await canvasService.createConnection(currentDocumentId, {
          source_item_id: pendingConnection.value.itemId,
          target_item_id: itemId,
          source_handle: pendingConnection.value.handle,
          target_handle: handle
        })
      )
      connections.value = [...connections.value, created]
    }

    pendingConnection.value = null
  }

  const removeConnection = async (connectionId) => {
    if (!currentDocumentId) return
    await canvasService.deleteConnection(currentDocumentId, connectionId)
    connections.value = connections.value.filter(
      (connection) => connection.id !== connectionId
    )
  }

  const updateViewport = ({
    zoom: nextZoom = zoom.value,
    pan: nextPan = pan.value
  }) => {
    zoom.value = Math.min(2, Math.max(0.5, Number(nextZoom)))
    pan.value = {
      x: Number(nextPan.x || 0),
      y: Number(nextPan.y || 0)
    }
  }

  return {
    loading,
    saving,
    document,
    items,
    connections,
    selectedItemIds,
    selectedItemId,
    selectedItem,
    dirty,
    zoom,
    pan,
    pendingConnection,
    loadDocument,
    save,
    createItem,
    updateItem,
    removeItem,
    removeItems,
    setSelection,
    setSelections,
    clearSelection,
    startConnection,
    completeConnection,
    removeConnection,
    updateViewport
  }
}
