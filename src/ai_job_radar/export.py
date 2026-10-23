"""Export reports: Markdown / JSON / CSV with sources, timestamps and
credibility info preserved."""

from __future__ import annotations

import csv
import sqlite3
from datetime import datetime
from pathlib import Path

from .models import (
    JOB_TYPE_LABELS,
    Company,
    CompanyScore,
    Job,
    JobStatus,
)
from .research.report import build_research_report
from .scoring.scorer import DIMENSION_LABELS
from .storage import repository as repo

SUPPORTED_CITIES = ["北京", "上海", "深圳", "杭州", "广州", "成都", "南京", "武汉", "苏州"]

# Spec 1.4: jobs marked only "Global Remote" with unknown actual location are
# kept but flagged 待核验, not silently dropped.
REMOTE_PENDING_CITIES = {"全球远程", "global remote", "remote"}


def remote_pending(job: Job) -> bool:
    return job.city.strip().lower() in REMOTE_PENDING_CITIES


def in_scope(job: Job) -> bool:
    """Hard constraint: actual work location must be in mainland China.
    Global Remote with unknown location counts as 待核验 (kept, Unknown)."""
    if job.city in SUPPORTED_CITIES:
        return True
    return remote_pending(job)


def _job_type_label(job: Job) -> str:
    return JOB_TYPE_LABELS.get(job.job_type, "-") if job.job_type else "-"


def _display_status(job: Job) -> str:
    if remote_pending(job) and job.status == JobStatus.RECENTLY_SEEN:
        return f"{JobStatus.UNKNOWN.value}（地点待核验）"
    return job.status.value


# ---------------------------------------------------------------- JSON

