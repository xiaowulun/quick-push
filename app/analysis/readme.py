import re
from typing import List

BLACKLIST_TITLES = {
    "installation", "install", "quick start", "getting started", 
    "documentation", "docs", "license", "changelog", "change log", 
    "faq", "support", "contact", "authors", "acknowledgments", 
    "credits", "code of conduct", "roadmap", "about", "contributing"
}

RETRIEVAL_BLACKLIST_TITLES = {
    "license", "changelog", "change log",
    "authors", "acknowledgments", "acknowledgements", "credits",
    "code of conduct", "contributing", "sponsor", "sponsors", "funding"
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
        
        if _is_badge(line):
            i += 1
            continue
            
        clean_line = re.sub(r'</?(?!img)[^>]+>', '', line)
        if not clean_line and line:
            i += 1
            continue
            
        if clean_line.startswith('#'):
            header_level = len(clean_line) - len(clean_line.lstrip('#'))
            header_text = clean_line.lstrip('#').strip()
            header_text_clean = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', header_text).lower()
            
            if any(black_word in header_text_clean for black_word in BLACKLIST_TITLES):
                i = _skip_section(lines, i, header_level)
                continue

        result_lines.append(clean_line)
        i += 1

    final_text = '\n'.join(result_lines)
    final_text = re.sub(r'\n{3,}', '\n\n', final_text)
    
    return final_text


def clean_readme_for_retrieval(content: str, max_code_lines: int = 40) -> str:
    """
    面向检索的 README 清洗。
    与多模态清洗不同，这里会保留 install/quick start/usage 等高价值信息。
    """
    if not content:
        return ""

    lines = content.split("\n")
    result_lines = []
    i = 0
    in_code_block = False
    code_line_count = 0

    while i < len(lines):
        line = lines[i].rstrip("\r")
        stripped = line.strip()

        if _is_badge(stripped):
            i += 1
            continue

        if stripped.startswith("```"):
            in_code_block = not in_code_block
            code_line_count = 0
            result_lines.append(stripped)
            i += 1
            continue

        if in_code_block:
            if code_line_count < max_code_lines:
                result_lines.append(line)
            code_line_count += 1
            i += 1
            continue

        clean_line = re.sub(r'</?(?!img)[^>]+>', '', line).strip()
        clean_line = re.sub(r'!\[[^\]]*\]\([^\)]+\)', '', clean_line).strip()
        clean_line = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', clean_line)

        if not clean_line and stripped:
            i += 1
            continue

        if clean_line.startswith('#'):
            header_level = len(clean_line) - len(clean_line.lstrip('#'))
            header_text = clean_line.lstrip('#').strip()
            header_text_clean = header_text.lower()

            if any(word in header_text_clean for word in RETRIEVAL_BLACKLIST_TITLES):
                i = _skip_section(lines, i, header_level)
                continue

        result_lines.append(clean_line)
        i += 1

    final_text = "\n".join(result_lines)
    final_text = re.sub(r'\n{3,}', '\n\n', final_text)
    return final_text.strip()


def split_readme_sections_for_retrieval(content: str) -> List[dict]:
    """按 Markdown 标题切分 README 段落，供 chunk 构建使用。"""
    if not content:
        return []

    lines = content.splitlines()
    sections: List[dict] = []
    current_title = "README"
    current_lines: List[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            if current_lines:
                text = "\n".join(current_lines).strip()
                if text:
                    sections.append({"section": current_title, "text": text})
            current_title = stripped.lstrip("#").strip() or "Untitled"
            current_lines = []
            continue

        current_lines.append(line)

    if current_lines:
        text = "\n".join(current_lines).strip()
        if text:
            sections.append({"section": current_title, "text": text})

    return sections

def _is_badge(line: str) -> bool:
    line_lower = line.lower()
    for domain in BADGE_DOMAINS:
        if domain in line_lower:
            return True
        try:
            if re.search(domain, line_lower):
                return True
        except re.error:
            pass
            
    if '![build]' in line_lower or '![ci]' in line_lower:
        return True
        
    return False

def _skip_section(lines: List[str], start_idx: int, header_level: int) -> int:
    i = start_idx + 1
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#'):
            next_level = len(line) - len(line.lstrip('#'))
            if next_level <= header_level:
                break
        i += 1
    return i
