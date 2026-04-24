# 推荐字段来源审查（2026-04-20）

本次审查字段：

- `summary`
- `reasons`
- `keywords`
- `tech_stack`
- `use_cases`

## 1. 字段来源结论

1. `summary` / `reasons`
- 一级来源：`EditorAgent` 产出的 `report.summary` 与 `report.reasons`。
- 汇总位置：`app/analysis/agents/orchestrator.py::_create_final_result`。
- 降级来源：`_create_fallback_result` 中调用 `editor._generate_report(...)` 的结果。

2. `keywords` / `tech_stack` / `use_cases`
- 一级来源：`app/analysis/structured_tags.py::extract_structured_tags`。
- 输入材料：
  - `summary`、`reasons`
  - `raw_readme_content`（优先）或清洗后 README
  - `repo_data`（language/topics）
  - `scout_data.community_sentiment.key_topics`
- 汇总位置：`app/analysis/agents/orchestrator.py`，在最终结果返回前统一附加。

## 2. 存储与读取链路

1. 写入：
- `Summarizer` 将上述字段写入 `AnalysisCache.set(...)`。
- 搜索索引阶段写入：
  - repo 级：`AnalysisCache.set_with_embedding(...)`
  - chunk 级：`AnalysisCache.replace_chunks(...)`

2. 读取：
- `AnalysisCache.get(...)` / `get_embedding(...)` / `get_all_embeddings(...)` / `get_all_chunks(...)` 返回这些字段。
- `SearchService` 聚合 chunk 时合并并截断 `keywords` / `tech_stack` / `use_cases`。

## 3. 对外返回链路

1. 搜索 API：
- `web/backend/routers/api.py::/api/search` 从 `SearchService.search_projects(...)` 映射到 `SearchResult`。
- `web/backend/models.py::SearchResult` 暴露 `keywords` / `tech_stack` / `use_cases`。

2. Dashboard API：
- `web/backend/routers/api.py::/api/dashboard` 从 `AnalysisCache.get(...)` 读取并返回这些字段（`ProjectCard`）。

## 4. 风险与本次修复点

1. 旧 SQLite 库缺列风险
- 旧库可能没有 `keywords` / `tech_stack` / `use_cases` 等列。
- 本次已在 `AnalysisCache._init_db()` 中补充 `ALTER TABLE` 兼容迁移。

2. 最终汇总分支一致性风险
- 之前 fallback 结果未统一附加结构化字段。
- 本次已在 `AgentOrchestrator.analyze_project()` 对成功结果统一附加这些字段。
