<template>
  <div class="paper-shell" :class="[themeClass, { 'sidebar-collapsed': isSidebarCollapsed }]">
    <aside class="side-panel" aria-label="主导航">
      <div class="brand-block">
        <LogoIcon class="brand-icon" />
        <div>
          <h2>OpenScout</h2>
          <p class="brand-subtitle">AI 驱动的开源洞察</p>
        </div>
      </div>
      <div class="side-divider"></div>

      <nav class="side-nav">
        <button class="nav-btn active" type="button" aria-label="发现">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <circle cx="12" cy="12" r="8" />
            <path d="M12 12l4-4" />
            <path d="M11 11l5-3-3 5z" fill="currentColor" stroke="none" />
          </svg>
          <span>发现</span>
        </button>
        <button class="nav-btn" type="button" aria-label="仪表盘" @click="router.push('/dashboard')">
          <DashboardIcon />
          <span>仪表盘</span>
        </button>
        <button class="nav-btn" type="button" aria-label="设置" @click="router.push('/settings')">
          <SettingsIcon />
          <span>设置</span>
        </button>
      </nav>

      <div class="side-footer">
        <button class="side-tool-btn" :class="{ dark: isDark }" type="button" @click="toggleTheme">
          <svg v-if="!isDark" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <circle cx="12" cy="12" r="4" />
            <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
          </svg>
          <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 1 0 9.8 9.8z" />
          </svg>
          <span>{{ isDark ? '浅色模式' : '深色模式' }}</span>
        </button>

        <button class="side-tool-btn" type="button" @click="toggleSidebar">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            :style="{ transform: isSidebarCollapsed ? 'rotate(180deg)' : 'none' }"
            aria-hidden="true"
          >
            <path d="M15 6l-6 6 6 6" />
          </svg>
          <span>{{ isSidebarCollapsed ? '展开侧栏' : '收起侧栏' }}</span>
        </button>

        <section class="account-card" aria-label="账户登录区">
          <p class="account-title">账户</p>
          <p class="account-hint">登录后可同步收藏、订阅与推送偏好</p>

          <button class="github-login-btn" type="button" :disabled="authLoading" @click="startGithubOAuth">
            <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M12 .7a12 12 0 0 0-3.8 23.4c.6.1.8-.3.8-.6v-2.1c-3.4.7-4.1-1.4-4.1-1.4-.6-1.5-1.3-1.8-1.3-1.8-1.1-.7.1-.7.1-.7 1.2.1 1.9 1.3 1.9 1.3 1.1 1.9 2.9 1.4 3.6 1 .1-.8.4-1.4.8-1.8-2.7-.3-5.5-1.3-5.5-6A4.7 4.7 0 0 1 6.7 8c-.1-.3-.5-1.6.1-3.2 0 0 1-.3 3.3 1.2a11.4 11.4 0 0 1 6 0c2.2-1.5 3.2-1.2 3.2-1.2.7 1.6.3 2.9.2 3.2a4.7 4.7 0 0 1 1.3 3.3c0 4.6-2.8 5.6-5.5 6 .4.4.8 1.2.8 2.4v3.6c0 .3.2.7.8.6A12 12 0 0 0 12 .7" />
            </svg>
            <span>{{ authLoading ? '跳转中...' : 'Github 登录' }}</span>
          </button>

          <div class="account-alt-row">
            <button
              class="account-alt-btn"
              type="button"
              title="飞书登录（即将上线）"
              @click="showToast('飞书登录即将上线')"
            >
              飞书
            </button>
            <button
              class="account-alt-btn"
              type="button"
              title="邮箱登录（即将上线）"
              @click="showToast('邮箱登录即将上线')"
            >
              邮箱
            </button>
          </div>
        </section>
      </div>
    </aside>

    <main class="feed-board" aria-label="项目流">
      <header class="feed-toolbar">
        <div class="toolbar-top">
          <div class="title-wrap">
            <p>从趋势项目里快速筛选值得深入的仓库</p>
          </div>
        </div>

        <div class="toolbar-row">
          <label class="search-box">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <circle cx="11" cy="11" r="7" />
              <path d="M20 20l-3.6-3.6" />
            </svg>
            <input
              v-model="searchDraft"
              type="text"
              placeholder="搜索仓库、技术栈、应用场景"
              aria-label="搜索仓库"
              @keydown.enter.prevent="applySearch"
            >
            <button class="search-btn" type="button" @click="applySearch">搜索</button>
          </label>

          <div class="period-group" role="tablist" aria-label="时间范围">
            <button
              v-for="item in periodOptions"
              :key="item.days"
              class="period-btn"
              :class="{ active: daysFilter === item.days }"
              type="button"
              @click="daysFilter = item.days"
            >
              {{ item.label }}
            </button>
          </div>
        </div>
      </header>

      <div v-if="loadingFeed" class="state-block">
        <div class="spinner"></div>
        <p>正在加载项目...</p>
      </div>

      <div v-else-if="feedError" class="state-block error" role="alert">
        <h3>项目加载失败</h3>
        <p>{{ feedError }}</p>
        <button class="retry-btn" type="button" @click="loadFeed">重试</button>
      </div>

      <div v-else class="feed-grid" role="list">
        <article
          v-for="project in filteredProjects"
          :key="project.repo_name"
          class="repo-card"
          :class="{ selected: activeRepo?.repo_name === project.repo_name }"
          role="listitem"
        >
          <div class="repo-head">
            <div class="repo-title-wrap">
              <svg class="repo-mark" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path d="M12 .7a12 12 0 0 0-3.8 23.4c.6.1.8-.3.8-.6v-2.1c-3.4.7-4.1-1.4-4.1-1.4-.6-1.5-1.3-1.8-1.3-1.8-1.1-.7.1-.7.1-.7 1.2.1 1.9 1.3 1.9 1.3 1.1 1.9 2.9 1.4 3.6 1 .1-.8.4-1.4.8-1.8-2.7-.3-5.5-1.3-5.5-6A4.7 4.7 0 0 1 6.7 8c-.1-.3-.5-1.6.1-3.2 0 0 1-.3 3.3 1.2a11.4 11.4 0 0 1 6 0c2.2-1.5 3.2-1.2 3.2-1.2.7 1.6.3 2.9.2 3.2a4.7 4.7 0 0 1 1.3 3.3c0 4.6-2.8 5.6-5.5 6 .4.4.8 1.2.8 2.4v3.6c0 .3.2.7.8.6A12 12 0 0 0 12 .7" />
              </svg>
              <div class="repo-title-main">
                <router-link :to="{ name: 'ProjectDetail', params: { repoFullName: project.repo_name } }" class="repo-title">
                  {{ project.repo_name }}
                </router-link>
                <span class="repo-age repo-status-badge">{{ projectAgeLabel(project) }}</span>
              </div>
            </div>

            <div class="repo-head-actions">
              <button
                class="repo-icon-btn favorite-btn"
                :class="{ active: favoriteRepos.has(project.repo_name) }"
                type="button"
                :aria-label="favoriteRepos.has(project.repo_name) ? '取消收藏' : '收藏项目'"
                :title="favoriteRepos.has(project.repo_name) ? '取消收藏' : '收藏项目'"
                @click.stop="toggleFavorite(project)"
              >
                <svg
                  v-if="favoriteRepos.has(project.repo_name)"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                  aria-hidden="true"
                >
                  <path d="M12 2.4l2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 16.8 6.4 19.6l1.1-6.2L3 9l6.2-.9L12 2.4z" />
                </svg>
                <svg
                  v-else
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  aria-hidden="true"
                >
                  <path d="M12 17.3l-5.2 3 1.4-5.9-4.6-4 6.1-.5L12 4.3l2.3 5.6 6.1.5-4.6 4 1.4 5.9z" />
                </svg>
              </button>
              <button
                class="repo-icon-btn subscribe-btn"
                :class="{ active: subscribedRepos.has(project.repo_name) }"
                type="button"
                :aria-label="subscribedRepos.has(project.repo_name) ? '取消订阅' : '订阅更新'"
                :title="subscribedRepos.has(project.repo_name) ? '取消订阅' : '订阅更新'"
                @click.stop="toggleSubscribe(project)"
              >
                <svg
                  v-if="subscribedRepos.has(project.repo_name)"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  aria-hidden="true"
                >
                  <path d="M15 17h5l-1.4-1.4a2 2 0 0 1-.6-1.4V11a6 6 0 1 0-12 0v3.2a2 2 0 0 1-.6 1.4L4 17h5" />
                  <path d="M10 17a2 2 0 1 0 4 0" />
                  <path d="M9.6 12.5l1.9 1.9 3.3-3.3" />
                </svg>
                <svg
                  v-else
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  aria-hidden="true"
                >
                  <path d="M15 17h5l-1.4-1.4a2 2 0 0 1-.6-1.4V11a6 6 0 1 0-12 0v3.2a2 2 0 0 1-.6 1.4L4 17h5" />
                  <path d="M10 17a2 2 0 1 0 4 0" />
                </svg>
              </button>
            </div>
          </div>

          <div class="repo-meta">
            <span class="meta-pill stars">
              <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path d="M12 2.4l2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 16.8 6.4 19.6l1.1-6.2L3 9l6.2-.9L12 2.4z" />
              </svg>
              <strong>{{ formatNumber(project.stars) }}</strong> stars
            </span>

            <span v-for="stack in topStacks(project)" :key="`${project.repo_name}-${stack}`" class="meta-pill stack">{{ stack }}</span>
            <span class="meta-pill">{{ project.category_label || '未分类' }}</span>
            <span class="meta-pill difficulty" :class="`difficulty-${estimateDifficulty(project)}`">
              实现难度：{{ difficultyLabel(estimateDifficulty(project)) }}
            </span>
          </div>

          <p class="repo-summary" :class="{ expanded: isRepoExpanded(project.repo_name) }">
            {{ project.summary || project.description || '暂无摘要信息。' }}
          </p>
          <button
            v-if="shouldShowExpand(project)"
            class="summary-toggle"
            type="button"
            @click="toggleRepoExpand(project.repo_name)"
          >
            {{ isRepoExpanded(project.repo_name) ? '收起详情' : '展开详情' }}
          </button>

          <div class="repo-tags">
            <span class="tag">推荐：{{ recommendationsText(project) }}</span>
            <span class="tag">场景：{{ inferUseCase(project) }}</span>
          </div>

          <div class="repo-actions">
            <button class="repo-btn primary ask-btn" type="button" @click="askOpenScout(project)">
              问 OpenScout
            </button>
          </div>
        </article>
      </div>
    </main>

    <aside class="chat-panel" aria-label="项目分析对话区">
      <header class="chat-head">
        <h2>OpenScout助手</h2>
        <button class="ghost-btn" type="button" @click="resetConversation">新会话</button>
      </header>

      <div v-if="messages.length <= 1" class="starter-grid">
        <button
          v-for="prompt in starterPrompts"
          :key="prompt"
          class="starter-chip"
          type="button"
          :disabled="isStreaming"
          @click="applyStarter(prompt)"
        >
          {{ prompt }}
        </button>
      </div>

      <div ref="messagesRef" class="message-list" aria-live="polite" @scroll="handleMessageScroll">
        <div v-for="(msg, index) in messages" :key="index" class="msg-row" :class="msg.role">
          <div class="msg-avatar">{{ msg.role === 'assistant' ? 'AI' : '你' }}</div>
          <div class="msg-bubble">{{ msg.content }}</div>
        </div>

        <div v-if="status" class="stream-status">
          <div class="spinner spinner-sm"></div>
          <span>{{ status }}</span>
        </div>
      </div>
      <button
        v-if="showBackToBottom"
        class="back-to-bottom"
        type="button"
        @click="jumpToBottom"
      >
        回到底部
      </button>

      <form class="composer" @submit.prevent="sendInput">
        <textarea
          v-model="draft"
          rows="3"
          placeholder="输入你想了解的问题..."
          :disabled="isStreaming"
          @keydown.enter.exact.prevent="sendInput"
        />

        <div class="composer-actions">
          <div class="composer-meta">
            <button class="mini-btn" type="button" :disabled="!draft" @click="clearDraft">清空</button>
            <button class="mini-btn" type="button" :disabled="!lastUserPrompt" @click="reuseLastPrompt">复用上次</button>
            <span class="draft-count">{{ draft.length }} 字</span>
          </div>
          <button v-if="!isStreaming" class="send-btn" type="submit" :disabled="!draft.trim()">发送</button>
          <button v-else class="stop-btn" type="button" @click="stopStreaming">停止</button>
        </div>
      </form>
    </aside>

    <transition name="toast-fade">
      <div v-if="toastMessage" class="subscribe-toast" role="status" aria-live="polite">
        {{ toastMessage }}
      </div>
    </transition>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import LogoIcon from '@/components/LogoIcon.vue'
