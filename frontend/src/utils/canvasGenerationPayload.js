import { buildPromptDerivatives } from '@/utils/promptMentionTokens'

export const IMAGE_ASPECT_RATIO_OPTIONS = ['1:1', '3:4', '4:3', '16:9', '9:16']
export const IMAGE_SIZE_OPTIONS = ['1024x1024', '1024x1536', '1536x1024']
export const IMAGE_COUNT_OPTIONS = [1, 2, 4]
export const VIDEO_ASPECT_RATIO_OPTIONS = ['16:9', '9:16', '1:1']
export const VIDEO_DURATION_OPTIONS = [5, 10]
export const DEFAULT_ASPECT_RATIO = '16:9'
export const DEFAULT_IMAGE_ASPECT_RATIO = '1:1'
export const DEFAULT_IMAGE_SIZE = '1024x1024'
export const DEFAULT_IMAGE_COUNT = 1
export const DEFAULT_VIDEO_DURATION_SECONDS = 5

export const getSupportedVideoAspectRatios = (modelName = '') => {
  const normalizedModelName = String(modelName || '')
    .trim()
    .toLowerCase()

  if (normalizedModelName.startsWith('veo')) {
    return ['16:9', '9:16']
  }

  return VIDEO_ASPECT_RATIO_OPTIONS
}

export const normalizeVideoAspectRatio = (modelName = '', aspectRatio = '') => {
  const supportedRatios = getSupportedVideoAspectRatios(modelName)
  return supportedRatios.includes(aspectRatio)
    ? aspectRatio
    : supportedRatios[0]
}

export const buildCanvasGenerationPayload = ({
  item,
  resolvedMentions = [],
  resolveImageReferenceObjectKey = (value) =>
    String(value?.object_key || value?.objectKey || '').trim(),
  resolveStyleReferenceImageObjectKey = (content = {}) =>
    String(content?.style_reference_image_object_key || '').trim()
} = {}) => {
  const content = item?.content || {}
  const promptTokens = Array.isArray(content.promptTokens)
    ? content.promptTokens
    : []
  const { promptPlainText } = buildPromptDerivatives(promptTokens)
  const payload = {
    prompt: promptPlainText || content.prompt || '',
    prompt_plain_text: promptPlainText || content.prompt || '',
    prompt_tokens: promptTokens,
    resolved_mentions: resolvedMentions,
    model: item?.generation_config?.model || undefined,
    api_key_id: item?.generation_config?.api_key_id || undefined,
    options: {}
  }

  if (item?.item_type === 'video') {
    const upstreamImageUrls = resolvedMentions
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
      .filter(Boolean)

    if (upstreamImageUrls.length) {
      payload.options.reference_image_urls = upstreamImageUrls
    }

    const aspectRatio = normalizeVideoAspectRatio(
      item?.generation_config?.model,
      item?.generation_config?.aspectRatio
    )
    if (aspectRatio) {
      payload.options.aspect_ratio = aspectRatio
    }
  } else if (item?.item_type === 'image') {
    const upstreamImageObjectKeys = resolvedMentions
      .filter(
        (reference) =>
          reference.nodeType === 'image' && reference.status === 'resolved'
      )
      .map((reference) =>
        resolveImageReferenceObjectKey(reference.resolvedContent)
      )
      .filter(Boolean)
    const styleReferenceImageObjectKey =
      resolveStyleReferenceImageObjectKey(content)
    const aspectRatio = String(content.aspectRatio || '').trim()
    const imageSize = String(content.imageSize || DEFAULT_IMAGE_SIZE).trim()
    const imageCount = Number(content.imageCount || DEFAULT_IMAGE_COUNT)

    if (upstreamImageObjectKeys.length) {
      payload.options.reference_image_object_keys = upstreamImageObjectKeys
    }
    if (styleReferenceImageObjectKey) {
      payload.options.style_reference_image_object_key =
        styleReferenceImageObjectKey
    }
    payload.options.aspect_ratio = aspectRatio || DEFAULT_IMAGE_ASPECT_RATIO
    payload.options.image_size = imageSize || DEFAULT_IMAGE_SIZE
    payload.options.n = Number.isFinite(imageCount)
      ? Math.min(Math.max(Math.trunc(imageCount), 1), 4)
      : DEFAULT_IMAGE_COUNT
  }

  if (item?.item_type === 'video') {
    const durationSeconds = Number(
      item?.generation_config?.durationSeconds || DEFAULT_VIDEO_DURATION_SECONDS
    )
    if (Number.isFinite(durationSeconds)) {
      payload.options.duration = Math.min(Math.max(Math.trunc(durationSeconds), 1), 10)
      payload.options.duration_seconds = payload.options.duration
    }
  }

  if (!Object.keys(payload.options).length) {
    delete payload.options
  }

  return payload
}
