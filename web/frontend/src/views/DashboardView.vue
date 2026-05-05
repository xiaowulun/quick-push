<template>
  <div class="dashboard-page" :class="{ dark: isDark }">
    <header class="topbar">
      <div class="topbar-left">
        <button class="brand" type="button" @click="scrollToTop">
          <span class="brand-icon">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M4.8 11.2 19.7 4.7 15 19.5l-3.5-4-3.3 2 .8-4.9z" />
            </svg>
          </span>
          <span class="brand-text">
            <strong>OpenScout</strong>
            <small>AI 驱动的开源洞察与决策助手</small>
          </span>
        </button>

        <nav class="top-nav" aria-label="一级导航">
          <button class="top-nav-btn" type="button" @click="router.push('/discover')">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="12" cy="12" r="8" />
              <path d="M12 12l4-4" />
              <path d="M11 11l5-3-3 5z" fill="currentColor" stroke="none" />
            </svg>
            <span>发现</span>
          </button>
          <button class="top-nav-btn active" type="button">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M4 5h6v6H4zM14 5h6v10h-6zM4 15h6v4H4zM14 17h6v2h-6z" />
            </svg>
            <span>仪表盘</span>
          </button>
        </nav>

        <TopbarSearch v-model="topbarSearch" @enter="handleTopbarSearch" />
      </div>

      <div class="topbar-right">
        <button class="theme-switch" type="button" @click="toggleTheme" :title="isDark ? '切换浅色模式' : '切换深色模式'">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="12" cy="12" r="4" />
            <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
          </svg>
          <span class="theme-track" :class="{ dark: isDark }">
            <i></i>
          </span>
        </button>
        <button class="icon-btn notify-btn" type="button" title="通知">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M15.2 18H4.8l1.4-1.4a2 2 0 0 0 .6-1.4V11a5.2 5.2 0 1 1 10.4 0v4.2a2 2 0 0 0 .6 1.4ZM10 18a2 2 0 1 0 4 0" />
          </svg>
          <span class="badge">{{ Math.max(3, urgentAlertCount) }}</span>
        </button>
        <div class="user-menu-wrap" ref="userMenuRef">
          <button class="user-chip" type="button">
            <img src="https://avatars.githubusercontent.com/u/1?v=4" alt="用户头像">
            <span class="user-meta">
              <strong>张小明</strong>
              <small>个人空间</small>
            </span>
            <em>Pro</em>
          </button>
          <button class="user-menu-toggle" type="button" @click.stop="toggleUserMenu" aria-label="打开用户菜单">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>
          </button>
          <div v-if="userMenuOpen" class="user-menu">
            <button type="button">用户信息</button>
            <button type="button">设置</button>
            <button type="button">我的收藏</button>
          </div>
        </div>
      </div>
    </header>

    <div class="body-shell">
      <aside class="left-rail">
        <div class="left-main">
          <div class="left-group">
            <p class="group-title">仪表盘</p>
            <button
              v-for="item in anchorItems"
              :key="item.key"
              class="rail-btn"
              :class="{ active: activeSection === item.key }"
              type="button"
              @click="scrollToSection(item.key)"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path v-if="item.key === 'watchlist'" d="M12 4 19 12 12 20 5 12z" />
                <path v-else-if="item.key === 'alerts'" d="M4 7h16M4 12h16M4 17h16" />
                <path v-else-if="item.key === 'compare'" d="M4 7h7v10H4zM13 7h7v4h-7zM13 13h7v4h-7z" />
                <path v-else d="M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 0-3 3z" />
              </svg>
              <span>{{ item.label }}</span>
            </button>
          </div>

          <div class="left-group">
            <p class="group-title">筛选视图</p>
            <button class="rail-btn" :class="{ active: priorityFilter === 'all' }" type="button" @click="priorityFilter = 'all'">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16" /></svg>
              <span>全部优先级</span>
            </button>
            <button class="rail-btn" :class="{ active: priorityFilter === 'high' }" type="button" @click="priorityFilter = 'high'">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 5 7v5c0 5 3.4 7.9 7 9 3.6-1.1 7-4 7-9V7z" /></svg>
              <span>只看高优先级</span>
            </button>
            <label class="sidebar-select">
              <span>关注分类</span>
              <select v-model="categoryFilter">
                <option value="all">全部分类</option>
                <option v-for="item in categoryOptions" :key="item.value" :value="item.value">
                  {{ item.label }}
                </option>
              </select>
            </label>
          </div>
        </div>

        <div class="left-bottom">
          <QuotaCard :quota-remain="quotaRemain" :quota-total="quotaTotal" :usage-percent="usagePercent" />
        </div>
      </aside>

      <main class="main-stage">
        <div v-if="loading" class="state-card">加载中...</div>
        <div v-else-if="error" class="state-card">
          <p class="state-title">加载失败</p>
          <p class="state-desc">{{ error }}</p>
          <button class="ghost-btn" type="button" @click="loadData">重试</button>
        </div>
        <div v-else-if="!hasData" class="state-card">
          <p class="state-title">暂无可展示的决策数据</p>
          <p class="state-desc">当前时间范围内还没有可用于构建个人决策中心的项目记录。</p>
        </div>

        <template v-else>
          <section class="hero-card">
            <div class="hero-main">
              <p class="hero-eyebrow">Dashboard</p>
              <h1>个人决策中心</h1>
              <p class="hero-desc">
                这里不再重复公共探索，而是把你的观察项目、待处理提醒、对比候选和历史决策放在一个工作台里。
              </p>
              <div class="hero-actions">
                <button class="primary-btn" type="button" @click="router.push('/discover')">去 Discover 继续探索</button>
                <button class="ghost-btn" type="button" @click="loadData">刷新决策信号</button>
              </div>
            </div>

            <div class="hero-side">
              <div class="freshness-card">
                <span class="freshness-dot" :class="{ stale: !isFreshToday }"></span>
                <div>
                  <p class="freshness-label">数据状态</p>
                  <strong>{{ freshnessText }}</strong>
                </div>
              </div>
              <div class="hero-note">
                左侧边栏沿用 Discover 的外壳，但内容改成个人决策导航和筛选。
              </div>
            </div>
          </section>

          <section class="summary-grid" aria-label="个人决策总览">
            <article class="summary-card">
              <p class="summary-label">观察项目</p>
              <strong class="summary-value">{{ formatNumber(filteredWatchlist.length) }}</strong>
              <span class="summary-meta">当前筛选后仍在关注池中的项目</span>
            </article>
            <article class="summary-card">
              <p class="summary-label">待处理提醒</p>
              <strong class="summary-value">{{ formatNumber(alertItems.length) }}</strong>
              <span class="summary-meta">其中高优先级 {{ urgentAlertCount }} 条</span>
            </article>
            <article class="summary-card">
              <p class="summary-label">近期对比候选</p>
              <strong class="summary-value">{{ formatNumber(compareCandidates.length) }}</strong>
              <span class="summary-meta">可直接回到 Discover 发起对比</span>
            </article>
            <article class="summary-card">
              <p class="summary-label">覆盖分类</p>
              <strong class="summary-value">{{ formatNumber(categoryCount) }}</strong>
              <span class="summary-meta">帮助判断关注范围是否过窄</span>
            </article>
          </section>

          <section class="content-grid">
            <section :id="sectionIds.watchlist" ref="watchlistRef" class="panel watchlist-panel">
              <header class="panel-head">
                <div>
                  <h2>我的观察列表</h2>
                  <p>默认只展示重点项，避免列表过长；需要时再展开全部。</p>
                </div>
                <button
                  v-if="filteredWatchlist.length > defaultWatchlistCount"
                  class="text-btn"
                  type="button"
                  @click="toggleWatchlist"
                >
                  {{ showAllWatchlist ? '收起' : `查看全部 ${filteredWatchlist.length} 个` }}
                </button>
              </header>

              <div class="watchlist-list">
                <article v-for="item in visibleWatchlist" :key="item.repo_name" class="watch-card">
                  <div class="watch-card-top">
                    <div>
                      <button class="repo-link" type="button" @click="openProject(item.repo_name)">
                        {{ item.repo_name }}
                      </button>
                      <p class="watch-meta">
                        <span>{{ categoryName(item.category) }}</span>
                        <span>{{ item.language }}</span>
                        <span>最近观察 {{ item.last_seen }}</span>
                      </p>
                    </div>
                    <span class="priority-badge" :class="item.priorityClass">{{ item.priorityText }}</span>
                  </div>

                  <div class="signal-grid">
                    <div class="signal-item">
                      <span>榜单增量</span>
                      <strong>+{{ item.stars_today }}</strong>
                    </div>
                    <div class="signal-item">
                      <span>上榜次数</span>
                      <strong>{{ item.appearances }}</strong>
                    </div>
                    <div class="signal-item">
                      <span>平均排名</span>
                      <strong>#{{ item.avg_rank }}</strong>
                    </div>
                    <div class="signal-item">
                      <span>总 Stars</span>
                      <strong>{{ formatCompact(item.stars) }}</strong>
                    </div>
                  </div>

                  <div class="watch-insight">
                    <p class="insight-title">当前判断</p>
                    <p class="insight-text">{{ item.insight }}</p>
                  </div>

                  <div class="watch-actions">
                    <button class="secondary-btn" type="button" @click="openProject(item.repo_name)">查看详情</button>
                    <button class="secondary-btn" type="button" @click="router.push('/discover')">加入对比</button>
                  </div>
                </article>
              </div>
            </section>

            <section :id="sectionIds.alerts" ref="alertsRef" class="panel">
              <header class="panel-head">
                <div>
                  <h2>待处理提醒</h2>
                  <p>系统建议你现在优先处理什么，而不是再列一遍项目。</p>
                </div>
              </header>
              <div v-if="alertItems.length" class="alert-list">
                <article v-for="item in alertItems" :key="item.id" class="alert-card" :class="item.level">
                  <div class="alert-row">
                    <span class="alert-level">{{ item.levelText }}</span>
                    <span class="alert-date">{{ item.date }}</span>
                  </div>
                  <p class="alert-title">{{ item.title }}</p>
                  <p class="alert-detail">{{ item.detail }}</p>
                </article>
              </div>
              <div v-else class="panel-empty">当前没有待处理提醒。</div>
            </section>

            <section :id="sectionIds.compare" ref="compareRef" class="panel">
              <header class="panel-head">
                <div>
                  <h2>我的对比面板</h2>
                  <p>先放最近值得比较的候选集，后续再接真实的个人对比历史。</p>
                </div>
                <button class="text-btn" type="button" @click="router.push('/discover')">去 Discover 对比</button>
              </header>
              <div v-if="compareCandidates.length" class="compare-list">
                <article v-for="item in compareCandidates" :key="item.repo_name" class="compare-card">
                  <div class="compare-top">
                    <strong>{{ item.repo_name }}</strong>
                    <span class="mini-tag">{{ item.language }}</span>
                  </div>
                  <p class="compare-desc">{{ item.compareReason }}</p>
                  <div class="compare-stats">
                    <span>+{{ item.stars_today }} 热度</span>
                    <span>{{ item.appearances }} 次上榜</span>
                  </div>
                </article>
              </div>
              <div v-else class="panel-empty">暂无可直接复用的对比候选。</div>
            </section>

            <section :id="sectionIds.history" ref="historyRef" class="panel">
              <header class="panel-head">
                <div>
                  <h2>历史决策记录</h2>
                  <p>帮助你快速回到最近一次决策上下文。</p>
                </div>
              </header>
              <div v-if="decisionRecords.length" class="history-overview">
                <div class="history-stat">
                  <span>最近对比</span>
                  <strong>{{ compareCandidates.length }}</strong>
                </div>
                <div class="history-stat">
                  <span>行动记录</span>
                  <strong>{{ decisionRecords.length }}</strong>
                </div>
                <div class="history-stat">
                  <span>最近观察池</span>
                  <strong>{{ visibleWatchlist.length }}</strong>
                </div>
              </div>

              <ol v-if="decisionRecords.length" class="history-list">
                <li
                  v-for="(item, index) in decisionRecords"
                  :key="`${item.type}-${item.date}-${item.title}-${index}`"
                  class="history-item"
                >
                  <span class="history-index">{{ index + 1 }}</span>
                  <div class="history-main">
                    <div class="history-top">
                      <span class="history-type" :class="item.type">{{ item.typeLabel }}</span>
                      <time class="history-date">{{ item.date }}</time>
                    </div>
                    <p class="history-title">{{ item.title }}</p>
                    <p class="history-detail">{{ item.detail }}</p>
                    <div class="history-meta">
                      <span>{{ item.source }}</span>
                      <span>{{ item.action }}</span>
                    </div>
                  </div>
                </li>
              </ol>
              <div v-else class="panel-empty">暂无历史记录。</div>
            </section>
          </section>
        </template>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import QuotaCard from '@/components/QuotaCard.vue'
