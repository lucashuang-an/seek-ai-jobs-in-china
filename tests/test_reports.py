"""Regression tests for the V0.2 acceptance fixes: optional dimension
weights, markdown export over model objects, evidence timestamp
preservation, and Global Remote pending-verification handling."""

import sqlite3
from datetime import datetime

from ai_job_radar.export import (
    _md_table,
    export_markdown,
    in_scope,
    remote_pending,
)
from ai_job_radar.models import (
    DEFAULT_WEIGHTS,
    Company,
    DimensionScore,
    Evidence,
    FundingEvent,
    Job,
    JobStatus,
    SourceType,
)
from ai_job_radar.scoring.scorer import compute_score
from ai_job_radar.storage import database, repository as repo


def _conn(tmp_path) -> sqlite3.Connection:
    return database.get_connection(tmp_path / "test.db")


def _seed(conn, tmp_path):
    repo.upsert_company(conn, Company(
        id="acme", name="埃克米", city="北京", aliases=["Acme AI"],
        funding_stage="A轮"))
    repo.add_funding(conn, FundingEvent(
        company_id="acme", date="2025-06-01", round="A轮",
        amount="1亿美元", investors=["红杉"]))
    repo.add_evidence(conn, Evidence(
        entity_type="company", entity_id="acme",
        source_type=SourceType.MEDIA, url="https://example.com/a",
        title="报道|标题", snippet="含|竖线\n与换行",
        retrieved_at=datetime(2026, 10, 1, 12, 0, 0)))
    repo.upsert_job(conn, Job(
        id="acme-j1", company_id="acme", title="AI产品经理", city="北京",
        source="BOSS直聘", salary_min=30, salary_max=60))
    dims = [DimensionScore(dimension="funding", score=8.0),   # 无 weight
            DimensionScore(dimension="product", score=6.0)]
    score = compute_score("acme", dims)
    repo.save_score(conn, score)
    conn.commit()
    return score


def test_dimension_score_weight_optional():
    """Bug 1 regression: agent-produced score JSON omits weight; it must
    default from config instead of failing validation."""
    d = DimensionScore(dimension="funding", score=8.0)
    assert d.weight is None
    s = compute_score("c1", [d])
    assert d.weight == DEFAULT_WEIGHTS["funding"]
    assert s.normalized_total == 8.0 and s.coverage == 0.25


def test_compute_score_unknown_dimension_raises():
    import pytest
    with pytest.raises(ValueError, match="未知评分维度"):
        compute_score("c1", [DimensionScore(dimension="vibes", score=9.0)])


def test_export_markdown_full(tmp_path):
    """Bug 2 regression: markdown export must render evidence/funding as
    model objects and not crash on pipes/newlines in stored text."""
    conn = _conn(tmp_path)
    _seed(conn, tmp_path)
    out = tmp_path / "report.md"
    export_markdown(conn, out)
    text = out.read_text(encoding="utf-8")
    assert "## 埃克米" in text
    assert "### 融资历史" in text
    assert "1亿美元" in text
    assert "### 关键来源" in text and "example.com/a" in text
    assert "### 评分（证据驱动）" in text and "8.0" in text
    # 标题在链接中原样展示；表格内竖线转义由 _md_table 测试覆盖
    assert "[报道|标题](https://example.com/a)" in text
    # None 综合分显示为 "-"，不泄漏 Python None
    assert "None" not in text


def test_export_markdown_single_company_by_alias(tmp_path):
    conn = _conn(tmp_path)
    _seed(conn, tmp_path)
    repo.upsert_company(conn, Company(id="other", name="另一家", city="上海"))
    conn.commit()
    out = tmp_path / "single.md"
    export_markdown(conn, out, company="Acme AI")
    text = out.read_text(encoding="utf-8")
    assert "埃克米" in text and "另一家" not in text


