import { ref } from 'vue'

const API_BASE = '/api'
const REQUEST_TIMEOUT = 60000
const STREAM_CHAT_TIMEOUT = 120000
const STREAM_CHAT_IDLE_TIMEOUT = 120000

function buildTimeoutError(message = '请求超时，请稍后重试。') {
  const err = new Error(message)
  err.name = 'TimeoutError'
  err.code = 'CHAT_TIMEOUT'
  err.status = 504
  return err
}

async function buildHttpError(response) {
  let payload = null
  try {
    payload = await response.json()
  } catch (_) {
    payload = null
  }

  const detail = payload?.detail ?? payload
  let code = `HTTP_${response.status}`
  let message = `请求失败（HTTP ${response.status}）`

  if (typeof detail === 'string') {
    message = detail
  } else if (detail && typeof detail === 'object') {
    code = detail.code || code
    message = detail.message || detail.error || message
  }

  const err = new Error(message)
  err.name = 'HttpError'
  err.code = code
  err.status = response.status
  err.payload = payload
  return err
}

export function useApi() {
  const loading = ref(false)
  const error = ref(null)

  async function fetchWithTimeout(url, options = {}) {
    const controller = new AbortController()
    let timedOut = false
    const timeoutId = setTimeout(() => {
      timedOut = true
      controller.abort()
    }, REQUEST_TIMEOUT)

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal
      })

      if (!response.ok) {
        throw await buildHttpError(response)
      }

      return await response.json()
    } catch (err) {
      if (timedOut && err.name === 'AbortError') {
        throw buildTimeoutError('请求超时，请点击重试。')
      }
      throw err
    } finally {
      clearTimeout(timeoutId)
    }
  }

  async function fetchDashboard(days) {
    loading.value = true
    error.value = null
    try {
      return await fetchWithTimeout(`${API_BASE}/dashboard?days=${days}`)
    } catch (err) {
      error.value = err.message
      throw err
    } finally {
      loading.value = false
    }
  }

  async function fetchDashboardInsights(days) {
    loading.value = true
    error.value = null
    try {
      return await fetchWithTimeout(`${API_BASE}/dashboard/insights?days=${days}`)
    } catch (err) {
      error.value = err.message
      throw err
    } finally {
      loading.value = false
    }
  }

  async function fetchTrends(days) {
    loading.value = true
    error.value = null
    try {
      return await fetchWithTimeout(`${API_BASE}/trends?days=${days}`)
    } catch (err) {
      error.value = err.message
      throw err
    } finally {
      loading.value = false
    }
  }

  async function fetchProjectDetail(repoFullName) {
    loading.value = true
    error.value = null
    try {
      const repoPath = String(repoFullName || '')
        .split('/')
        .map(segment => encodeURIComponent(segment))
        .join('/')
      return await fetchWithTimeout(`${API_BASE}/projects/${repoPath}`)
    } catch (err) {
      error.value = err.message
      throw err
    } finally {
      loading.value = false
    }
  }

  async function* streamChat(query, options = {}) {
    const {
      topK = 5,
      sessionId = null,
      signal = null,
      timeoutMs = STREAM_CHAT_TIMEOUT,
      idleTimeoutMs = STREAM_CHAT_IDLE_TIMEOUT
    } = options

    const controller = new AbortController()
    let timedOut = false
    let stoppedByUser = false
    let externalAbortHandler = null
    let timeoutId = null

    const armTimeout = (ms) => {
      if (timeoutId) clearTimeout(timeoutId)
      timeoutId = setTimeout(() => {
        timedOut = true
        controller.abort()
      }, ms)
    }

    // 首包超时：用于保护完全无响应场景（网络异常/后端卡死）。
    armTimeout(timeoutMs)

    if (signal) {
      externalAbortHandler = () => {
        stoppedByUser = true
        controller.abort()
      }
      if (signal.aborted) {
        externalAbortHandler()
      } else {
        signal.addEventListener('abort', externalAbortHandler, { once: true })
      }
    }

    try {
      const response = await fetch(`${API_BASE}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          top_k: topK,
          session_id: sessionId
        }),
        signal: controller.signal
      })

      if (!response.ok || !response.body) {
        throw await buildHttpError(response)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        // 流式阶段改用空闲超时：只要持续有数据，就不应该被总时长硬中断。
        armTimeout(idleTimeoutMs)

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          const trimmedLine = line.trim()
          if (trimmedLine.startsWith('data: ')) {
            try {
              yield JSON.parse(trimmedLine.slice(6))
            } catch (e) {
              console.error('Parse error:', e)
            }
          }
        }
      }
    } catch (err) {
      if (err?.name === 'AbortError') {
        if (timedOut) {
          const timeoutHintSec = Math.floor(Math.max(timeoutMs, idleTimeoutMs) / 1000)
          throw buildTimeoutError(`对话超时（超过${timeoutHintSec}秒无新内容），请重试。`)
        }
        if (stoppedByUser) {
          const stopErr = new Error('用户已停止生成')
          stopErr.name = 'AbortError'
          throw stopErr
        }
      }
      throw err
    } finally {
      if (timeoutId) clearTimeout(timeoutId)
      if (signal && externalAbortHandler) {
        signal.removeEventListener('abort', externalAbortHandler)
      }
    }
  }

  return {
    loading,
    error,
    fetchDashboard,
    fetchDashboardInsights,
    fetchTrends,
    fetchProjectDetail,
    streamChat
  }
}
