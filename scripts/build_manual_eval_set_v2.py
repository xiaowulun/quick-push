import json
from pathlib import Path
from typing import Dict, List


def build_items() -> List[Dict]:
    repos = [
        {
            "repo": "EvoMap/evolver",
            "keywords": ["agent", "进化", "gep"],
            "domain": "让 AI 智能体持续自我进化",
            "negative": "NousResearch/hermes-agent",
        },
        {
            "repo": "HKUDS/DeepTutor",
            "keywords": ["deeptutor", "个性化", "学习"],
            "domain": "个性化 AI 家教与学习辅导",
            "negative": "thedotmack/claude-mem",
        },
        {
            "repo": "NousResearch/hermes-agent",
            "keywords": ["hermes-agent", "长期记忆", "技能"],
            "domain": "可成长的通用 AI 助手",
            "negative": "EvoMap/evolver",
        },
        {
            "repo": "OpenBMB/VoxCPM",
            "keywords": ["voxcpm", "语音", "波形"],
            "domain": "直接建模波形的语音生成",
            "negative": "google-ai-edge/gallery",
        },
        {
            "repo": "TapXWorld/ChinaTextbook",
            "keywords": ["chinatextbook", "教材", "k16"],
            "domain": "海外华人教育教材资源库",
            "negative": "microsoft/markitdown",
        },
        {
            "repo": "TheCraigHewitt/seomachine",
            "keywords": ["seomachine", "seo", "博客"],
            "domain": "长尾 SEO 内容自动化工作流",
            "negative": "addyosmani/agent-skills",
        },
        {
            "repo": "addyosmani/agent-skills",
            "keywords": ["agent-skills", "spec", "plan"],
            "domain": "AI 编码技能与命令化流程",
            "negative": "forrestchang/andrej-karpathy-skills",
        },
        {
            "repo": "coleam00/Archon",
            "keywords": ["archon", "yaml", "编排"],
            "domain": "YAML 驱动的 AI 编码编排",
            "negative": "multica-ai/multica",
        },
        {
            "repo": "forrestchang/andrej-karpathy-skills",
            "keywords": ["karpathy", "claude.md", "skills"],
            "domain": "Karpathy 原则的 Claude 规范模板",
            "negative": "addyosmani/agent-skills",
        },
        {
            "repo": "google-ai-edge/gallery",
            "keywords": ["google-ai-edge", "gemma", "端侧"],
            "domain": "端侧本地运行模型展示",
            "negative": "OpenBMB/VoxCPM",
        },
        {
            "repo": "lsdefine/GenericAgent",
            "keywords": ["genericagent", "技能树", "自演进"],
            "domain": "可自演进技能树的通用智能体",
            "negative": "EvoMap/evolver",
        },
        {
            "repo": "microsoft/markitdown",
            "keywords": ["markitdown", "markdown", "rag"],
            "domain": "文档转 Markdown 的 RAG 预处理",
            "negative": "TapXWorld/ChinaTextbook",
        },
        {
            "repo": "multica-ai/andrej-karpathy-skills",
            "keywords": ["karpathy", "multica", "claude.md"],
            "domain": "面向 Multica 的 Karpathy 编码规范",
            "negative": "forrestchang/andrej-karpathy-skills",
        },
        {
            "repo": "multica-ai/multica",
            "keywords": ["multica", "代理", "协作"],
            "domain": "多 AI 代理托管协作平台",
            "negative": "coleam00/Archon",
        },
        {
            "repo": "shiyu-coder/Kronos",
            "keywords": ["kronos", "ohlcv", "金融"],
            "domain": "金融 K 线时间序列基础模型",
            "negative": "virattt/ai-hedge-fund",
        },
        {
            "repo": "thedotmack/claude-mem",
            "keywords": ["claude-mem", "记忆", "claude"],
            "domain": "Claude Code 跨会话记忆",
            "negative": "HKUDS/DeepTutor",
        },
        {
            "repo": "virattt/ai-hedge-fund",
            "keywords": ["ai-hedge-fund", "投资", "多智能体"],
            "domain": "多智能体投资决策模拟",
            "negative": "shiyu-coder/Kronos",
        },
    ]

    rows: List[Dict] = []
    for cfg in repos:
        repo = cfg["repo"]
        k1, k2, k3 = cfg["keywords"]
        domain = cfg["domain"]
        negative = cfg["negative"]

        rows.append({
            "query": f"我在找一个可以{domain}的开源项目，最好直接可用。",
            "gold_chunk_ids": [],
            "gold_repo_names": [repo],
            "expected_keywords": [k1, k2, k3],
            "query_type": "direct",
            "hard_negative_repo_names": [],
        })
        rows.append({
            "query": f"有没有适合做“{domain}”的方案？我更看重工程落地。",
            "gold_chunk_ids": [],
            "gold_repo_names": [repo],
            "expected_keywords": [k1, k2, k3],
            "query_type": "paraphrase",
            "hard_negative_repo_names": [],
        })
        rows.append({
            "query": f"我们团队要做 PoC：{domain}。你会先推荐哪个仓库起步？",
            "gold_chunk_ids": [],
            "gold_repo_names": [repo],
            "expected_keywords": [k1, k2, k3],
            "query_type": "scenario",
            "hard_negative_repo_names": [],
        })
        rows.append({
            "query": f"需求约束：文档清晰、维护活跃、方向是{domain}，请给最匹配的项目。",
            "gold_chunk_ids": [],
            "gold_repo_names": [repo],
            "expected_keywords": [k1, k2, k3],
            "query_type": "constraint",
            "hard_negative_repo_names": [],
        })
        rows.append({
            "query": f"我在 {negative} 和另一个方案之间犹豫，但我的核心需求其实是{domain}，应该选哪个？",
            "gold_chunk_ids": [],
            "gold_repo_names": [repo],
            "expected_keywords": [k1, k2, k3],
            "query_type": "hard_negative",
            "hard_negative_repo_names": [negative],
        })
        rows.append({
            "query": f"想找一个“{k2} + {k3}”相关项目，优先能覆盖{domain}的。",
            "gold_chunk_ids": [],
            "gold_repo_names": [repo],
            "expected_keywords": [k1, k2, k3],
            "query_type": "ambiguous",
            "hard_negative_repo_names": [],
        })

    return rows


def main() -> int:
    rows = build_items()
    out = Path("data/eval/manual_eval_set.v2.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} rows to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

