import { describe, expect, it } from 'vitest'
import { buildAssetLibraryLabels } from '@/utils/assetLibraryLabels'

describe('buildAssetLibraryLabels', () => {
  it('labels images from media_type', () => {
    const labels = buildAssetLibraryLabels({ media_type: 'image' })

    expect(labels.typeLabel).toBe('图片素材')
    expect(labels.typeTone).toBe('image')
    expect(labels.finalLabel).toBe('')
    expect(labels.canIdentifyFinal).toBe(false)
  })

  it('labels videos without guessing final output', () => {
    const labels = buildAssetLibraryLabels({
      media_type: 'video',
      object_key: 'uploads/user/final-compose-output.mp4',
      filename: 'final-compose-output.mp4'
    })

    expect(labels.typeLabel).toBe('视频素材')
    expect(labels.typeTone).toBe('video')
    expect(labels.finalLabel).toBe('')
    expect(labels.canIdentifyFinal).toBe(false)
    expect(labels.reliabilityNotes).toContain('final_not_identifiable')
  })

  it('labels text assets from mime_type', () => {
    const labels = buildAssetLibraryLabels({ mime_type: 'text/plain' })

    expect(labels.typeLabel).toBe('文本素材')
    expect(labels.typeTone).toBe('text')
  })

  it('labels Canvas source when canvas_id exists', () => {
    const labels = buildAssetLibraryLabels({ canvas_id: 'canvas-a' })

    expect(labels.sourceLabel).toBe('Canvas 来源')
    expect(labels.sourceTone).toBe('canvas')
  })

  it('labels Canvas source when canvas_item_id exists', () => {
    const labels = buildAssetLibraryLabels({ canvas_item_id: 'item-a' })

    expect(labels.sourceLabel).toBe('Canvas 来源')
    expect(labels.sourceTone).toBe('canvas')
  })

  it('does not infer Canvas source from object_key alone', () => {
    const labels = buildAssetLibraryLabels({
      object_key: 'uploads/user/canvas/final-video.mp4'
    })

    expect(labels.sourceLabel).toBe('来源未标注')
    expect(labels.sourceTone).toBe('unknown')
  })

  it('does not infer final output without an explicit reliable field', () => {
    const labels = buildAssetLibraryLabels({
      media_type: 'video',
      object_key: 'uploads/user/final.mp4',
      title: '最终成片'
    })

    expect(labels.canIdentifyFinal).toBe(false)
    expect(labels.finalLabel).toBe('')
  })
})
