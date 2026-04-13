<template>
  <div class="trends-view">
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
    
    <div v-else-if="data && data.total_projects === 0" class="empty-state">
      <div class="empty-state-icon">📭</div>
      <div class="empty-state-title">暂无趋势数据</div>
      <div class="empty-state-desc">当前时间范围内没有足够的数据来展示趋势分析</div>
    </div>
    
    <template v-else-if="data">
      <div class="stats-grid">
        <StatCard :value="data.total_projects" label="项目总数" />
        <StatCard :value="data.total_records" label="记录总数" />
        <StatCard :value="data.category_trends?.length || 0" label="分类数量" />
        <StatCard :value="data.language_trends?.length || 0" label="语言种类" />
      </div>
      
      <div class="trends-grid">
        <div class="chart-card">
          <h3 class="chart-title">分类趋势（{{ timeFilter }}天）</h3>
          <div class="chart-container">
            <canvas ref="categoryChartRef"></canvas>
          </div>
        </div>
        
        <div class="chart-card">
          <h3 class="chart-title">语言分布</h3>
          <div class="language-list">
            <div 
              v-for="(lang, index) in topLanguages" 
              :key="lang.language"
              class="language-item"
            >
              <div 
                class="language-color" 
                :style="{ background: languageColors[index % languageColors.length] }"
              ></div>
              <div class="language-info">
                <span class="language-name">{{ lang.language }}</span>
                <span class="language-count">{{ lang.count }}</span>
              </div>
              <div class="language-bar">
                <div 
                  class="language-bar-fill" 
                  :style="{ 
                    width: `${(lang.count / maxLanguageCount) * 100}%`,
                    background: languageColors[index % languageColors.length]
                  }"
                ></div>
              </div>
            </div>
          </div>
        </div>
        
        <div class="chart-card full-width">
          <h3 class="chart-title">热门项目排行 TOP 10</h3>
          <div class="ranking-list">
            <div 
              v-for="(proj, index) in topProjects" 
              :key="proj.repo_name"
              class="ranking-item"
            >
              <div class="rank-number" :class="getRankClass(index)">
                {{ index + 1 }}
              </div>
              <div class="rank-content">
                <span class="rank-project">{{ proj.repo_name }}</span>
                <div class="rank-stats">
                  <span class="rank-badge">{{ proj.appearances }} 次</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, inject, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { Chart, registerables } from 'chart.js'
import StatCard from '@/components/StatCard.vue'
import { useApi } from '@/composables/useApi'

Chart.register(...registerables)

const { fetchTrends, loading, error } = useApi()
const timeFilter = inject('trendsTimeFilter')

const data = ref(null)
const categoryChartRef = ref(null)
let chartInstance = null

const languageColors = [
  '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
  '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9'
]

const topLanguages = computed(() => {
  return data.value?.language_trends?.slice(0, 10) || []
})

const maxLanguageCount = computed(() => {
  return Math.max(...topLanguages.value.map(l => l.count), 1)
})

const topProjects = computed(() => {
  return data.value?.hot_projects?.slice(0, 10) || []
})

function getRankClass(index) {
  if (index === 0) return 'rank-1'
  if (index === 1) return 'rank-2'
  if (index === 2) return 'rank-3'
  return 'rank-other'
}

function getCategoryName(category) {
  const names = {
    'ai_ecosystem': 'AI 生态',
    'infra_and_tools': '开发工具',
    'product_and_ui': '产品与 UI',
    'knowledge_base': '知识库',
    'unknown': '未分类'
  }
  return names[category] || category
}

