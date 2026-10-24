# README 与传播入口设计记录

日期：2026-10-24。目标是提高首次访问时的理解与试用完成率；曝光和 Star 增长仍需发布后观察，不能由页面修改保证。

## 参考项目

Star 数为 2026-10-24 GitHub API 读取值，会持续变化。只参考介绍结构，未复用对方视觉资产、文案或背书。

| 项目 | 当日 Star | 借鉴的表达方式 |
|---|---:|---|
| [speedyapply/JobSpy](https://github.com/speedyapply/JobSpy) | 4,549 | 简短定位、可运行示例、真实输出放在参数说明之前 |
| [browser-use/browser-use](https://github.com/browser-use/browser-use) | 118,999 | 鲜明首屏、先展示结果、按使用方式划分入口、可复制的 Agent 需求 |
| [NanmiCoder/MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) | 67,976 | 中国信源的明确定位、功能一览、双语与安装依赖说明 |

## 本项目的落地

1. 原创 banner + 一句用户价值 + 少量真实徽章。
2. 历史报告可直接打开；离线 demo 在专用数据库生成 Markdown / JSON / CSV。
3. Windows 与 macOS/Linux 分开给出无需激活环境的执行命令。
4. 把Agent 联网研究与 CLI 本地处理的职责放到试用路径里。
5. 一句话定位突出国内 AI 岗位 Agent Skill，涵盖大厂与初创公司，支持社招、校招和实习岗位；小红书仅作为可选补充信源说明，并明确依赖 Agent 的 browser use 与用户登录，不进入 About 或首屏定位。
6. 增加公开信源建议表单、贡献说明、可调整的中英文分享文案。
7. About 文案与 topics 保存在 `.github/repository-metadata.json`，便于审阅和重复应用。
8. CI 实际运行测试、demo 与场景验收；README 状态徽章读取运行结果，不静态宣称 CI 已通过。

## Banner

输出：`docs/assets/banner.png`。使用内置 imagegen 工具生成，非 CLI/API fallback。生成提示词见 [banner-prompt.md](assets/banner-prompt.md)。

首屏采用米白、深绿与橙色点缀，雷达连接公司与研究档案，表达“发现公司、读懂机会”。终端图来自实际 demo 输出，仅将本机绝对路径替换为可移植的相对路径。

## 后续可以观察什么

- GitHub Traffic 中的 views、unique visitors、clones 和来源站点；这些数据可能包含平台采样和保留期限制。
- 首次试用反馈：Python 安装、命令执行、找到报告文件、理解历史样例与实时研究的区别。
- Issue 中新增的有效公开信源和改进建议。

本次不添加追踪代码、不虚构下载量、不向外部渠道自动发帖。
