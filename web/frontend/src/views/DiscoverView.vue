<template>
  <div class="discover-page" :class="{ dark: isDark }">
        <header class="topbar">
      <div class="topbar-left">
        <button class="brand" type="button" @click="scrollToTop">
          <span class="brand-icon">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M4.8 11.2 19.7 4.7 15 19.5l-3.5-4-3.3 2 .8-4.9z" />
            </svg>
          </span>
          <span class="brand-text">
            <strong>OpenScout</strong>
            <small>AI 驱动的开源洞察与决策助手</small>
          </span>
        </button>
        <nav class="top-nav" aria-label="一级导航">
          <button class="top-nav-btn active" type="button">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="12" cy="12" r="8" />
              <path d="M12 12l4-4" />
              <path d="M11 11l5-3-3 5z" fill="currentColor" stroke="none" />
            </svg>
            <span>发现</span>
          </button>
          <button class="top-nav-btn" type="button" @click="router.push('/dashboard')">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M4 5h6v6H4zM14 5h6v10h-6zM4 15h6v4H4zM14 17h6v2h-6z" />
            </svg>
            <span>仪表盘</span>
          </button>
        </nav>
        <TopbarSearch v-model="topbarSearch" @enter="reloadFeed" />
      </div>
      <div class="topbar-right">
        <button class="theme-switch" type="button" @click="toggleTheme" :title="isDark ? '切换浅色模式' : '切换深色模式'">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="12" cy="12" r="4" />
            <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
          </svg>
          <span class="theme-track" :class="{ dark: isDark }">
            <i></i>
          </span>
        </button>
        <button class="icon-btn notify-btn" type="button" title="通知">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M15.2 18H4.8l1.4-1.4a2 2 0 0 0 .6-1.4V11a5.2 5.2 0 1 1 10.4 0v4.2a2 2 0 0 0 .6 1.4ZM10 18a2 2 0 1 0 4 0" />
          </svg>
          <span class="badge">3</span>
        </button>
        <div class="user-menu-wrap">
          <button class="user-chip" type="button">
            <img src="https://avatars.githubusercontent.com/u/1?v=4" alt="&#29992;&#25143;&#22836;&#20687;">
            <span class="user-meta">
              <strong>&#24352;&#23567;&#26126;</strong>
              <small>&#20010;&#20154;&#31354;&#38388;</small>
            </span>
            <em>Pro</em>
          </button>
          <button class="user-menu-toggle" type="button" @click.stop="toggleUserMenu" aria-label="&#25171;&#24320;&#29992;&#25143;&#33756;&#21333;">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>
          </button>
          <div v-if="userMenuOpen" class="user-menu">
            <button type="button" @click="handleUserMenuAction('profile')">&#29992;&#25143;&#20449;&#24687;</button>
            <button type="button" @click="handleUserMenuAction('settings')">&#35774;&#32622;</button>
            <button type="button" @click="handleUserMenuAction('favorites')">&#25105;&#30340;&#25910;&#34255;</button>
          </div>
        </div>
      </div>
    </header>

    <div class="body-shell">
            <aside class="left-rail">
        <div class="left-main">
          <div class="left-group">
            <p class="group-title">发现</p>
            <button class="rail-btn active" type="button">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4 19 12 12 20 5 12z" /></svg>
              <span>探索推荐</span>
            </button>
            <button class="rail-btn" type="button">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2.8 14.7 8l5.8.8-4.2 4.1 1 5.8L12 16.1 6.7 18.7l1-5.8-4.2-4.1L9.3 8z" /></svg>
              <span>热门项目</span>
            </button>
            <button class="rail-btn" type="button">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16" /><circle cx="7" cy="7" r="1.4" /><circle cx="13" cy="12" r="1.4" /><circle cx="10" cy="17" r="1.4" /></svg>
              <span>榜单洞察</span>
            </button>
            <button class="rail-btn" type="button">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h7v10H4zM13 7h7v4h-7zM13 13h7v4h-7z" /></svg>
              <span>项目对比</span>
            </button>
          </div>

          <div class="left-group">
            <p class="group-title">理解与分析</p>
            <button class="rail-btn" type="button">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 0-3 3z" /><path d="M8 20V7a3 3 0 0 1 3-3" /></svg>
              <span>项目深度解读</span>
            </button>
            <button class="rail-btn" type="button">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16" /><circle cx="8" cy="6" r="1.5" /><circle cx="15" cy="12" r="1.5" /><circle cx="11" cy="18" r="1.5" /></svg>
              <span>技术栈分析</span>
            </button>
            <button class="rail-btn" type="button">
              <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="8" cy="9" r="3" /><circle cx="16" cy="9" r="3" /><path d="M3 19a5 5 0 0 1 10 0M11 19a5 5 0 0 1 10 0" /></svg>
              <span>社区与生态</span>
            </button>
            <button class="rail-btn" type="button">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 5 7v5c0 5 3.4 7.9 7 9 3.6-1.1 7-4 7-9V7z" /><path d="m9 12 2 2 4-4" /></svg>
              <span>安全与合规</span>
            </button>
          </div>
        </div>

        <div class="left-bottom">
          <QuotaCard :quota-remain="quotaRemain" :quota-total="quotaTotal" :usage-percent="usagePercent" />
        </div>
      </aside>

      <main class="main-stage">
        <section class="hero">
          <div class="hero-bg"></div>
          <div class="hero-content">
            <h2>&#21457;&#29616;&#20248;&#31168;&#24320;&#28304;&#39033;&#30446;&#65292;&#20570;&#20986;&#26356;&#22909;&#30340;&#25216;&#26415;&#20915;&#31574;</h2>
            <p>&#65;&#73;&#32;&#24110;&#20320;&#29702;&#35299;&#39033;&#30446;&#12289;&#23545;&#27604;&#26041;&#26696;&#12289;&#35780;&#20272;&#39118;&#38505;&#65292;&#39537;&#21160;&#22242;&#38431;&#36208;&#21521;&#25104;&#21151;</p>

            <label class="hero-search">
              <input
                v-model="searchKeyword"
                type="text"
                placeholder="&#38382;&#25105;&#20219;&#20309;&#20851;&#20110;&#24320;&#28304;&#30340;&#38382;&#39064;&#65292;&#20363;&#22914;&#65306;&#25512;&#33616;&#19968;&#20010;&#39640;&#24615;&#33021;&#30340;&#32;&#80;&#121;&#116;&#104;&#111;&#110;&#32;&#21521;&#37327;&#25968;&#25454;&#24211;"
                @keydown.enter.prevent="reloadFeed"
              >
              <button type="button" @click="reloadFeed" aria-label="&#25628;&#32034;"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6" /></svg></button>
            </label>

            <div class="hero-chips">
              <button v-for="item in quickSearches" :key="item" type="button" @click="applyQuickSearch(item)">
                {{ item }}
              </button>
            </div>
          </div>
          <div class="hero-illustration" aria-hidden="true">
            <svg class="hero-illus-svg" viewBox="0 0 360 220" role="img" aria-label="Open source insight illustration">
              <defs>
                <linearGradient id="deskTop" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stop-color="#f7f9ff" />
                  <stop offset="100%" stop-color="#e8efff" />
                </linearGradient>
                <linearGradient id="laptopA" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stop-color="#fdfefe" />
                  <stop offset="100%" stop-color="#dae8ff" />
                </linearGradient>
                <linearGradient id="laptopB" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stop-color="#dce8ff" />
                  <stop offset="100%" stop-color="#b8cdfb" />
                </linearGradient>
                <linearGradient id="screenA" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stop-color="#f7faff" />
                  <stop offset="100%" stop-color="#d7e5ff" />
                </linearGradient>
                <filter id="heroShadow" x="-30%" y="-30%" width="180%" height="200%">
                  <feDropShadow dx="0" dy="15" stdDeviation="11" flood-color="#6d8fe0" flood-opacity="0.25" />
                </filter>
              </defs>

              <ellipse cx="182" cy="186" rx="126" ry="20" fill="#c6d8ff" opacity="0.52" />
              <ellipse cx="182" cy="178" rx="98" ry="14" fill="#d7e4ff" opacity="0.46" />
              <path d="M66 54c20-18 48-24 76-16" fill="none" stroke="#d8e3ff" stroke-width="3" stroke-linecap="round" />
              <path d="M258 68c14 10 24 24 28 42" fill="none" stroke="#d8e3ff" stroke-width="3" stroke-linecap="round" />

              <g transform="translate(64,28)" filter="url(#heroShadow)">
                <polygon points="40,106 136,60 278,118 182,162" fill="url(#laptopA)" stroke="#95b1f6" />
                <polygon points="182,162 278,118 278,140 182,184" fill="url(#laptopB)" stroke="#95b1f6" />
                <polygon points="40,106 182,162 182,184 40,128" fill="#ebf2ff" stroke="#95b1f6" />

                <polygon points="68,98 140,66 238,106 166,138" fill="#8ea9ff" opacity="0.22" />

                <polygon points="58,86 138,50 218,84 138,120" fill="#ffffff" stroke="#9ab4f7" />
                <polygon points="138,120 218,84 218,98 138,134" fill="#dce8ff" stroke="#9ab4f7" />
                <polygon points="58,86 138,120 138,134 58,100" fill="#edf3ff" stroke="#9ab4f7" />

                <rect x="138" y="20" width="104" height="64" rx="14" fill="url(#screenA)" stroke="#94b0f5" />
                <rect x="152" y="34" width="32" height="22" rx="6" fill="#88a4f0" />
                <rect x="190" y="34" width="38" height="10" rx="5" fill="#9cb5f7" />
                <rect x="190" y="48" width="30" height="8" rx="4" fill="#aec2fb" />
                <path d="M152 66h70" stroke="#7e99ea" stroke-width="5.5" stroke-linecap="round" />

                <rect x="96" y="102" width="40" height="24" rx="7" fill="#7e99ef" />
                <rect x="144" y="120" width="34" height="20" rx="7" fill="#90afff" />
                <circle cx="150" cy="84" r="11" fill="#ffbb4a" />
                <path d="M146 84h8" stroke="#fff" stroke-width="2.2" stroke-linecap="round" />
                <path d="M150 80v8" stroke="#fff" stroke-width="2.2" stroke-linecap="round" />
                <rect x="228" y="112" width="30" height="20" rx="6" fill="#7f9af0" opacity="0.92" />
              </g>

              <g transform="translate(42,44)">
                <rect x="0" y="0" width="76" height="52" rx="12" fill="#f3f8ff" stroke="#a9c0fb" />
                <rect x="12" y="14" width="38" height="6" rx="3" fill="#7e9bef" />
                <rect x="12" y="26" width="48" height="6" rx="3" fill="#8ca8f2" />
                <rect x="12" y="38" width="34" height="6" rx="3" fill="#95aff6" />
              </g>

              <g transform="translate(240,56)">
                <rect x="0" y="0" width="64" height="46" rx="12" fill="#f2f7ff" stroke="#aac0fb" />
                <rect x="10" y="12" width="34" height="6" rx="3" fill="#8aa5ef" />
                <rect x="10" y="24" width="40" height="6" rx="3" fill="#9ab2f5" />
              </g>

              <circle cx="50" cy="130" r="6" fill="#89a3ff" />
              <circle cx="312" cy="52" r="8" fill="#ff8f9a" />
              <circle cx="258" cy="36" r="8" fill="#88a2ff" />
              <circle cx="324" cy="156" r="7" fill="#89a3ff" />

              <g transform="translate(286,112)">
                <circle cx="0" cy="0" r="14" fill="#eff5ff" stroke="#a7bdfa" />
                <path d="M-4 -1a5 5 0 1 0 7 7" stroke="#6b88dd" stroke-width="2.2" fill="none" stroke-linecap="round" />
                <path d="M3 6 8 11" stroke="#6b88dd" stroke-width="2.2" stroke-linecap="round" />
              </g>
            </svg>
          </div>
        </section>

        <section class="section-header">
          <div>
            <h3>&#20026;&#20320;&#25512;&#33616;</h3>
          </div>
          <button class="link-btn" type="button">&#26597;&#30475;&#20840;&#37096;&#25512;&#33616;<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 12h10M13 6l6 6-6 6" /></svg></button>
        </section>

        <section v-if="loadingFeed" class="state-row">正在加载推荐项目...</section>
        <section v-else-if="feedError" class="state-row error">
          <span>{{ feedError }}</span>
          <button type="button" @click="reloadFeed">重试</button>
        </section>
        <section v-else-if="featuredProjects.length === 0" class="state-row">当前没有可展示项目，请先运行数据管道后再刷新。</section>
        <section v-else class="recommend-grid">
          <article v-for="project in featuredProjects" :key="project.repo_name" class="recommend-card">
            <header>
              <div class="repo-head">
                <img :src="ownerAvatar(project.repo_name)" :alt="project.repo_name" loading="lazy" @error="onAvatarError">
                <div class="repo-head-text">
                  <button class="repo-name" type="button" @click="openProject(project.repo_name)">
                    {{ project.repo_name }}
                  </button>
                </div>
              </div>

              <div class="repo-actions">
                <button class="icon-action" :class="{ active: likedRepos.has(project.repo_name) }" type="button" title="&#21916;&#27426;" @click="toggleLike(project.repo_name)"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20.7 3.9 13a4.8 4.8 0 0 1 6.8-6.8L12 7.5l1.3-1.3a4.8 4.8 0 1 1 6.8 6.8z" /></svg></button>
                <button class="icon-action" :class="{ active: bookmarkedRepos.has(project.repo_name) }" type="button" title="&#25910;&#34255;" @click="toggleBookmark(project.repo_name)">
                  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 4h12a1 1 0 0 1 1 1v16l-7-4-7 4V5a1 1 0 0 1 1-1z" /></svg>
                </button>
              </div>
            </header>

            <p class="repo-summary">{{ conciseSummary(project.summary) }}</p>
            <div class="repo-tags">
              <span>{{ labelCategory(project.category) }}</span>
              <span>{{ project.language || 'Unknown' }}</span>
            </div>

            <div class="repo-footer">
              <div class="repo-stats">
                <span>
                  <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.212.611a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.195a.75.75 0 0 1-1.088.79L8 12.347l-3.768 1.98a.75.75 0 0 1-1.088-.79l.72-4.195-3.047-2.97a.75.75 0 0 1 .416-1.279l4.212-.61L7.327.667A.75.75 0 0 1 8 .25Z" /></svg>
                  {{ formatCompact(project.stars) }}
                </span>
              </div>
              <button class="compare-btn" :class="{ active: isSelected(project.repo_name) }" type="button" @click="toggleSelect(project.repo_name)">
                {{ isSelected(project.repo_name) ? '已加入对比' : '加入对比' }}
              </button>
            </div>
          </article>
        </section>

        <section class="insight-grid">
          <article class="insight-card trend-card">
            <div class="insight-head">
              <h4>趋势洞察</h4>
              <span>近 30 天</span>
            </div>
            <p class="trend-percent">↑ {{ trendGrowth }}%</p>
            <p class="trend-caption">整体活跃度增长</p>
            <div class="trend-body">
              <div class="chart-wrap chart-trend"><canvas ref="trendCanvasRef"></canvas></div>
              <div class="category-trend">
                <p>增长最快领域</p>
                <ul class="growth-list">
                  <li v-for="item in fastestCategories" :key="item.key">
                    <span>{{ item.label }}</span>
                    <strong>+{{ item.growth }}%</strong>
                  </li>
                </ul>
              </div>
            </div>
          </article>

          <article class="insight-card radar-card">
            <div class="insight-head">
              <h4>项目健康度雷达图</h4>
            </div>
            <div class="chart-wrap"><canvas ref="radarCanvasRef"></canvas></div>
          </article>

          <article class="insight-card risk-card">
            <div class="insight-head">
              <h4>风险与注意事项</h4>
            </div>
            <ul class="risk-list">
              <li v-for="risk in riskItems" :key="risk.id" :class="`risk-${risk.level}`">
                <div>
                  <strong>{{ riskLabel(risk.level) }}</strong>
                  <p>{{ risk.text }}</p>
                </div>
                <span>{{ risk.repo_name }}</span>
              </li>
            </ul>
          </article>
        </section>

        <section class="compare-section">
          <header>
            <h4>项目对比</h4>
            <button type="button" :disabled="selectedRepoNames.length < 2 || compareLoading" @click="refreshCompare">刷新对比</button>
          </header>
          <div v-if="selectedRepoNames.length" class="picked-repos">
            <span v-for="name in selectedRepoNames" :key="name">{{ name }}</span>
          </div>
          <div v-if="compareLoading" class="state-row">&#27491;&#22312;&#35745;&#31639;&#23545;&#27604;&#32467;&#26524;...</div>
          <div v-else-if="compareError" class="state-row error">{{ compareError }}</div>
          <div v-else-if="compareRows.length < 2" class="state-row">至少选择 2 个项目即可生成对比。</div>
          <table v-else class="compare-table">
            <thead>
              <tr>
                <th>项目</th>
                <th>综合评分</th>
                <th>活跃度</th>
                <th>社区</th>
                <th>文档</th>
                <th>安全</th>
                <th>易用</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in compareRows" :key="item.repo_name">
                <td>{{ item.repo_name }}</td>
                <td>{{ Number(item.overall_score || 0).toFixed(2) }}</td>
                <td>{{ Number(item.dimensions?.activity || 0).toFixed(1) }}</td>
                <td>{{ Number(item.dimensions?.community || 0).toFixed(1) }}</td>
                <td>{{ Number(item.dimensions?.docs || 0).toFixed(1) }}</td>
                <td>{{ Number(item.dimensions?.security || 0).toFixed(1) }}</td>
                <td>{{ Number(item.dimensions?.usability || 0).toFixed(1) }}</td>
              </tr>
            </tbody>
          </table>
        </section>
      </main>

      <aside class="assistant-panel">
        <header>
          <h3>OpenScout助手</h3>
          <button type="button" @click="resetAssistant">新对话</button>
        </header>

        <div ref="messageListRef" class="message-list">
          <div v-for="(msg, index) in assistantMessages" :key="index" class="msg-row" :class="msg.role">
            <div class="avatar">{{ msg.role === 'assistant' ? 'AI' : '你' }}</div>
            <p>{{ msg.content }}</p>
          </div>
          <div v-if="assistantStatus" class="assistant-status">{{ assistantStatus }}</div>
        </div>

        <div class="quick-questions">
          <p>你可以问我：</p>
          <button v-for="question in quickQuestions" :key="question" type="button" :disabled="assistantStreaming" @click="applyQuestion(question)">
            {{ question }}
          </button>
        </div>

        <div class="assistant-composer">
          <textarea
            v-model="assistantQuery"
            class="assistant-input"
            placeholder="&#38382;&#25105;&#20219;&#20309;&#20851;&#20110;&#24320;&#28304;&#30340;&#38382;&#39064;&#65292;&#20363;&#22914;&#65306;&#25512;&#33616;&#19968;&#20010;&#39640;&#24615;&#33021;&#30340;&#32;&#80;&#121;&#116;&#104;&#111;&#110;&#32;&#21521;&#37327;&#25968;&#25454;&#24211;"
            rows="3"
            :disabled="assistantStreaming"
            @keydown.enter.exact.prevent="handleAssistantAction"
            @keydown.ctrl.enter.exact.prevent="handleAssistantAction"
          ></textarea>
          <div class="assistant-actions">
            <button type="button" class="tool-btn" :disabled="assistantStreaming || !assistantQuery.trim()" @click="clearAssistantDraft">清空</button>
            <button type="button" class="tool-btn" :disabled="assistantStreaming || !lastUserPrompt" @click="reuseLastPrompt">复用上次</button>
            <span class="char-count">{{ assistantQuery.length }} 字</span>
            <button
              class="send-btn"
              type="button"
              :class="{ danger: assistantStreaming }"
              :disabled="!assistantStreaming && !assistantQuery.trim()"
              @click="handleAssistantAction"
            >
              {{ assistantStreaming ? '停止' : '发送' }}
            </button>
          </div>
        </div>

        <p v-if="assistantError" class="assistant-error">{{ assistantError }}</p>

        <div class="assistant-float-tools" aria-hidden="true">
          <button type="button">✦</button>
          <button type="button">⌘</button>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Chart, registerables } from 'chart.js'
