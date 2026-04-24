# OpenScout 🚀

> 从 GitHub 热榜中，找到真正值得投入时间的项目。

OpenScout 是一个面向开发者的开源项目发现与决策助手。
它不是单纯的 GitHub Trending 可视化页面，也不是单纯的 RAG Demo，而是一个把开源发现、项目理解、检索问答和决策支持串起来的 AI-native 工具。

它把零散的 GitHub Trending 信息，整理成可搜索、可理解、可问答的项目洞察，帮助你更快完成技术筛选、趋势跟踪和项目探索。

你可以用它来：

- 抓取 GitHub Trending（daily / weekly / monthly）
- 生成 AI 摘要与推荐理由
- 用混合检索（向量 + BM25 + 重排）搜索项目
- 通过聊天接口进行项目问答与推荐
- 在可视化看板里查看趋势变化

***

## 适合谁使用 👥

- 独立开发者
- AI 应用开发者
- 持续关注技术趋势的工程师
- 正在做技术选型、原型验证或 side project 的开发者

***

## 这个项目解决了什么问题 ❓

GitHub Trending 很有价值，但也有一个现实问题：
信息很多、噪音也很多，真正值得深入看、值得投入时间的项目并不好找。

OpenScout 想解决的，不是“怎么把热榜展示出来”，而是“怎么把刷榜变成有依据的筛选和判断”：

- 这个项目适合拿来做什么
- 为什么它值得关注
- 它和你当前需求的匹配度如何

如果你在做技术选型、搭建 side project、评估开源方案，或者持续跟踪 AI / 开发工具趋势，OpenScout 会是一个更高效的入口。

换句话说，OpenScout 想做的是：

- 帮你发现值得关注的开源项目
- 帮你理解项目背后的价值与适用场景
- 帮你基于搜索、推荐和问答更快做出技术判断

***

## 核心功能 ✨

- Trending 数据管道（抓取 + 分类 + 入库）
- AI 分析（摘要 + 推荐理由）
- 分块检索链路（chunk 召回 -> 重排 -> repo 聚合）
- 去重与多样性控制（避免结果被单一仓库“刷屏”）
- 聊天 API（仅 SSE 流式）
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

RAG 离线评估（增强手工评测集，建议在 `llm` 环境执行）：

```bash
conda run -n llm python scripts/eval_rag_quality.py \
  --eval-set data/eval/manual_eval_set.v2.jsonl \
  --top-k 10 \
  --baseline vector \
  --check-answers \
  --max-answer-queries 60 \
  --manual-off-topic-sample 60 \
  --manual-off-topic-output data/eval/manual_off_topic_sample.v2.60.jsonl \
  --output data/eval/eval_report.manual.v2.json
```

- 增强手工评测集：`data/eval/manual_eval_set.v2.jsonl`（102 条，含 `query_type` 与 hard negative）
- 可加 `--max-eval-queries 60` 做快速迭代评测
- 人工标注说明：`docs/eval/manual_quality_workflow.md`
- 回归门禁脚本：`scripts/check_eval_regression.py`（或 `scripts/run_eval_gate.ps1`）

***

## 数据目录说明 💾

- 当前默认数据目录为 `data/sqlite` 与 `data/chroma`。
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