import TopbarSearch from '@/components/TopbarSearch.vue'
import { useApi } from '@/composables/useApi'
import { getCategoryLabel } from '@/constants/categories'

const defaultWatchlistCount = 6
const quotaRemain = 320
const quotaTotal = 500
const usagePercent = 68
const THEME_KEY = 'openscout-dashboard-theme-v1'

const router = useRouter()
const { fetchDashboardInsights, loading, error } = useApi()

const sectionIds = {
  watchlist: 'dashboard-watchlist',
  alerts: 'dashboard-alerts',
  compare: 'dashboard-compare',
  history: 'dashboard-history',
}

const anchorItems = [
  { key: 'watchlist', label: '观察列表' },
  { key: 'alerts', label: '待处理提醒' },
  { key: 'compare', label: '我的对比' },
  { key: 'history', label: '历史记录' },
]

const topbarSearch = ref('')
const data = ref(null)
const showAllWatchlist = ref(false)
const priorityFilter = ref('all')
const categoryFilter = ref('all')
const activeSection = ref('watchlist')
const userMenuOpen = ref(false)
const userMenuRef = ref(null)
const theme = ref('light')
const isDark = computed(() => theme.value === 'dark')

const watchlistRef = ref(null)
const alertsRef = ref(null)
const compareRef = ref(null)
const historyRef = ref(null)

