import re
from typing import List

# 将黑名单全部转为小写，防止大小写匹配失败 (如 'quick start' vs 'Quick Start')
BLACKLIST_TITLES = {
    "installation", "install", "quick start", "getting started", 
    "documentation", "docs", "license", "changelog", "change log", 
    "faq", "support", "contact", "authors", "acknowledgments", 
    "credits", "code of conduct", "roadmap", "about", "contributing"
}

BADGE_DOMAINS = [
    'shields.io', 'badge.fury.io', 'github.com/.*?/workflows', 
    'img.shields.io', 'api.securityscorecards.dev', 'sonarcloud.io'
]

def clean_readme_for_multimodal(content: str) -> str:
    lines = content.split('\n')
    result_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        # 1. 过滤垃圾 Badge (保留有效的架构图/截图)
        if _is_badge(line):
            i += 1
            continue
            
        # 2. 清理 HTML 标签，但保留文本内容和 <img> 标签（<img> 可能也是重要图片）
        # 将 <div>文字</div> 变成 文字
        clean_line = re.sub(r'</?(?!img)[^>]+>', '', line)
        if not clean_line and line: # 如果清理后全空了（比如单纯的 <br>），则跳过
            i += 1
            continue
            
        # 3. 标题层级过滤机制 (黑名单过滤，不再区分 H2/H3，只要名字命中就干掉)
        if clean_line.startswith('#'):
            # 计算是几级标题
            header_level = len(clean_line) - len(clean_line.lstrip('#'))
            # 提取标题纯文本，去掉多余的 # 和可能的 Markdown 链接
            header_text = clean_line.lstrip('#').strip()
            header_text_clean = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', header_text).lower()
            
            # 检查是否命中黑名单
            if any(black_word in header_text_clean for black_word in BLACKLIST_TITLES):
                # 命中！跳过整个 section
                i = _skip_section(lines, i, header_level)
                continue

        # 如果活到了最后，说明是有效内容
        result_lines.append(clean_line)
        i += 1

    # 4. 合并多余的空行 (把连续的3个以上换行变成2个)
    final_text = '\n'.join(result_lines)
    final_text = re.sub(r'\n{3,}', '\n\n', final_text)
    
    return final_text

def _is_badge(line: str) -> bool:
    """只判断是否是垃圾徽章，绝不误杀正常图片"""
    line_lower = line.lower()
    # 检查是否包含已知的 badge 域名
    for domain in BADGE_DOMAINS:
        if domain in line_lower:
            return True
            
    # GitHub 原生的 workflow 徽章通常长这样: ![build](https://github.com/owner/repo/actions/...)
    if '![build]' in line_lower or '![ci]' in line_lower:
        return True
        
    return False

def _skip_section(lines: List[str], start_idx: int, header_level: int) -> int:
    """跳过逻辑保持不变，这是非常优雅的实现"""
    i = start_idx + 1
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#'):
            next_level = len(line) - len(line.lstrip('#'))
            # 如果遇到了同级或更高一级的标题，说明当前要跳过的 section 结束了
            if next_level <= header_level:
                break
        i += 1
    return i