# Seek AI Jobs in China

English | [中文](README.md)

An open-source AI job-intelligence agent. Discover AI companies hiring in mainland China, research their funding, founders, team size and products, and get evidence-backed scores and reports.

**Company-first · Agent-native · Evidence-based · Local-first**

> Discover AI Jobs. Research Companies. Make Informed Career Decisions.

## Why

AI job postings in China are scattered across job boards, career pages, funding news and investor portfolios. Finding an "AI Product Manager" JD is easy; knowing whether the company is truly AI-first, well-funded, led by a credible founding team, and actually still hiring — that takes hours of cross-checking. This project lets your personal AI agent do it for you.

**Not in scope:** auto-applying, messaging recruiters, resume generation, a centralized job platform.

## Quick Start

```bash
pip install -e ".[dev]"
pytest                                    # run tests
python scripts/acceptance_run.py --keep   # one-shot scenario acceptance (e2e)
ai-job-radar discover --city 北京 --hiring-only
ai-job-radar jobs --city 北京 --keyword "AI产品经理"
ai-job-radar export --format markdown --out report
```

All data lives in a local SQLite file (`~/.ai_job_radar/ai_jobs.db`). No cloud services required.

## Usage

### CLI

```bash
ai-job-radar discover --city 北京 --track "AI Agents" --team-min 10 --team-max 200
ai-job-radar jobs --city 北京 --keyword "Agent"
ai-job-radar research --company "月之暗面"                # structured research (JSON)
ai-job-radar export --company "月之暗面" --out moonshot   # single-company Markdown profile
ai-job-radar score --company "月之暗面"
ai-job-radar verify --company "月之暗面"                  # re-check posting pages & classify status
ai-job-radar export --format json --out report
```

Job-status verification fetches the original posting page: application CTA → **Verified Open**; reachable but no signal → **Listed / Unconfirmed**; explicitly closed → **Closed**; unreachable → **Unknown** (reason recorded). Global-Remote postings with unknown location are kept and flagged pending-verification.

### Agent Skill

Install this repo into any Agent-Skills-capable host (Codex / Claude Code). [SKILL.md](SKILL.md) defines the workflow (discover → research → verify → score → export), the mainland-China location constraint, and evidence & scoring rules. Just talk to your agent in natural language.

### MCP

Planned for Phase 3 — CLI / Skill / MCP share the same Python core.

## Scoring (evidence-driven)

Five dimensions with weights: Funding 25% · Founders 25% · Team 15% · Product 25% · Hiring opportunity 10%.

- Dimensions with insufficient evidence get `score=null` — missing info is never counted as zero.
- The overall score re-normalizes weights over scored dimensions and reports coverage.
- Every score ships with evidence, fact-kind (verified / inferred / unknown) and sources with retrieval dates.

## Hard Constraints & Privacy

- The **actual work location** must be in mainland China (v1 cities: 北京 / 上海 / 深圳 / 杭州 / 广州 / 成都 / 南京 / 武汉 / 苏州). Non-mainland postings are filtered; "Global Remote, location unknown" is kept as pending-verification.
- Never bypass job-platform logins, captchas or anti-bot protections; manual JD paste-in is supported.
- Credentials and cookies never enter the database or reports. Every fact keeps its source URL and retrieval time; conflicting sources are shown side by side.

## Repository Layout

See the [Chinese README](README.md) for a detailed tree. Key paths: `src/ai_job_radar/` (core), `SKILL.md` (agent workflow), `scripts/acceptance_run.py` (acceptance), `examples/data/` (datasets), `docs/` (spec & acceptance report, in Chinese).

## Status

V0.2 — core pipeline accepted end-to-end (13/13 acceptance checks, 18 tests). See [docs/验收报告_V0.2.md](docs/验收报告_V0.2.md).

## License

[Apache-2.0](LICENSE)
