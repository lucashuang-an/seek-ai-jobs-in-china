"""Evidence-driven company scoring.

Weights per spec section 4.4. Rules:
- Each dimension may independently be unknown (score=None).
- Missing information is NOT counted as zero.
- Normalized total = sum(score*weight) / sum(weights of scored dims) * 10? No:
  per spec, weights are re-normalized over scored dimensions, total stays 0-10.
- Coverage = sum(weights of scored dims) / sum(all weights).
"""

from __future__ import annotations

import yaml

from ..models import (
    DEFAULT_WEIGHTS,
    SCORE_DIMENSIONS,
    CompanyScore,
    DimensionScore,
    FactKind,
)

RUBRIC_TEXT = {
    "funding": "参考：最近融资时间、轮次、投资机构背景、融资与发展阶段匹配度、资金可持续性公开证据。未披露标记 Unknown，不推算现金储备。",
    "founders": "参考：创始人在产品领域的相关经验、技术与商业化能力、团队互补性、过往执行交付经历。区分官方介绍、第三方报道与 AI 推断。",
    "team": "参考：规模与阶段匹配度、关键职能是否齐备、扩张是否有公开依据、组织风险。人数多不等于分高。",
    "product": "参考：产品是否落地、目标市场是否明确、真实用户/客户证据、差异化证据、商业化路径清晰度。",
    "hiring": "参考：岗位真实性、工作内容是否属核心 AI 业务、JD 清晰度、岗位与阶段匹配度。",
}

DIMENSION_LABELS = {
    "funding": "融资",
    "founders": "创始团队",
    "team": "团队规模",
    "product": "产品业务",
    "hiring": "招聘机会",
}


def load_weights(path: str | None = None) -> dict[str, float]:
    if path:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        weights = data.get("weights", {})
        if weights:
            return {d: float(weights.get(d, 0)) for d in SCORE_DIMENSIONS}
    return dict(DEFAULT_WEIGHTS)


def compute_score(company_id: str, dimensions: list[DimensionScore],
                  weights: dict[str, float] | None = None,
                  note: str | None = None) -> CompanyScore:
    """Re-normalize weights over scored dimensions; report coverage."""
    weights = weights or dict(DEFAULT_WEIGHTS)
    unknown = sorted({d.dimension for d in dimensions
                      if d.dimension not in SCORE_DIMENSIONS})
    if unknown:
        raise ValueError(
            f"未知评分维度: {unknown}，有效维度: {SCORE_DIMENSIONS}")
    for d in dimensions:
        d.weight = weights.get(d.dimension, 0)
    total_w = sum(weights.values())
    scored_w = sum(d.weight for d in dimensions if d.score is not None)
    coverage = scored_w / total_w if total_w else 0.0
    if scored_w > 0:
        normalized_total = round(
            sum(d.score * d.weight for d in dimensions if d.score is not None)
            / scored_w, 2)
    else:
        normalized_total = None  # 证据不足时不输出综合分
    return CompanyScore(
        company_id=company_id, dimensions=dimensions, coverage=round(coverage, 2),
        normalized_total=normalized_total, note=note,
    )
