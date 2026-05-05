<template>
  <label class="topbar-search">
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M11 4a7 7 0 1 1 0 14 7 7 0 0 1 0-14m8 14 3 3" /></svg>
    <input
      :value="modelValue"
      type="text"
      :placeholder="placeholder"
      @input="handleInput"
      @keydown.enter.prevent="$emit('enter')"
    >
    <kbd>{{ shortcut }}</kbd>
  </label>
</template>

<script setup>
defineProps({
  modelValue: {
    type: String,
    default: '',
  },
  placeholder: {
    type: String,
    default: '搜索项目、技术、问题或者 Ask AI...',
  },
  shortcut: {
    type: String,
    default: 'K',
  },
})

const emit = defineEmits(['update:modelValue', 'enter'])

function handleInput(event) {
  emit('update:modelValue', event?.target?.value ?? '')
}
</script>

<style scoped>
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
  color: var(--text-muted);
  z-index: 3;
}

.topbar-search svg {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
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

@media (max-width: 1280px) {
  .topbar-search {
    position: static;
    transform: none;
    min-width: 0;
    width: 100%;
  }
}
</style>
