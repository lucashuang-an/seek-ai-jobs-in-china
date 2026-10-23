#!/usr/bin/env node
/**
 * ai-job-radar — npm shim around the Python core.
 *
 * On first run it creates a dedicated virtualenv (~/.ai_job_radar/venv),
 * pip-installs the Python package, then forwards every argument to
 * `python -m ai_job_radar.cli`. No postinstall script, no global pollution:
 * everything lives under ~/.ai_job_radar.
 *
 * Env overrides:
 *   AI_JOB_RADAR_PKG   — install source (PyPI name, git+URL, or local path).
 *                        Default: GitHub repo of this project.
 *   AI_JOB_RADAR_VENV  — venv location. Default: ~/.ai_job_radar/venv
 *   PYTHON             — prefer this Python interpreter.
 *
 * Subcommand: `ai-job-radar upgrade` — force pip install -U of the source.
 */

"use strict";

const { spawnSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

function log(msg) { process.stderr.write(`[ai-job-radar] ${msg}\n`); }

/** Well-known Windows install dirs (python.org defaults, not on PATH often). */
function windowsPythonCandidates() {
  const out = [];
  const roots = [path.join(process.env.LOCALAPPDATA || "", "Programs", "Python"),
                 "C:\\Python313", "C:\\Python312", "C:\\Python311"];
  for (const dir of [roots[0]]) {
    try {
      for (const name of fs.readdirSync(dir).sort().reverse()) {
        const exe = path.join(dir, name, "python.exe");
        if (fs.existsSync(exe)) out.push(exe);
      }
    } catch (_) { /* dir absent */ }
  }
  for (const exe of roots.slice(1)) if (fs.existsSync(exe)) out.push(exe);
  return out;
}

function pythonOk(cmd) {
  const r = spawnSync(cmd[0], ["--version"].concat(cmd.slice(1)),
                      { encoding: "utf8", shell: process.platform === "win32" });
  const out = `${r.stdout || ""}${r.stderr || ""}`;
  const m = out.match(/Python (\d+)\.(\d+)/);
  if (r.status === 0 && m) {
    const [major, minor] = [parseInt(m[1], 10), parseInt(m[2], 10)];
    if (major > 3 || (major === 3 && minor >= 11)) return true;
    log(`found ${out.trim()} but >=3.11 is required, trying next...`);
  }
  return false;
}

/** Find a Python >= 3.11 interpreter (venv not required yet). */
function findPython() {
  const fromPath = process.env.PYTHON
    ? [[process.env.PYTHON]]
    : process.platform === "win32"
      ? [["py", "-3"], ["python"], ["python3"]]
      : [["python3"], ["python"]];
  for (const cmd of fromPath) if (pythonOk(cmd)) return cmd;
  for (const exe of windowsPythonCandidates()) if (pythonOk([exe])) return [exe];
  return null;
}

const DEFAULT_PKG = "git+https://github.com/lucashuang-an/seek-ai-jobs-in-china.git";
const pkgSource = process.env.AI_JOB_RADAR_PKG || DEFAULT_PKG;
const venvDir = process.env.AI_JOB_RADAR_VENV ||
  path.join(os.homedir(), ".ai_job_radar", "venv");
const venvPython = process.platform === "win32"
  ? path.join(venvDir, "Scripts", "python.exe")
  : path.join(venvDir, "bin", "python");

function ensureVenv() {
  if (fs.existsSync(venvPython)) return true;
  const py = findPython();
  if (!py) {
    log("no Python >= 3.11 found. Install Python from https://python.org ");
    log("(or set PYTHON=/path/to/python3.11+), then retry.");
    return false;
  }
  log(`creating virtualenv at ${venvDir} ...`);
  const r = spawnSync(py[0], ["-m", "venv", venvDir].concat(py.slice(1)),
                      { stdio: "inherit" });
  return r.status === 0;
}

function coreInstalled() {
  const r = spawnSync(venvPython, ["-c", "import ai_job_radar"],
                      { encoding: "utf8" });
  return r.status === 0;
}

function pipInstall(upgrade) {
  const args = ["-m", "pip", "install", "--disable-pip-version-check", "--quiet"];
  if (upgrade) args.push("--upgrade");
  args.push(pkgSource);
  log(`${upgrade ? "upgrading" : "installing"} Python core from ${pkgSource} ...`);
  const r = spawnSync(venvPython, args, { stdio: "inherit" });
  if (r.status !== 0) {
    log("pip install failed. If the network blocks GitHub/PyPI, try a mirror:");
    log('  set PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple   (Windows)');
    log("  export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple  (macOS/Linux)");
    log("or point at a local checkout:  AI_JOB_RADAR_PKG=/path/to/seek-ai-jobs-in-china");
  }
  return r.status === 0;
}

function main() {
  const args = process.argv.slice(2);

  if (!ensureVenv()) process.exit(1);

  if (args[0] === "upgrade") {
    if (!pipInstall(true)) process.exit(1);
    log("done.");
    process.exit(0);
  }

  if (!coreInstalled() && !pipInstall(false)) process.exit(1);

  const r = spawnSync(venvPython, ["-m", "ai_job_radar.cli"].concat(args),
                      { stdio: "inherit" });
  // Typer exits with 2 on bad usage; propagate whatever the CLI returned.
  process.exit(r.status === null ? 1 : r.status);
}

main();
