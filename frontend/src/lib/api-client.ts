/**
 * Shared Axios instance used by every feature's api.ts module (auth, bank-accounts, etc.)
 * to talk to the FastAPI backend. Centralizing the client here means the base URL, the
 * Authorization header injection, and the 401-handling logout redirect only need to be
 * defined once instead of being duplicated across every feature module.
 */
import axios from 'axios'
import { useAuthStore } from '@/stores/authStore'

// No hardcoded Content-Type here: axios sets 'application/json' automatically for plain
// object/JSON bodies, and lets the browser generate 'multipart/form-data; boundary=...'
// for FormData bodies (e.g. uploadReceipts). A fixed instance-level 'application/json'
// header would make axios's transformRequest JSON-encode FormData payloads instead of
// sending them as multipart, breaking file uploads.
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api/v1',
})

// Attach the current user's JWT (if any) to every outgoing request.
apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// On any 401 response, clear the stale session and bounce the user back to /login.
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default apiClient
