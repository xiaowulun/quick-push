<template>
  <div class="quota-box">
    <p>{{ title }}</p>
    <div class="quota-progress"><i :style="{ width: `${usagePercent}%` }"></i></div>
    <div class="quota-meta">
      <span>剩余 {{ quotaRemain }} / {{ quotaTotal }}</span>
      <strong>{{ usagePercent }}%</strong>
    </div>
    <button class="quota-upgrade" type="button">{{ buttonText }}</button>
  </div>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    default: '本月 AI 使用额度',
  },
  quotaRemain: {
    type: Number,
    default: 320,
  },
  quotaTotal: {
    type: Number,
    default: 500,
  },
  usagePercent: {
    type: Number,
    default: 68,
  },
  buttonText: {
    type: String,
    default: '升级套餐',
  },
})
</script>

<style scoped>
.quota-box {
  box-sizing: border-box;
  width: 100%;
  border: 1px solid #d7e3f6;
  border-radius: 16px;
  background: #edf2ff;
  padding: 14px;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif;
}

.quota-box p {
  margin: 0;
  color: #4c5d7a;
  font-size: 13px;
  font-weight: 700;
  line-height: 1.2;
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
  align-items: center;
  justify-content: space-between;
  color: #4c5d7a;
  font-size: 13px;
  line-height: 1.2;
}

.quota-meta span,
.quota-meta strong {
  display: block;
  margin: 0;
  line-height: 1.2;
}

.quota-meta strong {
  font-size: 13px;
  font-weight: 700;
}

.quota-upgrade {
  margin-top: 12px;
  width: 100%;
  min-height: 36px;
  padding: 0 12px;
  border-radius: 12px;
  border: none;
  background: #5b6df5;
  color: #ffffff;
  line-height: 1;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}
</style>
