# Eval Hardening（2026-04-20）

本次补强目标：

1. 扩展评测集（更难、更贴近真实）
2. 补人工质量闭环
3. 增加 rerank 实际生效稳定性指标
4. 增加可执行回归门禁

## 变更清单

- 新增增强评测集生成脚本：`scripts/build_manual_eval_set_v2.py`
- 新增评测集：`data/eval/manual_eval_set.v2.jsonl`（102 条）
- 增强评估脚本：`scripts/eval_rag_quality.py`
  - 支持字段：`query_type`、`hard_negative_repo_names`
  - 输出分层指标：`retrieval_by_query_type`
  - 输出 hard-negative 混淆率：`hard_negative_confusion`
  - 输出 rerank 实际生效率：`rerank_effective_rate` 与原因分布
  - 人工标注字段扩展：`manual_grounded`、`manual_citation_consistent`、`manual_best_repo`
  - 可回读人工标注统计：`manual_grounded_rate`、`manual_citation_consistent_rate`
- reranker 稳定性补强：`app/infrastructure/reranker.py`
  - 增加运行状态埋点：`last_run_used_cross_encoder`、`last_run_reason`、`stats`
  - 模型加载失败后启用会话级缓存降级，避免每次 query 重复超时加载
- 新增回归门禁：
  - `scripts/check_eval_regression.py`
  - `scripts/run_eval_gate.ps1`
- 新增人工标注流程文档：`docs/eval/manual_quality_workflow.md`

