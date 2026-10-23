# Seek AI Jobs in China

[English](README_EN.md) | 中文

开源 AI 招聘情报 Agent —— 发现中国境内正在招聘的 AI 公司，研究融资、创始团队、团队规模与产品，输出证据驱动的评分与报告。

**Company-first · Agent-native · Evidence-based · Local-first**

> Discover AI Jobs. Research Companies. Make Informed Career Decisions.

## 🔍 差异化能力：小红书信源

**大量 AI 初创不投招聘平台，只在小红书发帖找人。** 本项目是首个把小红书作为一等信源的求职情报工具（2026-10 实测跑通）：

- **登录墙协作模式**：遇到登录墙自动弹出页面 → 用户扫码登录（凭据零存储）→ Agent 在用户会话内继续采集；
- **独占信号**：捞到招聘平台之外的一手帖——清华孵化初创 800 元/天实习岗、早期团队"创始成员通道"、前实习生招继任帖等，发帖 28 分钟内即可入库；
- **证据分级**：官方账号帖与个人内推帖分可信度标注；小红书链接匿名核验被拦截时如实标记 `Unknown (access blocked)`，绝不误判为已关闭；
- **合规边界**：不绕过登录/验证码/风控，只读用户本人已认证会话中的公开内容。

实测样本见 [examples/data/xhs_jobs_20261023.json](examples/data/xhs_jobs_20261023.json)，可行性评估见 [docs/数据源评估_小红书.md](docs/数据源评估_小红书.md)。

## 它解决什么问题

国内 AI 招聘信息分散在 BOSS 直聘、企业官网、融资报道、投资机构 Portfolio、创始人社交媒体等渠道。找到一份"AI 产品经理"JD 很容易，但弄清这家公司是否真做 AI、融到哪轮、创始团队是谁、产品是否落地，需要大量交叉检索。本项目让你的个人 AI Agent 替你做这件事。

**本项目不做**：自动投递、私信 HR、简历生成、面试日程、企业入驻、付费会员、集中式招聘平台。

## 快速开始

**方式一：npm（推荐，命令行一键安装）**

```bash
npm install -g ai-job-radar     # 发布后可用；首次运行自动创建独立 Python 虚拟环境
ai-job-radar discover --city 北京 --hiring-only
```

只需本机装有 Python ≥ 3.11（自动探测，无需配置 PATH）；详见 [npm/README.md](npm/README.md)。
发布前的本地测试：`cd npm && npm pack && npm install -g ./ai-job-radar-0.1.0.tgz`。

**方式二：pip**

```bash
pip install -e ".[dev]"
pytest                          # 运行测试
python scripts/acceptance_run.py --keep   # 一键场景验收（示例数据端到端）
ai-job-radar jobs --city 北京 --keyword "AI产品经理"
ai-job-radar export --format markdown --out report
```

数据存于本地 SQLite（`~/.ai_job_radar/ai_jobs.db`），不依赖任何云服务。评分导入无需提供权重，默认读取 `configs/scoring.yaml`。

## 使用方式

### 1. CLI

```bash
ai-job-radar discover --city 北京 --track "AI Agents" --team-min 10 --team-max 200
ai-job-radar jobs --city 北京 --keyword "Agent"
ai-job-radar research --company "月之暗面"              # JSON 结构化研究
ai-job-radar export --company "月之暗面" --out moonshot  # 单公司 Markdown 档案
ai-job-radar score --company "月之暗面"
ai-job-radar verify --job-id <id>        # 检查原始页面并分类岗位状态
ai-job-radar verify --company "月之暗面"
ai-job-radar export --format json --out report
```

岗位状态核验直接访问原始来源页并分类：有申请信号 → Verified Open；页面可达无信号 → Listed / Unconfirmed；明确关闭 → Closed；不可达 → Unknown（原因入状态历史）。仅标注 Global Remote、实际地点未知的岗位保留入库并标记待核验。

### 2. Agent Skill

把本仓库安装到支持 Agent Skills 的环境（如 Codex / Claude Code），SKILL.md 定义了适用场景、工具调用顺序、中国工作地点硬约束、证据与评分要求。用户用自然语言发起任务即可。

### 3. MCP（Phase 3 规划）

CLI / Skill / MCP 共用同一 Python Core。

## 架构

```text
Agent (Codex / Claude Code / ...)
        │  SKILL.md / CLI
        ▼
   Python Core (Typer CLI, Pydantic models)
        │
   Discovery & Search → Source Adapters → Entity Resolution
   → Evidence Extraction → Verification → Research & Scoring
        │
   SQLite Cache → Markdown / JSON / CSV
```

- **确定性工具**（本仓库）：采集、解析、过滤、实体匹配、去重、存储、评分计算。
- **LLM 任务**（宿主 Agent 执行）：非结构化信息抽取、公司归纳、评分解释、报告撰写。产出 JSON 经 `import-*` 命令入库。

## 岗位状态定义

| 状态 | 含义 |
|---|---|
| Verified Open | 有明确证据证明岗位当前开放 |
| Listed / Unconfirmed | 职位页存在，但无法确认 HC |
| Recently Seen | 近期发现，尚未完成最新核验 |
| Closed | 已确认停止招聘 |
| Unknown | 证据不足 |

## 目录结构

```text
seek-ai-jobs-in-china/
├── SKILL.md                    # Agent Skill 定义（宿主 Agent 按此执行工作流）
├── src/ai_job_radar/           # Python Core（CLI / 存储 / 去重 / 评分 / 导出）
│   ├── cli.py                  #   Typer CLI（10 个命令）
│   ├── core/                   #   发现、实体合并、去重、岗位核验
│   ├── sources/                #   官网 / 公开岗位 / BOSS 手动导入适配
│   ├── research/ scoring/      #   研究报告组装、评分计算（权重归一化）
│   └── storage/                #   SQLite（schema + repository）
├── npm/                        # npm 发行壳（npm install -g ai-job-radar）
├── configs/scoring.yaml        # 评分权重配置
├── scripts/acceptance_run.py   # 一键场景验收脚本
├── examples/data/              # 示例数据（3 赛道组 + 真实发现样例）
├── examples/acceptance_output/ # 验收产物（report.md/json、jobs.csv）
├── tests/                      # pytest（18 项：去重/评分/导出/地域过滤…）
└── docs/                       # 产品方案 V1.1、验收报告
```

- [docs/产品与技术方案_V1.1.txt](docs/产品与技术方案_V1.1.txt) — 产品与技术方案
- [docs/验收报告_V0.2.md](docs/验收报告_V0.2.md) — 场景验收结果（13/13 通过）
- [scripts/acceptance_run.py](scripts/acceptance_run.py) — 一键验收脚本
- [examples/](examples/) — 示例数据与验收产物

## 硬约束与隐私

- 岗位**实际工作地点**在中国大陆（第一版城市：北京、上海、深圳、杭州、广州、成都、南京、武汉、苏州）；中国大陆以外岗位过滤，仅标注 Global Remote 的岗位保留并标记待核验。
- 不绕过招聘平台登录/验证码/风控；支持手动粘贴导入 JD。
- 凭据与 Cookie 不入库、不导出；所有事实保留来源 URL 与检索时间，来源冲突并列展示。
- 证据不足的维度不打分（score=null），综合分用已评分维度权重归一化并报告覆盖率。

## License

[Apache-2.0](LICENSE)