import QuotaCard from '@/components/QuotaCard.vue'
import TopbarSearch from '@/components/TopbarSearch.vue'
import { useApi } from '@/composables/useApi'

Chart.register(...registerables)

const router = useRouter()
const { fetchDiscoverFeed, compareProjectScore, streamChat } = useApi()

const CATEGORY_LABELS = {
  ai_ecosystem: 'AI 生态',
  infra_and_tools: '开发工具',
  product_and_ui: '产品与 UI',
  knowledge_base: '知识库'
}

const quickSearches = ['推荐向量数据库', '对比 Next.js 和 Nuxt', '找工作流引擎', 'CI/CD 最佳实践']
const quickQuestions = ['适合生产环境吗？', '主要风险如何规避？', '如果两周上线 MVP 怎么做？']

const usagePercent = 68
const quotaRemain = 320
const quotaTotal = 500

const searchKeyword = ref('')
const loadingFeed = ref(false)
const feedError = ref('')
const feedItems = ref([])
const dataDate = ref('')
const isFreshToday = ref(false)

const selectedRepoNames = ref([])
const compareRows = ref([])
const compareLoading = ref(false)
const compareError = ref('')

const likedRepos = ref(new Set())
const bookmarkedRepos = ref(new Set())
const topbarSearch = ref('')
const userMenuOpen = ref(false)

