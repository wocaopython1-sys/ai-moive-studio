import { describe, expect, it } from 'vitest'
import { buildCanvasWorkflowSummary } from '@/utils/canvasWorkflowSummary'

const textItem = (id, overrides = {}) => ({
  id,
  item_type: 'text',
  title: `Prompt ${id}`,
  last_run_status: 'idle',
  ...overrides
})

const imageItem = (id, overrides = {}) => ({
  id,
  item_type: 'image',
  title: `Image ${id}`,
  last_run_status: 'completed',
  content: { result_image_url: `/media/${id}.png` },
  ...overrides
})

const videoItem = (id, overrides = {}) => ({
  id,
  item_type: 'video',
  title: `Video ${id}`,
  last_run_status: 'completed',
  content: { result_video_url: `/media/${id}.mp4` },
  ...overrides
})

const finalVideoItem = (id, overrides = {}) => ({
  id,
  item_type: 'video',
  title: `Final ${id}`,
  last_run_status: 'completed',
  content: {
    compose_mode: 'concat',
    compose_source_item_ids: ['video-a'],
    result_video_url: `/media/${id}.mp4`
  },
  ...overrides
})

const link = (source, target) => ({ source_item_id: source, target_item_id: target })

describe('buildCanvasWorkflowSummary', () => {
  it('returns a safe empty summary for missing graph data', () => {
    const summary = buildCanvasWorkflowSummary()

    expect(summary).toMatchObject({
      totalItems: 0,
      imageCount: 0,
      videoCount: 0,
      completedCount: 0,
      processingCount: 0,
      failedCount: 0,
      finalCount: 0,
      fillMissingCount: 0,
      hasFinalVideo: false,
      hasCompletedFinalVideo: false,
      statusLabel: '暂无 workflow 结果',
      statusTone: 'neutral',
      warnings: [],
      workflowLinks: [],
      reliableLinkCount: 0,
      hiddenLinkCount: 0,
      hasWorkflowLinks: false,
      linkSummaryLabel: '暂无可可靠推导链路',
      linkWarnings: []
    })
    expect(summary).not.toHaveProperty('reusedCount')
    expect(summary).not.toHaveProperty('reusedItems')
  })

  it('summarizes final, fill missing, failed, and processing nodes without guessing reused items', () => {
    const items = [
      textItem('prompt-a'),
      imageItem('image-fill', {
        title: 'Fill missing image',
        content: {
          fill_missing: true,
          workflow_stage: 'image',
          result_image_url: '/media/image.png'
        }
      }),
      videoItem('video-ready', { title: 'Ready video' }),
      finalVideoItem('video-final', {
        title: 'Final video',
        content: {
          compose_mode: 'concat',
          compose_source_item_ids: ['video-ready', 'video-fill'],
          result_video_url: '/media/final.mp4'
        }
      }),
      videoItem('video-failed', {
        title: 'Failed retry video',
        last_run_status: 'failed',
        generation_config: {
          options: {
            workflow_action: 'retry_missing_video_base64'
          }
        }
      }),
      videoItem('video-processing', {
        title: 'Processing video',
        last_run_status: 'processing'
      })
    ]
    const connections = [
      link('prompt-a', 'image-fill'),
      link('image-fill', 'video-ready'),
      link('video-ready', 'video-final')
    ]

    const summary = buildCanvasWorkflowSummary(items, connections)

    expect(summary).toMatchObject({
      totalItems: 6,
      imageCount: 1,
      videoCount: 4,
      completedCount: 3,
      processingCount: 1,
      failedCount: 1,
      finalCount: 1,
      fillMissingCount: 2,
      connectionCount: 3,
      hasConnections: true,
      hasFinalVideo: true,
      hasCompletedFinalVideo: true,
      statusLabel: '已有最终成片，存在失败节点',
      statusTone: 'warning'
    })
    expect(summary.finalVideoItems.map((item) => item.id)).toEqual(['video-final'])
    expect(summary.completedVideoItems.map((item) => item.id)).toEqual(['video-ready', 'video-final'])
    expect(summary.failedVideoItems.map((item) => item.id)).toEqual(['video-failed'])
    expect(summary.processingVideoItems.map((item) => item.id)).toEqual(['video-processing'])
    expect(summary.fillMissingItems.map((item) => item.id)).toEqual(['image-fill', 'video-failed'])
    expect(summary.warnings).toContain('仍有 1 个失败节点保留')
    expect(summary.warnings).toContain('仍有 1 个处理中节点')
    expect(summary).not.toHaveProperty('reusedCount')
    expect(summary).not.toHaveProperty('reusedItems')
  })

  it('builds a reliable Prompt to Image to Video to Final text link', () => {
    const summary = buildCanvasWorkflowSummary(
      [textItem('prompt-a'), imageItem('image-a'), videoItem('video-a'), finalVideoItem('final-a')],
      [link('prompt-a', 'image-a'), link('image-a', 'video-a'), link('video-a', 'final-a')]
    )

    expect(summary.hasWorkflowLinks).toBe(true)
    expect(summary.reliableLinkCount).toBe(1)
    expect(summary.hiddenLinkCount).toBe(0)
    expect(summary.workflowLinks[0]).toMatchObject({
      label: 'Prompt → Image → Video → Final',
      statusLabel: '已有最终成片',
      hasFailed: false,
      hasProcessing: false,
      hasFinal: true
    })
    expect(summary.workflowLinks[0].steps.map((step) => step.type)).toEqual([
      'prompt',
      'image',
      'video',
      'final'
    ])
  })

  it('limits multiple reliable branches and records hidden links', () => {
    const items = [textItem('prompt-a')]
    const connections = []
    for (let index = 1; index <= 6; index += 1) {
      items.push(imageItem(`image-${index}`), videoItem(`video-${index}`))
      connections.push(link('prompt-a', `image-${index}`), link(`image-${index}`, `video-${index}`))
    }

    const summary = buildCanvasWorkflowSummary(items, connections)

    expect(summary.reliableLinkCount).toBe(6)
    expect(summary.workflowLinks).toHaveLength(5)
    expect(summary.hiddenLinkCount).toBe(1)
    expect(summary.linkWarnings).toContain('另有 1 条链路未展示')
  })

  it('reflects failed and processing states on workflow links without changing counts', () => {
    const summary = buildCanvasWorkflowSummary(
      [
        textItem('prompt-a'),
        imageItem('image-a', { last_run_status: 'processing' }),
        videoItem('video-a', { last_run_status: 'failed' })
      ],
      [link('prompt-a', 'image-a'), link('image-a', 'video-a')]
    )

    expect(summary.processingCount).toBe(1)
    expect(summary.failedCount).toBe(1)
    expect(summary.workflowLinks[0]).toMatchObject({
      label: 'Prompt → Image → Video',
      statusLabel: '存在失败',
      hasFailed: true,
      hasProcessing: true,
      hasFinal: false
    })
  })

  it('ignores broken connections instead of creating fake links', () => {
    const summary = buildCanvasWorkflowSummary(
      [textItem('prompt-a'), imageItem('image-a'), videoItem('video-a')],
      [link('missing-source', 'image-a'), link('image-a', 'missing-target')]
    )

    expect(summary.workflowLinks).toEqual([])
    expect(summary.hasWorkflowLinks).toBe(false)
    expect(summary.linkSummaryLabel).toBe('暂无可可靠推导链路')
  })

  it('handles cycles with a depth guard', () => {
    const summary = buildCanvasWorkflowSummary(
      [textItem('prompt-a'), imageItem('image-a'), videoItem('video-a')],
      [link('prompt-a', 'image-a'), link('image-a', 'video-a'), link('video-a', 'image-a')]
    )

    expect(summary.workflowLinks.length).toBeGreaterThan(0)
    expect(summary.workflowLinks[0].steps.length).toBeLessThanOrEqual(6)
    expect(summary.workflowLinks[0].label).toContain('Prompt → Image → Video')
  })

  it('does not infer reused items from reuse compose metadata', () => {
    const summary = buildCanvasWorkflowSummary(
      [
        videoItem('video-a'),
        finalVideoItem('final-a', {
          content: {
            compose_mode: 'concat',
            workflow_action: 'reuse_compose',
            result_video_url: '/media/final.mp4'
          }
        })
      ],
      [link('video-a', 'final-a')]
    )

    expect(summary.workflowLinks[0].label).toBe('Video → Final')
    expect(summary.workflowLinks[0].label).not.toContain('reused')
    expect(summary.workflowLinks[0].label).not.toContain('复用')
    expect(summary).not.toHaveProperty('reusedCount')
    expect(summary).not.toHaveProperty('reusedItems')
  })
})
