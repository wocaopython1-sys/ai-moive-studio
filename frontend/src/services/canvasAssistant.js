import { useAuthStore } from '@/stores/auth'

const apiBase = '/api/v1'

const getAccessToken = () => {
  try {
    const authStore = useAuthStore()
    return authStore.token || localStorage.getItem('token') || ''
  } catch {
    return localStorage.getItem('token') || ''
  }
}

const stripUndefinedEntries = (value = {}) =>
  Object.fromEntries(Object.entries(value).filter(([, entry]) => entry !== undefined))

const normalizeMessage = (data = {}) => ({
  id: String(data.id || data.message_id || '').trim(),
  role: String(data.role || 'assistant').trim() || 'assistant',
  content: String(data.content ?? data.delta ?? data.text ?? ''),
  delta: typeof data.delta === 'string' ? data.delta : undefined,
  order: Number.isFinite(Number(data.order)) ? Number(data.order) : undefined
})

const normalizeToolCall = (data = {}) => ({
  id: String(data.id || data.tool_call_id || '').trim(),
  toolName: String(data.tool_name || data.toolName || '').trim(),
  status: String(data.status || 'completed').trim() || 'completed',
  args: data.args ?? data.arguments ?? null,
  result: data.result ?? null,
  effect: data.effect ?? data.result?.effect ?? null,
  order: Number.isFinite(Number(data.order)) ? Number(data.order) : undefined
})

const normalizeInterrupt = (data = {}) => ({
  interruptId: String(data.interrupt_id || data.interruptId || '').trim(),
  sessionId: String(data.session_id || data.sessionId || '').trim(),
  kind: String(data.kind || '').trim(),
  title: String(data.title || '').trim(),
  message: String(data.message || '').trim(),
  actions: Array.isArray(data.actions) ? data.actions : [],
  selectedModelId: String(data.selected_model_id || data.selectedModelId || '').trim(),
  modelOptions: Array.isArray(data.model_options || data.modelOptions) ? (data.model_options || data.modelOptions) : []
})

const normalizeThinking = (data = {}) => ({
  content: String(data.content ?? data.delta ?? data.message ?? ''),
  order: Number.isFinite(Number(data.order)) ? Number(data.order) : undefined
})

export const normalizeAssistantEvent = (rawEvent = {}) => {
  const type = String(rawEvent.type || rawEvent.event || '').trim()
  const data = rawEvent.data ?? rawEvent.payload ?? {}

  if (type === 'agent.session.started') {
    return { kind: 'session', sessionId: String(data.session_id || '').trim() }
  }
  if (type === 'agent.tool.call' || type === 'agent.tool.result') {
    return { kind: 'tool', toolCall: normalizeToolCall(data) }
  }
  if (type === 'agent.message.delta') {
    return { kind: 'message', message: normalizeMessage(data) }
  }
  if (type === 'agent.thinking.delta') {
    return { kind: 'thinking', thinking: normalizeThinking(data) }
  }
  if (type === 'agent.message.completed') {
    return { kind: 'message_completed', message: normalizeMessage(data) }
  }
  if (type === 'agent.interrupt.requested') {
    return { kind: 'interrupt', interrupt: normalizeInterrupt(data) }
  }
  if (type === 'agent.interrupt.resolved') {
    return {
      kind: 'interrupt_resolved',
      interrupt: {
        interruptId: String(data.interrupt_id || data.interruptId || '').trim(),
        decision: String(data.decision || '').trim()
      }
    }
  }
  if (type === 'agent.error') {
    return { kind: 'error', message: String(data.message || '').trim() }
  }
  if (type === 'agent.done') {
    return { kind: 'done', data }
  }
  return { kind: 'unknown', rawEvent }
}

const readSseBlock = (block) => {
  const lines = String(block || '').split(/\r?\n/)
  const event = { type: '', data: '' }
  for (const line of lines) {
    if (line.startsWith('event:')) {
      event.type = line.slice(6).trim()
      continue
    }
    if (line.startsWith('data:')) {
      event.data += `${event.data ? '\n' : ''}${line.slice(5).trimStart()}`
    }
  }

  if (!event.type && !event.data) {
    return null
  }

  let parsedData = {}
  if (event.data.trim()) {
    try {
      parsedData = JSON.parse(event.data)
    } catch (error) {
      parsedData = { message: event.data.trim(), parseError: error?.message || 'invalid json' }
    }
  }

  return normalizeAssistantEvent({
    type: event.type || parsedData.type || '',
    data: parsedData.data ?? parsedData
  })
}

async function consumeAssistantSse(response, handlers = {}) {
  const events = []
  const reader = response?.body?.getReader?.()
  if (!reader) {
    return { response, events }
  }
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) {
        break
      }
      buffer += decoder.decode(value, { stream: true })
      const blocks = buffer.split(/\r?\n\r?\n/)
      buffer = blocks.pop() || ''
      for (const block of blocks) {
        const event = readSseBlock(block)
        if (!event) continue
        events.push(event)
        handlers.onEvent?.(event)
      }
    }
  } finally {
    reader.releaseLock?.()
  }

  const tail = buffer.trim()
  if (tail) {
    const event = readSseBlock(tail)
    if (event) {
      events.push(event)
      handlers.onEvent?.(event)
    }
  }

  return { response, events }
}