import DashboardIcon from '@/components/icons/DashboardIcon.vue'
import SettingsIcon from '@/components/icons/SettingsIcon.vue'
import { useApi } from '@/composables/useApi'

const router = useRouter()
const { fetchDashboard, streamChat } = useApi()

const loadingFeed = ref(false)
const feedError = ref('')
const projects = ref([])
const daysFilter = ref(1)
const searchText = ref('')
const searchDraft = ref('')
const theme = ref('light')
const isSidebarCollapsed = ref(false)

const periodOptions = [
  { days: 1, label: '24小时' },
  { days: 7, label: '7天' },
  { days: 30, label: '30天' }
]

const CATEGORY_MAP = [
  { key: 'ai_ecosystem', label: 'AI生态' },
  { key: 'infra_and_tools', label: '基础设施' },
  { key: 'product_and_ui', label: '产品与UI' },
  { key: 'knowledge_base', label: '知识库' }
]

const messages = ref([
  {
    role: 'assistant',
    content: '我可以帮你对比项目、识别风险、给出落地建议。点击卡片里的“问 Copilot”开始。'
  }
])

const starterPrompts = [
  '帮我比较这个列表里最适合两周试点的 3 个项目。',
  '这个项目的落地风险和规避建议有哪些？',
  '如果要本周上线 MVP，优先做哪些能力？'
]

