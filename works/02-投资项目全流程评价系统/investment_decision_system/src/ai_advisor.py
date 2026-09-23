# -*- coding: utf-8 -*-
"""
ai_advisor.py — AI 辅助决策建议生成
====================================================================
本模块承担实操要求中的 **"AI 辅助功能（二）：生成决策建议"**。

双通道架构
----------
::

    ┌─────────────────────────────────────────────────────────┐
    │  generate_advice(project, evaluation, sensitivity)      │
    └───────────────────┬─────────────────────────────────────┘
                        │
            ┌───────────┴────────────┐
            ▼                        ▼
    ┌───────────────┐        ┌──────────────────┐
    │  规则引擎通道   │        │   大模型通道      │
    │ (离线可用)     │        │ (需配置 API Key)  │
    └───────────────┘        └──────────────────┘
      评价结论 + 风险规则       把结构化指标作为
        → 结构化文案            Prompt 交给 LLM 润色

**为什么以规则引擎为主通道？**

1. **可复现**：同一份数据永远产生同一段结论，报告结论可被复核；
2. **零幻觉**：所有数字都直接来自计算引擎，不存在大模型编造数字的风险；
3. **离线可用**：不依赖网络与 API Key，作业在任何环境都能完整跑通；
4. **可解释**：每条风险提示都能追溯到具体规则（见 ``_RISK_RULES``）。

大模型通道仅作为 **文案润色层**：把已经算好的结构化指标作为上下文
传入，要求模型"只做语言组织，不得修改任何数字"。这样既获得更自然的
表达，又避免了大模型在财务计算上的不可靠性。未配置 API Key 时
:func:`generate_advice` 会静默降级到规则引擎，不抛异常。
"""

from __future__ import annotations

import json
import statistics
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from .config import AI_API_KEY, AI_BASE_URL, AI_MODE, AI_MODEL
from .models import Evaluation, Project
from .sensitivity import SensitivityResult

__all__ = [
    "DecisionAdvice",
    "generate_advice",
    "generate_batch_advice",
    "summarize_advice",
    "advice_to_markdown",
    "call_llm_for_narratives",
    "LLM_AVAILABLE",
]


# 当前环境是否具备大模型调用条件（供报告说明使用）
LLM_AVAILABLE: bool = bool(AI_API_KEY)


# ======================================================================
# 一、结论等级定义
# ======================================================================
VERDICT_FEASIBLE = "可行（推荐投资）"
VERDICT_EDGE = "可行但安全边际不足（谨慎推进）"
VERDICT_INFEASIBLE = "不可行（建议否决）"
# 多重 IRR 情形下 IRR 判据失效，结论方向以 NPV 为准，因此拆为两个带方向的等级
VERDICT_IRR_INVALID_FEASIBLE = "IRR 多重根失效 → 按 NPV 判定：可行"
VERDICT_IRR_INVALID_INFEASIBLE = "IRR 多重根失效 → 按 NPV 判定：不可行"
# 向后兼容别名（历史上仅有一个"IRR 失效"等级）
VERDICT_IRR_INVALID = VERDICT_IRR_INVALID_FEASIBLE


@dataclass
class DecisionAdvice:
    """单个项目的 AI 决策建议。

    Attributes
    ----------
    code : str
        项目编号。
    name : str
        项目名称。
    verdict : str
        综合结论。
    headline : str
        一句话核心结论（用于报告摘要与图表标注）。
    reasons : list of str
        支撑结论的关键指标依据。
    risks : list of str
        风险点提示（每条均带具体数字）。
    actions : list of str
        建议动作。
    risk_score : int
        风险评分 0~100，数值越大风险越高（由规则累加得到）。
    irr_invalid : bool
        IRR 指标是否因多重根而失效（用于汇总分类）。
    generated_by : str
        文案生成通道（规则引擎 / 大模型）。
    """

    code: str
    name: str
    verdict: str
    headline: str
    reasons: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    risk_score: int = 0
    irr_invalid: bool = False
    generated_by: str = "规则引擎"

    def to_markdown(self) -> str:
        """渲染为 Markdown 片段。"""
        lines = [
            f"#### {self.code}｜{self.name}",
            "",
            f"**结论：{self.verdict}**　（风险评分：{self.risk_score}/100　文案通道：{self.generated_by}）",
            "",
            f"> {self.headline}",
            "",
            "**决策依据**",
            "",
        ]
        lines += [f"- {r}" for r in self.reasons]
        if self.risks:
            lines += ["", "**风险点提示**", ""]
            lines += [f"- {r}" for r in self.risks]
        if self.actions:
            lines += ["", "**建议动作**", ""]
            lines += [f"- {a}" for a in self.actions]
        return "\n".join(lines)


