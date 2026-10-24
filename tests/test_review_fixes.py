"""Regression tests for the 2026-10-24 code-review fixes (issues #1-#8).
Each test reproduces the reported scenario and asserts the fixed behavior."""

import json
import sqlite3
from datetime import datetime

import pytest
from typer.testing import CliRunner

from ai_job_radar.cli import app
from ai_job_radar.core.company_resolver import CompanyResolver
from ai_job_radar.core.deduplication import find_duplicate
from ai_job_radar.core.discovery import filter_companies
from ai_job_radar.export import export_json, export_markdown
from ai_job_radar.models import (
    Company,
    DimensionScore,
    Evidence,
    Job,
    JobStatus,
    JobType,
    SourceType,
)
from ai_job_radar.scoring.scorer import compute_score
from ai_job_radar.storage import database, repository as repo

RUNNER = CliRunner()


def _conn(tmp_path) -> sqlite3.Connection:
    return database.get_connection(tmp_path / "t.db")


# ---------------------------------------------------------------- #1

def test_reimport_merges_evidence_and_status(tmp_path):
    """重复导入命中去重时：新证据入库、状态变化写历史，而不是整条跳过。"""
    conn = _conn(tmp_path)
    repo.upsert_company(conn, Company(id="c", name="公司", city="北京"))
    conn.commit()
    first = [{"id": "j1", "company_id": "c", "title": "AI产品经理",
              "city": "北京", "source": "官网",
              "evidence": [{"source_type": "official", "url": "https://a",
                            "title": "官网岗"}]}]
    second = [{"id": "j1", "company_id": "c", "title": "AI产品经理",
               "city": "北京", "source": "官网", "status": "Closed",
               "evidence": [{"source_type": "media", "url": "https://b",
                             "title": "关闭报道"}]}]
    f1, f2 = tmp_path / "1.json", tmp_path / "2.json"
    f1.write_text(json.dumps(first, ensure_ascii=False), encoding="utf-8")
    f2.write_text(json.dumps(second, ensure_ascii=False), encoding="utf-8")
    db = str(tmp_path / "t.db")
    r1 = RUNNER.invoke(app, ["import-jobs", str(f1), "--db", db])
    r2 = RUNNER.invoke(app, ["import-jobs", str(f2), "--db", db])
    assert r1.exit_code == 0 and r2.exit_code == 0, (r1.output, r2.output)
    assert "去重合并 1" in r2.output
    job = repo.get_job(conn, "j1")
    assert job.status == JobStatus.CLOSED          # 新状态生效
    evs = repo.list_evidence(conn, "job", "j1")
    assert {e.url for e in evs} == {"https://a", "https://b"}  # 新证据保留
    hist = conn.execute(
        "SELECT status FROM job_status_history WHERE job_id='j1'").fetchall()
    assert any(h["status"] == "Closed" for h in hist)  # 状态历史可追溯


def test_reimport_fills_missing_fields(tmp_path):
    """去重合并时补全缺失字段（如 JD），不覆盖已有值。"""
    conn = _conn(tmp_path)
    repo.upsert_company(conn, Company(id="c", name="公司", city="北京"))
    repo.upsert_job(conn, Job(id="j1", company_id="c", title="AI产品经理",
                              city="北京", source="官网"))
    conn.commit()
    second = [{"id": "j1", "company_id": "c", "title": "AI产品经理",
               "city": "北京", "source": "官网", "salary_min": 30,
               "salary_max": 60, "jd": "负责 Agent 产品规划。"}]
    f2 = tmp_path / "2.json"
    f2.write_text(json.dumps(second, ensure_ascii=False), encoding="utf-8")
    r = RUNNER.invoke(app, ["import-jobs", str(f2), "--db", str(tmp_path / "t.db")])
    assert r.exit_code == 0 and "去重合并 1" in r.output
    job = repo.get_job(conn, "j1")
    assert job.jd == "负责 Agent 产品规划。" and job.salary_min == 30


# ---------------------------------------------------------------- #2

def test_same_title_different_job_type_not_dup():
    """同公司同城同名：实习 vs 正职是不同岗位，不得合并。"""
    a = Job(id="j1", company_id="c", title="AI产品经理", city="北京",
            source="BOSS直聘", job_type="intern")
    b = Job(id="j2", company_id="c", title="AI产品经理", city="北京",
            source="BOSS直聘", job_type="full_time")
    assert find_duplicate(b, [a]) is None


