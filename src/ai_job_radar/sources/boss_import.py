"""Manual BOSS直聘 import: paste job text/URLs from the platform.
Never bypasses login, captcha, or platform risk controls."""

from __future__ import annotations

import re
from datetime import datetime

from ..models import Job, JobStatus

SALARY_RE = re.compile(r"(\d+)[kK][-—~](\d+)[kK](?:·(\d+)薪)?")


def parse_pasted_job(text: str, company_id: str, source_url: str | None,
                     job_id: str | None = None) -> Job:
    """Best-effort structured extraction from a manually pasted JD."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    title = lines[0] if lines else "Unknown"
    salary = SALARY_RE.search(text)
    return Job(
        id=job_id or f"manual-{abs(hash(text)) % 10**10}",
        company_id=company_id,
        title=title,
        city="北京",  # must be confirmed by user on import
        salary_min=int(salary.group(1)) if salary else None,
        salary_max=int(salary.group(2)) if salary else None,
        salary_months=int(salary.group(3)) if salary and salary.group(3) else None,
        jd=text,
        source="BOSS直聘(手动导入)",
        source_url=source_url,
        status=JobStatus.RECENTLY_SEEN,
    )