# ======================================================================
# 二、风险评分与规则
# ======================================================================
def _risk_score(
    evaluation: Evaluation,
    safety_margin: float,
    rate_delta_critical: bool,
    payback_ratio: Optional[float],
    investment_share: Optional[float] = None,
) -> int:
    """按多因素规则累加计算风险评分（0~100）。

    权重分配（合计上限 100 分）：

    ==========================  ======  ==================================
    风险维度                     最高分   触发条件
    ==========================  ======  ==================================
    安全边际过薄                  35      安全边际 < 8pp 分档累加
    折现率 ±5pp 冲击击穿临界点     20      折现率上升 5pp 后 NPV 转负
    回收期占寿命比重过高           15      占比 ≥ 60% 分档累加
    现金流波动率过高               10      变异系数 ≥ 0.2 分档累加
    多重 IRR / 无实根              12      现金流多次变号导致指标失效
    资本集中度过高                  8      单项目占资本限额 ≥ 40%
    ==========================  ======  ==================================

    Parameters
    ----------
    evaluation : Evaluation
        评价结果。
    safety_margin : float
        安全边际（IRR − rate）。
    rate_delta_critical : bool
        折现率上升 5pp 后 NPV 是否转负。
    payback_ratio : float or None
        静态回收期 / 项目寿命。
    investment_share : float or None
        该项目投资额占资本限额的比例。

    Returns
    -------
    int
        风险评分，越高越危险。
    """
    score = 0.0
    # 1) 安全边际：越薄越危险（最高 35 分）
    if safety_margin < 0.01:
        score += 35
    elif safety_margin < 0.03:
        score += 24
    elif safety_margin < 0.05:
        score += 16
    elif safety_margin < 0.08:
        score += 7

    # 2) 折现率 ±5pp 冲击（最高 20 分）
    if rate_delta_critical:
        score += 20

    # 3) 回收期占寿命比重（最高 15 分）
    if payback_ratio is not None:
        if payback_ratio >= 0.9:
            score += 15
        elif payback_ratio >= 0.75:
            score += 10
        elif payback_ratio >= 0.6:
            score += 5

    # 4) 现金流波动（最高 10 分）
    flows = evaluation.project.cash_flows
    mean_flow = statistics.fmean(flows)
    if abs(mean_flow) > 1e-9:
        cv = statistics.pstdev(flows) / abs(mean_flow)
        if cv >= 0.6:
            score += 10
        elif cv >= 0.35:
            score += 6
        elif cv >= 0.2:
            score += 3

    # 5) 多重 IRR / 无实根（最高 12 分）
    if not evaluation.irr_result.is_unique or evaluation.irr is None:
        score += 12

    # 6) 资本集中度（最高 8 分）
    if investment_share is not None and investment_share >= 0.4:
        score += 8

    return int(min(round(score), 100))


# ======================================================================
# 三、规则引擎：生成建议
# ======================================================================
def generate_advice(
    evaluation: Evaluation,
    sensitivity: Optional[SensitivityResult] = None,
    investment_share: Optional[float] = None,
    use_llm: bool = False,
) -> DecisionAdvice:
    """基于评价结果与敏感性分析生成结构化决策建议。

    Parameters
    ----------
    evaluation : Evaluation
        项目评价结果。
    sensitivity : SensitivityResult or None
        项目的敏感性分析结果。为 None 时自动计算一份（误差 ±20%、折现率 ±5pp）。
    investment_share : float or None
        该项目投资额占资本限额的比例，用于集中度风险提示。
    use_llm : bool
        是否尝试调用大模型润色文案。需配置 ``IDS_LLM_API_KEY``，
        失败或未配置时自动降级为规则引擎。

    Returns
    -------
    DecisionAdvice
        结构化决策建议。
    """
    project = evaluation.project
    rate = evaluation.rate

    # 敏感性分析缺失时自动补算，保证建议总是有数据支撑
    if sensitivity is None:
        from .sensitivity import one_way_sensitivity
        sensitivity = one_way_sensitivity(project, rate)

    verdict, reasons, risks, actions, irr_invalid = _build_by_rules(
        evaluation, sensitivity, investment_share
    )

    # ---------- 文案结构（供大模型润色时作为上下文） ----------
    payback_ratio = (
        evaluation.static_payback / project.life
        if evaluation.static_payback and project.life else None
    )
    rate_delta_critical = any(
        f.name == "折现率" and f.critical for f in sensitivity.factors
    )
    risk_score = _risk_score(evaluation, sensitivity.safety_margin,
                            rate_delta_critical, payback_ratio, investment_share)

    headline = _build_headline(evaluation, sensitivity, verdict)

    advice = DecisionAdvice(
        code=project.code,
        name=project.name,
        verdict=verdict,
        headline=headline,
        reasons=reasons,
        risks=risks,
        actions=actions,
        risk_score=risk_score,
        irr_invalid=irr_invalid,
        generated_by="规则引擎",
    )

    # ---------- 可选：大模型润色通道 ----------
    want_llm = use_llm or AI_MODE == "llm"
    if want_llm and LLM_AVAILABLE:
        polished = _polish_with_llm(advice, evaluation, sensitivity)
        if polished:
            advice.headline = polished.get("headline", advice.headline)
            advice.risks = polished.get("risks", advice.risks)
            advice.actions = polished.get("actions", advice.actions)
            advice.generated_by = f"大模型润色（{AI_MODEL}）"
    elif AI_MODE == "llm" and not LLM_AVAILABLE:
        advice.generated_by = "规则引擎（未配置 API Key，已自动降级）"

    return advice


