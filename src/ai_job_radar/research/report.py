"""Assemble a company research report from stored evidence-backed data."""

from __future__ import annotations

import sqlite3

from ..storage import repository as repo


def build_research_report(conn: sqlite3.Connection, company_id: str,
                          as_models: bool = False) -> dict:
    """Return the report as a dict of Pydantic models (as_models=True) or
    of JSON-ready dicts (default)."""
    company = repo.get_company(conn, company_id)
    if not company:
        raise ValueError(f"company not found: {company_id}")
    funding = repo.list_funding(conn, company_id)
    founders = repo.list_founders(conn, company_id)
    products = repo.list_products(conn, company_id)
    team = repo.get_team_info(conn, company_id)
    evidence = repo.list_evidence(conn, "company", company_id)
    if as_models:
        return {"company": company, "funding": funding, "founders": founders,
                "team": team, "products": products, "evidence": evidence}
    return {
        "company": company.model_dump(),
        "funding": [f.model_dump() for f in funding],
        "founders": [f.model_dump() for f in founders],
        "team": team.model_dump() if team else None,
        "products": [p.model_dump() for p in products],
        "evidence": [e.model_dump() for e in evidence],
    }
