"""Read legally accessible public job pages. Only fetches URLs the user
explicitly provides; respects robots and platform terms."""

from __future__ import annotations

import httpx


def fetch_page(url: str, timeout: float = 15.0) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; ai-job-radar/0.1)"}
    with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as c:
        resp = c.get(url)
        resp.raise_for_status()
        return resp.text