def _build_headline(
    evaluation: Evaluation,
    sensitivity: SensitivityResult,
    verdict: str,
) -> str:
    """生成一句话结论。"""
    project = evaluation.project
    rate = evaluation.rate
    # 多重 IRR 情形需单独措辞：结论方向由 NPV 决定，而非 IRR
    if "IRR 多重根失效" in verdict:
        roots = "、".join(f"{r:.2%}" for r in evaluation.irr_result.all_roots)
        if evaluation.npv > 0:
            return (
                f"{project.code}（{project.name}）在 {rate:.1%} 折现率下 NPV 为 "
                f"+{evaluation.npv:,.0f} 万元，按 NPV 判定 **可行**；"
                f"但该项目 IRR 存在 {len(evaluation.irr_result.all_roots)} 个实根（{roots}），"
                f"IRR 判据完全失效，决策须以 NPV 与 MIRR 为唯一依据。"
            )
        # NPV 恰为 0 时（多重 IRR 项目的常见情形）需额外标注"临界"而非简单说"为 0"
        boundary = "（恰好为零，处于可行性临界点）" if abs(evaluation.npv) < 1e-6 else ""
        return (
            f"{project.code}（{project.name}）在 {rate:.1%} 折现率下 NPV 为 "
            f"{evaluation.npv:,.0f} 万元{boundary}，按 NPV 判定不可行；"
            f"该项目 IRR 存在 {len(evaluation.irr_result.all_roots)} 个实根（{roots}），"
            f"IRR 判据失效，不可作为决策或考核依据。"
        )
    if "不可行" in verdict:
        return (
            f"{project.code}（{project.name}）在 {rate:.1%} 折现率下 NPV 为 "
            f"{evaluation.npv:,.0f} 万元，未能覆盖资本成本，建议否决或重新设计方案参数。"
        )
    if "安全边际不足" in verdict:
        return (
            f"{project.code}（{project.name}）NPV 为 {evaluation.npv:,.0f} 万元，"
            f"但 IRR {evaluation.irr:.2%} 仅高于资本成本 {sensitivity.safety_margin * 100:.2f} "
            f"个百分点，安全边际偏薄，属于边缘可行项目。"
        )
    if sensitivity.safety_margin >= 0.08:
        strength = "抗风险能力强"
    elif sensitivity.safety_margin >= 0.05:
        strength = "抗风险能力较强"
    else:
        strength = "抗风险能力中等"
    return (
        f"{project.code}（{project.name}）NPV 为 {evaluation.npv:,.0f} 万元，"
        f"IRR 为 {evaluation.irr:.2%}（高于资本成本 {rate:.1%}），"
        f"{strength}，建议按计划推进。"
    )


