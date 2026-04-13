# QuickPush

QuickPush 是一个面向 GitHub Trending 的智能追踪与分析平台。\
它可以抓取热门仓库、生成 AI 摘要与推荐理由，并提供可视化看板和聊天式探索能力，帮助你快速发现值得关注的项目。

## 功能特性

- GitHub Trending 抓取与历史归档（SQLite）
- AI 摘要生成与项目分类
- 搜索与相似度检索
- 聊天问答（支持 SSE 流式响应）
- 看板与趋势分析页面
- 可选飞书通知
- GitHub Actions 定时自动执行

## 技术栈

- 后端：`Python`、`FastAPI`、`Pydantic`、`SQLite`
- AI：OpenAI 兼容接口 + `LangChain`
- 前端：`Vue 3`、`Vite`、`Pinia`、`Vue Router`、`Chart.js`
- 部署：`Render`、`GitHub Actions`

## 项目结构

```text
quick-push/
|-- app/                      # 核心逻辑：抓取、分析、检索、基础设施
|-- web/
|   |-- backend/              # FastAPI 服务
|   `-- frontend/             # Vue 3 前端
|-- scripts/                  # 工具和迁移脚本
|-- .github/workflows/        # CI/CD 与定时任务
|-- main.py                   # CLI 入口（抓取 + 分析 + 通知）
|-- requirements.txt
`-- render.yaml
```

## 快速开始

### 1. 环境要求

- Python `3.9+`
- Node.js `18+`
- npm `9+`

### 2. 安装后端依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

复制 `.env.example` 为 `.env`，并至少配置以下必填项：

```env
OPENAI_API_KEY=your_openai_api_key
OPENAI_BASE_URL=openai_base_url
GITHUB_TOKEN=your_github_token
```

可选配置：

- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`
- `FEISHU_RECEIVE_ID`
- `FEISHU_RECEIVE_ID_TYPE`
- `OPENAI_MODEL_FAST`
- `OPENAI_MODEL_STANDARD`
- `OPENAI_MODEL_PRO`
- `OPENAI_MODEL_CHAT`
- `OPENAI_MODEL_FALLBACK`

### 4. 运行数据管道（CLI）

```bash
# 默认执行：抓取 + 分析 + 通知
python main.py

# 按语言过滤
python main.py --language python

# 限制抓取数量
python main.py --limit 10

# 禁用通知
python main.py --no-notify
```

### 5. 启动后端 API

```bash
python web/backend/run.py
```

- API 地址：`http://localhost:8000`
- 健康检查：`http://localhost:8000/health`

### 6. 启动前端（Vue）

```bash
cd web/frontend
npm install
npm run dev
```

- 前端地址：`http://localhost:3000`
- Vite 已配置代理：`/api -> http://localhost:8000`

## API 概览

- `GET /api/dashboard` 看板数据
- `GET /api/trends` 趋势分析
- `GET /api/search` 项目搜索
- `POST /api/search/index` 重建搜索索引
- `GET /api/search/stats` 索引统计
- `POST /api/chat` 非流式问答
- `POST /api/chat/stream` 流式问答（SSE）
- `GET /api/github/validate` 验证 GitHub Token
- `GET /api/github/rate-limit` 查看 GitHub API 配额

## 构建前端

```bash
cd web/frontend
npm run build
```

构建产物目录：`web/frontend/dist`。

## 部署

### Render

仓库中已提供 `render.yaml`。\
默认启动命令：

```bash
cd web/backend && python run.py
```

请在 Render 中配置必要环境变量，尤其是 `OPENAI_API_KEY` 与 `GITHUB_TOKEN`。

### GitHub Actions

已提供定时任务配置：

- `.github/workflows/daily-trending.yml`

可按计划自动执行抓取分析，并在有变更时自动提交数据库更新。

## 常见问题

- 缺少 `OPENAI_API_KEY` 或 `GITHUB_TOKEN`：后端初始化会失败
- 前端请求失败：请确认后端已在 `8000` 端口启动
- 聊天长时间无响应：请检查模型服务可用性和 API 配额
- 趋势页无数据：请先执行一次 `python main.py` 生成本地缓存

## 参与贡献

欢迎提交 Issue 和 PR

## 许可证

MIT