const draft = ref('')
const status = ref('')
const isStreaming = ref(false)
const abortController = ref(null)
const sessionId = ref(null)
const activeRepo = ref(null)
const messagesRef = ref(null)
const showBackToBottom = ref(false)
const expandedRepos = ref(new Set())
const lastUserPrompt = ref('')
const favoriteRepos = ref(new Set())
const subscribedRepos = ref(new Set())
const toastMessage = ref('')
const authLoading = ref(false)
const STORAGE_KEY = 'openscout-discover-chat'
const THEME_KEY = 'openscout-discover-theme'
const githubOauthLoginUrl = String(import.meta.env.VITE_GITHUB_OAUTH_LOGIN_URL || '').trim()

let persistTimer = null
let scrollFrame = 0
let toastTimer = null

const isDark = computed(() => theme.value === 'dark')
const themeClass = computed(() => (isDark.value ? 'theme-dark' : 'theme-light'))

const filteredProjects = computed(() => {
  const keyword = searchText.value.trim().toLowerCase()
  if (!keyword) return projects.value

  return projects.value.filter((item) => {
    const text = [
      item.repo_name,
      item.summary,
      item.description,
      ...(item.reasons || []),
      ...(item.use_cases || []),
      ...(item.tech_stack || [])
    ]
      .join(' ')
      .toLowerCase()

    return text.includes(keyword)
  })
})

function formatNumber(value) {
  return Number(value || 0).toLocaleString()
}

function applySearch() {
  searchText.value = searchDraft.value.trim()
}

function topStacks(project) {
  const stacks = (project.tech_stack || []).filter(Boolean).slice(0, 2)
  return stacks.length ? stacks : ['通用技术栈']
}

function shouldShowExpand(project) {
  const summary = String(project.summary || project.description || '')
  return summary.length > 90
}

function isRepoExpanded(repoName) {
  return expandedRepos.value.has(repoName)
}

function toggleRepoExpand(repoName) {
  const next = new Set(expandedRepos.value)
  if (next.has(repoName)) {
    next.delete(repoName)
  } else {
    next.add(repoName)
  }
  expandedRepos.value = next
}

function recommendationsText(project) {
  const reasons = (project.reasons || []).filter(Boolean)
  if (!reasons.length) return '暂无明确推荐理由'
  return reasons[0]
}

