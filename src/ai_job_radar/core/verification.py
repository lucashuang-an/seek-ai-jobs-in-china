"""Job posting verification. A live page does NOT prove the headcount is
still open — status rules distinguish Listed from Verified Open.

Signal rules (review-hardened):
- Keywords are matched against *visible text only* (script/style/noscript
  stripped) — i18n strings inside JS bundles must not fake a status.
- Open/close signals are only trusted when the page is confirmed to be about
  THIS job (normalized title visible, or the source job id present). A generic
  careers homepage with an "Apply now" button is not a Verified Open.
- Access-blocked pages (login walls, anti-bot 404 shells) are Unknown —
  "we cannot see it" is never "the job is closed".
"""

from __future__ import annotations

import re

import httpx

from ..models import Job, JobStatus
from ..storage import repository as repo

_STRIP_RE = re.compile(r"(?is)<(script|style|noscript|svg|template)[^>]*>.*?</\1>")
_TAG_RE = re.compile(r"(?s)<[^>]+>")
_PUNCT_RE = re.compile(
    r"[\s\-—·•（）()【】\[\]|/、,，.。:：;；!！?？\"'“”‘’]")


def visible_text(html: str) -> str:
    """Human-visible text: strip script/style blocks first, then all tags."""
    return _TAG_RE.sub(" ", _STRIP_RE.sub(" ", html))


def _identity_key(text: str) -> str:
    return _PUNCT_RE.sub("", text or "")


def _identity_confirmed(job: Job, visible: str, raw: str) -> bool:
    """Does this page actually describe THIS job?"""
    if job.source_job_id and job.source_job_id in raw:
        return True
    key = _identity_key(job.title)
    return bool(key) and key in _identity_key(visible)


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
    raw = resp.text
    # 登录墙/风控拦截特征：404 外壳但实为拒绝匿名访问（如小红书 error_code=300031）
    if any(k in raw for k in ["error_code=300031", "当前笔记暂时无法浏览",
                              "登录后查看", "登录后即可访问"]):
        return JobStatus.UNKNOWN, "access blocked (login wall / anti-bot), cannot verify anonymously"
    if resp.status_code == 404:
        return JobStatus.CLOSED, f"HTTP 404 ({resp.url})"
    if resp.status_code != 200:
        return JobStatus.UNKNOWN, f"HTTP {resp.status_code}"

    visible = visible_text(raw)
    identity = _identity_confirmed(job, visible, raw)
    lower = visible.lower()
    if any(k in lower for k in ["职位已关闭", "该职位已关闭", "已停止招聘",
                                "job closed", "position closed",
                                "招聘已结束"]):
        if identity:
            return JobStatus.CLOSED, "page states position closed (identity confirmed)"
        return JobStatus.UNKNOWN, "closed keyword seen but job identity unconfirmed"
    if any(k in lower for k in ["立即沟通", "申请职位", "投递简历", "apply now",
                                "立即申请"]):
        if identity:
            return JobStatus.VERIFIED_OPEN, "page shows active application CTA for this job"
        return JobStatus.LISTED_UNCONFIRMED, "apply CTA present but job identity unconfirmed (generic page?)"
    # Page exists but no explicit open/close signal
    return JobStatus.LISTED_UNCONFIRMED, "page reachable, no open/close signal"


def verify_job(conn, job: Job) -> JobStatus:
    status, note = check_job_url(job)
    repo.update_job_status(conn, job.id, status.value, note)
    return status