const assistantQuery = ref('')
const assistantMessages = ref([
  { role: 'assistant', content: '你好，我是 OpenScout AI 助手。你有什么问题都可以问我。' }
])
const assistantStatus = ref('')
const assistantStreaming = ref(false)
const assistantError = ref('')
const assistantAbortController = ref(null)
const assistantSessionId = ref(null)
const messageListRef = ref(null)
const lastUserPrompt = computed(() => {
  for (let i = assistantMessages.value.length - 1; i >= 0; i -= 1) {
    const item = assistantMessages.value[i]
    if (item?.role === 'user' && String(item.content || '').trim()) {
      return String(item.content)
    }
  }
  return ''
})

const theme = ref('light')
const THEME_KEY = 'openscout-discover-theme-v4'
const isDark = computed(() => theme.value === 'dark')

const trendCanvasRef = ref(null)
const radarCanvasRef = ref(null)
let trendChart = null
let radarChart = null

const featuredProjects = computed(() => feedItems.value.slice(0, 8))
const freshnessText = computed(() => {
  const text = String(dataDate.value || '').trim()
  if (!text) return '暂无'
  return isFreshToday.value ? `数据日期 ${text}（今日）` : `数据日期 ${text}（非今日）`
})

const trendGrowth = computed(() => {
  if (!featuredProjects.value.length) return '0.0'
  const avg = featuredProjects.value.reduce((sum, item) => sum + Number(item.stars_today || 0), 0) / featuredProjects.value.length
  return (Math.max(5, avg / 2)).toFixed(1)
})

