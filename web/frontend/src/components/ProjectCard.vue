<template>
  <article
    class="project-card"
    role="button"
    tabindex="0"
    @click="goToDetail"
    @keydown.enter.prevent="goToDetail"
    @keydown.space.prevent="goToDetail"
  >
    <div class="card-header">
      <div class="card-title-row">
        <button class="project-name-btn" @click.stop="goToDetail">
          {{ project.repo_name }}
        </button>
        <div class="project-stars">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
          </svg>
          {{ formattedStars }}
        </div>
      </div>

      <div class="card-actions">
        <a :href="project.url" target="_blank" rel="noopener" class="action-btn" @click.stop>GitHub</a>
        <button class="action-btn" @click.stop="copyLink" title="复制链接">复制</button>
      </div>
    </div>

    <div class="card-meta">
      <span class="language">{{ project.language }}</span>
      <span class="stars-period">+{{ project.stars_today }} {{ starsPeriodLabel }}</span>
      <span class="jump-tip">查看详情</span>
    </div>

    <div class="card-details">
      <p class="project-summary">{{ project.summary }}</p>

      <div class="project-reasons">
        <div v-for="reason in displayReasons" :key="reason" class="reason-row">
          {{ reason }}
        </div>
      </div>

      <div class="tag-groups">
        <div v-if="project.use_cases?.length" class="tag-group">
          <div class="tag-label">适用场景</div>
          <div class="tag-list">
            <span v-for="item in project.use_cases.slice(0, 6)" :key="`case-${item}`" class="tag-pill tag-pill-alt">{{ item }}</span>
          </div>
        </div>

        <div v-if="project.tech_stack?.length" class="tag-group">
          <div class="tag-label">技术栈</div>
          <div class="tag-list">
            <span v-for="item in project.tech_stack.slice(0, 8)" :key="`tech-${item}`" class="tag-pill">{{ item }}</span>
          </div>
        </div>
      </div>
    </div>

    <div v-if="copied" class="copy-toast">已复制链接</div>
  </article>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

const props = defineProps({
  project: {
    type: Object,
    required: true
  }
})

const router = useRouter()
const copied = ref(false)

const formattedStars = computed(() => {
  const stars = Number(props.project.stars || 0)
  if (stars >= 10000) return `${(stars / 10000).toFixed(1)}万`
  if (stars >= 1000) return `${(stars / 1000).toFixed(1)}k`
  return String(stars)
})

const displayReasons = computed(() => props.project.reasons?.slice(0, 4) || [])

const starsPeriodLabel = computed(() => {
  const sinceType = String(props.project?.since_type || '').toLowerCase()
  if (sinceType === 'weekly') return '本周'
  if (sinceType === 'monthly') return '本月'
  return '今日'
})

const repoFullName = computed(() => {
  if (props.project.repo_full_name) return props.project.repo_full_name
  if (props.project.repo_name) return props.project.repo_name
  const url = String(props.project.url || '')
  const match = url.match(/github\.com\/([^/?#]+\/[^/?#]+)/i)
  return match ? match[1] : ''
})

function goToDetail() {
  if (!repoFullName.value) return
  router.push({
    name: 'ProjectDetail',
    params: { repoFullName: repoFullName.value }
  })
}

function copyLink() {
  const url = props.project.url
  if (!url) return

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
      }, 1600)
    }
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
  transition: all 0.25s ease;
  position: relative;
  cursor: pointer;
}

.project-card:hover {
  border-color: var(--border-hover);
  background: rgba(123, 104, 238, 0.05);
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(123, 104, 238, 0.12);
}

.project-card:focus-visible {
  outline: 2px solid rgba(123, 104, 238, 0.5);
  outline-offset: 2px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.card-title-row {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.project-name-btn {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  text-decoration: none;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  border: none;
  background: transparent;
  padding: 0;
  margin: 0;
  text-align: left;
  cursor: pointer;
}

.project-name-btn:hover {
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
  gap: 6px;
  flex-shrink: 0;
}

.action-btn {
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 6px 8px;
  cursor: pointer;
  color: var(--text-secondary);
  transition: all 0.2s;
  text-decoration: none;
  font-size: 12px;
}

.action-btn:hover {
  background: rgba(123, 104, 238, 0.1);
  border-color: var(--border-hover);
  color: var(--primary-color);
}

.card-meta {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 8px;
}

.jump-tip {
  color: var(--primary-light);
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
  margin-bottom: 10px;
}

.project-reasons {
  display: grid;
  gap: 6px;
  margin-bottom: 12px;
}

.reason-row {
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 8px;
  padding: 8px 10px;
}

.tag-groups {
  display: grid;
  gap: 10px;
}

.tag-group {
  display: grid;
  gap: 6px;
}

.tag-label {
  font-size: 11px;
  color: var(--text-muted);
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag-pill {
  font-size: 11px;
  padding: 4px 10px;
  background: rgba(123, 104, 238, 0.1);
  border: 1px solid rgba(123, 104, 238, 0.2);
  border-radius: 999px;
  color: var(--primary-light);
}

.tag-pill-alt {
  background: rgba(74, 144, 217, 0.1);
  border-color: rgba(74, 144, 217, 0.25);
  color: #7dc3ff;
}

.copy-toast {
  position: absolute;
  top: 8px;
  right: 8px;
  background: var(--primary-color);
  color: white;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  animation: fadeIn 0.2s ease;
}
</style>
