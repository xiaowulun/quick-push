import { ref } from 'vue'

const API_BASE = '/api'
const REQUEST_TIMEOUT = 60000

export function useApi() {
  const loading = ref(false)
  const error = ref(null)

  async function fetchWithTimeout(url, options = {}) {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT)
    
    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal
      })
      clearTimeout(timeoutId)
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      
      return await response.json()
    } catch (err) {
      clearTimeout(timeoutId)
      throw err
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

  async function* streamChat(query, options = {}) {
    const { topK = 5, sessionId = null, signal = null } = options

    const response = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        query, 
        top_k: topK,
        session_id: sessionId
      }),
      signal
    })

    if (!response.ok || !response.body) {
      throw new Error(`请求失败: ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

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
  }

  return {
    loading,
    error,
    fetchDashboard,
    fetchTrends,
    streamChat
  }
}
