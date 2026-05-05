# Discover 工作台改造执行报告（2026-04-25）

## 1. 识别到的问题

1. 当前产品能力分散在 `chat / dashboard / trends`，没有“发现 -> 对比 -> 建议”的单页闭环。
2. 虽然有分析数据，但缺少统一评分结构，前端难以做对比决策视图。
3. 多智能体产出的信息没有直接落成“可对比、可解释、可执行”的决策输出。

## 2. 改造目标

1. 新增一个 Discover 工作台页面，提供三栏布局：左导航、中间推荐与对比、右侧 AI 建议。
2. 后端新增 3 个接口：
   - `GET /api/discover/feed`
   - `POST /api/compare/score`
   - `POST /api/assistant/recommend`
3. 形成统一评分结果：`overall_score + dimensions + risk_flags`。

## 3. 具体执行内容

### 3.1 后端

文件：`web/backend/routers/api.py`

1. 新增请求模型：
   - `CompareScoreRequest`
   - `AssistantRecommendRequest`
2. 新增评分/风险/推荐辅助函数：
   - `_compute_project_score`
   - `_extract_risk_flags`
   - `_collect_discover_projects`
   - `_resolve_compare_item`
   - `_build_recommendation`
3. 新增 API 路由：
   - `GET /api/discover/feed`
   - `POST /api/compare/score`
   - `POST /api/assistant/recommend`

### 3.2 前端

文件：`web/frontend/src/views/DiscoverView.vue`

1. 新建 Discover 工作台页面，完成三栏结构：
   - 左侧导航与工作区卡片
   - 中间 Hero、推荐卡片、趋势/健康度/风险面板、对比表
   - 右侧 AI 助手问答与推荐结论卡
2. 支持项目选择进入对比（最多 5 项）。
3. 支持快捷问题触发 AI 推荐接口。

文件：`web/frontend/src/composables/useApi.js`

1. 新增 API 调用函数：
   - `fetchDiscoverFeed`
   - `compareProjectScore`
   - `fetchAssistantRecommend`

文件：`web/frontend/src/router/index.js`

1. 新增路由：`/discover`
2. 默认路由改为：`/ -> /discover`
3. 旧路由 `/chat` 重定向到 `/discover`

文件：`web/frontend/src/App.vue`

1. 更新发现入口导航，指向 `/discover`
2. 允许 `/discover` 使用独立页面渲染模式

### 3.3 测试

新增文件：`tests/test_discover_compare_api.py`

1. `test_discover_feed_returns_scored_items`
2. `test_compare_score_returns_ranked_rows`
3. `test_assistant_recommend_returns_decision`

## 4. 验证结果

1. 后端测试（llm 环境）：

```bash
conda run -n llm python -m pytest tests/test_discover_compare_api.py tests/test_dashboard_api.py tests/test_search_api.py -q
```

结果：`9 passed`

2. 前端构建：

```bash
npm.cmd run build
```

结果：构建成功，产物包含 `DiscoverView-*.js/css`

## 5. 效果评估

1. 已形成“发现 -> 对比 -> AI 建议”的可用闭环。
2. 推荐、对比、建议都基于同一评分结构，前后端一致性更高。
3. 对你的目标 UI 已完成第一阶段落地（信息架构与核心交互可用）。

## 6. 当前版本仍有不足

1. 评分模型是规则 + 启发式，尚未接入 Judge Agent 评审回合。
2. 风险识别主要依赖现有摘要/标签，尚未深挖 Issue/PR 证据链。
3. 助手建议为模板化策略，后续可升级为更强的上下文推理链。

## 7. 下一步建议

1. 引入 `Judge Agent`，对 Scout/Analyst 输出做证据门控与打分校准。
2. 增加项目对比导出（Markdown/PDF）与决策记录落库。
3. 增加维度权重配置（MVP/企业/研究三种策略模板）。
