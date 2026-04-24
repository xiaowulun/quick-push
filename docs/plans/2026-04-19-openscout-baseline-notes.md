# OpenScout Baseline Notes (2026-04-19)

## 1. 当前能力确认（基于代码现状）

### 1.1 搜索能力
- `app/knowledge/search.py` 当前链路：`chunk 召回 -> chunk 重排 -> repo 聚合`。
- 召回策略：`向量检索 + BM25` 混合检索，并对 query 做多路改写后做加权 RRF 融合。
- 精排策略：Cross-Encoder（可用时）；不可用时自动降级到融合结果。
- 聚合策略：按 repo 聚合 chunk，保留 `evidence_chunk / path / heading / chunk_id`，并做类别/语言多样性抑制。
- 过滤能力：支持 `language/category/min_stars/keywords/days`。

### 1.2 问答能力
- `app/knowledge/chat.py` 当前支持：
  - 技术问答与闲聊分流；
  - 检索增强问答（RAG）；
  - 低置信度降级回答；
  - 无匹配时的兜底回答；
  - 非流式 `/api/chat` 与 SSE 流式 `/api/chat/stream`；
  - 会话上下文与 follow-up 过滤器复用；
  - 引用标注与来源附录。

### 1.3 趋势能力
- `README.md` 与 `web/backend/routers/api.py` 显示：
  - `GET /api/dashboard`：按四大类返回看板卡片（去重后每类最多 10）。
  - `GET /api/trends`：按时间窗口聚合类别趋势、语言趋势、热门项目出现次数与平均排名。

## 2. 手工评测集

- 新增：`data/eval/manual_eval_set.jsonl`
- 规模：20 条真实中文 query（覆盖当前索引中的 17 个 repo，含重复场景）。
- 标注字段：
  - `query`
  - `gold_repo_names`
  - `gold_chunk_ids`（当前留空）
  - `expected_keywords`

## 3. 评估脚本调整

文件：`scripts/eval_rag_quality.py`

- 增加显式指标：
  - `hit_at_1_baseline`
  - `hit_at_1_candidate`
  - `hit_at_1_delta`
- `print_summary` 新增 Hit@1 输出。
- `load_eval_set` 增加 BOM 兼容（处理手工 JSONL 的 UTF-8 BOM）。

## 4. 离线评估命令与产物

执行环境：`llm`

```bash
conda run -n llm python scripts/eval_rag_quality.py \
  --eval-set data/eval/manual_eval_set.jsonl \
  --top-k 10 \
  --baseline vector \
  --check-answers \
  --max-answer-queries 20 \
  --manual-off-topic-sample 20 \
  --manual-off-topic-output data/eval/manual_off_topic_sample.manual.20.jsonl \
  --output data/eval/eval_report.manual.2026-04-19.json
```

产物：
- 评估报告：`data/eval/eval_report.manual.2026-04-19.json`
- 人工抽样：`data/eval/manual_off_topic_sample.manual.20.jsonl`

## 5. 本轮基线结果（2026-04-19）

### 5.1 检索效果
- Recall@10（baseline/vector）：`0.9000`
- Recall@10（candidate）：`1.0000`
- Recall@10 delta：`+0.1000`
- Hit@1（baseline/vector）：`0.7000`
- Hit@1（candidate）：`1.0000`
- Hit@1 delta：`+0.3000`

### 5.2 回答质量（脚本内置代理）
- 引用存在率：`1.0000`
- 引用有效率：`1.0000`
- 关键词答非所问（baseline）：`0.0000`
- 关键词答非所问（candidate）：`0.0000`

### 5.3 备注
- 运行中出现 `huggingface.co` 访问超时日志，Cross-Encoder 在部分情况下可能降级为融合结果（脚本有 fallback）。
- 本次结果可作为后续优化（query rewrite、rerank 稳定性、回答质量人工标注）的对照基线。
