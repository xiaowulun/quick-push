"""
GitHub 仓库数据获取工具

只负责一件事：通过 GitHub API 获取仓库原始数据
不做任何分析、评分或判断
"""

import aiohttp
import base64
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class GitHubRepoInspector:
    """仓库检查器 - 只获取原始数据，不做判断"""

    def __init__(self, token: Optional[str] = None):
        self.token = token
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            self.headers["Authorization"] = f"token {token}"

    async def _api_get(self, url: str) -> Optional[Any]:
        """调用 GitHub API"""
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers, timeout=15) as resp:
                if resp.status == 200:
                    return await resp.json()
                elif resp.status == 404:
                    return None
                else:
                    logger.warning(f"GitHub API {resp.status}: {url}")
                    return None

    async def _get_file_content(self, repo_name: str, path: str, max_lines: int = 50) -> Optional[str]:
        """获取文件内容（指定行数）"""
        url = f"https://api.github.com/repos/{repo_name}/contents/{path}"
        data = await self._api_get(url)

        if not data or "content" not in data:
            return None

        try:
            content = base64.b64decode(data["content"]).decode("utf-8")
            lines = content.split("\n")[:max_lines]
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"解码文件失败 {path}: {e}")
            return None

    async def get_directory_structure(self, repo_name: str, max_depth: int = 3) -> str:
        """获取格式化的目录树文本（直接可用于 LLM）"""
        url = f"https://api.github.com/repos/{repo_name}/git/trees/HEAD?recursive=1"
        data = await self._api_get(url)

        if not data or "tree" not in data:
            return f"{repo_name.split('/')[-1]}/\n(空仓库)"

        root = {"files": [], "directories": {}}

        for item in data["tree"]:
            path = item["path"]
            depth = path.count("/")

            if depth > max_depth:
                continue

            parts = path.split("/")
            current = root

            for part in parts[:-1]:
                if part not in current["directories"]:
                    current["directories"][part] = {"files": [], "directories": {}}
                current = current["directories"][part]

            if item["type"] == "blob":
                current["files"].append(parts[-1])

        return self._format_tree(root, repo_name.split('/')[-1] + "/")

    def _format_tree(self, structure: Dict, root_name: str, prefix: str = "", is_last: bool = True) -> str:
        """将嵌套结构格式化为树形文本"""
        lines = [root_name]

        files = structure.get("files", [])
        directories = list(structure.get("directories", {}).items())

        items = []
        for name, subdir in directories:
            items.append((name, subdir, True))
        for f in files:
            items.append((f, None, False))

        for i, (name, content, is_dir) in enumerate(items):
            is_last_item = (i == len(items) - 1)
            connector = "└── " if is_last_item else "├── "
            lines.append(f"{prefix}{connector}{name}{'/' if is_dir else ''}")

            if is_dir and content:
                extension = "    " if is_last_item else "│   "
                subdir_lines = self._format_tree(content, "", prefix + extension, is_last_item)
                lines.append(subdir_lines)

        return "\n".join(lines)

    async def get_key_files_content(self, repo_name: str) -> Dict[str, Any]:
        """获取关键文件内容（用于评估可运行性）"""
        result = {}

        readme_content = await self._get_file_content(repo_name, "README.md", max_lines=100)
        if readme_content:
            result["readme"] = readme_content
            result["readme_install_section"] = self._extract_install_section(readme_content)

        result["dockerfile"] = await self._get_file_content(repo_name, "Dockerfile", max_lines=30)
        result["docker_compose"] = await self._get_file_content(repo_name, "docker-compose.yml", max_lines=30)
        if not result["docker_compose"]:
            result["docker_compose"] = await self._get_file_content(repo_name, "docker-compose.yaml", max_lines=30)

        result["requirements"] = await self._get_file_content(repo_name, "requirements.txt", max_lines=50)
        result["pyproject"] = await self._get_file_content(repo_name, "pyproject.toml", max_lines=30)

        package_json_content = await self._get_file_content(repo_name, "package.json", max_lines=50)
        if package_json_content:
            result["package_json"] = package_json_content

        result["env_example"] = await self._get_file_content(repo_name, ".env.example", max_lines=20)

        result["makefile"] = await self._get_file_content(repo_name, "Makefile", max_lines=30)
        if not result["makefile"]:
            result["makefile"] = await self._get_file_content(repo_name, "makefile", max_lines=30)

        return result

    def _extract_install_section(self, readme: str) -> Optional[str]:
        """从 README 中提取安装部分"""
        lines = readme.split("\n")
        install_keywords = ["install", "setup", "getting started", "quick start", "安装", "部署"]

        start_idx = None
        for i, line in enumerate(lines):
            lower_line = line.lower()
            if any(kw in lower_line for kw in install_keywords):
                if line.strip().startswith(("#", "##", "###")):
                    start_idx = i
                    break

        if start_idx is None:
            return None

        end_idx = len(lines)
        current_level = lines[start_idx].count("#")

        for i in range(start_idx + 1, len(lines)):
            line = lines[i]
            if line.strip().startswith("#"):
                level = line.count("#")
                if level <= current_level:
                    end_idx = i
                    break

        return "\n".join(lines[start_idx:end_idx])

    async def get_issues(self, repo_name: str, limit: int = 20) -> List[Dict[str, Any]]:
        """获取最近的 Open Issues"""
        url = f"https://api.github.com/repos/{repo_name}/issues?state=open&per_page={limit}"
        data = await self._api_get(url)

        if not data:
            return []

        issues = []
        for item in data:
            if "pull_request" in item:
                continue

            issues.append({
                "title": item.get("title", ""),
                "body": item.get("body", "")[:500] if item.get("body") else "",
                "labels": [label["name"] for label in item.get("labels", [])],
                "comments_count": item.get("comments", 0),
                "created_at": item.get("created_at", ""),
                "url": item.get("html_url", "")
            })

        return issues

    async def inspect(self, repo_name: str) -> Dict[str, Any]:
        """完整检查 - 获取所有原始数据"""
        logger.info(f"[Inspector] 获取 {repo_name} 数据...")

        dir_task = self.get_directory_structure(repo_name, max_depth=3)
        files_task = self.get_key_files_content(repo_name)
        issue_task = self.get_issues(repo_name)

        dir_tree, key_files, issues = await asyncio.gather(
            dir_task, files_task, issue_task
        )

        return {
            "directory_tree": dir_tree,
            "key_files": key_files,
            "issues_text": self._format_issues(issues),
            "repo_name": repo_name
        }

    def _format_issues(self, issues: List[Dict]) -> str:
        """将 Issues 列表格式化为易读文本"""
        if not issues:
            return "无 Open Issues"

        lines = []
        for i, issue in enumerate(issues[:20], 1):
            title = issue.get("title", "")
            labels = ", ".join(issue.get("labels", [])) or "无标签"
            comments = issue.get("comments_count", 0)
            lines.append(f"{i}. [{labels}] {title} (评论: {comments})")

        return "\n".join(lines)


import asyncio


async def inspect_repository(repo_name: str, token: Optional[str] = None) -> Dict[str, Any]:
    """检查仓库的便捷函数"""
    inspector = GitHubRepoInspector(token)
    return await inspector.inspect(repo_name)
