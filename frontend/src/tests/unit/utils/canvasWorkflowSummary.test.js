import { describe, expect, it } from 'vitest'
import { buildCanvasWorkflowSummary } from '@/utils/canvasWorkflowSummary'

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
      warnings: []
    })
  })

  it('summarizes final, fill missing, failed, and processing nodes without guessing reused items', () => {
    const items = [
      {
        id: 'prompt-a',
        item_type: 'text',
        title: 'Prompt A',
        last_run_status: 'idle'
      },
      {
        id: 'image-fill',
        item_type: 'image',
        title: 'Fill missing image',
        last_run_status: 'completed',
        content: {
          fill_missing: true,
          workflow_stage: 'image',
          result_image_url: '/media/image.png'
        }
      },
      {
        id: 'video-ready',
        item_type: 'video',
        title: 'Ready video',
        last_run_status: 'completed',
        content: {
          result_video_url: '/media/video.mp4'
        }
      },
      {
        id: 'video-final',
        item_type: 'video',
        title: 'Final video',
        last_run_status: 'completed',
        content: {
          compose_mode: 'concat',
          compose_source_item_ids: ['video-ready', 'video-fill'],
          result_video_url: '/media/final.mp4'
        }
      },
      {
        id: 'video-failed',
        item_type: 'video',
        title: 'Failed retry video',
        last_run_status: 'failed',
        generation_config: {
          options: {
            workflow_action: 'retry_missing_video_base64'
          }
        }
      },
      {
        id: 'video-processing',
        item_type: 'video',
        title: 'Processing video',
        last_run_status: 'processing'
      }
    ]
    const connections = [
      { source_item_id: 'prompt-a', target_item_id: 'image-fill' },
      { source_item_id: 'image-fill', target_item_id: 'video-ready' },
      { source_item_id: 'video-ready', target_item_id: 'video-final' }
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
})