const fastestCategories = computed(() => {
  const grouped = {}
  for (const item of featuredProjects.value) {
    const key = String(item.category || 'infra_and_tools')
    grouped[key] = (grouped[key] || 0) + Number(item.stars_today || 0)
  }
  return Object.entries(grouped)
    .map(([key, stars]) => ({
      key,
      label: labelCategory(key),
      growth: Math.round(Math.max(4, stars / 8))
    }))
    .sort((a, b) => b.growth - a.growth)
    .slice(0, 3)
})

const radarValues = computed(() => {
  const source = compareRows.value.length >= 2 ? compareRows.value : featuredProjects.value
  const base = { activity: 0, community: 0, docs: 0, security: 0, usability: 0 }
  if (!source.length) return base
  for (const item of source) {
    base.activity += Number(item.dimensions?.activity || 0)
    base.community += Number(item.dimensions?.community || 0)
    base.docs += Number(item.dimensions?.docs || 0)
    base.security += Number(item.dimensions?.security || 0)
    base.usability += Number(item.dimensions?.usability || 0)
  }
  const count = source.length
  return {
    activity: Number((base.activity / count).toFixed(2)),
    community: Number((base.community / count).toFixed(2)),
    docs: Number((base.docs / count).toFixed(2)),
    security: Number((base.security / count).toFixed(2)),
    usability: Number((base.usability / count).toFixed(2))
  }
})

const riskItems = computed(() => {
  const list = []
  for (const row of compareRows.value) {
    for (const risk of row.risk_flags || []) {
      list.push({
        id: `${row.repo_name}-${risk.type}-${risk.text}`,
        repo_name: row.repo_name,
        level: normalizeRiskLevel(risk.level),
        text: risk.text || '未知风险'
      })
    }
  }
  if (!list.length) {
    return [
      { id: 'risk-1', repo_name: '系统', level: 'high', text: '安全风险项目：建议上线前补充依赖和许可证审查。' },
      { id: 'risk-2', repo_name: '系统', level: 'medium', text: '许可证风险项目：注意二次分发合规要求。' },
      { id: 'risk-3', repo_name: '系统', level: 'low', text: '维护者响应波动：建议建立替代方案。' }
    ]
  }
  return list.slice(0, 5)
})

function humanizeError(err) {
  const raw = String(err?.message || '').trim()
  if (!raw) return '暂时无法加载推荐数据，请稍后重试。'
  if (raw.includes('HTTP Request: POST') || raw.includes('api.siliconflow.cn')) {
    return '推荐流请求波动，系统已回退到稳定模式。请点击重试。'
  }
  return raw.length > 200 ? `${raw.slice(0, 200)}...` : raw
}

function normalizeRiskLevel(level) {
  const text = String(level || '').toLowerCase()
  if (text === 'high' || text === 'medium' || text === 'low') return text
  return 'medium'
}

function riskLabel(level) {
  if (level === 'high') return '安全风险项目'
  if (level === 'low') return '维护者响应风险'
  return '许可证风险项目'
}

function labelCategory(key) {
  return CATEGORY_LABELS[String(key || '')] || String(key || '未分类')
}

function conciseSummary(text) {
  const raw = String(text || '').replace(/\s+/g, ' ').trim()
  if (!raw) return '暂无摘要信息，点击项目查看详情。'
  return raw.length > 120 ? `${raw.slice(0, 120)}...` : raw
}

function formatCompact(value) {
  const num = Number(value || 0)
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}m`
  if (num >= 1000) return `${(num / 1000).toFixed(1)}k`
  return String(num)
}

function ownerAvatar(repoName) {
  const owner = String(repoName || '').split('/')[0]
  return owner ? `https://github.com/${encodeURIComponent(owner)}.png?size=96` : 'https://github.githubassets.com/favicons/favicon.png'
}

function onAvatarError(event) {
  const target = event?.target
  if (!target) return
  target.src = 'https://github.githubassets.com/favicons/favicon.png'
}

function openProject(repoName) {
  if (!repoName) return
  router.push({ name: 'ProjectDetail', params: { repoFullName: repoName } })
}

function toggleLike(repoName) {
  const next = new Set(likedRepos.value)
  if (next.has(repoName)) next.delete(repoName)
  else next.add(repoName)
  likedRepos.value = next
}

function toggleBookmark(repoName) {
  const next = new Set(bookmarkedRepos.value)
  if (next.has(repoName)) next.delete(repoName)
  else next.add(repoName)
  bookmarkedRepos.value = next
}

function isSelected(repoName) {
  return selectedRepoNames.value.includes(repoName)
}

async function toggleSelect(repoName) {
  const next = [...selectedRepoNames.value]
  const idx = next.indexOf(repoName)
  if (idx >= 0) next.splice(idx, 1)
  else if (next.length < 5) next.push(repoName)
  selectedRepoNames.value = next
  await refreshCompare()
}

function applyQuickSearch(value) {
  searchKeyword.value = value
  reloadFeed()
}

function applyQuestion(question) {
  assistantQuery.value = question
  sendAssistant()
}

function clearAssistantDraft() {
  assistantQuery.value = ''
}

function reuseLastPrompt() {
  if (!lastUserPrompt.value) return
  assistantQuery.value = lastUserPrompt.value
}

function handleAssistantAction() {
  if (assistantStreaming.value) {
    stopAssistant()
    return
  }
  sendAssistant()
}

function toggleUserMenu() {
  userMenuOpen.value = !userMenuOpen.value
}

function handleUserMenuAction(_action) {
  userMenuOpen.value = false
}

function handleGlobalClick(event) {
  const target = event?.target
  if (!(target instanceof HTMLElement)) return
  if (!target.closest('.user-menu-wrap')) {
    userMenuOpen.value = false
  }
}

function resetAssistant() {
  assistantMessages.value = [{ role: 'assistant', content: '新的对话已开始。你有什么问题都可以问我。' }]
  assistantSessionId.value = null
  assistantStatus.value = ''
  assistantError.value = ''
}

function toggleTheme() {
  theme.value = isDark.value ? 'light' : 'dark'
}

function scrollToTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function reloadFeed() {
  loadingFeed.value = true
  feedError.value = ''
  try {
    const data = await fetchDiscoverFeed({ days: 7, limit: 20, interests: searchKeyword.value })
    feedItems.value = Array.isArray(data?.items) ? data.items : []
    dataDate.value = String(data?.data_date || '')
    isFreshToday.value = Boolean(data?.is_fresh_today)
    selectedRepoNames.value = feedItems.value.slice(0, 3).map((item) => item.repo_name).filter(Boolean)
    await refreshCompare()
  } catch (err) {
    feedError.value = humanizeError(err)
    feedItems.value = []
    selectedRepoNames.value = []
    compareRows.value = []
  } finally {
    loadingFeed.value = false
  }
}

async function refreshCompare() {
  compareLoading.value = true
  compareError.value = ''
  try {
    if (selectedRepoNames.value.length < 2) {
      compareRows.value = []
      return
    }
    const data = await compareProjectScore(selectedRepoNames.value)
    compareRows.value = Array.isArray(data?.items) ? data.items : []
  } catch (err) {
    compareError.value = humanizeError(err)
    compareRows.value = []
  } finally {
    compareLoading.value = false
  }
}

function scrollAssistantToBottom() {
  requestAnimationFrame(async () => {
    await nextTick()
    const el = messageListRef.value
    if (!el) return
    el.scrollTop = el.scrollHeight
  })
}