const postAssistantStream = async (path, payload = {}, handlers = {}) => {
  const headers = new Headers(handlers.headers || {})
  headers.set('Accept', 'text/event-stream')
  headers.set('Content-Type', 'application/json')
  const accessToken = getAccessToken()
  if (accessToken && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${accessToken}`)
  }

  const response = await fetch(`${apiBase}${path}`, {
    method: 'POST',
    credentials: 'same-origin',
    body: JSON.stringify(stripUndefinedEntries(payload)),
    signal: handlers.signal,
    headers
  })
  if (!response?.ok) {
    throw new Error(`canvas assistant request failed (${response?.status || 'network'})`)
  }
  return consumeAssistantSse(response, handlers)
}

const postAssistantJson = async (path, payload = {}, options = {}) => {
  const headers = new Headers(options.headers || {})
  headers.set('Accept', 'application/json')
  headers.set('Content-Type', 'application/json')
  const accessToken = getAccessToken()
  if (accessToken && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${accessToken}`)
  }

  const response = await fetch(`${apiBase}${path}`, {
    method: 'POST',
    credentials: 'same-origin',
    body: JSON.stringify(stripUndefinedEntries(payload)),
    signal: options.signal,
    headers
  })
  if (!response?.ok) {
    let detail = ''
    try {
      const errorPayload = await response.json()
      detail = errorPayload?.detail || errorPayload?.message || ''
    } catch {
      detail = ''
    }
    throw new Error(detail || `canvas assistant request failed (${response?.status || 'network'})`)
  }
  return response.json()
}

const buildChatPayload = (payload = {}) => ({
  document_id: String(payload.documentId || payload.document_id || '').trim(),
  session_id: String(payload.sessionId || payload.session_id || '').trim() || undefined,
  message: String(payload.message || '').trim(),
  api_key_id: String(payload.apiKeyId || payload.api_key_id || '').trim() || undefined,
  chat_model_id: String(payload.chatModelId || payload.chat_model_id || '').trim() || undefined
})

const buildResumePayload = (payload = {}) => ({
  document_id: String(payload.documentId || payload.document_id || '').trim(),
  session_id: String(payload.sessionId || payload.session_id || '').trim(),
  interrupt_id: String(payload.interruptId || payload.interrupt_id || '').trim(),
  decision: String(payload.decision || '').trim(),
  selected_model_id: String(payload.selectedModelId || payload.selected_model_id || '').trim() || undefined
})

const buildSuggestPayload = (payload = {}) => ({
  canvas_id: String(payload.canvasId || payload.canvas_id || payload.documentId || payload.document_id || '').trim(),
  selected_item_id: String(payload.selectedItemId || payload.selected_item_id || '').trim() || undefined,
  action: String(payload.action || '').trim(),
  user_input: String(payload.userInput || payload.user_input || '').trim() || undefined,
  api_key_id: String(payload.apiKeyId || payload.api_key_id || '').trim() || undefined,
  chat_model_id: String(payload.chatModelId || payload.chat_model_id || '').trim() || undefined
})

const buildApplyPayload = (payload = {}) => ({
  canvas_id: String(payload.canvasId || payload.canvas_id || payload.documentId || payload.document_id || '').trim(),
  selected_item_id: String(payload.selectedItemId || payload.selected_item_id || '').trim() || undefined,
  mode: String(payload.mode || '').trim(),
  title: String(payload.title || '').trim() || undefined,
  content: String(payload.content || '').trim(),
  relation_source_item_id: String(payload.relationSourceItemId || payload.relation_source_item_id || '').trim() || undefined,
  position_x: Number.isFinite(Number(payload.positionX ?? payload.position_x)) ? Number(payload.positionX ?? payload.position_x) : undefined,
  position_y: Number.isFinite(Number(payload.positionY ?? payload.position_y)) ? Number(payload.positionY ?? payload.position_y) : undefined
})

export const canvasAssistantService = {
  chat(payload = {}, handlers = {}) {
    return postAssistantStream('/canvas-assistant/chat', buildChatPayload(payload), handlers)
  },
  resume(payload = {}, handlers = {}) {
    return postAssistantStream('/canvas-assistant/resume', buildResumePayload(payload), handlers)
  },
  suggest(payload = {}, options = {}) {
    return postAssistantJson('/canvas-assistant/suggest', buildSuggestPayload(payload), options)
  },
  apply(payload = {}, options = {}) {
    return postAssistantJson('/canvas-assistant/apply', buildApplyPayload(payload), options)
  }
}

export default canvasAssistantService
