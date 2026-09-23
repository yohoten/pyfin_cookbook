# -*- coding: utf-8 -*-
"""
optimizer.py — 项目优选与资本分配优化
====================================================================
本模块实现课程第 5 章的两类"决策"问题（相对 NPV/IRR 的"计算"问题）：

1. **互斥项目优选**（:func:`select_mutually_exclusive`）
   * 净现值法（NPV 最大）
   * 年金净流量法（ANCF / 等额年金最大，用于寿命不等的项目）
   * 自动识别两种方法结论冲突的情形，并用 **增量 IRR 分析** 给出仲裁依据

2. **资本限额下的项目组合优化**（:func:`optimize_portfolio`）
   * 排序法：按盈利能力指数 PI 降序贪心装入，速度快但可能非最优
   * 组合法：DFS 穷举 + 剪枝，求全局最优组合（保证最优）
   * 背包法：额度整数化后用 0-1 背包动态规划求解（适用于项目数很多的情形）
   * 自动对比三种方法的结果差异，并指明"排序法失效"的具体原因

------------------------------------------------------------------
为什么排序法会失效（本模块的核心知识点）
------------------------------------------------------------------
排序法的隐含假设是 **"资金可以按任意比例分割"**。当资本额度不可
分割时，高 PI 的小额项目会先把额度打碎，导致剩余额度无法被有效利用，
从而错过"整体 NPV 更高"的组合。

反之，**项目数很大** 时穷举法会指数爆炸，此时：
* 若额度量级可控（如按万元取整），改用 **0-1 背包 DP**，复杂度
  O(n × Budget)；
* 若额度也很大，则只能用启发式（PI 贪心 + 局部搜索），本模块
  在项目数超过阈值时自动降级并给出提示。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from .models import Evaluation, Project

__all__ = [
    "MutualGroupResult",
    "PortfolioResult",
    "OptimizationReport",
    "select_mutually_exclusive",
    "ranking_method",
    "combination_method",
    "knapsack_method",
    "optimize_portfolio",
]


# ======================================================================
# 一、互斥项目优选
# ======================================================================
@dataclass
class MutualGroupResult:
    """单个互斥组的优选结果。

    Attributes
    ----------
    group : str
        互斥组标签。
    evaluations : list of Evaluation
        组内全部方案的完整评价结果。
    best_by_npv : Evaluation
        NPV 法选出的最优方案。
    best_by_ancf : Evaluation
        年金净流量法选出的最优方案。
    best_by_irr : Evaluation
        IRR 法选出的最优方案。
    conflict_npv_ancf : bool
        NPV 法与年金净流量法结论是否冲突。
    conflict_npv_irr : bool
        NPV 法与 IRR 法结论是否冲突。
    same_life : bool
        组内各方案寿命是否完全相同。
    recommendation : str
        决策建议（含方法选择理由）。
    incremental : dict or None
        增量 IRR 分析结果（仅在 NPV 法与 IRR 法冲突时计算）。
    """

    group: str
    evaluations: List[Evaluation]
    best_by_npv: Evaluation
    best_by_ancf: Evaluation
    best_by_irr: Evaluation
    conflict_npv_ancf: bool
    conflict_npv_irr: bool
    same_life: bool
    recommendation: str
    incremental: Optional[Dict] = None


def select_mutually_exclusive(
    projects: Sequence[Project],
    rate: float,
) -> List[MutualGroupResult]:
    """对互斥项目分组并逐一优选。

    Parameters
    ----------
    projects : Sequence[Project]
        待筛选项目。仅处理带有 ``mutual_group`` 标签的项目。
    rate : float
        折现率。

    Returns
    -------
    list of MutualGroupResult
        每个互斥组一条结果，按组标签排序。

    Notes
    -----
    决策规则（严格按教材口径）：
    1. 若组内各方案 **寿命相同** → 直接比较 NPV，取 NPV 最大者；
       若此时 IRR 法与 NPV 法冲突，以 NPV 法为准，并用增量 IRR 验证；
    2. 若组内各方案 **寿命不同** → 必须使用年金净流量法（ANCF），
       取 ANCF 最大者，因为 NPV 在寿命不等时不具备可比性。
    """
    groups: Dict[str, List[Project]] = {}
    for p in projects:
        if p.mutual_group:
            groups.setdefault(p.mutual_group, []).append(p)

    results: List[MutualGroupResult] = []
    for group_name in sorted(groups):
        group_projects = groups[group_name]
        evaluations = [Evaluation.build(p, rate) for p in group_projects]

        best_npv = max(evaluations, key=lambda e: e.npv)
        best_ancf = max(evaluations, key=lambda e: e.ancf)
        # IRR 可能有 None（无实根），排序时置为 -inf
        best_irr = max(
            evaluations,
            key=lambda e: e.irr if e.irr is not None else float("-inf"),
        )

        lives = {p.life for p in group_projects}
        same_life = len(lives) == 1
        conflict_npv_ancf = best_npv.project.code != best_ancf.project.code
        conflict_npv_irr = best_npv.project.code != best_irr.project.code

        # ---------- 增量 IRR 分析（NPV 与 IRR 冲突时） ----------
        # 注意：增量分析要求两个方案 **寿命相同** 才能直接比较增量现金流。
        # 当寿命不等时，若强行做增量分析会得到与年金净流量法相反的结论，
        # 造成决策混乱，因此本系统在寿命不等时只输出年金净流量法结论。
        incremental: Optional[Dict] = None
        if conflict_npv_irr and same_life:
            small = min(evaluations, key=lambda e: e.project.initial_investment)
            large = max(evaluations, key=lambda e: e.project.initial_investment)
            from . import finance_core as fc
            delta = fc.incremental_irr(
                small.project.cash_flows, large.project.cash_flows,
                small.project.initial_investment, large.project.initial_investment,
            )
            incremental = {
                "小投资方案": small.project.code,
                "大投资方案": large.project.code,
                "增量投资额(万元)": round(
                    large.project.initial_investment - small.project.initial_investment, 2
                ),
                "增量IRR": f"{delta.irr:.2%}" if delta.irr is not None else "无实根",
                "增量IRR唯一性": "唯一" if delta.is_unique else f"多重({len(delta.all_roots)}个)",
                "判定": (
                    f"增量IRR {delta.irr:.2%} > 资本成本 {rate:.2%}，增量投资划算，选 {large.project.code}"
                    if delta.irr is not None and delta.irr > rate
                    else f"增量IRR {'—' if delta.irr is None else f'{delta.irr:.2%}'} ≤ 资本成本 {rate:.2%}，增量投资不划算，选 {small.project.code}"
                ),
            }

        # ---------- 生成决策建议文案 ----------
        if same_life:
            recommendation = (
                f"组内各方案寿命相同（均为 {next(iter(lives))} 年），采用 **净现值法** 决策，"
                f"选择 **{best_npv.project.code}（{best_npv.project.name}）**，"
                f"NPV = {best_npv.npv:,.2f} 万元，为组内最大值。"
            )
            if conflict_npv_irr:
                recommendation += (
                    f" ⚠️ 注意：IRR 法会误选 {best_irr.project.code}"
                    f"（IRR {best_irr.irr:.2%} 更高，但投资规模小、绝对价值增量低），"
                    f"互斥决策 **必须以 NPV 为准**。增量分析见「增量IRR」字段。"
                )
            if conflict_npv_ancf:
                recommendation += " （因寿命相同，年金净流量法与 NPV 法结论应一致，若冲突请检查数据。）"
        else:
            recommendation = (
                f"组内方案寿命不同（{'、'.join(str(x) + '年' for x in sorted(lives))}），"
                f"NPV 不可直接比较，采用 **年金净流量法（等额年金法）** 决策，"
                f"选择 **{best_ancf.project.code}（{best_ancf.project.name}）**，"
                f"年金净流量 ANCF = {best_ancf.ancf:,.2f} 万元/年，为组内最大值。"
            )
            if conflict_npv_ancf:
                recommendation += (
                    f" ⚠️ 注意：若误用 NPV 法将选中 {best_npv.project.code}"
                    f"（NPV {best_npv.npv:,.2f} 高于 {best_ancf.project.code} 的 {best_ancf.npv:,.2f}），"
                    f"但该方案寿命更长、年均创造价值反而更低，直接比 NPV 不公平。"
                )

        results.append(MutualGroupResult(
            group=group_name,
            evaluations=evaluations,
            best_by_npv=best_npv,
            best_by_ancf=best_ancf,
            best_by_irr=best_irr,
            conflict_npv_ancf=conflict_npv_ancf,
            conflict_npv_irr=conflict_npv_irr,
            same_life=same_life,
            recommendation=recommendation,
            incremental=incremental,
        ))
    return results


# ======================================================================
# 二、资本限额 — 排序法
# ======================================================================
@dataclass
class PortfolioResult:
    """一个投资组合方案的结果。

    Attributes
    ----------
    method : str
        求解方法名称。
    selected : list of Evaluation
        入选项目（按 PI 或编号排序）。
    rejected : list of Evaluation
        落选项目。
    total_investment : float
        合计投资额。
    total_npv : float
        组合净现值合计。
    budget : float
        资本限额。
    utilization : float
        额度使用率。
    idle_budget : float
        闲置额度。
    note : str
        方法说明 / 局限提示。
    """

    method: str
    selected: List[Evaluation]
    rejected: List[Evaluation]
    total_investment: float
    total_npv: float
    budget: float
    utilization: float
    idle_budget: float
    note: str = ""

    @property
    def codes(self) -> str:
        """入选项目编号，逗号分隔。"""
        return " + ".join(e.project.code for e in self.selected) or "（空组合）"

    def to_dict(self) -> Dict:
        """导出为扁平字典（用于报告表格）。"""
        return {
            "求解方法": self.method,
            "入选项目": self.codes,
            "入选数量": len(self.selected),
            "合计投资(万元)": round(self.total_investment, 2),
            "组合NPV(万元)": round(self.total_npv, 2),
            "额度使用率": f"{self.utilization:.2%}",
            "闲置额度(万元)": round(self.idle_budget, 2),
        }


def _check_budget(budget: float) -> float:
    """校验资本限额，返回 float 化的额度。

    Parameters
    ----------
    budget : float
        资本限额（万元）。

    Returns
    -------
    float
        校验通过的额度。

    Raises
    ------
    ValueError
        额度为负数时抛出。额度为 0 是合法输入（表示"本期无可用资金"，
        三种方法都会返回空组合），因此不作限制。
    """
    value = float(budget)
    if value != value:                      # NaN 自查（NaN != NaN）
        raise ValueError("资本限额不能为 NaN。")
    if value < 0:
        raise ValueError(
            f"资本限额不能为负数，当前为 {value:,.2f} 万元。"
            f"若本期无可用资金请传入 0。"
        )
    return value


def ranking_method(
    projects: Sequence[Project],
    rate: float,
    budget: float,
) -> PortfolioResult:
    """排序法（盈利能力指数 PI 降序贪心）。

    Parameters
    ----------
    projects : Sequence[Project]
        候选项目。
    rate : float
        折现率。
    budget : float
        资本限额。

    Returns
    -------
    PortfolioResult

    Notes
    -----
    算法：先剔除 NPV ≤ 0 的项目（负 NPV 项目不应投资），
    再按 PI 降序依次装入，放得下就选、放不下就跳过。
    时间复杂度 O(n log n)，但 **不保证全局最优**。
    """
    budget = _check_budget(budget)

    valid = [Evaluation.build(p, rate) for p in projects]
    valid = [e for e in valid if e.npv > 0]          # 负 NPV 项目直接排除
    ordered = sorted(valid, key=lambda e: e.pi, reverse=True)

    selected: List[Evaluation] = []
    remaining = float(budget)
    for e in ordered:
        if e.project.initial_investment <= remaining + 1e-9:
            selected.append(e)
            remaining -= e.project.initial_investment

    selected.sort(key=lambda e: e.project.code)
    selected_codes = {e.project.code for e in selected}
    rejected = [e for e in valid if e.project.code not in selected_codes]

    total_inv = sum(e.project.initial_investment for e in selected)
    total_npv = sum(e.npv for e in selected)
    return PortfolioResult(
        method="排序法（PI 贪心）",
        selected=selected,
        rejected=rejected,
        total_investment=total_inv,
        total_npv=total_npv,
        budget=budget,
        utilization=total_inv / budget if budget else 0.0,
        idle_budget=max(0.0, budget - total_inv),
        note="按盈利能力指数降序贪心装入；假设资金不可分割时可能非全局最优。",
    )


# ======================================================================
# 三、资本限额 — 组合法（穷举 / DFS 剪枝）
# ======================================================================
def combination_method(
    projects: Sequence[Project],
    rate: float,
    budget: float,
    max_projects_for_exhaustive: int = 22,
) -> PortfolioResult:
    """组合法：枚举所有可行组合，取 NPV 合计最大者（**保证全局最优**）。

    Parameters
    ----------
    projects : Sequence[Project]
        候选项目。
    rate : float
        折现率。
    budget : float
        资本限额。
    max_projects_for_exhaustive : int
        允许穷举的最大项目数。超过该值时改用启发式并给出提示，
        以避免 2^n 组合爆炸。

    Returns
    -------
    PortfolioResult

    Notes
    -----
    实现方式：DFS + 剪枝。

    * **可行性剪枝**：当前累计投资额 + 待选项目投资额 > 预算则跳过；
    * **最优性剪枝**：若 当前 NPV + 剩余全部项目 NPV 之和 ≤ 已知最优解，
      则该分支不可能更优，直接回溯。

    剪枝后实际搜索节点数远小于 2^n，可轻松处理 20 个项目以上。
    """
    budget = _check_budget(budget)

    evals = [Evaluation.build(p, rate) for p in projects]
    # 负 NPV 项目一定不入选，提前剔除可大幅缩小搜索空间
    evals = [e for e in evals if e.npv > 0]
    n = len(evals)

    if n > max_projects_for_exhaustive:
        result = ranking_method(projects, rate, budget)
        result.method = "组合法（降级→排序法）"
        result.note = (
            f"候选项目数 {n} 超过穷举上限 {max_projects_for_exhaustive}，"
            f"已自动降级为排序法。如需精确解请改用 knapsack_method。"
        )
        return result

    # 按 PI 降序排列，让高收益项目先进入搜索路径，便于剪枝尽早生效
    evals.sort(key=lambda e: e.pi, reverse=True)
    investments = [e.project.initial_investment for e in evals]
    npvs = [e.npv for e in evals]

    # 后缀和：用于最优性剪枝上界
    suffix_npv = [0.0] * (n + 1)
    for i in range(n - 1, -1, -1):
        suffix_npv[i] = suffix_npv[i + 1] + npvs[i]

    best = {"npv": 0.0, "mask": 0}

    def dfs(idx: int, remaining: float, current_npv: float, mask: int) -> None:
        # 最优性剪枝：即便把剩余项目全部装入也不如当前最优解 → 回溯
        if current_npv + suffix_npv[idx] <= best["npv"] + 1e-9:
            return
        if idx == n:
            if current_npv > best["npv"]:
                best["npv"] = current_npv
                best["mask"] = mask
            return
        # 分支 1：装入第 idx 个项目（可行性剪枝）
        if investments[idx] <= remaining + 1e-9:
            dfs(idx + 1, remaining - investments[idx], current_npv + npvs[idx], mask | (1 << idx))
        # 分支 2：跳过第 idx 个项目
        dfs(idx + 1, remaining, current_npv, mask)

    dfs(0, float(budget), 0.0, 0)

    selected = [evals[i] for i in range(n) if best["mask"] >> i & 1]
    selected.sort(key=lambda e: e.project.code)
    selected_codes = {e.project.code for e in selected}
    rejected = [e for e in evals if e.project.code not in selected_codes]

    total_inv = sum(e.project.initial_investment for e in selected)
    total_npv = sum(e.npv for e in selected)
    return PortfolioResult(
        method="组合法（DFS 穷举 + 剪枝）",
        selected=selected,
        rejected=rejected,
        total_investment=total_inv,
        total_npv=total_npv,
        budget=budget,
        utilization=total_inv / budget if budget else 0.0,
        idle_budget=max(0.0, budget - total_inv),
        note=f"已搜索全部可行组合（候选 {n} 个项目），结果 **保证全局最优**。",
    )


# ======================================================================
# 四、资本限额 — 0-1 背包动态规划（大规模场景备选）
# ======================================================================
def knapsack_method(
    projects: Sequence[Project],
    rate: float,
    budget: float,
    unit: float = 1.0,
) -> PortfolioResult:
    """0-1 背包动态规划法（适用于项目数很多、额度可整数化的场景）。

    Parameters
    ----------
    projects : Sequence[Project]
        候选项目。
    rate : float
        折现率。
    budget : float
        资本限额（万元）。
    unit : float
        额度离散化单位（万元），默认 1 万元。单位越小结果越精确、耗时越长。

    Returns
    -------
    PortfolioResult

    Notes
    -----
    状态定义：``dp[b]`` = 使用额度不超过 b 时能获得的组合 NPV 最大值。
    转移方程：``dp[b] = max(dp[b], dp[b - cost_i] + npv_i)``。
    时间复杂度 O(n × Budget / unit)，适用于 n > 22 且预算量级可控的场景。

    ⚠️ 离散化会引入误差：单位取 1 万元时，组合投资额最多被高估 1 万元，
    一般情况下不影响最优组合的选取；追求严格精确时应使用组合法。
    """
    budget = _check_budget(budget)

    evals = [Evaluation.build(p, rate) for p in projects]
    evals = [e for e in evals if e.npv > 0]

    capacity = int(budget // unit)
    costs = [int(round(e.project.initial_investment / unit)) for e in evals]
    values = [e.npv for e in evals]

    dp = [0.0] * (capacity + 1)
    choice = [[False] * (capacity + 1) for _ in range(len(evals))]

    for i, (cost, value) in enumerate(zip(costs, values)):
        if cost > capacity:
            continue
        # 逆序遍历容量，保证每个项目最多被选一次（0-1 背包）
        for b in range(capacity, cost - 1, -1):
            if dp[b - cost] + value > dp[b] + 1e-9:
                dp[b] = dp[b - cost] + value
                choice[i][b] = True

    # 回溯求解选了哪些项目
    selected_idx: List[int] = []
    b = capacity
    for i in range(len(evals) - 1, -1, -1):
        if choice[i][b]:
            selected_idx.append(i)
            b -= costs[i]

    selected = [evals[i] for i in selected_idx]
    selected.sort(key=lambda e: e.project.code)
    selected_codes = {e.project.code for e in selected}
    rejected = [e for e in evals if e.project.code not in selected_codes]

    total_inv = sum(e.project.initial_investment for e in selected)
    total_npv = sum(e.npv for e in selected)
    return PortfolioResult(
        method=f"背包法（0-1 DP，单位 {unit:g} 万元）",
        selected=selected,
        rejected=rejected,
        total_investment=total_inv,
        total_npv=total_npv,
        budget=budget,
        utilization=total_inv / budget if budget else 0.0,
        idle_budget=max(0.0, budget - total_inv),
        note=f"按 {unit:g} 万元离散化后动态规划求解；组合法已验证最优性时二者应一致。",
    )


# ======================================================================
# 五、综合优化入口
# ======================================================================
@dataclass
class OptimizationReport:
    """资本限额组合优化的完整对比报告。

    Attributes
    ----------
    results : dict of str → PortfolioResult
        各方法的求解结果，键为方法短名。
    best : PortfolioResult
        推荐采用的最优组合。
    comparison : str
        方法对比结论文案（含排序法失效的定量说明）。
    """

    results: Dict[str, PortfolioResult]
    best: PortfolioResult
    comparison: str


def optimize_portfolio(
    projects: Sequence[Project],
    rate: float,
    budget: float,
    run_knapsack: bool = True,
) -> OptimizationReport:
    """资本限额下的项目组合优化（三方法并行对比）。

    Parameters
    ----------
    projects : Sequence[Project]
        候选项目。
    rate : float
        折现率。
    budget : float
        资本限额。
    run_knapsack : bool
        是否同时运行背包法作为交叉验证。

    Returns
    -------
    OptimizationReport
        含排序法 / 组合法（/ 背包法）结果与对比结论。

    Notes
    -----
    推荐采用 **组合法** 结果作为最终投资组合，因为它是唯一保证
    全局最优的方法；排序法结果用于展示"贪心策略为何失效"；
    背包法结果用于交叉验证组合法的正确性。
    """
    budget = _check_budget(budget)

    ranking = ranking_method(projects, rate, budget)
    combination = combination_method(projects, rate, budget)
    results: Dict[str, PortfolioResult] = {
        "排序法": ranking,
        "组合法": combination,
    }
    if run_knapsack:
        try:
            results["背包法"] = knapsack_method(projects, rate, budget, unit=1.0)
        except Exception:  # pragma: no cover - 极端规模下的保护
            pass

    best = combination
    # ---------- 生成对比结论 ----------
    gap = combination.total_npv - ranking.total_npv
    if gap > 1e-6:
        comparison = (
            f"**排序法未能取得最优解。** 排序法组合 [{ranking.codes}] 的 NPV 合计为 "
            f"{ranking.total_npv:,.2f} 万元，剩余闲置额度 {ranking.idle_budget:,.2f} 万元"
            f"（使用率仅 {ranking.utilization:.2%}）；"
            f"组合法给出的最优组合 [{combination.codes}] 的 NPV 合计为 "
            f"{combination.total_npv:,.2f} 万元，额度使用率 {combination.utilization:.2%}，"
            f"较排序法多创造价值 **{gap:,.2f} 万元（提升 {gap / abs(ranking.total_npv):.2%}）**。\n\n"
            f"**原因分析**：排序法按盈利能力指数 PI 降序装入，"
            f"优先选中了 PI 最高的 {ranking.selected[0].project.code}"
            f"（投资 {ranking.selected[0].project.initial_investment:,.0f} 万元）等方案，"
            f"挤占了额度并产生 {ranking.idle_budget:,.2f} 万元碎片化闲置额度，"
            f"使后续项目无法装入；而组合法通过穷举全部可行组合，"
            f"找到了额度利用率更高、整体 NPV 更大的组合。"
            f"结论：**资本额度不可分割时，排序法（PI 贪心）不保证最优，应使用组合法。**"
        )
    else:
        comparison = (
            f"本案例中排序法与组合法结论一致（均为 [{combination.codes}]，"
            f"NPV 合计 {combination.total_npv:,.2f} 万元）。"
            f"排序法在额度可被充分利用时通常也能取得最优解，"
            f"但其最优性不受理论保证，工程实践中仍建议以组合法结果为准。"
        )

    if "背包法" in results:
        kb = results["背包法"]
        consistent = abs(kb.total_npv - combination.total_npv) < 1e-6
        comparison += (
            f"\n\n**交叉验证**：背包法（0-1 动态规划）得到组合 [{kb.codes}]，"
            f"NPV 合计 {kb.total_npv:,.2f} 万元，与组合法结果"
            f"{'完全一致，验证了穷举求解的正确性' if consistent else '存在差异（离散化误差或并列最优）'}。"
        )

    return OptimizationReport(results=results, best=best, comparison=comparison)
