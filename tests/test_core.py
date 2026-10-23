"""Tests for dedup, resolver, scoring and in-scope filtering."""

import sqlite3

from ai_job_radar.core.company_resolver import CompanyResolver
from ai_job_radar.core.deduplication import find_duplicate, jd_similarity
from ai_job_radar.export import in_scope
from ai_job_radar.models import Company, DimensionScore, Job
from ai_job_radar.scoring.scorer import compute_score
from ai_job_radar.storage import database, repository as repo


def _conn(tmp_path):
    return database.get_connection(tmp_path / "test.db")


def test_resolver_alias(tmp_path):
    conn = _conn(tmp_path)
    c = Company(id="moonshot", name="月之暗面", city="北京",
                aliases=["Moonshot AI", "Kimi"])
    repo.upsert_company(conn, c)
    r = CompanyResolver(conn)
    assert r.resolve("Moonshot AI") == "moonshot"
    assert r.resolve("月之暗面") == "moonshot"
    assert r.resolve("月之 暗面") == "moonshot"  # normalized
    assert r.resolve("完全无关公司") is None


def test_dedup_same_title(tmp_path):
    conn = _conn(tmp_path)
    repo.upsert_company(conn, Company(id="c1", name="公司甲", city="北京"))
    existing = [Job(id="j1", company_id="c1", title="AI 产品经理", city="北京",
                    source="BOSS直聘")]
    new = Job(id="j2", company_id="c1", title="AI产品经理", city="北京",
              source="猎聘")
    assert find_duplicate(new, existing) is not None


def test_dedup_different_company_not_dup(tmp_path):
    conn = _conn(tmp_path)
    existing = [Job(id="j1", company_id="c1", title="AI 产品经理", city="北京",
                    source="BOSS直聘")]
    new = Job(id="j2", company_id="c2", title="AI 产品经理", city="北京",
              source="猎聘")
    assert find_duplicate(new, existing) is None


def test_jd_similarity():
    a = "负责 AI Agent 平台的产品规划、路线图及落地结果"
    b = "负责 AI Agent 平台的产品规划、路线图及落地结果，深入理解业务"
    assert jd_similarity(a, b) > 0.6
    assert jd_similarity(a, "食堂厨师，负责切配") < 0.2


def test_scoring_missing_dims_not_zero():
    dims = [DimensionScore(dimension="funding", score=8.0, weight=0.25),
            DimensionScore(dimension="product", score=6.0, weight=0.25)]
    s = compute_score("c1", dims)
    # 权重归一化：(8*.25+6*.25)/(.5)=7，而不是把缺失维度当 0 分
    assert s.normalized_total == 7.0
    assert s.coverage == 0.5


def test_scoring_all_unknown_no_total():
    dims = [DimensionScore(dimension="funding", score=None, weight=0.25)]
    s = compute_score("c1", dims)
    assert s.normalized_total is None
    assert s.coverage == 0.0


def test_in_scope_china_only():
    assert in_scope(Job(id="j", company_id="c", title="t", city="北京", source="s"))
    assert not in_scope(Job(id="j", company_id="c", title="t", city="新加坡",
                            source="s"))