function estimateDifficulty(project) {
  let score = 0
  const category = project.category_label || ''

  if (category === '基础设施') score += 2
  if (category === 'AI生态' || category === '产品与UI') score += 1

  const stackCount = (project.tech_stack || []).length
  if (stackCount >= 4) score += 2
  else if (stackCount >= 2) score += 1

  const reasonsCount = (project.reasons || []).length
  if (reasonsCount >= 3) score += 1

  const summaryLen = String(project.summary || project.description || '').length
  if (summaryLen >= 120) score += 1

  if (score <= 2) return 'low'
  if (score <= 4) return 'medium'
  return 'high'
}

function difficultyLabel(level) {
  if (level === 'low') return '低'
  if (level === 'medium') return '中'
  return '高'
}

function inferUseCase(project) {
  if (project.use_cases?.[0]) return project.use_cases[0]
  if (project.reasons?.[1]) return project.reasons[1]
  return '适合快速验证和技术选型'
}

function projectAgeLabel(project) {
  const raw = project.updated_at || project.created_at || project.fetched_at || project.timestamp
  if (!raw) return 'recent'

  const ts = new Date(raw).getTime()
  if (Number.isNaN(ts)) return 'recent'

  const diffHours = Math.max(1, Math.floor((Date.now() - ts) / 3600000))
  if (diffHours < 24) return `${diffHours}h`

  const diffDays = Math.floor(diffHours / 24)
  if (diffDays < 30) return `${diffDays}d`

  return `${Math.floor(diffDays / 30)}mo`
}

async function loadFeed() {
  loadingFeed.value = true
  feedError.value = ''

  try {
    const data = await fetchDashboard(daysFilter.value)
    projects.value = CATEGORY_MAP.flatMap(({ key, label }) =>
      (data[key] || []).map((item) => ({
        ...item,
        category_label: label
      }))
    )
  } catch (err) {
    feedError.value = err.message || '加载失败'
  } finally {
    loadingFeed.value = false
  }
}

function toggleFavorite(project) {
  const next = new Set(favoriteRepos.value)
  if (next.has(project.repo_name)) {
    next.delete(project.repo_name)
  } else {
    next.add(project.repo_name)
  }
  favoriteRepos.value = next
  activeRepo.value = project
}

function toggleSubscribe(project) {
  const next = new Set(subscribedRepos.value)
  let isSubscribing = true
  if (next.has(project.repo_name)) {
    next.delete(project.repo_name)
    isSubscribing = false
  } else {
    next.add(project.repo_name)
  }
  subscribedRepos.value = next
  activeRepo.value = project
  showToast(isSubscribing ? '已加入自动化推送队列' : '已取消订阅推送')
}

function askOpenScout(project) {
  activeRepo.value = project
  draft.value = `请帮我分析 ${project.repo_name} 的落地价值、主要风险和优先实现建议。`
  queueScrollToBottom()
}

function startGithubOAuth() {
  if (!githubOauthLoginUrl) {
    showToast('请先配置 VITE_GITHUB_OAUTH_LOGIN_URL')
    return
  }

  authLoading.value = true
  window.location.href = githubOauthLoginUrl
}

function showToast(message) {
  toastMessage.value = message
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toastMessage.value = ''
    toastTimer = null
  }, 1800)
}

function applyStarter(text) {
  draft.value = text
}

function resetConversation() {
  messages.value = [
    {
      role: 'assistant',
      content: '会话已重置。你可以继续选择项目提问。'
    }
  ]
  sessionId.value = null
  status.value = ''
  isStreaming.value = false
  abortController.value = null
}

function toggleTheme() {
  theme.value = isDark.value ? 'light' : 'dark'
}

function toggleSidebar() {
  isSidebarCollapsed.value = !isSidebarCollapsed.value
}

async function sendInput() {
  const text = draft.value.trim()
  if (!text || isStreaming.value) return

  lastUserPrompt.value = text
  draft.value = ''
  messages.value.push({ role: 'user', content: text })
  isStreaming.value = true
  status.value = '正在分析中...'

  const currentMessage = reactive({ role: 'assistant', content: '' })
  let assistantAdded = false
  abortController.value = new AbortController()

  const query = activeRepo.value ? `[Context: ${activeRepo.value.repo_name}] ${text}` : text

  try {
    for await (const data of streamChat(query, {
      topK: 5,
      sessionId: sessionId.value,
      signal: abortController.value.signal
    })) {
      if (data.type === 'session') {
        sessionId.value = data.session_id
      } else if (data.type === 'status') {
        status.value = data.content
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
          messages.value.push(currentMessage)
          assistantAdded = true
        }
        currentMessage.content = data.content || '请求失败，请重试。'
      }
      queueScrollToBottom()
    }
  } catch (err) {
    if (err?.name !== 'AbortError') {
      messages.value.push({ role: 'assistant', content: err.message || '请求失败，请稍后重试。' })
    }
  } finally {
    isStreaming.value = false
    status.value = ''
    abortController.value = null
    queueScrollToBottom()
  }
}

function stopStreaming() {
  if (abortController.value) {
    abortController.value.abort()
  }
  isStreaming.value = false
  status.value = ''
}

function clearDraft() {
  draft.value = ''
}

function reuseLastPrompt() {
  if (!lastUserPrompt.value) return
  draft.value = lastUserPrompt.value
}

function handleMessageScroll() {
  const el = messagesRef.value
  if (!el) return
  const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
  showBackToBottom.value = distanceFromBottom > 120
}

function jumpToBottom() {
  queueScrollToBottom()
}

