import re
from urllib.parse import urljoin
from typing import List, Dict


def build_multimodal_payload(
    cleaned_readme: str,
    repo_full_name: str,
    max_chars: int = 3000,
    max_images: int = 3
) -> List[Dict]:
    """
    将清洗后的 README 转换为 Qwen3-VL 接受的多模态 List 格式

    Args:
        cleaned_readme: 清洗后的 README 内容
        repo_full_name: 仓库全名 (如 "owner/repo")
        max_chars: 最大字符数限制
        max_images: 最大图片数量限制

    Returns:
        List[Dict]: 多模态 payload，包含 text 和 image_url 节点
    """
    # 按双换行符把文章分割成自然段 (Block)
    blocks = cleaned_readme.split('\n\n')

    payload = []
    current_text_buffer = ""
    char_count = 0
    image_count = 0

    # 匹配 Markdown 图片 ![alt](url) 和 HTML 图片 <img src="url">
    md_img_pattern = re.compile(r'!\[.*?\]\((.*?)\)')
    html_img_pattern = re.compile(r'<img[^>]+src=["\'](.*?)["\']', re.IGNORECASE)

    # 构造 GitHub Raw 文件的基础 URL，用于解决相对路径问题
    # 使用 HEAD 会自动指向默认分支 (main 或 master)
    raw_base_url = f"https://raw.githubusercontent.com/{repo_full_name}/HEAD/"

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # 尝试提取图片 URL
        img_url = None
        md_match = md_img_pattern.search(block)
        html_match = html_img_pattern.search(block)

        if md_match:
            img_url = md_match.group(1)
        elif html_match:
            img_url = html_match.group(1)

        # 如果这个段落是一张图片
        if img_url:
            if image_count >= max_images:
                continue  # 图片额度用完了，直接跳过后续图片

            # 处理相对路径，将其转换为绝对路径
            if not img_url.startswith(('http://', 'https://')):
                # 过滤掉 base64 图片（极其消耗 token）
                if img_url.startswith('data:image'):
                    continue
                # 拼接绝对路径
                img_url = urljoin(raw_base_url, img_url)

            # 把之前攒的纯文本先推入 payload
            if current_text_buffer.strip():
                payload.append({"type": "text", "text": current_text_buffer.strip()})
                current_text_buffer = ""  # 清空缓存

            # 推入图片节点
            payload.append({
                "type": "image_url",
                "image_url": {"url": img_url}
            })
            image_count += 1

        # 如果这个段落是普通文本 / 代码块
        else:
            # 检查加上这段文字后，是否会超出总字数限制
            if char_count + len(block) > max_chars:
                # 超出限制，截断当前段落，塞入缓存，然后结束整个循环
                remaining_space = max_chars - char_count
                if remaining_space > 50:  # 留点余量，太短就不要了
                    current_text_buffer += "\n\n" + block[:remaining_space] + "...\n(由于长度限制，后续内容已截断)"
                break
            else:
                current_text_buffer += "\n\n" + block
                char_count += len(block)

    # 循环结束后，不要忘了把最后一点文字推入 payload
    if current_text_buffer.strip():
        payload.append({"type": "text", "text": current_text_buffer.strip()})

    return payload


def payload_to_string(payload: List[Dict]) -> str:
    """
    将多模态 payload 转换为纯文本（用于不支持多模态的模型）

    Args:
        payload: 多模态 payload

    Returns:
        str: 纯文本内容（图片会被替换为 [图片: url]）
    """
    parts = []
    for item in payload:
        if item["type"] == "text":
            parts.append(item["text"])
        elif item["type"] == "image_url":
            parts.append(f"\n[图片: {item['image_url']['url']}]\n")
    return "".join(parts)
