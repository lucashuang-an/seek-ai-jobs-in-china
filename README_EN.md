<p align="center">
  <img src="docs/assets/banner.png" alt="Seek AI Jobs in China — Discover companies. Understand the opportunity." width="100%">
</p>

<h1 align="center">Seek AI Jobs in China</h1>

<p align="center">
  <strong>An Agent Skill for finding AI jobs in China.</strong><br>
  Big tech & startups · Experienced hires, graduate roles & internships<br>
  Use with Codex, Trae, Zcode, Workbuddy and other agents.
</p>

<p align="center">
  <a href="https://github.com/lucashuang-an/seek-ai-jobs-in-china/actions/workflows/checks.yml"><img src="https://github.com/lucashuang-an/seek-ai-jobs-in-china/actions/workflows/checks.yml/badge.svg" alt="Checks"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/Python-3.11%2B-173F35?logo=python&logoColor=white" alt="Python 3.11+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache--2.0-173F35" alt="Apache-2.0 License"></a>
  <a href="SKILL.md"><img src="https://img.shields.io/badge/Agent_Skill-%2B_CLI-E67E42" alt="Agent Skill + CLI"></a>
</p>

<p align="center">
  <a href="README.md">简体中文</a> · English<br><br>
  <a href="#quickstart">Quickstart</a> · <a href="#examples">See the output</a> ·
  <a href="#agent">Try with your agent</a> · <a href="CONTRIBUTING.md">Contribute</a>
</p>

---

**Find AI roles at big tech companies and startups in mainland China, from experienced hires to graduate roles and internships.** Connect each opportunity with company funding, founders, products and hiring evidence, then use traceable reports to compare your options.

~~~text
“Find AI product roles in Beijing. Research each company's funding, team and
 products, then make a report with sources. Flag what you cannot confirm.”
~~~

## What you get

| Your question | What the workflow brings together |
|---|---|
| Who is hiring, and where? | Actual work city, employment type, job description, salary and status |
| What is the company building? | Funding history, founders, team size and products |
| Where can I discover opportunities? | Company websites, public job listings and optional supplementary sources |
| Why should I trust a conclusion? | Source URLs, retrieval dates, fact/inference labels, scoring rationale and coverage |

**Company-first · Evidence-based · Local-first.** Store data in your own SQLite database and export Markdown, JSON or CSV.

<a id="quickstart"></a>
## Quickstart: generate your first report

**Requires Git and Python 3.11+.** Once installed, the demo runs on bundled historical data with no model API key, browser login or online collection.

~~~bash
git clone https://github.com/lucashuang-an/seek-ai-jobs-in-china.git
cd seek-ai-jobs-in-china
~~~

<details>
<summary><strong>Windows · PowerShell</strong></summary>

~~~powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e .
./.venv/Scripts/python.exe scripts/demo.py
~~~

</details>

<details open>
<summary><strong>macOS / Linux</strong></summary>

~~~bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python scripts/demo.py
~~~

</details>

Open **`demo-output/report.md`**. The demo uses a separate `demo-output/demo.db` and never writes to your default personal database.

<p align="center">
  <img src="docs/assets/demo-terminal.svg" alt="Actual demo: 20 companies, 58 jobs and 13 scored profiles. Historical snapshot; no live verification." width="920">
</p>

| File | Use it for |
|---|---|
| `demo-output/report.md` | Read or share a company and job research report |
| `demo-output/report.json` | Structured output with job evidence |
| `demo-output/jobs.csv` | Filter roles in Excel or another spreadsheet tool |
| `demo-output/demo-info.json` | Snapshot date, counts and demo metadata |

> **Historical demo, not a live jobs feed.** The preview uses a 2026-10-23 snapshot. Generating a report does not re-verify hiring status. Use the agent workflow below for fresh research.

<a id="examples"></a>
## See the output without installing

| Example | What to look for |
|---|---|
| [Full research report](examples/acceptance_output/report.md) | Company overview, profiles, scores and sources |
| [Moonshot AI company profile](examples/acceptance_output/moonshot.md) | How a single-company report is structured |
| [Startup hiring found on Xiaohongshu](examples/acceptance_output/xhs_omnimind.md) | Public recruiting posts turned into company and job records |
| [Internship CSV](examples/acceptance_output/intern_jobs_20261023.csv) | A spreadsheet-friendly internship shortlist |

These are historical artifacts, mostly in Chinese. Re-check company facts and job status before using them for a career decision.

<a id="agent"></a>
## Try it with your agent

Use with agents such as Codex, Trae, Zcode or Workbuddy. Your environment should support reading `SKILL.md`, running local commands and searching the web. Try this prompt:

~~~text
Read this repository's SKILL.md and follow its workflow.

Find AI product manager / agent product roles in Beijing, with actual work
locations in mainland China. Research each startup's funding, founders,
team and products. Search official careers pages and public job listings;
separate experienced hires, graduate roles and internships.

Keep source URLs and retrieval times. Use null for unknown facts and label
inferences separately. Explain which sources you will query, import the
results locally, then export a Markdown report. Let me sign in myself if
a login wall appears; do not bypass captchas or platform controls.
~~~

Other starting points:

- **Internships:** “Find AI product internships in Shanghai. Separate internships, graduate roles and experienced hires.”
- **Company research:** “Research Moonshot AI's funding, founders and products. Show the gaps.”
- **Compare opportunities:** “Compare these three companies' products, teams and hiring evidence, with sources.”

