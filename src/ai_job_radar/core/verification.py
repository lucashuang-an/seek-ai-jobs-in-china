"""Job posting verification. A live page does NOT prove the headcount is
still open — status rules distinguish Listed from Verified Open."""

from __future__ import annotations

import httpx

from ..models import Job, JobStatus
from ..storage import repository as repo


def check_job_url(job: Job, timeout: float = 15.0) -> tuple[JobStatus, str]:
    """Fetch the original posting URL and classify status.

    Returns (status, note). Network failures return (Unknown, reason).
    """
    if not job.source_url:
        return JobStatus.UNKNOWN, "no source URL"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; ai-job-radar/0.1)"}
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout,
                          headers=headers) as client:
            resp = client.get(job.source_url)
    except Exception as exc:  # network failure -> Unknown, with reason
        return JobStatus.UNKNOWN, f"fetch failed: {exc.__class__.__name__}"
    if resp.status_code == 404:
        return JobStatus.CLOSED, f"HTTP 404 ({resp.url})"
    if resp.status_code != 200:
        return JobStatus.UNKNOWN, f"HTTP {resp.status_code}"
    body = resp.text.lower()
    if any(k in body for k in ["职位已关闭", "该职位已关闭", "已停止招聘",
                               "job closed", "position closed",
                               "招聘已结束"]):
        return JobStatus.CLOSED, "page states position closed"
    if any(k in body for k in ["立即沟通", "申请职位", "投递简历", "apply now",
                               "立即申请"]):
        return JobStatus.VERIFIED_OPEN, "page shows active application CTA"
    # Page exists but no explicit open/close signal
    return JobStatus.LISTED_UNCONFIRMED, "page reachable, no open/close signal"


def verify_job(conn, job: Job) -> JobStatus:
    status, note = check_job_url(job)
    repo.update_job_status(conn, job.id, status.value, note)
    return status
