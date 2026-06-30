<template>
  <aside
    class="canvas-assistant"
    style="user-select: text; -webkit-user-select: text"
  >
    <CanvasAssistantHeader
      :title="title"
      :status="status"
      :session-id="sessionId"
      :can-reset="canReset"
      :streaming="isAssistantBusy"
      @reset="handleReset"
    />

    <section class="canvas-assistant__quick">
      <div class="quick-actions">
        <button
          class="quick-action"
          type="button"
          :disabled="!canRunTextAction || isAssistantBusy"
          data-testid="assistant-optimize-prompt"
          @click="handleQuickAction('optimize_prompt')"
        >
          优化 Prompt
        </button>
        <button
          class="quick-action"
          type="button"
          :disabled="!canRunImageAction || isAssistantBusy"
          data-testid="assistant-image-video-prompt"
          @click="handleQuickAction('image_to_video_prompt')"
        >
          视频 Prompt
        </button>
        <button
          class="quick-action"
          type="button"
          :disabled="!canRunStoryboardAction || isAssistantBusy"
          data-testid="assistant-storyboard"
          @click="handleQuickAction('storyboard')"
        >
          分镜建议
        </button>
      </div>
      <div v-if="selectedItemSummary" class="quick-context">
        当前节点：{{ selectedItemSummary }}
      </div>
      <article v-if="assistantDraft?.text" class="quick-result">
        <div class="quick-result__title">
          {{ assistantDraft.suggested_title || '助手建议' }}
        </div>
        <pre class="quick-result__text">{{ assistantDraft.text }}</pre>
        <div class="quick-result__actions">
          <button
            v-if="canUpdateSelectedText"
            class="quick-result__btn quick-result__btn--primary"
            type="button"
            data-testid="assistant-apply-current"
            :disabled="resultActionBusy"
            @click="handleApplyToSelected"
          >
            写回当前节点
          </button>
          <button
            class="quick-result__btn quick-result__btn--primary"
            type="button"
            data-testid="assistant-create-node"
            :disabled="resultActionBusy"
            @click="handleApplyCreateNode"
          >
            新建文本节点
          </button>
          <button
            v-if="assistantDraft?.action === 'optimize_prompt'"
            class="quick-result__btn quick-result__btn--primary"
            type="button"
            data-testid="assistant-use-image-prompt"
            :disabled="!canUseAsImagePrompt || resultActionBusy"
            @click="handleUseAsImagePrompt"
          >
            用作图片 Prompt
          </button>
          <button
            v-if="assistantDraft?.action === 'image_to_video_prompt'"
            class="quick-result__btn quick-result__btn--primary"
            type="button"
            data-testid="assistant-use-video-prompt"
            :disabled="!canUseAsVideoPrompt || resultActionBusy"
            @click="handleUseAsVideoPrompt"
          >
            用当前图片生成视频
          </button>
          <button
            v-if="assistantDraft?.action === 'storyboard'"
            class="quick-result__btn quick-result__btn--primary"
            type="button"
            data-testid="assistant-split-storyboard"
            :disabled="resultActionBusy"
            @click="handleSplitStoryboard"
          >
            拆成多个 Prompt 节点
          </button>
          <button
            class="quick-result__btn"
            type="button"
            data-testid="assistant-copy-result"
            @click="handleCopyDraft"
          >
            复制
          </button>
        </div>
        <div v-if="resultActionMessage" class="quick-result__status">
          {{ resultActionMessage }}
        </div>
      </article>
    </section>

    <CanvasAssistantTimeline
      class="canvas-assistant__timeline"
      :items="timelineItems"
      :busy="isAssistantBusy"
      :can-write-back="canWriteBack"
      @approve="handleApprove"
      @reject="handleReject"
      @create-text-node="handleCreateTextNode"
      @write-to-selected="handleWriteToSelected"
      @update:selected-model-id="handleUpdateSelectedModelId"
    />

    <CanvasAssistantComposer
      class="canvas-assistant__composer"
      :disabled="!canSend"
      :loading="isAssistantBusy"
      :placeholder="composerPlaceholder"
      :api-key-options="apiKeyOptions"
      :chat-model-options="chatModelOptions"
      :selected-api-key-id="selectedApiKeyId"
      :selected-chat-model-id="selectedChatModelId"
      :api-keys-loading="apiKeysLoading"
      :chat-models-loading="chatModelsLoading"
      @update:selected-api-key-id="handleUpdateSelectedApiKeyId"
      @update:selected-chat-model-id="handleUpdateSelectedChatModelId"
      @submit="handleSend"
    />
  </aside>
