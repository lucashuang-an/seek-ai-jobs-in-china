"""Company entity resolution: map aliases / English names / product brands
to a stable Company ID. Names must match exactly or via registered alias —
similar names alone never merge."""

from __future__ import annotations

import re
import sqlite3
import unicodedata


def normalize(name: str) -> str:
    n = unicodedata.normalize("NFKC", name).strip().lower()
    return re.sub(r"[\s·•\-\—_（）()【】\[\]]+", "", n)


class CompanyResolver:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def resolve(self, name: str) -> str | None:
        """Return Company ID for an exact alias/normalized match, else None."""
        row = self.conn.execute(
            "SELECT id FROM companies WHERE id=?", (name,)
        ).fetchone()
        if row:
            return row["id"]
        row = self.conn.execute(
            "SELECT company_id FROM company_aliases WHERE alias=?", (name,)
        ).fetchone()
        if row:
            return row["company_id"]
        row = self.conn.execute(
            "SELECT company_id FROM company_aliases WHERE alias=?", (normalize(name),)
        ).fetchone()
        if row:
            return row["company_id"]
        # Older databases registered only the original spelling. Do not
        # choose arbitrarily if normalized legacy aliases are ambiguous.
        matches = {
            r["company_id"] for r in self.conn.execute(
                "SELECT alias, company_id FROM company_aliases")
            if normalize(r["alias"]) == normalize(name)
        }
        return next(iter(matches)) if len(matches) == 1 else None

    def register_alias(self, alias: str, company_id: str) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO company_aliases (alias, company_id) VALUES (?,?)",
            (alias, company_id),
        )
        self.conn.execute(
            "INSERT OR IGNORE INTO company_aliases (alias, company_id) VALUES (?,?)",
            (normalize(alias), company_id),
        )
