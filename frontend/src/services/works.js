import { del, get, patch, post } from './api'

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
  }
}

export default worksService
