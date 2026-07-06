import { del, get, patch } from './api'

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
  }
}

export default worksService
