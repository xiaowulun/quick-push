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
    
    <template v-else-if="data">
      <div v-if="totalProjects === 0" class="empty-state">
        <div class="empty-state-icon">📭</div>
        <div class="empty-state-title">暂无数据</div>
        <div class="empty-state-desc">当前时间范围内没有项目数据，请稍后再试</div>
      </div>
      
      <template v-else>
        <div class="stats-grid">
          <StatCard :value="totalProjects" label="总项目数" />
          <StatCard :value="activeCategories" label="活跃分类" />
          <StatCard :value="aiProjects" label="AI 项目" />
          <StatCard :value="devTools" label="开发工具" />
        </div>
        
        <CategorySection
          v-for="category in categoriesWithData"
          :key="category.key"
          :title="category.title"
          :projects="category.projects"
        />
      </template>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, inject, watch, onMounted } from 'vue'
import StatCard from '@/components/StatCard.vue'
import CategorySection from '@/components/CategorySection.vue'
import { useApi } from '@/composables/useApi'

const { fetchDashboard, loading, error } = useApi()
const timeFilter = inject('dashboardTimeFilter')

const data = ref(null)

const categories = [
  { key: 'ai_ecosystem', title: 'AI 生态' },
  { key: 'infra_and_tools', title: '开发工具' },
  { key: 'product_and_ui', title: '产品与 UI' },
  { key: 'knowledge_base', title: '知识库' }
]

const totalProjects = computed(() => {
  if (!data.value) return 0
  return categories.reduce((sum, cat) => {
    return sum + (data.value[cat.key]?.length || 0)
  }, 0)
})

const activeCategories = computed(() => {
  if (!data.value) return 0
  return categories.filter(cat => data.value[cat.key]?.length > 0).length
})

const aiProjects = computed(() => {
  return data.value?.ai_ecosystem?.length || 0
})

const devTools = computed(() => {
  return data.value?.infra_and_tools?.length || 0
})

const categoriesWithData = computed(() => {
  if (!data.value) return []
  return categories
    .filter(cat => data.value[cat.key]?.length > 0)
    .map(cat => ({
      ...cat,
      projects: data.value[cat.key]
    }))
})

async function loadData() {
  try {
    data.value = await fetchDashboard(timeFilter.value)
  } catch (err) {
    console.error('Failed to load dashboard:', err)
  }
}

watch(timeFilter, () => {
  loadData()
})

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.dashboard-view {
  min-height: 400px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 32px;
}

@media (max-width: 1024px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
