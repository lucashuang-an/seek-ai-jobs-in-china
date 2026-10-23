# ai-job-radar (npm wrapper)

npm 发行壳：`npm install -g ai-job-radar` 或 `npx ai-job-radar` 即可使用，无需手动管理 Python 环境。

首次运行时自动在 `~/.ai_job_radar/venv` 创建独立虚拟环境并安装 Python 核心（默认从 GitHub 仓库安装），之后直接转发所有参数给 CLI，开销为零。

要求：本机有 Python ≥ 3.11（python.org 安装即可）。

## 环境变量

| 变量 | 作用 | 默认 |
|---|---|---|
| `AI_JOB_RADAR_PKG` | Python 包安装源（PyPI 名 / git+URL / 本地路径） | 本项目 GitHub 仓库 |
| `AI_JOB_RADAR_VENV` | venv 位置 | `~/.ai_job_radar/venv` |
| `PYTHON` | 指定 Python 解释器 | 自动探测（py -3 / python3 / python） |

## 子命令

- `ai-job-radar upgrade` — 强制升级 Python 核心
- 其余参数原样透传，如 `ai-job-radar jobs --city 上海 --keyword 产品经理`

## 本地测试（未发布到 npm registry 前）

```bash
cd npm
npm pack                       # 生成 ai-job-radar-0.1.0.tgz
npm install -g ./ai-job-radar-0.1.0.tgz
ai-job-radar --help
AI_JOB_RADAR_PKG=/path/to/本地仓库 ai-job-radar jobs --city 上海   # 离线安装测试
```

网络受限时可配合 pip 镜像：`PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple`。
