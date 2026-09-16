# -*- coding: utf-8 -*-
"""
ai_data_generator.py — AI 辅助的多项目现金流数据生成
====================================================================
本模块承担实操要求中的 **"AI 辅助功能（一）：生成多项目现金流数据"**。

设计思路
--------
直接让大模型"随口编"现金流数字存在两个致命问题：
1. **数量级不可控** —— 可能生成"投资 100 万、每年回收 800 万"这类
   违背商业常识的数据，使后续 NPV / IRR 结论失去教学意义；
2. **不可复现** —— 相同指令两次调用结果不同，无法支撑作业报告的
   结果复核。

因此本模块采用 **"行业原型约束 + 参数化生成"** 的混合策略：

* 先由行业知识构建 :class:`~src.models.IndustryProfile`（投资规模区间、
  寿命区间、现金回收效率、成长性、波动率、现金流形态）；
* 再由生成器在区间内采样，并按 ``steady / growth / jcurve / cycle``
  四种典型形态生成现金流曲线；
* 随机数使用固定种子（:data:`~src.config.RANDOM_SEED`），保证
  **同一份代码在任何机器上跑出完全一致的数据**；
* 若配置了大模型 API，可由 :func:`generate_project_narratives` 生成
  更自然的项目背景描述文案，未配置时自动降级为内置模板。

这样既保留了"AI 生成测试用例"的价值（多行业、多周期、形态多样），
又保证了工业级数据质量与可复现性。
"""

from __future__ import annotations

import math
import random
from typing import Dict, List, Optional

from .config import RANDOM_SEED
from .models import IndustryProfile, Project

__all__ = [
    "INDUSTRY_PROFILES",
    "generate_projects",
    "generate_project_narratives",
    "profiles_to_table",
]


# ======================================================================
# 一、行业特征原型库
# ======================================================================
# 每个原型都对应真实的资本投资特征，参数取值参考行业一般规律：
#   * 新能源/半导体：投资规模大、寿命中等、成长性高但波动大；
#   * 医药研发：J 曲线（前期持续投入、后期才产出）；
#   * 消费零售/公用事业：投资中小、回收稳定、波动小；
#   * 数字软件：轻资产、回收快、寿命相对短但成长性强。
INDUSTRY_PROFILES: List[IndustryProfile] = [
    IndustryProfile(
        name="新能源（光伏组件制造）",
        investment_range=(3800.0, 5200.0),
        life_range=(8, 10),
        cf_ratio_range=(0.20, 0.26),
        growth=0.05,
        volatility=0.06,
        pattern="growth",
        risk_level="中高",
    ),
    IndustryProfile(
        name="半导体（晶圆产线）",
        investment_range=(6000.0, 9000.0),
        life_range=(10, 12),
        cf_ratio_range=(0.16, 0.21),
        growth=0.03,
        volatility=0.09,
        pattern="cycle",
        risk_level="高",
    ),
    IndustryProfile(
        name="生物医药（创新药研发）",
        investment_range=(2200.0, 3000.0),
        life_range=(9, 10),
        cf_ratio_range=(0.24, 0.30),
        growth=0.08,
        volatility=0.10,
        pattern="jcurve",
        risk_level="高",
    ),
    IndustryProfile(
        name="消费零售（连锁门店）",
        investment_range=(900.0, 1600.0),
        life_range=(5, 6),
        cf_ratio_range=(0.28, 0.34),
        growth=0.03,
        volatility=0.05,
        pattern="steady",
        risk_level="低",
    ),
    IndustryProfile(
        name="公用事业（城市管网改造）",
        investment_range=(2800.0, 3600.0),
        life_range=(12, 15),
        cf_ratio_range=(0.13, 0.16),
        growth=0.02,
        volatility=0.03,
        pattern="steady",
        risk_level="低",
    ),
    IndustryProfile(
        name="数字软件（SaaS 平台）",
        investment_range=(700.0, 1200.0),
        life_range=(5, 7),
        cf_ratio_range=(0.30, 0.38),
        growth=0.10,
        volatility=0.08,
        pattern="growth",
        risk_level="中",
    ),
]


