<template>
  <div class="project-card" :class="{ expanded: isExpanded }">
    <div class="card-header">
      <div class="card-title-row">
        <a 
          :href="project.url" 
          target="_blank" 
          class="project-name"
          @click.stop
        >
          {{ project.repo_name }}
        </a>
        <div class="project-stars">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
          </svg>
          {{ formattedStars }}
        </div>
      </div>
      <div class="card-actions">
        <button class="action-btn" @click.stop="copyLink" title="复制链接">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="9" y="9" width="13" height="13" rx="2"/>
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
          </svg>
        </button>
        <button class="action-btn expand-btn" @click.stop="toggleExpand" :title="isExpanded ? '收起' : '展开'">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" :class="{ rotated: isExpanded }">
            <path d="M6 9l6 6 6-6"/>
          </svg>
        </button>
      </div>
    </div>
    
    <div class="card-meta">
      <span class="language">{{ project.language }}</span>
      <span class="stars-today">+{{ project.stars_today }} 今日</span>
    </div>
    
    <transition name="expand">
      <div v-if="isExpanded" class="card-details">
        <p class="project-summary">{{ project.summary }}</p>
        <div class="project-reasons">
          <span v-for="reason in displayReasons" :key="reason" class="reason-tag">
            {{ reason }}
          </span>
        </div>
      </div>
    </transition>
    
    <div v-if="copied" class="copy-toast">已复制链接</div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  project: {
    type: Object,
    required: true
  }
})

const isExpanded = ref(false)
const copied = ref(false)

const formattedStars = computed(() => {
  const stars = props.project.stars
  if (stars >= 10000) {
    return (stars / 10000).toFixed(1) + '万'
  } else if (stars >= 1000) {
    return (stars / 1000).toFixed(1) + 'k'
  }
  return stars
})

const displayReasons = computed(() => {
  return props.project.reasons?.slice(0, 3) || []
})

function toggleExpand() {
  isExpanded.value = !isExpanded.value
}

function copyLink() {
  const url = props.project.url
  if (!url) {
    alert('链接不存在')
    return
  }
  
  const textarea = document.createElement('textarea')
  textarea.value = url
  textarea.style.position = 'fixed'
  textarea.style.top = '0'
  textarea.style.left = '0'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.focus()
  textarea.select()
  
  try {
    const successful = document.execCommand('copy')
    if (successful) {
      copied.value = true
      setTimeout(() => {
        copied.value = false
      }, 2000)
    } else {
      alert('复制失败，请手动复制：' + url)
    }
  } catch (err) {
    console.error('Copy failed:', err)
    alert('复制失败，请手动复制：' + url)
  } finally {
    document.body.removeChild(textarea)
  }
}
</script>

<style scoped>
.project-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 16px;
  transition: all 0.3s ease;
  position: relative;
  align-self: start;
  height: fit-content;
}

.project-card:hover {
  border-color: var(--border-hover);
  background: rgba(123, 104, 238, 0.05);
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(123, 104, 238, 0.1);
}

.project-card.expanded {
  background: rgba(30, 30, 45, 0.6);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 8px;
}

.card-title-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  min-width: 0;
}

.project-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  text-decoration: none;
  transition: color 0.2s;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-name:hover {
  color: var(--primary-color);
}

.project-stars {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--primary-color);
  font-weight: 500;
  font-size: 13px;
}

.card-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.action-btn {
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 6px;
  cursor: pointer;
  color: var(--text-secondary);
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.action-btn:hover {
  background: rgba(123, 104, 238, 0.1);
  border-color: var(--border-hover);
  color: var(--primary-color);
}

.expand-btn svg {
  transition: transform 0.3s ease;
}

.expand-btn svg.rotated {
  transform: rotate(180deg);
}

.card-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--text-muted);
}

.card-details {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-color);
}

.project-summary {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 12px;
}

.project-reasons {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.reason-tag {
  font-size: 11px;
  padding: 4px 10px;
  background: rgba(123, 104, 238, 0.1);
  border: 1px solid rgba(123, 104, 238, 0.2);
  border-radius: 20px;
  color: var(--primary-color);
}

.copy-toast {
  position: absolute;
  top: 8px;
  right: 8px;
  background: var(--primary-color);
  color: white;
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 12px;
  animation: fadeIn 0.2s ease;
}

.expand-enter-active,
.expand-leave-active {
  transition: all 0.3s ease;
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
}

.expand-enter-to,
.expand-leave-from {
  max-height: 200px;
}
</style>
