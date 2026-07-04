const normalizeText = (value) => String(value || '').trim()

const mediaTypeFromMime = (mimeType = '') => {
  const value = normalizeText(mimeType).toLowerCase()
  if (value.startsWith('image/')) return 'image'
  if (value.startsWith('video/')) return 'video'
  if (value.startsWith('text/')) return 'text'
  return ''
}

const normalizedMediaType = (asset = {}) => {
  const mediaType = normalizeText(asset.media_type).toLowerCase()
  if (['image', 'video', 'text'].includes(mediaType)) return mediaType
  return mediaTypeFromMime(asset.mime_type)
}

const typeMeta = (asset = {}) => {
  const mediaType = normalizedMediaType(asset)
  if (mediaType === 'image') {
    return { typeLabel: '图片素材', typeTone: 'image' }
  }
  if (mediaType === 'video') {
    return { typeLabel: '视频素材', typeTone: 'video' }
  }
  if (mediaType === 'text') {
    return { typeLabel: '文本素材', typeTone: 'text' }
  }
  return { typeLabel: '素材', typeTone: 'neutral' }
}

const hasCanvasSource = (asset = {}) =>
  Boolean(normalizeText(asset.canvas_id) || normalizeText(asset.canvas_item_id))

export function buildAssetLibraryLabels(asset = {}) {
  const type = typeMeta(asset)
  const mediaType = normalizedMediaType(asset)
  const sourceIsCanvas = hasCanvasSource(asset)
  const reliabilityNotes = []

  if (mediaType === 'video') {
    reliabilityNotes.push('final_not_identifiable')
  }
  if (!sourceIsCanvas) {
    reliabilityNotes.push('source_not_identified')
  }

  return {
    ...type,
    sourceLabel: sourceIsCanvas ? 'Canvas 来源' : '来源未标注',
    sourceTone: sourceIsCanvas ? 'canvas' : 'unknown',
    reliabilityNotes,
    canIdentifyFinal: false,
    finalLabel: ''
  }
}
