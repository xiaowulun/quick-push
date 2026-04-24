<template>
  <router-view v-if="isDiscoverRoute" />

  <div v-else class="paper-shell" :class="[themeClass, { 'sidebar-collapsed': isSidebarCollapsed }]">
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
        <button class="nav-btn" :class="{ active: route.path === '/chat' }" type="button" aria-label="发现" @click="router.push('/chat')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <circle cx="12" cy="12" r="8" />
            <path d="M12 12l4-4" />
            <path d="M11 11l5-3-3 5z" fill="currentColor" stroke="none" />
          </svg>
          <span>发现</span>
        </button>
        <button
          class="nav-btn"
          :class="{ active: route.path === '/dashboard' || route.path.startsWith('/projects/') }"
          type="button"
          aria-label="仪表盘"
          @click="router.push('/dashboard')"
        >
          <DashboardIcon />
          <span>仪表盘</span>
        </button>
        <button class="nav-btn" :class="{ active: route.path === '/settings' }" type="button" aria-label="设置" @click="router.push('/settings')">
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
            <button class="account-alt-btn" type="button" title="飞书登录（即将上线）" @click="showToast('飞书登录即将上线')">
              飞书
            </button>
            <button class="account-alt-btn" type="button" title="邮箱登录（即将上线）" @click="showToast('邮箱登录即将上线')">
              邮箱
            </button>
          </div>
        </section>
      </div>
    </aside>

    <main class="content-board">
      <header class="content-header">
        <h1>{{ pageTitle }}</h1>
        <div v-if="showTimeFilter" class="header-controls">
          <TimeFilter
            :options="timeFilterOptions"
            :model-value="currentTimeFilter"
            @update:model-value="handleTimeFilterChange"
          />
        </div>
      </header>

      <div class="content-body">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </div>
    </main>

    <transition name="toast-fade">
      <div v-if="toastMessage" class="global-toast" role="status" aria-live="polite">
        {{ toastMessage }}
      </div>
    </transition>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, provide, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LogoIcon from '@/components/LogoIcon.vue'
import TimeFilter from '@/components/TimeFilter.vue'
import DashboardIcon from '@/components/icons/DashboardIcon.vue'
import SettingsIcon from '@/components/icons/SettingsIcon.vue'

const route = useRoute()
const router = useRouter()

const pageTitles = {
  '/dashboard': '项目仪表盘',
  '/trends': '趋势分析',
  '/settings': '系统设置'
}

const isDiscoverRoute = computed(() => route.path === '/chat')

const pageTitle = computed(() => {
  if (route.path.startsWith('/projects/')) {
    const repo = String(route.params.repoFullName || '').trim()
    return repo ? `项目详情 · ${repo}` : '项目详情'
  }
  return pageTitles[route.path] || 'OpenScout'
})

const showTimeFilter = computed(() => route.path === '/trends')

const dashboardTimeFilter = ref(7)
const trendsTimeFilter = ref(7)
const theme = ref('light')
const isSidebarCollapsed = ref(false)
const authLoading = ref(false)
const toastMessage = ref('')

const THEME_KEY = 'openscout-app-theme'
const SIDEBAR_KEY = 'openscout-app-sidebar-collapsed'
const githubOauthLoginUrl = String(import.meta.env.VITE_GITHUB_OAUTH_LOGIN_URL || '').trim()

let toastTimer = null

const isDark = computed(() => theme.value === 'dark')
const themeClass = computed(() => (isDark.value ? 'theme-dark' : 'theme-light'))

const currentTimeFilter = computed({
  get: () => {
    if (route.path === '/dashboard') return dashboardTimeFilter.value
    if (route.path === '/trends') return trendsTimeFilter.value
    return 7
  },
  set: (value) => {
    if (route.path === '/dashboard') {
      dashboardTimeFilter.value = value
    } else if (route.path === '/trends') {
      trendsTimeFilter.value = value
    }
  }
})

const timeFilterOptions = computed(() => {
  if (route.path === '/trends') {
    return [
      { days: 7, label: '本周' },
      { days: 30, label: '本月' }
    ]
  }
  return []
})

function handleTimeFilterChange(days) {
  currentTimeFilter.value = days
}

function showToast(message) {
  toastMessage.value = message
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toastMessage.value = ''
    toastTimer = null
  }, 2200)
}

function startGithubOAuth() {
  if (authLoading.value) return
  if (!githubOauthLoginUrl) {
    showToast('未配置 Github OAuth 登录地址')
    return
  }
  authLoading.value = true
  window.location.href = githubOauthLoginUrl
  setTimeout(() => {
    authLoading.value = false
  }, 1200)
}

function toggleTheme() {
  theme.value = isDark.value ? 'light' : 'dark'
}

function toggleSidebar() {
  isSidebarCollapsed.value = !isSidebarCollapsed.value
}

onMounted(() => {
  const savedTheme = localStorage.getItem(THEME_KEY)
  if (savedTheme === 'dark' || savedTheme === 'light') {
    theme.value = savedTheme
  }

  const savedCollapsed = localStorage.getItem(SIDEBAR_KEY)
  if (savedCollapsed === '1') {
    isSidebarCollapsed.value = true
  }
})

onBeforeUnmount(() => {
  if (toastTimer) {
    clearTimeout(toastTimer)
    toastTimer = null
  }
})

watch(theme, (value) => {
  localStorage.setItem(THEME_KEY, value)
})

watch(isSidebarCollapsed, (value) => {
  localStorage.setItem(SIDEBAR_KEY, value ? '1' : '0')
})

provide('dashboardTimeFilter', dashboardTimeFilter)
provide('trendsTimeFilter', trendsTimeFilter)
</script>

<style scoped>
.paper-shell {
  --page-bg: #f3f4f6;
  --panel-bg: #ffffff;
  --panel-alt-bg: #f8fafc;
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

  height: 100dvh;
  display: grid;
  grid-template-columns: 232px minmax(0, 1fr);
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
}

.paper-shell.sidebar-collapsed {
  grid-template-columns: 88px minmax(0, 1fr);
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
.content-board {
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

.content-board {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
}

.content-header {
  padding: 14px 16px;
  border-bottom: 1px solid var(--line);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.content-header h1 {
  font-size: 28px;
  line-height: 1.2;
}

.content-body {
  min-height: 0;
  overflow: auto;
}

.header-controls {
  display: flex;
  align-items: center;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.global-toast {
  position: absolute;
  top: 24px;
  right: 24px;
  z-index: 20;
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

  .content-header {
    position: sticky;
    top: 0;
    z-index: 5;
    backdrop-filter: blur(8px);
  }
}
</style>