</template>

<script setup>
  import { computed, ref, watch } from 'vue'
  import { ElMessage } from 'element-plus'
  import useCanvasAssistant from '@/composables/useCanvasAssistant'
  import { useCanvasAssistantTimeline } from '@/composables/useCanvasAssistantTimeline'
  import CanvasAssistantComposer from './CanvasAssistantComposer.vue'
  import CanvasAssistantHeader from './CanvasAssistantHeader.vue'
  import CanvasAssistantTimeline from './CanvasAssistantTimeline.vue'

  const props = defineProps({
    // documentId: 当前画布 id，用来绑定 assistant 会话和上下文。
    documentId: { type: String, default: '' },
    refreshCanvas: { type: Function, default: null },
    selectedItem: { type: Object, default: null },
    // title: 右侧助手栏标题，默认保持通用文案。
    title: { type: String, default: 'AI 助手' }
  })
  const emit = defineEmits([
    'assistant_prompt_to_image',
    'assistant_prompt_to_video',
    'assistant_split_storyboard_prompts'
  ])

  // assistant composable 负责真实状态机；组件本身只拼装头部、时间线和输入区。
  const assistant = useCanvasAssistant({
    documentId: computed(() => props.documentId),
    onMutationApplied: (...args) => props.refreshCanvas?.(...args)
  })
  const sessionId = assistant.sessionId
  const status = assistant.status
  const error = assistant.error
  const messages = assistant.messages
  const eventLog = assistant.eventLog ?? computed(() => [])
  const pendingInterrupt = assistant.pendingInterrupt ?? computed(() => null)
  const apiKeyOptions = assistant.apiKeyOptions
  const chatModelOptions = assistant.chatModelOptions
  const selectedApiKeyId = assistant.selectedApiKeyId
  const selectedChatModelId = assistant.selectedChatModelId
  const apiKeysLoading = assistant.apiKeysLoading
  const chatModelsLoading = assistant.chatModelsLoading
  const isStreaming = assistant.isStreaming
  const quickActionLoading = assistant.quickActionLoading
  const assistantDraft = assistant.assistantDraft
  const canSend = assistant.canSend
  const sendMessage = assistant.sendMessage
  const runQuickAction = assistant.runQuickAction
  const applySuggestion = assistant.applySuggestion
  const updateSelectedApiKeyId = assistant.updateSelectedApiKeyId
  const updateSelectedChatModelId = assistant.updateSelectedChatModelId
  const resumeInterrupt = assistant.resumeInterrupt ?? (() => false)
  const updatePendingInterruptModelId = assistant.updatePendingInterruptModelId ?? (() => {})
  const reset = assistant.reset
  const resultActionLoading = ref('')
  const resultActionMessage = ref('')
  const lastResultItem = ref(null)

  const { timelineItems } = useCanvasAssistantTimeline(assistant)
  const resultActionBusy = computed(() => Boolean(quickActionLoading.value || resultActionLoading.value))
  const isAssistantBusy = computed(
    () => Boolean(isStreaming.value || quickActionLoading.value || resultActionLoading.value || status.value === 'streaming')
  )

  const canReset = computed(
    () =>
      eventLog.value.length > 0 ||
      messages.value.length > 0 ||
      Boolean(pendingInterrupt.value) ||
      Boolean(error.value)
  )
  const composerPlaceholder = computed(
    () =>
      '先给我一句创意、一个剧本想法，或者告诉我要从哪一步开始；我会先帮你创建节点'
  )
  const activeSelectedItem = computed(() => lastResultItem.value || props.selectedItem)
  const selectedItemType = computed(() => String(activeSelectedItem.value?.item_type || '').trim())
  const selectedItemSummary = computed(() => {
    if (!activeSelectedItem.value) return ''
    const title = String(activeSelectedItem.value.title || '').trim()
    const fallback = String(
      activeSelectedItem.value.content?.text ||
        activeSelectedItem.value.content?.prompt ||
        activeSelectedItem.value.content?.result_image_object_key ||
        activeSelectedItem.value.content?.result_video_object_key ||
        ''
    ).trim()
    const typeLabel =
      selectedItemType.value === 'text'
        ? '文本'
        : selectedItemType.value === 'image'
          ? '图片'
          : selectedItemType.value === 'video'
            ? '视频'
            : '节点'
    return `${typeLabel} / ${title || fallback || activeSelectedItem.value.id}`
  })
  const canRunTextAction = computed(() => Boolean(activeSelectedItem.value && selectedItemType.value === 'text'))
  const canRunImageAction = computed(() => Boolean(activeSelectedItem.value && selectedItemType.value === 'image'))
  const canRunStoryboardAction = computed(() => Boolean(props.documentId))
  const canUpdateSelectedText = computed(() => Boolean(activeSelectedItem.value && selectedItemType.value === 'text'))
  const canUseAsImagePrompt = computed(() => Boolean(activeSelectedItem.value && selectedItemType.value === 'text'))
  const canUseAsVideoPrompt = computed(() => Boolean(activeSelectedItem.value && selectedItemType.value === 'image'))
  const lastAssistantText = computed(() => {
    const list = messages.value
      .filter((message) => String(message?.role || '') === 'assistant')
      .map((message) => String(message?.content || '').trim())
      .filter(Boolean)
    return list[list.length - 1] || ''
  })
  const canWriteBack = computed(() => Boolean(lastAssistantText.value))

  watch(
    () => props.selectedItem?.id,
    (nextId) => {
      if (lastResultItem.value?.id && String(nextId || '') === String(lastResultItem.value.id)) {
        return
      }
      lastResultItem.value = null
      resultActionMessage.value = ''
    }
  )

  const handleSend = (message) => sendMessage(message)
  const handleQuickAction = async (action) => {
    const response = await runQuickAction({
      action,
      selectedItem: activeSelectedItem.value
    })
    if (response?.text) {
      ElMessage.success('助手建议已生成')
    }
  }
  const handleApplyToSelected = async () => {
    const response = await applySuggestion({
      mode: 'update_selected_text_node',
      selectedItem: props.selectedItem,
      title: props.selectedItem?.title || assistantDraft.value?.suggested_title,
      content: assistantDraft.value?.text || ''
    })
    if (response?.item) {
      ElMessage.success('已写回当前节点')
    }
  }
  const handleApplyCreateNode = async () => {
    const response = await applySuggestion({
      mode: 'create_text_node',
      selectedItem: props.selectedItem,
      title: assistantDraft.value?.suggested_title || '助手建议',
      content: assistantDraft.value?.text || '',
      relationSourceItemId: props.selectedItem?.id || ''
    })
    if (response?.item) {
      ElMessage.success('已写回画布')
    }
  }
  const runResultAction = async (actionName, eventName, successMessage) => {
    const text = String(assistantDraft.value?.text || '').trim()
    if (!text) {
      ElMessage.warning('助手没有可使用的内容')
      return
    }
    resultActionLoading.value = actionName
    resultActionMessage.value = '正在处理...'
    try {
      const actionPayload = {
          action: eventName,
          text,
          title: assistantDraft.value?.suggested_title || '助手建议',
          selectedItem: activeSelectedItem.value
        }
      const actionResult = props.refreshCanvas
        ? await Promise.resolve(props.refreshCanvas(actionPayload))
        : null
      const nextItem = actionResult?.item || actionResult?.targetItem || actionResult || null
      if (nextItem?.id && nextItem?.item_type) {
        lastResultItem.value = nextItem
      }
      resultActionMessage.value = successMessage
      ElMessage.success(successMessage)
      emit(eventName, {
        text,
        title: assistantDraft.value?.suggested_title || '助手建议',
        selectedItem: props.selectedItem
      })
    } catch (error) {
      const message = error?.response?.data?.detail || error?.message || '处理失败'
      resultActionMessage.value = message
      ElMessage.error(message)
    } finally {
      resultActionLoading.value = ''
    }
  }
  const handleUseAsImagePrompt = () =>
    runResultAction(
      'image',
      'assistant_prompt_to_image',
      '已用助手 Prompt 生成图片并加入画布'
    )
  const handleUseAsVideoPrompt = () =>
    runResultAction(
      'video',
      'assistant_prompt_to_video',
      '已用当前图片生成视频并加入画布'
    )
  const handleSplitStoryboard = () =>
    runResultAction(
      'storyboard',
      'assistant_split_storyboard_prompts',
      '已拆成多个 Prompt 节点'
    )
  const handleCopyDraft = async () => {
    const text = String(assistantDraft.value?.text || '').trim()
    if (!text) return
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
    ElMessage.success('已复制')
  }
  const handleWriteToSelected = () => {
    if (!lastAssistantText.value) return
    props.refreshCanvas?.({
      action: 'write_assistant_text_to_selected',
      text: lastAssistantText.value,
      selectedItem: props.selectedItem
    })
  }
  const handleCreateTextNode = () => {
    if (!lastAssistantText.value) return
    props.refreshCanvas?.({
      action: 'create_assistant_text_node',
      text: lastAssistantText.value
    })
  }
  const handleUpdateSelectedApiKeyId = (apiKeyId) => updateSelectedApiKeyId(apiKeyId)
  const handleUpdateSelectedChatModelId = (chatModelId) => updateSelectedChatModelId(chatModelId)
  const handleApprove = (selectedModelId) =>
    resumeInterrupt({ decision: 'approve', selectedModelId })
  const handleReject = () => resumeInterrupt({ decision: 'reject' })
  const handleUpdateSelectedModelId = (selectedModelId) =>
    updatePendingInterruptModelId(selectedModelId)
  const handleReset = () => reset()

  defineExpose({
    ...assistant
  })