async function sendAssistant() {
  const text = String(assistantQuery.value || '').trim()
  if (!text || assistantStreaming.value) return

  assistantQuery.value = ''
  assistantError.value = ''
  assistantStatus.value = '正在检索相关项目...'
  assistantStreaming.value = true
  assistantMessages.value.push({ role: 'user', content: text })
  scrollAssistantToBottom()

  const currentMessage = reactive({ role: 'assistant', content: '' })
  let assistantAdded = false
  let isFirstAssistantChunk = true
  assistantAbortController.value = new AbortController()

  const contextPrefix = selectedRepoNames.value.length ? `[候选项目: ${selectedRepoNames.value.join(', ')}] ` : ''
  const query = `${contextPrefix}${text}`

  try {
    for await (const data of streamChat(query, {
      topK: 6,
      sessionId: assistantSessionId.value,
      signal: assistantAbortController.value.signal
    })) {
      if (data.type === 'session') {
        assistantSessionId.value = data.session_id
      } else if (data.type === 'status') {
        assistantStatus.value = data.content || ''
      } else if (data.type === 'content_start') {
        assistantStatus.value = ''
        if (!assistantAdded) {
          assistantMessages.value.push(currentMessage)
          assistantAdded = true
        }
      } else if (data.type === 'content') {
        if (!assistantAdded) {
          assistantStatus.value = ''
          assistantMessages.value.push(currentMessage)
          assistantAdded = true
        }
        let content = String(data.content || '')
        if (isFirstAssistantChunk) {
          content = content.replace(/^\s+/, '')
          if (!content) continue
          isFirstAssistantChunk = false
        }
        currentMessage.content += content
      } else if (data.type === 'error') {
        if (!assistantAdded) {
          assistantMessages.value.push(currentMessage)
          assistantAdded = true
        }
        currentMessage.content = data.content || '暂时无法回答这个问题，请稍后重试。'
      }
      scrollAssistantToBottom()
    }
  } catch (err) {
    if (err?.name !== 'AbortError') {
      assistantError.value = humanizeError(err)
      assistantMessages.value.push({ role: 'assistant', content: assistantError.value })
    }
  } finally {
    assistantStreaming.value = false
    assistantStatus.value = ''
    assistantAbortController.value = null
    scrollAssistantToBottom()
  }
}

function stopAssistant() {
  if (assistantAbortController.value) assistantAbortController.value.abort()
  assistantStreaming.value = false
  assistantStatus.value = ''
}

function destroyCharts() {
  if (trendChart) {
    trendChart.destroy()
    trendChart = null
  }
  if (radarChart) {
    radarChart.destroy()
    radarChart = null
  }
}

function renderTrendChart() {
  if (!trendCanvasRef.value) return
  if (trendChart) trendChart.destroy()

  const days = 8
  const labels = Array.from({ length: days }, (_, idx) => {
    const date = new Date()
    date.setDate(date.getDate() - (days - 1 - idx))
    const mm = String(date.getMonth() + 1).padStart(2, '0')
    const dd = String(date.getDate()).padStart(2, '0')
    return `${mm}-${dd}`
  })
  const avgStarsToday = featuredProjects.value.length
    ? featuredProjects.value.reduce((sum, item) => sum + Number(item.stars_today || 0), 0) / featuredProjects.value.length
    : 8
  const base = Math.max(4, Math.round(avgStarsToday))
  const curve = [0.72, 0.78, 0.75, 0.84, 0.81, 0.9, 0.96, 1.08]
  const values = curve.map((rate, idx) => Math.round(base * (rate + idx * 0.03)))
  const accent = isDark.value ? '#9bb7ff' : '#3e6dff'
  const fill = isDark.value ? 'rgba(155,183,255,.24)' : 'rgba(62,109,255,.18)'

  trendChart = new Chart(trendCanvasRef.value.getContext('2d'), {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          data: values,
          borderColor: accent,
          backgroundColor: fill,
          borderWidth: 2.5,
          fill: true,
          tension: 0.4,
          pointRadius: 0,
          pointHoverRadius: 4,
          pointHoverBackgroundColor: accent
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => `活跃增量 ${ctx.parsed.y}`
          }
        }
      },
      scales: {
        x: {
          ticks: {
            color: isDark.value ? '#9fb0d0' : '#7487ab',
            maxRotation: 0,
            autoSkip: true
          },
          grid: { display: false }
        },
        y: {
          ticks: {
            color: isDark.value ? '#8ea2c8' : '#8da0c2',
            maxTicksLimit: 4
          },
          grid: {
            color: isDark.value ? 'rgba(124,150,196,.22)' : 'rgba(140,162,205,.22)',
            drawBorder: false
          }
        }
      }
    }
  })
}

function renderRadarChart() {
  if (!radarCanvasRef.value) return
  if (radarChart) radarChart.destroy()

  const values = radarValues.value
  const accent = isDark.value ? '#9bb7ff' : '#3e6dff'
  const fill = isDark.value ? 'rgba(155,183,255,.24)' : 'rgba(62,109,255,.16)'

  radarChart = new Chart(radarCanvasRef.value.getContext('2d'), {
    type: 'radar',
    data: {
      labels: ['活跃度', '社区', '文档', '安全', '易用'],
      datasets: [{ data: [values.activity, values.community, values.docs, values.security, values.usability], borderColor: accent, backgroundColor: fill, borderWidth: 2, pointRadius: 1.5 }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        r: {
          min: 0,
          max: 5,
          ticks: { display: false },
          grid: { color: isDark.value ? '#2a3f67' : '#deE7fb' },
          angleLines: { color: isDark.value ? '#2a3f67' : '#deE7fb' },
          pointLabels: { color: isDark.value ? '#cddbf8' : '#4b5f83', font: { size: 12 } }
        }
      }
    }
  })
}

watch(isDark, (value) => {
  localStorage.setItem(THEME_KEY, value ? 'dark' : 'light')
})

watch(
  () => [featuredProjects.value, compareRows.value, isDark.value],
  async () => {
    await nextTick()
    renderTrendChart()
    renderRadarChart()
  },
  { deep: true }
)

onMounted(async () => {
  window.addEventListener('click', handleGlobalClick)
  const saved = localStorage.getItem(THEME_KEY)
  if (saved === 'dark' || saved === 'light') theme.value = saved
  await reloadFeed()
  await nextTick()
  renderTrendChart()
  renderRadarChart()
})

onBeforeUnmount(() => {
  window.removeEventListener('click', handleGlobalClick)
  destroyCharts()
})
</script>

<style scoped>
.discover-page {
  --bg: #f5f6fb;
  --surface: #ffffff;
  --line: #e3e8f2;
  --line-2: #d6deec;
  --text-main: #17233b;
  --text-sub: #56698e;
  --text-muted: #7f90ae;
  --brand: #3e6dff;
  --brand-soft: #edf2ff;
  --good: #16a34a;
  --warn: #ca8a04;
  --bad: #ef4444;
  min-height: 100dvh;
  background: var(--bg);
  color: var(--text-main);
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif;
}

.discover-page.dark {
  --bg: #0f1525;
  --surface: #111b31;
  --line: #223553;
  --line-2: #2a4268;
  --text-main: #e8efff;
  --text-sub: #adc0e5;
  --text-muted: #869cc8;
  --brand: #89abff;
  --brand-soft: #1b2c4a;
  --good: #35c777;
  --warn: #f5b941;
  --bad: #ff6b7f;
}

.topbar {
  height: 76px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  padding: 0 18px 0 16px;
  background: var(--surface);
  border-bottom: 1px solid var(--line);
  position: sticky;
  top: 0;
  z-index: 40;
  backdrop-filter: blur(10px);
}

.topbar-left,
.topbar-right {
  display: flex;
  align-items: center;
  gap: 14px;
}

.topbar-left {
  position: relative;
  flex: 1;
  min-width: 0;
}

.brand {
  border: none;
  background: transparent;
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}

.brand-icon {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: linear-gradient(135deg, #2f63ff, #6f95ff);
  display: grid;
  place-items: center;
}

.brand-icon svg {
  width: 20px;
  height: 20px;
  fill: #fff;
}

.brand-text strong {
  display: block;
  text-align: left;
  font-size: 24px;
  line-height: 1.08;
  letter-spacing: -0.02em;
  color: var(--text-main);
}

.brand-text small {
  display: block;
  margin-top: 1px;
  text-align: left;
  color: var(--text-muted);
  font-size: 11px;
}

.top-nav {
  display: flex;
  gap: 18px;
  margin-left: 56px;
}

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

.top-nav-btn {
  position: relative;
  border: none;
  border-radius: 10px;
  background: transparent;
  min-height: 38px;
  padding: 0 14px;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-sub);
  cursor: pointer;
  font-weight: 700;
  font-size: 14px;
  transition: background-color 0.2s ease, color 0.2s ease;
}

