# 人工质量标注流程

## 1. 先导出待标注样本

```bash
conda run -n llm python scripts/eval_rag_quality.py \
  --eval-set data/eval/manual_eval_set.v2.jsonl \
  --max-eval-queries 60 \
  --top-k 10 \
  --baseline vector \
  --check-answers \
  --max-answer-queries 20 \
  --manual-off-topic-sample 20 \
  --manual-off-topic-output data/eval/manual_off_topic_sample.v2.20.jsonl \
  --output data/eval/eval_report.manual.v2.sample60.json
```

导出的 `manual_off_topic_sample` 每条会包含以下待填字段：

- `manual_off_topic`: `true/false`，回答是否答非所问
- `manual_grounded`: `true/false`，结论是否被给定证据支持
- `manual_citation_consistent`: `true/false`，引用和正文是否一致
- `manual_best_repo`: 手工认为更合适的 repo（可空）
- `manual_reason`: 备注原因

## 2. 标注建议

- 抽样量建议：至少 50 条（推荐 80-120 条）
- 双人抽样：同一批次随机抽 20 条双标，校准口径
- 判定优先级：
  1. 是否命中正确目标（off-topic）
  2. 是否证据充分（grounded）
  3. 引用是否对得上正文（citation consistency）

## 3. 回填后计算人工指标

```bash
conda run -n llm python scripts/eval_rag_quality.py \
  --manual-off-topic-only \
  --manual-off-topic-labeled data/eval/manual_off_topic_sample.v2.60.jsonl \
  --output data/eval/eval_report.manual.label.v2.json
```

输出会包含：

- `manual_off_topic_rate`
- `manual_grounded_rate`
- `manual_citation_consistent_rate`

## 4. 作为回归门禁输入

把人工标注结果并入候选报告后，使用回归脚本检查是否回归：

```bash
conda run -n llm python scripts/check_eval_regression.py \
  --baseline data/eval/eval_report.manual.2026-04-19.json \
  --candidate data/eval/eval_report.manual.v2.json \
  --min-recall-delta 0 \
  --min-hit1-delta 0 \
  --min-rerank-effective-rate 0.5
```
