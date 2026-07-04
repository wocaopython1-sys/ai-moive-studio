import {
  isCanvasFinalVideoItem,
  isCanvasWorkflowFillMissingItem
} from './canvasStageMedia.js'

const COMPLETED_STATUSES = new Set(['completed', 'succeeded'])
const PROCESSING_STATUSES = new Set([
  'processing',
  'running',
  'pending',
  'queued',
  'submitted'
])
const FAILED_STATUSES = new Set(['failed', 'error'])
const MAX_WORKFLOW_LINKS = 5
const MAX_LINK_DEPTH = 6

const normalizeStatus = (value) => String(value || '').trim().toLowerCase()

const asArray = (value) => (Array.isArray(value) ? value : [])

const firstString = (...values) => {
  for (const value of values) {
    const normalized = String(value || '').trim()
    if (normalized) {
      return normalized
    }
  }
  return ''
}

const hasVideoResult = (item) =>
  Boolean(
    firstString(
      item?.content?.result_video_object_key,
      item?.content?.result_video_url,
      item?.last_output?.result_video_object_key,
      item?.last_output?.result_video_url,
      item?.last_output?.object_key,
      item?.last_output?.video_url,
      item?.last_output?.stream_url,
      item?.last_output?.provider_response?.result_video_object_key,
      item?.last_output?.provider_response?.object_key
    )
  )

const isCompleted = (item) => COMPLETED_STATUSES.has(normalizeStatus(item?.last_run_status))
const isProcessing = (item) => PROCESSING_STATUSES.has(normalizeStatus(item?.last_run_status))
const isFailed = (item) => FAILED_STATUSES.has(normalizeStatus(item?.last_run_status))

const buildStatusMeta = ({
  mediaCount,
  completedCount,
  processingCount,
  failedCount,
  finalCount
}) => {
  if (!mediaCount) {
    return {
      statusLabel: '暂无 workflow 结果',
      statusTone: 'neutral'
    }
  }

  if (finalCount && failedCount) {
    return {
      statusLabel: '已有最终成片，存在失败节点',
      statusTone: 'warning'
    }
  }

  if (finalCount && processingCount) {
    return {
      statusLabel: '已有最终成片，仍有处理中节点',
      statusTone: 'warning'
    }
  }

  if (finalCount) {
    return {
      statusLabel: '已有最终成片',
      statusTone: 'success'
    }
  }

  if (failedCount) {
    return {
      statusLabel: '部分失败',
      statusTone: 'error'
    }
  }

  if (processingCount) {
    return {
      statusLabel: '仍在处理中',
      statusTone: 'info'
    }
  }

  if (completedCount) {
    return {
      statusLabel: '已有可用结果',
      statusTone: 'success'
    }
  }

  return {
    statusLabel: '暂无完成结果',
    statusTone: 'neutral'
  }
}

const buildWarnings = ({ mediaCount, failedCount, processingCount, finalCount }) => {
  const warnings = []
  if (failedCount) {
    warnings.push(`仍有 ${failedCount} 个失败节点保留`)
  }
  if (processingCount) {
    warnings.push(`仍有 ${processingCount} 个处理中节点`)
  }
  if (mediaCount && !finalCount) {
    warnings.push('尚未发现最终成片节点')
  }
  return warnings
}

const nodeTypeMeta = (item) => {
  if (isCanvasFinalVideoItem(item)) {
    return { type: 'final', label: 'Final', isFinal: true }
  }
  if (item?.item_type === 'text' || item?.item_type === 'prompt') {
    return { type: 'prompt', label: 'Prompt', isFinal: false }
  }
  if (item?.item_type === 'image') {
    return { type: 'image', label: 'Image', isFinal: false }
  }
  if (item?.item_type === 'video') {
    return { type: 'video', label: 'Video', isFinal: false }
  }
  return { type: 'node', label: '节点', isFinal: false }
}

const buildStep = (item) => {
  const meta = nodeTypeMeta(item)
  return {
    itemId: item?.id,
    type: meta.type,
    label: meta.label,
    status: normalizeStatus(item?.last_run_status) || 'unknown',
    isFinal: meta.isFinal
  }
}

const isReliablePath = (steps) => {
  if (steps.length < 2) {
    return false
  }
  const types = new Set(steps.map((step) => step.type))
  return (
    types.has('final') ||
    types.has('video') ||
    (types.has('prompt') && types.has('image')) ||
    (types.has('image') && types.has('video'))
  )
}

const workflowLinkStatusLabel = ({ hasFailed, hasProcessing, hasFinal, steps }) => {
  if (hasFailed) {
    return '存在失败'
  }
  if (hasProcessing) {
    return '处理中'
  }
  if (hasFinal) {
    return '已有最终成片'
  }
  const mediaSteps = steps.filter((step) => ['image', 'video'].includes(step.type))
  if (mediaSteps.length && mediaSteps.every((step) => COMPLETED_STATUSES.has(step.status))) {
    return '已完成'
  }
  return '可查看'
}

const workflowLinkScore = (link) => {
  const types = new Set(link.steps.map((step) => step.type))
  let score = 0
  if (types.has('final')) score += 100
  if (types.has('image') && types.has('video')) score += 60
  if (types.has('prompt')) score += 20
  score += Math.min(link.steps.length, MAX_LINK_DEPTH)
  if (link.hasFailed) score -= 5
  if (link.hasProcessing) score -= 2
  return score
}

const buildWorkflowLink = (path) => {
  const steps = path.map(buildStep)
  const hasFailed = path.some(isFailed)
  const hasProcessing = path.some(isProcessing)
  const hasFinal = steps.some((step) => step.isFinal)
  return {
    id: steps.map((step) => step.itemId).join('>'),
    label: steps.map((step) => step.label).join(' → '),
    steps,
    statusLabel: workflowLinkStatusLabel({ hasFailed, hasProcessing, hasFinal, steps }),
    hasFailed,
    hasProcessing,
    hasFinal
  }
}