.top-nav-btn svg {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
}

.top-nav-btn::after {
  content: '';
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: -8px;
  height: 2px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--brand) 88%, #8db0ff 12%);
  opacity: 0;
  transform: scaleX(0.7);
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.top-nav-btn.active,
.top-nav-btn:hover {
  background: color-mix(in srgb, var(--brand-soft) 58%, var(--surface) 42%);
  color: var(--brand);
}

.top-nav-btn.active::after,
.top-nav-btn:hover::after {
  opacity: 1;
  transform: scaleX(1);
}

.theme-switch {
  border: 1px solid var(--line-2);
  border-radius: 999px;
  background: var(--surface);
  display: flex;
  align-items: center;
  gap: 8px;
  height: 38px;
  padding: 0 8px 0 10px;
  color: var(--text-sub);
  cursor: pointer;
}

.theme-switch svg {
  width: 14px;
  height: 14px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
}

.theme-track {
  width: 40px;
  height: 20px;
  border-radius: 999px;
  border: 1px solid var(--line-2);
  background: #e9eefb;
  padding: 1px;
  display: flex;
  align-items: center;
  transition: background 0.2s ease;
}

.theme-track i {
  width: 16px;
  height: 16px;
  border-radius: 999px;
  background: #fff;
  box-shadow: 0 2px 6px rgba(23, 35, 59, 0.2);
  transition: transform 0.2s ease;
}

.theme-track.dark {
  background: #3158c7;
}

.theme-track.dark i {
  transform: translateX(19px);
}

.icon-btn {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  border: 1px solid var(--line-2);
  background: var(--surface);
  color: var(--text-sub);
  display: grid;
  place-items: center;
  cursor: pointer;
  position: relative;
}

.icon-btn svg {
  width: 19px;
  height: 19px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
}

.notify-btn .badge {
  position: absolute;
  top: -4px;
  right: -4px;
  min-width: 15px;
  height: 15px;
  border-radius: 999px;
  background: #ef4444;
  color: #fff;
  font-size: 10px;
  display: grid;
  place-items: center;
}

.user-chip {
  border: 1px solid var(--line-2);
  border-radius: 999px;
  background: var(--surface);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 146px;
  padding: 4px 10px 4px 4px;
  cursor: pointer;
}

.user-chip img {
  width: 30px;
  height: 30px;
  border-radius: 999px;
}

.user-meta {
  min-width: 0;
  text-align: left;
}

.user-chip strong {
  display: block;
  color: var(--text-main);
  font-size: 13px;
}

.user-chip small {
  display: block;
  color: var(--text-muted);
  font-size: 11px;
}

.user-chip em {
  font-style: normal;
  color: var(--brand);
  font-size: 11px;
  font-weight: 800;
}

.user-menu-wrap {
  position: relative;
  display: flex;
  align-items: center;
  gap: 6px;
}

.user-menu-toggle {
  width: 30px;
  height: 30px;
  border: 1px solid var(--line-2);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text-sub);
  display: grid;
  place-items: center;
  cursor: pointer;
}

.user-menu-toggle svg {
  width: 14px;
  height: 14px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
}

.user-menu {
  position: absolute;
  right: 0;
  top: calc(100% + 8px);
  min-width: 140px;
  border: 1px solid var(--line-2);
  border-radius: 10px;
  background: var(--surface);
  box-shadow: 0 10px 24px rgba(31, 47, 82, 0.16);
  padding: 6px;
  display: grid;
  gap: 4px;
  z-index: 20;
}

.user-menu button {
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text-sub);
  text-align: left;
  font-size: 13px;
  min-height: 32px;
  padding: 0 9px;
  cursor: pointer;
}

.user-menu button:hover {
  background: var(--brand-soft);
  color: var(--brand);
}

.body-shell {
  display: grid;
  grid-template-columns: 248px minmax(0, 1fr) 376px;
  gap: 16px;
  padding: 14px 16px 20px;
  align-items: start;
}

