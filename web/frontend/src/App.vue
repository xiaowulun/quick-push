<template>
  <div class="app-container">
    <aside class="sidebar">
      <header class="sidebar-header">
        <div class="logo">
          <LogoIcon class="logo-icon" />
          <span class="logo-text">QuickPush</span>
        </div>
      </header>
      
      <nav class="sidebar-nav">
        <router-link 
          v-for="item in navItems" 
          :key="item.path"
          :to="item.path"
          class="nav-item"
          :class="{ active: $route.path === item.path }"
        >
          <component :is="item.icon" />
          {{ item.label }}
        </router-link>
      </nav>
    </aside>
    
    <main class="main-content">
      <header class="main-header">
        <h1 class="page-title">{{ pageTitle }}</h1>
        <div v-if="showTimeFilter" class="header-controls">
          <TimeFilter 
            :options="timeFilterOptions"
            :model-value="currentTimeFilter"
            @update:model-value="handleTimeFilterChange"
          />
        </div>
      </header>
      
      <div class="page-container">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </div>
    </main>
  </div>
</template>

<script setup>
import { computed, provide, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import LogoIcon from '@/components/LogoIcon.vue'
import TimeFilter from '@/components/TimeFilter.vue'
import ChatIcon from '@/components/icons/ChatIcon.vue'
import DashboardIcon from '@/components/icons/DashboardIcon.vue'
import TrendsIcon from '@/components/icons/TrendsIcon.vue'
import SettingsIcon from '@/components/icons/SettingsIcon.vue'

const route = useRoute()

const navItems = [
  { path: '/chat', label: '聊天', icon: ChatIcon },
  { path: '/dashboard', label: '仪表盘', icon: DashboardIcon },
  { path: '/trends', label: '趋势分析', icon: TrendsIcon },
  { path: '/settings', label: '设置', icon: SettingsIcon }
]

const pageTitles = {
  '/chat': '聊天',
  '/dashboard': '仪表盘',
  '/trends': '趋势分析',
  '/settings': '设置'
}

const pageTitle = computed(() => pageTitles[route.path] || 'QuickPush')

const showTimeFilter = computed(() => {
  return route.path === '/dashboard' || route.path === '/trends'
})

const dashboardTimeFilter = ref(1)
const trendsTimeFilter = ref(7)

const currentTimeFilter = computed({
  get: () => {
    if (route.path === '/dashboard') return dashboardTimeFilter.value
    if (route.path === '/trends') return trendsTimeFilter.value
    return 1
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
  if (route.path === '/dashboard') {
    return [
      { days: 1, label: '今日' },
      { days: 7, label: '本周' },
      { days: 30, label: '本月' }
    ]
  } else if (route.path === '/trends') {
    return [
      { days: 7, label: '本周' },
      { days: 30, label: '本月' }
    ]
  }
  return []
})

const handleTimeFilterChange = (days) => {
  currentTimeFilter.value = days
}

provide('dashboardTimeFilter', dashboardTimeFilter)
provide('trendsTimeFilter', trendsTimeFilter)
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
