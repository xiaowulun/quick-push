<template>
  <div class="chat-message" :class="role">
    <div class="chat-avatar">
      {{ role === 'assistant' ? '🤖' : '👤' }}
    </div>
    <div class="chat-bubble">
      <div class="chat-content" v-html="formattedContent"></div>
      
      <div v-if="projects && projects.length > 0" class="chat-referenced-projects">
        <div class="chat-referenced-projects-title">📚 参考项目</div>
        <div 
          v-for="project in projects" 
          :key="project.repo_full_name"
          class="chat-project-card"
        >
          <div class="chat-project-card-header">
            <a :href="project.url" target="_blank" class="chat-project-card-name">
              {{ project.repo_full_name }}
            </a>
            <span class="chat-project-card-similarity">{{ project.similarity }}% 相关</span>
          </div>
          <div class="chat-project-card-summary">{{ project.summary }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { marked } from 'marked'

const props = defineProps({
  role: {
    type: String,
    required: true
  },
  content: {
    type: String,
    default: ''
  },
  projects: {
    type: Array,
    default: () => []
  }
})

const formattedContent = computed(() => {
  if (!props.content) return ''
  return marked.parse(props.content)
})
</script>

<style scoped>
.chat-message {
  display: flex;
  gap: 12px;
  animation: fadeIn 0.3s ease;
}

.chat-message.user {
  flex-direction: row-reverse;
}

.chat-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 16px;
}

.chat-message.assistant .chat-avatar {
  background: var(--primary-gradient);
  box-shadow: 0 4px 15px rgba(123, 104, 238, 0.3);
}

.chat-message.user .chat-avatar {
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.chat-bubble {
  max-width: 75%;
  padding: 14px 18px;
  border-radius: 20px;
  line-height: 1.6;
}

.chat-message.assistant .chat-bubble {
  background: var(--bg-input);
  backdrop-filter: blur(10px);
  border: 1px solid var(--border-color);
  border-bottom-left-radius: 6px;
}

.chat-message.user .chat-bubble {
  background: var(--primary-gradient);
  color: white;
  border-bottom-right-radius: 6px;
  box-shadow: 0 4px 15px rgba(123, 104, 238, 0.3);
}

.chat-content :deep(pre) {
  background: rgba(0, 0, 0, 0.3);
  padding: 12px 16px;
  border-radius: 10px;
  overflow-x: auto;
  margin: 10px 0;
  border: 1px solid var(--border-color);
}

.chat-content :deep(code) {
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
}

.chat-content :deep(ul),
.chat-content :deep(ol) {
  margin: 10px 0;
  padding-left: 20px;
}

.chat-content :deep(li) {
  margin: 6px 0;
}

.chat-content :deep(a) {
  color: var(--primary-color);
  text-decoration: none;
}

.chat-content :deep(a):hover {
  text-decoration: underline;
}

.chat-content :deep(strong) {
  color: var(--text-primary);
}

.chat-content :deep(p) {
  margin: 10px 0;
}

.chat-referenced-projects {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border-color);
}

.chat-referenced-projects-title {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 12px;
}

.chat-project-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 12px 16px;
  margin-bottom: 10px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.chat-project-card:hover {
  border-color: var(--border-hover);
  background: rgba(123, 104, 238, 0.05);
  transform: translateX(4px);
}

.chat-project-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.chat-project-card-name {
  font-weight: 500;
  color: var(--text-primary);
  text-decoration: none;
  transition: color 0.2s;
}

.chat-project-card-name:hover {
  color: var(--primary-color);
}

.chat-project-card-similarity {
  font-size: 11px;
  color: var(--primary-color);
  background: rgba(123, 104, 238, 0.1);
  padding: 3px 10px;
  border-radius: 20px;
}

.chat-project-card-summary {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
}
</style>
