<template>
  <div class="category-section">
    <div class="category-header">
      <h3 class="category-title">
        {{ title }}
        <span class="category-count">{{ projects.length }} 个项目</span>
      </h3>
    </div>
    <div class="projects-grid">
      <ProjectCard 
        v-for="project in projects" 
        :key="project.repo_name"
        :project="project"
      />
    </div>
  </div>
</template>

<script setup>
import ProjectCard from './ProjectCard.vue'

defineProps({
  title: {
    type: String,
    required: true
  },
  projects: {
    type: Array,
    required: true
  }
})
</script>

<style scoped>
.category-section {
  margin-bottom: 32px;
}

.category-header {
  margin-bottom: 16px;
}

.category-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 8px;
}

.category-count {
  font-size: 12px;
  color: var(--text-muted);
  background: rgba(255, 255, 255, 0.05);
  padding: 4px 10px;
  border-radius: 20px;
}

.projects-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}
</style>
