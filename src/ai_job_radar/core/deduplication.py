"""Job deduplication across sources. A job is a duplicate when several key
fields agree; merged duplicates keep all source records."""

from __future__ import annotations

import hashlib
import re

from ..models import Job


def _norm(text: str | None) -> str:
    return re.sub(r"\s+", "", (text or "").lower())


def job_fingerprint(job: Job) -> str:
    """Stable suffix for distinct postings that reuse an import ID."""
    base = "|".join([
        job.company_id, _norm(job.title), job.city,
        job.job_type.value if job.job_type else "",
        job.source, job.source_job_id or job.source_url or "",
    ])
    return hashlib.sha1(base.encode()).hexdigest()[:12]


def jd_similarity(a: str | None, b: str | None) -> float:
    """Cheap Jaccard similarity over character bigrams of JD text.
    Missing/empty JD text yields 0.0 — absence of evidence is not a match."""
    def grams(t: str) -> set:
        t = _norm(t)
        return {t[i:i + 2] for i in range(len(t) - 1)} if len(t) > 1 else {t}
    if not _norm(a) or not _norm(b):
        return 0.0
    ga, gb = grams(a), grams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)


def find_duplicate(job: Job, existing: list[Job], threshold: float = 0.6) -> Job | None:
    # Jaccard over short template JDs is unstable (two one-line JDs sharing a
    # template can cross the threshold) — only trust it on substantive text.
    min_jd_chars = 60
    for e in existing:
        if e.company_id != job.company_id or e.city != job.city:
            continue
        # Intern / campus / full-time postings sharing a title are distinct
        # jobs — job_type conflict blocks the merge entirely.
        if job.job_type and e.job_type and job.job_type != e.job_type:
            continue
        # Different IDs on the same platform are separate postings even
        # when their titles and template descriptions agree.
        if job.source == e.source and job.source_job_id and e.source_job_id:
            if job.source_job_id == e.source_job_id:
                return e
            continue
        if _norm(e.title) == _norm(job.title):
            return e
        if (min(len(_norm(e.jd)), len(_norm(job.jd))) >= min_jd_chars
                and jd_similarity(e.jd, job.jd) >= threshold):
            return e
    return None
