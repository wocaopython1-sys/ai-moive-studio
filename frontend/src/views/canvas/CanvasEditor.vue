<template>
  <section class="canvas-editor-page" v-loading="loading">
    <div ref="stageShellRef" class="canvas-stage-shell">
      <KonvaCanvasStage
        :items="items"
        :connections="connections"
        :selected-item-ids="selectedItemIds"
        :selected-connection-ids="selectedConnectionIds"
        :editing-item-id="selectedItem?.id || ''"
        :viewport-command="viewportCommand"
        @connection-click="handleConnectionClick"
        @item-click="handleItemClick"
        @item-drag-end="handleItemDragEnd"
        @item-handle-pointerdown="handleStageHandlePointerDown"
        @item-resize-suggest="handleItemResizeSuggest"
        @stage-click="handleStageClick"
        @viewport-change="handleViewportChange"
        @selection-box-end="handleSelectionBoxEnd"
      />

      <CanvasLinkDragOverlay :path="dragPath" />
      <CanvasConnectionActions
        :visible="Boolean(selectedConnection && connectionActionPosition)"
        :position="connectionActionPosition"
        @delete="handleRemoveSelectedConnection"
      />
      <CanvasLinkCreateMenu
        :visible="linkMenu.visible"
        :screen-x="linkMenu.screenX"
        :screen-y="linkMenu.screenY"
        :options="createOptions"
        @select="handleCreateLinkedNode"
      />

      <CanvasWorkbenchLayout
        :title="document?.title || 'Canvas'"
        :zoom-hint-text="zoomHintText"
        :zoom-text="`${Math.round(zoom * 100)}% 视图`"
        :link-mode-text="linkModeText"
        :show-launcher="!selectedItem"
        @back="router.push('/canvas')"
        @create-item="createNode"
        @open-assets="openAssetDrawer"
        @open-tasks="openCanvasTasks"
      >
        <CanvasAssistant
          :document-id="assistantDocumentId"
          :selected-item="selectedItem"
          :refresh-canvas="handleAssistantMutationApplied"
        />
      </CanvasWorkbenchLayout>

      <CanvasTextStudio
        v-if="selectedItem?.item_type === 'text'"
        ref="textStudioRef"
        :item="selectedItem"
        :style="selectedItemStyle"
        :draft="textStudioDraft"
        :available-reference-items="availableReferenceItems"
        :global-reference-items="globalReferenceItems"
        :generating="Boolean(generationLoadingByItem[selectedItem.id])"
        :api-key-options="apiKeyOptions"
        :model-options="textModelOptions"
        :model-options-loading="catalogLoading"
        @focus-item="handleFocusItem"
        @drag-node="startStudioNodeDrag"
        @handle-drag="handleStudioHandleDrag"
        @update:title="patchSelected({ title: $event })"
        @update:text="patchSelectedContent({ text: $event })"
        @update:api-key-id="patchGenerationConfig({ api_key_id: $event })"
        @update:model-id="patchGenerationConfig({ model: $event })"
        @update:tokens="updatePromptTokens($event)"
        @submit-generation="handleGenerate"
        @create-image-from-text="createImageFromTextNode"
        @create-video-from-text="createVideoFromTextNode"
        @delete="removeSelectedItem"
      />

      <CanvasImageStudio
        v-if="selectedItem?.item_type === 'image'"
        ref="imageStudioRef"
        :style="selectedItemStyle"
        :draft="imageStudioDraft"
        :available-reference-items="availableReferenceItems"
        :global-reference-items="globalReferenceItems"
        :generating="Boolean(generationLoadingByItem[selectedItem.id])"
        :uploading="uploading"
        :api-key-options="apiKeyOptions"
        :model-options="imageModelOptions"
        :model-options-loading="catalogLoading"
        :aspect-ratio-options="imageAspectRatioOptions"
        @focus-item="handleFocusItem"
        @drag-node="startStudioNodeDrag"
        @handle-drag="handleStudioHandleDrag"
        @update:title="patchSelected({ title: $event })"
        @update:api-key-id="patchGenerationConfig({ api_key_id: $event })"
        @update:model-id="patchGenerationConfig({ model: $event })"
        @update:aspect-ratio="patchSelectedContent({ aspectRatio: $event })"
        @update:tokens="updatePromptTokens($event)"
        @generate="handleGenerate"
        @history="openHistoryDrawer()"
        @copy-url="copySelectedMediaUrl"
        @download="downloadSelectedMedia"
        @create-video-from-image="createVideoFromImageNode"
        @upload="uploadMedia($event, 'image')"
        @upload-style-reference="uploadStyleReference"
        @clear-style-reference="clearStyleReference"
        @delete="removeSelectedItem"
      />

      <CanvasVideoStudio
        v-if="selectedItem?.item_type === 'video'"
        ref="videoStudioRef"
        :style="selectedItemStyle"
        :draft="videoStudioDraft"
        :status-meta="selectedVideoStatusMeta"
        :available-reference-items="availableReferenceItems"
        :global-reference-items="globalReferenceItems"
        :reference-hint-text="videoReferenceHint"
        :generating="Boolean(generationLoadingByItem[selectedItem.id])"
        :uploading="uploading"
        :api-key-options="apiKeyOptions"
        :model-options="videoModelOptions"
        :model-options-loading="catalogLoading"
        :aspect-ratio-options="videoAspectRatioOptions"
        @focus-item="handleFocusItem"
        @drag-node="startStudioNodeDrag"
        @handle-drag="handleStudioHandleDrag"
        @update:title="patchSelected({ title: $event })"
        @update:api-key-id="patchGenerationConfig({ api_key_id: $event })"
        @update:model-id="patchGenerationConfig({ model: $event })"
        @update:aspect-ratio="patchGenerationConfig({ aspectRatio: $event })"
        @update:tokens="updatePromptTokens($event)"
        @generate="handleGenerate"
        @history="openHistoryDrawer()"
        @copy-url="copySelectedMediaUrl"
        @download="downloadSelectedMedia"
        @upload="uploadMedia($event, 'video')"
        @delete="removeSelectedItem"
      />

      <CanvasGenerationHistoryDrawer
        :visible="historyDrawerVisible"
        :title="historyDrawerTitle"
        :subtitle="historyDrawerSubtitle"
        :items="historyDrawerItems"
        :loading="historyDrawerLoading"
        :selecting-id="historySelectingId"
        :media-type="historyDrawerMediaType"
        @update:visible="historyDrawerVisible = $event"
        @refresh="refreshHistory"
        @select="handleHistorySelect"
      />

      <aside
        v-if="assetDrawerVisible"
        class="canvas-asset-panel"
        data-testid="canvas-asset-panel"
      >
        <header class="canvas-asset-panel__header">
          <div>
            <h3>最近素材</h3>
            <p>{{ assetItems.length }} 个可加入 Canvas 的图片/视频</p>
          </div>
          <div class="canvas-asset-panel__header-actions">
            <input
              ref="assetUploadInput"
              class="canvas-asset-panel__upload-input"
              type="file"
              accept=".png,.jpg,.jpeg,.webp,.gif,.bmp,.mp4,.webm,.mov,image/*,video/mp4,video/webm,video/quicktime"
              @change="handleAssetUploadChange"
            />
            <button
              class="canvas-asset-panel__icon-btn"
              type="button"
              :disabled="assetLoading || uploading"
              data-testid="upload-asset-from-canvas"
              @click="triggerAssetUpload"
            >
              {{ uploading ? '上传中' : '上传' }}
            </button>
            <button
              class="canvas-asset-panel__icon-btn"
              type="button"
              :disabled="assetLoading"
              data-testid="refresh-assets"
              @click="loadAssetItems"
            >
              刷新
            </button>
            <button
              class="canvas-asset-panel__close"
              type="button"
              aria-label="关闭最近素材"
              @click="assetDrawerVisible = false"
            >
              ×
            </button>
          </div>
        </header>

        <div v-if="assetLoading" class="canvas-asset-panel__state">
          正在加载素材...
        </div>
        <div v-else-if="!assetItems.length" class="canvas-asset-panel__state">
          暂无图片或视频素材
        </div>
        <div v-else class="canvas-asset-panel__list">
          <article
            v-for="asset in assetItems"
            :key="asset.object_key"
            class="canvas-asset-card"
            :data-media-type="asset.media_type"
          >
            <div class="canvas-asset-card__preview">
              <img
                v-if="asset.media_type === 'image'"
                :src="asset.preview_url"
                :alt="asset.filename"
                loading="lazy"
                draggable="false"
              />
              <video
                v-else
                :src="asset.preview_url"
                controls
                playsinline
                preload="metadata"
              ></video>
            </div>
            <div class="canvas-asset-card__body">
              <div class="canvas-asset-card__title">{{ asset.filename }}</div>
              <div class="canvas-asset-card__meta">
                {{ asset.media_type === 'image' ? '图片' : '视频' }}
                <span v-if="asset.size_mb"> · {{ asset.size_mb }} MB</span>
              </div>
              <div class="canvas-asset-card__actions">
                <button
                  class="canvas-asset-card__primary"
                  type="button"
                  data-testid="add-asset-to-canvas"
                  @click="addAssetToCanvas(asset)"
                >
                  加入 Canvas
                </button>
                <button
                  class="canvas-asset-card__secondary"
                  type="button"
                  data-testid="copy-asset-url"
                  @click="copyAssetUrl(asset)"
                >
                  复制 URL
                </button>
              </div>
            </div>
          </article>
        </div>
      </aside>

      <aside
        v-if="selectedItem"
        class="canvas-relation-panel"
        data-testid="canvas-relation-panel"
      >
        <div class="canvas-relation-panel__header">
          <div>
            <h3>关系</h3>
            <p>当前：{{ relationNodeLabel(selectedItem) }}</p>
          </div>
        </div>

        <div class="canvas-relation-panel__body">
          <div v-if="directSourceItems.length" class="canvas-relation-panel__sources">
            <button
              v-for="source in directSourceItems"
              :key="source.id"
              class="canvas-relation-source"
              type="button"
              data-testid="relation-source-item"
              @click="handleFocusItem(source.id)"
            >
              <span>来源</span>
              <strong>{{ relationNodeLabel(source) }}</strong>
            </button>
          </div>
          <div v-else class="canvas-relation-panel__empty">暂无来源关系</div>

          <div v-if="relationSourceItem" class="canvas-relation-candidate">
            待关联来源：{{ relationNodeLabel(relationSourceItem) }}
          </div>

          <div
            v-if="relationSourceItem"
            class="canvas-relation-targets"
            data-testid="relation-target-list"
          >
            <div class="canvas-relation-targets__title">可关联目标</div>
            <button
              v-for="target in compatibleRelationTargets"
              :key="target.id"
              class="canvas-relation-target"
              type="button"
              data-testid="relation-target-link"
              @click="linkRelationSourceToItem(target)"
            >
              <span>关联</span>
              <strong>{{ relationNodeLabel(target) }}</strong>
            </button>
            <div
              v-if="!compatibleRelationTargets.length"
              class="canvas-relation-panel__empty"
            >
              没有可关联的目标节点
            </div>
          </div>

          <div
            v-if="compatibleRelationSources.length"
            class="canvas-relation-targets"
            data-testid="relation-source-list"
          >
            <div class="canvas-relation-targets__title">可选来源</div>
            <button
              v-for="source in compatibleRelationSources"
              :key="source.id"
              class="canvas-relation-target"
              type="button"
              data-testid="relation-source-link"
              @click="linkItemToSelected(source)"
            >
              <span>来源</span>
              <strong>{{ relationNodeLabel(source) }}</strong>
            </button>
          </div>
        </div>

        <div class="canvas-relation-panel__actions">
          <button
            class="canvas-relation-btn canvas-relation-btn--primary"
            type="button"
            data-testid="save-selected-to-library"
            @click="saveSelectedToLibrary"
          >
            保存到素材库
          </button>
          <button
            class="canvas-relation-btn"
            type="button"
            data-testid="set-relation-source"
            :disabled="!canUseAsRelationSource(selectedItem)"
            @click="setSelectedAsRelationSource"
          >
            设为来源
          </button>
          <button
            v-if="relationSourceItem && relationSourceItem.id !== selectedItem.id"
            class="canvas-relation-btn canvas-relation-btn--primary"
            type="button"
            data-testid="link-relation-to-selected"
            :disabled="!canCreateRelation(relationSourceItem, selectedItem)"
            @click="linkRelationSourceToSelected"
          >
            关联到当前节点
          </button>
          <button
            v-if="relationSourceItem"
            class="canvas-relation-btn canvas-relation-btn--ghost"
            type="button"
            data-testid="clear-relation-source"
            @click="clearRelationSource"
          >
            取消
          </button>
        </div>
      </aside>
    </div>
  </section>
