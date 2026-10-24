"""Generate an offline demo from bundled snapshots without touching the user DB.

Run from a source checkout after `python -m pip install -e .`:
    python scripts/demo.py
    python scripts/demo.py --out /path/to/demo-output
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from typer.testing import CliRunner

from ai_job_radar.cli import app
from ai_job_radar.storage import database, repository as repo

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "examples" / "data"
SNAPSHOT = "2026-10-23"
DATASET = f"bundled-snapshot-{SNAPSHOT}"


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if stream and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("demo-output"),
                        help="Separate directory for the demo DB and reports")
    out = parser.parse_args().out.resolve()
    db = out / "demo.db"
    manifest = out / "demo-info.json"
    # Re-running our demo is safe; an unrelated database is never used.
    if db.exists():
        try:
            owned = json.loads(manifest.read_text(encoding="utf-8")).get("dataset") == DATASET
        except (OSError, ValueError):
            owned = False
        if not owned:
            parser.error(f"{db} already exists and is not a managed demo; choose another --out")
    out.mkdir(parents=True, exist_ok=True)
    runner = CliRunner()

    def run(*args: str) -> None:
        result = runner.invoke(app, [*args, "--db", str(db)])
        if result.exit_code:
            raise RuntimeError(f"{' '.join(args)}\n{result.output}") from result.exception

    print("SEEK AI JOBS IN CHINA / offline demo")
    print(f"Historical snapshot: {SNAPSHOT} | No live job verification")
    print()
    print("[1/3] Import bundled companies, jobs, research and scores")
    for command, prefix, groups in (
        ("import-companies", "companies", ("agents", "bigtech", "infra")),
        ("import-jobs", "jobs", ("agents", "bigtech", "infra")),
        ("import-research", "research", ("apps", "foundation", "others")),
        ("import-scores", "scores", ("apps", "foundation", "others")),
    ):
        for group in groups:
            run(command, str(DATA / f"{prefix}_{group}.json"))

    print("[2/3] Export Markdown, JSON and CSV")
    for fmt, name in (("markdown", "report"), ("json", "report"), ("csv", "jobs")):
        run("export", "--format", fmt, "--out", str(out / name))
    report = out / "report.md"
    notice = (
        f"> **历史样例 / Historical demo — {SNAPSHOT}**\n> "
        "本报告使用随仓库提供的数据快照，未联网核验；生成时间不代表岗位仍开放。\n> "
        "Bundled data only. Report generation does not confirm current hiring.\n\n"
    )
    report.write_text(notice + report.read_text(encoding="utf-8"), encoding="utf-8")
    conn = database.get_connection(db)
    try:
        companies = repo.list_companies(conn)
        counts = {
            "companies": len(companies), "jobs": len(repo.list_jobs(conn)),
            "scored_companies": sum(repo.get_latest_score(conn, c.id) is not None
                                    for c in companies),
        }
    finally:
        conn.close()
    manifest.write_text(json.dumps({
        "dataset": DATASET, "snapshot_date": SNAPSHOT, "live_verified": False,
        "generated_at": datetime.now(timezone.utc).isoformat(), **counts,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[3/3] Ready")
    print(f"{counts['companies']} companies | {counts['jobs']} jobs | "
          f"{counts['scored_companies']} scored profiles")
    for name in ("report.md", "report.json", "jobs.csv", "demo.db", "demo-info.json"):
        print(f"  {name}")
    print(f"\nOpen: {report}")
    print("Next: ask your host agent to research fresh opportunities using SKILL.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