# ======================================================================
# 二、现金流形态生成器
# ======================================================================
def _gen_steady(base: float, life: int, growth: float, vol: float, rng: random.Random) -> List[float]:
    """稳定型现金流：围绕基准值小幅增长并叠加随机扰动。"""
    flows = []
    for t in range(1, life + 1):
        value = base * (1.0 + growth) ** (t - 1)
        value *= 1.0 + rng.uniform(-vol, vol)
        flows.append(round(value, 2))
    return flows


def _gen_growth(base: float, life: int, growth: float, vol: float, rng: random.Random) -> List[float]:
    """成长型现金流：前期爬坡（产能利用率提升），后期增速放缓趋于稳定。

    形态设计：前 3 年按 ``growth + ramp`` 快速增长，之后回归基准增速，
    贴合制造业"产能爬坡 — 满产稳定"的真实节奏。
    """
    flows = []
    for t in range(1, life + 1):
        ramp = 0.22 if t <= 3 else 0.08 if t <= 5 else 0.02
        rate = growth + ramp
        value = base * (1.0 + rate) ** (t - 1)
        value *= 1.0 + rng.uniform(-vol, vol)
        flows.append(round(value, 2))
    return flows


def _gen_jcurve(base: float, life: int, growth: float, vol: float, rng: random.Random) -> List[float]:
    """J 曲线型现金流：前 2 期为净流出（继续投入临床/中试），第 3 年起转正并快速增长。

    该形态会产生 **多次现金流符号变化**，是检验 IRR 多重根诊断的天然样本。
    """
    flows = []
    for t in range(1, life + 1):
        if t <= 2:
            value = -base * rng.uniform(0.35, 0.55)     # 研发/中试阶段净流出
        elif t == 3:
            value = base * 0.35 * (1.0 + rng.uniform(-vol, vol))
        else:
            value = base * (1.0 + growth + 0.18) ** (t - 3) * 0.9
            value *= 1.0 + rng.uniform(-vol, vol)
        flows.append(round(value, 2))
    return flows


def _gen_cycle(base: float, life: int, growth: float, vol: float, rng: random.Random) -> List[float]:
    """周期型现金流：景气度先高后低，中段出现一轮下行（模拟半导体周期）。"""
    flows = []
    for t in range(1, life + 1):
        # 用一个完整的正弦周期刻画行业景气循环
        wave = 1.0 + 0.28 * math.sin(2 * math.pi * (t - 1) / max(life - 1, 1))
        value = base * wave * (1.0 + growth) ** (t - 1)
        value *= 1.0 + rng.uniform(-vol, vol)
        flows.append(round(value, 2))
    return flows


_PATTERN_DISPATCH = {
    "steady": _gen_steady,
    "growth": _gen_growth,
    "jcurve": _gen_jcurve,
    "cycle": _gen_cycle,
}


# ======================================================================
# 三、项目批量生成
# ======================================================================
def generate_projects(
    count_per_industry: int = 2,
    seed: int = RANDOM_SEED,
    max_projects: Optional[int] = None,
) -> List[Project]:
    """按行业原型批量生成投资项目（AI 模拟测试用例）。

    Parameters
    ----------
    count_per_industry : int
        每个行业生成的项目数量。
    seed : int
        随机种子，固定值保证结果可复现。
    max_projects : int or None
        结果上限，None 表示不限制。

    Returns
    -------
    list of Project
        按"行业顺序 + 编号"排列的项目列表。

    Notes
    -----
    每个行业原型生成的项目具有一致的商业特征（投资规模量级、寿命区间），
    但具体数值不同，可用于测试模型对不同规模项目的适应性。
    """
    rng = random.Random(seed)
    projects: List[Project] = []
    serial = 0
    for profile in INDUSTRY_PROFILES:
        for _ in range(count_per_industry):
            serial += 1
            investment = round(rng.uniform(*profile.investment_range), 2)
            life = rng.randint(*profile.life_range)
            ratio = rng.uniform(*profile.cf_ratio_range)
            base = investment * ratio
            flows = _PATTERN_DISPATCH[profile.pattern](
                base, life, profile.growth, profile.volatility, rng
            )
            projects.append(
                Project(
                    code=f"P{serial:02d}",
                    name=f"{profile.name.split('（')[0]}项目{serial:02d}",
                    industry=profile.name,
                    initial_investment=investment,
                    cash_flows=flows,
                    risk_level=profile.risk_level,
                    description="",
                )
            )
            if max_projects is not None and len(projects) >= max_projects:
                return projects
    return projects


