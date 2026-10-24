"""End-to-end regressions for batch updates, entity IDs and report filters."""

import csv
import json
from datetime import datetime

import pytest
from typer.testing import CliRunner

from ai_job_radar.cli import app
from ai_job_radar.core.company_resolver import CompanyResolver
from ai_job_radar.export import export_jobs_csv, export_json, export_markdown
from ai_job_radar.models import Company, DimensionScore, Job
from ai_job_radar.scoring import scorer
from ai_job_radar.storage import database, repository as repo


@pytest.fixture
def store(tmp_path):
    db = tmp_path / "test.db"
    conn = database.get_connection(db)
    repo.upsert_company(conn, Company(id="c", name="Acme AI", city="北京"))
    conn.commit()
    yield conn, db
    conn.close()


def _import(tmp_path, db, command, payload, *options):
    path = tmp_path / "input.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    result = CliRunner().invoke(app, [command, str(path), "--db", str(db), *options])
    assert result.exit_code == 0, (result.output, result.exception)
    return result.output


def _job(**changes):
    return dict(id="j", company_id="c", title="AI PM", city="北京",
                source="官网") | changes


@pytest.mark.parametrize("preexisting", [True, False])
def test_batch_merges_preserve_every_update(store, tmp_path, preexisting):
    conn, db = store
    if preexisting:
        _import(tmp_path, db, "import-jobs", [_job()])
    _import(tmp_path, db, "import-jobs", [
        _job(status="Closed", salary_min=30), _job(salary_max=60),
        _job(education="本科"),
    ])
    job = repo.get_job(conn, "j")
    assert job.status.value == "Closed"
    assert (job.salary_min, job.salary_max, job.education) == (30, 60, "本科")
    if preexisting:
        assert job.last_verified_at is not None
        assert [r["status"] for r in conn.execute(
            "SELECT status FROM job_status_history WHERE job_id='j'")] == ["Closed"]


@pytest.mark.parametrize("first,second", [
    ({"job_type": "intern"}, {"job_type": "full_time"}),
    ({"source_job_id": "P001"}, {"source_job_id": "P002"}),
    ({"title": "A very long job title " + "a" * 30},
     {"title": "A very long job title " + "b" * 30}),
])
def test_distinct_jobs_reusing_id_survive_reimports(store, tmp_path, first, second):
    conn, db = store
    _import(tmp_path, db, "import-jobs", [_job(**first)])
    output = _import(tmp_path, db, "import-jobs", [_job(**second)])
    assert "id 冲突改写 1" in output
    before = {j.id for j in repo.list_jobs(conn)}
    assert len(before) == 2 and "j" in before
    for _ in range(2):
        output = _import(tmp_path, db, "import-jobs", [_job(**second)])
        assert "新增 0" in output
    assert {j.id for j in repo.list_jobs(conn)} == before
    original = repo.get_job(conn, "j").model_dump(mode="json")
    assert all(original[key] == value for key, value in first.items())


def test_fingerprint_collision_never_overwrites(store, tmp_path, monkeypatch):
    from ai_job_radar.core import deduplication
    monkeypatch.setattr(deduplication, "job_fingerprint", lambda job: "samehash")
    conn, db = store
    payload = [_job(job_type=kind) for kind in ("intern", "campus", "full_time")]
    _import(tmp_path, db, "import-jobs", payload)
    ids = {j.id for j in repo.list_jobs(conn)}
    assert ids == {"j", "j-samehash", "j-samehash-2"}
    _import(tmp_path, db, "import-jobs", payload)
    assert {j.id for j in repo.list_jobs(conn)} == ids


