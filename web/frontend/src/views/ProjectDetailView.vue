<template>
  <div class="project-detail-view">
    <div v-if="loading" class="loading">
      <div class="spinner"></div>
      <div>正在加载项目详情...</div>
    </div>

    <div v-else-if="error" class="error-state">
      <div class="error-state-icon">!</div>
      <div class="error-state-title">加载失败</div>
      <div class="error-state-desc">{{ error }}</div>
      <button class="retry-btn" @click="loadData">重试</button>
    </div>

    <template v-else-if="detail">
      <section class="hero-card">
        <div class="hero-actions">
          <button class="ghost-btn" @click="goBack">返回</button>
          <a :href="detail.basic.url" target="_blank" rel="noopener" class="ghost-btn">GitHub</a>
        </div>

        <h2 class="repo-title">{{ detail.basic.repo_full_name }}</h2>
        <p class="repo-summary">{{ detail.summary || detail.basic.description || '暂无项目摘要。' }}</p>

        <div class="meta-grid">
          <div class="meta-item">
            <div class="meta-label">语言</div>
            <div class="meta-value">{{ detail.basic.language || 'Unknown' }}</div>
          </div>
          <div class="meta-item">
            <div class="meta-label">分类</div>
            <div class="meta-value">{{ categoryDisplay(detail.basic.category) }}</div>
          </div>
          <div class="meta-item">
            <div class="meta-label">Stars</div>
            <div class="meta-value">{{ formatNumber(detail.basic.stars) }}</div>
          </div>
          <div class="meta-item meta-item-accent">
            <div class="meta-label">今日增量</div>
            <div class="meta-value positive">+{{ formatNumber(detail.basic.stars_today) }}</div>
          </div>
          <div class="meta-item">
            <div class="meta-label">最佳排名</div>
            <div class="meta-value">{{ detail.trend_summary?.best_rank || '-' }}</div>
          </div>
          <div class="meta-item">
            <div class="meta-label">出现次数</div>
            <div class="meta-value">{{ detail.basic.total_appearances || 0 }}</div>
          </div>
        </div>
      </section>

      <section class="content-grid">
        <article class="panel">
          <h3>推荐理由</h3>
          <ul class="reason-list">
            <li v-for="reason in detail.reasons" :key="reason">{{ reason }}</li>
            <li v-if="!detail.reasons?.length" class="muted">暂无推荐理由。</li>
          </ul>
        </article>

        <article class="panel">
          <h3>适用场景</h3>
          <div class="tag-list">
            <span v-for="item in displayUseCases" :key="`use-${item}`" class="tag tag-alt">{{ item }}</span>
            <span v-if="!displayUseCases.length" class="muted">暂无适用场景。</span>
          </div>
          <p v-if="isUseCaseFallback" class="hint">已根据摘要与推荐理由做智能推断。</p>
        </article>

        <article class="panel">
          <h3>技术栈</h3>
          <div class="tag-list">
            <span v-for="item in displayTechStack" :key="`tech-${item}`" class="tag">{{ item }}</span>
            <span v-if="!displayTechStack.length" class="muted">暂无技术栈。</span>
          </div>
          <p v-if="isTechFallback" class="hint">已根据语言与语义关键词做智能推断。</p>
        </article>

        <article class="panel">
          <h3>标签画像</h3>
          <div class="tag-list">
            <span v-for="item in detail.suitable_for" :key="`fit-${item}`" class="tag tag-neutral">{{ item }}</span>
            <span v-if="!detail.suitable_for?.length" class="muted">暂无画像标签。</span>
          </div>
          <div class="profile-strip">
            <span class="chip">成熟度：{{ detail.maturity || 'unknown' }}</span>
            <span class="chip">复杂度：{{ detail.complexity || 'unknown' }}</span>
          </div>
        </article>

        <article class="panel panel-wide">
          <div class="panel-head">
            <h3>趋势信息</h3>
            <span class="muted">最近 {{ chartHistory.length || 0 }} 条记录</span>
          </div>
          <div v-if="chartHistory.length" class="trend-chart-wrap">
            <canvas ref="trendChartRef"></canvas>
          </div>
          <div v-else class="muted">暂无趋势数据。</div>
          <div class="trend-foot">
            <span>首次出现：{{ formatDate(detail.trend_summary?.first_seen) }}</span>
            <span>最近出现：{{ formatDate(detail.trend_summary?.last_seen) }}</span>
            <span>日均新增：{{ Number(detail.trend_summary?.avg_stars_today || 0).toFixed(1) }}</span>
          </div>
        </article>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Chart, registerables } from 'chart.js'