**The agent discovers, reads and researches. This repository imports, resolves entities, deduplicates, verifies posting pages, calculates scores and exports reports.** CLI `discover` and `jobs` query local data; they do not initiate a web-wide search. Model and browser setup depends on your agent environment.

## Xiaohongshu: another source of hiring signals

This is an **optional supplementary source** requiring your agent's browser-use capability and your own signed-in Xiaohongshu browser session. With both available, public posts can provide early-team recruiting, internship and personal-referral signals. See the [historical examples](examples/data/xhs_jobs_20261023.json).

- **Use the user's browser session:** sign in yourself when your agent reaches a login wall.
- **Keep source context:** distinguish official accounts from personal referrals and record trust notes.
- **Preserve uncertainty:** blocked anonymous access becomes `Unknown`, rather than evidence that a job has closed.

This is a agent workflow, not a standalone Xiaohongshu crawler. See the [source assessment](docs/数据源评估_小红书.md) for capabilities and limits (Chinese).

<a id="cli"></a>
## CLI: import, filter, verify, export

After installation, use `ai-job-radar`. Without activating the environment, invoke the matching virtualenv Python with `-m ai_job_radar.cli`. Query the demo database:

~~~bash
ai-job-radar discover --city 北京 --track "AI Agents" --db demo-output/demo.db
ai-job-radar jobs --city 北京 --keyword "产品经理" --db demo-output/demo.db
ai-job-radar research --company "月之暗面" --db demo-output/demo.db
ai-job-radar export --company "月之暗面" --out demo-output/moonshot --db demo-output/demo.db
~~~

For fresh research, import agent-produced results into your own database:

~~~bash
ai-job-radar import-companies companies.json
ai-job-radar import-jobs jobs.json
ai-job-radar import-research research.json
ai-job-radar import-scores scores.json
ai-job-radar verify --company "公司名"
ai-job-radar export --format markdown --out report
~~~

See [examples/data](examples/data) for input shapes. Default storage: `~/.ai_job_radar/ai_jobs.db`; override it with `--db`. `verify` visits original posting URLs, so results depend on page content and access restrictions.

<details>
<summary><strong>Update, scoring and export rules</strong></summary>

- Company imports preserve omitted fields; explicit `null` or an empty list clears a field.
- Job merges fill gaps and keep source evidence. Different employment types or job IDs on the same platform remain separate.
- Identical research facts are imported once; differing facts are retained.
- Five scoring dimensions: funding 25%, founders 25%, team 15%, product 25%, hiring 10%. Unknown dimensions stay unscored; weights are re-normalized and coverage is reported.
- Source checkouts read `configs/scoring.yaml`; installed packages use bundled defaults. Override with `import-scores scores.json --weights path/to/scoring.yaml`; all five weights must be finite positive numbers.
- `export --city 北京` filters actual work cities in all three formats. JSON job entries contain `{"job": {...}, "evidence": [...]}`.

</details>

<details>
<summary><strong>npm wrapper: local testing</strong></summary>

Use the source-install quickstart above as the primary trial path. The repository also contains an [npm wrapper](npm/README.md) you can test locally; no registry publication is assumed:

~~~bash
npm install -g ./npm
~~~

Requires Node.js 16+, Python 3.11+ and Git. On first use it creates an isolated Python environment and installs the core from GitHub. Set `AI_JOB_RADAR_PKG` to an absolute local checkout path when testing local changes.

</details>

## FAQ

**Why is my first search empty?** A fresh install has no personal data. Run `scripts/demo.py` and query with `--db demo-output/demo.db`, or ask your agent to research and import data.

**Why aren't all jobs Verified Open?** A reachable page does not establish available headcount. Statuses distinguish `Verified Open`, `Listed / Unconfirmed`, `Recently Seen`, `Closed` and `Unknown`.

**Which cities are supported?** Beijing, Shanghai, Shenzhen, Hangzhou, Guangzhou, Chengdu, Nanjing, Wuhan and Suzhou. Other cities are currently filtered on import. Global Remote with unknown actual location is retained as pending verification.

**Do I need another account or API key?** The offline demo and local CLI processing need no model key. Fresh research uses your agent's model and browser capabilities. Sign in through your browser; never import cookies, tokens or private content.

**Does it apply or contact recruiters?** The current scope is discovery and research. Automated applications, resume generation, recruiter messages and recruiting transactions are outside scope. MCP integration is planned.

## Develop and contribute

~~~bash
python -m pip install -e ".[dev]"
python -m pytest -q
python scripts/acceptance_run.py
~~~

Latest local validation: 56 tests and 13 scenario checks passed. The badge above shows live CI status; [historical acceptance notes](docs/验收报告_V0.2.md) are also available.

- [Contributing guide](CONTRIBUTING.md): sources, corrections, code and first-run feedback.
- [Suggest a source](https://github.com/lucashuang-an/seek-ai-jobs-in-china/issues/new?template=source-suggestion.yml): include a public URL and observation date.
- [Share copy and visuals](docs/SHARING.md): introduce the project to someone exploring AI careers.
- [Product and technical plan](docs/产品与技术方案_V1.1.txt): scope and data constraints (Chinese).

If the workflow is useful, [Star the repository](https://github.com/lucashuang-an/seek-ai-jobs-in-china/stargazers) to keep it handy, or contribute a public hiring lead worth researching.

[Apache-2.0](LICENSE) · Independent open-source project, unaffiliated with recruiting platforms or researched companies.
