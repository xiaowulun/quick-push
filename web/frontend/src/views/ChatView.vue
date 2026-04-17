<template>
  <div class="chat-container">
    <div ref="messagesContainer" class="chat-messages">
      <div v-if="messages.length === 0" class="chat-welcome">
        <div class="chat-welcome-icon">
          <LogoIcon />
        </div>
        <h2 class="chat-welcome-title">GitHub Trending 助手</h2>
        <p class="chat-welcome-desc">基于 GitHub Trending 榜单数据，为您推荐最适合的开源项目</p>
        <div class="chat-suggestions">
          <button 
            v-for="suggestion in suggestions" 
            :key="suggestion"
            class="chat-suggestion-btn"
            @click="handleSuggestion(suggestion)"
          >
            {{ suggestion }}
          </button>
        </div>
      </div>
      
      <ChatMessage
        v-for="(msg, index) in messages"
        :key="index"
        :role="msg.role"
        :content="msg.content"
        :projects="msg.projects"
      />
      
      <div v-if="status" class="chat-status">
        <div class="spinner spinner-sm"></div>
        <span>{{ status }}</span>
      </div>

      <div v-if="lastFailedQuery && !isStreaming" class="chat-retry">
        <span class="chat-retry-text">上次请求失败：{{ lastFailureReason || '请重试' }}</span>
        <button class="chat-retry-btn" @click="handleRetry">重试</button>
      </div>
    </div>
    
    <div class="chat-input-container">
      <ChatInput
        ref="chatInput"
        :is-streaming="isStreaming"
        @send="handleSend"
        @stop="handleStop"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, nextTick, inject, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import LogoIcon from '@/components/LogoIcon.vue'
import ChatMessage from '@/components/ChatMessage.vue'
import ChatInput from '@/components/ChatInput.vue'
import { useApi } from '@/composables/useApi'

const route = useRoute()
const { streamChat } = useApi()

const messages = ref([])
const status = ref('')
const isStreaming = ref(false)
const messagesContainer = ref(null)
const chatInput = ref(null)
const abortController = ref(null)
const sessionId = ref(null)
const lastFailedQuery = ref('')
const lastFailureReason = ref('')
const STORAGE_KEY = 'quickpush-chat'

const timeFilter = inject('timeFilter')

const suggestions = [
  '有没有好用的 Python 爬虫框架？',
  '推荐一些 AI 编程助手',
  '最近有什么热门的数据可视化工具？',
  '有什么好用的机器学习框架？'
]

watch(() => route.path, () => {
  if (route.path === '/chat') {
    nextTick(() => {
      chatInput.value?.focus()
    })
  }
})

onMounted(() => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      const parsed = JSON.parse(saved)
      messages.value = parsed.messages || []
      sessionId.value = parsed.sessionId || null
    }
  } catch (e) {
    console.warn('恢复聊天记录失败', e)
  }

  if (route.path === '/chat') {
    nextTick(() => chatInput.value?.focus())
  }
})

watch([messages, sessionId], ([msgs, sid]) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      messages: msgs,
      sessionId: sid
    }))
  } catch (e) {
    console.warn('保存聊天记录失败', e)
  }
}, { deep: true })

