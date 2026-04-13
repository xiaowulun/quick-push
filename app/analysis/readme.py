import re
from typing import List

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

def _is_badge(line: str) -> bool:
    line_lower = line.lower()
    for domain in BADGE_DOMAINS:
        if domain in line_lower:
            return True
            
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
