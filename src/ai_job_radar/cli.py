"""ai-job-radar CLI. Deterministic tools only; LLM tasks (extraction,
scoring rationale, report writing) are executed by the host agent, which
feeds results back via the import commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from .core import discovery, verification
from .core.company_resolver import CompanyResolver
from .core.deduplication import find_duplicate
from .export import export_jobs_csv, export_json, export_markdown
from .models import (
    Company,
    CompanyScore,
    DimensionScore,
    Evidence,
    Founder,
    FundingEvent,
    Job,
    Product,
    TeamInfo,
    Track,
)
from .scoring.scorer import compute_score, load_weights
from .storage import database, repository as repo

app = typer.Typer(help="Seek AI Jobs in China - AI 招聘情报 Agent CLI")
DB_OPTION = typer.Option(None, "--db", help="SQLite 路径，默认 ~/.ai_job_radar/ai_jobs.db")


def _conn(db: Optional[str]):
    return database.get_connection(db)


@app.command()
def discover(
    city: Optional[str] = typer.Option(None, "--city"),
    track: Optional[str] = typer.Option(None, "--track"),
    company_type: Optional[str] = typer.Option(None, "--type"),
    funding_stage: Optional[str] = typer.Option(None, "--funding-stage"),
    team_min: Optional[int] = typer.Option(None, "--team-min"),
    team_max: Optional[int] = typer.Option(None, "--team-max"),
    hiring_only: bool = typer.Option(False, "--hiring-only"),
    db: Optional[str] = DB_OPTION,
):
    """发现符合条件的 AI 企业（基于本地库）。"""
    conn = _conn(db)
    tracks = None
    if track:
        try:
            tracks = [Track(track)]
        except ValueError:
            valid = ", ".join(t.value for t in Track)
            raise typer.BadParameter(f"未知赛道 {track!r}，可选：{valid}")
    companies = discovery.filter_companies(
        conn, city=city, tracks=tracks, company_type=company_type,
        funding_stage=funding_stage, team_size_min=team_min,
        team_size_max=team_max, hiring_only=hiring_only)
    for c in companies:
        n = len(repo.list_jobs(conn, company_id=c.id))
        typer.echo(f"{c.id}\t{c.name}\t{c.city}\t{c.funding_stage or '?'}"
                   f"\t岗位数:{n}\t{','.join(t.value for t in c.tracks)}")
    typer.echo(f"共 {len(companies)} 家", err=True)


@app.command("import-companies")
def import_companies(
    file: Path = typer.Argument(..., exists=True),
    db: Optional[str] = DB_OPTION,
):
    """导入公司 JSON（宿主 Agent 调研产出的结构化结果）。"""
    conn = _conn(db)
    data = json.loads(file.read_text(encoding="utf-8"))
    n = 0
    for item in data:
        raw = dict(item["company"])
        if raw.get("company_type") not in ("startup", "bigtech_ai_team",
                                           "foreign_in_china"):
            raw["company_type"] = "startup"
        company = Company(**raw)
        resolver = CompanyResolver(conn)
        dup = resolver.resolve(company.name)
        if dup and dup != company.id:
            typer.echo(f"合并到已有实体 {dup}: {company.name}", err=True)
            old_id = company.id
            company.id = dup
            # 旧 ID 注册为别名：后续引用旧 ID 的岗位/研究仍能解析到合并后实体
            resolver.register_alias(old_id, dup)
        repo.upsert_company(conn, company)
        for alias in item.get("aliases", []):
            resolver.register_alias(alias, company.id)
        for ev in item.get("evidence", []):
            repo.add_evidence(conn, Evidence(entity_type="company",
                                             entity_id=company.id, **ev))
        conn.commit()
        n += 1
    typer.echo(f"已导入 {n} 家公司")


@app.command("import-jobs")
def import_jobs(
    file: Path = typer.Argument(..., exists=True),
    db: Optional[str] = DB_OPTION,
):
    """导入岗位 JSON，自动去重并过滤非中国境内岗位。

    仅标注 Global Remote、实际地点未知的岗位保留入库，状态标记
    Unknown（地点待核验）；明确位于中国大陆以外的岗位被过滤。
    """
    conn = _conn(db)
    data = json.loads(file.read_text(encoding="utf-8"))
    from .core.deduplication import find_duplicate, job_fingerprint
    from .export import in_scope, remote_pending
    from .models import JobStatus

    def _norm_evidence_date(value):
        # 与 import-research 一致：'2026' → '2026-01-01'，'2026-03' → '2026-03-01'
        if isinstance(value, str) and len(value) in (4, 7):
            return value + ("-01-01" if len(value) == 4 else "-01")
        return value

    existing = repo.list_jobs(conn)
    resolver = CompanyResolver(conn)
    n, merged, filtered, pending, rekeyed, orphan = 0, 0, 0, 0, 0, 0
    for item in data:
        try:
            job = Job(**item)
        except Exception as exc:
            typer.echo(f"跳过非法岗位记录: {exc}", err=True)
            filtered += 1
            continue
        # 公司 ID 统一经别名解析；无法关联到已存在公司的记录拒绝入库，
        # 否则该岗位在所有按公司聚合的视图（报告/导出）中会静默丢失。
        resolved_cid = resolver.resolve(job.company_id) or job.company_id
        if resolved_cid != job.company_id:
            job.company_id = resolved_cid
        if not repo.get_company(conn, job.company_id):
            typer.echo(f"跳过岗位（公司不存在）: {job.id} -> {job.company_id}",
                       err=True)
            orphan += 1
            continue
        if remote_pending(job):
            job.status = JobStatus.UNKNOWN  # 待核验：实际地点未知
            pending += 1
        elif not in_scope(job):
            filtered += 1
            continue
        # 同一 ID 已被另一条岗位占用时不得覆盖：派生稳定后缀保留两条记录
        row = repo.get_job(conn, job.id)
        if row and (row.title, row.company_id, row.city) != (
                job.title, job.company_id, job.city):
            job.id = f"{job.id}-{job_fingerprint(job)[:6]}"
            rekeyed += 1
        dup = find_duplicate(job, existing)
        if dup:
            merged += 1
            # 合并而非跳过：新证据入库、缺失字段补全、状态变化记录历史
            for ev in item.get("evidence", []):
                ev = dict(ev)
                ev["published_at"] = _norm_evidence_date(ev.get("published_at"))
                repo.add_evidence(conn, Evidence(entity_type="job",
                                                 entity_id=dup.id, **ev))
            filled = dup.model_copy()
            for f in ("location_detail", "job_type", "salary_min", "salary_max",
                      "salary_months", "experience", "education", "jd",
                      "source_url", "source_job_id"):
                if getattr(filled, f) is None and getattr(job, f) is not None:
                    setattr(filled, f, getattr(job, f))
            repo.upsert_job(conn, filled)
            if job.status != dup.status and job.status != JobStatus.RECENTLY_SEEN:
                repo.update_job_status(conn, dup.id, job.status.value,
                                       "重复导入记录携带状态更新")
            continue
        repo.upsert_job(conn, job)
        for ev in item.get("evidence", []):
            ev = dict(ev)
            ev["published_at"] = _norm_evidence_date(ev.get("published_at"))
            repo.add_evidence(conn, Evidence(entity_type="job",
                                             entity_id=job.id, **ev))
        existing.append(job)
        n += 1
    conn.commit()
    notes = []
    if rekeyed:
        notes.append(f"id 冲突改写 {rekeyed}")
    if orphan:
        notes.append(f"公司缺失跳过 {orphan}")
    note = ("，" + "，".join(notes)) if notes else ""
    typer.echo(f"新增 {n}，去重合并 {merged}，地域过滤 {filtered}，"
               f"地点待核验 {pending}{note}")


@app.command("import-research")
def import_research(
    file: Path = typer.Argument(..., exists=True),
    db: Optional[str] = DB_OPTION,
):
    """导入公司研究 JSON：融资/创始团队/团队规模/产品 + 证据。"""

    def _date(value):
        if isinstance(value, str):
            if len(value) == 4:
                return value + "-01-01"
            if len(value) == 7:
                return value + "-01"
        return value

    def _fact_kind(value):
        return {"official": "verified", "media": "verified",
                "ai": "inferred"}.get(value, value)

    conn = _conn(db)
    data = json.loads(file.read_text(encoding="utf-8"))
    resolver = CompanyResolver(conn)
    ok_research = 0
    for item in data:
        cid = resolver.resolve(item["company_id"]) or item["company_id"]
        if not repo.get_company(conn, cid):
            typer.echo(f"跳过研究（公司不存在）: {item['company_id']}", err=True)
            continue
        ok_research += 1
        for f in item.get("funding", []):
            f = dict(f)
            f["date"] = _date(f.get("date"))
            if f.get("investors") is None:
                f["investors"] = []
            repo.add_funding(conn, FundingEvent(company_id=cid, **f))
        for f in item.get("founders", []):
            f = dict(f)
            f["source_fact_kind"] = _fact_kind(f.get("source_fact_kind"))
            repo.add_founder(conn, Founder(company_id=cid, **f))
        if item.get("team"):
            team = dict(item["team"])
            team["source_fact_kind"] = _fact_kind(team.get("source_fact_kind"))
            repo.upsert_team_info(conn, TeamInfo(company_id=cid, **team))
        for p in item.get("products", []):
            repo.add_product(conn, Product(company_id=cid, **p))
        for ev in item.get("evidence", []):
            ev = dict(ev)
            ev["published_at"] = _date(ev.get("published_at"))
            repo.add_evidence(conn, Evidence(entity_type="company",
                                             entity_id=cid, **ev))
        c = repo.get_company(conn, cid)
        if c:
            from datetime import datetime
            c.last_verified_at = datetime.now()
            repo.upsert_company(conn, c)
        conn.commit()
    typer.echo(f"已导入 {ok_research}/{len(data)} 份研究")


@app.command("import-scores")
def import_scores(
    file: Path = typer.Argument(..., exists=True),
    weights_file: Optional[Path] = typer.Option(None, "--weights"),
    db: Optional[str] = DB_OPTION,
):
    """导入维度评分 JSON（宿主 Agent 依据 Rubric 评估），计算归一化综合分。"""
    conn = _conn(db)
    weights = load_weights(str(weights_file) if weights_file else None)
    data = json.loads(file.read_text(encoding="utf-8"))
    ok = 0
    for item in data:
        try:
            dims = [DimensionScore(**d) for d in item["dimensions"]]
            score = compute_score(item["company_id"], dims, weights,
                                  note=item.get("note"))
        except Exception as exc:
            typer.echo(f"跳过 {item.get('company_id')}: {exc}", err=True)
            continue
        repo.save_score(conn, score)
        conn.commit()
        ok += 1
        typer.echo(f"{item['company_id']}: 综合分 {score.normalized_total}"
                   f" 覆盖率 {score.coverage:.0%}")
    typer.echo(f"已导入 {ok}/{len(data)} 份评分", err=True)


@app.command()
def jobs(
    city: Optional[str] = typer.Option(None, "--city"),
    keyword: Optional[str] = typer.Option(None, "--keyword"),
    company: Optional[str] = typer.Option(None, "--company"),
    job_type: Optional[str] = typer.Option(
        None, "--type", help="岗位性质：实习 / 校招 / 社招（或 intern/campus/full_time）"),
    db: Optional[str] = DB_OPTION,
):
    """检索中国境内 AI 岗位（--type 区分实习/校招/社招正职）。"""
    conn = _conn(db)
    cid = None
    if company:
        cid = CompanyResolver(conn).resolve(company) or company
    from .models import JOB_TYPE_LABELS, JobType
    type_value = None
    if job_type:
        mapping = {"实习": "intern", "intern": "intern",
                   "校招": "campus", "campus": "campus", "应届": "campus",
                   "社招": "full_time", "正职": "full_time",
                   "full_time": "full_time"}
        type_value = mapping.get(job_type.strip().lower(), job_type)
        try:
            JobType(type_value)
        except ValueError:
            valid = "实习 / 校招 / 社招"
            raise typer.BadParameter(f"未知岗位性质 {job_type!r}，可选：{valid}")
    matched = repo.list_jobs(conn, city=city, keyword=keyword, company_id=cid,
                             job_type=type_value)
    for j in matched:
        label = JOB_TYPE_LABELS.get(j.job_type, "未标注") if j.job_type else "未标注"
        typer.echo(f"{j.id}\t{j.title}\t{j.city}\t{label}\t{j.status.value}\t{j.source}")
    typer.echo(f"共 {len(matched)} 条岗位", err=True)


@app.command()
def research(
    company: str = typer.Option(..., "--company"),
    db: Optional[str] = DB_OPTION,
):
    """输出公司研究报告（JSON）。"""
    conn = _conn(db)
    cid = CompanyResolver(conn).resolve(company) or company
    from .research.report import build_research_report
    typer.echo(json.dumps(build_research_report(conn, cid),
                          ensure_ascii=False, indent=2, default=str))


@app.command()
def score(
    company: Optional[str] = typer.Option(None, "--company"),
    db: Optional[str] = DB_OPTION,
):
    """查看公司评分。"""
    conn = _conn(db)
    ids = ([CompanyResolver(conn).resolve(company) or company] if company
           else [c.id for c in repo.list_companies(conn)])
    for cid in ids:
        s = repo.get_latest_score(conn, cid)
        if s:
            typer.echo(f"{cid}: {s.normalized_total} (覆盖率 {s.coverage:.0%})")
        else:
            typer.echo(f"{cid}: 暂无评分")


@app.command()
def verify(
    job_id: Optional[str] = typer.Option(None, "--job-id"),
    company: Optional[str] = typer.Option(None, "--company"),
    db: Optional[str] = DB_OPTION,
):
    """核验岗位状态（检查原始页面是否存在并分类）。"""
    conn = _conn(db)
    if company:
        cid = CompanyResolver(conn).resolve(company) or company
        targets = repo.list_jobs(conn, company_id=cid)
    else:
        targets = [repo.get_job(conn, job_id)] if job_id else []
    for j in targets:
        if not j:
            continue
        status = verification.verify_job(conn, j)
        conn.commit()
        typer.echo(f"{j.id}\t{j.title}\t-> {status.value}")


@app.command()
def export(
    fmt: str = typer.Option("markdown", "--format",
                            help="markdown | json | csv"),
    out: Path = typer.Option(Path("report"), "--out"),
    city: Optional[str] = typer.Option(None, "--city"),
    company: Optional[str] = typer.Option(
        None, "--company", help="仅导出该公司（id/名称/别名）的档案"),
    db: Optional[str] = DB_OPTION,
):
    """导出研究报告，保留来源、时间与可信度信息。"""
    conn = _conn(db)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        if fmt == "markdown":
            p = out.with_suffix(".md")
            export_markdown(conn, p, city=city, company=company)
        elif fmt == "json":
            if company:
                raise typer.BadParameter("--company 仅支持 markdown 格式")
            p = out.with_suffix(".json")
            export_json(conn, p, city=city)
        elif fmt == "csv":
            p = out.with_suffix(".csv")
            export_jobs_csv(conn, p, city=city)
        else:
            raise typer.BadParameter("format must be markdown|json|csv")
    except ValueError as exc:
        raise typer.BadParameter(str(exc))
    typer.echo(f"已导出 {p}")


if __name__ == "__main__":
    app()