.left-rail {
  position: sticky;
  top: 88px;
  height: calc(100dvh - 100px);
  background: color-mix(in srgb, var(--surface) 92%, #eff4ff 8%);
  border: 1px solid var(--line);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.left-main,
.left-bottom {
  padding: 12px;
}

.left-main {
  overflow: auto;
}

.left-bottom {
  border-top: 1px solid var(--line);
  margin-top: auto;
}

.left-group {
  display: grid;
  gap: 6px;
  margin-bottom: 14px;
}

.group-title {
  font-size: 13px;
  color: var(--text-muted);
  font-weight: 700;
}

.rail-btn {
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  color: var(--text-sub);
  min-height: 38px;
  padding: 0 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s ease;
}

.rail-btn svg {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
}

.rail-btn.active,
.rail-btn:hover {
  background: var(--brand-soft);
  border-color: var(--line-2);
  color: var(--brand);
}

.rail-badge {
  margin-left: auto;
  border-radius: 999px;
  background: color-mix(in srgb, var(--brand) 18%, #fff);
  border: 1px solid color-mix(in srgb, var(--brand) 40%, var(--line));
  color: var(--brand);
  font-size: 10px;
  line-height: 1;
  font-style: normal;
  font-weight: 700;
  padding: 3px 5px;
}

.quota-box {
  border: 1px solid var(--line-2);
  border-radius: 16px;
  background: var(--brand-soft);
  padding: 14px;
}

.quota-box p {
  color: var(--text-sub);
  font-size: 13px;
  font-weight: 700;
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
  justify-content: space-between;
  color: var(--text-sub);
  font-size: 13px;
}

.quota-upgrade {
  margin-top: 12px;
  width: 100%;
  min-height: 36px;
  border-radius: 12px;
  border: none;
  background: #5b6df5;
  color: #ffffff;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.main-stage {
  display: grid;
  gap: 14px;
  min-width: 0;
}

.hero {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 14px;
  min-height: 228px;
  background: var(--surface);
}

.hero-bg {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(560px 240px at 85% 6%, rgba(143, 169, 252, 0.33), transparent 68%),
    radial-gradient(420px 220px at -2% 104%, rgba(255, 207, 156, 0.2), transparent 70%),
    linear-gradient(145deg, #f4f6ff 0%, #eef2ff 52%, #f2f0ff 100%);
}

.discover-page.dark .hero-bg {
  background:
    radial-gradient(420px 220px at 86% 8%, rgba(121, 145, 220, 0.28), transparent 70%),
    radial-gradient(320px 160px at 14% 92%, rgba(235, 143, 95, 0.16), transparent 72%),
    linear-gradient(140deg, #1a2743, #1a2640 55%, #20263e);
}

.hero-content {
  position: relative;
  z-index: 2;
  padding: 20px 418px 14px 52px;
}

.hero-content h2 {
  font-size: clamp(16px, 1.35vw, 22px);
  line-height: 1.2;
  letter-spacing: -0.004em;
  font-weight: 700;
  max-width: 100%;
  white-space: nowrap;
  color: #101a33;
}

.hero-content p {
  margin-top: 10px;
  color: #5f6f8f;
  font-size: 14px;
  max-width: 640px;
}

.discover-page.dark .hero-content h2 {
  color: #e6eeff;
}

.hero-search {
  margin-top: 16px;
  border: 1px solid #d9deec;
  border-radius: 12px;
  background: #ffffff;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  padding: 4px 4px 4px 8px;
  width: min(680px, calc(100% - 16px));
  max-width: 680px;
  box-shadow: 0 6px 18px rgba(61, 84, 136, 0.08);
}

.discover-page.dark .hero-search {
  background: rgba(18, 33, 60, 0.85);
}

.hero-search input {
  border: none;
  outline: none;
  background: transparent;
  color: #2e3d5d;
  min-height: 42px;
  font-size: 14px;
  padding: 0 10px;
}

.hero-search input::placeholder {
  color: #8896b2;
}

.hero-search button {
  border: none;
  border-radius: 10px;
  width: 42px;
  min-width: 42px;
  min-height: 38px;
  padding: 0;
  background: #5b63f5;
  color: #fff;
  cursor: pointer;
  box-shadow: 0 8px 16px rgba(62, 109, 255, 0.28);
  transition: transform 0.15s ease, filter 0.2s ease;
  display: grid;
  place-items: center;
}

.hero-search button svg {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
}

.hero-search button:hover {
  filter: brightness(1.04);
}

.hero-search button:active {
  transform: translateY(1px);
}

.hero-chips {
  margin-top: 18px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  max-width: min(700px, calc(100% - 12px));
}

.hero-chips button {
  border: 1px solid #e3e7f4;
  border-radius: 999px;
  background: #eef1fb;
  color: #4d5d80;
  font-size: 13px;
  font-weight: 600;
  padding: 8px 16px;
  cursor: pointer;
}

.hero-illustration {
  position: absolute;
  right: 30px;
  top: -8px;
  width: 486px;
  height: 224px;
  z-index: 1;
  pointer-events: none;
}

.hero-illus-svg {
  width: 100%;
  height: 100%;
  display: block;
  filter: drop-shadow(0 8px 14px rgba(106, 132, 201, 0.14));
}

.discover-page.dark .hero-illus-svg {
  filter: brightness(0.9) saturate(0.88) drop-shadow(0 8px 14px rgba(22, 34, 62, 0.35));
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.section-header h3 {
  font-size: 24px;
  letter-spacing: -0.02em;
}

.section-header p {
  margin-top: 4px;
  color: var(--text-muted);
  font-size: 13px;
}

.link-btn {
  border: none;
  background: transparent;
  color: var(--brand);
  font-weight: 700;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.link-btn svg {
  width: 15px;
  height: 15px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
}

.state-row {
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--surface);
  color: var(--text-sub);
  min-height: 46px;
  padding: 0 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.state-row.error {
  color: var(--bad);
}

.state-row button {
  border: 1px solid var(--line-2);
  border-radius: 8px;
  background: var(--surface);
  color: inherit;
  min-height: 28px;
  padding: 0 10px;
  cursor: pointer;
}

.recommend-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(230px, 1fr));
  gap: 13px;
}

.recommend-card {
  border: 1px solid #e3e8f3;
  border-radius: 14px;
  background: #ffffff;
  padding: 13px;
  display: grid;
  gap: 10px;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
  min-height: 196px;
  font-family: 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Noto Sans SC', sans-serif;
}

.recommend-card:hover {
  transform: translateY(-1px);
  border-color: #ccd7ef;
  box-shadow: 0 10px 22px rgba(43, 67, 118, 0.08);
}

.recommend-card header {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
}

.repo-head {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr);
  gap: 9px;
  min-width: 0;
  align-items: center;
}

.repo-head img {
  width: 44px;
  height: 44px;
  border-radius: 999px;
  border: 1px solid #e4e9f5;
}

.repo-head-text {
  min-width: 0;
}

.repo-name {
  border: none;
  background: transparent;
  padding: 0;
  font-size: 18px;
  line-height: 1.2;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--text-main);
  cursor: pointer;
  text-align: left;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.repo-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.icon-action {
  width: 36px;
  height: 36px;
  border-radius: 999px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  display: grid;
  place-items: center;
  cursor: pointer;
}

.icon-action svg {
  width: 19px;
  height: 19px;
  fill: currentColor;
}

.icon-action.active {
  color: #566ff7;
}

.icon-action:hover {
  color: #4d66f6;
}

.repo-summary {
  font-size: 13px;
  line-height: 1.45;
  color: #6c7b97;
  min-height: 54px;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.repo-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.repo-tags span {
  border: 1px solid #f1d7b3;
  border-radius: 999px;
  background: #fff3e2;
  color: #915420;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.01em;
  padding: 4px 10px;
}

.repo-tags span:nth-child(2) {
  border-color: #b9e9df;
  background: #e9faf5;
  color: #0f7566;
}

.repo-footer {
  margin-top: auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.repo-stats {
  display: inline-flex;
  gap: 13px;
}

.repo-stats span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #7484a3;
  font-size: 12px;
  font-weight: 600;
}

.repo-stats svg {
  width: 14px;
  height: 14px;
  fill: currentColor;
}

.compare-btn {
  border: 1px solid #cfd8ea;
  border-radius: 999px;
  min-height: 32px;
  padding: 0 15px;
  background: #f2f5fb;
  color: #3e547b;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.01em;
  cursor: pointer;
  transition: all 0.2s ease;
  margin-top: -4px;
}

.compare-btn:hover {
  border-color: #a9b7d2;
  background: #ecf1fa;
}

.compare-btn.active {
  border-color: #546cf4;
  background: linear-gradient(135deg, #5a67f7, #7286ff);
  color: #fff;
}

.insight-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(0, 1fr) minmax(0, 1fr);
  gap: 12px;
  align-items: stretch;
}

.trend-card {
  min-height: 270px;
}

.radar-card {
  min-height: 270px;
}

.risk-card {
  min-height: 270px;
}

.insight-card {
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--surface);
  padding: 12px;
  display: flex;
  flex-direction: column;
  min-height: 220px;
}

.insight-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.insight-head h4 {
  font-size: 18px;
  letter-spacing: -0.02em;
}

.insight-head span {
  font-size: 12px;
  color: var(--text-muted);
}

.trend-percent {
  margin-top: 8px;
  font-size: 34px;
  line-height: 1;
  color: var(--good);
  font-weight: 700;
}

.trend-caption {
  margin-top: 6px;
  color: var(--text-muted);
  font-size: 13px;
}

.chart-wrap {
  margin-top: 8px;
  height: 160px;
}

.trend-body {
  margin-top: 8px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 206px;
  gap: 12px;
  align-items: stretch;
  min-height: 176px;
}

.chart-wrap.chart-trend {
  margin-top: 0;
  height: 100%;
}

.category-trend {
  border-left: 1px dashed var(--line-2);
  padding-left: 12px;
}

.category-trend p {
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 700;
}

.growth-list {
  margin-top: 8px;
  list-style: none;
  display: grid;
  gap: 8px;
}

.growth-list li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--brand-soft);
  padding: 6px 8px;
  font-size: 12px;
}

.growth-list strong {
  color: var(--good);
}

.risk-list {
  margin-top: 10px;
  list-style: none;
  display: grid;
  gap: 8px;
  flex: 1;
  align-content: start;
}

.risk-list li {
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 8px;
  display: flex;
  justify-content: space-between;
  gap: 8px;
}

.risk-list li strong {
  font-size: 12px;
}

.risk-list li p {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-sub);
  line-height: 1.4;
}

.risk-list li span {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
}

.risk-high {
  background: rgba(239, 68, 68, 0.12);
  border-color: rgba(239, 68, 68, 0.28);
}

.risk-high strong {
  color: #dc2626;
}

.risk-medium {
  background: rgba(245, 186, 64, 0.16);
  border-color: rgba(245, 186, 64, 0.38);
}

.risk-medium strong {
  color: #b45309;
}

.risk-low {
  background: rgba(255, 114, 118, 0.12);
  border-color: rgba(255, 114, 118, 0.25);
}

.risk-low strong {
  color: #e11d48;
}

.compare-section {
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--surface);
  padding: 12px;
}

.compare-section header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.compare-section h4 {
  font-size: 20px;
}

