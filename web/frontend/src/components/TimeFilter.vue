<template>
  <div class="time-filter">
    <button
      v-for="option in options"
      :key="option.days"
      class="time-filter-btn"
      :class="{ active: modelValue === option.days }"
      @click="$emit('update:modelValue', option.days)"
    >
      {{ option.label }}
    </button>
  </div>
</template>

<script setup>
defineProps({
  options: {
    type: Array,
    required: true
  },
  modelValue: {
    type: Number,
    required: true
  }
})

defineEmits(['update:modelValue'])
</script>

<style scoped>
.time-filter {
  display: flex;
  gap: 12px;
  align-items: center;
}
</style>