# ======================================================================
# 四、项目背景文案生成（AI / 模板双通道）
# ======================================================================
_NARRATIVE_TEMPLATE = (
    "{name}属于{industry}领域，计划投资 {investment:,.0f} 万元，建设期计入第 0 年，"
    "运营期 {life} 年。预计运营期年均净现金流约 {avg_cf:,.0f} 万元，"
    "现金流形态为「{pattern_desc}」，行业风险等级评估为「{risk}」。"
)


def _pattern_description(project: Project) -> str:
    """根据现金流形态反推形态描述文案。"""
    flows = project.cash_flows
    if any(f < 0 for f in flows):
        return "前期继续投入、后期产出（J 曲线）"
    if flows[-1] > flows[0] * 1.6:
        return "产能爬坡、逐年增长"
    if flows[-1] < flows[0] * 0.8:
        return "前期景气、后期回落（周期型）"
    return "运营稳定、现金流平稳"


def generate_project_narratives(
    projects: List[Project],
    use_llm: bool = False,
) -> List[Project]:
    """为项目批量生成业务背景描述文案（就地写入 ``project.description``）。

    Parameters
    ----------
    projects : list of Project
        待补充描述的项目列表。
    use_llm : bool
        是否调用大模型生成更自然的文案。为 True 且环境已配置
        ``IDS_LLM_API_KEY`` 时调用大模型，否则 **静默降级** 为内置模板。

    Returns
    -------
    list of Project
        同一列表对象（已填充 description），便于链式调用。

    Notes
    -----
    内置模板采用"数据驱动"写法：把投资额、寿命、年均现金流、形态特征
    拼接成标准段落，保证离线环境下报告文案依然完整、专业、无占位符。
    """
    llm_texts: Dict[str, str] = {}
    if use_llm:
        try:
            from .ai_advisor import call_llm_for_narratives
            llm_texts = call_llm_for_narratives(projects)
        except Exception:  # pragma: no cover - 网络/依赖异常时静默降级
            llm_texts = {}

    for p in projects:
        if p.code in llm_texts:
            p.description = llm_texts[p.code]
            continue
        avg_cf = sum(p.cash_flows) / len(p.cash_flows)
        p.description = _NARRATIVE_TEMPLATE.format(
            name=p.name,
            industry=p.industry,
            investment=p.initial_investment,
            life=p.life,
            avg_cf=avg_cf,
            pattern_desc=_pattern_description(p),
            risk=p.risk_level,
        )
    return projects


def profiles_to_table() -> List[Dict]:
    """导出行业原型参数表（用于报告附录展示数据生成依据）。

    Returns
    -------
    list of dict
        每行一个行业的参数记录。
    """
    rows = []
    for p in INDUSTRY_PROFILES:
        rows.append({
            "行业原型": p.name,
            "投资规模区间(万元)": f"{p.investment_range[0]:,.0f} ~ {p.investment_range[1]:,.0f}",
            "寿命区间(年)": f"{p.life_range[0]} ~ {p.life_range[1]}",
            "现金回收效率": f"{p.cf_ratio_range[0]:.0%} ~ {p.cf_ratio_range[1]:.0%}",
            "成长率": f"{p.growth:.1%}",
            "波动率": f"{p.volatility:.1%}",
            "现金流形态": {
                "steady": "稳定型", "growth": "成长型",
                "jcurve": "J 曲线型", "cycle": "周期型",
            }.get(p.pattern, p.pattern),
            "风险等级": p.risk_level,
        })
    return rows
