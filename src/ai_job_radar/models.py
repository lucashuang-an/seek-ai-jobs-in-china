"""Pydantic data models for ai-job-radar.

All entities keep evidence (source + retrieval time). Timestamps for
posting / first-seen / last-verified are stored separately by design.
"""

from __future__ import annotations

from datetime import date, datetime
from datetime import date as Date  # avoid shadowing by field named `date`
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class CompanyType(str, Enum):
    STARTUP = "startup"
    BIGTECH_AI_TEAM = "bigtech_ai_team"
    FOREIGN_IN_CHINA = "foreign_in_china"


class JobStatus(str, Enum):
    VERIFIED_OPEN = "Verified Open"
    LISTED_UNCONFIRMED = "Listed / Unconfirmed"
    RECENTLY_SEEN = "Recently Seen"
    CLOSED = "Closed"
    UNKNOWN = "Unknown"


class JobType(str, Enum):
    FULL_TIME = "full_time"  # 社招正职
    INTERN = "intern"        # 实习（日常/暑期）
    CAMPUS = "campus"        # 校招（应届正职）


JOB_TYPE_LABELS = {
    JobType.FULL_TIME: "社招正职",
    JobType.INTERN: "实习",
    JobType.CAMPUS: "校招",
}


class SourceType(str, Enum):
    OFFICIAL = "official"          # 企业官方一手信息
    INVESTOR = "investor"          # 投资机构披露
    MEDIA = "media"                # 可信媒体报道
    JOB_PLATFORM = "job_platform"  # 招聘平台公开职位
    COMMUNITY = "community"        # 社区/个人公开讨论


class FactKind(str, Enum):
    VERIFIED = "verified"     # 已验证事实
    INFERRED = "inferred"     # 合理推断
    UNKNOWN = "unknown"       # 未知


class Track(str, Enum):
    FOUNDATION_MODELS = "Foundation Models"
    AI_AGENTS = "AI Agents"
    AI_APPLICATIONS = "AI Applications"
    AI_INFRASTRUCTURE = "AI Infrastructure"
    AI_DEVELOPER_TOOLS = "AI Developer Tools"
    AI_ROBOTICS = "AI Robotics"
    AI_ENTERPRISE_SOFTWARE = "AI Enterprise Software"


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

class Evidence(BaseModel):
    """A source reference attached to any fact."""
    id: str | None = None
    entity_type: str  # company | job | funding | founder | product | score
    entity_id: str
    source_type: SourceType
    url: str | None = None
    publisher: str | None = None
    title: str | None = None
    snippet: str | None = None
    published_at: date | None = None
    retrieved_at: datetime = Field(default_factory=datetime.now)
    trust_note: str | None = None


# ---------------------------------------------------------------------------
# Company
# ---------------------------------------------------------------------------

class Company(BaseModel):
    id: str  # stable Company ID (slug)
    name: str
    aliases: list[str] = []
    english_name: str | None = None
    website: str | None = None
    city: str  # 主要办公城市
    hq_location: str | None = None
    company_type: CompanyType = CompanyType.STARTUP
    tracks: list[Track] = []
    description: str | None = None
    funding_stage: str | None = None  # e.g. 天使轮/A轮/B轮/C轮/D轮及以上/战略投资/未披露
    team_size_min: int | None = None
    team_size_max: int | None = None
    hiring_signals: list[str] = []
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    last_verified_at: datetime | None = None


# ---------------------------------------------------------------------------
# Job
# ---------------------------------------------------------------------------

class Job(BaseModel):
    id: str
    company_id: str
    title: str
    city: str
    location_detail: str | None = None
    job_type: JobType | None = None  # 实习/校招/社招正职；None=未标注
    salary_min: int | None = None  # 月薪下限（K）；实习为日薪换算或不填
    salary_max: int | None = None  # 月薪上限（K）
    salary_months: int | None = None  # 薪月数，如 14 薪
    experience: str | None = None
    education: str | None = None
    jd: str | None = None
    source: str  # e.g. BOSS直聘 / 猎聘 / 官网 / Moka
    source_url: str | None = None
    source_job_id: str | None = None
    posted_at: date | None = None
    first_seen_at: datetime = Field(default_factory=datetime.now)
    last_verified_at: datetime | None = None
    status: JobStatus = JobStatus.RECENTLY_SEEN


# ---------------------------------------------------------------------------
# Research modules
# ---------------------------------------------------------------------------

class FundingEvent(BaseModel):
    id: str | None = None
    company_id: str
    date: Date | None = None
    round: str | None = None  # 未披露 -> None + note
    amount: str | None = None  # keep original text, e.g. "数千万人民币"
    currency: str | None = None
    investors: list[str] = []
    note: str | None = None


class Founder(BaseModel):
    id: str | None = None
    company_id: str
    name: str
    title: str | None = None
    education: str | None = None
    career: str | None = None
    relevant_experience: str | None = None
    previous_startups: str | None = None
    source_fact_kind: FactKind = FactKind.VERIFIED  # 官方介绍/第三方报道/AI推断


class Product(BaseModel):
    id: str | None = None
    company_id: str
    name: str
    website: str | None = None
    positioning: str | None = None
    core_features: str | None = None
    target_users: str | None = None
    scenarios: str | None = None
    traction: str | None = None  # 公开用户和商业化信息


class TeamInfo(BaseModel):
    company_id: str
    size_min: int | None = None
    size_max: int | None = None
    stage_note: str | None = None  # 组织发展阶段
    expansion_signals: list[str] = []
    source_fact_kind: FactKind = FactKind.VERIFIED


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

SCORE_DIMENSIONS = ["funding", "founders", "team", "product", "hiring"]
DEFAULT_WEIGHTS = {
    "funding": 0.25,
    "founders": 0.25,
    "team": 0.15,
    "product": 0.25,
    "hiring": 0.10,
}


class DimensionScore(BaseModel):
    dimension: str
    # 0-10; None when evidence insufficient. Bounds enforced so a bad
    # agent-produced score fails at parse time instead of polluting totals.
    score: float | None = Field(None, ge=0, le=10)
    # Optional: compute_score() fills it from configs/scoring.yaml when absent,
    # so agent-produced score JSON only needs dimension + score.
    weight: float | None = None
    evidence_summary: str | None = None
    fact_kind: FactKind = FactKind.VERIFIED
    rationale: str | None = None


class CompanyScore(BaseModel):
    company_id: str
    dimensions: list[DimensionScore]
    coverage: float  # 已评分维度权重和 / 总权重
    normalized_total: float | None = None  # 权重归一化综合分
    computed_at: datetime = Field(default_factory=datetime.now)
    note: str | None = None