function queueScrollToBottom() {
  if (scrollFrame) return

  scrollFrame = requestAnimationFrame(async () => {
    scrollFrame = 0
    await nextTick()
    const el = messagesRef.value
    if (!el) return
    el.scrollTop = el.scrollHeight
    showBackToBottom.value = false
  })
}

function schedulePersist() {
  if (persistTimer) clearTimeout(persistTimer)

  persistTimer = setTimeout(() => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        messages: messages.value,
        sessionId: sessionId.value
      })
    )
  }, 320)
}

onMounted(async () => {
  const savedTheme = localStorage.getItem(THEME_KEY)
  if (savedTheme === 'dark' || savedTheme === 'light') {
    theme.value = savedTheme
  }

  await loadFeed()

  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')
    if (Array.isArray(saved.messages) && saved.messages.length > 0) {
      messages.value = saved.messages.slice(-120)
    }
    if (saved.sessionId) sessionId.value = saved.sessionId
  } catch (_) {
    // ignore malformed local storage
  }

  queueScrollToBottom()
})

onBeforeUnmount(() => {
  if (persistTimer) clearTimeout(persistTimer)
  if (scrollFrame) cancelAnimationFrame(scrollFrame)
  if (toastTimer) clearTimeout(toastTimer)
})

watch(daysFilter, () => {
  loadFeed()
})

watch(messages, schedulePersist, { deep: true })
watch(sessionId, schedulePersist)
watch(theme, (value) => {
  localStorage.setItem(THEME_KEY, value)
})
</script>

<style scoped>
:global(body) {
  background: #f3f4f6;
}

.paper-shell {
  --page-bg: #f3f4f6;
  --panel-bg: #ffffff;
  --panel-alt-bg: #f8fafc;
  --card-bg: #ffffff;
  --line: #e8ebf1;
  --line-strong: #d7deea;
  --text-main: #111827;
  --text-sub: #4b5563;
  --text-muted: #6b7280;
  --primary: #2563eb;
  --primary-soft: #e8f0ff;
  --btn-main-bg: #2563eb;
  --btn-main-bg-hover: #1d4ed8;
  --btn-main-text: #ffffff;
  --btn-sub-bg: #f3f4f6;
  --btn-sub-text: #374151;
  --star: #f59e0b;
  --stack-bg: rgba(37, 99, 235, 0.12);
  --stack-text: #1d4ed8;
  --chat-separator: rgba(37, 99, 235, 0.1);
  --chat-panel-width: 432px;
  --chat-panel-width-collapsed: 426px;

  height: 100dvh;
  display: grid;
  grid-template-columns: 232px minmax(0, 1fr) var(--chat-panel-width);
  gap: 14px;
  padding: 14px;
  background: var(--page-bg);
  color: var(--text-main);
  overflow: hidden;
}

.paper-shell.theme-dark {
  --page-bg: #0f172a;
  --panel-bg: #111827;
  --panel-alt-bg: #122037;
  --card-bg: #111827;
  --line: #263244;
  --line-strong: #37465d;
  --text-main: #f3f4f6;
  --text-sub: #cbd5e1;
  --text-muted: #94a3b8;
  --primary: #60a5fa;
  --primary-soft: rgba(96, 165, 250, 0.16);
  --btn-main-bg: #3b82f6;
  --btn-main-bg-hover: #2563eb;
  --btn-main-text: #eff6ff;
  --btn-sub-bg: #1f2937;
  --btn-sub-text: #d1d5db;
  --star: #fbbf24;
  --stack-bg: rgba(96, 165, 250, 0.18);
  --stack-text: #bfdbfe;
  --chat-separator: rgba(96, 165, 250, 0.22);
}

.paper-shell.theme-dark .repo-btn.primary {
  border-color: rgba(96, 165, 250, 0.5);
  background: rgba(96, 165, 250, 0.2);
  color: #dbeafe;
}

.paper-shell.theme-dark .repo-btn.primary:hover {
  background: rgba(96, 165, 250, 0.28);
}

.paper-shell.sidebar-collapsed {
  grid-template-columns: 88px minmax(0, 1fr) var(--chat-panel-width-collapsed);
}

.paper-shell.sidebar-collapsed .brand-block {
  grid-template-columns: 1fr;
  place-items: center;
  gap: 0;
}

.paper-shell.sidebar-collapsed .brand-block > div,
.paper-shell.sidebar-collapsed .nav-btn span,
.paper-shell.sidebar-collapsed .account-title,
.paper-shell.sidebar-collapsed .account-hint,
.paper-shell.sidebar-collapsed .account-alt-row,
.paper-shell.sidebar-collapsed .github-login-btn span,
.paper-shell.sidebar-collapsed .side-tool-btn span {
  display: none;
}

.paper-shell.sidebar-collapsed .account-card {
  padding: 6px;
}

.paper-shell.sidebar-collapsed .github-login-btn {
  min-height: 34px;
  justify-content: center;
  padding: 0;
}

.paper-shell.sidebar-collapsed .nav-btn,
.paper-shell.sidebar-collapsed .github-login-btn,
.paper-shell.sidebar-collapsed .side-tool-btn {
  justify-content: center;
  padding: 0;
}

.side-panel,
.feed-board,
.chat-panel {
  border: 1px solid var(--line);
  border-radius: 16px;
  background: var(--panel-bg);
  min-height: 0;
  overflow: hidden;
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.035);
}

.side-panel {
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  border-radius: 0;
  box-shadow: none;
}

.brand-block {
  padding: 2px 2px 0;
  display: grid;
  grid-template-columns: 56px 1fr;
  gap: 12px;
  align-items: center;
}