function createChart() {
  if (!categoryChartRef.value || !data.value?.category_trends?.length) return
  
  if (chartInstance) {
    chartInstance.destroy()
  }
  
  const ctx = categoryChartRef.value.getContext('2d')
  const categoryTrends = data.value.category_trends
  
  chartInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: categoryTrends.map(c => getCategoryName(c.category)),
      datasets: [{
        data: categoryTrends.map(c => c.count),
        backgroundColor: [
          'rgba(255, 109, 90, 0.85)',
          'rgba(255, 184, 77, 0.85)',
          'rgba(78, 205, 196, 0.85)',
          'rgba(149, 225, 211, 0.85)',
          'rgba(243, 129, 129, 0.85)'
        ],
        borderColor: [
          'rgba(255, 109, 90, 1)',
          'rgba(255, 184, 77, 1)',
          'rgba(78, 205, 196, 1)',
          'rgba(149, 225, 211, 1)',
          'rgba(243, 129, 129, 1)'
        ],
        borderWidth: 2,
        hoverOffset: 15,
        hoverBorderWidth: 3
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '65%',
      plugins: {
        legend: {
          position: 'right',
          labels: {
            color: '#E5E5E5',
            font: { size: 13, weight: '500' },
            padding: 14,
            usePointStyle: true,
            pointStyle: 'circle'
          }
        },
        tooltip: {
          backgroundColor: 'rgba(30, 30, 45, 0.95)',
          titleColor: '#E5E5E5',
          bodyColor: '#E5E5E5',
          borderColor: 'rgba(123, 104, 238, 0.3)',
          borderWidth: 1,
          padding: 12,
          displayColors: true,
          callbacks: {
            label: function(context) {
              const label = context.label || ''
              const value = context.parsed || 0
              const total = context.dataset.data.reduce((a, b) => a + b, 0)
              const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0
              return `${label}: ${value} (${percentage}%)`
            }
          }
        }
      },
      animation: {
        animateScale: true,
        animateRotate: true,
        duration: 800,
        easing: 'easeOutQuart'
      }
    }
  })
}

async function loadData() {
  try {
    data.value = await fetchTrends(timeFilter.value)
    await nextTick()
    createChart()
  } catch (err) {
    console.error('Failed to load trends:', err)
  }
}

watch(timeFilter, () => {
  loadData()
})

onMounted(() => {
  loadData()
})

onUnmounted(() => {
  if (chartInstance) {
    chartInstance.destroy()
  }
})
</script>

<style scoped>
.trends-view {
  min-height: 400px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.trends-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

.chart-card {
  background: var(--bg-card);
  backdrop-filter: blur(10px);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  padding: 20px;
}

.chart-card.full-width {
  grid-column: 1 / -1;
}

.chart-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 16px;
  color: var(--text-primary);
}

.chart-container {
  position: relative;
  height: 250px;
}

.language-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.language-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.language-color {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
}

.language-info {
  flex: 1;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.language-name {
  font-size: 13px;
  color: var(--text-primary);
}

.language-count {
  font-size: 12px;
  color: var(--text-muted);
}

.language-bar {
  flex: 1;
  height: 4px;
  background: var(--border-color);
  border-radius: 2px;
  overflow: hidden;
  margin-left: 12px;
}

.language-bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.5s ease;
}

.ranking-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ranking-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 12px;
  transition: all 0.3s ease;
}

.ranking-item:hover {
  background: rgba(123, 104, 238, 0.05);
  transform: translateX(4px);
}

.rank-number {
  font-size: 16px;
  font-weight: 700;
  width: 32px;
  text-align: center;
  flex-shrink: 0;
}

.rank-1 { color: #FFD700; text-shadow: 0 0 10px rgba(255, 215, 0, 0.5); }
.rank-2 { color: #C0C0C0; text-shadow: 0 0 10px rgba(192, 192, 192, 0.5); }
.rank-3 { color: #CD7F32; text-shadow: 0 0 10px rgba(205, 127, 50, 0.5); }
.rank-other { color: var(--text-muted); }

.rank-content {
  flex: 1;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.rank-project {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
}

.rank-badge {
  background: var(--primary-gradient);
  color: white;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
}

@media (max-width: 1024px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .trends-grid {
    grid-template-columns: 1fr;
  }
}
</style>
