import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const canvasEditorSource = () =>
  readFileSync(resolve(process.cwd(), 'src/views/canvas/CanvasEditor.vue'), 'utf8')

const archiveSelectedWorkBody = () => {
  const source = canvasEditorSource()
  const start = source.indexOf('const archiveSelectedWork = async () => {')
  const end = source.indexOf('  const openSelectedInLibrary = () => {', start)

  if (start === -1 || end === -1) {
    throw new Error('archiveSelectedWork block not found')
  }

  return source.slice(start, end)
}

describe('CanvasEditor archiveSelectedWork', () => {
  it('does not block works archive POST on dirty canvas save', () => {
    const body = archiveSelectedWorkBody()
    const postIndex = body.indexOf('worksService.createWorkFromCanvasFinal')
    const saveIndex = body.indexOf('await save()')

    expect(postIndex).toBeGreaterThan(-1)
    expect(saveIndex === -1 || saveIndex > postIndex).toBe(true)
  })
})