.brand-icon {
  width: 56px;
  height: 56px;
}

.brand-block h2 {
  font-size: 20px;
  line-height: 1.2;
}

.brand-subtitle {
  margin-top: 3px;
  font-size: 12px;
  color: #94a3b8;
  letter-spacing: 1px;
}

.side-divider {
  height: 1px;
  background: var(--line);
}

.side-nav {
  display: grid;
  gap: 10px;
}

.nav-btn {
  min-height: 43px;
  border-radius: 10px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-sub);
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 0 12px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
}

.nav-btn svg {
  width: 18px;
  height: 18px;
}

.nav-btn:hover {
  border-color: var(--line);
  background: var(--primary-soft);
}

.nav-btn.active {
  border-color: var(--line-strong);
  background: var(--primary-soft);
  color: var(--primary);
}

.side-footer {
  margin-top: auto;
  display: grid;
  gap: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--line);
}

.account-card {
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 10px;
  background: var(--panel-alt-bg);
  display: grid;
  gap: 8px;
}

.account-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-main);
}

.account-hint {
  font-size: 11px;
  line-height: 1.5;
  color: var(--text-muted);
}

.github-login-btn {
  min-height: 36px;
  border-radius: 10px;
  border: 1px solid var(--btn-main-bg);
  background: linear-gradient(135deg, var(--btn-main-bg), var(--btn-main-bg-hover));
  color: var(--btn-main-text);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 600;
  padding: 0 10px;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, opacity 0.2s ease;
}

.github-login-btn svg {
  width: 14px;
  height: 14px;
}

.github-login-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 10px 18px rgba(37, 99, 235, 0.24);
}

.github-login-btn:disabled {
  opacity: 0.72;
  cursor: not-allowed;
}

.account-alt-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.account-alt-btn {
  min-height: 30px;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: var(--panel-bg);
  color: var(--text-sub);
  font-size: 11px;
  cursor: pointer;
  transition: border-color 0.2s ease, color 0.2s ease, background-color 0.2s ease;
}

.account-alt-btn:hover {
  border-color: var(--line-strong);
  color: var(--text-main);
  background: rgba(37, 99, 235, 0.08);
}

.side-tool-btn {
  min-height: 34px;
  border-radius: 9px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 8px;
  transition: color 0.2s ease, border-color 0.2s ease, background-color 0.2s ease;
}

.side-tool-btn svg {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  transition: transform 0.2s ease;
}

.side-tool-btn:hover {
  color: var(--text-sub);
  border-color: var(--line);
  background: var(--panel-alt-bg);
}

.side-tool-btn.dark {
  color: var(--primary);
  border-color: rgba(37, 99, 235, 0.24);
  background: rgba(37, 99, 235, 0.08);
}

.side-tool-btn.dark:hover {
  border-color: rgba(37, 99, 235, 0.36);
  background: rgba(37, 99, 235, 0.12);
}

.feed-board {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  min-width: 0;
}

.feed-toolbar {
  width: 100%;
  max-width: 1260px;
  margin: 0 auto;
  padding: 18px 20px 16px;
  border-bottom: 1px solid var(--line);
}

.toolbar-top {
  display: flex;
  align-items: center;
  gap: 12px;
}

.title-wrap h1 {
  font-size: 24px;
  line-height: 1.2;
}

.title-wrap p {
  margin-top: 2px;
  color: var(--text-muted);
  font-size: 14px;
}

.toolbar-row {
  margin-top: 12px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
}

.search-box {
  min-height: 44px;
  border: 1px solid var(--line);
  border-radius: 11px;
  background: var(--card-bg);
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  padding: 0 10px;
}

.search-box svg {
  width: 15px;
  height: 15px;
  color: var(--text-muted);
}

.search-box input {
  border: none;
  width: 100%;
  outline: none;
  background: transparent;
  color: var(--text-main);
  font-size: 13px;
}

.search-box input::placeholder {
  color: var(--text-muted);
}

.search-btn {
  min-height: 32px;
  border-radius: 9px;
  border: 1px solid var(--btn-main-bg);
  background: var(--btn-main-bg);
  color: var(--btn-main-text);
  font-size: 12px;
  padding: 0 11px;
  cursor: pointer;
}

.search-btn:hover {
  background: var(--btn-main-bg-hover);
}

.period-group {
  display: flex;
  gap: 8px;
}

.period-btn {
  min-width: 60px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--panel-bg);
  color: var(--text-sub);
  font-size: 12px;
  cursor: pointer;
  padding: 0 12px;
}

.period-btn.active {
  border-color: var(--line-strong);
  color: var(--primary);
  background: var(--primary-soft);
}

.feed-grid {
  min-height: 0;
  overflow: auto;
  width: 100%;
  max-width: 1260px;
  margin: 0 auto;
  padding: 16px 20px 20px;
  display: grid;
  grid-template-columns: repeat(2, minmax(280px, 1fr));
  gap: 14px;
  align-content: start;
}

.repo-card {
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 13px;
  background: var(--card-bg);
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.045);
  display: flex;
  flex-direction: column;
}

.repo-card.selected {
  border-color: var(--primary);
  box-shadow: 0 0 0 1px var(--primary-soft), 0 10px 24px rgba(37, 99, 235, 0.08);
}

.repo-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
}

.repo-title-wrap {
  display: flex;
  gap: 8px;
  min-width: 0;
  align-items: flex-start;
}

