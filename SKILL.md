---
name: seek-ai-jobs-in-china
description: 发现中国境内正在招聘的 AI 公司与岗位，研究公司融资、创始团队、规模与产品，并输出证据驱动的评分与报告。当用户想找工作、调查 AI 公司背景、比较多家 AI 公司时使用。
---

# Seek AI Jobs in China

开源 AI 招聘情报 Agent：Company-first · Agent-native · Evidence-based · Local-first。

## 适用场景

- 「帮我找北京/上海/深圳…正在招聘 AI 产品经理（或 Agent/算法/运营等）的公司」
- 「调查这家公司：融资、创始人、团队规模、旗下产品」
- 「比较这几家 AI 公司，给我评分和依据」
- 「核验这个岗位还在招吗」

## 工作流（发现 → 研究 → 验证 → 评分 → 报告）

1. **发现公司**：用网络搜索找符合城市/赛道/阶段/规模的 AI 公司，必须找到招聘线索（岗位页、官网招聘页、招聘平台）。
2. **搜索岗位**：岗位实际工作地点必须在中国大陆（默认城市：北京、上海、深圳、杭州、广州、成都、南京、武汉、苏州）。以**实际工作地点**为准，不看公司注册地。中国大陆以外的岗位一律过滤；"Global Remote 实际地点未知"标记为待核验。
3. **研究公司**：融资历史、创始团队、团队规模、旗下产品。区分官方介绍、第三方报道与 AI 推断（`source_fact_kind`: verified / inferred / unknown）。未披露的信息填 null，标记 Unknown，**不得推测**。
4. **验证**：岗位页存在 ≠ 仍在招聘。能打开且有"立即沟通/申请"类信号 → Verified Open；页面在但无开放信号 → Listed / Unconfirmed；明确显示关闭 → Closed；打不开 → Unknown 并记录原因。
5. **评分**：按 Rubric 五维度（融资 25%、创始团队 25%、团队规模与组织 15%、产品与业务 25%、招聘机会质量 10%）打分。证据不足的维度不打分（score=null），缺失维度不计零分；综合分用已评分维度权重归一化，并报告覆盖率。评分不是投资建议。
6. **导出**：Markdown / JSON / CSV，保留来源、时间与可信度。

## 数据落地方式（与 CLI 配合）

Agent 把调研结果写成 JSON 后调用 CLI（先 `pip install -e .`）：

```bash
ai-job-radar import-companies companies.json   # 自动实体合并（别名/英文名）
ai-job-radar import-jobs jobs.json             # 自动去重 + 中国境内地域过滤
ai-job-radar import-research research.json     # 融资/团队/规模/产品 + 证据
ai-job-radar import-scores scores.json         # 计算归一化综合分
ai-job-radar verify --company "公司名"          # 核验岗位状态
ai-job-radar export --format markdown --out report
```

## 硬约束

- 不绕过招聘平台登录、验证码或风控；只使用公开可访问页面或用户手动粘贴的内容。
- 用户 Cookie、凭据、API Key 不进入数据库与报告。
- 同一企业用统一 Company ID + 别名合并；仅凭名称相似不得合并。
- 所有事实保留来源 URL 与检索时间；来源冲突时并列展示冲突，不互相覆盖。
- 数据默认存本地 SQLite（`~/.ai_job_radar/ai_jobs.db`）。

## 评分 Rubric 摘要

- **融资**：最近融资时间/轮次/投资机构背景/与发展阶段匹配/资金可持续性证据。不推算现金储备。
- **创始团队**：产品领域相关经验、技术与商业化能力、互补性、过往交付。区分事实与推断。
- **团队规模**：与阶段匹配、关键职能齐备、扩张公开依据、组织风险。人数多≠分高。
- **产品**：是否落地、目标市场、真实用户/客户证据、差异化、商业化路径。
- **招聘**：岗位真实性、是否核心 AI 业务、JD 清晰度、与阶段匹配。