const buildWorkflowLinks = (items, connections) => {
  const itemById = new Map()
  for (const item of items) {
    const id = firstString(item?.id)
    if (id) {
      itemById.set(id, item)
    }
  }

  const outgoing = new Map()
  const incomingIds = new Set()
  for (const connection of connections) {
    const sourceId = firstString(connection?.source_item_id)
    const targetId = firstString(connection?.target_item_id)
    if (!sourceId || !targetId || !itemById.has(sourceId) || !itemById.has(targetId)) {
      continue
    }
    if (!outgoing.has(sourceId)) {
      outgoing.set(sourceId, [])
    }
    outgoing.get(sourceId).push(targetId)
    incomingIds.add(targetId)
  }

  for (const targetIds of outgoing.values()) {
    targetIds.sort((left, right) => left.localeCompare(right))
  }

  const sourceItems = items.filter((item) => outgoing.has(firstString(item?.id)))
  const rootItems = sourceItems.filter((item) => !incomingIds.has(firstString(item?.id)))
  const startItems = rootItems.length ? rootItems : sourceItems
  const candidateLinks = []
  const seenPathIds = new Set()

  const addCandidate = (path) => {
    const steps = path.map(buildStep)
    if (!isReliablePath(steps)) {
      return
    }
    const id = steps.map((step) => step.itemId).join('>')
    if (seenPathIds.has(id)) {
      return
    }
    seenPathIds.add(id)
    candidateLinks.push(buildWorkflowLink(path))
  }

  const walk = (item, path, visitedIds) => {
    const itemId = firstString(item?.id)
    const targetIds = outgoing.get(itemId) || []
    const reachedMaxDepth = path.length >= MAX_LINK_DEPTH
    const reachedFinal = isCanvasFinalVideoItem(item)
    const nextTargetIds = targetIds.filter((targetId) => !visitedIds.has(targetId))

    if (reachedFinal || reachedMaxDepth || !nextTargetIds.length) {
      addCandidate(path)
      return
    }

    for (const targetId of nextTargetIds) {
      const targetItem = itemById.get(targetId)
      walk(targetItem, [...path, targetItem], new Set([...visitedIds, targetId]))
    }
  }

  for (const item of startItems) {
    const itemId = firstString(item?.id)
    walk(item, [item], new Set([itemId]))
  }

  const reliableLinks = candidateLinks.sort((left, right) => {
    const scoreDiff = workflowLinkScore(right) - workflowLinkScore(left)
    if (scoreDiff) {
      return scoreDiff
    }
    return left.id.localeCompare(right.id)
  })
  const workflowLinks = reliableLinks.slice(0, MAX_WORKFLOW_LINKS)
  const hiddenLinkCount = Math.max(reliableLinks.length - workflowLinks.length, 0)
  const linkWarnings = hiddenLinkCount ? [`另有 ${hiddenLinkCount} 条链路未展示`] : []

  return {
    workflowLinks,
    reliableLinkCount: reliableLinks.length,
    hiddenLinkCount,
    hasWorkflowLinks: workflowLinks.length > 0,
    linkSummaryLabel: workflowLinks.length
      ? `已识别 ${reliableLinks.length} 条可靠链路`
      : '暂无可可靠推导链路',
    linkWarnings
  }
}

export function buildCanvasWorkflowSummary(items = [], connections = []) {
  const safeItems = asArray(items)
  const safeConnections = asArray(connections)
  const imageItems = safeItems.filter((item) => item?.item_type === 'image')
  const videoItems = safeItems.filter((item) => item?.item_type === 'video')
  const mediaItems = [...imageItems, ...videoItems]
  const completedItems = mediaItems.filter(isCompleted)
  const processingItems = mediaItems.filter(isProcessing)
  const failedItems = mediaItems.filter(isFailed)
  const finalVideoItems = videoItems.filter(isCanvasFinalVideoItem)
  const fillMissingItems = mediaItems.filter(isCanvasWorkflowFillMissingItem)
  const completedVideoItems = videoItems.filter(isCompleted)
  const processingVideoItems = videoItems.filter(isProcessing)
  const failedVideoItems = videoItems.filter(isFailed)
  const completedFinalVideoItems = finalVideoItems.filter(
    (item) => isCompleted(item) && hasVideoResult(item)
  )
  const statusMeta = buildStatusMeta({
    mediaCount: mediaItems.length,
    completedCount: completedItems.length,
    processingCount: processingItems.length,
    failedCount: failedItems.length,
    finalCount: finalVideoItems.length
  })
  const warnings = buildWarnings({
    mediaCount: mediaItems.length,
    failedCount: failedItems.length,
    processingCount: processingItems.length,
    finalCount: finalVideoItems.length
  })
  const workflowLinkSummary = buildWorkflowLinks(safeItems, safeConnections)

  return {
    totalItems: safeItems.length,
    connectionCount: safeConnections.length,
    hasConnections: safeConnections.length > 0,
    imageCount: imageItems.length,
    videoCount: videoItems.length,
    completedCount: completedItems.length,
    processingCount: processingItems.length,
    failedCount: failedItems.length,
    finalCount: finalVideoItems.length,
    fillMissingCount: fillMissingItems.length,
    hasFinalVideo: finalVideoItems.length > 0,
    hasCompletedFinalVideo: completedFinalVideoItems.length > 0,
    finalVideoItems,
    completedVideoItems,
    processingVideoItems,
    failedVideoItems,
    fillMissingItems,
    ...statusMeta,
    warnings,
    ...workflowLinkSummary
  }
}