.repo-title-main {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.repo-mark {
  width: 16px;
  height: 16px;
  color: var(--text-sub);
  margin-top: 2px;
  flex-shrink: 0;
}

.repo-title {
  color: var(--text-main);
  text-decoration: none;
  font-size: 16px;
  font-weight: 700;
  line-height: 1.28;
  word-break: break-word;
}

.repo-title:hover {
  color: var(--primary);
}

.repo-age {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
}

.repo-status-badge {
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 2px 8px;
  background: var(--panel-alt-bg);
  color: var(--text-muted);
  letter-spacing: 0.02em;
}

.repo-head-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.repo-icon-btn {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  border: 1px solid transparent;
  background: transparent;
  color: #9ca3af;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: color 0.2s ease, border-color 0.2s ease, background-color 0.2s ease, transform 0.2s ease;
}

.repo-icon-btn svg {
  width: 16px;
  height: 16px;
}

.repo-icon-btn:hover {
  transform: translateY(-1px);
}

.favorite-btn:hover {
  color: #f59e0b;
  border-color: rgba(245, 158, 11, 0.36);
  background: rgba(245, 158, 11, 0.12);
}

.favorite-btn.active {
  color: #d97706;
  border-color: rgba(245, 158, 11, 0.45);
  background: rgba(245, 158, 11, 0.16);
}

.subscribe-btn:hover {
  color: var(--primary);
  border-color: rgba(37, 99, 235, 0.34);
  background: rgba(37, 99, 235, 0.12);
}

.subscribe-btn.active {
  color: var(--primary);
  border-color: rgba(37, 99, 235, 0.44);
  background: rgba(37, 99, 235, 0.18);
}

.paper-shell.theme-dark .favorite-btn.active {
  color: #fbbf24;
}

.paper-shell.theme-dark .subscribe-btn.active {
  color: #93c5fd;
}

.repo-meta {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  font-size: 12px;
}

.meta-pill {
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 3px 9px;
  background: var(--panel-bg);
  color: var(--text-sub);
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.meta-pill.stars {
  color: #7a4f00;
  background: rgba(245, 158, 11, 0.12);
  border-color: rgba(245, 158, 11, 0.45);
}

.paper-shell.theme-dark .meta-pill.stars {
  color: #f8d38a;
  background: rgba(245, 158, 11, 0.2);
  border-color: rgba(245, 158, 11, 0.45);
}

.meta-pill.stars svg {
  width: 13px;
  height: 13px;
  color: var(--star);
}

.meta-pill.stack {
  background: var(--stack-bg);
  border-color: transparent;
  color: var(--stack-text);
}

.meta-pill.difficulty {
  font-weight: 600;
}

.difficulty-low {
  color: #166534;
}

.difficulty-medium {
  color: #a16207;
}

.difficulty-high {
  color: #b91c1c;
}

.paper-shell.theme-dark .difficulty-low {
  color: #86efac;
}

.paper-shell.theme-dark .difficulty-medium {
  color: #fcd34d;
}

.paper-shell.theme-dark .difficulty-high {
  color: #fca5a5;
}

.repo-summary {
  margin-top: 10px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-main);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.repo-summary.expanded {
  display: block;
  -webkit-line-clamp: unset;
  -webkit-box-orient: unset;
  overflow: visible;
}

.summary-toggle {
  margin-top: 6px;
  border: none;
  background: transparent;
  color: var(--primary);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  padding: 0;
}

.repo-tags {
  margin-top: 10px;
  display: grid;
  gap: 6px;
}

.tag {
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 6px 9px;
  font-size: 12px;
  line-height: 1.4;
  color: var(--text-sub);
  background: var(--panel-bg);
  white-space: normal;
  word-break: break-word;
}

.repo-actions {
  margin-top: auto;
  padding-top: 12px;
  display: flex;
  gap: 8px;
}

.repo-btn {
  min-height: 36px;
  border-radius: 10px;
  border: 1px solid var(--line);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.repo-btn.primary {
  border-color: rgba(37, 99, 235, 0.35);
  background: rgba(37, 99, 235, 0.08);
  color: #1d4ed8;
}

.repo-btn.primary:hover {
  background: rgba(37, 99, 235, 0.14);
}

.repo-btn.ask-btn {
  width: 100%;
}

.repo-btn.secondary {
  background: var(--btn-sub-bg);
  color: var(--btn-sub-text);
}

.chat-panel {
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: var(--panel-alt-bg);
  box-shadow: inset 1px 0 0 var(--chat-separator), -6px 0 20px rgba(15, 23, 42, 0.04);
  position: relative;
}

.chat-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  padding: 16px;
  border-bottom: 1px solid var(--line);
  background: var(--panel-bg);
}

.chat-head h2 {
  font-size: 18px;
  line-height: 1.2;
}

.ghost-btn {
  min-height: 30px;
  border-radius: 9px;
  border: 1px solid var(--line);
  background: var(--panel-bg);
  color: var(--text-sub);
  font-size: 12px;
  cursor: pointer;
  padding: 0 10px;
}

.starter-grid {
  padding: 10px 12px 0;
  display: grid;
  gap: 7px;
}

.starter-chip {
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--panel-bg);
  color: var(--text-sub);
  font-size: 12px;
  text-align: left;
  line-height: 1.4;
  padding: 8px 10px;
  cursor: pointer;
}

.starter-chip:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.message-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 16px 16px 64px;
  display: grid;
  gap: 12px;
  align-content: start;
  scrollbar-gutter: stable;
  background:
    radial-gradient(120% 80% at 50% -20%, rgba(37, 99, 235, 0.08), transparent 60%),
    transparent;
}