def test_evidence_retrieved_at_preserved(tmp_path):
    """Spec: 检索时间必须保留，不得被 now() 静默替换。"""
    conn = _conn(tmp_path)
    _seed(conn, tmp_path)
    ev = repo.list_evidence(conn, "company", "acme")[0]
    assert ev.retrieved_at == datetime(2026, 10, 1, 12, 0, 0)


def test_company_timestamps_preserved(tmp_path):
    conn = _conn(tmp_path)
    created = datetime(2026, 1, 1, 9, 0, 0)
    repo.upsert_company(conn, Company(id="c1", name="公司一", city="北京",
                                      created_at=created))
    got = repo.get_company(conn, "c1")
    assert got.created_at == created
    got.last_verified_at = datetime(2026, 10, 22, 8, 0, 0)
    repo.upsert_company(conn, got)
    again = repo.get_company(conn, "c1")
    assert again.last_verified_at == datetime(2026, 10, 22, 8, 0, 0)


def test_remote_pending_jobs_kept_and_flagged(tmp_path):
    assert in_scope(Job(id="j", company_id="c", title="t",
                        city="全球远程", source="s"))
    assert remote_pending(Job(id="j", company_id="c", title="t",
                              city="Global Remote", source="s"))
    assert not in_scope(Job(id="j", company_id="c", title="t",
                            city="新加坡", source="s"))
    conn = _conn(tmp_path)
    repo.upsert_company(conn, Company(id="c", name="公司", city="北京"))
    job = Job(id="j1", company_id="c", title="Remote PM", city="全球远程",
              source="官网")
    job.status = JobStatus.UNKNOWN  # import-jobs 对待核验岗位的写法
    repo.upsert_job(conn, job)
    got = repo.get_job(conn, "j1")
    assert got.status == JobStatus.UNKNOWN


def test_job_type_field_and_filter(tmp_path):
    """job_type (实习/校招/社招正职) round-trips and filters."""
    from ai_job_radar.models import JobType
    conn = _conn(tmp_path)
    repo.upsert_company(conn, Company(id="c", name="公司", city="北京"))
    for jid, jt in [("j-intern", "intern"), ("j-campus", "campus"),
                    ("j-full", "full_time"), ("j-none", None)]:
        repo.upsert_job(conn, Job(id=jid, company_id="c", title=f"岗{jid}",
                                  city="北京", source="官网", job_type=jt))
    conn.commit()
    got = repo.get_job(conn, "j-intern")
    assert got.job_type == JobType.INTERN
    assert repo.get_job(conn, "j-none").job_type is None
    assert len(repo.list_jobs(conn, job_type="intern")) == 1
    assert len(repo.list_jobs(conn, job_type="campus")) == 1
    assert len(repo.list_jobs(conn, city="北京")) == 4


def test_job_type_migration_from_old_schema(tmp_path):
    """Old databases (pre-job_type) are upgraded in place on connect."""
    import sqlite3 as sq
    db = tmp_path / "old.db"
    raw = sq.connect(db)
    raw.executescript("""
        CREATE TABLE companies (id TEXT PRIMARY KEY, name TEXT NOT NULL,
            aliases TEXT DEFAULT '[]', english_name TEXT, website TEXT,
            city TEXT NOT NULL, hq_location TEXT, company_type TEXT DEFAULT 'startup',
            tracks TEXT DEFAULT '[]', description TEXT, funding_stage TEXT,
            team_size_min INTEGER, team_size_max INTEGER, hiring_signals TEXT DEFAULT '[]',
            created_at TEXT, updated_at TEXT, last_verified_at TEXT);
        CREATE TABLE jobs (id TEXT PRIMARY KEY, company_id TEXT NOT NULL,
            title TEXT NOT NULL, city TEXT NOT NULL, location_detail TEXT,
            salary_min INTEGER, salary_max INTEGER, salary_months INTEGER,
            experience TEXT, education TEXT, jd TEXT, source TEXT, source_url TEXT,
            source_job_id TEXT, posted_at TEXT, first_seen_at TEXT,
            last_verified_at TEXT, status TEXT DEFAULT 'Recently Seen');
        INSERT INTO jobs (id, company_id, title, city, source)
            VALUES ('legacy-1', 'c', '旧岗位', '北京', '官网');
    """)
    raw.commit()
    raw.close()
    conn = database.get_connection(db)          # triggers _migrate
    assert repo.get_job(conn, "legacy-1").job_type is None   # 旧数据不丢
    repo.upsert_job(conn, Job(id="new-1", company_id="c", title="新实习岗",
                              city="北京", source="官网",
                              job_type="intern"))
    conn.commit()
    assert repo.get_job(conn, "new-1").job_type is not None
    assert len(repo.list_jobs(conn, job_type="intern")) == 1