import { useApi } from '@/composables/useApi'
import { getCategoryLabel } from '@/constants/categories'

Chart.register(...registerables)

const route = useRoute()
const router = useRouter()
const { fetchProjectDetail, loading, error } = useApi()

const detail = ref(null)
const trendChartRef = ref(null)
let trendChart = null

const repoFullName = computed(() => {
  const raw = String(route.params.repoFullName || '')
  try {
    return decodeURIComponent(raw)
  } catch (_) {
    return raw
  }
})

const chartHistory = computed(() => {
  const list = detail.value?.trend_history || []
  return [...list].reverse()
})

const displayTechStack = computed(() => {
  const raw = detail.value?.tech_stack || []
  if (raw.length) return raw
  const fallback = []
  const language = detail.value?.basic?.language
  if (language && String(language).toLowerCase() !== 'unknown') {
    fallback.push(language)
  }
  for (const item of detail.value?.keywords || []) {
    if (fallback.length >= 8) break
    fallback.push(item)
  }
  return dedupe(fallback).slice(0, 8)
})

const displayUseCases = computed(() => {
  const raw = detail.value?.use_cases || []
  if (raw.length) return raw
  const fromProfile = detail.value?.suitable_for || []
  if (fromProfile.length) return fromProfile
  return (detail.value?.keywords || []).slice(0, 6)
})

const isTechFallback = computed(() => (detail.value?.tech_stack || []).length === 0 && displayTechStack.value.length > 0)
const isUseCaseFallback = computed(() => (detail.value?.use_cases || []).length === 0 && displayUseCases.value.length > 0)

function dedupe(items) {
  const seen = new Set()
  const result = []
  for (const raw of items) {
    const text = String(raw || '').trim()
    if (!text) continue
    const key = text.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    result.push(text)
  }
  return result
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString()
}

function formatDate(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleDateString()
}

function categoryDisplay(value) {
  return getCategoryLabel(value)
}

function goBack() {
  if (window.history.length > 1) {
    router.back()
    return
  }
  router.push('/dashboard')
}

function renderTrendChart() {
  if (!trendChartRef.value) return
  if (trendChart) {
    trendChart.destroy()
  }
  const history = chartHistory.value
  if (!history.length) return

  const labels = history.map(item => formatDate(item.record_date))
  const stars = history.map(item => Number(item.stars || 0))
  const starsToday = history.map(item => Number(item.stars_today || 0))

  trendChart = new Chart(trendChartRef.value.getContext('2d'), {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Stars',
          data: stars,
          borderColor: '#5f49d8',
          backgroundColor: 'rgba(95, 73, 216, 0.14)',
          fill: true,
          tension: 0.34,
          pointRadius: 2,
          pointHoverRadius: 4
        },
        {
          label: '日增',
          data: starsToday,
          borderColor: '#61bafb',
          backgroundColor: 'rgba(97, 186, 251, 0.2)',
          tension: 0.28,
          fill: false,
          pointRadius: 2
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          labels: {
            color: '#475569',
            boxWidth: 10,
            boxHeight: 10
          }
        },
        tooltip: {
          backgroundColor: '#0f172a',
          titleColor: '#e2e8f0',
          bodyColor: '#e2e8f0',
          borderColor: 'rgba(148, 163, 184, 0.35)',
          borderWidth: 1
        }
      },
      scales: {
        x: {
          ticks: { color: '#64748b', maxRotation: 0, autoSkip: true },
          grid: { color: 'rgba(148, 163, 184, 0.2)' }
        },
        y: {
          ticks: { color: '#64748b' },
          grid: { color: 'rgba(148, 163, 184, 0.2)' }
        }
      }
    }
  })
}

async function loadData() {
  if (!repoFullName.value) return
  try {
    detail.value = await fetchProjectDetail(repoFullName.value)
    await nextTick()
    renderTrendChart()
  } catch (_) {
    detail.value = null
  }
}

watch(
  () => route.params.repoFullName,
  async () => {
    await loadData()
  }
)

onMounted(async () => {
  await loadData()
})

onUnmounted(() => {
  if (trendChart) trendChart.destroy()
})
</script>

