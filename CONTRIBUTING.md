# Contributing / 参与贡献

You can help without writing code. / 不写代码也可以参与。

| Contribution / 方向 | Start here / 从这里开始 |
|---|---|
| A useful company or hiring source / 推荐公司、招聘信源 | [Open a source suggestion](https://github.com/lucashuang-an/seek-ai-jobs-in-china/issues/new?template=source-suggestion.yml) |
| A wrong fact or stale job / 纠错、过期信息 | [Open an issue](https://github.com/lucashuang-an/seek-ai-jobs-in-china/issues/new), include the public URL and observation date |
| First-run friction / 首次安装体验 | Include OS, Python version, command and error; redact private paths and data |
| Code or docs / 代码与文档 | Open an issue describing the change, then submit a focused PR |

## Local development

Use Python 3.11+ in a virtual environment. From the repository root:

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python scripts/demo.py
python scripts/acceptance_run.py
```

The demo uses its own `demo-output/demo.db`. Never commit a personal database or exported research containing private information. / demo 使用独立数据库，不要提交个人数据库或含隐私的研究结果。

## Evidence rules / 证据规则

- Record a public source URL and retrieval time. Distinguish official sources, media, platforms and personal referrals.
- Unknown facts stay unknown. A reachable page alone does not establish that a job is still open.
- Use the job's actual work location; flag unclear Global Remote roles for verification.
- Keep conflicting sources side by side. Do not infer funding, headcount, salary or dates from missing data.
- Do not submit cookies, session tokens, private messages, resumes or credentials. Remove URL session tokens before sharing links.

记录来源与检索时间；未知不猜测、冲突不覆盖。岗位地点以实际工作城市为准。公开页面存在不等于岗位仍在招。遵守登录、验证码与风控边界。

## Sharing / 分享

See [ready-to-adapt copy and visual assets](docs/SHARING.md). When sharing a historical demo, keep the snapshot date and the fact that jobs have not been live verified.
