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
import { ref, nextTick, inject, watch } from 'vue'
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

async function handleSend(text) {
  messages.value.push({
    role: 'user',
    content: text
  })
  
  isStreaming.value = true
  status.value = '正在思考...'
  
  let currentMessage = {
    role: 'assistant',
    content: '',
    projects: []
  }
  
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
        messages.value.push(currentMessage)
      } else if (data.type === 'content') {
        currentMessage.content += data.content
      } else if (data.type === 'error') {
        currentMessage.content = `❌ ${data.content}`
      }
    }
  } catch (err) {
    if (err.name !== 'AbortError') {
      messages.value.push({
        role: 'assistant',
        content: `❌ 网络错误: ${err.message}`
      })
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
    content: '⏱️ 已停止生成'
  })
}

function handleSuggestion(text) {
  handleSend(text)
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
  gap: 10px;
  color: var(--text-secondary);
  font-size: 13px;
  padding: 8px 0;
}

.chat-input-container {
  padding: 24px;
  background: transparent;
}
</style>