let observer = null

const summary = computed(() => data.value?.summary || {
  total_projects: 0,
  today_projects: 0,
  today_stars: 0,
})
const decisionProjects = computed(() => data.value?.decision_projects || [])
const recentActivities = computed(() => data.value?.recent_activities || [])
const dataDate = computed(() => String(data.value?.data_date || '').trim())
const isFreshToday = computed(() => Boolean(data.value?.is_fresh_today))
const hasData = computed(() => summary.value.total_projects > 0)

const freshnessText = computed(() => {
  if (!dataDate.value) return '暂无数据日期'
  return isFreshToday.value ? `${dataDate.value} · 今日数据` : `${dataDate.value} · 非今日数据`
})

const watchlistItems = computed(() => decisionProjects.value.map((project) => {
  const starsToday = Number(project.stars_today || 0)
  const appearances = Number(project.appearances || 0)
  const avgRank = Number(project.avg_rank || 0)

  let priorityText = '常规观察'
  let priorityClass = 'normal'
  let insight = '建议继续跟踪基本走势，必要时补一次项目详情分析。'

  if (starsToday >= 20 || (avgRank > 0 && avgRank <= 3)) {
    priorityText = '重点跟进'
    priorityClass = 'high'
    insight = '热度和排名都较强，适合优先进入下一轮项目对比。'
  } else if (appearances >= 3) {
    priorityText = '持续观察'
    priorityClass = 'medium'
    insight = '该项目已经连续多次进入观察范围，值得持续跟踪稳定性。'
  }

  return {
    ...project,
    avg_rank: avgRank > 0 ? avgRank.toFixed(1) : '-',
    priorityText,
    priorityClass,
    insight,
  }
}))

