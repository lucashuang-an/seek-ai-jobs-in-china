"""Evidence-driven company scoring.

Weights per spec section 4.4. Rules:
- Each dimension may independently be unknown (score=None).
- Missing information is NOT counted as zero.
- Normalized total = sum(score*weight) / sum(weights of scored dims) * 10? No:
  per spec, weights are re-normalized over scored dimensions, total stays 0-10.
- Coverage = sum(weights of scored dims) / sum(all weights).
"""

from __future__ import annotations

from importlib.resources import files
import math
from pathlib import Path

import yaml

from ..models import (
    SCORE_DIMENSIONS,
    CompanyScore,
    DimensionScore,
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


REPO_WEIGHTS_PATH = Path(__file__).resolve().parents[3] / "configs" / "scoring.yaml"


def _validated_weights(weights) -> dict[str, float]:
    if not isinstance(weights, dict) or set(weights) != set(SCORE_DIMENSIONS):
        raise ValueError("评分权重配置无效：须提供 funding/founders/team/product/hiring 五个维度")
    try:
        result = {dim: float(weights[dim]) for dim in SCORE_DIMENSIONS}
    except (TypeError, ValueError) as exc:
        raise ValueError("评分权重配置无效：权重须为有限正数") from exc
    if any(not math.isfinite(w) or w <= 0 for w in result.values()):
        raise ValueError("评分权重配置无效：权重须为有限正数")
    return result


def load_weights(path: str | None = None) -> dict[str, float]:
    config = (Path(path) if path is not None else REPO_WEIGHTS_PATH
              if REPO_WEIGHTS_PATH.is_file() else
              files("ai_job_radar.scoring").joinpath("default_weights.yaml"))
    try:
        with config.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ValueError(f"评分配置不是有效的 YAML: {config}") from exc
    if not isinstance(data, dict):
        raise ValueError("评分权重配置无效：根节点须为映射")
    return _validated_weights(data.get("weights"))


def compute_score(company_id: str, dimensions: list[DimensionScore],
                  weights: dict[str, float] | None = None,
                  note: str | None = None) -> CompanyScore:
    """Re-normalize weights over scored dimensions; report coverage.

    Raises ValueError on duplicate dimensions and on invalid weights
    (every dimension must carry a positive weight, else coverage math
    is meaningless).
    """
    weights = _validated_weights(load_weights() if weights is None else weights)
    seen: set[str] = set()
    for d in dimensions:
        if d.dimension in seen:
            raise ValueError(f"重复评分维度: {d.dimension}（每个维度只允许一条）")
        seen.add(d.dimension)
    unknown = sorted(seen - set(SCORE_DIMENSIONS))
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