def test_same_source_job_id_is_dup():
    """同来源同职位 ID 是确定重复（即使标题措辞不同）。"""
    a = Job(id="j1", company_id="c", title="AI产品经理（急聘）", city="北京",
            source="BOSS直聘", source_job_id="B001")
    b = Job(id="j2", company_id="c", title="AI产品经理", city="北京",
            source="BOSS直聘", source_job_id="B001")
    assert find_duplicate(b, [a]) is a


# ---------------------------------------------------------------- #3

def test_company_merge_keeps_old_id_jobs_reachable(tmp_path):
    """公司合并进已有实体后：旧 ID 注册为别名，引用旧 ID 的岗位入库并归属正确。"""
    conn = _conn(tmp_path)
    db = str(tmp_path / "t.db")
    repo.upsert_company(conn, Company(id="c", name="埃克米", city="北京",
                                      aliases=["Acme"]))
    conn.commit()
    new_co = [{"company": {"id": "new-c", "name": "Acme", "city": "北京"},
               "aliases": ["Acme Lab"]}]
    fc = tmp_path / "c.json"
    fc.write_text(json.dumps(new_co, ensure_ascii=False), encoding="utf-8")
    r = RUNNER.invoke(app, ["import-companies", str(fc), "--db", db])
    assert r.exit_code == 0 and "合并到已有实体 c" in r.output
    # 引用旧 ID 的岗位应解析到合并后实体并正常入库
    jobs = [{"id": "j9", "company_id": "new-c", "title": "算法工程师",
             "city": "北京", "source": "官网"}]
    fj = tmp_path / "j.json"
    fj.write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8")
    r2 = RUNNER.invoke(app, ["import-jobs", str(fj), "--db", db])
    assert r2.exit_code == 0 and "新增 1" in r2.output, r2.output
    job = repo.get_job(conn, "j9")
    assert job.company_id == "c"


def test_jobs_with_unknown_company_rejected(tmp_path):
    """无法关联公司的岗位被拒绝入库，不产生静默孤儿数据。"""
    conn = _conn(tmp_path)
    jobs = [{"id": "jx", "company_id": "ghost-co", "title": "岗位",
             "city": "北京", "source": "官网"}]
    fj = tmp_path / "j.json"
    fj.write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8")
    r = RUNNER.invoke(app, ["import-jobs", str(fj), "--db", str(tmp_path / "t.db")])
    assert r.exit_code == 0 and "公司缺失跳过 1" in r.output
    assert repo.get_job(conn, "jx") is None


# ---------------------------------------------------------------- #4

def test_job_timestamps_roundtrip(tmp_path):
    """first_seen_at / last_verified_at 存取不丢失。"""
    conn = _conn(tmp_path)
    repo.upsert_company(conn, Company(id="c", name="公司", city="北京"))
    seen = datetime(2025, 3, 1, 9, 30, 0)
    verified = datetime(2026, 10, 1, 8, 0, 0)
    repo.upsert_job(conn, Job(id="j1", company_id="c", title="岗位",
                              city="北京", source="官网",
                              first_seen_at=seen,
                              last_verified_at=verified))
    conn.commit()
    got = repo.get_job(conn, "j1")
    assert got.first_seen_at == seen
    assert got.last_verified_at == verified


# ---------------------------------------------------------------- #5

def _fake_client(html: str, status: int = 200):
    import ai_job_radar.core.verification as v

    class FakeResp:
        status_code = status
        text = html
        url = "https://example.com/job"

    class FakeClient:
        def __init__(self, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, url): return FakeResp()

    return v, v.httpx.Client, FakeClient


def test_verification_ignores_script_text(tmp_path):
    """脚本里的模板文案（如'职位已关闭'翻译串）不影响状态判断。"""
    html = ("<html><body><h1>开放平台产品经理</h1>"
            "<button>立即申请</button></body>"
            "<script>window.I18N={'closed':'职位已关闭'};</script></html>")
    v, orig, fake = _fake_client(html)
    v.httpx.Client = fake
    try:
        job = Job(id="j", company_id="c", title="开放平台产品经理",
                  city="北京", source="官网", source_url="https://x")
        status, note = v.check_job_url(job)
        assert status == JobStatus.VERIFIED_OPEN
    finally:
        v.httpx.Client = orig


