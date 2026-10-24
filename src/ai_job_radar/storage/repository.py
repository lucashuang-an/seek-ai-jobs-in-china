"""Repository: model <-> SQLite mapping for all entities."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from ..models import (
    Company,
    CompanyScore,
    DimensionScore,
    Evidence,
    Founder,
    FundingEvent,
    Job,
    Product,
    TeamInfo,
)
from .database import jdump, jload

NOW = lambda: datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------- companies

def upsert_company(conn: sqlite3.Connection, c: Company) -> None:
    current = get_company(conn, c.id)
    if current:
        # Omitted fields are a patch; explicit null/[] still clears a value.
        changes = c.model_dump(exclude_unset=True, exclude={"created_at"})
        c = Company(**(current.model_dump() | changes))
    conn.execute(
        """INSERT INTO companies (id, name, aliases, english_name, website, city,
               hq_location, company_type, tracks, description, funding_stage,
               team_size_min, team_size_max, hiring_signals, created_at, updated_at,
               last_verified_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET
               name=excluded.name, aliases=excluded.aliases,
               english_name=excluded.english_name, website=excluded.website,
               city=excluded.city, hq_location=excluded.hq_location,
               company_type=excluded.company_type, tracks=excluded.tracks,
               description=excluded.description, funding_stage=excluded.funding_stage,
               team_size_min=excluded.team_size_min, team_size_max=excluded.team_size_max,
               hiring_signals=excluded.hiring_signals, updated_at=excluded.updated_at,
               last_verified_at=excluded.last_verified_at""",
        (c.id, c.name, jdump(c.aliases), c.english_name, c.website, c.city,
         c.hq_location, c.company_type.value, jdump([t.value for t in c.tracks]),
         c.description, c.funding_stage, c.team_size_min, c.team_size_max,
         jdump(c.hiring_signals), c.created_at.isoformat(timespec="seconds"),
         NOW(), c.last_verified_at.isoformat(timespec="seconds") if c.last_verified_at else None),
    )
    from ..core.company_resolver import CompanyResolver
    resolver = CompanyResolver(conn)
    for alias in {c.name, *c.aliases, *( [c.english_name] if c.english_name else [] )}:
        if alias:
            resolver.register_alias(alias, c.id)


def get_company(conn: sqlite3.Connection, company_id: str) -> Company | None:
    row = conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone()
    return _company_from_row(row) if row else None


def list_companies(conn: sqlite3.Connection, city: str | None = None,
                   track: str | None = None) -> list[Company]:
    rows = conn.execute("SELECT * FROM companies ORDER BY name").fetchall()
    out = [_company_from_row(r) for r in rows]
    if city:
        out = [c for c in out if c.city == city]
    if track:
        out = [c for c in out if any(track.lower() in t.value.lower() for t in c.tracks)]
    return out


def _company_from_row(r: sqlite3.Row) -> Company:
    from ..models import CompanyType, Track

    def _dt(value):
        try:
            return datetime.fromisoformat(value) if value else None
        except ValueError:
            return None

    return Company(
        id=r["id"], name=r["name"], aliases=jload(r["aliases"], []),
        english_name=r["english_name"], website=r["website"], city=r["city"],
        hq_location=r["hq_location"],
        company_type=CompanyType(r["company_type"] or "startup"),
        tracks=[Track(t) for t in jload(r["tracks"], [])],
        description=r["description"], funding_stage=r["funding_stage"],
        team_size_min=r["team_size_min"], team_size_max=r["team_size_max"],
        hiring_signals=jload(r["hiring_signals"], []),
        created_at=_dt(r["created_at"]) or Company.model_fields["created_at"].get_default(),
        updated_at=_dt(r["updated_at"]) or datetime.now(),
        last_verified_at=_dt(r["last_verified_at"]),
    )


# ---------------------------------------------------------------- jobs

def upsert_job(conn: sqlite3.Connection, j: Job) -> None:
    conn.execute(
        """INSERT INTO jobs (id, company_id, title, city, location_detail, job_type,
               salary_min, salary_max, salary_months, experience, education, jd,
               source, source_url, source_job_id, posted_at, first_seen_at,
               last_verified_at, status)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET
               title=excluded.title, city=excluded.city,
               location_detail=excluded.location_detail,
               job_type=excluded.job_type,
               salary_min=excluded.salary_min, salary_max=excluded.salary_max,
               salary_months=excluded.salary_months, experience=excluded.experience,
               education=excluded.education, jd=excluded.jd, status=excluded.status,
               source=excluded.source, source_url=excluded.source_url,
               source_job_id=excluded.source_job_id, posted_at=excluded.posted_at,
               last_verified_at=excluded.last_verified_at""",
        (j.id, j.company_id, j.title, j.city, j.location_detail,
         j.job_type.value if j.job_type else None,
         j.salary_min, j.salary_max, j.salary_months, j.experience, j.education, j.jd,
         j.source, j.source_url, j.source_job_id,
         j.posted_at.isoformat() if j.posted_at else None,
         j.first_seen_at.isoformat(timespec="seconds"),
         j.last_verified_at.isoformat(timespec="seconds") if j.last_verified_at else None,
         j.status.value),
    )


def get_job(conn: sqlite3.Connection, job_id: str) -> Job | None:
    row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    return _job_from_row(row) if row else None


def list_jobs(conn: sqlite3.Connection, city: str | None = None,
              keyword: str | None = None,
              company_id: str | None = None,
              job_type: str | None = None) -> list[Job]:
    rows = conn.execute("SELECT * FROM jobs ORDER BY first_seen_at DESC").fetchall()
    out = [_job_from_row(r) for r in rows]
    if city:
        out = [j for j in out if j.city == city]
    if company_id:
        out = [j for j in out if j.company_id == company_id]
    if job_type:
        out = [j for j in out if j.job_type and j.job_type.value == job_type]
    if keyword:
        kw = keyword.lower()
        out = [j for j in out if kw in (j.title + (j.jd or "")).lower()]
    return out


def update_job_status(conn: sqlite3.Connection, job_id: str, status: str,
                      note: str | None = None) -> None:
    conn.execute(
        "UPDATE jobs SET status=?, last_verified_at=? WHERE id=?",
        (status, NOW(), job_id),
    )
    conn.execute(
        "INSERT INTO job_status_history (job_id, status, checked_at, note) VALUES (?,?,?,?)",
        (job_id, status, NOW(), note),
    )


def _job_from_row(r: sqlite3.Row) -> Job:
    from ..models import JobStatus, JobType
    from datetime import date, datetime

    def _dt(value):
        try:
            return datetime.fromisoformat(value) if value else None
        except ValueError:
            return None

    return Job(
        id=r["id"], company_id=r["company_id"], title=r["title"], city=r["city"],
        location_detail=r["location_detail"],
        job_type=JobType(r["job_type"]) if r["job_type"] else None,
        salary_min=r["salary_min"],
        salary_max=r["salary_max"], salary_months=r["salary_months"],
        experience=r["experience"], education=r["education"], jd=r["jd"],
        source=r["source"], source_url=r["source_url"],
        source_job_id=r["source_job_id"],
        posted_at=date.fromisoformat(r["posted_at"]) if r["posted_at"] else None,
        first_seen_at=_dt(r["first_seen_at"]) or datetime.now(),
        last_verified_at=_dt(r["last_verified_at"]),
        status=JobStatus(r["status"]),
    )


# ---------------------------------------------------------------- research

def _insert_fact(conn: sqlite3.Connection, table: str, values: dict) -> None:
    """Ignore exact repeat imports; retain differing facts side by side.

    Table/column names come only from the fixed mappings below. IS compares
    NULL values too, so undated funding events are also idempotent.
    """
    columns = ", ".join(values)
    placeholders = ", ".join("?" for _ in values)
    match = " AND ".join(f"{column} IS ?" for column in values)
    params = tuple(values.values())
    conn.execute(
        f"INSERT INTO {table} ({columns}) SELECT {placeholders} "
        f"WHERE NOT EXISTS (SELECT 1 FROM {table} WHERE {match})",
        params + params,
    )


def add_funding(conn: sqlite3.Connection, f: FundingEvent) -> None:
    _insert_fact(conn, "funding_events", {
        "company_id": f.company_id, "date": f.date.isoformat() if f.date else None,
        "round": f.round, "amount": f.amount, "currency": f.currency,
        "investors": jdump(sorted(set(f.investors))), "note": f.note,
    })


def list_funding(conn: sqlite3.Connection, company_id: str) -> list[FundingEvent]:
    from datetime import date
    rows = conn.execute(
        "SELECT * FROM funding_events WHERE company_id=? ORDER BY date DESC",
        (company_id,),
    ).fetchall()
    return [FundingEvent(
        company_id=r["company_id"],
        date=date.fromisoformat(r["date"]) if r["date"] else None,
        round=r["round"], amount=r["amount"], currency=r["currency"],
        investors=jload(r["investors"], []), note=r["note"],
    ) for r in rows]


def add_founder(conn: sqlite3.Connection, f: Founder) -> None:
    _insert_fact(conn, "founders", {
        "company_id": f.company_id, "name": f.name, "title": f.title,
        "education": f.education, "career": f.career,
        "relevant_experience": f.relevant_experience,
        "previous_startups": f.previous_startups,
        "source_fact_kind": f.source_fact_kind.value,
    })


def list_founders(conn: sqlite3.Connection, company_id: str) -> list[Founder]:
    rows = conn.execute(
        "SELECT * FROM founders WHERE company_id=?", (company_id,)
    ).fetchall()
    from ..models import FactKind
    return [Founder(
        company_id=r["company_id"], name=r["name"], title=r["title"],
        education=r["education"], career=r["career"],
        relevant_experience=r["relevant_experience"],
        previous_startups=r["previous_startups"],
        source_fact_kind=FactKind(r["source_fact_kind"]),
    ) for r in rows]


def add_product(conn: sqlite3.Connection, p: Product) -> None:
    _insert_fact(conn, "products", {
        "company_id": p.company_id, "name": p.name, "website": p.website,
        "positioning": p.positioning, "core_features": p.core_features,
        "target_users": p.target_users, "scenarios": p.scenarios,
        "traction": p.traction,
    })


def list_products(conn: sqlite3.Connection, company_id: str) -> list[Product]:
    rows = conn.execute(
        "SELECT * FROM products WHERE company_id=?", (company_id,)
    ).fetchall()
    return [Product(
        company_id=r["company_id"], name=r["name"], website=r["website"],
        positioning=r["positioning"], core_features=r["core_features"],
        target_users=r["target_users"], scenarios=r["scenarios"],
        traction=r["traction"],
    ) for r in rows]


def upsert_team_info(conn: sqlite3.Connection, t: TeamInfo) -> None:
    conn.execute(
        """INSERT INTO team_info
           (company_id, size_min, size_max, stage_note, expansion_signals,
            source_fact_kind)
           VALUES (?,?,?,?,?,?)
           ON CONFLICT(company_id) DO UPDATE SET
               size_min=excluded.size_min, size_max=excluded.size_max,
               stage_note=excluded.stage_note,
               expansion_signals=excluded.expansion_signals,
               source_fact_kind=excluded.source_fact_kind""",
        (t.company_id, t.size_min, t.size_max, t.stage_note,
         jdump(t.expansion_signals), t.source_fact_kind.value),
    )


def get_team_info(conn: sqlite3.Connection, company_id: str) -> TeamInfo | None:
    r = conn.execute(
        "SELECT * FROM team_info WHERE company_id=?", (company_id,)
    ).fetchone()
    if not r:
        return None
    from ..models import FactKind
    return TeamInfo(
        company_id=r["company_id"], size_min=r["size_min"], size_max=r["size_max"],
        stage_note=r["stage_note"], expansion_signals=jload(r["expansion_signals"], []),
        source_fact_kind=FactKind(r["source_fact_kind"]),
    )


# ---------------------------------------------------------------- evidence

def add_evidence(conn: sqlite3.Connection, e: Evidence) -> None:
    conn.execute(
        """INSERT INTO evidence
           (entity_type, entity_id, source_type, url, publisher, title, snippet,
            published_at, retrieved_at, trust_note)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (e.entity_type, e.entity_id, e.source_type.value, e.url, e.publisher,
         e.title, e.snippet, e.published_at.isoformat() if e.published_at else None,
         e.retrieved_at.isoformat(timespec="seconds"), e.trust_note),
    )


