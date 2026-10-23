"""Filtering/discovery helpers over the local database.

Discovery itself (finding companies online) is performed by the host agent
or source adapters; this module applies the structured filters.
"""

from __future__ import annotations

import sqlite3

from ..models import Company, Track
from ..storage import repository as repo


def filter_companies(
    conn: sqlite3.Connection,
    city: str | None = None,
    tracks: list[Track] | None = None,
    company_type: str | None = None,
    funding_stage: str | None = None,
    team_size_min: int | None = None,
    team_size_max: int | None = None,
    hiring_only: bool = False,
) -> list[Company]:
    companies = repo.list_companies(conn)
    out = []
    for c in companies:
        if city and c.city != city:
            continue
        if tracks and not set(tracks) & set(c.tracks):
            continue
        if company_type and c.company_type.value != company_type:
            continue
        if funding_stage and (c.funding_stage or "") != funding_stage:
            continue
        if team_size_min is not None and (c.team_size_max or 0) < team_size_min:
            continue
        if team_size_max is not None and (c.team_size_min or 10**9) > team_size_max:
            continue
        if hiring_only and not repo.list_jobs(conn, company_id=c.id):
            continue
        out.append(c)
    return out