def test_verification_generic_page_cta_not_verified_open(tmp_path):
    """跳转到通用招聘首页：有 Apply now 但页面并非该岗位 → 不判 Verified Open。"""
    html = ("<html><body><h1>Join Us</h1><a>Apply now</a>"
            "<h2>Backend Engineer</h2><h2>Data Analyst</h2></body></html>")
    v, orig, fake = _fake_client(html)
    v.httpx.Client = fake
    try:
        job = Job(id="j", company_id="c", title="开放平台产品经理",
                  city="北京", source="官网", source_url="https://x")
        status, note = v.check_job_url(job)
        assert status == JobStatus.LISTED_UNCONFIRMED
        assert "identity unconfirmed" in note
    finally:
        v.httpx.Client = orig


def test_verification_closed_with_identity(tmp_path):
    html = ("<html><body><h1>开放平台产品经理</h1>"
            "<p>该职位已关闭</p></body></html>")
    v, orig, fake = _fake_client(html)
    v.httpx.Client = fake
    try:
        job = Job(id="j", company_id="c", title="开放平台产品经理",
                  city="北京", source="官网", source_url="https://x")
        status, _ = v.check_job_url(job)
        assert status == JobStatus.CLOSED
    finally:
        v.httpx.Client = orig


# ---------------------------------------------------------------- #6

def test_export_includes_job_evidence(tmp_path):
    """岗位级证据随 JSON 与 Markdown 报告导出。"""
    conn = _conn(tmp_path)
    repo.upsert_company(conn, Company(id="c", name="公司", city="北京"))
    repo.upsert_job(conn, Job(id="j1", company_id="c", title="AI产品经理",
                              city="北京", source="官网"))
    repo.add_evidence(conn, Evidence(
        entity_type="job", entity_id="j1", source_type=SourceType.OFFICIAL,
        url="https://careers.example/j1", title="岗位页",
        retrieved_at=datetime(2026, 10, 23, 10, 0, 0)))
    conn.commit()
    jp = tmp_path / "r.json"
    export_json(conn, jp)
    data = json.loads(jp.read_text(encoding="utf-8"))
    job_entry = data[0]["jobs"][0]
    assert job_entry["job"]["id"] == "j1"
    assert job_entry["evidence"][0]["url"] == "https://careers.example/j1"
    mp = tmp_path / "r.md"
    export_markdown(conn, mp)
    md = mp.read_text(encoding="utf-8")
    assert "#### 岗位来源" in md and "careers.example/j1" in md
    # A posting URL is still directly reachable when no Evidence record was
    # provided, and Markdown punctuation in titles/URLs cannot break links.
    job = repo.get_job(conn, "j1")
    job.title = "AI[产品]经理"
    job.source_url = "https://careers.example/job(1)?city=北京"
    repo.upsert_job(conn, job)
    export_markdown(conn, mp)
    md = mp.read_text(encoding="utf-8")
    assert r"[AI\[产品\]经理](https://careers.example/job%281%29?city=%E5%8C%97%E4%BA%AC)" in md


# ---------------------------------------------------------------- #7

def test_hiring_only_excludes_all_closed(tmp_path):
    """唯一岗位已 Closed 的公司不算'在招'。"""
    conn = _conn(tmp_path)
    repo.upsert_company(conn, Company(id="c1", name="全关公司", city="北京"))
    repo.upsert_company(conn, Company(id="c2", name="在招公司", city="北京"))
    j = Job(id="j1", company_id="c1", title="岗位", city="北京", source="官网")
    j.status = JobStatus.CLOSED
    repo.upsert_job(conn, j)
    repo.upsert_job(conn, Job(id="j2", company_id="c2", title="岗位",
                              city="北京", source="官网"))
    conn.commit()
    ids = [c.id for c in filter_companies(conn, hiring_only=True)]
    assert "c1" not in ids and "c2" in ids


# ---------------------------------------------------------------- #8

def test_score_out_of_range_rejected():
    with pytest.raises(Exception):
        DimensionScore(dimension="funding", score=100)


def test_duplicate_dimensions_rejected():
    dims = [DimensionScore(dimension="funding", score=8.0),
            DimensionScore(dimension="funding", score=9.0)]
    with pytest.raises(ValueError, match="重复评分维度"):
        compute_score("c", dims)


def test_invalid_weights_rejected():
    with pytest.raises(ValueError, match="权重配置无效"):
        compute_score("c", [DimensionScore(dimension="funding", score=8.0)],
                      weights={"funding": 0.25, "founders": 0.25,
                               "team": 0.15, "product": 0.25, "hiring": 0})
