# GitHub Trending 分析推送工具

自动抓取 GitHub Trending 榜单，通过 LLM 分析每个项目的核心价值和爆火原因，并推送日报到飞书。

## 功能特性

- **智能数据抓取**: 异步并行获取 GitHub Trending 榜单和项目 README
- **README 智能清洗**: 自动过滤徽章、HTML 标签、非核心章节，保留关键信息
- **智能内容分块**: 基于段落的分块策略，支持多模态输入（文本+图片）
- **LLM 深度分析**: 分析项目简介和爆火原因，支持重试和失败降级
- **分析结果缓存**: SQLite 缓存
- **多渠道推送**: 支持飞书机器人推送和终端打印
- **灵活配置**: 环境变量配置，支持多模态开关、缓存控制等

## 安装

```bash
pip install -r requirements.txt
```

## 配置

复制 `.env.example` 为 `.env`，填入必要的配置：

```env
# OpenAI / SiliconFlow API（必填）
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.siliconflow.cn/v1
OPENAI_MODEL=Qwen/Qwen3.5-397B-A17B

# GitHub Token（可选，建议填入以提高 API 限制）
GITHUB_TOKEN=your_github_token

# 飞书配置（可选，用于推送通知）
FEISHU_APP_ID=your_app_id
FEISHU_APP_SECRET=your_app_secret
FEISHU_RECEIVE_ID=your_receive_id
FEISHU_RECEIVE_ID_TYPE=chat_id

# 多模态配置（可选）
MULTIMODAL_MAX_CHARS=3000
MULTIMODAL_MAX_IMAGES=3
MULTIMODAL_ENABLE=false
```

## 使用

```bash
# 基础用法（分析 10 个热门项目并推送）
python main.py

# 指定编程语言
python main.py -l python

# 指定时间范围（daily/weekly/monthly）
python main.py -s weekly

# 指定获取数量
python main.py -n 10

# 禁用飞书推送，仅打印到终端
python main.py --no-notify

# 调整日志级别
python main.py --log-level DEBUG
```

## 项目结构

```
quick-push/
├── main.py                      # 入口文件
├── core/
│   ├── config.py               # 统一配置管理
│   ├── github_fetcher.py       # GitHub 数据抓取（异步）
│   ├── readme_cleaner.py       # README 智能清洗
│   └── summarizer.py           # LLM 项目分析（支持缓存）
├── utils/
│   ├── cache.py                # SQLite 分析结果缓存
│   ├── logging_config.py       # 日志配置
│   ├── multimodal_builder.py   # 多模态 payload 构建
│   └── notifier.py             # 飞书/打印通知
└── tests/                      # 单元测试
```

## 核心流程

```
1. 抓取 GitHub Trending 榜单
   ↓
2. 异步并行获取项目 README
   ↓
3. README 智能清洗（过滤徽章、HTML、非核心章节）
   ↓
4. 智能分块（段落级分割，提取图片）
   ↓
5. 检查缓存 → 命中则直接返回
   ↓
6. LLM 分析（支持重试和失败处理）
   ↓
7. 保存到缓存
   ↓
8. 推送日报（飞书/终端）
```

## 缓存机制

分析结果会自动缓存到 SQLite 数据库（`.cache/analysis_cache.db`）：

- **缓存键**: 项目全名（`owner/repo`）
- **缓存内容**: 项目简介、爆火原因、分析时间
- **缓存策略**: 简单缓存，不检测 README 变化
- **缓存统计**: 可通过 `AnalysisCache().get_stats()` 查看

禁用缓存：
```python
summarizer = Summarizer(enable_cache=False)
```

## 开发

```bash
# 运行测试
pytest tests/

# 查看缓存统计
python -c "from utils.cache import AnalysisCache; print(AnalysisCache().get_stats())"

# 清空缓存
python -c "from utils.cache import AnalysisCache; AnalysisCache().clear()"
```

## 技术栈

- **异步爬虫**: aiohttp, BeautifulSoup
- **LLM 调用**: LangChain, ChatOpenAI
- **配置管理**: Pydantic, python-dotenv
- **数据缓存**: SQLite
- **消息推送**: 飞书 Open API

## 自动化部署

推荐配合 GitHub Actions 使用，实现每日自动推送：

```yaml
# .github/workflows/daily-trending.yml
name: Daily GitHub Trending

on:
  schedule:
    - cron: '0 9 * * *'  # 每天上午 9 点
  workflow_dispatch:  # 支持手动触发

jobs:
  push:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python main.py
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          FEISHU_APP_ID: ${{ secrets.FEISHU_APP_ID }}
          FEISHU_APP_SECRET: ${{ secrets.FEISHU_APP_SECRET }}
          FEISHU_RECEIVE_ID: ${{ secrets.FEISHU_RECEIVE_ID }}
```

## License

MIT
