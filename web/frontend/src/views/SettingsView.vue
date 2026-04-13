<template>
  <div class="settings-view">
    <div class="settings-section">
      <h2 class="section-title">GitHub 配置</h2>
      
      <div v-if="loading" class="loading">
        <div class="spinner"></div>
        <div>验证中...</div>
      </div>
      
      <div v-else-if="githubStatus" class="github-status" :class="{ valid: githubStatus.valid, invalid: !githubStatus.valid }">
        <div class="status-header">
          <div class="status-icon">
            <span v-if="githubStatus.valid">✅</span>
            <span v-else>❌</span>
          </div>
          <div class="status-info">
            <h3>{{ githubStatus.valid ? '已连接' : '未连接' }}</h3>
            <p>{{ githubStatus.message }}</p>
          </div>
        </div>
        
        <div v-if="githubStatus.valid" class="user-info">
          <img v-if="githubStatus.avatar_url" :src="githubStatus.avatar_url" :alt="githubStatus.username" class="avatar" />
          <div class="user-details">
            <p><strong>用户名:</strong> {{ githubStatus.username }}</p>
            <p v-if="githubStatus.name"><strong>名称:</strong> {{ githubStatus.name }}</p>
          </div>
        </div>
        
        <div v-if="rateLimit" class="rate-limit">
          <h4>API 速率限制</h4>
          <div class="rate-bar">
            <div class="rate-used" :style="{ width: `${ratePercent}%` }"></div>
          </div>
          <p>{{ rateLimit.remaining }} / {{ rateLimit.limit }} 剩余请求</p>
        </div>
        
        <button class="retry-btn" @click="validateGitHub">重新验证</button>
      </div>
    </div>
    
    <div class="settings-section">
      <h2 class="section-title">配置说明</h2>
      <div class="config-help">
        <p>在项目根目录的 <code>.env</code> 文件中配置以下参数：</p>
        <pre>
GITHUB_TOKEN=your_github_token_here
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_BASE_URL=https://api.siliconflow.cn/v1
        </pre>
        <p>获取 GitHub Token：</p>
        <ol>
          <li>访问 <a href="https://github.com/settings/tokens" target="_blank">GitHub Settings → Tokens</a></li>
          <li>点击 "Generate new token (classic)"</li>
          <li>选择需要的权限（至少需要 public_repo）</li>
          <li>复制生成的 Token 到 .env 文件</li>
        </ol>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const loading = ref(false)
const githubStatus = ref(null)
const rateLimit = ref(null)

const ratePercent = computed(() => {
  if (!rateLimit.value) return 0
  return ((rateLimit.value.limit - rateLimit.value.remaining) / rateLimit.value.limit) * 100
})

async function validateGitHub() {
  loading.value = true
  try {
    const [validateRes, rateRes] = await Promise.all([
      fetch('/api/github/validate'),
      fetch('/api/github/rate-limit')
    ])
    
    githubStatus.value = await validateRes.json()
    rateLimit.value = await rateRes.json()
  } catch (err) {
    console.error('Validation failed:', err)
    githubStatus.value = {
      valid: false,
      message: '验证请求失败: ' + err.message
    }
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  validateGitHub()
})
</script>

<style scoped>
.settings-view {
  max-width: 600px;
  margin: 0 auto;
}

.settings-section {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 24px;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 20px;
}

.github-status {
  padding: 16px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
}

.github-status.valid {
  background: rgba(78, 205, 196, 0.1);
  border-color: rgba(78, 205, 196, 0.3);
}

.github-status.invalid {
  background: rgba(255, 107, 107, 0.1);
  border-color: rgba(255, 107, 107, 0.3);
}

.status-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.status-icon {
  font-size: 32px;
}

.status-info h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.status-info p {
  font-size: 13px;
  color: var(--text-secondary);
}

.user-info {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 12px;
  margin-bottom: 16px;
}

.avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
}

.user-details p {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.rate-limit {
  margin-bottom: 16px;
}

.rate-limit h4 {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.rate-bar {
  height: 8px;
  background: var(--border-color);
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 8px;
}

.rate-used {
  height: 100%;
  background: var(--primary-gradient);
  border-radius: 4px;
  transition: width 0.3s ease;
}

.rate-limit p {
  font-size: 12px;
  color: var(--text-muted);
}

.config-help {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.8;
}

.config-help code {
  background: rgba(123, 104, 238, 0.1);
  padding: 2px 8px;
  border-radius: 4px;
  font-family: monospace;
  color: var(--primary-color);
}

.config-help pre {
  background: rgba(0, 0, 0, 0.3);
  padding: 16px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 12px 0;
  font-size: 13px;
}

.config-help ol {
  padding-left: 20px;
  margin: 12px 0;
}

.config-help li {
  margin-bottom: 8px;
}

.config-help a {
  color: var(--primary-color);
  text-decoration: none;
}

.config-help a:hover {
  text-decoration: underline;
}
</style>