<style scoped>
.project-detail-view {
  --pd-bg: #f4f6fb;
  --pd-card: #ffffff;
  --pd-border: #dfe5ef;
  --pd-border-strong: #cfd9e9;
  --pd-text: #0f172a;
  --pd-sub: #475569;
  --pd-muted: #64748b;

  min-height: 420px;
  color: var(--pd-text);
}

:global(.paper-shell.theme-dark) .project-detail-view {
  --pd-bg: #0f172a;
  --pd-card: #111827;
  --pd-border: #2f3b52;
  --pd-border-strong: #3e4c67;
  --pd-text: #f1f5f9;
  --pd-sub: #cbd5e1;
  --pd-muted: #94a3b8;
}

.hero-card {
  position: relative;
  border: 1px solid var(--pd-border-strong);
  background:
    radial-gradient(980px 320px at 8% -30%, rgba(95, 73, 216, 0.14), transparent 60%),
    radial-gradient(780px 260px at 92% -20%, rgba(97, 186, 251, 0.16), transparent 65%),
    var(--pd-card);
  border-radius: 20px;
  padding: 22px;
  margin-bottom: 14px;
}

.hero-actions {
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
}

.ghost-btn {
  border: 1px solid var(--pd-border);
  color: var(--pd-sub);
  background: rgba(148, 163, 184, 0.08);
  border-radius: 999px;
  padding: 7px 13px;
  cursor: pointer;
  text-decoration: none;
}

.ghost-btn:hover {
  color: var(--pd-text);
  border-color: var(--pd-border-strong);
  background: rgba(148, 163, 184, 0.14);
}

.repo-title {
  font-size: clamp(24px, 3vw, 34px);
  line-height: 1.2;
  margin-bottom: 10px;
  letter-spacing: -0.02em;
  word-break: break-word;
  color: var(--pd-text);
}

.repo-summary {
  font-size: 16px;
  line-height: 1.8;
  color: var(--pd-sub);
  margin-bottom: 14px;
  max-width: 980px;
}

.meta-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
}

.meta-item {
  border: 1px solid var(--pd-border);
  border-radius: 14px;
  padding: 10px;
  background: rgba(148, 163, 184, 0.07);
}

.meta-item-accent {
  border-color: rgba(95, 73, 216, 0.3);
  background: rgba(95, 73, 216, 0.08);
}

.meta-label {
  color: var(--pd-muted);
  font-size: 12px;
  margin-bottom: 4px;
}

.meta-value {
  font-size: 18px;
  font-weight: 700;
  color: var(--pd-text);
}

.meta-value.positive {
  color: #5f49d8;
}

.content-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.panel {
  border: 1px solid var(--pd-border);
  border-radius: 16px;
  padding: 16px;
  background: var(--pd-card);
}

.panel h3 {
  margin: 0 0 10px;
  font-size: 18px;
  color: var(--pd-text);
}

.panel-wide {
  grid-column: 1 / -1;
}

.reason-list {
  display: grid;
  gap: 8px;
  margin: 0;
  padding-left: 18px;
}

.reason-list li {
  line-height: 1.7;
  color: var(--pd-sub);
  font-size: 15px;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag {
  padding: 6px 11px;
  border-radius: 999px;
  font-size: 12px;
  border: 1px solid rgba(95, 73, 216, 0.35);
  background: rgba(95, 73, 216, 0.1);
  color: #5f49d8;
}

.tag-alt {
  border-color: rgba(97, 186, 251, 0.5);
  background: rgba(97, 186, 251, 0.16);
  color: #0c6baa;
}

.tag-neutral {
  border-color: rgba(100, 116, 139, 0.35);
  background: rgba(148, 163, 184, 0.16);
  color: var(--pd-sub);
}

.hint {
  margin-top: 8px;
  font-size: 12px;
  color: var(--pd-muted);
}

.profile-strip {
  margin-top: 12px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.chip {
  font-size: 12px;
  border: 1px solid var(--pd-border);
  background: rgba(148, 163, 184, 0.07);
  border-radius: 10px;
  padding: 5px 10px;
  color: var(--pd-sub);
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.trend-chart-wrap {
  height: 290px;
}

.trend-foot {
  margin-top: 12px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  color: var(--pd-muted);
  font-size: 12px;
}

.muted {
  color: var(--pd-muted);
  font-size: 12px;
}

@media (max-width: 1200px) {
  .meta-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .content-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .hero-card {
    border-radius: 16px;
    padding: 16px;
  }

  .meta-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .trend-chart-wrap {
    height: 230px;
  }

  .trend-foot {
    grid-template-columns: 1fr;
  }
}
</style>
