"""MCP server entry point (Phase 3).

Exposes the same Python Core functions as MCP tools. CLI / Skill / MCP all
call into ai_job_radar core to avoid duplicate maintenance.
"""

from __future__ import annotations

# V0.1 placeholder: MCP SDK wiring lands in Phase 3 (V0.3).
# The tool surface mirrors cli.py commands:
#   discover_ai_companies / search_ai_jobs / research_company /
#   score_company / verify_job / export_report