def export_json(conn: sqlite3.Connection, out_path: Path,
                city: str | None = None) -> None:
    companies = repo.list_companies(conn, city=city)
    payload = []
    for c in companies:
        score = repo.get_latest_score(conn, c.id)
        jobs_payload = []
        for j in repo.list_jobs(conn, company_id=c.id):
            if not in_scope(j):
                continue
            jobs_payload.append({
                "job": j.model_dump(),
                "evidence": [e.model_dump() for e in
                             repo.list_evidence(conn, "job", j.id)],
            })
        payload.append({
            "company": c.model_dump(),
            "jobs": jobs_payload,
            "research": build_research_report(conn, c.id),
            "score": score.model_dump() if score else None,
        })
    import json
    out_path.write_text(json.dumps(
        payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


# ---------------------------------------------------------------- CSV

def export_jobs_csv(conn: sqlite3.Connection, out_path: Path,
                    city: str | None = None) -> None:
    jobs = [j for j in repo.list_jobs(conn, city=city) if in_scope(j)]
    fields = ["id", "company_id", "title", "city", "job_type", "salary_min",
              "salary_max", "salary_months", "experience", "education", "source",
              "source_url", "posted_at", "status"]
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for j in jobs:
            d = j.model_dump()
            d["posted_at"] = str(d.get("posted_at") or "")
            d["job_type"] = _job_type_label(j)
            d["status"] = _display_status(j)
            writer.writerow({k: d.get(k) for k in fields})


# ---------------------------------------------------------------- Markdown

def _cell(value) -> str:
    """Markdown table cells must not contain raw pipes or line breaks."""
    text = "-" if value is None else str(value)
    return text.replace("|", "\\|").replace("\r\n", " ").replace("\n", " ").strip() or "-"


def _md_table(rows: list[list], headers: list[str]) -> str:
    line1 = "| " + " | ".join(_cell(h) for h in headers) + " |"
    line2 = "|" + "---|" * len(headers)
    body = ["| " + " | ".join(_cell(c) for c in r) + " |" for r in rows]
    return "\n".join([line1, line2, *body])


def _weight_display(d) -> str:
    from .models import DEFAULT_WEIGHTS
    w = d.weight if d.weight is not None else DEFAULT_WEIGHTS.get(d.dimension, 0)
    return f"{w:.0%}"


def _company_lines(conn: sqlite3.Connection, c: Company,
                   score: CompanyScore | None) -> list[str]:
    research = build_research_report(conn, c.id, as_models=True)
    jobs = [j for j in repo.list_jobs(conn, company_id=c.id) if in_scope(j)]
    lines = [f"## {c.name}", ""]
    if c.description:
        lines += [c.description, ""]
    team = research["team"]
    size = (f"{team.size_min}-{team.size_max} 人" if team and team.size_min
            else f"{c.team_size_min}-{c.team_size_max or '?'} 人" if c.team_size_min
            else "未知")
    lines += [f"- 官网：{c.website or '未知'}",
              f"- 城市：{c.city}",
              f"- 融资阶段：{c.funding_stage or '未披露'}",
              f"- 团队规模：{size}",
              f"- 赛道：{', '.join(t.value for t in c.tracks) or '未知'}",
              f"- 最后核验：{c.last_verified_at:%Y-%m-%d %H:%M}"
              if c.last_verified_at else "- 最后核验：未核验", ""]

    if research["funding"]:
        lines += ["### 融资历史", ""]
        lines.append(_md_table(
            [[f.date or "?", f.round or "未披露", f.amount or "-",
              ", ".join(f.investors) or "-"] for f in research["funding"]],
            ["时间", "轮次", "金额", "投资机构"]))
        lines.append("")
    if research["founders"]:
        lines += ["### 创始团队", ""]
        for f in research["founders"]:
            lines.append(
                f"- **{f.name}**（{f.title or '职位未知'}）：{f.career or '履历未知'}"
                f"（{f.source_fact_kind.value}）")
        lines.append("")
    if team:
        lines += ["### 团队规模", ""]
        lines.append(f"- 规模：{team.size_min or '?'}-{team.size_max or '?'} 人"
                     f"（{team.source_fact_kind.value}）")
        for s in team.expansion_signals:
            lines.append(f"- 扩张信号：{s}")
        if team.stage_note:
            lines.append(f"- 阶段备注：{team.stage_note}")
        lines.append("")
    if research["products"]:
        lines += ["### 旗下产品", ""]
        for p in research["products"]:
            entry = f"- **{p.name}**：{p.positioning or '定位未知'}"
            if p.target_users:
                entry += f"，目标用户：{p.target_users}"
            if p.traction:
                entry += f"。公开进展：{p.traction}"
            lines.append(entry)
        lines.append("")

    if score:
        lines += ["### 评分（证据驱动）", ""]
        if score.normalized_total is not None:
            lines.append(f"- 综合分（权重归一化）：**{score.normalized_total} / 10**")
        else:
            lines.append("- 综合分：证据不足，未输出")
        lines.append(f"- 证据覆盖率：{score.coverage:.0%}")
        if score.note:
            lines.append(f"- 备注：{score.note}")
        lines.append("")
        lines.append(_md_table(
            [[DIMENSION_LABELS.get(d.dimension, d.dimension),
              d.score if d.score is not None else "未知（不计零分）",
              _weight_display(d), d.fact_kind.value,
              d.rationale or d.evidence_summary or "-"]
             for d in score.dimensions],
            ["维度", "得分(0-10)", "权重", "事实类型", "依据摘要"]))
        lines.append("")

    if jobs:
        lines += ["### 在招岗位", ""]
        lines.append(_md_table(
            [[j.title, j.city, _job_type_label(j), j.salary_min or "?",
              j.salary_max or "?", j.experience or "-", _display_status(j)]
             for j in jobs],
            ["岗位", "城市", "性质", "薪资下限K", "薪资上限K", "经验", "状态"]))
        lines.append("")
        # 岗位级证据：来源、检索时间与可信度随报告一起导出
        job_ev_lines = []
        for j in jobs:
            evs = repo.list_evidence(conn, "job", j.id)
            if not evs:
                continue
            items = []
            for e in evs[:3]:
                label = e.title or e.publisher or e.url or "来源"
                link = f"[{label}]({e.url})" if e.url else label
                items.append(f"{link}（{e.source_type.value}，"
                             f"检索于 {e.retrieved_at:%Y-%m-%d}）")
            job_ev_lines.append(f"- **{j.title}**：" + "；".join(items)
                                + (f" 等共 {len(evs)} 条" if len(evs) > 3 else ""))
        if job_ev_lines:
            lines += ["#### 岗位来源", *job_ev_lines, ""]

    ev = research["evidence"]
    if ev:
        lines += ["### 关键来源", ""]
        for e in ev[:10]:
            label = e.title or e.publisher or e.url or "来源"
            link = f"[{label}]({e.url})" if e.url else label
            lines.append(f"- {link}（{e.source_type.value}，"
                         f"检索于 {e.retrieved_at:%Y-%m-%d}）")
        lines.append("")
    return lines


def export_markdown(conn: sqlite3.Connection, out_path: Path,
                    city: str | None = None,
                    company: str | None = None) -> None:
    """Full report over all companies, or a single-company profile when
    `company` (id / name / alias) is given."""
    if company:
        c = repo.get_company(conn, company)
        if not c:
            from .core.company_resolver import CompanyResolver
            cid = CompanyResolver(conn).resolve(company)
            c = repo.get_company(conn, cid) if cid else None
        if not c:
            raise ValueError(f"company not found: {company}")
        companies = [c]
    else:
        companies = repo.list_companies(conn, city=city)

    lines: list[str] = [
        "# AI 公司与岗位研究报告",
        "",
        f"> 生成时间：{datetime.now():%Y-%m-%d %H:%M}。"
        "所有信息均保留来源与核验时间；评分为证据驱动的辅助参考，不构成投资建议。",
        "",
    ]
    if company:
        lines += [f"单一公司档案：{companies[0].name}", ""]
    else:
        lines += [f"共 {len(companies)} 家公司。", "", "## 公司总览", ""]
        rows = []
        for c in companies:
            score = repo.get_latest_score(conn, c.id)
            n_jobs = len([j for j in repo.list_jobs(conn, company_id=c.id)
                          if in_scope(j)])
            rows.append([
                c.name, c.city, c.funding_stage or "未知",
                f"{c.team_size_min or '?'}-{c.team_size_max or '?'}",
                ", ".join(t.value for t in c.tracks),
                n_jobs,
                score.normalized_total if score and score.normalized_total
                is not None else "-",
                f"{score.coverage:.0%}" if score else "-",
            ])
        lines.append(_md_table(rows,
            ["公司", "城市", "融资阶段", "团队规模", "赛道", "岗位数", "综合分", "覆盖率"]))
        lines.append("")

    for c in companies:
        score = repo.get_latest_score(conn, c.id)
        lines += _company_lines(conn, c, score)

    out_path.write_text("\n".join(lines), encoding="utf-8")
