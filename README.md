# QuickPush

GitHub Trending 热门项目智能分析工具，基于 Multi-Agent 架构，自动分析热门项目的爆火原因和技术价值。

## ✨ 特性

- 🤖 **Multi-Agent 协作** - Scout（趋势侦察）、Analyst（技术分析）、Editor（编辑整合）三个 Agent 协同工作
- 🔍 **多源数据聚合** - 整合 Hacker News、Reddit、GitHub Discussions 等社区讨论
- 📊 **深度分析报告** - 输出项目分析（价值、可行性）和爆火原因（结合热点）
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
Oh My codeX (OmX) 是一个为 OpenAI Codex CLI 设计的增强层，其核心价值在于将复杂的提示工程和多智能体协作工作流产品化、命令行化。它解决了开发者在 AI 辅助编程中面临的工作流碎片化、会话状态不可重复等工程难题，通过预设技能和项目级状态管理，使 AI 协作变得可预测、可积累。

爆火原因:
  - 将前沿提示工程与多智能体协作封装为简单命令，降低使用门槛
  - 通过 .omx/ 目录管理会话状态，解决 AI 编程可重复性与工程化痛点
  - 定位为 Codex CLI 增强层，提供开箱即用的高价值体验升级
```

## 🏗️ 架构

```
Scout Agent ─────┐
                 ├──► Editor Agent ──► 项目分析 + 爆火原因
Analyst Agent ───┘
```

- **Scout（趋势侦察员）**：市场层面分析，搜索外部讨论，分析爆火原因、趋势关联、社区热度、竞争优势
- **Analyst（技术分析师）**：技术层面分析，评估部署难度、代码质量、Issue 健康度
- **Editor（编辑）**：整合 Scout 和 Analyst 的调研资料，生成面向用户的简洁报告

## 🛠️ 技术栈

- Python 3.9+
- LangChain + ChatOpenAI
- aiohttp（异步爬虫）
- SQLite（数据缓存）
- Pydantic（配置管理）

## 📄 License

MIT