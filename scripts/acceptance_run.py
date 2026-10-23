"""V0.2 场景验收运行脚本。

对照《产品与技术方案 V1.1》10.5 第一阶段验收目标，在全新 SQLite 库上
端到端运行：导入 3 组示例数据 → 发现/检索/研究/评分/核验 → 导出
Markdown/JSON/CSV，并自动核对数量目标。

用法：
    python scripts/acceptance_run.py            # 运行并打印结果
    python scripts/acceptance_run.py --keep     # 同时把报告产物留在 examples/acceptance_output/

说明：核验(verify)依赖外网，脚本默认跳过；人工核验步骤见验收报告。
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from typer.testing import CliRunner

from ai_job_radar.cli import app

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "examples" / "data"
RUNNER = CliRunner()

checks: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str) -> None:
    checks.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name} — {detail}")


def run(args: list[str], db: str) -> str:
    result = RUNNER.invoke(app, [*args, "--db", db])
    if result.exception:
        raise result.exception
    return result.output


def main() -> int:
    keep = "--keep" in sys.argv
    out_dir = ROOT / "examples" / "acceptance_output"
    tmp = tempfile.mkdtemp(prefix="ai_job_radar_acc_")
    db = str(Path(tmp) / "acceptance.db")
    out_base = out_dir if keep else Path(tmp)
    print(f"== 验收运行（临时库：{db}）==\n")

    # ---- 1. 导入 3 组示例数据 -------------------------------------
    print("[导入] 公司 / 岗位 / 研究 / 评分")
    for group in ("agents", "bigtech", "infra"):
        run(["import-companies", str(DATA / f"companies_{group}.json")], db)
    for group in ("agents", "bigtech", "infra"):
        run(["import-jobs", str(DATA / f"jobs_{group}.json")], db)
    for group in ("apps", "foundation", "others"):
        run(["import-research", str(DATA / f"research_{group}.json")], db)
    for group in ("apps", "foundation", "others"):
        run(["import-scores", str(DATA / f"scores_{group}.json")], db)

    # 幂等性（去重）：重复导入同组公司应全部合并、岗位新增 0
    print("[去重] 重复导入 agents 组验证幂等")
    out = run(["import-companies", str(DATA / "companies_agents.json")], db)
    check("公司实体去重（重复导入全合并）", "已导入 10 家公司" in out, out.strip())
    out = run(["import-jobs", str(DATA / "jobs_agents.json")], db)
    check("岗位去重（重复导入新增 0）", "新增 0" in out, out.strip())

    # 地域过滤 + Global Remote 待核验（注入合成记录演示，非示例数据）
    print("[地域] 注入合成岗位验证过滤与待核验")
    synthetic = [
        {"id": "acc-out-of-scope", "company_id": "moonshot",
         "title": "新加坡 Office PM", "city": "新加坡", "source": "官网"},
        {"id": "acc-remote-pending", "company_id": "moonshot",
         "title": "Global Remote PM", "city": "全球远程", "source": "官网"},
    ]
    syn_file = Path(tmp) / "synthetic_jobs.json"
    syn_file.write_text(json.dumps(synthetic, ensure_ascii=False), encoding="utf-8")
    out = run(["import-jobs", str(syn_file)], db)
    check("中国大陆以外岗位被过滤", "地域过滤 1" in out, out.strip())
    out = run(["jobs", "--keyword", "Remote PM"], db)
    check("Global Remote 保留为待核验", "Global Remote PM" in out, "岗位可检索")

    # ---- 2. 发现与检索 ---------------------------------------------
    print("\n[发现] discover / jobs")
    out = run(["discover", "--city", "北京", "--hiring-only"], db)
    n_hiring = len([l for l in out.splitlines() if l and not l.startswith("共")])
    check("发现 ≥20 家有招聘线索企业", n_hiring >= 20, f"{n_hiring} 家")
    out = run(["discover", "--city", "北京", "--track", "AI Agents",
               "--team-min", "10", "--team-max", "200"], db)
    n_track = len([l for l in out.splitlines() if l and not l.startswith("共")])
    check("按赛道/规模组合筛选可用", n_track >= 1, f"AI Agents + 10-200人: {n_track} 家")
    out = run(["jobs", "--city", "北京", "--keyword", "产品经理"], db)
    n_pm = len([l for l in out.splitlines() if l and not l.startswith("共")])
    check("关键词检索岗位", n_pm >= 10, f"“产品经理”命中 {n_pm} 条")

    # ---- 3. 研究与评分 ---------------------------------------------
    print("\n[研究/评分] research / score")
    n_research = 0
    for cid in ("moonshot", "zhipu", "shengshu", "aisphere", "modelbest",
                "baichuan", "deephlang", "paoding", "laiye", "lingxin",
                "langboat", "recurrent", "galaxy-general"):
        out = run(["research", "--company", cid], db)
        report = json.loads(out)
        assert report["company"]["id"] == cid
        n_research += 1
    check("≥10 家企业结构化研究报告（JSON 可解析）", n_research >= 10,
          f"{n_research} 家")
    out = run(["score"], db)
    scored = [l for l in out.splitlines() if "暂无评分" not in l and l.strip()]
    check("≥10 家企业完成证据驱动评分", len(scored) >= 10, f"{len(scored)} 家")

    # ---- 4. 导出 ----------------------------------------------------
    print("\n[导出] markdown / json / csv / 单公司档案")
    run(["export", "--format", "markdown", "--out", str(out_base / "report")], db)
    run(["export", "--format", "json", "--out", str(out_base / "report")], db)
    run(["export", "--format", "csv", "--out", str(out_base / "jobs")], db)
    run(["export", "--format", "markdown", "--out", str(out_base / "moonshot"),
         "--company", "月之暗面"], db)
    md = (out_base / "report.md").read_text(encoding="utf-8")
    payload = json.loads((out_base / "report.json").read_text(encoding="utf-8"))
    csv_rows = (out_base / "jobs.csv").read_text(encoding="utf-8-sig").splitlines()
    check("Markdown 报告生成（含总览+评分+来源）",
          all(s in md for s in ("## 公司总览", "### 评分（证据驱动）", "### 关键来源")),
          f"{len(md.splitlines())} 行")
    check("JSON 报告生成且含研究/评分", len(payload) >= 15
          and all("research" in c and "score" in c for c in payload),
          f"{len(payload)} 家公司")
    check("CSV 岗位表生成", len(csv_rows) > 30, f"{len(csv_rows) - 1} 行数据")
    single = (out_base / "moonshot.md").read_text(encoding="utf-8")
    check("单公司档案导出（场景 B）", "## 月之暗面" in single and "### 融资历史" in single,
          "moonshot.md")

    # ---- 5. 汇总 ----------------------------------------------------
    print("\n" + "=" * 60)
    failed = [c for c in checks if not c[1]]
    for name, ok, detail in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    print("=" * 60)
    print(f"验收结果：{len(checks) - len(failed)}/{len(checks)} 项通过"
          + (f"；未通过 {len(failed)} 项" if failed else "，全部通过 ✅"))
    if keep:
        print(f"报告产物保留在：{out_dir}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
