import { get, post } from './api'

export const taskHistoryService = {
  list(params = {}) {
    return get('/tasks/history', { params })
  },

  detail(id) {
    return get(`/tasks/history/${id}`)
  },

  retry(id) {
    return post(`/tasks/history/${id}/retry`)
  },

  refresh(id) {
    return post(`/tasks/history/${id}/refresh`)
  },

  resume(id) {
    return post(`/tasks/history/${id}/resume`)
  }
}

export default taskHistoryService