def _build_by_rules(
    evaluation: Evaluation,
    sensitivity: SensitivityResult,
    investment_share: Optional[float],
) -> tuple:
    """规则引擎核心：输出结论、依据、风险点与建议动作。

    Returns
    -------
    tuple
        ``(verdict, reasons, risks, actions, irr_invalid)``
    """
    project = evaluation.project
    rate = evaluation.rate
    irr = evaluation.irr
    safety = sensitivity.safety_margin

    reasons: List[str] = []
    risks: List[str] = []
    actions: List[str] = []

    # ------------------------------------------------------------------
    # 1. 结论判定
    # ------------------------------------------------------------------
    # 多重 IRR 时 IRR 判据失效，结论方向完全由 NPV 决定
    irr_invalid = not evaluation.irr_result.is_unique
    if irr_invalid:
        verdict = (VERDICT_IRR_INVALID_FEASIBLE if evaluation.npv > 0
                   else VERDICT_IRR_INVALID_INFEASIBLE)
    elif evaluation.npv > 0 and irr is not None and irr > rate:
        verdict = VERDICT_FEASIBLE if safety >= 0.03 else VERDICT_EDGE
    else:
        verdict = VERDICT_INFEASIBLE

    # ------------------------------------------------------------------
    # 2. 决策依据（关键指标，全部为实算值）
    # ------------------------------------------------------------------
    npv_comment = (
        "大于零，项目创造价值" if evaluation.npv > 1e-9
        else "小于零，项目减损价值" if evaluation.npv < -1e-9
        else "恰好为零，**项目处于可行性临界点**——既不创造也不减损价值"
    )
    reasons.append(
        f"净现值 NPV = **{evaluation.npv:,.2f} 万元**（折现率 {rate:.2%}，"
        f"初始投资 {project.initial_investment:,.0f} 万元，寿命 {project.life} 年），"
        f"{npv_comment}。"
    )
    if irr is not None and irr_invalid:
        roots = "、".join(f"{r:.2%}" for r in evaluation.irr_result.all_roots)
        reasons.append(
            f"内含报酬率 IRR 方程 **存在 {len(evaluation.irr_result.all_roots)} 个实根"
            f"（{roots}）**，IRR 判据失效，可行性改以 NPV 为唯一依据"
            f"（MIRR = {evaluation.mirr:.2%}，恒唯一，可作稳定替代判据）。"
        )
    elif irr is not None:
        reasons.append(
            f"内含报酬率 IRR = **{irr:.2%}**，"
            f"{'高于' if irr > rate else '低于'}资本成本 {rate:.2%}，"
            f"安全边际 {safety * 100:+.2f} 个百分点，抗风险等级「{sensitivity.grade}」。"
        )
    else:
        reasons.append(
            f"内含报酬率 IRR 在 (-99%, 500%] 区间内 **无实根**，"
            f"说明项目在任何折现率下均无法收回投资，应直接否决。"
        )
    reasons.append(
        f"盈利能力指数 PI = **{evaluation.pi:.4f}**，"
        f"年金净流量 ANCF = **{evaluation.ancf:,.2f} 万元/年**，"
        f"修正内部收益率 MIRR = {evaluation.mirr:.2%}。"
    )
    if evaluation.static_payback is not None:
        detail = f"静态投资回收期 **{evaluation.static_payback:.2f} 年**"
        if evaluation.dynamic_payback is not None:
            detail += (
                f"（占寿命 {evaluation.static_payback / project.life:.0%}），"
                f"动态投资回收期 **{evaluation.dynamic_payback:.2f} 年**。"
            )
        else:
            detail += (
                f"（占寿命 {evaluation.static_payback / project.life:.0%}）；"
                f"但 **动态投资回收期超过项目寿命**，说明扣减资金时间价值后，"
                f"项目在整个寿命期内无法收回全部投资。"
            )
        reasons.append(detail)
    else:
        reasons.append("投资在项目寿命期内未能全部收回（回收期超过寿命），流动性风险显著。")

    # ------------------------------------------------------------------
    # 3. 风险点提示
    # ------------------------------------------------------------------
    # (1) 折现率冲击风险 —— 题目要求的典型提示句式
    rate_factor = next((f for f in sensitivity.factors if f.name == "折现率"), None)
    if rate_factor is not None:
        next_rate = rate + 0.05
        if irr_invalid:
            # 多重 IRR 项目须用"非单调性"话术，套用常规的"临界折现率缓冲"表述会严重误导
            direction = "反而上升" if rate_factor.adverse_npv > sensitivity.base_npv else "下降"
            risks.append(
                f"**折现率非单调风险（高）**：本项目 NPV 与折现率 **非单调**——"
                f"折现率从 {rate:.2%} 升至 {next_rate:.2%} 时，NPV 由 "
                f"{sensitivity.base_npv:,.2f} 万元变为 {rate_factor.adverse_npv:,.2f} 万元（{direction}），"
                f"与常规项目「折现率越高、NPV 越低」的规律相反。"
                f"因此不能凭折现率的变动方向推断项目的风险方向，"
                f"必须逐点绘制 NPV—折现率曲线后再作判断。"
            )
        elif sensitivity.base_npv <= 0:
            # 基准情形已不可行时，折现率波动不是主要矛盾，应提示"先解决盈利性"
            risks.append(
                f"**可行性风险（高）**：项目在基准折现率 {rate:.2%} 下 NPV 已为 "
                f"{sensitivity.base_npv:,.2f} 万元，本身即不满足可行性要求；"
                f"折现率再上升 5 个百分点至 {next_rate:.2%} 时 NPV 降至 "
                f"{rate_factor.adverse_npv:,.2f} 万元，亏损进一步扩大。"
                f"**当前首要矛盾是项目自身的盈利性而非折现率波动**，"
                f"应在压缩投资或提升现金流后再评估折现率风险。"
            )
        elif rate_factor.critical:
            margin_text = (
                f"（IRR 仅 {irr:.2%}，安全边际 {safety * 100:.2f}pp）" if irr is not None else ""
            )
            risks.append(
                f"**折现率上升风险（高）**：折现率上升 5 个百分点至 {next_rate:.2%} 时，"
                f"项目 NPV 由 +{sensitivity.base_npv:,.2f} 万元转为 "
                f"{rate_factor.adverse_npv:,.2f} 万元，**由正转负**，抗风险能力较弱"
                f"{margin_text}。若宏观利率上行或资本成本重估，项目将立即失效。"
            )
        elif irr is not None:
            risks.append(
                f"**折现率风险（可控）**：折现率上升 5 个百分点至 {next_rate:.2%} 时，"
                f"NPV 仍为 +{rate_factor.adverse_npv:,.2f} 万元，"
                f"距临界折现率（IRR {irr:.2%}）尚有 {safety * 100:.2f} 个百分点缓冲。"
            )
        else:
            risks.append(
                f"**折现率风险**：折现率上升 5 个百分点至 {next_rate:.2%} 时，"
                f"NPV 为 {rate_factor.adverse_npv:,.2f} 万元。"
            )

    # (2) 投资超支风险
    inv_limit = sensitivity.breakeven.get("初始投资最大可上升幅度")
    if inv_limit is not None and isinstance(inv_limit, float) and inv_limit == inv_limit:  # 非 NaN
        critical_inv = project.initial_investment * (1 + inv_limit)
        if inv_limit < -1e-9:
            risks.append(
                f"**投资规模风险（高）**：初始投资已 **超出临界投资额** —— "
                f"临界值为 {critical_inv:,.0f} 万元，而当前投资为 "
                f"{project.initial_investment:,.0f} 万元，超出 "
                f"{project.initial_investment - critical_inv:,.0f} 万元"
                f"（{-inv_limit:.2%}）。项目当前即为负 NPV，"
                f"必须先将投资规模压缩至临界值以下，再重新测算。"
            )
        elif inv_limit <= 1e-9:
            risks.append(
                f"**投资超支风险（高）**：项目当前 NPV **已处于可行性临界状态**，"
                f"初始投资 **没有任何超支空间**"
                f"（临界投资额 {critical_inv:,.0f} 万元与当前投资额基本持平），"
                f"任何超支都会使 NPV 立即转为负值。"
            )
        elif inv_limit < 0.15:
            risks.append(
                f"**投资超支风险（高）**：初始投资最多只能上升 **{inv_limit:.2%}**"
                f"（临界值 {critical_inv:,.0f} 万元），"
                f"工程超支、建设期延长的容错空间极小。"
            )
        elif inv_limit < 0.35:
            risks.append(
                f"**投资超支风险（中）**：初始投资可承受的最大超支幅度为 "
                f"{inv_limit:.2%}（临界值 {critical_inv:,.0f} 万元），"
                f"建议在预算中预留不低于 10% 的不可预见费。"
            )
        else:
            risks.append(
                f"**投资超支风险（低）**：初始投资可承受最大超支 {inv_limit:.2%}，"
                f"预算弹性充足。"
            )

    # (3) 现金流下滑风险
    mean_flow = statistics.fmean(project.cash_flows)
    cf_limit = sensitivity.breakeven.get("年现金流最大可下降幅度")
    if cf_limit is not None and isinstance(cf_limit, float) and cf_limit == cf_limit:
        min_cf = mean_flow * (1 - cf_limit)
        if cf_limit < -1e-9:
            risks.append(
                f"**收入水平风险（高）**：年现金流已 **低于临界水平** —— "
                f"临界年均现金流为 {min_cf:,.0f} 万元，而当前年均仅 "
                f"{mean_flow:,.0f} 万元，缺口 {min_cf - mean_flow:,.0f} 万元"
                f"（{-cf_limit:.2%}）。项目当前即为负 NPV，"
                f"需将收入水平提升至临界值以上或压缩投资规模后重新测算。"
            )
        elif cf_limit <= 1e-9:
            risks.append(
                f"**收入下滑风险（高）**：项目当前 NPV **已处于可行性临界状态**，"
                f"年现金流 **没有任何下降空间**（临界年均现金流约 {min_cf:,.0f} 万元，"
                f"与当前年均 {mean_flow:,.0f} 万元基本持平），"
                f"任何收入下滑都会使 NPV 立即转为负值。"
            )
        elif cf_limit < 0.10:
            risks.append(
                f"**收入下滑风险（高）**：年现金流最大可下降 **{cf_limit:.2%}**，"
                f"即年均现金流低于 {min_cf:,.0f} 万元时 NPV 转为负值。"
                f"该缓冲幅度低于行业常见的收入波动区间，项目对市场需求变化极为敏感。"
            )
        elif cf_limit < 0.25:
            risks.append(
                f"**收入下滑风险（中）**：年现金流最大可下降 {cf_limit:.2%}，"
                f"低于此幅度 NPV 转负，需锁定核心客户与长期订单。"
            )
        else:
            risks.append(
                f"**收入下滑风险（低）**：年现金流可承受 {cf_limit:.2%} 的降幅，"
                f"对市场波动的缓冲较厚。"
            )

    # (4) 回收期 / 流动性风险
    if evaluation.static_payback is None:
        risks.append(
            "**流动性风险（高）**：项目寿命期内无法收回全部投资，"
            "资金将被长期占用，需重新评估融资安排。"
        )
    else:
        ratio = evaluation.static_payback / project.life
        if ratio >= 0.85:
            risks.append(
                f"**流动性风险（高）**：静态回收期 {evaluation.static_payback:.2f} 年，"
                f"占项目寿命的 {ratio:.0%}，资金占用时间长，"
                f"后期现金流一旦不达预期将难以收回投资。"
            )
        elif ratio >= 0.7:
            risks.append(
                f"**流动性风险（中）**：静态回收期 {evaluation.static_payback:.2f} 年，"
                f"占寿命 {ratio:.0%}，回收节奏偏慢。"
            )

    # (5) 多重 IRR 风险
    if irr_invalid:
        roots = "、".join(f"{r:.2%}" for r in evaluation.irr_result.all_roots)
        risks.append(
            f"**指标失效风险（高）**：现金流出现 {evaluation.sign_changes} 次符号变化，"
            f"IRR 方程存在 **{len(evaluation.irr_result.all_roots)} 个实根**（{roots}），"
            f"IRR 指标不适用。当资本成本落在两个实根之间时 NPV 为正、之外则为负，"
            f"同一项目会因折现率取值不同得出相反结论。"
            f"此时应以 NPV 为唯一判据，或改用 MIRR（{evaluation.mirr:.2%}）。"
        )
        # 说明：NPV 与折现率非单调的提示已由前面的"折现率非单调风险"段落覆盖，
        # 此处不再重复输出，避免报告冗余。

    # (6) 现金流波动风险
    flows = project.cash_flows
    if abs(mean_flow) > 1e-9:
        cv = statistics.pstdev(flows) / abs(mean_flow)
        if cv >= 0.35:
            risks.append(
                f"**经营波动风险（中高）**：各期现金流变异系数 {cv:.2f}（{cv:.0%}），"
                f"现金流分布离散度高，收入预测的不确定性较大。"
            )

    # (7) 资本集中度风险
    if investment_share is not None and investment_share >= 0.4:
        risks.append(
            f"**资本集中度风险（中高）**：本项目占资本限额的 {investment_share:.0%}，"
            f"若单独投产将显著抬高整体资金集中度，建议与其他项目组合实施以分散风险。"
        )

    # ------------------------------------------------------------------
    # 4. 建议动作
    # ------------------------------------------------------------------
    if irr_invalid:
        if evaluation.npv > 0:
            actions.append(
                "**以 NPV 为唯一决策依据**：本项目在基准折现率下 NPV 为正，按 NPV 判定可行；"
                "IRR 因多重根不具参考价值，不得用于决策与绩效考核。"
            )
        else:
            actions.append(
                "**以 NPV 为唯一决策依据**：本项目在基准折现率下 NPV 不为正，按 NPV 判定不可行；"
                "IRR 因多重根不具参考价值。"
            )
        actions.append(
            "向决策层披露多重 IRR 情形，避免使用 IRR 作为对外的项目绩效承诺指标。"
        )
        actions.append(
            "关注 NPV—折现率曲线的 **非单调性**：应结合完整曲线而非单点取值判断项目，"
            "并同时列示 MIRR 作为辅助判据。"
        )
    elif verdict == VERDICT_INFEASIBLE:
        actions.append("**否决该方案**：当前参数下无法覆盖资本成本，不建议投入资金。")
        # 注：inv_limit 可能为 None 或 NaN（临界值求解失败），不能用 `inv_limit or 0`
        # 兜底 —— NaN 在布尔语境下为真值，会输出"需降至 nan 万元以内"。
        inv_limit_safe = (
            float(inv_limit)
            if (inv_limit is not None and isinstance(inv_limit, float) and inv_limit == inv_limit)
            else 0.0
        )
        actions.append(
            "若战略上必须推进，需重新设计：压缩初始投资（当前 "
            f"{project.initial_investment:,.0f} 万元，需降至 "
            f"{project.initial_investment * (1 + inv_limit_safe):,.0f} 万元以内）、"
            "延长寿命期或提升产能利用率以抬升年现金流。"
        )
    elif verdict == VERDICT_EDGE:
        actions.append("**分期投入、设置退出机制**：将投资拆分为 2~3 期，每期结束后按实测现金流复核是否继续。")
        actions.append("**锁定收益端不确定性**：签订长期供货/服务合同，压低现金流波动。")
        actions.append(f"设置折现率红线：资本成本一旦超过 {irr:.2%}，立即停止后续投入。")
    else:
        actions.append("**按计划推进**：NPV 与 IRR 双指标通过，安全边际充足。")
        if sensitivity.factors:
            top = sensitivity.factors[0]
            actions.append(
                f"**重点监控最敏感因素「{top.name}」**：该因素波动对 NPV 的影响最大"
                f"（±{sensitivity.delta:.0%} 扰动引起 NPV 变动 {top.swing:,.2f} 万元），"
                f"应在项目执行中建立该指标的月度跟踪机制。"
            )
        actions.append("建议纳入投资组合整体安排，与其他项目在时间与行业上形成分散配置。")

    return verdict, reasons, risks, actions, irr_invalid


