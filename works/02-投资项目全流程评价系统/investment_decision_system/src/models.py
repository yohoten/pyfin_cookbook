# -*- coding: utf-8 -*-
"""
models.py — 数据结构定义
====================================================================
定义全系统通用的数据载体，避免在各模块间传递裸 dict 造成字段歧义。

* :class:`Project`           —— 投资项目（输入数据）
* :class:`Evaluation`        —— 单项目评价结果（各类指标）
* :class:`IndustryProfile`   —— 行业特征原型（AI 数据生成器的输入）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import numpy as np

from . import finance_core as fc


# ======================================================================
# 行业特征原型
# ======================================================================
@dataclass
class IndustryProfile:
    """行业特征原型，用于 AI 参数化生成"不同行业"的现金流形态。

    Attributes
    ----------
    name : str
        行业名称。
    investment_range : tuple of float
        初始投资额生成区间（万元）。
    life_range : tuple of int
        项目寿命生成区间（年）。
    cf_ratio_range : tuple of float
        首年净现金流 / 初始投资 的比率区间，反映资产"现金回收效率"。
    growth : float
        现金流年均增长率，体现行业成长性。
    volatility : float
        现金流波动率（标准差比例），体现行业不确定性。
    pattern : str
        现金流形态，可选：
        ``"steady"``   稳定型（消费、公用事业）
        ``"growth"``   成长型（新能源、TMT）
        ``"jcurve"``   J 曲线型（医药研发，前期有现金流出）
        ``"cycle"``    周期型（半导体、航运，先高后低）
    risk_level : str
        行业风险等级：低 / 中 / 中高 / 高。
    """

    name: str
    investment_range: tuple
    life_range: tuple
    cf_ratio_range: tuple
    growth: float
    volatility: float
    pattern: str
    risk_level: str


# ======================================================================
# 投资项目
# ======================================================================
@dataclass
class Project:
    """投资项目。

    Attributes
    ----------
    code : str
        项目编号，如 ``P01``。
    name : str
        项目名称。
    industry : str
        所属行业。
    initial_investment : float
        t = 0 初始投资额（正数，单位：万元）。
    cash_flows : list of float
        t = 1..n 各期净现金流（单位：万元）。
    risk_level : str
        风险等级：低 / 中 / 中高 / 高。
    mutual_group : str or None
        互斥组标签。同一标签内的项目互斥，只能择一投产。
    description : str
        项目说明（用于报告展示，由 AI 生成的业务背景文案）。
    """

    code: str
    name: str
    industry: str
    initial_investment: float
    cash_flows: List[float]
    risk_level: str = "中"
    mutual_group: Optional[str] = None
    description: str = ""

    # ------------------------------------------------------------------
    # 基础属性
    # ------------------------------------------------------------------
    @property
    def life(self) -> int:
        """项目寿命期（年）= 现金流期数。"""
        return len(self.cash_flows)

    @property
    def full_cash_flows(self) -> np.ndarray:
        """完整现金流序列 ``[-I0, CF1, ..., CFn]``。"""
        return fc.build_full_cash_flows(self.cash_flows, self.initial_investment)

    @property
    def has_unconventional_sign_changes(self) -> int:
        """现金流符号变化次数。> 1 次提示可能存在多重 IRR。"""
        signs = np.sign(self.full_cash_flows)
        signs = signs[signs != 0]
        if signs.size < 2:
            return 0
        return int(np.sum(signs[1:] != signs[:-1]))

    # ------------------------------------------------------------------
    # 指标计算（便捷方法，内部委托 finance_core）
    # ------------------------------------------------------------------
    def npv(self, rate: float) -> float:
        """净现值 NPV。"""
        return fc.npv(rate, self.cash_flows, self.initial_investment)

    def irr(self) -> Optional[float]:
        """内含报酬率 IRR（主根）。"""
        return fc.irr(self.cash_flows, self.initial_investment)

    def irr_details(self) -> fc.IRRResult:
        """IRR 及其多重根诊断。"""
        return fc.irr_details(self.cash_flows, self.initial_investment)

    def ancf(self, rate: float) -> float:
        """年金净流量 ANCF（等额年金法）。"""
        return fc.annuity_net_cash_flow(self.npv(rate), rate, self.life)

    def pi(self, rate: float) -> float:
        """盈利能力指数 PI。"""
        return fc.profitability_index(self.npv(rate), self.initial_investment)

    def static_payback(self) -> Optional[float]:
        """静态投资回收期。"""
        return fc.payback_period(self.cash_flows, self.initial_investment)

    def dynamic_payback(self, rate: float) -> Optional[float]:
        """动态投资回收期。"""
        return fc.discounted_payback_period(self.cash_flows, self.initial_investment, rate)

    def mirr(self, finance_rate: float, reinvest_rate: Optional[float] = None) -> float:
        """修正内部收益率 MIRR。"""
        return fc.mirr(
            self.cash_flows, self.initial_investment,
            finance_rate, reinvest_rate if reinvest_rate is not None else finance_rate,
        )

    def npv_curve(self, rate_min: float = 0.0, rate_max: float = 0.5, points: int = 200):
        """折现率 — NPV 关系曲线数据。"""
        return fc.npv_curve(self.cash_flows, self.initial_investment, rate_min, rate_max, points)

    # ------------------------------------------------------------------
    def to_dict(self) -> Dict:
        """导出为扁平字典（便于写入 CSV / DataFrame）。"""
        return {
            "项目编号": self.code,
            "项目名称": self.name,
            "所属行业": self.industry,
            "初始投资(万元)": round(self.initial_investment, 2),
            "寿命期(年)": self.life,
            "互斥组": self.mutual_group or "-",
            "风险等级": self.risk_level,
            "各期净现金流(万元)": ", ".join(f"{c:.2f}" for c in self.cash_flows),
            "现金流符号变化次数": self.has_unconventional_sign_changes,
        }


# ======================================================================
# 评价结果
# ======================================================================
@dataclass
class Evaluation:
    """单个项目的完整评价结果。

    Attributes
    ----------
    project : Project
        被评价项目。
    rate : float
        评价所用折现率（资本成本）。
    npv : float
        净现值。
    irr : float or None
        内含报酬率。
    irr_result : IRRResult
        IRR 详细信息（含多重根诊断）。
    ancf : float
        年金净流量。
    pi : float
        盈利能力指数。
    static_payback : float or None
        静态回收期。
    dynamic_payback : float or None
        动态回收期。
    mirr : float
        修正内部收益率。
    feasible : bool
        综合可行性结论（NPV > 0 且 IRR > 折现率）。
    sign_changes : int
        现金流符号变化次数。
    """

    project: Project
    rate: float
    npv: float
    irr: Optional[float]
    irr_result: fc.IRRResult
    ancf: float
    pi: float
    static_payback: Optional[float]
    dynamic_payback: Optional[float]
    mirr: float
    feasible: bool
    sign_changes: int = 0

    @staticmethod
    def build(project: Project, rate: float) -> "Evaluation":
        """按给定折现率对项目进行全指标评价。

        Parameters
        ----------
        project : Project
            待评价项目。
        rate : float
            折现率。

        Returns
        -------
        Evaluation
        """
        npv_value = project.npv(rate)
        irr_result = project.irr_details()
        project_irr = irr_result.irr
        # 可行性判定：
        #   * 常规现金流（IRR 唯一）→ NPV 与 IRR 双指标同时通过才视为可行；
        #   * 非常规现金流（IRR 多重或无解）→ IRR 判据失效，**仅以 NPV 为准**。
        #     原因是多重根时"选哪个根代表 IRR"本身无客观标准，
        #     若仍套用 IRR > r 判据会得出与 NPV 相反的结论。
        if irr_result.is_unique:
            feasible = (npv_value > 0) and (project_irr is not None and project_irr > rate)
        else:
            feasible = npv_value > 0
        return Evaluation(
            project=project,
            rate=rate,
            npv=npv_value,
            irr=project_irr,
            irr_result=irr_result,
            ancf=project.ancf(rate),
            pi=project.pi(rate),
            static_payback=project.static_payback(),
            dynamic_payback=project.dynamic_payback(rate),
            mirr=project.mirr(rate),
            feasible=feasible,
            sign_changes=project.has_unconventional_sign_changes,
        )

    def to_dict(self) -> Dict:
        """导出为扁平字典。"""
        return {
            "项目编号": self.project.code,
            "项目名称": self.project.name,
            "所属行业": self.project.industry,
            "初始投资(万元)": round(self.project.initial_investment, 2),
            "寿命期(年)": self.project.life,
            "折现率": f"{self.rate:.2%}",
            "NPV(万元)": round(self.npv, 2),
            "IRR": f"{self.irr:.2%}" if self.irr is not None else "无实根",
            "IRR唯一性": "唯一" if self.irr_result.is_unique else f"多重({len(self.irr_result.all_roots)}个)",
            "年金净流量ANCF(万元)": round(self.ancf, 2),
            "盈利能力指数PI": round(self.pi, 4),
            "静态回收期(年)": round(self.static_payback, 2) if self.static_payback else "寿命内未收回",
            "动态回收期(年)": round(self.dynamic_payback, 2) if self.dynamic_payback else "寿命内未收回",
            "MIRR": f"{self.mirr:.2%}" if np.isfinite(self.mirr) else "-",
            "可行性": "可行" if self.feasible else "不可行",
        }
