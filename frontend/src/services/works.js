import api, { del, get, patch, post } from './api'

const mediaPathPart = (value = '') => encodeURIComponent(String(value || '').trim())

const workItemMediaPath = (workId, itemId, mode) =>
  `/works/${mediaPathPart(workId)}/items/${mediaPathPart(itemId)}/${mode}`

const safeDownloadName = (filename = 'work-media') => {
  const name = String(filename || 'work-media').trim() || 'work-media'
  return name.replace(/[^A-Za-z0-9._-]/g, '_') || 'work-media'
}

const triggerBlobDownload = (blob, filename) => {
  const blobUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = blobUrl
  link.download = safeDownloadName(filename)
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(blobUrl)
}

export const worksService = {
  listWorks(params = {}) {
    return get('/works', { params })
  },

  getWork(workId) {
    return get(`/works/${workId}`)
  },

  updateWork(workId, payload) {
    return patch(`/works/${workId}`, payload)
  },

  deleteWork(workId) {
    return del(`/works/${workId}`)
  },

  createWorkFromCanvasFinal(payload) {
    return post('/works/from-canvas-final', payload)
  },

  getWorkItemPreviewPath(workId, itemId) {
    return workItemMediaPath(workId, itemId, 'preview')
  },

  getWorkItemDownloadPath(workId, itemId) {
    return workItemMediaPath(workId, itemId, 'download')
  },

  fetchWorkItemPreviewBlob(workId, itemId) {
    return api.get(this.getWorkItemPreviewPath(workId, itemId), { responseType: 'blob' })
  },

  fetchWorkItemDownloadBlob(workId, itemId) {
    return api.get(this.getWorkItemDownloadPath(workId, itemId), { responseType: 'blob' })
  },

  async downloadWorkItemMedia(workId, itemId, filename) {
    const blob = await this.fetchWorkItemDownloadBlob(workId, itemId)
    triggerBlobDownload(blob, filename)
    return blob
  }
}

export default worksService