const categoryOptions = computed(() => {
  const seen = new Set()
  return watchlistItems.value
    .map((item) => String(item.category || ''))
    .filter((value) => {
      if (!value || seen.has(value)) return false
      seen.add(value)
      return true
    })
    .map((value) => ({ value, label: categoryName(value) }))
})

const filteredWatchlist = computed(() => watchlistItems.value.filter((item) => {
  if (priorityFilter.value === 'high' && item.priorityClass !== 'high') return false
  if (categoryFilter.value !== 'all' && item.category !== categoryFilter.value) return false
  return true
}))

const visibleWatchlist = computed(() => {
  if (showAllWatchlist.value) return filteredWatchlist.value
  return filteredWatchlist.value.slice(0, defaultWatchlistCount)
})

const alertItems = computed(() => {
  const derived = []

  for (const project of filteredWatchlist.value.slice(0, 8)) {
    const starsToday = Number(project.stars_today || 0)
    const appearances = Number(project.appearances || 0)

    if (starsToday >= 20) {
      derived.push({
        id: `${project.repo_name}-growth`,
        level: 'high',
        levelText: '高优先级',
        date: project.last_seen,
        title: `${project.repo_name} 热度明显上升`,
        detail: `今日新增 ${starsToday} stars，建议尽快加入对比，确认是否值得进入采用候选。`,
      })
    } else if (appearances >= 3) {
      derived.push({
        id: `${project.repo_name}-consistency`,
        level: 'medium',
        levelText: '建议处理',
        date: project.last_seen,
        title: `${project.repo_name} 持续上榜`,
        detail: `该项目已出现 ${appearances} 次，建议补一次项目详情或风险评估。`,
      })
    }
  }

  const mappedActivities = recentActivities.value.slice(0, 4).map((item, index) => ({
    id: `activity-${index}-${item.date}-${item.title}`,
    level: item.type === 'hot' ? 'high' : item.type === 'watch' ? 'medium' : 'low',
    levelText: item.type === 'hot' ? '高优先级' : item.type === 'watch' ? '建议处理' : '提示',
    date: item.date,
    title: item.title,
    detail: item.detail,
  }))

  return [...derived, ...mappedActivities].slice(0, 6)
})

const compareCandidates = computed(() => filteredWatchlist.value.slice(0, 4).map((project) => ({
  ...project,
  compareReason: Number(project.stars_today || 0) >= 15
    ? '热度增长较快，适合和你的主备选方案做快速比较。'
    : '当前信号稳定，适合放入中短期候选池继续观察。',
})))

const historyItems = computed(() => recentActivities.value.slice(0, 6))
const decisionRecords = computed(() => {
  const compareRecords = compareCandidates.value.slice(0, 2).map((item) => ({
    type: 'compare',
    typeLabel: '对比记录',
    date: item.last_seen,
    title: `${item.repo_name} 进入比较候选`,
    detail: item.compareReason,
    source: '来源：Discover / 加入对比',
    action: `动作：关注 +${item.stars_today} 热度变化`,
  }))

  const activityRecords = historyItems.value.slice(0, 3).map((item) => ({
    type: item.type === 'hot' ? 'alert' : 'review',
    typeLabel: item.type === 'hot' ? '行动事项' : '复查记录',
    date: item.date,
    title: item.title,
    detail: item.detail,
    source: '来源：系统信号',
    action: item.type === 'hot' ? '动作：建议立即处理' : '动作：保留在观察池',
  }))

  const watchRecords = visibleWatchlist.value.slice(0, 2).map((item) => ({
    type: 'watch',
    typeLabel: '观察池记录',
    date: item.last_seen,
    title: `${item.repo_name} 保持在观察池`,
    detail: item.insight,
    source: `来源：${categoryName(item.category)} / ${item.language}`,
    action: `动作：当前优先级为${item.priorityText}`,
  }))

  return [...compareRecords, ...activityRecords, ...watchRecords].slice(0, 6)
})
const urgentAlertCount = computed(() => alertItems.value.filter((item) => item.level === 'high').length)
const categoryCount = computed(() => new Set(filteredWatchlist.value.map((item) => String(item.category || ''))).size)