def list_evidence(conn: sqlite3.Connection, entity_type: str,
                  entity_id: str) -> list[Evidence]:
    from ..models import SourceType
    from datetime import date
    rows = conn.execute(
        "SELECT * FROM evidence WHERE entity_type=? AND entity_id=?",
        (entity_type, entity_id),
    ).fetchall()
    out = []
    for r in rows:
        try:
            retrieved_at = (datetime.fromisoformat(r["retrieved_at"])
                            if r["retrieved_at"] else None)
        except ValueError:
            retrieved_at = None
        out.append(Evidence(
            entity_type=r["entity_type"], entity_id=r["entity_id"],
            source_type=SourceType(r["source_type"]), url=r["url"],
            publisher=r["publisher"], title=r["title"], snippet=r["snippet"],
            published_at=date.fromisoformat(r["published_at"]) if r["published_at"] else None,
            retrieved_at=retrieved_at or datetime.now(),
            trust_note=r["trust_note"],
        ))
    return out


# ---------------------------------------------------------------- scores

def save_score(conn: sqlite3.Connection, s: CompanyScore) -> None:
    conn.execute(
        """INSERT INTO scores
           (company_id, dimensions, coverage, normalized_total, computed_at, note)
           VALUES (?,?,?,?,?,?)""",
        (s.company_id, jdump([d.model_dump() for d in s.dimensions]), s.coverage,
         s.normalized_total, s.computed_at.isoformat(timespec="seconds"), s.note),
    )


def get_latest_score(conn: sqlite3.Connection, company_id: str) -> CompanyScore | None:
    from ..models import FactKind
    r = conn.execute(
        "SELECT * FROM scores WHERE company_id=? ORDER BY computed_at DESC, id DESC LIMIT 1",
        (company_id,),
    ).fetchone()
    if not r:
        return None
    dims = []
    for d in jload(r["dimensions"], []):
        d["fact_kind"] = FactKind(d.get("fact_kind", "verified"))
        dims.append(DimensionScore(**d))
    return CompanyScore(
        company_id=r["company_id"], dimensions=dims, coverage=r["coverage"],
        normalized_total=r["normalized_total"], note=r["note"],
        computed_at=datetime.fromisoformat(r["computed_at"]),
    )
