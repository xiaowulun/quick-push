import json
import httpx
from dataclasses import dataclass
from typing import List
from utils.logging_config import get_logger
from core.config import get_config

logger = get_logger(__name__)


@dataclass
class TrendingMessage:
    repo_name: str
    description: str
    url: str
    stars: int
    stars_today: int
    language: str
    summary: str
    reasons: list[str]


class Notifier:
    def __init__(self, mode: str = "print"):
        self.mode = mode

    def send(self, messages: List[TrendingMessage], title: str = "GitHub 热门项目日报"):
        if self.mode == "feishu":
            self._send_to_feishu(messages, title)
        else:
            self._print_messages(messages, title)

    def send_failure_report(self, failure_items: List[tuple], title: str = "GitHub 热门项目日报"):
        if self.mode == "feishu":
            self._send_failure_to_feishu(failure_items, title)
        else:
            self._print_failure_report(failure_items, title)

    def _print_failure_report(self, failure_items: List[tuple], title: str):
        print(f"\n{'='*60}")
        print(f"⚠️ 以下项目分析失败（不影响阅读）：")
        print(f"{'='*60}\n")

        for i, (repo, analysis) in enumerate(failure_items, 1):
            print(f"【{i}】{repo.full_name}")
            print(f"  原因: {analysis.get('reasons', ['未知'])[0]}")
            print(f"  链接: {repo.url}")
            print()

    def _send_failure_to_feishu(self, failure_items: List[tuple], title: str):
        config = get_config()

        if not config.is_feishu_configured():
            self._print_failure_report(failure_items, title)
            return

        token = self._get_access_token(config)
        if not token:
            self._print_failure_report(failure_items, title)
            return

        content = self._build_failure_content(failure_items, title)
        self._send_message(config, token, content)

    def _build_failure_content(self, failure_items: List[tuple], title: str) -> str:
        content_lines = [
            {"tag": "text", "text": f"⚠️ 以下项目分析失败（不影响阅读）：\n\n"}
        ]

        for i, (repo, analysis) in enumerate(failure_items, 1):
            reason = analysis.get('reasons', ['未知'])[0]
            project_block = [
                {"tag": "text", "text": f"━━━━━━━━━━━━━━━━━━━━\n"},
                {"tag": "text", "text": f"【{i}】{repo.full_name}\n"},
                {"tag": "text", "text": f"原因: {reason}\n"},
                {"tag": "a", "text": "查看项目", "href": repo.url},
                {"tag": "text", "text": "\n"}
            ]
            content_lines.extend(project_block)

        post_content = {
            "zh_cn": {
                "title": title,
                "content": [content_lines]
            }
        }

        return json.dumps(post_content, ensure_ascii=False)

    def _build_card_content(self, messages: List[TrendingMessage], title: str) -> dict:
        """构建飞书卡片消息内容"""
        elements = []

        # 标题头
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**📊 {title}**\n共 {len(messages)} 个热门项目"
            }
        })

        # 分隔线
        elements.append({"tag": "hr"})

        for i, msg in enumerate(messages, 1):
            stars_str = self._format_stars(msg.stars)
            today_str = f"+{msg.stars_today}" if msg.stars_today else "0"

            # 项目名称和排名
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**#{i}** [{msg.repo_name}]({msg.url})"
                }
            })

            # Star 数和语言
            lang_str = f" | 🌐 {msg.language}" if msg.language else ""
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"⭐ {stars_str} (今日 {today_str}){lang_str}"
                }
            })

            # 项目简介
            if msg.description:
                desc = msg.description[:80] + "..." if len(msg.description) > 80 else msg.description
                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"💡 {desc}"
                    }
                })

            # 项目分析
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**📝 项目分析**\n{msg.summary}"
                }
            })

            # 爆火原因
            reasons_text = "\n".join([f"• {reason}" for reason in msg.reasons])
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**🔥 爆火原因**\n{reasons_text}"
                }
            })

            # 操作按钮
            elements.append({
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {
                            "tag": "plain_text",
                            "content": "🔗 查看项目"
                        },
                        "type": "primary",
                        "url": msg.url
                    }
                ]
            })

            # 分隔线（除了最后一个）
            if i < len(messages):
                elements.append({"tag": "hr"})

        card_content = {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "template": "blue",
                "title": {
                    "tag": "plain_text",
                    "content": title
                }
            },
            "elements": elements
        }

        return card_content

    def _print_messages(self, messages: List[TrendingMessage], title: str):
        print(f"\n{'='*60}")
        print(f"📊 {title}")
        print(f"{'='*60}")
        print(f"共 {len(messages)} 个热门项目\n")

        for i, msg in enumerate(messages, 1):
            stars_str = self._format_stars(msg.stars)
            today_str = f"+{msg.stars_today}" if msg.stars_today else "0"
            print(f"【{i}】{msg.repo_name}")
            print(f"⭐ {stars_str} (今日 +{today_str}) | {msg.language or 'N/A'} | {msg.url}")
            print(f"简介: {msg.description or '无'}")
            print(f"\n📝 项目分析:\n{msg.summary}")
            print(f"\n🔥 爆火原因:")
            for reason in msg.reasons:
                print(f"  • {reason}")
            print("-" * 60)

    def _format_stars(self, stars: int) -> str:
        if stars >= 10000:
            return f"{stars/10000:.1f}万"
        elif stars >= 1000:
            return f"{stars/1000:.1f}k"
        return str(stars)

    def _send_to_feishu(self, messages: List[TrendingMessage], title: str = "GitHub 热门项目日报"):
        config = get_config()

        if not config.is_feishu_configured():
            logger.warning("飞书配置不完整，切换为打印模式")
            self._print_messages(messages, title)
            return

        token = self._get_access_token(config)
        if not token:
            logger.warning("获取飞书 access_token 失败，切换为打印模式")
            self._print_messages(messages, title)
            return

        card_content = self._build_card_content(messages, title)
        self._send_card_message(config, token, card_content)

    def _get_access_token(self, config) -> str:
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        try:
            response = httpx.post(
                url,
                json={"app_id": config.feishu.app_id, "app_secret": config.feishu.app_secret},
                timeout=10.0
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    return data["tenant_access_token"]
        except httpx.RequestError as e:
            logger.error(f"获取飞书 access_token 请求失败: {e}")
        except Exception as e:
            logger.error(f"获取飞书 access_token 异常: {e}")
        return ""

    def _send_message(self, config, token: str, content: str):
        url = "https://open.feishu.cn/open-apis/im/v1/messages"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        params = {"receive_id_type": config.feishu.receive_id_type}

        body = {
            "receive_id": config.feishu.receive_id,
            "msg_type": "post",
            "content": content
        }

        try:
            response = httpx.post(url, headers=headers, params=params, json=body, timeout=30.0)
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    logger.info("飞书消息发送成功")
                else:
                    logger.error(f"飞书消息发送失败: {data.get('msg')}")
            else:
                logger.error(f"飞书请求失败: {response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"飞书消息发送请求失败: {e}")
        except Exception as e:
            logger.error(f"飞书消息发送异常: {e}")

    def _send_card_message(self, config, token: str, card_content: dict):
        """发送卡片消息"""
        url = "https://open.feishu.cn/open-apis/im/v1/messages"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        params = {"receive_id_type": config.feishu.receive_id_type}

        body = {
            "receive_id": config.feishu.receive_id,
            "msg_type": "interactive",
            "content": json.dumps(card_content, ensure_ascii=False)
        }

        try:
            response = httpx.post(url, headers=headers, params=params, json=body, timeout=30.0)
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    logger.info("飞书卡片消息发送成功")
                else:
                    logger.error(f"飞书卡片消息发送失败: {data.get('msg')}")
            else:
                logger.error(f"飞书卡片请求失败: {response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"飞书卡片消息发送请求失败: {e}")
        except Exception as e:
            logger.error(f"飞书卡片消息发送异常: {e}")

    def _build_post_content(self, messages: List[TrendingMessage], title: str) -> str:
        content_lines = [
            {"tag": "text", "text": f"📊 {title}\n"},
            {"tag": "text", "text": f"共 {len(messages)} 个热门项目\n\n"}
        ]

        for i, msg in enumerate(messages, 1):
            stars_str = self._format_stars(msg.stars)
            today_str = f"+{msg.stars_today}" if msg.stars_today else "0"

            project_block = [
                {"tag": "text", "text": f"━━━━━━━━━━━━━━━━━━━━\n"},
                {"tag": "text", "text": f"【{i}】{msg.repo_name}\n"},
                {"tag": "text", "text": f"⭐ {stars_str} (今日 +{today_str})  |  "},
                {"tag": "a", "text": "查看项目", "href": msg.url},
                {"tag": "text", "text": "\n"}
            ]

            if msg.language:
                project_block.append({"tag": "text", "text": f"语言: {msg.language}\n"})

            if msg.description:
                desc = msg.description[:100] + "..." if len(msg.description) > 100 else msg.description
                project_block.append({"tag": "text", "text": f"简介: {desc}\n"})

            project_block.extend([
                {"tag": "text", "text": f"\n📝 项目分析:\n{msg.summary}\n\n"},
                {"tag": "text", "text": "🔥 爆火原因:\n"}
            ])

            for reason in msg.reasons:
                project_block.append({"tag": "text", "text": f"  • {reason}\n"})

            content_lines.extend(project_block)

        post_content = {
            "zh_cn": {
                "title": title,
                "content": [content_lines]
            }
        }

        return json.dumps(post_content, ensure_ascii=False)