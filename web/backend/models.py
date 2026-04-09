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
