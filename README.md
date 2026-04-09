# QuickPush

GitHub Trending 热门项目智能分析工具，基于 Multi-Agent 架构，自动分析热门项目的爆火原因和技术价值。

## ✨ 特性

- 🤖 **Multi-Agent 协作** - Scout（趋势侦察）、Analyst（技术分析）、Editor（编辑整合）三个 Agent 协同工作
- 🔍 **多源数据聚合** - 整合 Hacker News、Reddit、GitHub Discussions 等社区讨论
- 📊 **深度分析报告** - 输出项目简介、爆火原因、技术亮点、目标用户等结构化内容
- ⚡ **异步并行处理** - 高效处理多个项目，快速生成分析报告
- 🔔 **多平台推送** - 支持飞书群推送

## 🚀 快速开始

### 安装

```bash
pip install -r requirements.txt
```

### 配置

创建 `.env` 文件：

```env
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.siliconflow.cn/v1
FEISHU_APP_ID=your_app_id
FEISHU_APP_SECRET=your_app_secret
```

### 使用

```bash
# 分析热门项目
python main.py

# 指定语言
python main.py --language python

# 限制数量
python main.py --limit 10

# 仅终端输出
python main.py --no-notify
```

## 📖 示例输出

```
项目分析:
  项目简介：Oh My Codex (OMX) 是 OpenAI Codex CLI 的增强工具，通过添加 hooks、智能体团队、HUD 界面等功能，将单点 AI 代码生成扩展为可协作、可定制的工作流。
  
  爆火原因:
    - 通过结构化工作流解决原始 AI 编码助手输出不一致问题
    - 引入多智能体团队协作概念，支持处理复杂任务
    - 提供 HUD 界面和钩子等扩展，增强 AI 协作的可控性
  
  技术亮点:
    - 混合架构：TypeScript 协调层 + Rust 高性能模块
    - 基于 tmux 的跨终端会话管理
  
  目标用户：熟悉 OpenAI Codex CLI 的中高级开发者
```

## 🏗️ 架构

```
Scout Agent ─────┐
                 ├──► Editor Agent ──► 结构化报告
Analyst Agent ───┘
```

- **Scout**：搜索外部讨论，分析爆火原因和趋势关联
- **Analyst**：评估技术深度、代码质量、潜在风险
- **Editor**：整合分析结果，生成最终报告

## 🛠️ 技术栈

- Python 3.9+
- LangChain + ChatOpenAI
- aiohttp（异步爬虫）
- SQLite（数据缓存）
- Pydantic（配置管理）

## 📄 License

MIT