def test_source_fields_and_secondary_links_survive(store, tmp_path):
    conn, db = store
    _import(tmp_path, db, "import-jobs", [_job(source="小红书")])
    _import(tmp_path, db, "import-jobs", [
        _job(source_url="https://example.com/official", source_job_id="P001")])
    job = repo.get_job(conn, "j")
    assert (job.source, job.source_url, job.source_job_id) == (
        "官网", "https://example.com/official", "P001")
    _import(tmp_path, db, "import-jobs", [
        _job(source="小红书", source_url="https://example.com/community")])
    assert {e.url for e in repo.list_evidence(conn, "job", "j")} == {
        "https://example.com/official", "https://example.com/community"}
    assert repo.get_job(conn, "j").source_job_id == "P001"


def test_sparse_company_import_preserves_fields_and_explicit_null_clears(store, tmp_path):
    conn, db = store
    verified = datetime(2026, 10, 1)
    repo.upsert_company(conn, Company(
        id="c", name="Acme AI", city="北京", website="https://example.com",
        company_type="bigtech_ai_team", tracks=["AI Agents"],
        funding_stage="B轮", team_size_min=50, last_verified_at=verified))
    conn.commit()
    _import(tmp_path, db, "import-companies", [
        {"company": {"id": "new-c", "name": "Acme AI", "city": "北京"}}])
    company = repo.get_company(conn, "c")
    assert (company.website, company.funding_stage, company.team_size_min,
            company.last_verified_at) == ("https://example.com", "B轮", 50, verified)
    assert company.company_type.value == "bigtech_ai_team"
    assert [t.value for t in company.tracks] == ["AI Agents"]
    _import(tmp_path, db, "import-companies", [
        {"company": {"id": "c", "name": "Acme AI", "city": "北京",
                     "website": None, "tracks": []}}])
    company = repo.get_company(conn, "c")
    assert company.website is None and company.tracks == []
    assert company.funding_stage == "B轮"


def test_normalized_and_legacy_aliases_resolve_without_duplicate_company(store, tmp_path):
    conn, db = store
    conn.execute("INSERT INTO company_aliases VALUES (?,?)", ("Legacy Labs", "c"))
    conn.commit()
    resolver = CompanyResolver(conn)
    assert resolver.resolve("ＡＣＭＥ ai") == "c"
    assert resolver.resolve("legacy labs") == "c"
    _import(tmp_path, db, "import-companies", [
        {"company": {"id": "new-c", "name": "acme ai", "city": "北京"}}])
    assert len(repo.list_companies(conn)) == 1
    assert resolver.resolve("new-c") == "c"


def test_score_import_uses_canonical_company_id_and_rejects_orphans(store, tmp_path):
    conn, db = store
    _import(tmp_path, db, "import-companies", [
        {"company": {"id": "new-c", "name": "Acme AI", "city": "北京"}}])
    output = _import(tmp_path, db, "import-scores", [
        {"company_id": cid, "dimensions": [{"dimension": "funding", "score": 8}]}
        for cid in ("new-c", "ghost")])
    assert "已导入 1/2" in output
    assert repo.get_latest_score(conn, "c").normalized_total == 8
    assert repo.get_latest_score(conn, "new-c") is None
    assert repo.get_latest_score(conn, "ghost") is None


def test_research_reimports_deduplicate_exact_facts_but_keep_conflicts(store, tmp_path):
    conn, db = store
    research = {"company_id": "c", "funding": [
        {"round": "A", "amount": "100万元", "investors": ["B", "A"]}],
        "founders": [{"name": "Alice"}], "team": {"size_min": 10},
        "products": [{"name": "App"}]}
    for _ in range(2):
        _import(tmp_path, db, "import-research", [research])
    research["funding"][0]["investors"].reverse()
    _import(tmp_path, db, "import-research", [research])
    assert len(repo.list_funding(conn, "c")) == 1
    assert len(repo.list_founders(conn, "c")) == 1
    assert len(repo.list_products(conn, "c")) == 1
    assert repo.list_founders(conn, "c")[0].source_fact_kind.value == "verified"
    assert repo.get_team_info(conn, "c").source_fact_kind.value == "verified"
    research["funding"][0]["amount"] = "200万元"
    _import(tmp_path, db, "import-research", [research])
    assert {f.amount for f in repo.list_funding(conn, "c")} == {"100万元", "200万元"}