</template>

<script setup>
  import {
    computed,
    onBeforeUnmount,
    onMounted,
    reactive,
    ref,
    watch
  } from 'vue'
  import { useRoute, useRouter } from 'vue-router'
  import { ElMessage, ElMessageBox } from 'element-plus'
  import CanvasConnectionActions from '@/components/canvas/CanvasConnectionActions.vue'
  import CanvasGenerationHistoryDrawer from '@/components/canvas/CanvasGenerationHistoryDrawer.vue'
import CanvasImageStudio from '@/components/canvas/CanvasImageStudio.vue'
import CanvasLinkCreateMenu from '@/components/canvas/CanvasLinkCreateMenu.vue'
import CanvasLinkDragOverlay from '@/components/canvas/CanvasLinkDragOverlay.vue'
import CanvasAssistant from '@/components/canvas/assistant/CanvasAssistant.vue'
import CanvasTextStudio from '@/components/canvas/CanvasTextStudio.vue'
  import CanvasVideoStudio from '@/components/canvas/CanvasVideoStudio.vue'
  import CanvasWorkbenchLayout from '@/components/canvas/CanvasWorkbenchLayout.vue'
  import KonvaCanvasStage from '@/components/canvas/KonvaCanvasStage.vue'
  import { useCanvasEditor } from '@/composables/useCanvasEditor'
  import { useCanvasGeneration } from '@/composables/useCanvasGeneration'
  import { apiKeysService } from '@/services/apiKeys'
  import { canvasService } from '@/services/canvas'
  import { fileService } from '@/services/upload'
  import {
    DEFAULT_ASPECT_RATIO,
    buildCanvasGenerationPayload,
    getSupportedVideoAspectRatios,
    IMAGE_ASPECT_RATIO_OPTIONS,
    normalizeVideoAspectRatio
  } from '@/utils/canvasGenerationPayload'
  import { buildCanvasHistoryEntries } from '@/utils/canvasGenerationHistory'
  import { resolveCanvasRunStatusMeta } from '@/utils/canvasStageMedia'
  import { buildPromptDerivatives } from '@/utils/promptMentionTokens'

  const route = useRoute()
  const router = useRouter()
  const stageShellRef = ref(null)
  const textStudioRef = ref(null)
  const imageStudioRef = ref(null)
  const videoStudioRef = ref(null)
  const assetUploadInput = ref(null)
  const uploading = ref(false)
  const catalogLoading = ref(false)
  const styleReferencePreviewMap = ref({})
  const imageUploadPreviewMap = ref({})
  const apiKeyOptions = ref([])
  const modelCatalog = ref({
    text: [],
    image: [],
    video: []
  })
  const historyDrawerVisible = ref(false)
  const historyTargetItemId = ref('')
  const historyTargetMediaType = ref('image')
  const historySelectingId = ref('')
  const assetDrawerVisible = ref(false)
  const assetLoading = ref(false)
  const assetItems = ref([])
  const relationSourceItemId = ref('')
  const handledEntryModeKeys = new Set()

  const entryModeConfigs = {
    image: {
      title: '图片 Prompt',
      text: '请输入你想生成的图片描述。',
      successMessage: '已进入图片创作模式，可以编辑 Prompt 后生成图片。'
    },
    video: {
      title: '视频 Prompt',
      text: '请输入你想生成的视频描述。',
      successMessage: '已进入视频创作模式，可以编辑 Prompt 后生成视频。'
    },
    storyboard: {
      title: '故事 / 分镜输入',
      text: '请输入故事梗概、角色、场景或镜头要求。',
      successMessage: '已进入 Prompt / 分镜助手模式。'
    }
  }
  const entryAssetModeMessages = {
    i2v: '请选择一张图片作为图生视频参考。',
    upload: '上传图片、视频或选择已有素材加入 Canvas。'
  }

  const {
    loading,
    saving,
    document,
    items,
    connections,
    selectedItemIds,
    selectedItemId,
    selectedItem,
    zoom,
    pan,
    dirty,
    loadDocument,
    save,
    createItem,
    updateItem,
    removeItems,
    setSelection,
    setSelections,
    clearSelection,
    startConnection,
    completeConnection,
    removeConnection,
    updateViewport
  } = useCanvasEditor()

  const {
    generationLoadingByItem,
    generationHistories,
    historyLoadingByItem,
    loadHistory,
    generate,
    applyGeneration
  } = useCanvasGeneration(
    updateItem,
    (itemId) => items.value.find((entry) => entry.id === itemId) || null
  )

  const viewport = reactive({ width: 0, height: 0 })
  const viewportCommand = ref(null)
  const selectedConnectionId = ref(null)
  const linkDrag = ref(null)
  const studioDrag = ref(null)
  const linkMenu = reactive({
    visible: false,
    screenX: 0,
    screenY: 0,
    canvasX: 0,
    canvasY: 0,
    sourceItemId: '',
    sourceHandle: 'right'
  })

  const createOptions = [
    { type: 'text', label: '文本节点', description: '创建文本节点并自动连接' },
    { type: 'image', label: '图片节点', description: '创建图片节点并自动连接' },
    { type: 'video', label: '视频节点', description: '创建视频节点并自动连接' }
  ]

  const assistantDocumentId = computed(() =>
    String(document.value?.id || route.params.canvasId || '').trim()
  )
  const selectedConnectionIds = computed(() =>
    selectedConnectionId.value ? [selectedConnectionId.value] : []
  )
  const selectedConnection = computed(
    () =>
      connections.value.find(
        (connection) => connection.id === selectedConnectionId.value
      ) || null
  )
  const relationSourceItem = computed(() =>
    items.value.find((item) => item.id === relationSourceItemId.value) || null
  )

  const handleAssistantMutationApplied = async (payload = {}) => {
    if (payload?.action === 'assistant_apply_result') {
      const targetDocumentId = String(payload.documentId || assistantDocumentId.value || '').trim()
      const targetItemId = String(payload.item?.id || '').trim()
      if (!targetDocumentId) {
        return
      }
      syncSelectedStudioDraft()
      if (dirty.value) {
        await save()
      }
      await loadDocument(targetDocumentId)
      selectedConnectionId.value = null
      const targetItem = items.value.find((item) => item.id === targetItemId)
      if (targetItem) {
        await focusCanvasItem(targetItem)
      } else {
        clearSelection()
      }
      return
    }
    if (payload?.action === 'write_assistant_text_to_selected') {
      await writeAssistantTextToSelected(payload.text)
      return
    }
    if (payload?.action === 'create_assistant_text_node') {
      await createAssistantTextNode(payload.text)
      return
    }
    if (payload?.action === 'assistant_prompt_to_image') {
      return await createImageFromAssistantPrompt(payload)
    }
    if (payload?.action === 'assistant_prompt_to_video') {
      return await createVideoFromAssistantPrompt(payload)
    }
    if (payload?.action === 'assistant_split_storyboard_prompts') {
      return await splitAssistantStoryboardPrompts(payload)
    }
    const { documentId } = payload || {}
    const targetDocumentId = String(documentId || assistantDocumentId.value || '').trim()
    if (!targetDocumentId) {
      return
    }
    if (dirty.value) {
      await save()
    }
    const preservedSelectionIds = [...(selectedItemIds.value || [])]
    const preservedConnectionId = selectedConnectionId.value
    syncSelectedStudioDraft()
    await loadDocument(targetDocumentId)
    const nextSelectionIds = preservedSelectionIds.filter((selectionId) =>
      items.value.some((item) => item.id === selectionId)
    )
    if (nextSelectionIds.length > 1) {
      setSelections(nextSelectionIds)
    } else if (nextSelectionIds.length === 1) {
      setSelection(nextSelectionIds[0])
    } else {
      clearSelection()
    }
    if (preservedConnectionId && connections.value.some((connection) => connection.id === preservedConnectionId)) {
      selectedConnectionId.value = preservedConnectionId
    } else {
      selectedConnectionId.value = null
    }
  }

  const selectedItemStyle = computed(() => {
    if (!selectedItem.value) {
      return null
    }
    const shellRect = stageShellRef.value?.getBoundingClientRect()
    const screenLeft = selectedItem.value.position_x * zoom.value + pan.value.x
    const screenTop = selectedItem.value.position_y * zoom.value + pan.value.y
    const screenWidth = selectedItem.value.width * zoom.value
    const screenHeight = selectedItem.value.height * zoom.value
    const panelWidth = selectedItem.value.item_type === 'text' ? 560 : 620
    const panelMinWidth = selectedItem.value.item_type === 'text' ? 360 : 420
    const spaceBelow = shellRect
      ? shellRect.height - (screenTop + screenHeight) - 20
      : 0
    const viewportSpaceBelow =
      shellRect && typeof window !== 'undefined'
        ? window.innerHeight - (shellRect.top + screenTop + screenHeight) - 20
        : spaceBelow
    const availableSpaceBelow = Math.min(spaceBelow, viewportSpaceBelow)
    const estimatedPanelHeight =
      selectedItem.value.item_type === 'text' ? 210 : 300
    const minSpaceAbove = 180
    const shouldPlacePanelAbove = shellRect
      ? availableSpaceBelow < estimatedPanelHeight &&
        screenTop > minSpaceAbove
      : false
    const headerNeedsInset = shellRect ? screenTop < 64 : false
    let panelOffsetX = 0
    if (shellRect) {
      const safeWidth = Math.max(
        panelMinWidth,
        Math.min(panelWidth, shellRect.width - 32)
      )
      const centeredLeft = screenLeft + screenWidth / 2 - safeWidth / 2
      const clampedLeft = Math.min(
        Math.max(centeredLeft, 16),
        Math.max(16, shellRect.width - safeWidth - 16)
      )
      panelOffsetX = clampedLeft - centeredLeft
    }
    const computedPanelMaxWidth = shellRect
      ? Math.max(panelMinWidth, Math.min(panelWidth, shellRect.width - 32))
      : panelWidth
    return {
      position: 'absolute',
      left: '0',
      top: '0',
      width: `${selectedItem.value.width * zoom.value}px`,
      height: `${selectedItem.value.height * zoom.value}px`,
      transform: `translate(${selectedItem.value.position_x * zoom.value + pan.value.x}px, ${selectedItem.value.position_y * zoom.value + pan.value.y}px)`,
      transformOrigin: 'top left',
      '--studio-panel-top': shouldPlacePanelAbove
        ? 'auto'
        : 'calc(100% + 22px)',
      '--studio-panel-bottom': shouldPlacePanelAbove
        ? 'calc(100% + 18px)'
        : 'auto',
      '--studio-panel-offset-x': `${panelOffsetX}px`,
      '--studio-panel-max-width': `${computedPanelMaxWidth}px`,
      '--studio-panel-min-width': `${Math.min(panelMinWidth, Math.max(280, (shellRect?.width || panelMinWidth) - 32))}px`,
      '--studio-header-top': headerNeedsInset ? '12px' : '-48px'
    }
  })

  const normalizePromptTokens = (tokens = []) => {
    const nextTokens = Array.isArray(tokens) ? tokens : []
    const { promptPlainText } = buildPromptDerivatives(nextTokens)
    return {
      promptTokens: nextTokens,
      prompt: promptPlainText,
      promptPlainText
    }
  }

  const resolveInitialPromptTokens = (item) => {
    const existingTokens = item?.content?.promptTokens
    if (Array.isArray(existingTokens) && existingTokens.length) {
      return existingTokens
    }
    const prompt = String(item?.content?.prompt || '')
    return prompt ? [{ type: 'text', text: prompt }] : []
  }

  const textStudioDraft = computed(() => {
    if (!selectedItem.value) return {}
    return {
      title: selectedItem.value.title || '',
      text:
        selectedItem.value.content?.text ||
        selectedItem.value.content?.draft_text ||
        selectedItem.value.content?.text_preview ||
        '',
      apiKeyId: selectedItem.value.generation_config?.api_key_id || '',
      model: selectedItem.value.generation_config?.model || '',
      ...normalizePromptTokens(resolveInitialPromptTokens(selectedItem.value))
    }
  })

  const imageStudioDraft = computed(() => {
    if (!selectedItem.value) return {}
    const styleReferenceObjectKey = resolveStyleReferenceImageObjectKey(
      selectedItem.value.content
    )
    const styleReferencePreview =
      styleReferencePreviewMap.value[selectedItem.value.id] || {}
    const uploadPreview =
      imageUploadPreviewMap.value[selectedItem.value.id] || ''
    return {
      title: selectedItem.value.title || '',
      resultImageUrl: resolveImagePreviewUrl(
        selectedItem.value.content,
        uploadPreview
      ),
      referenceImageUrl: resolveImagePreviewUrl(
        selectedItem.value.content,
        uploadPreview
      ),
      styleReferenceObjectKey,
      styleReferenceName:
        styleReferencePreview.name ||
        (styleReferenceObjectKey ? '已选择风格参考' : ''),
      styleReferencePreviewUrl: styleReferencePreview.url || '',
      aspectRatio: String(
        selectedItem.value.content?.aspectRatio || DEFAULT_ASPECT_RATIO || ''
      ).trim(),
      apiKeyId: selectedItem.value.generation_config?.api_key_id || '',
      model: selectedItem.value.generation_config?.model || '',
      ...normalizePromptTokens(resolveInitialPromptTokens(selectedItem.value))
    }
  })

  const videoStudioDraft = computed(() => {
    if (!selectedItem.value) return {}
    return {
      title: selectedItem.value.title || '',
      resultVideoUrl: selectedItem.value.content?.result_video_url || '',
      aspectRatio: normalizeVideoAspectRatio(
        selectedItem.value.generation_config?.model || '',
        selectedItem.value.generation_config?.aspectRatio || ''
      ),
      apiKeyId: selectedItem.value.generation_config?.api_key_id || '',
      model: selectedItem.value.generation_config?.model || '',
      ...normalizePromptTokens(resolveInitialPromptTokens(selectedItem.value))
    }
  })

  const selectedVideoStatusMeta = computed(() => {
    if (!selectedItem.value || selectedItem.value.item_type !== 'video') {
      return null
    }
    return resolveCanvasRunStatusMeta(selectedItem.value)
  })

  const textModelOptions = computed(() => modelCatalog.value.text || [])
  const imageModelOptions = computed(() => modelCatalog.value.image || [])
  const videoModelOptions = computed(() => modelCatalog.value.video || [])
  const defaultCanvasApiKeyId = computed(
    () => String(apiKeyOptions.value[0]?.value || '').trim()
  )
  const defaultImageModel = computed(
    () => String(imageModelOptions.value[0] || '').trim()
  )
  const defaultVideoModel = computed(
    () => String(videoModelOptions.value[0] || '').trim()
  )
  const imageAspectRatioOptions = IMAGE_ASPECT_RATIO_OPTIONS
  const videoAspectRatioOptions = computed(() =>
    getSupportedVideoAspectRatios(
      selectedItem.value?.generation_config?.model || ''
    )
  )

  const buildDefaultGenerationConfig = (type) => {
    if (type !== 'image' && type !== 'video') {
      return {}
    }
    const apiKeyId = defaultCanvasApiKeyId.value
    const model =
      type === 'image' ? defaultImageModel.value : defaultVideoModel.value
    const config = {}
    if (apiKeyId) {
      config.api_key_id = apiKeyId
    }
    if (model) {
      config.model = model
    }
    return config
  }
  const historyTargetItem = computed(
    () =>
      items.value.find((item) => item.id === historyTargetItemId.value) || null
  )
  const historyDrawerMediaType = computed(() => historyTargetMediaType.value)
  const historyDrawerLoading = computed(() =>
    Boolean(historyLoadingByItem[historyTargetItemId.value])
  )
  const historyDrawerTitle = computed(() => {
    const item = historyTargetItem.value
    const mediaLabel =
      historyDrawerMediaType.value === 'video' ? '视频' : '图片'
    if (!item) {
      return `${mediaLabel}历史`
    }
    return `${item.title || mediaLabel} 历史`
  })
  const historyDrawerSubtitle = computed(() => {
    const item = historyTargetItem.value
    if (!item) {
      return ''
    }
    return `选择一个历史生成结果，回填到当前${historyDrawerMediaType.value === 'video' ? '视频' : '图片'}节点。`
  })

  const reverseConnectionMap = computed(() => {
    const map = new Map()
    connections.value.forEach((connection) => {
      const list = map.get(connection.target_item_id) || []
      list.push(connection.source_item_id)
      map.set(connection.target_item_id, list)
    })
    return map
  })

  const directSourceItems = computed(() => {
    if (!selectedItem.value) return []
    return (reverseConnectionMap.value.get(selectedItem.value.id) || [])
      .map((itemId) => items.value.find((item) => item.id === itemId))
      .filter(Boolean)
  })

  const relationNodeLabel = (item) => {
    if (!item) return ''
    const typeLabel =
      item.item_type === 'text'
        ? '文本'
        : item.item_type === 'image'
          ? '图片'
          : '视频'
    const title = String(item.title || '').trim()
    const fallback =
      item.item_type === 'text'
        ? String(item.content?.text || item.content?.prompt || '').trim()
        : item.item_type === 'image'
          ? String(
              item.content?.result_image_object_key ||
                item.content?.reference_image_object_key ||
                item.content?.prompt ||
                ''
            ).trim()
          : String(item.content?.result_video_object_key || item.content?.prompt || '').trim()
    return `${typeLabel}：${title || fallback || item.id}`
  }

  const canUseAsRelationSource = (item) =>
    Boolean(item && ['text', 'image'].includes(item.item_type))

  const canCreateRelation = (source, target) => {
    if (!source || !target || source.id === target.id) return false
    if (source.item_type === 'text') {
      return ['image', 'video'].includes(target.item_type)
    }
    if (source.item_type === 'image') {
      return target.item_type === 'video'
    }
    return false
  }

  const relationExists = (sourceId, targetId) =>
    connections.value.some(
      (connection) =>
        connection.source_item_id === sourceId &&
        connection.target_item_id === targetId
    )

  const compatibleRelationTargets = computed(() => {
    const source = relationSourceItem.value
    if (!source) return []
    return items.value.filter(
      (item) =>
        item.id !== source.id &&
        canCreateRelation(source, item) &&
        !relationExists(source.id, item.id)
    )
  })

  const compatibleRelationSources = computed(() => {
    const target = selectedItem.value
    if (!target) return []
    return items.value.filter(
      (item) =>
        item.id !== target.id &&
        canCreateRelation(item, target) &&
        !relationExists(item.id, target.id)
    )
  })

  const buildReferenceItem = (item) => ({
    ...item,
    previewUrl:
      item.item_type === 'image'
        ? resolveImagePreviewUrl(
            item.content,
            imageUploadPreviewMap.value[item.id] || ''
          )
        : '',
    previewText:
      item.item_type === 'text' ? String(item.content?.text || '') : ''
  })

  const resolveImageReferenceObjectKey = (content = {}) =>
    String(
      content?.result_image_object_key ||
        content?.reference_image_object_key ||
        content?.result_image_key ||
        content?.object_key ||
        content?.objectKey ||
        ''
    ).trim()

  const resolveStyleReferenceImageObjectKey = (content = {}) =>
    String(
      content?.style_reference_image_object_key ||
        content?.reference_image_object_key ||
        content?.reference_image_key ||
        ''
    ).trim()

  const resolveImagePreviewUrl = (content = {}, sessionPreviewUrl = '') => {
    const resultObjectKey = String(
      content?.result_image_object_key || content?.result_image_key || ''
    ).trim()
    const referenceObjectKey = String(
      content?.reference_image_object_key || content?.reference_image_key || ''
    ).trim()
    const resultUrl = String(content?.result_image_url || '').trim()
    const referenceUrl = String(content?.reference_image_url || '').trim()

    if (resultObjectKey && resultUrl) {
      return resultUrl
    }
    if (referenceObjectKey && referenceUrl) {
      return referenceUrl
    }
    return String(sessionPreviewUrl || '').trim()
  }

  const resolveVideoPreviewUrl = (content = {}) =>
    String(content?.result_video_url || '').trim()

  const mediaPathForObjectKey = (objectKey = '', mode = 'preview') => {
    const cleanKey = String(objectKey || '').trim().replace(/^\/+/, '')
    if (!cleanKey) return ''
    return `/api/v1/media/${mode}/${cleanKey}`
  }

  const toAbsoluteUrl = (url = '') => {
    const value = String(url || '').trim()
    if (!value) return ''
    if (/^https?:\/\//i.test(value)) return value
    return `${window.location.origin}${value.startsWith('/') ? value : `/${value}`}`
  }

  const resolveItemMediaUrl = (item, mode = 'preview') => {
    if (!item) return ''
    const content = item.content || {}
    if (item.item_type === 'image') {
      const objectKey = String(
        content.result_image_object_key ||
          content.reference_image_object_key ||
          ''
      ).trim()
      return objectKey
        ? mediaPathForObjectKey(objectKey, mode)
        : String(content.result_image_url || content.reference_image_url || '')
    }
    if (item.item_type === 'video') {
      const objectKey = String(content.result_video_object_key || '').trim()
      return objectKey
        ? mediaPathForObjectKey(objectKey, mode)
        : String(content.result_video_url || '')
    }
    return ''
  }

  const resolveObjectKeyFromItem = (item) => {
    const content = item?.content || {}
    if (item?.item_type === 'image') {
      return String(
        content.result_image_object_key ||
          content.reference_image_object_key ||
          ''
      ).trim()
    }
    if (item?.item_type === 'video') {
      return String(content.result_video_object_key || '').trim()
    }
    return ''
  }

  const mediaTypeFromObjectKey = (objectKey = '') => {
    const suffix = String(objectKey || '').split('?')[0].split('.').pop()?.toLowerCase()
    if (['png', 'jpg', 'jpeg', 'webp', 'gif'].includes(suffix)) return 'image'
    if (['mp4', 'webm', 'mov'].includes(suffix)) return 'video'
    return ''
  }

  const copyTextToClipboard = async (value, successMessage = '已复制') => {
    const text = String(value || '').trim()
    if (!text) {
      ElMessage.warning('没有可复制的 URL')
      return false
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
    ElMessage.success(successMessage)
    return true
  }

  const downloadUrl = (url = '') => {
    const target = String(url || '').trim()
    if (!target) {
      ElMessage.warning('没有可下载的媒体')
      return
    }
    window.open(target, '_blank', 'noopener,noreferrer')
  }

  const buildMentionTokenForItem = (item) => ({
    type: 'mention',
    nodeId: item.id,
    nodeType: item.item_type,
    nodeTitleSnapshot: item.title || '',
    nodePreviewUrlSnapshot: resolveItemMediaUrl(item, 'preview'),
    nodePreviewObjectKeySnapshot: resolveObjectKeyFromItem(item)
  })

  const connectItems = async (sourceItemId, targetItemId) => {
    if (!sourceItemId || !targetItemId) return
    startConnection(sourceItemId, 'right')
    await completeConnection(targetItemId, 'left')
  }

  const createLinkedNodeFromItem = async (sourceItem, targetType, options = {}) => {
    if (!sourceItem?.id || !targetType) return null
    syncSelectedStudioDraft()
    if (dirty.value) {
      await save()
    }
    const created = await createItem(targetType, {
      title: options.title,
      position: {
        position_x: Number(options.position_x ?? sourceItem.position_x + sourceItem.width + 120),
        position_y: Number(options.position_y ?? sourceItem.position_y)
      },
      content: options.content || {},
      generation_config: {
        ...buildDefaultGenerationConfig(targetType),
        ...(options.generation_config || {})
      },
      last_run_status: options.last_run_status,
      last_output: options.last_output || {}
    })
    if (created?.id) {
      await connectItems(sourceItem.id, created.id)
      await focusCanvasItem(created)
    }
    return created
  }

  const resolvePayloadSelectedItem = (payload = {}) => {
    const itemId = String(payload.selectedItem?.id || selectedItem.value?.id || '').trim()
    if (!itemId) return null
    return items.value.find((item) => item.id === itemId) || selectedItem.value || null
  }

  const runGenerationForItem = async (targetItem, successMessage = '生成完成') => {
    if (!targetItem?.id) {
      throw new Error('目标节点不存在')
    }
    if (dirty.value) {
      await save()
    }
    const response = await generate(targetItem, buildGenerationPayload(targetItem))
    if (response?.item?.id) {
      updateItem(response.item.id, {
        content: response.item.content,
        generation_config: response.item.generation_config,
        last_run_status: response.item.last_run_status,
        last_run_error: response.item.last_run_error,
        last_output: response.item.last_output,
        is_persisted: true
      })
      await loadHistory(response.item.id)
      const refreshedItem =
        items.value.find((item) => item.id === response.item.id) ||
        response.item
      await focusCanvasItem(refreshedItem)
      await Promise.resolve()
      await setSelectionWithDraftSync(refreshedItem.id)
    }
    await save()
    ElMessage.success(response?.message || successMessage)
    return {
      ...response,
      item:
        items.value.find((item) => item.id === (response?.item?.id || targetItem.id)) ||
        response?.item ||
        targetItem
    }
  }

  const createImageFromAssistantPrompt = async (payload = {}) => {
    const prompt = String(payload.text || '').trim()
    const source = resolvePayloadSelectedItem(payload)
    if (!prompt) {
      throw new Error('助手没有可用于图片生成的 Prompt')
    }
    if (!source || source.item_type !== 'text') {
      throw new Error('请先选择一个文本节点')
    }
    const imageNode = await createLinkedNodeFromItem(source, 'image', {
      title: '助手 Prompt 生成图片',
      content: {
        prompt,
        promptTokens: [{ type: 'text', text: prompt }]
      },
      position_x: source.position_x + source.width + 140,
      position_y: source.position_y
    })
    if (!imageNode?.id) {
      throw new Error('图片节点创建失败')
    }
    await focusCanvasItem(imageNode)
    return await runGenerationForItem(imageNode, '图片生成完成')
  }

  const createVideoFromAssistantPrompt = async (payload = {}) => {
    const prompt = String(payload.text || '').trim()
    const source = resolvePayloadSelectedItem(payload)
    if (!prompt) {
      throw new Error('助手没有可用于视频生成的 Prompt')
    }
    if (!source || source.item_type !== 'image') {
      throw new Error('请先选择一个图片节点')
    }
    const videoNode = await createLinkedNodeFromItem(source, 'video', {
      title: '助手 Prompt 生成视频',
      content: {
        prompt,
        promptTokens: [
          buildMentionTokenForItem(source),
          { type: 'text', text: ` ${prompt}` }
        ]
      },
      position_x: source.position_x + source.width + 140,
      position_y: source.position_y
    })
    if (!videoNode?.id) {
      throw new Error('视频节点创建失败')
    }
    await focusCanvasItem(videoNode)
    return await runGenerationForItem(videoNode, '视频生成完成')
  }

  const parseStoryboardPrompts = (text = '') => {
    const source = String(text || '').trim()
    if (!source) return []
    const cleanLine = (line = '') =>
      String(line || '')
        .replace(/^\s*(?:[-*•]|第?\s*\d+\s*[.、:：）)]?)\s*/, '')
        .trim()
    const lineItems = source
      .split(/\r?\n+/)
      .map(cleanLine)
      .filter((line) => line.length >= 6)
    if (lineItems.length >= 3) {
      return lineItems.slice(0, 5)
    }
    return source
      .split(/(?<=[。！？!?])\s*/)
      .map(cleanLine)
      .filter((line) => line.length >= 6)
      .slice(0, 5)
  }

  const splitAssistantStoryboardPrompts = async (payload = {}) => {
    const prompts = parseStoryboardPrompts(payload.text)
    if (!prompts.length) {
      throw new Error('没有可拆分的分镜内容')
    }
    const source = resolvePayloadSelectedItem(payload)
    const basePlacement = source
      ? {
          position_x: source.position_x + source.width + 140,
          position_y: source.position_y
        }
      : getVisibleCanvasCenterPosition('text')
    const createdItems = []
    for (const [index, prompt] of prompts.entries()) {
      const item = await createItem('text', {
        title: `分镜 Prompt ${index + 1}`,
        position: {
          position_x: basePlacement.position_x + (index % 2) * 420,
          position_y: basePlacement.position_y + Math.floor(index / 2) * 280
        },
        content: {
          text: prompt,
          prompt,
          promptTokens: [{ type: 'text', text: prompt }]
        },
        last_run_status: 'completed',
        last_output: { text: prompt }
      })
      if (item?.id) {
        createdItems.push(item)
        if (source?.id && source.id !== item.id && canCreateRelation(source, item)) {
          await connectItems(source.id, item.id)
        }
      }
    }
    if (createdItems.length) {
      await save()
      await focusCanvasItem(createdItems[0])
      ElMessage.success(`已创建 ${createdItems.length} 个分镜 Prompt 节点`)
    }
    return { item: createdItems[0] || null, items: createdItems }
  }

  const historyDrawerItems = computed(() => {
    const item = historyTargetItem.value
    const histories = generationHistories[historyTargetItemId.value] || []
    return buildCanvasHistoryEntries({
      item,
      mediaType: historyDrawerMediaType.value,
      histories
    })
  })

  const normalizeAssetFile = (file = {}) => {
    const objectKey = String(file.object_key || file.storage_key || '').trim()
    const mediaType = mediaTypeFromObjectKey(objectKey)
    if (!objectKey || !mediaType) return null
    return {
      ...file,
      object_key: objectKey,
      filename: file.filename || objectKey.split('/').pop() || objectKey,
      media_type: file.media_type || mediaType,
      preview_url: file.preview_url || mediaPathForObjectKey(objectKey, 'preview'),
      download_url: file.download_url || mediaPathForObjectKey(objectKey, 'download'),
      stream_url:
        file.stream_url ||
        (mediaType === 'video' ? mediaPathForObjectKey(objectKey, 'stream') : '')
    }
  }

  const loadAssetItems = async () => {
    assetLoading.value = true
    try {
      const response = await fileService.listFiles({ page: 1, size: 100 })
      assetItems.value = (response?.files || [])
        .map(normalizeAssetFile)
        .filter(Boolean)
    } catch (error) {
      ElMessage.error(
        error?.response?.data?.detail || error?.message || '加载素材失败'
      )
    } finally {
      assetLoading.value = false
    }
  }

  const openAssetDrawer = async () => {
    assetDrawerVisible.value = true
    await loadAssetItems()
  }

  const triggerAssetUpload = () => {
    assetUploadInput.value?.click()
  }

  const handleAssetUploadChange = async (event) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return

    uploading.value = true
    try {
      const formData = new FormData()
      formData.append('file', file)
      await fileService.uploadFile(formData)
      await loadAssetItems()
      ElMessage.success('素材已上传，可加入 Canvas')
    } catch (error) {
      ElMessage.error(
        error?.response?.data?.detail || error?.message || '上传素材失败'
      )
    } finally {
      uploading.value = false
    }
  }

  const copyAssetUrl = async (asset) => {
    await copyTextToClipboard(toAbsoluteUrl(asset?.preview_url), '素材 URL 已复制')
  }

  const extractSelectedTextForLibrary = (item) => {
    if (!item) return ''
    return String(
      item.content?.text ||
        item.content?.draft_text ||
        item.content?.promptPlainText ||
        item.content?.prompt ||
        item.last_output?.text ||
        ''
    ).trim()
  }

  const saveSelectedToLibrary = async () => {
    if (!selectedItem.value) {
      ElMessage.warning('请先选择一个节点')
      return
    }
    try {
      syncSelectedStudioDraft()
      const item = selectedItem.value
      const text = item.item_type === 'text' ? extractSelectedTextForLibrary(item) : ''
      if (item.item_type === 'text' && !text) {
        ElMessage.warning('当前文本节点没有可保存内容')
        return
      }
      const objectKey = resolveObjectKeyFromItem(item)
      if (['image', 'video'].includes(item.item_type) && !objectKey) {
        ElMessage.warning('当前媒体节点没有可保存的 object_key')
        return
      }

      const patch = {
        content: {
          ...item.content,
          saved_to_library: true,
          library_title: item.title || (item.item_type === 'text' ? 'Prompt 素材' : '媒体素材'),
          library_saved_at: new Date().toISOString()
        }
      }
      if (item.item_type === 'text') {
        patch.last_run_status = item.last_run_status || 'completed'
        patch.last_output = { ...(item.last_output || {}), text }
      }
      updateItem(item.id, patch)
      await save()
      await loadAssetItems()
      ElMessage.success(
        item.item_type === 'text'
          ? '文本/Prompt 已保存到素材库'
          : '媒体已在素材库可见，并已标记保存'
      )
    } catch (error) {
      ElMessage.error(
        error?.response?.data?.detail || error?.message || '保存到素材库失败'
      )
    }
  }

  const getVisibleCanvasCenterPosition = (nodeType = 'image') => {
    const size =
      nodeType === 'video'
        ? { width: 420, height: 260 }
        : nodeType === 'text'
          ? { width: 320, height: 220 }
        : { width: 360, height: 260 }
    const safeScale = Math.max(Number(zoom.value || 1), 0.1)
    const visibleWidth =
      Number(viewport.width || 0) ||
      stageShellRef.value?.getBoundingClientRect?.().width ||
      960
    const visibleHeight =
      Number(viewport.height || 0) ||
      stageShellRef.value?.getBoundingClientRect?.().height ||
      720

    return {
      position_x:
        (visibleWidth / 2 - Number(pan.value?.x || 0)) / safeScale -
        size.width / 2,
      position_y:
        (visibleHeight / 2 - Number(pan.value?.y || 0)) / safeScale -
        size.height / 2,
      width: size.width,
      height: size.height
    }
  }

  const focusCanvasItem = async (item) => {
    if (!item?.id) return
    await setSelectionWithDraftSync(item.id)

    const visibleWidth =
      Number(viewport.width || 0) ||
      stageShellRef.value?.getBoundingClientRect?.().width ||
      960
    const visibleHeight =
      Number(viewport.height || 0) ||
      stageShellRef.value?.getBoundingClientRect?.().height ||
      720
    const safeScale = Math.max(Number(zoom.value || 1), 0.1)
    const itemCenterX =
      Number(item.position_x || 0) + Number(item.width || 0) / 2
    const itemCenterY =
      Number(item.position_y || 0) + Number(item.height || 0) / 2

    const nextPan = {
      x: visibleWidth / 2 - itemCenterX * safeScale,
      y: visibleHeight / 2 - itemCenterY * safeScale
    }
    updateViewport({
      zoom: safeScale,
      pan: nextPan
    })
    viewportCommand.value = {
      id: `${item.id}-${Date.now()}`,
      x: nextPan.x,
      y: nextPan.y,
      scale: safeScale
    }
  }

  const focusRouteItemIfPresent = async () => {
    const itemId = String(route.query.item_id || route.query.itemId || '').trim()
    if (!itemId) return
    const targetItem = items.value.find((item) => item.id === itemId)
    if (!targetItem) {
      return
    }
    await focusCanvasItem(targetItem)
  }

  const normalizeEntryMode = () => {
    const rawMode = Array.isArray(route.query.mode)
      ? route.query.mode[0]
      : route.query.mode
    return String(rawMode || '').trim()
  }

  const shouldForceEntryMode = () =>
    String(
      Array.isArray(route.query.force) ? route.query.force[0] : route.query.force || ''
    ).trim() === '1'

  const clearEntryModeQuery = async () => {
    if (!route.query.mode && !route.query.force) return
    const nextQuery = { ...route.query }
    delete nextQuery.mode
    delete nextQuery.force
    await router.replace({
      name: route.name || 'CanvasEditor',
      params: route.params,
      query: nextQuery
    })
  }

  const hasStarterForMode = (mode) =>
    items.value.some(
      (item) =>
        item.item_type === 'text' &&
        item.content?.phase1e_starter === true &&
        item.content?.starter_mode === mode
    )

  const initializeEntryModeIfPresent = async () => {
    const mode = normalizeEntryMode()
    if (!mode || (!entryModeConfigs[mode] && !entryAssetModeMessages[mode])) {
      return
    }
    if (route.query.item_id || route.query.itemId) {
      return
    }

    const canvasId = String(document.value?.id || route.params.canvasId || '').trim()
    if (!canvasId || loading.value) return

    const force = shouldForceEntryMode()
    const entryKey = `${canvasId}:${mode}:${force ? 'force' : 'normal'}`
    if (handledEntryModeKeys.has(entryKey)) {
      await clearEntryModeQuery()
      return
    }
    handledEntryModeKeys.add(entryKey)

    try {
      if (entryAssetModeMessages[mode]) {
        await openAssetDrawer()
        ElMessage.success(entryAssetModeMessages[mode])
        return
      }

      if (!force && (items.value.length > 0 || hasStarterForMode(mode))) {
        return
      }

      const config = entryModeConfigs[mode]
      const placement = getVisibleCanvasCenterPosition('text')
      const item = await createItem('text', {
        title: config.title,
        position: {
          position_x: placement.position_x,
          position_y: placement.position_y
        },
        width: placement.width,
        height: placement.height,
        content: {
          text: config.text,
          text_preview: config.text,
          prompt: config.text,
          promptTokens: [{ type: 'text', text: config.text }],
          phase1e_starter: true,
          starter_mode: mode
        }
      })
      if (item?.id) {
        await focusCanvasItem(item)
        ElMessage.success(config.successMessage)
      }
    } catch (error) {
      ElMessage.error(
        error?.response?.data?.detail || error?.message || '初始化创作入口失败'
      )
    } finally {
      await clearEntryModeQuery()
    }
  }

  const openCanvasTasks = () => {
    const canvasId = String(document.value?.id || route.params.canvasId || '').trim()
    router.push({
      name: 'TasksHistoryPage',
      query: canvasId ? { canvas_id: canvasId } : {}
    })
  }

  const addAssetToCanvas = async (asset) => {
    if (!asset?.object_key || !asset.media_type) return
    try {
      const type = asset.media_type
      const objectKey = asset.object_key
      const placement = getVisibleCanvasCenterPosition(type)
      const content =
        type === 'image'
          ? {
              result_image_object_key: objectKey,
              prompt: asset.filename || '',
              promptTokens: asset.filename
                ? [{ type: 'text', text: asset.filename }]
                : []
            }
          : {
              result_video_object_key: objectKey,
              prompt: asset.filename || '',
              promptTokens: asset.filename
                ? [{ type: 'text', text: asset.filename }]
                : []
            }
      const item = await createItem(type, {
        title: asset.filename || (type === 'image' ? '素材图片' : '素材视频'),
        position: {
          position_x: placement.position_x,
          position_y: placement.position_y
        },
        width: placement.width,
        height: placement.height,
        content,
        last_run_status: 'completed',
        last_output:
          type === 'image'
            ? { result_image_object_key: objectKey }
            : { result_video_object_key: objectKey },
        generation_config: buildDefaultGenerationConfig(type)
      })
      if (item?.id) {
        await focusCanvasItem(item)
        assetDrawerVisible.value = false
        ElMessage.success('已加入画布，并定位到新节点')
      }
    } catch (error) {
      ElMessage.error(
        error?.response?.data?.detail || error?.message || '素材加入 Canvas 失败'
      )
    }
  }

  const setSelectedAsRelationSource = () => {
    if (!canUseAsRelationSource(selectedItem.value)) {
      ElMessage.warning('只有文本或图片节点可以作为来源')
      return
    }
    relationSourceItemId.value = selectedItem.value.id
    ElMessage.success('已设为来源，请选择目标节点后点击关联')
  }

  const clearRelationSource = () => {
    relationSourceItemId.value = ''
  }

  const linkRelationSourceToSelected = async () => {
    await linkRelationSourceToItem(selectedItem.value)
  }

  const linkRelationSourceToItem = async (target) => {
    const source = relationSourceItem.value
    if (!source || !target) return
    await createRelationBetweenItems(source, target)
  }

  const linkItemToSelected = async (source) => {
    await createRelationBetweenItems(source, selectedItem.value)
  }

  const createRelationBetweenItems = async (source, target) => {
    if (!source || !target) return
    if (!canCreateRelation(source, target)) {
      ElMessage.warning('当前来源和目标类型不支持建立该关系')
      return
    }
    if (relationExists(source.id, target.id)) {
      ElMessage.info('该来源关系已存在')
      relationSourceItemId.value = ''
      return
    }
    try {
      syncSelectedStudioDraft()
      startConnection(source.id, 'right')
      await completeConnection(target.id, 'left')
      relationSourceItemId.value = ''
      selectedConnectionId.value = null
      await setSelectionWithDraftSync(target.id)
      ElMessage.success('来源关系已建立')
    } catch (error) {
      ElMessage.error(
        error?.response?.data?.detail || error?.message || '建立来源关系失败'
      )
    }
  }

  const hydrateCanvasConfigCatalog = async () => {
    catalogLoading.value = true
    try {
      const [apiKeysResponse, modelCatalogResponse] = await Promise.all([
        apiKeysService.getAPIKeys({ page: 1, size: 100, key_status: 'active' }),
        canvasService.getModelCatalog()
      ])

      apiKeyOptions.value = (apiKeysResponse?.api_keys || []).map((key) => ({
        value: key.id,
        label: `${key.name} (${key.provider})`
      }))

      modelCatalog.value = {
        text: Array.isArray(modelCatalogResponse?.text)
          ? modelCatalogResponse.text
          : [],
        image: Array.isArray(modelCatalogResponse?.image)
          ? modelCatalogResponse.image
          : [],
        video: Array.isArray(modelCatalogResponse?.video)
          ? modelCatalogResponse.video
          : []
      }
    } catch (error) {
      console.error('Load canvas config catalog failed', error)
      apiKeyOptions.value = []
      modelCatalog.value = { text: [], image: [], video: [] }
      ElMessage.warning('加载画布模型目录失败')
    } finally {
      catalogLoading.value = false
    }
  }

  const buildItemMap = (itemsList = []) =>
    itemsList.reduce((accumulator, item) => {
      accumulator[item.id] = item
      return accumulator
    }, {})

  const resolvePromptMentions = (tokens = [], itemMap = {}) =>
    tokens
      .filter((token) => token.type === 'mention')
      .map((token) => {
        const item = itemMap[token.nodeId]
        if (!item) {
          return {
            mentionId: token.mentionId,
            nodeId: token.nodeId,
            nodeType: token.nodeType,
            nodeTitle: token.nodeTitleSnapshot || '',
            resolvedContent: null,
            status: 'missing'
          }
        }

        if (token.nodeType === 'text' && item.item_type === 'text') {
          const text = String(
            item.content?.text || item.content?.text_preview || ''
          )
          return {
            mentionId: token.mentionId,
            nodeId: token.nodeId,
            nodeType: token.nodeType,
            nodeTitle: item.title || token.nodeTitleSnapshot || '',
            resolvedContent: {
              text,
              length: text.length
            },
            status: text ? 'resolved' : 'missing'
          }
        }

        if (token.nodeType === 'image' && item.item_type === 'image') {
          const objectKey = String(
            item.content?.result_image_object_key ||
              item.content?.reference_image_object_key ||
              item.content?.result_image_key ||
              item.content?.object_key ||
              item.content?.objectKey ||
              ''
          )
          const previewUrl = resolveImagePreviewUrl(
            item.content,
            imageUploadPreviewMap.value[item.id] || ''
          )
          return {
            mentionId: token.mentionId,
            nodeId: token.nodeId,
            nodeType: token.nodeType,
            nodeTitle: item.title || token.nodeTitleSnapshot || '',
            resolvedContent: {
              object_key: objectKey,
              objectKey,
              url: previewUrl,
              width: Number(item.width || 0),
              height: Number(item.height || 0)
            },
            status: objectKey || previewUrl ? 'resolved' : 'missing'
          }
        }

        return {
          mentionId: token.mentionId,
          nodeId: token.nodeId,
          nodeType: token.nodeType,
          nodeTitle: item.title || token.nodeTitleSnapshot || '',
          resolvedContent: null,
          status: 'invalid_type'
        }
      })

  const availableReferenceItems = computed(() => {
    if (!selectedItem.value) return []
    const visited = new Set()
    const queue = [
      ...(reverseConnectionMap.value.get(selectedItem.value.id) || [])
    ]
    const references = []
    while (queue.length) {
      const currentId = queue.shift()
      if (!currentId || visited.has(currentId)) continue
      visited.add(currentId)
      const item = items.value.find((entry) => entry.id === currentId)
      if (item && ['text', 'image'].includes(item.item_type)) {
        references.push(buildReferenceItem(item))
      }
      ;(reverseConnectionMap.value.get(currentId) || []).forEach(
        (upstreamId) => {
          if (!visited.has(upstreamId)) {
            queue.push(upstreamId)
          }
        }
      )
    }
    return references
  })

  const globalReferenceItems = computed(() =>
    items.value
      .filter(
        (item) =>
          item.id !== selectedItem.value?.id &&
          ['text', 'image'].includes(item.item_type)
      )
      .map(buildReferenceItem)
  )

  const videoReferenceHint = computed(() => {
    if (!selectedItem.value || selectedItem.value.item_type !== 'video')
      return ''
    const imageCount = availableReferenceItems.value.filter(
      (item) => item.item_type === 'image'
    ).length
    const textCount = availableReferenceItems.value.filter(
      (item) => item.item_type === 'text'
    ).length
    return `上游可引用 ${imageCount} 个图片节点，${textCount} 个文本节点。视频生成会自动带上上游图片 URL。`
  })

  const zoomHintText = computed(
    () =>
      `缩放 ${Math.round(zoom.value * 100)}%，左键拖动画布平移，按住 Shift 左键拖拽框选节点。`
  )
  const linkModeText = computed(() => {
    if (!linkDrag.value) return ''
    return '拖到目标节点上完成连线，在线路空白处松开可直接创建下游节点。'
  })

  const connectionActionPosition = computed(() => {
    if (!selectedConnection.value) {
      return null
    }
    const source = items.value.find(
      (item) => item.id === selectedConnection.value.source_item_id
    )
    const target = items.value.find(
      (item) => item.id === selectedConnection.value.target_item_id
    )
    if (!source || !target) {
      return null
    }
    const sourceX =
      source.position_x +
      (selectedConnection.value.source_handle === 'left' ? 0 : source.width)
    const sourceY = source.position_y + source.height / 2
    const targetX =
      target.position_x +
      (selectedConnection.value.target_handle === 'right' ? target.width : 0)
    const targetY = target.position_y + target.height / 2
    return {
      x: ((sourceX + targetX) / 2) * zoom.value + pan.value.x,
      y: ((sourceY + targetY) / 2) * zoom.value + pan.value.y
    }
  })

  const dragPath = computed(() => {
    if (!linkDrag.value) return ''
    const startScreenX = linkDrag.value.startCanvasX * zoom.value + pan.value.x
    const startScreenY = linkDrag.value.startCanvasY * zoom.value + pan.value.y
    const endScreenX = linkDrag.value.currentScreenX
    const endScreenY = linkDrag.value.currentScreenY
    const delta = Math.max(80, Math.abs(endScreenX - startScreenX) / 2)
    return `M ${startScreenX} ${startScreenY} C ${startScreenX + delta} ${startScreenY}, ${endScreenX - delta} ${endScreenY}, ${endScreenX} ${endScreenY}`
  })

  const getCanvasPointFromMouse = (event) => {
    const rect = stageShellRef.value?.getBoundingClientRect()
    if (!rect) {
      return { screenX: 0, screenY: 0, canvasX: 0, canvasY: 0 }
    }
    const screenX = event.clientX - rect.left
    const screenY = event.clientY - rect.top
    return {
      screenX,
      screenY,
      canvasX: (screenX - pan.value.x) / zoom.value,
      canvasY: (screenY - pan.value.y) / zoom.value
    }
  }

  const clampCanvasPosition = (x, y) => ({
    x: Math.max(0, Number(x || 0)),
    y: Math.max(0, Number(y || 0))
  })

  const resolveHandleCanvasPoint = (item, handle) => ({
    x: handle === 'left' ? item.position_x : item.position_x + item.width,
    y: item.position_y + item.height / 2
  })

  const findItemAtCanvasPoint = (canvasX, canvasY, ignoreItemId = '') =>
    [...items.value]
      .sort((a, b) => (b.z_index || 0) - (a.z_index || 0))
      .find((item) => {
        if (item.id === ignoreItemId) return false
        return (
          canvasX >= item.position_x &&
          canvasX <= item.position_x + item.width &&
          canvasY >= item.position_y &&
          canvasY <= item.position_y + item.height
        )
      }) || null

  const closeLinkMenu = () => {
    linkMenu.visible = false
    linkMenu.screenX = 0
    linkMenu.screenY = 0
    linkMenu.canvasX = 0
    linkMenu.canvasY = 0
    linkMenu.sourceItemId = ''
    linkMenu.sourceHandle = 'right'
  }

  const startLinkDrag = (item, handle, event) => {
    event?.preventDefault?.()
    const pointer = getCanvasPointFromMouse(event)
    const startPoint = resolveHandleCanvasPoint(item, handle)
    linkDrag.value = {
      sourceItemId: item.id,
      sourceHandle: handle,
      startCanvasX: startPoint.x,
      startCanvasY: startPoint.y,
      currentScreenX: pointer.screenX,
      currentScreenY: pointer.screenY,
      currentCanvasX: pointer.canvasX,
      currentCanvasY: pointer.canvasY
    }
    closeLinkMenu()
    window.addEventListener('mousemove', handleGlobalPointerMove)
    window.addEventListener('mouseup', handleGlobalPointerUp)
  }

  const handleGlobalPointerMove = (event) => {
    if (linkDrag.value || studioDrag.value) {
      event?.preventDefault?.()
    }
    const point = getCanvasPointFromMouse(event)

    if (linkDrag.value) {
      linkDrag.value = {
        ...linkDrag.value,
        currentScreenX: point.screenX,
        currentScreenY: point.screenY,
        currentCanvasX: point.canvasX,
        currentCanvasY: point.canvasY
      }
    }

    if (studioDrag.value) {
      const nextPosition = clampCanvasPosition(
        point.canvasX - studioDrag.value.pointerOffsetX,
        point.canvasY - studioDrag.value.pointerOffsetY
      )
      updateItem(studioDrag.value.itemId, {
        position_x: nextPosition.x,
        position_y: nextPosition.y
      })
    }
  }

  const handleGlobalPointerUp = async () => {
    if (studioDrag.value) {
      studioDrag.value = null
    }

    if (linkDrag.value) {
      const sourceItemId = linkDrag.value.sourceItemId
      const sourceHandle = linkDrag.value.sourceHandle
      const targetItem = findItemAtCanvasPoint(
        linkDrag.value.currentCanvasX,
        linkDrag.value.currentCanvasY,
        sourceItemId
      )
      try {
        if (targetItem) {
          const targetHandle =
            linkDrag.value.currentCanvasX <
            targetItem.position_x + targetItem.width / 2
              ? 'left'
              : 'right'
          startConnection(sourceItemId, sourceHandle)
          await completeConnection(targetItem.id, targetHandle)
          await setSelectionWithDraftSync(targetItem.id)
        } else {
          linkMenu.visible = true
          linkMenu.screenX = linkDrag.value.currentScreenX
          linkMenu.screenY = linkDrag.value.currentScreenY
          linkMenu.canvasX = linkDrag.value.currentCanvasX
          linkMenu.canvasY = linkDrag.value.currentCanvasY
          linkMenu.sourceItemId = sourceItemId
          linkMenu.sourceHandle = sourceHandle
        }
      } catch (error) {
        ElMessage.error(
          error?.response?.data?.detail || error?.message || '创建连线失败'
        )
      } finally {
        linkDrag.value = null
        window.removeEventListener('mousemove', handleGlobalPointerMove)
        window.removeEventListener('mouseup', handleGlobalPointerUp)
      }
      return
    }

    window.removeEventListener('mousemove', handleGlobalPointerMove)
    window.removeEventListener('mouseup', handleGlobalPointerUp)
  }

  const patchSelected = (patch) => {
    if (!selectedItem.value) return
    updateItem(selectedItem.value.id, patch)
  }

  const patchSelectedContent = (patch) => {
    if (!selectedItem.value) return
    updateItem(selectedItem.value.id, {
      content: {
        ...selectedItem.value.content,
        ...patch
      }
    })
  }

  const patchGenerationConfig = (patch) => {
    if (!selectedItem.value) return
    updateItem(selectedItem.value.id, {
      generation_config: {
        ...selectedItem.value.generation_config,
        ...patch
      }
    })
  }

  const updatePromptTokens = (tokens) => {
    if (!selectedItem.value) return
    patchSelectedContent(normalizePromptTokens(tokens))
  }

  const createNode = async (type) => {
    try {
      syncSelectedStudioDraft()
      const item = await createItem(type, {
        generation_config: buildDefaultGenerationConfig(type)
      })
      closeLinkMenu()
      if (item?.id) {
        await setSelectionWithDraftSync(item.id)
      }
    } catch (error) {
      ElMessage.error(
        error?.response?.data?.detail || error?.message || '创建节点失败'
      )
    }
  }

  const createImageFromTextNode = async () => {
    if (!selectedItem.value || selectedItem.value.item_type !== 'text') return
    try {
      const source = selectedItem.value
      const sourceText = String(
        source.content?.text ||
          source.content?.prompt ||
          source.content?.text_preview ||
          ''
      ).trim()
      await createLinkedNodeFromItem(source, 'image', {
        title: '由文本生成图片',
        content: {
          prompt: sourceText,
          promptTokens: [buildMentionTokenForItem(source)]
        }
      })
      ElMessage.success('已创建图片下游节点')
    } catch (error) {
      ElMessage.error(
        error?.response?.data?.detail || error?.message || '创建图片下游节点失败'
      )
    }
  }

  const createVideoFromTextNode = async () => {
    if (!selectedItem.value || selectedItem.value.item_type !== 'text') return
    try {
      const source = selectedItem.value
      const sourceText = String(
        source.content?.text ||
          source.content?.prompt ||
          source.content?.text_preview ||
          ''
      ).trim()
      await createLinkedNodeFromItem(source, 'video', {
        title: '由文本生成视频',
        content: {
          prompt: sourceText,
          promptTokens: [buildMentionTokenForItem(source)]
        }
      })
      ElMessage.success('已创建视频下游节点')
    } catch (error) {
      ElMessage.error(
        error?.response?.data?.detail || error?.message || '创建视频下游节点失败'
      )
    }
  }

  const createVideoFromImageNode = async () => {
    if (!selectedItem.value || selectedItem.value.item_type !== 'image') return
    try {
      const source = selectedItem.value
      await createLinkedNodeFromItem(source, 'video', {
        title: '由图片生成视频',
        content: {
          prompt: String(source.content?.prompt || source.title || '').trim(),
          promptTokens: [buildMentionTokenForItem(source)]
        }
      })
      ElMessage.success('已创建图生视频节点')
    } catch (error) {
      ElMessage.error(
        error?.response?.data?.detail || error?.message || '创建图生视频节点失败'
      )
    }
  }

  const copySelectedMediaUrl = async () => {
    await copyTextToClipboard(
      toAbsoluteUrl(resolveItemMediaUrl(selectedItem.value, 'preview')),
      '媒体 URL 已复制'
    )
  }

  const downloadSelectedMedia = () => {
    downloadUrl(resolveItemMediaUrl(selectedItem.value, 'download'))
  }

  const writeAssistantTextToSelected = async (text = '') => {
    const value = String(text || '').trim()
    if (!value) {
      ElMessage.warning('助手没有可写回的内容')
      return
    }
    if (!selectedItem.value || selectedItem.value.item_type !== 'text') {
      await createAssistantTextNode(value)
      return
    }
    patchSelectedContent({
      text: value,
      prompt: value,
      promptTokens: [{ type: 'text', text: value }]
    })
    await save()
    ElMessage.success('助手结果已写入当前文本节点')
  }

  const createAssistantTextNode = async (text = '') => {
    const value = String(text || '').trim()
    if (!value) {
      ElMessage.warning('助手没有可写回的内容')
      return
    }
    const source = selectedItem.value
    const item = await createItem('text', {
      title: '助手建议',
      position: {
        position_x: source ? source.position_x + source.width + 120 : 180,
        position_y: source ? source.position_y : 180
      },
      content: {
        text: value,
        prompt: value,
        promptTokens: [{ type: 'text', text: value }]
      },
      last_run_status: 'completed',
      last_output: { text: value }
    })
    if (item?.id) {
      if (source?.id) {
        await connectItems(source.id, item.id)
      }
      await setSelectionWithDraftSync(item.id)
      ElMessage.success('助手结果已创建为文本节点')
    }
  }

  const handleCreateLinkedNode = async (type) => {
    try {
      syncSelectedStudioDraft()
      const item = await createItem(type, {
        position: {
          position_x: Math.max(40, linkMenu.canvasX),
          position_y: Math.max(40, linkMenu.canvasY)
        },
        generation_config: buildDefaultGenerationConfig(type)
      })
      if (!item?.id) {
        return
      }
      startConnection(linkMenu.sourceItemId, linkMenu.sourceHandle)
      await completeConnection(item.id, 'left')
      await setSelectionWithDraftSync(item.id)
      closeLinkMenu()
    } catch (error) {
      ElMessage.error(
        error?.response?.data?.detail || error?.message || '创建下游节点失败'
      )
    }
  }

  const handleRemoveSelectedConnection = async () => {
    if (!selectedConnection.value) return
    try {
      await removeConnection(selectedConnection.value.id)
      selectedConnectionId.value = null
    } catch (error) {
      ElMessage.error(
        error?.response?.data?.detail || error?.message || '删除连线失败'
      )
    }
  }

  const handleStageClick = async () => {
    await clearSelectionWithDraftSync()
    selectedConnectionId.value = null
    closeLinkMenu()
  }

  const handleItemClick = async (item) => {
    await setSelectionWithDraftSync(item.id)
    selectedConnectionId.value = null
    closeLinkMenu()
  }

  const handleConnectionClick = async (connection) => {
    syncSelectedStudioDraft()
    selectedConnectionId.value = connection.id
    clearSelection()
    closeLinkMenu()
  }

  const handleItemDragEnd = ({ id, positionX, positionY }) => {
    updateItem(id, { position_x: positionX, position_y: positionY })
  }

  const handleItemResizeSuggest = ({ id, width, height }) => {
    const item = items.value.find((entry) => entry.id === id)
    if (!item) {
      return
    }
    if (
      Math.abs(Number(item.width || 0) - Number(width || 0)) < 2 &&
      Math.abs(Number(item.height || 0) - Number(height || 0)) < 2
    ) {
      return
    }
    updateItem(id, { width, height })
  }

  const handleViewportChange = ({ x, y, scale, width, height }) => {
    updateViewport({ zoom: scale, pan: { x, y } })
    viewport.width = width
    viewport.height = height
  }

  const handleStageHandlePointerDown = ({ item, handle, event }) => {
    startLinkDrag(item, handle, event.evt)
  }

  const syncSelectedStudioDraft = () => {
    if (!selectedItem.value) {
      return
    }

    if (selectedItem.value.item_type === 'text') {
      textStudioRef.value?.flushDraft?.()
      return
    }

    if (selectedItem.value.item_type === 'image') {
      imageStudioRef.value?.flushDraft?.()
      return
    }

    if (selectedItem.value.item_type === 'video') {
      videoStudioRef.value?.flushDraft?.()
    }
  }

  const setSelectionWithDraftSync = async (itemId) => {
    if (itemId === selectedItem.value?.id) {
      setSelection(itemId)
      return
    }

    syncSelectedStudioDraft()
    await Promise.resolve()
    setSelection(itemId)
  }

  const clearSelectionWithDraftSync = async () => {
    syncSelectedStudioDraft()
    await Promise.resolve()
    clearSelection()
  }

  const shouldIgnoreDeleteShortcut = (event) => {
    if (!event) return true
    if (event.ctrlKey || event.metaKey || event.altKey) {
      return true
    }
    const target = event.target
    if (!target) {
      return false
    }
    const tagName = String(target.tagName || '').toLowerCase()
    return (
      target.isContentEditable ||
      ['input', 'textarea', 'select', 'button'].includes(tagName)
    )
  }

  const pruneRemovedItemArtifacts = (itemIds = []) => {
    const removedIdSet = new Set(itemIds)
    const nextPreviewMap = { ...styleReferencePreviewMap.value }
    const nextImagePreviewMap = { ...imageUploadPreviewMap.value }
    removedIdSet.forEach((itemId) => {
      delete nextPreviewMap[itemId]
      delete nextImagePreviewMap[itemId]
    })
    if (relationSourceItemId.value && removedIdSet.has(relationSourceItemId.value)) {
      relationSourceItemId.value = ''
    }
    styleReferencePreviewMap.value = nextPreviewMap
    imageUploadPreviewMap.value = nextImagePreviewMap
    if (historyTargetItemId.value && removedIdSet.has(historyTargetItemId.value)) {
      historyDrawerVisible.value = false
      historyTargetItemId.value = ''
      historySelectingId.value = ''
    }
  }

  const confirmDeleteItems = async (itemIds = []) => {
    const count = itemIds.length
    if (!count) {
      return false
    }
    const message =
      count === 1
        ? '确认删除该节点吗？'
        : `确认删除已选中的 ${count} 个节点吗？`
    await ElMessageBox.confirm(message, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
    return true
  }

  const requestDeleteItems = async (itemIds = []) => {
    const normalizedIds = [...new Set((itemIds || []).filter(Boolean))]
    if (!normalizedIds.length) {
      return
    }
    try {
      await confirmDeleteItems(normalizedIds)
      syncSelectedStudioDraft()
      await removeItems(normalizedIds)
      pruneRemovedItemArtifacts(normalizedIds)
      selectedConnectionId.value = null
      closeLinkMenu()
    } catch (error) {
      if (error === 'cancel' || error === 'close' || error?.message === 'cancel') {
        return
      }
      ElMessage.error(
        error?.response?.data?.detail || error?.message || '删除节点失败'
      )
    }
  }

  const handleKeydown = (event) => {
    if (!['Delete', 'Backspace'].includes(String(event?.key || ''))) {
      return
    }
    if (shouldIgnoreDeleteShortcut(event)) {
      return
    }
    if (!selectedItemIds.value.length) {
      return
    }
    event.preventDefault()
    void requestDeleteItems(selectedItemIds.value)
  }

  const handleFocusItem = async (itemId) => {
    await setSelectionWithDraftSync(itemId)
  }

  const handleStudioHandleDrag = (event, handle) => {
    if (!selectedItem.value) return
    startLinkDrag(selectedItem.value, handle, event)
  }

  const startStudioNodeDrag = (event) => {
    if (!selectedItem.value) {
      return
    }

    event?.preventDefault?.()
    const point = getCanvasPointFromMouse(event)
    studioDrag.value = {
      itemId: selectedItem.value.id,
      pointerOffsetX: point.canvasX - selectedItem.value.position_x,
      pointerOffsetY: point.canvasY - selectedItem.value.position_y
    }
    closeLinkMenu()
    window.addEventListener('mousemove', handleGlobalPointerMove)
    window.addEventListener('mouseup', handleGlobalPointerUp)
  }

  const handleSelectionBoxEnd = ({ bounds, appendToSelection }) => {
    const hitItems = items.value.filter(
      (item) =>
        item.position_x < bounds.right &&
        item.position_x + item.width > bounds.left &&
        item.position_y < bounds.bottom &&
        item.position_y + item.height > bounds.top
    )
    if (hitItems.length > 1) {
      syncSelectedStudioDraft()
      setSelections(hitItems.map((item) => item.id))
      selectedConnectionId.value = null
    } else if (hitItems.length === 1) {
      void setSelectionWithDraftSync(hitItems[0].id)
      selectedConnectionId.value = null
    } else if (!appendToSelection) {
      void clearSelectionWithDraftSync()
    }
  }

  const buildGenerationPayload = (item) => {
    const promptTokens = item.content?.promptTokens || []
    const resolvedMentions = resolvePromptMentions(
      promptTokens,
      buildItemMap(items.value)
    )
    let effectiveItem = item

    if (item.item_type === 'video') {
      const referencePatch = {
        reference_image_urls: resolvedMentions
          .filter(
            (reference) =>
              reference.nodeType === 'image' && reference.status === 'resolved'
          )
          .map(
            (reference) =>
              reference.resolvedContent?.object_key ||
              reference.resolvedContent?.url ||
              ''
          )
          .filter(Boolean),
        reference_text_ids: resolvedMentions
          .filter(
            (reference) =>
              reference.nodeType === 'text' && reference.status === 'resolved'
          )
          .map((reference) => reference.nodeId)
      }
      effectiveItem = {
        ...item,
        content: {
          ...(item.content || {}),
          ...referencePatch
        }
      }
      updateItem(item.id, { content: effectiveItem.content }, { persist: false })
    }

    return buildCanvasGenerationPayload({
      item: effectiveItem,
      resolvedMentions,
      resolveImageReferenceObjectKey,
      resolveStyleReferenceImageObjectKey
    })
  }

  const handleGenerate = async () => {
    if (!selectedItem.value) return
    const targetItem = selectedItem.value
    const targetItemId = String(targetItem.id || '').trim()
    try {
      syncSelectedStudioDraft()
      if (dirty.value) {
        await save()
      }
      const response = await generate(
        targetItem,
        buildGenerationPayload(targetItem)
      )
      ElMessage.success(response.message || '生成任务已提交')
      if (targetItemId) {
        await loadHistory(targetItemId)
      }
      if (response?.item?.id) {
        updateItem(response.item.id, {
          content: response.item.content,
          generation_config: response.item.generation_config,
          last_run_status: response.item.last_run_status,
          last_run_error: response.item.last_run_error,
          last_output: response.item.last_output,
          is_persisted: true
        })
      }
    } catch (error) {
      ElMessage.error(
        error?.response?.data?.detail || error?.message || '生成提交失败'
      )
    }
  }

  const uploadMedia = async (file, type) => {
    if (!selectedItem.value || !file) return
    uploading.value = true
    try {
      if (type === 'image') {
        const formData = new FormData()
        formData.append('file', file)
        const response = await fileService.uploadFile(formData)
        const objectKey =
          response?.storage_info?.object_key ||
          response?.data?.storage_key ||
          ''
        const fileUrl = response?.storage_info?.url || response?.data?.url || ''
        if (!objectKey) {
          ElMessage.warning('上传成功，但没有拿到图片存储键')
          return
        }
        if (fileUrl) {
          imageUploadPreviewMap.value = {
            ...imageUploadPreviewMap.value,
            [selectedItem.value.id]: fileUrl
          }
          updateItem(
            selectedItem.value.id,
            {
              content: {
                reference_image_object_key: objectKey,
                reference_image_url: fileUrl
              }
            },
            { persist: false }
          )
        }
        patchSelectedContent({
          reference_image_object_key: objectKey
        })
      } else {
        const formDataForCanvas = new FormData()
        formDataForCanvas.append('file', file)
        const canvasResponse = await canvasService.uploadVideo(
          document.value.id,
          selectedItem.value.id,
          formDataForCanvas
        )
        updateItem(selectedItem.value.id, {
          content: canvasResponse.item.content,
          generation_config: canvasResponse.item.generation_config,
          last_run_status: canvasResponse.item.last_run_status,
          last_run_error: canvasResponse.item.last_run_error,
          last_output: canvasResponse.item.last_output
        })
      }
      ElMessage.success('文件已上传')
    } finally {
      uploading.value = false
    }
  }

  const uploadStyleReference = async (file) => {
    if (
      !selectedItem.value ||
      selectedItem.value.item_type !== 'image' ||
      !file
    )
      return
    uploading.value = true
    try {
      const formData = new FormData()
      formData.append('file', file)
      const response = await fileService.uploadFile(formData)
      const objectKey =
        response?.storage_info?.object_key || response?.data?.storage_key || ''
      const previewUrl =
        response?.storage_info?.url || response?.data?.url || ''
      if (!objectKey) {
        ElMessage.warning('上传成功，但没有拿到风格参考图存储键')
        return
      }
      styleReferencePreviewMap.value = {
        ...styleReferencePreviewMap.value,
        [selectedItem.value.id]: {
          name: file.name || '已选择风格参考',
          url: previewUrl
        }
      }
      patchSelectedContent({
        style_reference_image_object_key: objectKey
      })
      ElMessage.success('风格参考图已上传')
    } finally {
      uploading.value = false
    }
  }

  const clearStyleReference = () => {
    if (!selectedItem.value || selectedItem.value.item_type !== 'image') return
    const nextPreviewMap = { ...styleReferencePreviewMap.value }
    delete nextPreviewMap[selectedItem.value.id]
    styleReferencePreviewMap.value = nextPreviewMap
    patchSelectedContent({
      style_reference_image_object_key: ''
    })
  }

  const openHistoryDrawer = async (item = selectedItem.value) => {
    if (!item?.id || !['image', 'video'].includes(item.item_type)) {
      return
    }
    historyTargetItemId.value = item.id
    historyTargetMediaType.value = item.item_type
    historyDrawerVisible.value = true
    await loadHistory(item.id)
  }

  const refreshHistory = async () => {
    if (!historyTargetItemId.value) return
    await loadHistory(historyTargetItemId.value)
  }

  const handleHistorySelect = async (history) => {
    const targetItem = historyTargetItem.value
    const generationId = String(history?.id || '').trim()
    if (!targetItem?.id || !generationId) {
      return
    }

    historySelectingId.value = generationId
    try {
      syncSelectedStudioDraft()
      if (dirty.value) {
        await save()
      }
      await applyGeneration(targetItem, generationId)
      ElMessage.success('已切换到选中的历史版本')
    } catch (error) {
      ElMessage.error(
        error?.response?.data?.detail || error?.message || '切换历史版本失败'
      )
    } finally {
      historySelectingId.value = ''
    }
  }

  const removeSelectedItem = async () => {
    if (!selectedItemIds.value.length) return
    await requestDeleteItems(selectedItemIds.value)
  }

  const handleBeforeUnload = (event) => {
    if (!dirty.value) return
    event.preventDefault()
    event.returnValue = ''
  }

  watch(
    () => selectedItem.value?.id,
    async (itemId) => {
      if (itemId && selectedItem.value?.is_persisted) {
        selectedConnectionId.value = null
        await loadHistory(itemId)
      }
    },
    { immediate: true }
  )

  watch(historyTargetItem, (item) => {
    if (!item && historyTargetItemId.value) {
      historyDrawerVisible.value = false
      historyTargetItemId.value = ''
      historySelectingId.value = ''
    }
  })

  watch(
    () => route.params.canvasId,
    async (canvasId) => {
      if (canvasId) {
        syncSelectedStudioDraft()
        styleReferencePreviewMap.value = {}
        imageUploadPreviewMap.value = {}
        historyDrawerVisible.value = false
        historyTargetItemId.value = ''
        historySelectingId.value = ''
        await loadDocument(canvasId)
        await focusRouteItemIfPresent()
        await initializeEntryModeIfPresent()
      }
    },
    { immediate: true }
  )

  watch(
    () => route.query.mode,
    async () => {
      await initializeEntryModeIfPresent()
    }
  )

  watch(
    () => route.query.item_id || route.query.itemId,
    async () => {
      await focusRouteItemIfPresent()
    }
  )

  onMounted(() => {
    void hydrateCanvasConfigCatalog()
    window.addEventListener('beforeunload', handleBeforeUnload)
    window.addEventListener('keydown', handleKeydown)
  })

  onBeforeUnmount(() => {
    syncSelectedStudioDraft()
    window.removeEventListener('beforeunload', handleBeforeUnload)
    window.removeEventListener('keydown', handleKeydown)
    window.removeEventListener('mousemove', handleGlobalPointerMove)
    window.removeEventListener('mouseup', handleGlobalPointerUp)
  })
</script>

<style scoped>
  .canvas-editor-page {
    height: calc(100vh - 120px);
    min-height: 720px;
  }

  .canvas-stage-shell {
    position: relative;
    width: 100%;
    height: 100%;
    overflow: hidden;
    user-select: none;
    -webkit-user-select: none;
    border-radius: 28px;
    background:
      radial-gradient(circle at top, rgba(79, 117, 255, 0.14), transparent 30%),
      linear-gradient(180deg, #fbfcff 0%, #f4f7fb 100%);
    border: 1px solid rgba(26, 43, 77, 0.08);
    box-shadow: 0 18px 48px rgba(46, 82, 144, 0.1);
  }

  .canvas-asset-panel {
    position: absolute;
    top: 84px;
    right: 20px;
    z-index: 1210;
    width: min(420px, calc(100% - 40px));
    max-height: calc(100% - 108px);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    border: 1px solid rgba(31, 49, 88, 0.14);
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.98);
    box-shadow: 0 18px 42px rgba(24, 42, 80, 0.18);
  }

  .canvas-asset-panel__header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    padding: 16px 16px 12px;
    border-bottom: 1px solid rgba(31, 49, 88, 0.08);
  }

  .canvas-asset-panel__header h3 {
    margin: 0;
    color: #1d2b46;
    font-size: 16px;
    line-height: 1.3;
  }

  .canvas-asset-panel__header p {
    margin: 4px 0 0;
    color: #6b7894;
    font-size: 12px;
    line-height: 1.4;
  }

  .canvas-asset-panel__header-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .canvas-asset-panel__upload-input {
    display: none;
  }

  .canvas-asset-panel__icon-btn,
  .canvas-asset-panel__close,
  .canvas-asset-card__primary,
  .canvas-asset-card__secondary {
    appearance: none;
    border: 0;
    cursor: pointer;
    font: inherit;
  }

  .canvas-asset-panel__icon-btn {
    min-width: 56px;
    height: 32px;
    padding: 0 12px;
    border-radius: 8px;
    color: #274064;
    background: #edf2f8;
  }

  .canvas-asset-panel__icon-btn:disabled {
    cursor: wait;
    opacity: 0.6;
  }

  .canvas-asset-panel__close {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    color: #4c5f7d;
    font-size: 22px;
    line-height: 30px;
    background: #f4f6fa;
  }

  .canvas-asset-panel__state {
    padding: 32px 18px;
    color: #6b7894;
    font-size: 14px;
    text-align: center;
  }

  .canvas-asset-panel__list {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 14px;
    overflow: auto;
  }

  .canvas-asset-card {
    display: grid;
    grid-template-columns: 118px minmax(0, 1fr);
    gap: 12px;
    padding: 10px;
    border: 1px solid rgba(31, 49, 88, 0.11);
    border-radius: 12px;
    background: #fff;
  }

  .canvas-asset-card__preview {
    width: 118px;
    min-height: 84px;
    overflow: hidden;
    border-radius: 10px;
    background: #eef2f6;
  }

  .canvas-asset-card__preview img,
  .canvas-asset-card__preview video {
    display: block;
    width: 100%;
    height: 100%;
    min-height: 84px;
    object-fit: cover;
  }

  .canvas-asset-card__body {
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .canvas-asset-card__title {
    color: #21314d;
    font-size: 13px;
    font-weight: 700;
    line-height: 1.35;
    word-break: break-all;
  }

  .canvas-asset-card__meta {
    color: #71809c;
    font-size: 12px;
  }

  .canvas-asset-card__actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: auto;
  }

  .canvas-asset-card__primary,
  .canvas-asset-card__secondary {
    min-height: 30px;
    padding: 0 11px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 700;
  }

  .canvas-asset-card__primary {
    color: #fff;
    background: #2f68ff;
  }

  .canvas-asset-card__secondary {
    color: #274064;
    background: #edf2f8;
  }

  .canvas-relation-panel {
    position: absolute;
    left: 88px;
    top: 84px;
    z-index: 980;
    width: min(300px, calc(100% - 132px));
    max-height: min(36vh, 280px);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    border: 1px solid rgba(31, 49, 88, 0.14);
    border-radius: 14px;
    background: rgba(255, 255, 255, 0.97);
    box-shadow: 0 12px 28px rgba(24, 42, 80, 0.12);
  }

  .canvas-relation-panel__header {
    padding: 12px 14px 9px;
    border-bottom: 1px solid rgba(31, 49, 88, 0.08);
  }

  .canvas-relation-panel__header h3 {
    margin: 0;
    color: #1d2b46;
    font-size: 14px;
    line-height: 1.25;
  }

  .canvas-relation-panel__header p,
  .canvas-relation-panel__empty,
  .canvas-relation-candidate {
    margin: 4px 0 0;
    color: #6b7894;
    font-size: 12px;
    line-height: 1.45;
  }

  .canvas-relation-panel__body {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 10px 12px;
    overflow: auto;
  }

  .canvas-relation-panel__sources {
    display: flex;
    flex-direction: column;
    gap: 7px;
  }

  .canvas-relation-source {
    appearance: none;
    width: 100%;
    min-width: 0;
    padding: 8px 10px;
    border: 1px solid rgba(47, 104, 255, 0.16);
    border-radius: 10px;
    background: #f4f7ff;
    color: #274064;
    cursor: pointer;
    text-align: left;
  }

  .canvas-relation-source span {
    display: block;
    color: #6b7894;
    font-size: 11px;
    line-height: 1.2;
  }

  .canvas-relation-source strong {
    display: block;
    margin-top: 2px;
    overflow: hidden;
    color: #20314f;
    font-size: 12px;
    line-height: 1.35;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .canvas-relation-candidate {
    padding: 8px 10px;
    border-radius: 10px;
    background: #f6f8fb;
  }

  .canvas-relation-targets {
    display: flex;
    flex-direction: column;
    gap: 7px;
  }

  .canvas-relation-targets__title {
    color: #6b7894;
    font-size: 11px;
    font-weight: 700;
    line-height: 1.2;
  }

  .canvas-relation-target {
    appearance: none;
    width: 100%;
    min-width: 0;
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    align-items: center;
    gap: 8px;
    padding: 8px 10px;
    border: 1px solid rgba(31, 49, 88, 0.1);
    border-radius: 10px;
    background: #fff;
    color: #274064;
    cursor: pointer;
    text-align: left;
  }

  .canvas-relation-target span {
    color: #2f68ff;
    font-size: 11px;
    font-weight: 800;
  }

  .canvas-relation-target strong {
    min-width: 0;
    overflow: hidden;
    font-size: 12px;
    line-height: 1.35;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .canvas-relation-panel__actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    padding: 10px 12px 12px;
    border-top: 1px solid rgba(31, 49, 88, 0.08);
  }

  .canvas-relation-btn {
    appearance: none;
    min-height: 30px;
    padding: 0 11px;
    border: 0;
    border-radius: 8px;
    background: #edf2f8;
    color: #274064;
    cursor: pointer;
    font: inherit;
    font-size: 12px;
    font-weight: 700;
  }

  .canvas-relation-btn:disabled {
    cursor: not-allowed;
    opacity: 0.45;
  }

  .canvas-relation-btn--primary {
    color: #fff;
    background: #2f68ff;
  }

  .canvas-relation-btn--ghost {
    background: transparent;
    color: #6b7894;
  }

  @media (max-width: 720px) {
    .canvas-asset-panel {
      top: 72px;
      right: 12px;
      left: 12px;
      width: auto;
    }

    .canvas-asset-card {
      grid-template-columns: 96px minmax(0, 1fr);
    }

    .canvas-asset-card__preview {
      width: 96px;
    }

    .canvas-relation-panel {
      left: 12px;
      right: 12px;
      bottom: 16px;
      width: auto;
    }
  }
</style>