.picked-repos {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.picked-repos span {
  border: 1px solid var(--line-2);
  border-radius: 999px;
  background: var(--brand-soft);
  color: var(--text-sub);
  font-size: 11px;
  padding: 4px 9px;
}

.compare-section header button {
  border: 1px solid var(--line-2);
  border-radius: 8px;
  background: var(--surface);
  color: var(--brand);
  min-height: 34px;
  padding: 0 12px;
  font-weight: 700;
  cursor: pointer;
}

.compare-section header button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.compare-table {
  margin-top: 10px;
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.compare-table th,
.compare-table td {
  border-bottom: 1px solid var(--line);
  padding: 8px;
  text-align: left;
}

.compare-table th {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
}

.assistant-panel {
  position: sticky;
  top: 88px;
  height: calc(100dvh - 100px);
  border: 1px solid var(--line);
  border-radius: 12px;
  background: #f3f5f9;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow: hidden;
}

.assistant-panel header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.assistant-panel h3 {
  font-size: 24px;
  letter-spacing: -0.01em;
  color: #12284a;
}

.assistant-panel header button {
  border: 1px solid var(--line-2);
  border-radius: 8px;
  background: #ffffff;
  color: #1d3258;
  min-height: 36px;
  padding: 0 14px;
  font-weight: 700;
  cursor: pointer;
}

.message-list {
  border-radius: 10px;
  background: #eef1f7;
  padding: 12px;
  flex: 1;
  min-height: 320px;
  overflow: auto;
  display: grid;
  gap: 10px;
  grid-auto-rows: max-content;
  align-content: start;
  align-items: start;
}

.msg-row {
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr);
  gap: 10px;
  align-items: start;
}

.msg-row.user {
  grid-template-columns: minmax(0, 1fr) 30px;
}

.msg-row.user .avatar {
  order: 2;
}

.msg-row.user p {
  order: 1;
  justify-self: end;
  max-width: 88%;
  border: none;
  background: linear-gradient(135deg, #2e58d9, #2c6be6);
  color: #fff;
  border-radius: 14px 14px 6px 14px;
}

.avatar {
  width: 30px;
  height: 30px;
  border-radius: 9px;
  border: 1px solid #cfd8e8;
  background: #fff;
  display: grid;
  place-items: center;
  font-size: 11px;
  font-weight: 700;
}

.msg-row.assistant .avatar {
  color: #2f58d6;
}

.msg-row p {
  border: 1px solid #d9e2f1;
  border-radius: 14px 14px 14px 6px;
  background: #fff;
  padding: 10px 12px;
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: #223b63;
  white-space: pre-wrap;
  max-width: 92%;
}

.assistant-status {
  color: #6b7c98;
  font-size: 12px;
  padding-left: 38px;
}

.quick-questions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 0 2px;
}

.quick-questions p {
  width: 100%;
  margin: 0 0 4px;
  color: #6f819f;
  font-size: 12px;
  font-weight: 600;
}

.quick-questions button {
  border: 1px solid #cfdaed;
  border-radius: 999px;
  background: #fff;
  color: #35517f;
  font-size: 12px;
  padding: 6px 11px;
  cursor: pointer;
}

.quick-questions button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.assistant-composer {
  margin-top: auto;
  border-top: 1px solid #d6deeb;
  padding-top: 10px;
  display: grid;
  gap: 8px;
}

.assistant-input {
  width: 100%;
  border: 1px solid #d4deed;
  border-radius: 12px;
  outline: none;
  background: #f8f9fc;
  color: #1d3359;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.5;
  min-height: 106px;
  padding: 10px 12px;
  resize: none;
}

.assistant-input:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.assistant-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tool-btn {
  border: 1px solid #d4deed;
  border-radius: 10px;
  background: #f7f9fc;
  color: #587096;
  min-height: 30px;
  padding: 0 10px;
  font-size: 12px;
  cursor: pointer;
}

.tool-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.char-count {
  color: #5e7396;
  font-size: 12px;
  margin-left: 2px;
}

.send-btn {
  border: none;
  border-radius: 12px;
  margin-left: auto;
  min-width: 96px;
  min-height: 40px;
  padding: 0 16px;
  color: #fff;
  font-weight: 700;
  cursor: pointer;
  background: linear-gradient(135deg, #6f93e9, #6f8fe8);
  transition: filter 0.2s ease;
}

.send-btn:hover {
  filter: brightness(1.05);
}

.send-btn.danger {
  background: linear-gradient(135deg, #f97316, #ef4444);
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.assistant-error {
  color: var(--bad);
  font-size: 12px;
}

.assistant-float-tools {
  position: absolute;
  right: 10px;
  top: 54%;
  display: grid;
  gap: 10px;
  pointer-events: none;
}

.assistant-float-tools button {
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.9);
  color: #d57da1;
  font-size: 16px;
  box-shadow: 0 6px 18px rgba(83, 110, 163, 0.15);
}

.discover-page.dark .assistant-panel {
  background: #111a2d;
}

.discover-page.dark .assistant-panel h3 {
  color: #dbe8ff;
}

.discover-page.dark .assistant-panel header button {
  background: #1a2944;
  border-color: #2f4770;
  color: #bbcdf2;
}

.discover-page.dark .message-list {
  background: #16243b;
}

.discover-page.dark .avatar {
  background: #1d2d4a;
  border-color: #34507d;
}

.discover-page.dark .msg-row p {
  background: #1d2d49;
  border-color: #2f4a73;
  color: #d5e2fb;
}

.discover-page.dark .msg-row.user p {
  background: linear-gradient(135deg, #2d5ce1, #3778ff);
  color: #fff;
}

.discover-page.dark .quick-questions p,
.discover-page.dark .char-count,
.discover-page.dark .assistant-status {
  color: #94aad3;
}

.discover-page.dark .quick-questions button,
.discover-page.dark .tool-btn {
  background: #1b2b46;
  border-color: #32507d;
  color: #bdd0f2;
}

.discover-page.dark .assistant-composer {
  border-top-color: #2c436b;
}

.discover-page.dark .assistant-input {
  background: #1b2b45;
  border-color: #304d79;
  color: #dbe7ff;
}

@media (max-width: 1520px) {
  .body-shell {
    grid-template-columns: 230px minmax(0, 1fr) 340px;
  }

  .recommend-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .hero-content {
    padding: 20px 380px 14px 44px;
  }

  .hero-illustration {
    width: 434px;
    height: 214px;
    right: 18px;
    top: -6px;
  }
}

@media (max-width: 1280px) {
  .top-nav {
    margin-left: 18px;
  }

  .topbar-search {
    left: 58%;
    width: min(350px, 38vw);
  }

  .body-shell {
    grid-template-columns: 1fr;
  }

  .left-rail,
  .assistant-panel {
    position: static;
    height: auto;
  }

  .hero {
    grid-template-columns: 1fr;
  }

  .hero-content {
    padding-right: 22px;
  }

  .hero-illustration {
    display: none;
  }

  .insight-grid {
    grid-template-columns: 1fr;
  }

  .trend-body {
    grid-template-columns: 1fr;
  }

  .category-trend {
    border-left: none;
    border-top: 1px dashed var(--line-2);
    padding-left: 0;
    padding-top: 10px;
  }

  .message-list {
    min-height: 260px;
  }

  .assistant-float-tools {
    display: none;
  }
}

@media (max-width: 920px) {
  .topbar {
    height: auto;
    padding: 10px;
    flex-direction: column;
    align-items: center;
    gap: 8px;
  }

  .topbar-left,
  .topbar-right {
    justify-content: space-between;
    width: 100%;
  }

  .topbar-search {
    position: static;
    transform: none;
    width: 100%;
    max-width: none;
    margin-top: 6px;
  }

  .topbar-right {
    justify-content: flex-end;
  }

  .user-chip {
    min-width: auto;
    padding-right: 8px;
  }

  .user-chip small {
    display: none;
  }

  .top-nav {
    margin-left: 8px;
  }

  .brand-text strong {
    font-size: 24px;
  }

  .hero-content h2 {
    font-size: 26px;
  }

  .recommend-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>



