# ======================================================================
# 四、批量与汇总
# ======================================================================
def generate_batch_advice(
    evaluations: Sequence[Evaluation],
    sensitivity_map: Optional[Dict[str, SensitivityResult]] = None,
    budget: Optional[float] = None,
    use_llm: bool = False,
) -> List[DecisionAdvice]:
    """批量生成决策建议。

    Parameters
    ----------
    evaluations : Sequence[Evaluation]
        项目评价结果列表。
    sensitivity_map : dict or None
        项目编号 → 敏感性分析结果。缺失项将自动补算。
    budget : float or None
        资本限额，用于计算各项目投资占比并触发集中度风险提示。
    use_llm : bool
        是否启用大模型润色通道。

    Returns
    -------
    list of DecisionAdvice
    """
    advices: List[DecisionAdvice] = []
    for ev in evaluations:
        sens = (sensitivity_map or {}).get(ev.project.code)
        share = (
            ev.project.initial_investment / budget
            if budget and budget > 0 else None
        )
        advices.append(generate_advice(ev, sens, share, use_llm=use_llm))
    return advices


def summarize_advice(advices: Sequence[DecisionAdvice]) -> str:
    """汇总全部建议，生成整体决策意见段落。

    Parameters
    ----------
    advices : Sequence[DecisionAdvice]
        决策建议列表。

    Returns
    -------
    str
        Markdown 格式的汇总意见。
    """
    if not advices:
        return "无项目可供评价。"

    feasible = [a for a in advices if not a.irr_invalid and a.verdict == VERDICT_FEASIBLE]
    edge = [a for a in advices if not a.irr_invalid and a.verdict == VERDICT_EDGE]
    invalid = [a for a in advices if a.irr_invalid]
    infeasible = [a for a in advices if not a.irr_invalid and a.verdict == VERDICT_INFEASIBLE]
    avg_risk = sum(a.risk_score for a in advices) / len(advices)

    lines = [
        f"本次共评价 **{len(advices)} 个投资项目**，"
        f"其中推荐投资 {len(feasible)} 个、边缘可行（需谨慎）{len(edge)} 个、"
        f"IRR 多重根失效（按 NPV 判定）{len(invalid)} 个、建议否决 {len(infeasible)} 个，"
        f"平均风险评分 **{avg_risk:.1f}/100**。",
        "",
    ]

    if feasible:
        codes = "、".join(f"{a.code}" for a in feasible)
        best = min(feasible, key=lambda a: a.risk_score)
        lines.append(
            f"**优先推进**：{codes}。其中 {best.code}（{best.name}）风险评分最低"
            f"（{best.risk_score}/100），可作为首选投资标的。"
        )
    if edge:
        codes = "、".join(f"{a.code}" for a in edge)
        lines.append(
            f"**审慎推进**：{codes}。这些项目 NPV 为正但安全边际不足 3 个百分点，"
            f"建议采用分期投入并设置折现率红线，避免一次性全额投入。"
        )
    if invalid:
        # 多重 IRR 组内按 NPV 方向再细分，避免把"按 NPV 可行"的项目混入否决名单
        ok = [a.code for a in invalid if "判定：可行" in a.verdict]
        ng = [a.code for a in invalid if a.code not in ok]
        detail = []
        if ok:
            detail.append(f"{'、'.join(ok)} 按 NPV 判定为可行")
        if ng:
            detail.append(f"{'、'.join(ng)} 按 NPV 判定为不可行")
        lines.append(
            f"**特殊处理**：{'、'.join(a.code for a in invalid)} 存在多重 IRR，"
            f"内部报酬率指标不可用（{'；'.join(detail)}），"
            f"决策与考核应以 NPV 与 MIRR 为准。"
        )
    if infeasible:
        codes = "、".join(f"{a.code}" for a in infeasible)
        lines.append(
            f"**建议否决**：{codes}。在既定折现率下无法覆盖资本成本，"
            f"应释放相应资金用于其他更优用途。"
        )

    lines.append("")
    lines.append(
        "**整体判断**：建议按「风险评分升序 + 资本限额约束」的顺序配置资金，"
        "优先满足高安全边际项目的资金需求；对边缘可行项目实行分阶段拨付与"
        "里程碑考核，一旦关键假设偏离即触发再评估机制。"
    )
    return "\n".join(lines)


