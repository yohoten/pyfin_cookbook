# -*- coding: utf-8 -*-
"""
sensitivity.py — 投资决策敏感性分析
====================================================================
本模块实现课程第 5 章的 **投资决策敏感性分析**，回答三类问题：

1. **单因素敏感度**（:func:`one_way_sensitivity`）
   分别让折现率、初始投资、年现金流（及项目寿命）上下波动，
   观察 NPV 的变动幅度，量化"哪个因素最要命"。

2. **临界点 / 盈亏平衡分析**（:func:`breakeven_analysis`）
   求解使 NPV 恰好为 0 的临界值：临界折现率、初始投资上限、
   年现金流下限、以及对应的"可承受的最大不利变动幅度"。

3. **双因素联动分析**（:func:`two_way_sensitivity`）
   折现率 × 年现金流 的二维敏感性矩阵，用于绘制热力图，
   识别"可行区 / 不可行区"的分界线。

------------------------------------------------------------------
核心概念：安全边际（Margin of Safety）
------------------------------------------------------------------
    安全边际（百分点） = IRR − 资本成本 r

该值衡量项目"抗风险能力"：
* 安全边际 ≥ 8pp → 抗风险能力强，折现率大幅上升仍可行；
* 安全边际 3~8pp  → 抗风险能力中等；
* 安全边际 1~3pp  → 抗风险能力较弱，需重点关注；
* 安全边际 < 1pp  → 处于可行与不可行的边缘，谨慎决策。

------------------------------------------------------------------
敏感度弹性（Sensitivity Elasticity）
------------------------------------------------------------------
    弹性 e = (ΔNPV / NPV_base) / (ΔX / X_base)

含义为"因素变动 1%，NPV 变动 e%"。弹性为负表示反向影响
（如折现率上升 → NPV 下降）。弹性绝对值越大，该因素越关键。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import finance_core as fc
from .models import Evaluation, Project

__all__ = [
    "FactorSensitivity",
    "SensitivityResult",
    "one_way_sensitivity",
    "rate_sensitivity_table",
    "breakeven_analysis",
    "two_way_sensitivity",
    "risk_grade",
]


# ======================================================================
# 一、数据结构
# ======================================================================
@dataclass
class FactorSensitivity:
    """单个影响因素的敏感性结果。

    Attributes
    ----------
    name : str
        因素名称（折现率 / 初始投资 / 年现金流 / 项目寿命）。
    adverse_npv : float
        因素向 **不利方向** 变动 delta 后的 NPV。
    favorable_npv : float
        因素向 **有利方向** 变动 delta 后的 NPV。
    adverse_label : str
        不利方向的文字说明，如 "折现率 +5.00pp"。
    favorable_label : str
        有利方向的文字说明。
    swing : float
        NPV 波动幅度 = |favorable_npv − adverse_npv|，用于 tornado 图排序。
    adverse_elasticity : float
        不利方向变动的弹性。
    critical : bool
        不利变动后是否使 NPV 由正转负（跨越可行性临界点）。
    """

    name: str
    adverse_npv: float
    favorable_npv: float
    adverse_label: str
    favorable_label: str
    swing: float
    adverse_elasticity: float
    critical: bool = False


@dataclass
class SensitivityResult:
    """一个项目的完整敏感性分析结果。

    Attributes
    ----------
    project : Project
        被分析项目。
    rate : float
        基准折现率。
    delta : float
        扰动幅度（折现率按绝对百分点，其余按相对比例）。
    base_npv : float
        基准 NPV。
    base_irr : float or None
        基准 IRR。
    factors : list of FactorSensitivity
        各因素敏感性结果，按 swing 降序（即 tornado 图从上到下的顺序）。
    safety_margin : float
        安全边际 = IRR − rate（百分点，小数形式）。
    grade : str
        抗风险能力等级。
    breakeven : dict
        临界点分析结果。
    """

    project: Project
    rate: float
    delta: float
    base_npv: float
    base_irr: Optional[float]
    factors: List[FactorSensitivity] = field(default_factory=list)
    safety_margin: float = 0.0
    grade: str = ""
    breakeven: Dict = field(default_factory=dict)


# ======================================================================
# 二、单因素敏感性分析
# ======================================================================
def _npv_with_scaled_cash_flows(project: Project, rate: float, scale: float) -> float:
    """按比例缩放全部各期现金流后计算 NPV。

    Parameters
    ----------
    project : Project
        项目。
    rate : float
        折现率。
    scale : float
        现金流缩放系数（1.05 表示全部现金流上升 5%）。

    Returns
    -------
    float
        NPV。
    """
    scaled = [cf * scale for cf in project.cash_flows]
    return fc.npv(rate, scaled, project.initial_investment)


def _npv_with_investment(project: Project, rate: float, investment: float) -> float:
    """给定初始投资额计算 NPV。"""
    return fc.npv(rate, project.cash_flows, investment)


def risk_grade(safety_margin: float) -> str:
    """按安全边际划分抗风险等级。

    Parameters
    ----------
    safety_margin : float
        安全边际 = IRR − 资本成本（小数形式）。

    Returns
    -------
    str
        等级：强 / 较强 / 中等 / 较弱 / 极弱。
    """
    if safety_margin >= 0.08:
        return "强"
    if safety_margin >= 0.05:
        return "较强"
    if safety_margin >= 0.03:
        return "中等"
    if safety_margin >= 0.01:
        return "较弱"
    return "极弱"


def one_way_sensitivity(
    project: Project,
    rate: float,
    delta: float = 0.20,
    rate_delta_pp: Optional[float] = 0.05,
    include_life: bool = True,
) -> SensitivityResult:
    """对单个项目执行单因素敏感性分析。

    Parameters
    ----------
    project : Project
        待分析项目。
    rate : float
        基准折现率。
    delta : float
        相对扰动幅度，作用于初始投资与年现金流。默认 0.20（±20%）。
    rate_delta_pp : float or None
        折现率的绝对扰动幅度（百分点）。默认 0.05（±5 个百分点），
        与题目要求的"折现率上升 5%"口径一致。None 表示不分析折现率。
    include_life : bool
        是否纳入寿命期敏感性（寿命缩短/延长 1 年）。

    Returns
    -------
    SensitivityResult
        含各因素敏感性、安全边际与临界点分析。

    Notes
    -----
    折现率采用 **绝对百分点** 扰动而非相对比例，原因是折现率的
    "5% 相对上升"（10% → 10.5%）在实践中几乎无意义，行业惯例是
    以百分点衡量利率变动。

    寿命期因素的处理：寿命缩短 1 年即删除最后一期现金流，
    寿命延长 1 年则补入一个等于最后一期的现金流（延续假设）。
    """
    base_npv = project.npv(rate)
    irr_result = project.irr_details()
    base_irr = irr_result.irr
    dollar_base = abs(base_npv) if abs(base_npv) > 1e-9 else 1e-9

    factors: List[FactorSensitivity] = []

    # ---------- 因素 1：折现率（绝对百分点变动） ----------
    if rate_delta_pp is not None:
        adverse_rate = rate + rate_delta_pp
        favorable_rate = rate - rate_delta_pp
        npv_adverse = project.npv(adverse_rate) if adverse_rate > -1 else float("nan")
        npv_favorable = project.npv(favorable_rate) if favorable_rate > -1 else float("nan")
        elasticity = ((npv_adverse - base_npv) / dollar_base) / (rate_delta_pp / rate) if rate else 0.0
        factors.append(FactorSensitivity(
            name="折现率",
            adverse_npv=npv_adverse,
            favorable_npv=npv_favorable,
            adverse_label=f"折现率 +{rate_delta_pp * 100:.2f}pp → {adverse_rate:.2%}",
            favorable_label=f"折现率 −{rate_delta_pp * 100:.2f}pp → {favorable_rate:.2%}",
            swing=abs(npv_favorable - npv_adverse),
            adverse_elasticity=elasticity,
            critical=(base_npv > 0 >= npv_adverse),
        ))

    # ---------- 因素 2：初始投资 ----------
    inv_adverse = project.initial_investment * (1.0 + delta)
    inv_favorable = project.initial_investment * (1.0 - delta)
    npv_adverse = _npv_with_investment(project, rate, inv_adverse)
    npv_favorable = _npv_with_investment(project, rate, inv_favorable)
    factors.append(FactorSensitivity(
        name="初始投资",
        adverse_npv=npv_adverse,
        favorable_npv=npv_favorable,
        adverse_label=f"投资 +{delta:.0%} → {inv_adverse:,.0f} 万元",
        favorable_label=f"投资 −{delta:.0%} → {inv_favorable:,.0f} 万元",
        swing=abs(npv_favorable - npv_adverse),
        adverse_elasticity=((npv_adverse - base_npv) / dollar_base) / delta,
        critical=(base_npv > 0 >= npv_adverse),
    ))

    # ---------- 因素 3：年现金流 ----------
    npv_adverse = _npv_with_scaled_cash_flows(project, rate, 1.0 - delta)
    npv_favorable = _npv_with_scaled_cash_flows(project, rate, 1.0 + delta)
    factors.append(FactorSensitivity(
        name="年现金流",
        adverse_npv=npv_adverse,
        favorable_npv=npv_favorable,
        adverse_label=f"现金流 −{delta:.0%}",
        favorable_label=f"现金流 +{delta:.0%}",
        swing=abs(npv_favorable - npv_adverse),
        adverse_elasticity=((npv_adverse - base_npv) / dollar_base) / delta,
        critical=(base_npv > 0 >= npv_adverse),
    ))

    # ---------- 因素 4：项目寿命（±1 年） ----------
    if include_life:
        if project.life >= 2:
            shorter = Project(
                code=project.code + "-S", name=project.name, industry=project.industry,
                initial_investment=project.initial_investment,
                cash_flows=project.cash_flows[:-1],
            )
            npv_adverse = shorter.npv(rate)
        else:
            npv_adverse = float("nan")
        extended_flows = list(project.cash_flows) + [project.cash_flows[-1]]
        longer = Project(
            code=project.code + "-L", name=project.name, industry=project.industry,
            initial_investment=project.initial_investment, cash_flows=extended_flows,
        )
        npv_favorable = longer.npv(rate)
        factors.append(FactorSensitivity(
            name="项目寿命",
            adverse_npv=npv_adverse,
            favorable_npv=npv_favorable,
            adverse_label=f"寿命 −1 年 → {project.life - 1} 年",
            favorable_label=f"寿命 +1 年 → {project.life + 1} 年",
            swing=abs(npv_favorable - npv_adverse),
            adverse_elasticity=(
                ((npv_adverse - base_npv) / dollar_base) / (1.0 / project.life)
                if project.life and not np.isnan(npv_adverse) else 0.0
            ),
            critical=(base_npv > 0 >= npv_adverse),
        ))

    # 按 swing 降序排列，直接对应 tornado 图的绘制顺序（影响大者在上）
    factors.sort(key=lambda f: f.swing, reverse=True)

    safety = (base_irr - rate) if base_irr is not None else float("nan")
    return SensitivityResult(
        project=project,
        rate=rate,
        delta=delta,
        base_npv=base_npv,
        base_irr=base_irr,
        factors=factors,
        safety_margin=safety,
        grade=risk_grade(safety),
        breakeven=breakeven_analysis(project, rate).get("关键临界值", {}),
    )


# ======================================================================
# 三、折现率敏感性曲线数据
# ======================================================================
def rate_sensitivity_table(
    project: Project,
    rate: float,
    rates: Optional[Sequence[float]] = None,
) -> List[Dict]:
    """生成"折现率 — NPV"敏感性明细表。

    Parameters
    ----------
    project : Project
        项目。
    rate : float
        基准折现率（用于标记基准行）。
    rates : Sequence[float] or None
        待计算的折现率列表。默认取基准值上下对称的 7 个点
        （−4pp、−3pp、−2pp、−1pp、基准、+1pp、+2pp、+3pp、+4pp、+5pp）。

    Returns
    -------
    list of dict
        每行含折现率、NPV、相对基准变动额与是否可行。
    """
    if rates is None:
        rates = [rate + d for d in (-0.04, -0.03, -0.02, -0.01, 0.0,
                                     0.01, 0.02, 0.03, 0.04, 0.05)]
    base = project.npv(rate)
    rows = []
    for r in rates:
        if r <= -1.0:
            continue
        value = project.npv(r)
        rows.append({
            "折现率": f"{r:.2%}",
            "折现率变动": f"{r - rate:+.2%}" if abs(r - rate) > 1e-12 else "基准",
            "NPV(万元)": round(value, 2),
            "相对基准变动(万元)": round(value - base, 2),
            "可行性": "可行" if value > 0 else "不可行",
        })
    return rows


# ======================================================================
# 四、临界点（盈亏平衡）分析
# ======================================================================
def breakeven_analysis(project: Project, rate: float) -> Dict:
    """求解使 NPV = 0 的各因素临界值。

    Parameters
    ----------
    project : Project
        项目。
    rate : float
        基准折现率。

    Returns
    -------
    dict
        含四个关键块：

        * ``基准情况``：基准 NPV、IRR、安全边际；
        * ``临界折现率``：使 NPV = 0 的折现率（数值上等于 IRR）；
        * ``初始投资上限``：现金流现值合计，投资超过该值即不可行；
        * ``年现金流下限``：使 NPV = 0 所需的现金流缩放系数与对应最低
          年均现金流；
        * ``关键临界值``：汇总各因素的"可承受最大不利变动幅度"。
    """
    base_npv = project.npv(rate)
    irr_result = project.irr_details()
    project_irr = irr_result.irr

    # 初始投资上限 = 各期现金流按基准折现率折现的现值合计
    pv_of_inflows = sum(
        cf / (1.0 + rate) ** t for t, cf in enumerate(project.cash_flows, start=1)
    )
    investment_limit = pv_of_inflows

    # 年现金流下限：NPV = 0 → PV(k × CF) = I0 → k* = I0 / PV(CF)
    scale_limit = project.initial_investment / pv_of_inflows if pv_of_inflows > 0 else float("nan")
    avg_cf = float(np.mean(project.cash_flows))
    min_avg_cf = avg_cf * scale_limit

    # 可承受的最大不利变动幅度
    tolerable = {
        "折现率最大可上升幅度(pp)": (
            (project_irr - rate) * 100 if project_irr is not None else float("nan")
        ),
        "初始投资最大可上升幅度": (
            (investment_limit - project.initial_investment) / project.initial_investment
            if project.initial_investment else float("nan")
        ),
        "年现金流最大可下降幅度": (1.0 - scale_limit) if np.isfinite(scale_limit) else float("nan"),
    }

    return {
        "基准情况": {
            "基准折现率": f"{rate:.2%}",
            "基准NPV(万元)": round(base_npv, 2),
            "IRR": f"{project_irr:.2%}" if project_irr is not None else "无实根",
            "IRR唯一性": "唯一" if irr_result.is_unique else f"多重({len(irr_result.all_roots)}个)",
            "安全边际(pp)": round((project_irr - rate) * 100, 2) if project_irr is not None else None,
            "抗风险等级": risk_grade((project_irr - rate) if project_irr is not None else 0.0),
        },
        "临界折现率": {
            "临界值": f"{project_irr:.2%}" if project_irr is not None else "无实根",
            "临界值数值": project_irr,
            "含义": "折现率超过该值后 NPV 转为负值，项目由可行变为不可行",
            "全部实根": (
                [f"{r:.2%}" for r in irr_result.all_roots] if irr_result.all_roots else []
            ),
        },
        "初始投资上限": {
            "现值合计(万元)": round(pv_of_inflows, 2),
            "现值合计数值": pv_of_inflows,
            "基准投资(万元)": round(project.initial_investment, 2),
            "含义": "初始投资超过该上限后 NPV 转为负值",
        },
        "年现金流下限": {
            "最低现金流系数": f"{scale_limit:.4f}" if np.isfinite(scale_limit) else "-",
            "最低现金流系数数值": scale_limit,
            "最低年均现金流(万元)": round(min_avg_cf, 2) if np.isfinite(min_avg_cf) else "-",
            "基准年均现金流(万元)": round(avg_cf, 2),
            "含义": "年现金流低于该水平后 NPV 转为负值",
        },
        "关键临界值": tolerable,
    }


# ======================================================================
# 五、双因素敏感性矩阵
# ======================================================================
def two_way_sensitivity(
    project: Project,
    rate: float,
    rate_deltas: Sequence[float] = (-0.04, -0.02, 0.0, 0.02, 0.04),
    cf_deltas: Sequence[float] = (-0.20, -0.10, 0.0, 0.10, 0.20),
) -> Tuple[List[List[float]], List[float], List[float]]:
    """计算"折现率 × 年现金流"双因素敏感性矩阵。

    Parameters
    ----------
    project : Project
        项目。
    rate : float
        基准折现率。
    rate_deltas : Sequence[float]
        折现率的扰动序列（相对基准的比例）。
    cf_deltas : Sequence[float]
        年现金流的扰动序列（相对基准的比例）。

    Returns
    -------
    (matrix, rate_axis, cf_axis)
        * ``matrix[i][j]``：第 i 个现金流扰动、第 j 个折现率扰动下的 NPV；
        * ``rate_axis``：各列对应的折现率；
        * ``cf_axis``：各行对应的现金流缩放系数。

    Notes
    -----
    矩阵中 NPV 变号的位置即"可行性分界线"，可用于热力图展示。
    基准点（0, 0）对应基准 NPV。
    """
    rate_axis = [rate + d for d in rate_deltas]
    cf_axis = [1.0 + d for d in cf_deltas]
    matrix: List[List[float]] = []
    for scale in cf_axis:
        row = []
        for r in rate_axis:
            if r <= -1.0:
                row.append(float("nan"))
            else:
                row.append(_npv_with_scaled_cash_flows(project, r, scale))
        matrix.append(row)
    return matrix, rate_axis, cf_axis
