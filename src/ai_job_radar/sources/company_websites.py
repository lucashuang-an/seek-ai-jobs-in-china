"""Fetch official company pages (careers / about / news)."""

from __future__ import annotations

from .public_jobs import fetch_page


def fetch_careers_page(url: str) -> str:
    return fetch_page(url)
