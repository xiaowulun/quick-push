<template>
  <div class="dashboard-view">
    <div v-if="loading" class="loading">
      <div class="spinner"></div>
      <div>加载中...</div>
    </div>

    <div v-else-if="error" class="error-state">
      <div class="error-state-icon">⚠️</div>
      <div class="error-state-title">加载失败</div>
      <div class="error-state-desc">{{ error }}</div>
      <button class="retry-btn" @click="loadData">重试</button>
    </div>

    <div v-else-if="!hasData" class="empty-state">
      <div class="empty-state-icon">📭</div>
      <div class="empty-state-title">暂无仪表盘数据</div>
      <div class="empty-state-desc">当前时间范围内没有可展示的数据，请稍后刷新。</div>
    </div>

    <template v-else>
      <section class="kpi-grid" aria-label="顶部总览">
        <article class="panel kpi-card">
          <p class="kpi-title">项目总数</p>
          <p class="kpi-desc">当前周期去重后的项目规模</p>
          <p class="kpi-value">{{ formatNumber(summary.total_projects) }}</p>
          <div class="sparkline-wrap">
            <canvas ref="totalSparkRef"></canvas>
          </div>
        </article>

        <article class="panel kpi-card">
          <p class="kpi-title">今日项目数</p>
          <p class="kpi-desc">今日进入趋势榜单的项目数量</p>
          <p class="kpi-value">{{ formatNumber(summary.today_projects) }}</p>
          <div class="sparkline-wrap">
            <canvas ref="todaySparkRef"></canvas>
          </div>
        </article>

        <article class="panel kpi-card">
          <p class="kpi-title">今日新增 Stars 总和</p>
          <p class="kpi-desc">用于衡量当前热度变化速度</p>
          <p class="kpi-value">{{ formatNumber(summary.today_stars) }}</p>
          <div class="sparkline-wrap">
            <canvas ref="starsSparkRef"></canvas>
          </div>
        </article>
      </section>

      <section class="trend-grid" aria-label="趋势层">
        <article class="panel trend-panel category-panel">
          <header class="panel-head">
            <h3>分类占比</h3>
            <span class="panel-sub">最近 7 天</span>
          </header>

          <div class="category-layout">
            <div class="chart-wrap donut-wrap">
              <canvas ref="categoryChartRef"></canvas>
            </div>

            <ul class="category-legend">
              <li v-for="item in categoryItems" :key="item.key" class="legend-item">
                <div class="legend-row">
                  <div class="legend-title-wrap">
                    <span class="legend-dot" :style="{ backgroundColor: item.color }"></span>
                    <span class="legend-title">{{ item.label }}</span>
                  </div>
                  <span class="legend-value">{{ item.count }} · {{ item.percentage }}%</span>
                </div>
                <div class="legend-bar">
                  <span class="legend-fill" :style="{ width: `${item.percentage}%`, backgroundColor: item.color }"></span>
                </div>
              </li>
            </ul>
          </div>
        </article>

        <article class="panel trend-panel language-panel">
          <header class="panel-head">
            <h3>语言分布</h3>
            <span class="panel-sub">Top 8</span>
          </header>

          <div class="chart-wrap bar-wrap">
            <canvas ref="languageChartRef"></canvas>
          </div>
        </article>
      </section>

      <section class="panel top10-panel" aria-label="Top 10 榜单">
        <header class="panel-head">
          <h3>Top 10 榜单</h3>
          <span class="panel-sub">按今日增量与稳定上榜排序</span>
        </header>

        <div class="table-wrap">
          <table class="top-table">
            <thead>
              <tr>
                <th class="col-rank">排位</th>
                <th class="col-project">项目</th>
                <th class="col-category">类别</th>
                <th class="col-language">语言</th>
                <th class="col-delta">今日新增</th>
                <th class="col-appear">上榜次数</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(project, index) in topProjects"
                :key="project.repo_name"
                role="button"
                tabindex="0"
                @click="openProject(project.repo_name)"
                @keydown.enter.prevent="openProject(project.repo_name)"
                @keydown.space.prevent="openProject(project.repo_name)"
              >
                <td class="rank-cell">{{ index + 1 }}</td>
                <td class="project-cell">
                  <img
                    class="repo-avatar"
                    :src="ownerAvatar(project.repo_name)"
                    :alt="project.repo_name"
                    loading="lazy"
                    @error="onAvatarError"
                  >
                  <div class="project-main">
                    <span class="repo-name">{{ project.repo_name }}</span>
                    <span class="stars-chip">⭐ {{ formatNumber(project.stars) }}</span>
                  </div>
                </td>
                <td>
                  <span class="tag category">{{ categoryName(project.category) }}</span>
                </td>
                <td>
                  <span class="tag language">{{ project.language }}</span>
                </td>
                <td>
                  <span class="delta-pill">+{{ project.stars_today }}</span>
                </td>
                <td>{{ project.appearances }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="panel activity-panel" aria-label="活动层">
        <header class="panel-head">
          <h3>活动层</h3>
          <span class="panel-sub">最近动态与重点信号</span>
        </header>

        <ol class="activity-list">
          <li
            v-for="(activity, index) in recentActivities"
            :key="`${activity.date}-${activity.title}-${index}`"
            class="activity-item"
          >
            <div class="activity-dot" :class="activity.type"></div>
            <div class="activity-main">
              <div class="activity-row">
                <p class="activity-title">{{ activity.title }}</p>
                <time class="activity-date">{{ activity.date }}</time>
              </div>
              <p class="activity-detail">{{ activity.detail }}</p>
            </div>
          </li>
        </ol>
      </section>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, inject, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { Chart, registerables } from 'chart.js'
import { useApi } from '@/composables/useApi'

Chart.register(...registerables)

const router = useRouter()
const { fetchDashboardInsights, loading, error } = useApi()
const timeFilter = inject('dashboardTimeFilter')

const data = ref(null)
const totalSparkRef = ref(null)
const todaySparkRef = ref(null)
const starsSparkRef = ref(null)
const categoryChartRef = ref(null)
const languageChartRef = ref(null)

let totalSparkChart = null
let todaySparkChart = null
let starsSparkChart = null
let categoryChart = null
let languageChart = null

const CATEGORY_STYLE = [
  { key: 'ai_ecosystem', label: 'AI生态', color: '#5F49D8' },
  { key: 'product_and_ui', label: '产品与UI', color: '#8B7AF5' },
  { key: 'infra_and_tools', label: '开发工具', color: '#61BAFB' }
]

const LANGUAGE_COLORS = ['#4F46E5', '#6366F1', '#7C3AED', '#06B6D4', '#0EA5E9', '#10B981', '#F59E0B', '#EC4899']

const summary = computed(() => data.value?.summary || {
  total_projects: 0,
  today_projects: 0,
  today_stars: 0
})

const hasData = computed(() => summary.value.total_projects > 0)
const timeline = computed(() => data.value?.stars_timeline || [])
const last7Timeline = computed(() => timeline.value.slice(-7))

const categoryDistribution = computed(() => data.value?.category_distribution || [])
const languageDistribution = computed(() => (data.value?.language_distribution || []).slice(0, 8))
const decisionProjects = computed(() => data.value?.decision_projects || [])
const topProjects = computed(() => decisionProjects.value.slice(0, 10))
const recentActivities = computed(() => data.value?.recent_activities || [])

const categoryItems = computed(() => {
  const sourceMap = new Map(categoryDistribution.value.map(item => [String(item.name || ''), item]))
  const raw = CATEGORY_STYLE.map((meta) => {
    const match = sourceMap.get(meta.key)
    return {
      ...meta,
      count: Number(match?.count || 0)
    }
  })

  const total = raw.reduce((sum, item) => sum + item.count, 0)
  return raw.map((item) => ({
    ...item,
    percentage: total > 0 ? Number(((item.count / total) * 100).toFixed(1)) : 0
  }))
})

function formatNumber(value) {
  return new Intl.NumberFormat('zh-CN').format(Number(value || 0))
}

function categoryName(raw) {
  const item = CATEGORY_STYLE.find(entry => entry.key === raw)
  return item?.label || raw || '未分类'
}

function ownerAvatar(repoName) {
  const owner = String(repoName || '').split('/')[0]
  return owner ? `https://github.com/${encodeURIComponent(owner)}.png?size=72` : 'https://github.githubassets.com/favicons/favicon.png'
}

function onAvatarError(event) {
  const img = event?.target
  if (!img || img.dataset.fallbackApplied === '1') return
  img.dataset.fallbackApplied = '1'
  img.src = 'https://github.githubassets.com/favicons/favicon.png'
}

function openProject(repoFullName) {
  if (!repoFullName) return
  router.push({
    name: 'ProjectDetail',
    params: { repoFullName }
  })
}

function destroyCharts() {
  for (const chart of [totalSparkChart, todaySparkChart, starsSparkChart, categoryChart, languageChart]) {
    if (chart) chart.destroy()
  }
  totalSparkChart = null
  todaySparkChart = null
  starsSparkChart = null
  categoryChart = null
  languageChart = null
}

function createSparkline(canvas, values, color) {
  if (!canvas) return null
  return new Chart(canvas.getContext('2d'), {
    type: 'line',
    data: {
      labels: last7Timeline.value.map(item => item.label),
      datasets: [
        {
          data: values,
          borderColor: color,
          backgroundColor: 'transparent',
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.35
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      scales: {
        x: { display: false },
        y: { display: false }
      }
    }
  })
}

function createKpiCharts() {
  if (last7Timeline.value.length === 0) return

  let cumulativeProjects = 0
  const totalSeries = last7Timeline.value.map(item => {
    if (typeof item.total_projects === 'number') {
      return Number(item.total_projects || 0)
    }
    cumulativeProjects += Number(item.projects || 0)
    return cumulativeProjects
  })

  const todaySeries = last7Timeline.value.map(item => Number(item.projects || 0))
  const starsSeries = last7Timeline.value.map(item => Number(item.stars_today || 0))

  totalSparkChart = createSparkline(totalSparkRef.value, totalSeries, '#2563eb')
  todaySparkChart = createSparkline(todaySparkRef.value, todaySeries, '#0ea5e9')
  starsSparkChart = createSparkline(starsSparkRef.value, starsSeries, '#8b5cf6')
}

function createCategoryChart() {
  if (!categoryChartRef.value || categoryItems.value.length === 0) return

  categoryChart = new Chart(categoryChartRef.value.getContext('2d'), {
    type: 'doughnut',
    data: {
      labels: categoryItems.value.map(item => item.label),
      datasets: [
        {
          data: categoryItems.value.map(item => item.count),
          backgroundColor: categoryItems.value.map(item => item.color),
          borderWidth: 0
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '66%',
      plugins: {
        legend: { display: false }
      }
    }
  })
}

function createLanguageChart() {
  if (!languageChartRef.value || languageDistribution.value.length === 0) return

  languageChart = new Chart(languageChartRef.value.getContext('2d'), {
    type: 'bar',
    data: {
      labels: languageDistribution.value.map(item => item.name),
      datasets: [
        {
          data: languageDistribution.value.map(item => item.count),
          backgroundColor: languageDistribution.value.map((_, index) => LANGUAGE_COLORS[index % LANGUAGE_COLORS.length]),
          borderRadius: 8,
          borderSkipped: false,
          barThickness: 18
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: 'y',
      plugins: { legend: { display: false } },
      scales: {
        x: {
          ticks: { color: '#6b7280' },
          grid: { color: '#e5e7eb' }
        },
        y: {
          ticks: { color: '#374151' },
          grid: { display: false }
        }
      }
    }
  })
}

async function renderCharts() {
  destroyCharts()
  await nextTick()
  if (!hasData.value) return
  createKpiCharts()
  createCategoryChart()
  createLanguageChart()
}

async function loadData() {
  try {
    const selectedDays = Number(timeFilter?.value || 7)
    const days = Math.max(7, selectedDays)
    data.value = await fetchDashboardInsights(days)
    await renderCharts()
  } catch (err) {
    console.error('Failed to load dashboard insights:', err)
  }
}

watch(timeFilter, () => {
  loadData()
})

onMounted(() => {
  loadData()
})

onUnmounted(() => {
  destroyCharts()
})
</script>

<style scoped>
.dashboard-view {
  display: grid;
  gap: 14px;
  padding: 14px;
  border-radius: 14px;
  border: 1px solid #dfe4ec;
  background: linear-gradient(180deg, #f8faff, #f3f4f6);
}

.panel {
  background: #ffffff;
  border: 1px solid #dfe4ec;
  border-radius: 14px;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.04);
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.kpi-card {
  padding: 14px;
}

.kpi-title {
  font-size: 14px;
  font-weight: 700;
  color: #111827;
}

.kpi-desc {
  margin-top: 4px;
  color: #6b7280;
  font-size: 12px;
  line-height: 1.45;
  min-height: 34px;
}

.kpi-value {
  margin-top: 10px;
  font-size: 36px;
  line-height: 1;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: #111827;
}

.sparkline-wrap {
  margin-top: 10px;
  height: 64px;
}

.trend-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.trend-panel {
  padding: 14px;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.panel-head h3 {
  font-size: 16px;
  font-weight: 700;
  color: #111827;
}

.panel-sub {
  font-size: 12px;
  color: #6b7280;
}

.category-layout {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 16px;
  align-items: center;
}

.chart-wrap {
  position: relative;
}

.donut-wrap,
.bar-wrap {
  height: 248px;
}

.category-legend {
  list-style: none;
  display: grid;
  gap: 10px;
}

.legend-item {
  border: 1px solid #e6e8ef;
  border-radius: 10px;
  background: #fafbff;
  padding: 10px;
  display: grid;
  gap: 7px;
}

.legend-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.legend-title-wrap {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.12);
}

.legend-title {
  font-size: 13px;
  font-weight: 600;
  color: #1f2937;
}

.legend-value {
  font-size: 12px;
  color: #6b7280;
}

.legend-bar {
  height: 6px;
  border-radius: 999px;
  background: #e5e7eb;
  overflow: hidden;
}

.legend-fill {
  display: block;
  height: 100%;
  border-radius: 999px;
}

.language-panel .bar-wrap {
  height: 330px;
}

.top10-panel,
.activity-panel {
  padding: 14px;
}

.table-wrap {
  overflow-x: auto;
}

.top-table {
  width: 100%;
  min-width: 860px;
  border-collapse: collapse;
}

.top-table th,
.top-table td {
  padding: 11px 8px;
  border-bottom: 1px solid #e5e7eb;
  text-align: left;
  font-size: 12px;
  color: #374151;
}

.top-table th {
  font-size: 11px;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.top-table tbody tr {
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.top-table tbody tr:hover {
  background: #f8fafc;
}

.top-table tbody tr:focus-visible {
  outline: 2px solid #93c5fd;
  outline-offset: -2px;
}

.rank-cell {
  width: 70px;
  font-weight: 700;
  color: #2563eb;
}

.project-cell {
  display: flex;
  align-items: center;
  gap: 9px;
}

.repo-avatar {
  width: 30px;
  height: 30px;
  border-radius: 999px;
  border: 1px solid #d1d5db;
  object-fit: cover;
  flex-shrink: 0;
}

.project-main {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.repo-name {
  font-size: 13px;
  font-weight: 700;
  color: #111827;
}

.stars-chip {
  font-size: 11px;
  color: #92400e;
  background: #fef3c7;
  border: 1px solid #fcd34d;
  border-radius: 999px;
  padding: 2px 7px;
  white-space: nowrap;
}

.tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid transparent;
}

.tag.category {
  color: #4c1d95;
  background: #ede9fe;
  border-color: #c4b5fd;
}

.tag.language {
  color: #0f766e;
  background: #ecfeff;
  border-color: #a5f3fc;
}

.delta-pill {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid #86efac;
  background: #ecfdf5;
  color: #15803d;
  font-weight: 600;
}

.activity-list {
  list-style: none;
  display: grid;
  gap: 10px;
}

.activity-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px;
  border: 1px solid #e3e8f0;
  border-radius: 12px;
  background: #f9fafb;
}

.activity-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: #3b82f6;
  margin-top: 5px;
  flex-shrink: 0;
}

.activity-dot.hot {
  background: #f59e0b;
}

.activity-dot.system {
  background: #10b981;
}

.activity-dot.insight {
  background: #8b5cf6;
}

.activity-main {
  flex: 1;
  min-width: 0;
}

.activity-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.activity-title {
  font-size: 13px;
  font-weight: 700;
  color: #111827;
}

.activity-date {
  font-size: 11px;
  color: #6b7280;
}

.activity-detail {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.45;
  color: #4b5563;
}

@media (max-width: 1280px) {
  .kpi-grid,
  .trend-grid {
    grid-template-columns: 1fr;
  }

  .category-layout {
    grid-template-columns: 1fr;
  }
}
</style>
