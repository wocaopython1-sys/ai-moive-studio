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
    warnings
  }
}