def advice_to_markdown(advices: Sequence[DecisionAdvice]) -> str:
    """把全部建议渲染为 Markdown。"""
    parts = [a.to_markdown() for a in advices]
    return "\n\n---\n\n".join(parts)


# ======================================================================
# 五、大模型通道（可选，未配置 Key 时自动跳过）
# ======================================================================
def _call_openai_compatible(prompt: str, timeout: int = 45) -> Optional[str]:
    """调用 OpenAI 兼容接口的大模型。

    Parameters
    ----------
    prompt : str
        提示词。
    timeout : int
        超时秒数。

    Returns
    -------
    str or None
        模型返回的文本；调用失败返回 None（由调用方决定降级策略）。

    Notes
    -----
    仅使用标准库 ``urllib`` 实现，不引入额外依赖。
    未配置 ``IDS_LLM_API_KEY`` 时直接返回 None，不发起网络请求。
    """
    if not AI_API_KEY:
        return None
    payload = json.dumps({
        "model": AI_MODEL,
        "messages": [
            {"role": "system",
             "content": "你是企业投资决策分析师。只做语言组织与润色，"
                        "严禁修改、编造或推断任何数字；所有数值必须原样引用用户提供的数据。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
    }).encode("utf-8")
    request = urllib.request.Request(
        f"{AI_BASE_URL.rstrip('/')}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AI_API_KEY}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]
    except (urllib.error.URLError, KeyError, json.JSONDecodeError,
            TimeoutError, OSError):
        return None


def _polish_with_llm(
    advice: DecisionAdvice,
    evaluation: Evaluation,
    sensitivity: SensitivityResult,
) -> Optional[Dict]:
    """让大模型润色风险提示与建议动作文案（数字严格锁定）。"""
    prompt = (
        "以下是已由财务模型计算完成的投资决策结论，请仅优化表达使其更专业流畅，"
        "不得修改任何数字、结论方向或专业术语。\n\n"
        f"项目：{evaluation.project.code} {evaluation.project.name}\n"
        f"结论：{advice.verdict}\n"
        f"核心结论：{advice.headline}\n"
        f"风险提示（逐条润色，条数不变）：\n"
        + "\n".join(f"{i + 1}. {r}" for i, r in enumerate(advice.risks))
        + "\n\n建议动作（逐条润色，条数不变）：\n"
        + "\n".join(f"{i + 1}. {a}" for i, a in enumerate(advice.actions))
        + "\n\n请严格输出 JSON：{\"headline\": \"...\", \"risks\": [\"...\"], \"actions\": [\"...\"]}"
    )
    text = _call_openai_compatible(prompt)
    if not text:
        return None
    try:
        # 容错：模型可能用 ```json 包裹
        cleaned = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


def call_llm_for_narratives(projects: Sequence[Project]) -> Dict[str, str]:
    """调用大模型为项目生成业务背景文案。

    Parameters
    ----------
    projects : Sequence[Project]
        项目列表。

    Returns
    -------
    dict
        项目编号 → 背景描述。未配置 API Key 或调用失败时返回空字典，
        调用方（:func:`src.ai_data_generator.generate_project_narratives`）
        会自动使用内置模板。
    """
    result: Dict[str, str] = {}
    for p in projects:
        prompt = (
            f"请为以下投资项目写一段 80 字以内的业务背景描述，"
            f"语言专业客观，需包含行业特征与投资逻辑，不要编造未给出的数字：\n"
            f"行业：{p.industry}；投资额：{p.initial_investment:,.0f} 万元；"
            f"寿命：{p.life} 年；各期净现金流（万元）："
            f"{', '.join(f'{c:.0f}' for c in p.cash_flows)}；风险等级：{p.risk_level}"
        )
        text = _call_openai_compatible(prompt, timeout=30)
        if text:
            result[p.code] = text.strip()
    return result
