# QuickPush 🚀

> 追踪 GitHub Trending，用更少时间看懂项目，用对话方式快速找到真正值得关注的开源仓库。

QuickPush 是一个面向开发者的实用工具箱。
它把零散的 Trending 信息，整理成可以直接拿来决策的洞察：

- 抓取 GitHub Trending（daily / weekly / monthly）
- 生成 AI 摘要与推荐理由
- 用混合检索（向量 + BM25 + 重排）搜索项目
- 通过聊天接口进行项目问答与推荐
- 在可视化看板里查看趋势变化

***

## 这个项目解决了什么问题 ❓

大家都知道 Trending 有价值，但也有一个现实问题：
信息很多、噪音也很多，真正适合自己的项目并不好找。

QuickPush 的目标是把“刷榜”变成“有依据的筛选”：

- 这个项目适合拿来做什么
- 为什么它值得关注
- 它和你当前需求的匹配度如何

如果你在做技术选型、搭建 side project、或持续跟踪 AI/开发工具趋势，这个项目会很有帮助。

***

## 核心功能 ✨

- Trending 数据管道（抓取 + 分类 + 入库）
- AI 分析（摘要 + 推荐理由）
- 分块检索链路（chunk 召回 -> 重排 -> repo 聚合）
- 去重与多样性控制（避免结果被单一仓库“刷屏”）
- 聊天 API（普通模式 + SSE 流式）
- Dashboard / Trends / Search API
- Vue 前端可视化
- 可选飞书通知

***

## 技术栈 🧰

- 后端：`Python`、`FastAPI`、`SQLite`
- 检索：`ChromaDB`、`BM25`、`Cross-Encoder`、`jieba`
- LLM：OpenAI 兼容接口（`openai` + `langchain-openai`）
- 前端：`Vue 3`、`Vite`、`Pinia`、`Vue Router`、`Chart.js`

***

## 项目结构 🗂️

```text
quick-push/
├── app/                    # 核心逻辑：抓取、分析、检索、基础设施
├── data/
│   ├── sqlite/             # SQLite 数据（analysis_cache.db）
│   └── chroma/             # Chroma 向量索引数据
├── web/
│   ├── backend/            # FastAPI 服务
│   └── frontend/           # Vue 前端
├── tests/                  # pytest 自动化测试
├── scripts/                # 工具脚本（含手动检查脚本）
├── .github/workflows/      # CI / 定时任务
├── main.py                 # CLI 入口（抓取 + 分析 + 通知）
├── pytest.ini
├── requirements.txt
└── README.md
```

***

## 快速开始 ⚡

### 1. 环境要求 🧱

- Python `3.9+`
- Node.js `18+`
- npm `9+`

### 2. 安装依赖 📦

```bash
pip install -r requirements.txt
```

```bash
cd web/frontend
npm install
cd ../..
```

### 3. 配置环境变量 🔐

复制 `.env.example` 为 `.env`，至少配置以下内容：

```env
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.siliconflow.cn/v1
```

可选配置（GitHub Token、飞书、模型路由、多模态开关、Reddit 检索等）请参考 `.env.example`。
其中 `GITHUB_TOKEN` 为可选，不配置也可运行（但更容易遇到限流）。

### 4. 运行数据管道（CLI） 🏃

```bash
# 默认：抓取 + 分析 + 通知
python main.py

# 示例
python main.py --language python
python main.py --since weekly --limit 20
python main.py --no-notify
python main.py --no-cache
```

### 5. 启动后端 🖥️

```bash
python web/backend/run.py
```

- API 地址：`http://localhost:8000`
- 健康检查：`http://localhost:8000/health`

### 6. 启动前端 🌐

```bash
cd web/frontend
npm run dev
```

- 前端地址：`http://localhost:3000`（或 Vite 分配端口）

***

## API 概览 🔌

- `GET /api/dashboard`：看板数据
- `GET /api/trends`：趋势分析
- `GET /api/search`：项目搜索
- `POST /api/search/index`：重建检索索引
- `GET /api/search/stats`：检索统计
- `POST /api/chat`：非流式对话
- `POST /api/chat/stream`：流式对话（SSE）
- `GET /api/github/validate`：验证 GitHub Token
- `GET /api/github/rate-limit`：查看 GitHub API 配额

***

## 推荐开发流程 🛠️

1. 先执行 `python main.py` 抓取和分析最新项目。
2. 调用 `POST /api/search/index` 刷新检索索引。
3. 启动前端，联调 Dashboard / Search / Chat。
4. 迭代提示词、检索参数和重排策略。

***

## 测试与验证 ✅

自动化测试（pytest）：

```bash
python -m pytest
```

手动分类检查脚本（会调用真实模型接口）：

```bash
python scripts/manual_confidence_check.py
```

***

## 数据目录说明 💾

- 当前默认数据目录为 `data/sqlite` 与 `data/chroma`。
- 历史目录 `.cache` 与 `.chroma_db` 已废弃。
- `AnalysisCache` 仍保留从 `.cache/analysis_cache.db` 到 `data/sqlite/analysis_cache.db` 的一次性兼容迁移逻辑（如存在旧库）。

***

## 常见问题 🧯

- 缺少 `OPENAI_API_KEY` 或 `OPENAI_BASE_URL` 不可用
  - 后端初始化或聊天分析会失败。
- 没有配置 `GITHUB_TOKEN`
  - 可以运行，但抓取 GitHub 数据时更可能触发限流或超时重试。
- 前端请求失败
  - 请确认后端是否已在 `:8000` 启动。
- 搜索没有结果
  - 先确认数据已抓取，并且已执行索引重建。
- 聊天响应慢
  - 请检查模型服务延迟和 API 配额。

***



## 参与贡献 🤝

欢迎提 Issue 和 PR。


***

## License 📄

MIT
