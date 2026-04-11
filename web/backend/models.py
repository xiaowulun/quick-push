from pydantic import BaseModel
from typing import List, Optional


class ProjectCard(BaseModel):
    repo_name: str
    description: str
    summary: str
    reasons: List[str]
    stars: int
    stars_today: int
    language: str
    category: str
    url: str


class DashboardResponse(BaseModel):
    ai_ecosystem: List[ProjectCard]
    dev_tools: List[ProjectCard]
    infrastructure: List[ProjectCard]
    product_and_ui: List[ProjectCard]


class CategoryTrend(BaseModel):
    category: str
    count: int
    percentage: float


class LanguageTrend(BaseModel):
    language: str
    count: int
    percentage: float


class HotProject(BaseModel):
    repo_name: str
    appearances: int
    avg_rank: float
    last_seen: str
    category: Optional[str] = None


class TrendChart(BaseModel):
    date: str
    count: int


class TrendsResponse(BaseModel):
    period: str
    category_trends: List[CategoryTrend]
    language_trends: List[LanguageTrend]
    hot_projects: List[HotProject]
    total_projects: int
    total_records: int


class SearchResult(BaseModel):
    repo_full_name: str
    summary: str
    reasons: List[str]
    similarity: float
    category: Optional[str] = None
    language: Optional[str] = None
    stars: Optional[int] = None
    keywords: List[str] = []
    tech_stack: List[str] = []
    use_cases: List[str] = []


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    total: int


class ChatRequest(BaseModel):
    query: str
    top_k: int = 3
    threshold: float = 0.5


class ChatProject(BaseModel):
    repo_full_name: str
    summary: str
    similarity: float
    language: Optional[str] = None
    stars: Optional[int] = None
    url: str


class ChatResponse(BaseModel):
    answer: str
    projects: List[ChatProject]
    success: bool
