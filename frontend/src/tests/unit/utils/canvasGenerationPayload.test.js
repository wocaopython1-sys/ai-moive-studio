import { describe, expect, it } from 'vitest'
import { buildCanvasGenerationPayload } from '@/utils/canvasGenerationPayload'

describe('buildCanvasGenerationPayload', () => {
  it('defaults image size and count when unset', () => {
    const payload = buildCanvasGenerationPayload({
      item: {
        item_type: 'image',
        content: {
          prompt: 'white studio desk',
          promptTokens: [{ type: 'text', text: 'white studio desk' }]
        },
        generation_config: {
          model: 'gpt-image-1',
          api_key_id: 'key-1'
        }
      },
      resolvedMentions: []
    })

    expect(payload.options).toMatchObject({
      aspect_ratio: '1:1',
      image_size: '1024x1024',
      n: 1
    })
  })

  it('includes selected image aspect ratio in generation options', () => {
    const payload = buildCanvasGenerationPayload({
      item: {
        item_type: 'image',
        content: {
          prompt: 'white studio desk',
          promptTokens: [{ type: 'text', text: 'white studio desk' }],
          aspectRatio: '3:4'
        },
        generation_config: {
          model: 'gpt-image-1',
          api_key_id: 'key-1'
        }
      },
      resolvedMentions: []
    })

    expect(payload.options).toMatchObject({
      aspect_ratio: '3:4',
      image_size: '1024x1024',
      n: 1
    })
  })

  it('includes selected video aspect ratio in generation options', () => {
    const payload = buildCanvasGenerationPayload({
      item: {
        item_type: 'video',
        content: {
          prompt: 'camera push in',
          promptTokens: [{ type: 'text', text: 'camera push in' }]
        },
        generation_config: {
          model: 'veo-3-fast',
          api_key_id: 'key-2',
          aspectRatio: '9:16'
        }
      },
      resolvedMentions: [
        {
          nodeType: 'image',
          status: 'resolved',
          resolvedContent: {
            object_key: 'uploads/reference.png'
          }
        }
      ]
    })

    expect(payload.options).toMatchObject({
      aspect_ratio: '9:16',
      duration: 5,
      duration_seconds: 5,
      reference_image_urls: ['uploads/reference.png']
    })
  })

  it('defaults video aspect ratio to 16:9 when unset', () => {
    const payload = buildCanvasGenerationPayload({
      item: {
        item_type: 'video',
        content: {
          prompt: 'camera push in',
          promptTokens: [{ type: 'text', text: 'camera push in' }]
        },
        generation_config: {
          model: 'veo-3-fast',
          api_key_id: 'key-2'
        }
      },
      resolvedMentions: []
    })

    expect(payload.options).toMatchObject({
      aspect_ratio: '16:9',
      duration: 5,
      duration_seconds: 5
    })
  })
})
