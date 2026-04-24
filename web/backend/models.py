from pydantic import BaseModel, Field
from typing import List, Optional


class ProjectCard(BaseModel):
    repo_name: str
    description: str
    summary: str
    reasons: List[str]
    keywords: List[str] = Field(default_factory=list)
    tech_stack: List[str] = Field(default_factory=list)
    use_cases: List[str] = Field(default_factory=list)
    stars: int
    stars_today: int
    since_type: Optional[str] = None
    language: str
    category: str
    url: str


class DashboardResponse(BaseModel):
    ai_ecosystem: List[ProjectCard]
    infra_and_tools: List[ProjectCard]
    product_and_ui: List[ProjectCard]
    knowledge_base: List[ProjectCard]


class DashboardSummary(BaseModel):
    total_projects: int = 0
    today_projects: int = 0
    today_stars: int = 0


class DashboardTimelinePoint(BaseModel):
    date: str
    label: str
    stars_today: int
    projects: int
    total_projects: int = 0


class DashboardDistributionItem(BaseModel):
    name: str
    count: int
    percentage: float


class DashboardDecisionProject(BaseModel):
    repo_name: str
    category: str
    language: str
    stars: int
    stars_today: int
    appearances: int
    avg_rank: float
    last_seen: str
    url: str


class DashboardActivityItem(BaseModel):
    date: str
    type: str
    title: str
    detail: str


class DashboardInsightsResponse(BaseModel):
    period: str
    summary: DashboardSummary
    stars_timeline: List[DashboardTimelinePoint]
    category_distribution: List[DashboardDistributionItem]
    language_distribution: List[DashboardDistributionItem]
    decision_projects: List[DashboardDecisionProject]
    recent_activities: List[DashboardActivityItem]


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
    keywords: List[str] = Field(default_factory=list)
    tech_stack: List[str] = Field(default_factory=list)
    use_cases: List[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    total: int


class ProjectBasicInfo(BaseModel):
    repo_full_name: str
    url: str
    description: str = ""
    language: str = "Unknown"
    category: str = "infra_and_tools"
    stars: int = 0
    stars_today: int = 0
    rank: Optional[int] = None
    since_type: Optional[str] = None
    repo_updated_at: Optional[str] = None
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    total_appearances: int = 0


class ProjectEvidence(BaseModel):
    chunk_id: Optional[str] = None
    chunk_text: str = ""
    section: Optional[str] = None
    path: Optional[str] = None
    heading: Optional[str] = None
    updated_at: Optional[str] = None


class ProjectTrendHistoryPoint(BaseModel):
    record_date: str
    stars: int = 0
    stars_today: int = 0
    rank: Optional[int] = None
    since_type: Optional[str] = None
    language: Optional[str] = None
    category: Optional[str] = None


class ProjectTrendSummary(BaseModel):
    total_records: int = 0
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    best_rank: Optional[int] = None
    latest_stars: int = 0
    avg_stars_today: float = 0.0


class ProjectDetailResponse(BaseModel):
    basic: ProjectBasicInfo
    summary: str
    reasons: List[str]
    keywords: List[str] = Field(default_factory=list)
    tech_stack: List[str] = Field(default_factory=list)
    use_cases: List[str] = Field(default_factory=list)
    suitable_for: List[str] = Field(default_factory=list)
    complexity: str = "unknown"
    maturity: str = "unknown"
    risk_notes: List[str] = Field(default_factory=list)
    evidence: ProjectEvidence
    trend_summary: ProjectTrendSummary
    trend_history: List[ProjectTrendHistoryPoint] = Field(default_factory=list)


class ChatRequest(BaseModel):
    query: str
    top_k: int = 5
    session_id: Optional[str] = None