async function handleSend(text) {
  if (isStreaming.value) return

  lastFailedQuery.value = ''
  lastFailureReason.value = ''
  messages.value.push({
    role: 'user',
    content: text
  })
  
  isStreaming.value = true
  status.value = '正在思考中...'
  
  const currentMessage = reactive({
    role: 'assistant',
    content: '',
    projects: []
  })

  let assistantAdded = false
  
  abortController.value = new AbortController()
  
  try {
    for await (const data of streamChat(text, {
      topK: 5,
      sessionId: sessionId.value,
      signal: abortController.value.signal
    })) {
      if (data.type === 'session') {
        sessionId.value = data.session_id
      } else if (data.type === 'status') {
        status.value = data.content
      } else if (data.type === 'projects') {
        currentMessage.projects = data.projects
      } else if (data.type === 'content_start') {
        status.value = ''
        if (!assistantAdded) {
          messages.value.push(currentMessage)
          assistantAdded = true
        }
      } else if (data.type === 'content') {
        if (!assistantAdded) {
          status.value = ''
          messages.value.push(currentMessage)
          assistantAdded = true
        }
        currentMessage.content += data.content
      } else if (data.type === 'error') {
        if (!assistantAdded) {
          status.value = ''
          messages.value.push(currentMessage)
          assistantAdded = true
        }
        const codeText = data.code ? ` [${data.code}]` : ''
        currentMessage.content = `出错了${codeText}：${data.content}`
        lastFailedQuery.value = text
        lastFailureReason.value = data.content || '服务异常，请重试。'
      }
    }
  } catch (err) {
    if (err.name !== 'AbortError') {
      const timeoutHint = err.name === 'TimeoutError' || err.code === 'CHAT_TIMEOUT'
      const message = timeoutHint
        ? `请求超时：${err.message}`
        : `出错了：${err.message}`
      messages.value.push({
        role: 'assistant',
        content: message
      })
      lastFailedQuery.value = text
      lastFailureReason.value = timeoutHint
        ? '响应超时，建议重试。'
        : (err.message || '请求失败，请重试。')
    }
  } finally {
    isStreaming.value = false
    status.value = ''
    abortController.value = null
    nextTick(() => {
      chatInput.value?.focus()
    })
  }
}

function handleStop() {
  if (abortController.value) {
    abortController.value.abort()
  }
  isStreaming.value = false
  status.value = ''
  messages.value.push({
    role: 'assistant',
    content: '已停止生成，您可以继续提问。'
  })
}

function handleSuggestion(text) {
  handleSend(text)
}

function handleRetry() {
  if (!lastFailedQuery.value || isStreaming.value) return
  handleSend(lastFailedQuery.value)
}
</script>

<style scoped>
.chat-container {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 140px);
  max-width: 800px;
  margin: 0 auto;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.chat-welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  color: var(--text-secondary);
  padding: 20px;
}

.chat-welcome-icon {
  width: 120px;
  height: 120px;
  margin-bottom: 24px;
  animation: float 3s ease-in-out infinite;
  filter: drop-shadow(0 0 30px rgba(100, 150, 255, 0.5)) drop-shadow(0 0 60px rgba(180, 100, 255, 0.3));
}

.chat-welcome-title {
  font-size: 28px;
  font-weight: 700;
  background: var(--primary-gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: 12px;
}

.chat-welcome-desc {
  font-size: 14px;
  margin-bottom: 40px;
  max-width: 400px;
  line-height: 1.6;
  color: var(--text-muted);
}

.chat-suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: center;
  max-width: 600px;
}

.chat-suggestion-btn {
  background: var(--bg-card);
  backdrop-filter: blur(10px);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  padding: 12px 20px;
  border-radius: 24px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.3s ease;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

.chat-suggestion-btn:hover {
  border-color: rgba(123, 104, 238, 0.5);
  color: var(--text-primary);
  background: rgba(123, 104, 238, 0.1);
  transform: translateY(-2px);
}

.chat-status {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  align-self: flex-start;
  gap: 10px;
  color: var(--text-secondary);
  font-size: 13px;
  padding: 8px 16px;
  margin-left: 0;
}

.chat-status .spinner {
  margin: 0;
}

.chat-retry {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 10px;
  margin: 8px 0 0 0;
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid rgba(255, 184, 77, 0.35);
  background: rgba(255, 184, 77, 0.1);
  align-self: flex-start;
}

.chat-retry-text {
  font-size: 12px;
  color: var(--text-secondary);
}

.chat-retry-btn {
  border: 1px solid var(--border-color);
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-primary);
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 14px;
  cursor: pointer;
}

.chat-retry-btn:hover {
  border-color: rgba(123, 104, 238, 0.6);
}

.chat-input-container {
  padding: 24px;
  background: transparent;
}
</style>