function formatNumber(value) {
  return new Intl.NumberFormat('zh-CN').format(Number(value || 0))
}

function formatCompact(value) {
  return new Intl.NumberFormat('zh-CN', {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(Number(value || 0))
}

function categoryName(raw) {
  return getCategoryLabel(raw)
}

function openProject(repoFullName) {
  if (!repoFullName) return
  router.push({
    name: 'ProjectDetail',
    params: { repoFullName },
  })
}

function handleTopbarSearch() {
  router.push('/discover')
}

function scrollToTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function scrollToSection(key) {
  activeSection.value = key
  const element = document.getElementById(sectionIds[key])
  if (!element) return
  element.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function toggleWatchlist() {
  showAllWatchlist.value = !showAllWatchlist.value
}

function toggleUserMenu() {
  userMenuOpen.value = !userMenuOpen.value
}

function handleOutsideClick(event) {
  const target = event?.target
  if (!target || !userMenuRef.value) return
  if (!userMenuRef.value.contains(target)) {
    userMenuOpen.value = false
  }
}

function toggleTheme() {
  theme.value = isDark.value ? 'light' : 'dark'
  localStorage.setItem(THEME_KEY, theme.value)
}

function setupSectionObserver() {
  if (observer) observer.disconnect()
  const sections = [
    { key: 'watchlist', el: watchlistRef.value },
    { key: 'alerts', el: alertsRef.value },
    { key: 'compare', el: compareRef.value },
    { key: 'history', el: historyRef.value },
  ].filter((item) => item.el)

  if (!sections.length) return

  observer = new IntersectionObserver(
    (entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0]
      if (!visible) return
      const match = sections.find((section) => section.el === visible.target)
      if (match) activeSection.value = match.key
    },
    {
      root: null,
      rootMargin: '-25% 0px -55% 0px',
      threshold: [0.1, 0.3, 0.6],
    }
  )

  for (const section of sections) {
    observer.observe(section.el)
  }
}

async function loadData() {
  try {
    data.value = await fetchDashboardInsights(7)
    await nextTick()
    setupSectionObserver()
  } catch (err) {
    console.error('Failed to load dashboard insights:', err)
  }
}

watch([priorityFilter, categoryFilter], () => {
  showAllWatchlist.value = false
})

onMounted(() => {
  const savedTheme = localStorage.getItem(THEME_KEY)
  if (savedTheme === 'dark' || savedTheme === 'light') {
    theme.value = savedTheme
  }
  loadData()
  window.addEventListener('click', handleOutsideClick)
})

onBeforeUnmount(() => {
  if (observer) observer.disconnect()
  window.removeEventListener('click', handleOutsideClick)
})
</script>

<style scoped>
.dashboard-page {
  --bg: #f6f8fd;
  --surface: #ffffff;
  --line: #e6ebf5;
  --line-2: #d7e3f6;
  --text-main: #111827;
  --text-sub: #4c5d7a;
  --text-muted: #8a9bb8;
  --brand: #5b6df5;
  --brand-soft: #edf2ff;
  min-height: 100vh;
  color: var(--text-main);
  background: var(--bg);
}

.dashboard-page.dark {
  --bg: #0f1525;
  --surface: #111b31;
  --line: #223553;
  --line-2: #2a4268;
  --text-main: #e8efff;
  --text-sub: #adc0e5;
  --text-muted: #869cc8;
  --brand: #89abff;
  --brand-soft: #1b2c4a;
}

.topbar {
  height: 76px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  padding: 0 18px 0 16px;
  background: var(--surface);
  border-bottom: 1px solid var(--line);
  position: sticky;
  top: 0;
  z-index: 40;
  backdrop-filter: blur(10px);
}

.topbar-left,
.topbar-right {
  display: flex;
  align-items: center;
  gap: 14px;
}

.topbar-left {
  position: relative;
  flex: 1;
  min-width: 0;
}

.brand {
  border: none;
  background: transparent;
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}

.brand-icon {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: linear-gradient(135deg, #2f63ff, #6f95ff);
  display: grid;
  place-items: center;
}

.brand-icon svg {
  width: 20px;
  height: 20px;
  fill: #fff;
}

.brand-text strong {
  display: block;
  text-align: left;
  font-size: 24px;
  line-height: 1.08;
  letter-spacing: -0.02em;
  color: var(--text-main);
}

.brand-text small {
  display: block;
  margin-top: 1px;
  text-align: left;
  color: var(--text-muted);
  font-size: 11px;
}

.top-nav {
  display: flex;
  gap: 18px;
  margin-left: 56px;
}

.top-nav-btn {
  position: relative;
  border: none;
  border-radius: 10px;
  background: transparent;
  min-height: 38px;
  padding: 0 14px;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-sub);
  cursor: pointer;
  font-weight: 700;
  font-size: 14px;
  transition: background-color 0.2s ease, color 0.2s ease;
}

.top-nav-btn svg,
.topbar-search svg,
.theme-switch svg,
.icon-btn svg,
.user-menu-toggle svg,
.rail-btn svg {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
}

.top-nav-btn::after {
  content: '';
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: -8px;
  height: 2px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--brand) 88%, #8db0ff 12%);
  opacity: 0;
  transform: scaleX(0.7);
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.top-nav-btn.active,
.top-nav-btn:hover {
  background: color-mix(in srgb, var(--brand-soft) 58%, var(--surface) 42%);
  color: var(--brand);
}

.top-nav-btn.active::after,
.top-nav-btn:hover::after {
  opacity: 1;
  transform: scaleX(1);
}

.topbar-search {
  position: absolute;
  left: 55%;
  top: 50%;
  transform: translate(-50%, -50%);
  border: 1px solid var(--line-2);
  border-radius: 12px;
  background: color-mix(in srgb, var(--surface) 88%, #eef3ff 12%);
  min-height: 40px;
  width: min(456px, 34vw);
  display: grid;
  grid-template-columns: 20px minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  padding: 0 10px 0 12px;
  z-index: 3;
}

.topbar-search input {
  border: none;
  background: transparent;
  color: var(--text-main);
  font-size: 13px;
  outline: none;
}

.topbar-search input::placeholder {
  color: var(--text-muted);
}

.topbar-search kbd {
  border: 1px solid var(--line-2);
  border-radius: 7px;
  min-width: 22px;
  height: 22px;
  padding: 0 6px;
  display: grid;
  place-items: center;
  font-size: 11px;
  font-weight: 700;
  color: var(--text-muted);
  background: color-mix(in srgb, var(--surface) 86%, #edf1fd 14%);
}

.theme-switch {
  border: 1px solid var(--line-2);
  border-radius: 999px;
  background: var(--surface);
  display: flex;
  align-items: center;
  gap: 8px;
  height: 38px;
  padding: 0 8px 0 10px;
  color: var(--text-sub);
  cursor: pointer;
}

.theme-track {
  width: 40px;
  height: 20px;
  border-radius: 999px;
  border: 1px solid var(--line-2);
  background: #e9eefb;
  padding: 1px;
  display: flex;
  align-items: center;
}

.theme-track i {
  width: 16px;
  height: 16px;
  border-radius: 999px;
  background: #fff;
  box-shadow: 0 2px 6px rgba(23, 35, 59, 0.2);
  transition: transform 0.2s ease;
}

.theme-track.dark {
  background: #3158c7;
}

.theme-track.dark i {
  transform: translateX(19px);
}

.icon-btn {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  border: 1px solid var(--line-2);
  background: var(--surface);
  color: var(--text-sub);
  display: grid;
  place-items: center;
  cursor: pointer;
  position: relative;
}

.notify-btn .badge {
  position: absolute;
  top: -4px;
  right: -4px;
  min-width: 15px;
  height: 15px;
  border-radius: 999px;
  background: #ef4444;
  color: #fff;
  font-size: 10px;
  display: grid;
  place-items: center;
}

.user-chip {
  border: 1px solid var(--line-2);
  border-radius: 999px;
  background: var(--surface);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 146px;
  padding: 4px 10px 4px 4px;
  cursor: pointer;
}

.user-chip img {
  width: 30px;
  height: 30px;
  border-radius: 999px;
}

.user-meta {
  min-width: 0;
  text-align: left;
}

.user-chip strong {
  display: block;
  color: var(--text-main);
  font-size: 13px;
}

.user-chip small {
  display: block;
  color: var(--text-muted);
  font-size: 11px;
}

.user-chip em {
  font-style: normal;
  color: var(--brand);
  font-size: 11px;
  font-weight: 800;
}

.user-menu-wrap {
  position: relative;
  display: flex;
  align-items: center;
  gap: 6px;
}

.user-menu-toggle {
  width: 30px;
  height: 30px;
  border: 1px solid var(--line-2);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text-sub);
  display: grid;
  place-items: center;
  cursor: pointer;
}

.user-menu {
  position: absolute;
  right: 0;
  top: calc(100% + 8px);
  min-width: 140px;
  border: 1px solid var(--line-2);
  border-radius: 10px;
  background: var(--surface);
  box-shadow: 0 10px 24px rgba(31, 47, 82, 0.16);
  padding: 6px;
  display: grid;
  gap: 4px;
  z-index: 20;
}

.user-menu button {
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text-sub);
  text-align: left;
  font-size: 13px;
  min-height: 32px;
  padding: 0 9px;
  cursor: pointer;
}

.user-menu button:hover {
  background: var(--brand-soft);
  color: var(--brand);
}

.body-shell {
  display: grid;
  grid-template-columns: 248px minmax(0, 1fr);
  gap: 16px;
  padding: 14px 16px 20px;
  align-items: start;
}

.left-rail {
  position: sticky;
  top: 88px;
  height: calc(100dvh - 100px);
  background: color-mix(in srgb, var(--surface) 92%, #eff4ff 8%);
  border: 1px solid var(--line);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.left-main,
.left-bottom {
  padding: 12px;
}

.left-main {
  overflow: auto;
}

.left-bottom {
  border-top: 1px solid var(--line);
  margin-top: auto;
}

.left-group {
  display: grid;
  gap: 6px;
  margin-bottom: 14px;
}

.group-title {
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 700;
}

.rail-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  border: none;
  border-radius: 10px;
  background: transparent;
  min-height: 38px;
  padding: 0 12px;
  color: var(--text-sub);
  cursor: pointer;
  font-size: 14px;
  font-weight: 700;
}

.rail-btn.active,
.rail-btn:hover {
  background: color-mix(in srgb, var(--brand-soft) 58%, var(--surface) 42%);
  color: var(--brand);
}

.sidebar-select {
  display: grid;
  gap: 8px;
  color: var(--text-sub);
  font-size: 13px;
}

.sidebar-select select {
  border: 1px solid var(--line-2);
  border-radius: 12px;
  background: color-mix(in srgb, var(--surface) 90%, #eff4ff 10%);
  color: var(--text-main);
  min-height: 38px;
  padding: 0 12px;
  outline: none;
}

.quota-box {
  border: 1px solid var(--line-2);
  border-radius: 16px;
  background: var(--brand-soft);
  padding: 14px;
}

.quota-box p {
  color: var(--text-sub);
  font-weight: 700;
  font-size: 13px;
}

.quota-progress {
  margin-top: 12px;
  height: 8px;
  border-radius: 999px;
  background: rgba(126, 161, 255, 0.22);
  overflow: hidden;
}

.quota-progress i {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, #3d6dff, #7fa2ff);
}

.quota-meta {
  margin-top: 10px;
  display: flex;
  justify-content: space-between;
  color: var(--text-sub);
  font-size: 13px;
}

.quota-upgrade {
  margin-top: 12px;
  width: 100%;
  min-height: 36px;
  border-radius: 12px;
  border: none;
  background: #5b6df5;
  color: #ffffff;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.main-stage {
  display: grid;
  gap: 14px;
}

.state-card,
.hero-card,
.summary-card,
.panel {
  border: 1px solid var(--line);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 12px 24px rgba(15, 23, 42, 0.04);
}

.state-card {
  padding: 24px;
  text-align: center;
}

.state-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-main);
}

.state-desc {
  margin-top: 8px;
  color: var(--text-muted);
}

.hero-card {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(280px, 0.8fr);
  gap: 18px;
  padding: 22px;
  background: linear-gradient(135deg, rgba(219, 234, 254, 0.7), rgba(255, 255, 255, 0.96));
}

.hero-eyebrow,
.insight-title {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.hero-eyebrow {
  color: #c2410c;
}

.hero-main h1 {
  margin-top: 10px;
  font-size: 40px;
  line-height: 1.05;
  color: var(--text-main);
}

.hero-desc,
.hero-note,
.summary-meta,
.watch-meta,
.compare-desc,
.alert-detail,
.history-detail,
.panel-head p,
.panel-empty {
  color: var(--text-muted);
  line-height: 1.7;
}

.hero-actions,
.watch-actions {
  display: flex;
  gap: 12px;
  margin-top: 18px;
}

.primary-btn,
.ghost-btn,
.secondary-btn,
.text-btn {
  border: none;
  border-radius: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.primary-btn,
.ghost-btn,
.secondary-btn {
  padding: 11px 16px;
  font-weight: 700;
}

.primary-btn {
  background: #0f172a;
  color: #ffffff;
}

.ghost-btn,
.secondary-btn {
  background: #eef2ff;
  color: #1e293b;
}

.text-btn {
  background: transparent;
  color: #2563eb;
  padding: 0;
  font-weight: 700;
}

.hero-side {
  display: grid;
  gap: 14px;
  align-content: start;
}

.freshness-card,
.hero-note {
  border: 1px solid var(--line);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.7);
  padding: 16px;
}

.freshness-card {
  display: flex;
  align-items: center;
  gap: 12px;
}

.freshness-label {
  margin-bottom: 4px;
  color: var(--text-muted);
  font-size: 12px;
}

.freshness-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: #16a34a;
  box-shadow: 0 0 0 6px rgba(34, 197, 94, 0.12);
}

.freshness-dot.stale {
  background: #ea580c;
  box-shadow: 0 0 0 6px rgba(249, 115, 22, 0.12);
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.summary-card {
  padding: 18px;
}

.summary-label {
  color: var(--text-sub);
  font-size: 13px;
}

.summary-value {
  display: block;
  margin-top: 8px;
  font-size: 30px;
  line-height: 1;
  color: var(--text-main);
}

.summary-meta {
  display: block;
  margin-top: 8px;
  font-size: 13px;
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(320px, 0.9fr);
  gap: 14px;
}

.watchlist-panel {
  grid-row: span 3;
}

.panel {
  padding: 18px;
}

.panel-head,
.watch-card-top,
.compare-top,
.alert-row {
  display: flex;
  justify-content: space-between;
  align-items: start;
  gap: 12px;
}

.panel-head h2 {
  font-size: 20px;
  color: var(--text-main);
}

.panel-head p {
  margin-top: 6px;
  font-size: 13px;
}

.watchlist-list,
.alert-list,
.compare-list,
.history-list {
  display: grid;
  gap: 14px;
}

.watch-card,
.alert-card,
.compare-card,
.history-item {
  border: 1px solid var(--line);
  border-radius: 16px;
  background: var(--surface);
}

.watch-card {
  padding: 16px;
}

.repo-link {
  border: none;
  background: transparent;
  padding: 0;
  cursor: pointer;
  font-size: 18px;
  font-weight: 700;
  text-align: left;
  color: var(--text-main);
}

.watch-meta,
.compare-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  margin-top: 6px;
  font-size: 13px;
}

.priority-badge,
.mini-tag,
.alert-level {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.priority-badge.high,
.alert-card.high .alert-level {
  background: #fee2e2;
  color: #b91c1c;
}

.priority-badge.medium,
.alert-card.medium .alert-level {
  background: #fef3c7;
  color: #b45309;
}

.priority-badge.normal,
.mini-tag,
.alert-card.low .alert-level {
  background: #e0f2fe;
  color: #075985;
}

.signal-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-top: 14px;
}

.signal-item {
  border-radius: 12px;
  background: #f8fafc;
  padding: 12px;
  display: grid;
  gap: 6px;
}

.signal-item span {
  color: var(--text-muted);
  font-size: 12px;
}

.watch-insight {
  margin-top: 14px;
  border-left: 3px solid #cbd5e1;
  padding-left: 12px;
}

.insight-title {
  color: var(--text-muted);
}

.insight-text {
  margin-top: 6px;
  color: var(--text-sub);
  line-height: 1.7;
}

.alert-card,
.compare-card,
.history-item {
  padding: 14px;
}

.alert-card.high {
  background: linear-gradient(180deg, #fff7f7, #ffffff);
}

.alert-card.medium {
  background: linear-gradient(180deg, #fffaf0, #ffffff);
}

.alert-card.low {
  background: linear-gradient(180deg, #f8fbff, #ffffff);
}

.alert-date,
.history-date {
  color: var(--text-muted);
  font-size: 12px;
}

.alert-title,
.history-title {
  margin-top: 10px;
  font-size: 15px;
  font-weight: 700;
  color: var(--text-main);
}

.compare-desc {
  margin-top: 8px;
}

.compare-stats {
  margin-top: 10px;
}

.history-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 12px;
  align-items: start;
}

.history-index {
  width: 28px;
  height: 28px;
  border-radius: 999px;
  background: #eff6ff;
  color: #2563eb;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
}

.history-overview {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 14px;
}

.history-stat {
  border: 1px solid var(--line);
  border-radius: 14px;
  background: color-mix(in srgb, var(--surface) 92%, #eff4ff 8%);
  padding: 12px;
  display: grid;
  gap: 6px;
}

.history-stat span {
  color: var(--text-muted);
  font-size: 12px;
}

.history-stat strong {
  color: var(--text-main);
  font-size: 22px;
  line-height: 1;
}

.history-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.history-type {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.history-type.compare {
  background: #e0f2fe;
  color: #075985;
}

.history-type.alert {
  background: #fee2e2;
  color: #b91c1c;
}

.history-type.review {
  background: #fef3c7;
  color: #b45309;
}

.history-type.watch {
  background: #ede9fe;
  color: #6d28d9;
}

.history-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  margin-top: 10px;
  color: var(--text-muted);
  font-size: 12px;
}

@media (max-width: 1280px) {
  .topbar {
    flex-direction: column;
    align-items: stretch;
    height: auto;
    padding: 12px 16px;
  }

  .topbar-left,
  .topbar-right {
    flex-wrap: wrap;
  }

  .topbar-search {
    position: static;
    transform: none;
    min-width: 0;
    width: 100%;
  }

  .body-shell,
  .content-grid,
  .summary-grid,
  .hero-card {
    grid-template-columns: 1fr;
  }

  .left-rail {
    position: static;
    height: auto;
  }
}

@media (max-width: 760px) {
  .signal-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .history-overview {
    grid-template-columns: 1fr;
  }

  .hero-actions,
  .watch-actions {
    flex-direction: column;
  }
}
</style>
