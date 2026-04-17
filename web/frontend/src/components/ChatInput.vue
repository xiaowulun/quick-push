<template>
  <div class="chat-input-wrapper" :class="{ focused: isFocused }">
    <textarea
      ref="inputRef"
      v-model="inputText"
      class="chat-input"
      :placeholder="placeholder"
      rows="1"
      :disabled="disabled"
      @keydown="handleKeydown"
      @focus="isFocused = true"
      @blur="isFocused = false"
    />
    <button 
      v-if="!isStreaming"
      class="chat-send-btn"
      :disabled="!inputText.trim() || disabled"
      @click="handleSend"
    >
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M22 2L11 13"/>
        <path d="M22 2L15 22L11 13L2 9L22 2Z"/>
      </svg>
    </button>
    <button 
      v-else
      class="chat-stop-btn"
      @click="$emit('stop')"
    >
      <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
        <rect x="6" y="6" width="12" height="12" rx="2"/>
      </svg>
    </button>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  placeholder: {
    type: String,
    default: '输入您的问题...'
  },
  disabled: {
    type: Boolean,
    default: false
  },
  isStreaming: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['send', 'stop'])

const inputRef = ref(null)
const inputText = ref('')
const isFocused = ref(false)

function handleKeydown(event) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    handleSend()
  }
}

function handleSend() {
  const text = inputText.value.trim()
  if (text && !props.disabled) {
    emit('send', text)
    inputText.value = ''
  }
}

function focus() {
  inputRef.value?.focus()
}

defineExpose({ focus })
</script>

<style scoped>
.chat-input-wrapper {
  display: flex;
  gap: 12px;
  align-items: center;
  max-width: 700px;
  margin: 0 auto;
  background: var(--bg-input);
  backdrop-filter: blur(20px);
  border: 1px solid var(--border-color);
  border-radius: 28px;
  padding: 6px 6px 6px 20px;
  transition: all 0.3s ease;
}

.chat-input-wrapper.focused {
  border-color: rgba(123, 104, 238, 0.5);
  box-shadow: 0 0 30px rgba(123, 104, 238, 0.15);
}

.chat-input {
  flex: 1;
  width: 100%;
  background: transparent;
  border: none;
  padding: 12px 8px;
  color: var(--text-primary);
  font-size: 14px;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  resize: none;
  min-height: 44px;
  height: auto;
  outline: none;
  line-height: 1.5;
  overflow: auto;
  align-self: center;
}

.chat-input::placeholder {
  color: #555;
}

.chat-send-btn,
.chat-stop-btn {
  background: var(--primary-gradient);
  color: white;
  border: none;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 4px 15px rgba(123, 104, 238, 0.3);
}

.chat-send-btn:hover:not(:disabled) {
  transform: scale(1.05);
  box-shadow: 0 6px 20px rgba(123, 104, 238, 0.4);
}

.chat-send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.chat-stop-btn {
  background: rgba(255, 107, 107, 0.2);
  border: 1px solid rgba(255, 107, 107, 0.5);
  color: var(--error-color);
  box-shadow: none;
}

.chat-stop-btn:hover {
  background: rgba(255, 107, 107, 0.3);
}
</style>
