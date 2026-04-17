import os
import requests
from dotenv import load_dotenv

load_dotenv()


def run() -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is required")

    tests = [
        ("facebook/react", "A JavaScript library for building user interfaces"),
        ("microsoft/markitdown", "Python tool for converting files to Markdown"),
        ("awesome-python/awesome-python", "A curated list of awesome Python frameworks"),
    ]

    for repo, desc in tests:
        response = requests.post(
            "https://api.siliconflow.cn/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "Qwen/Qwen2.5-7B-Instruct",
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "Classify this repository and only output one-line JSON.\n"
                            f"repo: {repo}\n"
                            f"description: {desc}\n"
                            "choices: ai_ecosystem, infra_and_tools, product_and_ui, knowledge_base\n"
                            'format: {"category":"xxx","confidence":0.8,"reasoning":"xxx"}'
                        ),
                    }
                ],
                "max_tokens": 120,
                "temperature": 0.2,
            },
            timeout=30,
        )

        try:
            result = response.json()
        except ValueError:
            print(f"{repo}: invalid JSON response -> {response.text[:200]}")
            continue

        if "choices" in result:
            content = result["choices"][0]["message"]["content"]
            print(f"{repo}: {content.strip()}")
        else:
            print(f"{repo}: Error - {result}")


if __name__ == "__main__":
    run()