.message-list::-webkit-scrollbar {
  width: 10px;
}

.message-list::-webkit-scrollbar-track {
  background: rgba(148, 163, 184, 0.22);
  border-radius: 999px;
}

.message-list::-webkit-scrollbar-thumb {
  background: rgba(100, 116, 139, 0.55);
  border-radius: 999px;
}

.msg-row {
  display: flex;
  gap: 8px;
}

.msg-row.assistant .msg-avatar {
  background: var(--panel-bg);
  border-color: var(--line-strong);
  color: var(--text-main);
}

.msg-row.user {
  justify-content: flex-end;
}

.msg-row.user .msg-avatar {
  order: 2;
  background: var(--primary-soft);
  border-color: var(--line-strong);
  color: var(--primary);
}

.msg-avatar {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: var(--panel-bg);
  color: var(--text-sub);
  font-size: 11px;
  font-weight: 700;
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.msg-bubble {
  max-width: 84%;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--card-bg);
  padding: 9px 11px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-main);
  white-space: pre-wrap;
  word-break: break-word;
}

.msg-row.assistant .msg-bubble {
  background: var(--panel-bg);
  border-color: var(--line-strong);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
}

.msg-row.user .msg-bubble {
  background: linear-gradient(135deg, var(--btn-main-bg), var(--btn-main-bg-hover));
  border-color: transparent;
  color: var(--btn-main-text);
  box-shadow: 0 10px 20px rgba(37, 99, 235, 0.22);
}

.stream-status {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 12px;
  color: var(--text-muted);
}

.back-to-bottom {
  position: absolute;
  right: 18px;
  bottom: 126px;
  z-index: 2;
  min-height: 30px;
  border-radius: 999px;
  border: 1px solid var(--line-strong);
  background: var(--panel-bg);
  color: var(--text-sub);
  font-size: 12px;
  padding: 0 11px;
  cursor: pointer;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.12);
}

.composer {
  border-top: 1px solid var(--line);
  padding: 14px 16px;
  display: grid;
  gap: 9px;
  background: var(--panel-bg);
  box-shadow: 0 -12px 22px rgba(15, 23, 42, 0.08);
}

.subscribe-toast {
  position: absolute;
  top: 16px;
  right: 16px;
  z-index: 5;
  min-height: 36px;
  border-radius: 10px;
  border: 1px solid rgba(37, 99, 235, 0.35);
  background: rgba(37, 99, 235, 0.16);
  color: var(--text-main);
  padding: 8px 12px;
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.18);
  backdrop-filter: blur(6px);
}

.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}

.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

.composer textarea {
  width: 100%;
  border-radius: 11px;
  border: 1px solid var(--line);
  background: var(--card-bg);
  color: var(--text-main);
  font-size: 13px;
  line-height: 1.55;
  resize: none;
  padding: 11px;
  min-height: 92px;
  outline: none;
}

.composer textarea:focus {
  border-color: var(--line-strong);
}

.composer textarea::placeholder {
  color: var(--text-muted);
}

.composer-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.composer-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mini-btn {
  min-height: 28px;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: var(--panel-bg);
  color: var(--text-sub);
  font-size: 12px;
  padding: 0 9px;
  cursor: pointer;
}

.mini-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.draft-count {
  color: var(--text-muted);
  font-size: 12px;
}

.send-btn,
.stop-btn {
  min-width: 86px;
  min-height: 36px;
  border-radius: 11px;
  border: 1px solid var(--btn-main-bg);
  background: var(--btn-main-bg);
  color: var(--btn-main-text);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.send-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.stop-btn {
  border-color: var(--line);
  background: var(--btn-sub-bg);
  color: var(--btn-sub-text);
}

.state-block {
  margin: 16px;
  border: 1px dashed var(--line);
  border-radius: 14px;
  min-height: 170px;
  display: grid;
  place-items: center;
  text-align: center;
  color: var(--text-sub);
  padding: 16px;
}

.retry-btn {
  margin-top: 12px;
  min-height: 34px;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: var(--panel-bg);
  color: var(--text-sub);
  cursor: pointer;
  padding: 0 12px;
}

.spinner {
  width: 28px;
  height: 28px;
  border: 3px solid var(--line);
  border-top-color: var(--primary);
  border-radius: 999px;
  animation: spin 0.9s linear infinite;
}

.spinner-sm {
  width: 14px;
  height: 14px;
  border-width: 2px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 1520px) {
  .feed-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 1200px) {
  .paper-shell {
    height: auto;
    min-height: 100vh;
    grid-template-columns: 220px minmax(0, 1fr);
    overflow: visible;
  }

  .paper-shell.sidebar-collapsed {
    grid-template-columns: 88px minmax(0, 1fr);
  }

  .chat-panel {
    grid-column: 1 / -1;
    min-height: 520px;
  }
}

@media (max-width: 860px) {
  .paper-shell {
    grid-template-columns: 1fr;
    padding: 10px;
    gap: 10px;
  }

  .paper-shell.sidebar-collapsed {
    grid-template-columns: 1fr;
  }

  .side-nav {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .nav-btn {
    justify-content: center;
  }

  .toolbar-row {
    grid-template-columns: 1fr;
  }

  .repo-actions {
    display: block;
  }

  .composer-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .composer-meta {
    justify-content: space-between;
  }

  .back-to-bottom {
    bottom: 154px;
  }

  .msg-bubble {
    max-width: 92%;
  }

  .subscribe-toast {
    left: 12px;
    right: 12px;
    top: auto;
    bottom: 14px;
    justify-content: center;
  }
}
</style>