</script>

<style scoped>
  .canvas-assistant {
    height: 100%;
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 18px;
    border-left: 1px solid rgba(34, 57, 98, 0.08);
    background:
      linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(246, 249, 255, 0.94)),
      radial-gradient(circle at top, rgba(75, 120, 255, 0.08), transparent 34%);
    backdrop-filter: blur(18px);
    box-shadow: inset 1px 0 0 rgba(255, 255, 255, 0.6);
    user-select: text;
    -webkit-user-select: text;
  }

  .canvas-assistant__timeline {
    flex: 1;
    min-height: 0;
  }

  .canvas-assistant__quick {
    flex: 0 0 auto;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .quick-actions {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
  }

  .quick-action,
  .quick-result__btn {
    min-height: 32px;
    border: 1px solid rgba(34, 57, 98, 0.12);
    border-radius: 10px;
    background: rgba(255, 255, 255, 0.9);
    color: #1f2a44;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
  }

  .quick-action:disabled,
  .quick-result__btn:disabled {
    cursor: not-allowed;
    opacity: 0.48;
  }

  .quick-context {
    color: #5f6b85;
    font-size: 12px;
    line-height: 1.45;
  }

  .quick-result {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 10px;
    border: 1px solid rgba(34, 57, 98, 0.1);
    border-radius: 12px;
    background: rgba(255, 255, 255, 0.74);
  }

  .quick-result__title {
    color: #1f2a44;
    font-size: 13px;
    font-weight: 700;
  }

  .quick-result__text {
    max-height: 148px;
    margin: 0;
    overflow: auto;
    white-space: pre-wrap;
    word-break: break-word;
    color: #34415c;
    font-family: inherit;
    font-size: 12px;
    line-height: 1.55;
  }

  .quick-result__actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .quick-result__btn {
    padding: 0 10px;
  }

  .quick-result__btn--primary {
    border-color: rgba(75, 120, 255, 0.28);
    background: rgba(75, 120, 255, 0.1);
    color: #234fb8;
  }

  .canvas-assistant__composer {
    flex: 0 0 auto;
  }

</style>
