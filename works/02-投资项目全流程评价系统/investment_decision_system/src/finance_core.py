# -*- coding: utf-8 -*-
"""
finance_core.py — 投资决策核心评价模型
====================================================================
本模块对应课程 **第 5 章** 的核心计算引擎，实现：

1. 净现值 NPV 计算（支持任意期数、任意折现率）
2. 内含报酬率 IRR 计算（数值稳健，且能识别"多重 IRR"异常情形）
3. 年金净流量 ANCF（等额年金法 / EAA，用于不同寿命互斥项目优选）
4. 辅助指标：盈利能力指数 PI、静态回收期、动态回收期、修正内部收益率 MIRR
5. 增量现金流 IRR（互斥项目增量分析法的判定依据）

------------------------------------------------------------------
现金流符号约定（全模块统一，非常重要）
------------------------------------------------------------------
``cash_flows`` 一律表示 **t = 1, 2, ..., n 各期期末的净现金流**
（经营净现金流 + 期末残值回收，正值表示流入）；
``initial_investment`` 一律表示 **t = 0 的初始投资额，用正数输入**
（内部自动取负号）。

即：完整现金流序列为 ``[-I0, CF1, CF2, ..., CFn]``，
其净现值定义为：

    NPV = -I0 + Σ(t=1..n) CFt / (1 + r)^t

这样的约定避免了"现金流正负号到底怎么写"的歧义，调用方只需按
会计直觉填写：投入多少、每年收回多少。

------------------------------------------------------------------
数值方法说明
------------------------------------------------------------------
IRR 的求解本质是求方程 NPV(r) = 0 的根。该方程等价于一个 n 次多项式，
可能出现 **0 个、1 个或多个** 大于 -1 的实根：

* 常规现金流（仅一次符号变化）→ 有且仅有 1 个 IRR，由笛卡尔符号法则保证；
* 非常规现金流（多次符号变化，如采掘业"投产-治理-再投产"）→ 可能出现
  多重 IRR，此时 IRR 指标失效，本模块会显式报出全部实根并给出告警。

因此本模块采用 **"网格扫描 + Brent 精解"** 的稳健策略，而非直接调用
简单的牛顿迭代：先在一维网格上定位 NPV 变号区间，再对每个区间用
``scipy.optimize.brentq`` 精确定位，可同时捕获全部实根。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np
from scipy.optimize import brentq

__all__ = [
    "build_full_cash_flows",
    "npv",
    "npv_of_full",
    "irr",
    "irr_all_roots",
    "irr_details",
    "npv_curve",
    "pvifa",
    "annuity_net_cash_flow",
    "profitability_index",
    "payback_period",
    "discounted_payback_period",
    "mirr",
    "incremental_irr",
    "IRRResult",
]

# IRR 搜索区间：折现率下界取 -0.99（避免 (1+r) → 0 导致除零），上界取 500%
_IRR_LOWER_BOUND: float = -0.99
_IRR_UPPER_BOUND: float = 5.00
_IRR_GRID_POINTS: int = 2000


# ======================================================================
# 一、基础工具
# ======================================================================
def build_full_cash_flows(
    cash_flows: Sequence[float],
    initial_investment: float = 0.0,
) -> np.ndarray:
    """构造完整现金流序列 ``[-I0, CF1, ..., CFn]``。

    Parameters
    ----------
    cash_flows : Sequence[float]
        t = 1..n 各期期末净现金流。
    initial_investment : float, optional
        t = 0 初始投资额（正数输入，内部取负）。默认 0。

    Returns
    -------
    numpy.ndarray
        长度为 n + 1 的完整现金流数组，索引即时间点 t。

    Raises
    ------
    ValueError
        当现金流为空，或出现负的初始投资额时。

    Examples
    --------
    >>> build_full_cash_flows([500, 500, 500], 1000)
    array([-1000.,   500.,   500.,   500.])
    """
    cf = np.asarray(list(cash_flows), dtype=float)
    if cf.size == 0:
        raise ValueError("cash_flows 不能为空，至少需要一期现金流。")
    if initial_investment < 0:
        raise ValueError(
            "initial_investment 请用正数输入初始投资额（内部的负号由本函数自动处理）。"
        )
    return np.concatenate(([-float(initial_investment)], cf))


def pvifa(rate: float, periods: int) -> float:
    """计算年金现值系数 PVIFA(r, n) = [1 - (1 + r)^(-n)] / r。

    Parameters
    ----------
    rate : float
        折现率，小数形式（如 0.10 表示 10%）。
    periods : int
        期数 n。

    Returns
    -------
    float
        年金现值系数。当 ``rate == 0`` 时按极限值 n 处理。

    Notes
    -----
    这是年金净流量法（等额年金法）的核心系数，用于把不同寿命项目的
    NPV 折算成可比口径的"每年等额净流量"。
    """
    if periods <= 0:
        raise ValueError("periods 必须为正整数。")
    if abs(rate) < 1e-12:
        return float(periods)      # lim(r→0) PVIFA = n
    return (1.0 - (1.0 + rate) ** (-periods)) / rate


# ======================================================================
# 二、净现值 NPV
# ======================================================================
def npv_of_full(rate: float, full_cash_flows: Sequence[float]) -> float:
    """对完整现金流序列（含 t = 0）计算净现值。

    公式：NPV = Σ(t=0..n) CFt / (1 + r)^t

    Parameters
    ----------
    rate : float
        折现率，小数形式。
    full_cash_flows : Sequence[float]
        完整现金流，索引 0 为 t = 0。

    Returns
    -------
    float
        净现值。

    Raises
    ------
    ValueError
        当折现率 ≤ -100%（即 1 + r ≤ 0）时无法折现。
    """
    if rate <= -1.0:
        raise ValueError("折现率必须大于 -100%，否则折现因子无意义。")
    cf = np.asarray(list(full_cash_flows), dtype=float)
    t = np.arange(cf.size)
    discount_factors = (1.0 + rate) ** (-t)
    return float(np.dot(cf, discount_factors))


def npv(
    rate: float,
    cash_flows: Sequence[float],
    initial_investment: float = 0.0,
) -> float:
    """计算项目净现值 NPV。

    这是本系统最核心的评价函数，支持自定义初始投资、各期现金流、折现率。

    Parameters
    ----------
    rate : float
        折现率（资本成本 / 投资者要求报酬率），小数形式。例如 0.10。
    cash_flows : Sequence[float]
        t = 1..n 各期期末净现金流。允许各期金额不等、允许负值（如追加投资）。
    initial_investment : float, optional
        t = 0 初始投资额，**正数输入**。默认 0。

    Returns
    -------
    float
        净现值。NPV > 0 表示项目创造价值，方案可行。

    Notes
    -----
    * 若现金流在第 0 期也有流入（如营运资金回收前置），可将其并入
      ``cash_flows`` 的第 1 期，或直接调用 :func:`npv_of_full`。
    * 各期期限视为等长（年度），若为不规则期限应改用 XIRR 模型。

    Examples
    --------
    >>> round(npv(0.10, [500, 500, 500], 1000), 2)
    243.43

    含义：初始投入 1000，连续 3 年每年收回 500，按 10% 折现，
    项目净现值为 +243.43，方案可行。
    """
    full_cf = build_full_cash_flows(cash_flows, initial_investment)
    return npv_of_full(rate, full_cf)


# ======================================================================
# 三、内含报酬率 IRR
# ======================================================================
@dataclass
class IRRResult:
    """IRR 求解结果容器。

    Attributes
    ----------
    irr : float or None
        主 IRR（最接近合理取值区间的实根）。无实根时为 None。
    all_roots : list of float
        方程 NPV(r) = 0 在 (-99%, 500%] 区间内的 **全部** 实根。
    is_unique : bool
        是否唯一实根。False 表示存在多重 IRR，此时 IRR 指标不可靠。
    npv_at_irr : float
        在返回的 irr 处回代计算的 NPV（用于精度自检，应≈0）。
    """

    irr: Optional[float]
    all_roots: List[float] = field(default_factory=list)
    is_unique: bool = True
    npv_at_irr: float = 0.0

    def __str__(self) -> str:  # pragma: no cover - 展示用
        if self.irr is None:
            return "IRR 无实根（该项目在 -99%~500% 区间内不存在使 NPV=0 的折现率）"
        flag = "" if self.is_unique else f"（注意：存在多重 IRR，全部实根 = {[f'{r:.2%}' for r in self.all_roots]}）"
        return f"IRR = {self.irr:.4%}{flag}"


def irr_all_roots(
    cash_flows: Sequence[float],
    initial_investment: float = 0.0,
    lower: float = _IRR_LOWER_BOUND,
    upper: float = _IRR_UPPER_BOUND,
    grid_points: int = _IRR_GRID_POINTS,
) -> List[float]:
    """求 NPV(r) = 0 在指定区间内的全部实根。

    算法：网格扫描定位变号区间 → 对每个区间用 Brent 法精解。

    Parameters
    ----------
    cash_flows : Sequence[float]
        t = 1..n 各期期末净现金流。
    initial_investment : float
        t = 0 初始投资额（正数）。
    lower, upper : float
        搜索区间，默认 (-0.99, 5.00)。
    grid_points : int
        网格点数，越大越不容易漏根（代价是耗时线性增加）。

    Returns
    -------
    list of float
        升序排列的全部实根。
    """
    full_cf = build_full_cash_flows(cash_flows, initial_investment)
    rates = np.linspace(lower, upper, grid_points)
    values = np.array([npv_of_full(r, full_cf) for r in rates])

    roots: List[float] = []
    for i in range(grid_points - 1):
        v1, v2 = values[i], values[i + 1]
        if v1 == 0.0:
            roots.append(float(rates[i]))
        elif v1 * v2 < 0:
            root = brentq(
                lambda r: npv_of_full(r, full_cf),
                rates[i], rates[i + 1],
                xtol=1e-12, rtol=1e-14, maxiter=200,
            )
            roots.append(float(root))

    # 去重（相邻网格点可能捕获同一个根）
    unique_roots: List[float] = []
    for r in roots:
        if not unique_roots or abs(r - unique_roots[-1]) > 1e-6:
            unique_roots.append(r)
    return sorted(unique_roots)


def irr_details(
    cash_flows: Sequence[float],
    initial_investment: float = 0.0,
) -> IRRResult:
    """求解 IRR 并附带多重根诊断信息。

    Parameters
    ----------
    cash_flows : Sequence[float]
        t = 1..n 各期期末净现金流。
    initial_investment : float
        t = 0 初始投资额（正数）。

    Returns
    -------
    IRRResult
        含主 IRR、全部实根、唯一性标记与回代精度。

    Notes
    -----
    多重根时的"主 IRR"选取规则：优先取 **最接近常规折现率区间
    [0%, 100%] 且 NPV 一阶导为负** 的根（经济含义上最可能是真实
    的边际报酬率）；若均不在该区间，则取绝对值最小的正根。
    """
    roots = irr_all_roots(cash_flows, initial_investment)
    if not roots:
        return IRRResult(irr=None, all_roots=[], is_unique=True, npv_at_irr=float("nan"))

    full_cf = build_full_cash_flows(cash_flows, initial_investment)

    if len(roots) == 1:
        main = roots[0]
    else:
        # 优先在 [0, 1] 区间内挑选 NPV 递减的根
        in_range = [r for r in roots if 0.0 <= r <= 1.0]
        candidates = in_range if in_range else [r for r in roots if r > 0] or roots
        main = min(candidates, key=lambda r: abs(r - 0.10))

    residual = npv_of_full(main, full_cf)
    return IRRResult(
        irr=main,
        all_roots=roots,
        is_unique=(len(roots) == 1),
        npv_at_irr=residual,
    )


def irr(
    cash_flows: Sequence[float],
    initial_investment: float = 0.0,
) -> Optional[float]:
    """计算项目内含报酬率 IRR。

    IRR 是使项目净现值恰好为 0 的折现率，反映项目自身的报酬率水平。

    Parameters
    ----------
    cash_flows : Sequence[float]
        t = 1..n 各期期末净现金流。
    initial_investment : float
        t = 0 初始投资额（正数）。

    Returns
    -------
    float or None
        IRR（小数形式，如 0.1835 表示 18.35%）。若区间内无实根返回 None。

    Notes
    -----
    判定标准：IRR > 资本成本（必要报酬率）→ 方案可行。
    若项目存在多重 IRR，本函数只返回主 IRR，**请改用**
    :func:`irr_details` 查看全部实根后再做判断。

    Examples
    --------
    >>> r = irr([500, 500, 500], 1000)
    >>> round(r, 4)
    0.2338
    """
    return irr_details(cash_flows, initial_investment).irr


def npv_curve(
    cash_flows: Sequence[float],
    initial_investment: float = 0.0,
    rate_min: float = 0.0,
    rate_max: float = 0.50,
    points: int = 200,
) -> Tuple[np.ndarray, np.ndarray]:
    """生成"折现率 — NPV"关系曲线数据，用于绘图。

    Parameters
    ----------
    cash_flows : Sequence[float]
        t = 1..n 各期期末净现金流。
    initial_investment : float
        t = 0 初始投资额（正数）。
    rate_min, rate_max : float
        横轴折现率范围。
    points : int
        采样点数。

    Returns
    -------
    (numpy.ndarray, numpy.ndarray)
        ``(rates, npv_values)`` 两个等长数组。

    Notes
    -----
    曲线与横轴的交点即为该项目的 IRR，因此该曲线同时承担"IRR 与
    折现率关系曲线"的可视化任务。
    """
    full_cf = build_full_cash_flows(cash_flows, initial_investment)
    rates = np.linspace(rate_min, rate_max, points)
    values = np.array([npv_of_full(r, full_cf) for r in rates])
    return rates, values


# ======================================================================
# 四、年金净流量法（等额年金 EAA）
# ======================================================================
def annuity_net_cash_flow(
    npv_value: float,
    rate: float,
    life: int,
) -> float:
    """把 NPV 折算为"年金净流量 ANCF"（等额年金 EAA）。

    公式：ANCF = NPV / PVIFA(r, n) = NPV × r / [1 - (1+r)^(-n)]

    Parameters
    ----------
    npv_value : float
        项目净现值。
    rate : float
        折现率。
    life : int
        项目寿命期（年）。

    Returns
    -------
    float
        年金净流量，经济含义为"项目在其寿命内每年创造的等额净价值"。

    Notes
    -----
    该方法的关键价值：把寿命期不同的项目折算到 **同一可比口径**
    （每年等额），解决 NPV 法在寿命不等时直接比较不公平的问题。
    判定规则：ANCF 越大方案越优；ANCF > 0 项目可行。
    """
    return float(npv_value) / pvifa(rate, life)


# ======================================================================
# 五、辅助评价指标
# ======================================================================
def profitability_index(
    npv_value: float,
    initial_investment: float,
) -> float:
    """计算盈利能力指数（现值指数）PI。

    公式：PI = (NPV + I0) / I0 = 未来现金流现值合计 / 初始投资额

    Parameters
    ----------
    npv_value : float
        项目净现值。
    initial_investment : float
        初始投资额（正数）。

    Returns
    -------
    float
        PI。PI > 1 表示方案可行，且 PI 是 **资本限额下排序法** 的核心排序依据
        （单位投资额创造的现值最大者优先）。
    """
    if initial_investment <= 0:
        raise ValueError("initial_investment 必须为正数才能计算盈利能力指数。")
    return (float(npv_value) + float(initial_investment)) / float(initial_investment)


def payback_period(
    cash_flows: Sequence[float],
    initial_investment: float,
) -> Optional[float]:
    """计算静态投资回收期（不考虑资金时间价值）。

    Parameters
    ----------
    cash_flows : Sequence[float]
        t = 1..n 各期期末净现金流。
    initial_investment : float
        初始投资额（正数）。

    Returns
    -------
    float or None
        回收期（年），采用线性插值确定不足整年的部分；寿命内未收回返回 None。

    Notes
    -----
    回收期是**风险与流动性**指标而非盈利指标：回收越快，项目抵御
    长期不确定性的能力越强，因此常用于辅助敏感性分析的风险提示。
    """
    cumulative = -float(initial_investment)
    for idx, cf in enumerate(cash_flows, start=1):
        previous = cumulative
        cumulative += float(cf)
        if cumulative >= 0:
            gap = cumulative - previous
            if abs(gap) < 1e-12:
                return float(idx)
            return float(idx - 1) + (-previous) / gap
    return None


def discounted_payback_period(
    cash_flows: Sequence[float],
    initial_investment: float,
    rate: float,
) -> Optional[float]:
    """计算动态投资回收期（现金流先折现再累计）。

    Parameters
    ----------
    cash_flows : Sequence[float]
        t = 1..n 各期期末净现金流。
    initial_investment : float
        初始投资额（正数）。
    rate : float
        折现率。

    Returns
    -------
    float or None
        动态回收期（年），未收回返回 None。
    """
    cumulative = -float(initial_investment)
    for idx, cf in enumerate(cash_flows, start=1):
        previous = cumulative
        cumulative += float(cf) / (1.0 + rate) ** idx
        if cumulative >= 0:
            gap = cumulative - previous
            if abs(gap) < 1e-12:
                return float(idx)
            return float(idx - 1) + (-previous) / gap
    return None


def mirr(
    cash_flows: Sequence[float],
    initial_investment: float,
    finance_rate: float,
    reinvest_rate: float,
) -> float:
    """计算修正内部收益率 MIRR。

    针对 IRR"隐含再投资假设不合理 + 多重根"两大缺陷的改进指标：
    将各期 **正现金流按再投资率** 复利到期末，**负现金流按融资成本**
    折现到 t = 0，再求解使两端相等的折现率。

    Parameters
    ----------
    cash_flows : Sequence[float]
        t = 1..n 各期期末净现金流。
    initial_investment : float
        t = 0 初始投资额（正数）。
    finance_rate : float
        融资成本（用于折现现金流出）。
    reinvest_rate : float
        再投资率（用于复利现金流入）。

    Returns
    -------
    float
        MIRR。MIRR 恒唯一，是多重 IRR 项目的重要替代判据。
    """
    full_cf = build_full_cash_flows(cash_flows, initial_investment)
    n = full_cf.size - 1
    pv_outflows = 0.0     # 现金流出（负值）折现到 0 时点
    fv_inflows = 0.0      # 现金流入（正值）复利到 n 时点
    for t, cf in enumerate(full_cf):
        if cf < 0:
            pv_outflows += cf / (1.0 + finance_rate) ** t
        else:
            fv_inflows += cf * (1.0 + reinvest_rate) ** (n - t)
    if pv_outflows == 0:
        return float("inf")
    return (fv_inflows / (-pv_outflows)) ** (1.0 / n) - 1.0


# ======================================================================
# 六、互斥项目的增量分析
# ======================================================================
def incremental_irr(
    cf_a: Sequence[float],
    cf_b: Sequence[float],
    inv_a: float,
    inv_b: float,
) -> IRRResult:
    """计算增量现金流（B - A）的内含报酬率，用于互斥项目增量分析法。

    Parameters
    ----------
    cf_a, cf_b : Sequence[float]
        方案 A、方案 B 的各期净现金流（长度需一致，不一致时补零对齐）。
    inv_a, inv_b : float
        方案 A、方案 B 的初始投资额（正数）。

    Returns
    -------
    IRRResult
        增量 IRR 结果。

    Notes
    -----
    判别规则：设 B 为投资额较大的方案，若 ΔIRR > 资本成本，
    则增量投资是划算的，应 **选 B**；否则应选投资较小的 A。
    当增量现金流仍为常规形态时，ΔIRR 唯一。
    """
    n = max(len(cf_a), len(cf_b))
    a = list(cf_a) + [0.0] * (n - len(cf_a))
    b = list(cf_b) + [0.0] * (n - len(cf_b))
    delta_cf = [bi - ai for ai, bi in zip(a, b)]
    delta_inv = float(inv_b) - float(inv_a)
    # 增量投资为负说明实际是 A 更大，统一翻转为"大减小"以保证符号方向清晰
    if delta_inv < 0:
        delta_cf = [-x for x in delta_cf]
        delta_inv = -delta_inv
    return irr_details(delta_cf, delta_inv)