def test_md_table_escapes_pipes_and_newlines():
    table = _md_table([["a|b", "x\ny"]], ["h|1", "h2"])
    assert "a\\|b" in table and "x y" in table and "h\\|1" in table


def test_jd_similarity_empty_text_is_zero():
    """Regression: two jobs without JD text must not look identical."""
    from ai_job_radar.core.deduplication import jd_similarity
    assert jd_similarity(None, None) == 0.0
    assert jd_similarity("", "  ") == 0.0


def test_short_templated_jd_not_duplicate(tmp_path):
    """Regression: two distinct postings whose one-line template JDs score
    >=0.6 must stay separate — JD dedup only applies to substantive text."""
    from ai_job_radar.core.deduplication import find_duplicate, jd_similarity
    a = Job(id="j1", company_id="c", title="AI产品经理（消费医疗方向）",
            city="上海", source="猎聘",
            jd="美团 AI产品经理（消费医疗方向）：3-5年经验，本科，30-60k·15薪。")
    b = Job(id="j2", company_id="c", title="AI产品经理（大模型及商业策略算法方向）",
            city="上海", source="猎聘",
            jd="美团 AI产品经理（大模型及商业策略算法方向）：3-5年经验，本科，40-60k·15薪。")
    assert jd_similarity(a.jd, b.jd) >= 0.6   # 相似度本身高，但文本太短不可信
    assert find_duplicate(b, [a]) is None


def test_job_id_conflict_both_kept(tmp_path):
    """Regression: importing a different posting that reuses an existing job
    id must not overwrite the stored record; both survive with stable ids."""
    import json

    from typer.testing import CliRunner

    from ai_job_radar.cli import app

    conn = _conn(tmp_path)
    repo.upsert_company(conn, Company(id="mb", name="面壁", city="北京"))
    conn.commit()
    runner = CliRunner()
    first = [{"id": "mb-j1", "company_id": "mb", "title": "岗位A",
              "city": "北京", "source": "官网"}]
    second = [{"id": "mb-j1", "company_id": "mb", "title": "岗位B",
               "city": "北京", "source": "官网"}]
    f1 = tmp_path / "j1.json"
    f2 = tmp_path / "j2.json"
    f1.write_text(json.dumps(first, ensure_ascii=False), encoding="utf-8")
    f2.write_text(json.dumps(second, ensure_ascii=False), encoding="utf-8")
    r1 = runner.invoke(app, ["import-jobs", str(f1), "--db", str(tmp_path / "t.db")])
    r2 = runner.invoke(app, ["import-jobs", str(f2), "--db", str(tmp_path / "t.db")])
    assert r1.exit_code == 0 and r2.exit_code == 0
    assert "新增 1" in r2.output and "id 冲突改写 1" in r2.output
    jobs = repo.list_jobs(conn if False else database.get_connection(
        tmp_path / "t.db"))
    titles = sorted(j.title for j in jobs)
    assert titles == ["岗位A", "岗位B"]
    # 重复导入第二次：改写后的 id 稳定，内容去重生效，不再新增
    r3 = runner.invoke(app, ["import-jobs", str(f2), "--db", str(tmp_path / "t.db")])
    assert "新增 0" in r3.output