def test_all_exports_filter_actual_job_city(store, tmp_path):
    conn, _ = store
    repo.upsert_company(conn, Company(id="s", name="Shanghai HQ", city="上海"))
    repo.upsert_job(conn, Job(**_job(id="bj-job", title="北京岗位", company_id="s")))
    repo.upsert_job(conn, Job(**_job(id="sh-job", title="上海岗位", city="上海")))
    conn.commit()
    export_json(conn, tmp_path / "r.json", city="北京")
    export_markdown(conn, tmp_path / "r.md", city="北京")
    export_jobs_csv(conn, tmp_path / "r.csv", city="北京")
    data = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
    assert [co["company"]["id"] for co in data] == ["s"]
    assert [e["job"]["id"] for co in data for e in co["jobs"]] == ["bj-job"]
    with (tmp_path / "r.csv").open(encoding="utf-8-sig", newline="") as stream:
        assert [row["id"] for row in csv.DictReader(stream)] == ["bj-job"]
    md = (tmp_path / "r.md").read_text(encoding="utf-8")
    assert "北京岗位" in md and "上海岗位" not in md and "Shanghai HQ" in md
    export_markdown(conn, tmp_path / "single.md", city="北京", company="c")
    assert "上海岗位" not in (tmp_path / "single.md").read_text(encoding="utf-8")


def test_default_weights_read_config_and_packaged_fallback(tmp_path, monkeypatch):
    weights = scorer.load_weights()
    custom = weights | {"funding": 0.5, "founders": 0.2, "product": 0.1,
                        "team": 0.1, "hiring": 0.1}
    path = tmp_path / "weights.yaml"
    path.write_text(json.dumps({"weights": custom}), encoding="utf-8")
    monkeypatch.setattr(scorer, "REPO_WEIGHTS_PATH", path)
    assert scorer.load_weights() == custom
    score = scorer.compute_score("c", [DimensionScore(dimension="funding", score=8)])
    assert score.coverage == 0.5
    monkeypatch.setattr(scorer, "REPO_WEIGHTS_PATH", tmp_path / "absent.yaml")
    assert scorer.load_weights() == weights


def test_bundled_weights_work_through_cli(store, tmp_path):
    conn, db = store
    _import(tmp_path, db, "import-scores", [
        {"company_id": "c", "dimensions": [{"dimension": "funding", "score": 8}]}],
        "--weights", str(scorer.REPO_WEIGHTS_PATH))
    assert repo.get_latest_score(conn, "c").normalized_total == 8


@pytest.mark.parametrize("text", [
    '"""invalid yaml header"""\nweights: {}', "[]", "weights: {}",
    json.dumps({"weights": {"funding": 1}}),
    json.dumps({"weights": {"funding": "nan", "founders": 1, "team": 1,
                            "product": 1, "hiring": 1}}),
])
def test_invalid_config_is_a_clear_cli_error(store, tmp_path, text):
    _, db = store
    path = tmp_path / "bad.yaml"
    path.write_text(text, encoding="utf-8")
    data = tmp_path / "scores.json"
    data.write_text("[]", encoding="utf-8")
    result = CliRunner().invoke(app, [
        "import-scores", str(data), "--db", str(db), "--weights", str(path)])
    assert result.exit_code == 2
    assert "--weights" in result.output


def test_latest_score_retains_time_and_breaks_second_precision_ties(store):
    conn, _ = store
    timestamp = datetime(2025, 3, 1)
    for value in (6, 8):
        score = scorer.compute_score("c", [DimensionScore(dimension="funding", score=value)])
        score.computed_at = timestamp
        repo.save_score(conn, score)
    latest = repo.get_latest_score(conn, "c")
    assert latest.normalized_total == 8 and latest.computed_at == timestamp
