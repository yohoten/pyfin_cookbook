# -*- coding: utf-8 -*-
"""
visualizer.py — 可视化输出模块
====================================================================
本模块负责生成全部图表，输出目录为 ``outputs/figures/``。

图表清单
--------
======================  ============================================  ==================
函数                     图表                                          对应要求
======================  ============================================  ==================
plot_npv_comparison     多项目 NPV 对比柱状图（附 IRR 标注）             NVP 对比柱状图
plot_irr_vs_rate        NPV—折现率关系曲线族 + IRR 交点                IRR 与折现率曲线
plot_tornado            单因素敏感性 tornado（旋风图）                 敏感性旋风图
plot_cash_flows         各项目现金流结构对比（分组柱状图）               现金流结构
plot_two_way_heatmap    折现率 × 现金流 双因素热力图                   联动敏感性
plot_portfolio          资本限额额度占用与组合 NPV 对比                  资本分配
plot_mutual_group       互斥组多指标对比（NPV / ANCF / IRR）            互斥优选
======================  ============================================  ==================

配色约定
--------
遵循国内财务惯例：**红色代表正向收益（NPV > 0），绿色代表负向（NPV < 0）**，
与欧美习惯相反。该约定集中在 :mod:`src.config` 中定义，便于统一调整。
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

from .config import (
    COLOR_BASE,
    COLOR_HIGHLIGHT,
    COLOR_NEGATIVE,
    COLOR_NEUTRAL,
    COLOR_POSITIVE,
    FIGURE_DIR,
    PALETTE,
    setup_matplotlib_chinese,
)
from .models import Evaluation, Project
from .optimizer import MutualGroupResult, PortfolioResult
from .sensitivity import SensitivityResult

# 模块导入时即完成字体配置，避免调用方忘记配置导致中文乱码
setup_matplotlib_chinese()

__all__ = [
    "plot_npv_comparison",
    "plot_irr_vs_rate",
    "plot_tornado",
    "plot_cash_flows",
    "plot_two_way_heatmap",
    "plot_portfolio",
    "plot_mutual_group",
]


def _save(fig, filename: str) -> Path:
    """保存图形并关闭，返回文件路径。

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        图形对象。
    filename : str
        文件名（不含目录）。

    Returns
    -------
    pathlib.Path
        保存后的绝对路径。
    """
    path = FIGURE_DIR / filename
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


# ======================================================================
# 1. 多项目 NPV 对比柱状图
# ======================================================================
def plot_npv_comparison(
    evaluations: Sequence[Evaluation],
    title: str = "各项目净现值（NPV）对比",
    filename: str = "01_npv_comparison.png",
    show_irr: bool = True,
) -> Path:
    """绘制多项目 NPV 对比柱状图。

    Parameters
    ----------
    evaluations : Sequence[Evaluation]
        项目评价结果列表（建议不超过 14 个，避免横轴拥挤）。
    title : str
        图标题。
    filename : str
        输出文件名。
    show_irr : bool
        是否在柱顶标注 IRR。

    Returns
    -------
    pathlib.Path
        图片路径。

    Notes
    -----
    * 红色柱 = NPV > 0（可行），绿色柱 = NPV < 0（不可行）；
    * 灰色虚线为零基准线，深蓝虚线标注基准折现率下的整体判断水位。
    """
    codes = [f"{e.project.code}\n{e.project.name[:8]}" for e in evaluations]
    npvs = [e.npv for e in evaluations]
    colors = [COLOR_POSITIVE if v > 0 else COLOR_NEGATIVE for v in npvs]

    fig, ax = plt.subplots(figsize=(max(9, len(codes) * 0.85), 5.6))
    bars = ax.bar(range(len(codes)), npvs, color=colors, width=0.62,
                  edgecolor="white", linewidth=0.8, zorder=3)

    # 数值标注
    for bar, value, ev in zip(bars, npvs, evaluations):
        offset = 0.02 * max(abs(v) for v in npvs) if max(abs(v) for v in npvs) > 0 else 1
        va = "bottom" if value >= 0 else "top"
        y = value + offset if value >= 0 else value - offset
        label = f"{value:,.0f}"
        if show_irr and ev.irr is not None:
            label += f"\nIRR {ev.irr:.1%}"
        ax.text(bar.get_x() + bar.get_width() / 2, y, label,
                ha="center", va=va, fontsize=9, zorder=4)

    ax.axhline(0, color=COLOR_BASE, linewidth=1.2, linestyle="-", zorder=2)
    ax.set_xticks(range(len(codes)))
    ax.set_xticklabels(codes, fontsize=9)
    ax.set_ylabel("净现值 NPV（万元）")
    ax.set_title(title, fontsize=13, fontweight="bold", pad=14)
    ax.legend(handles=[
        Patch(facecolor=COLOR_POSITIVE, label="NPV > 0（可行）"),
        Patch(facecolor=COLOR_NEGATIVE, label="NPV < 0（不可行）"),
    ], loc="best", framealpha=0.9)
    ax.margins(y=0.18)
    fig.tight_layout()
    return _save(fig, filename)


# ======================================================================
# 2. NPV — 折现率关系曲线（含 IRR 交点）
# ======================================================================
def plot_irr_vs_rate(
    evaluations: Sequence[Evaluation],
    rate_min: float = 0.0,
    rate_max: float = 0.45,
    title: str = "NPV 与折现率关系曲线（曲线与横轴交点即为 IRR）",
    filename: str = "02_irr_vs_rate.png",
    highlight_rate: Optional[float] = None,
) -> Path:
    """绘制多项目的 NPV—折现率关系曲线族，并标注 IRR 交点。

    Parameters
    ----------
    evaluations : Sequence[Evaluation]
        项目评价结果列表。
    rate_min, rate_max : float
        横轴折现率范围。
    title : str
        图标题。
    filename : str
        输出文件名。
    highlight_rate : float or None
        需要竖线标注的折现率（通常为资本成本）。

    Returns
    -------
    pathlib.Path
        图片路径。

    Notes
    -----
    曲线自上而下穿过横轴的交点即该项目的 IRR：
    * 折现率低于 IRR 时 NPV > 0（可行区，红色阴影）；
    * 折现率高于 IRR 时 NPV < 0（不可行区，绿色阴影）。
    """
    fig, ax = plt.subplots(figsize=(9.6, 6.0))
    ax.axhspan(-1e9, 0, color=COLOR_NEGATIVE, alpha=0.05, zorder=0)
    ax.axhspan(0, 1e9, color=COLOR_POSITIVE, alpha=0.05, zorder=0)

    for idx, ev in enumerate(evaluations):
        rates, values = ev.project.npv_curve(rate_min, rate_max, 240)
        color = PALETTE[idx % len(PALETTE)]
        ax.plot(rates, values, color=color, linewidth=2.0,
                label=f"{ev.project.code}（IRR {ev.irr:.2%}）" if ev.irr is not None
                else f"{ev.project.code}（IRR 无实根）", zorder=3)
        # 标注 IRR 交点
        if ev.irr is not None and rate_min <= ev.irr <= rate_max:
            ax.plot([ev.irr], [0], marker="o", markersize=7, color=color,
                    markeredgecolor="white", markeredgewidth=1.4, zorder=5)
            ax.annotate(f"{ev.irr:.2%}", xy=(ev.irr, 0),
                        xytext=(ev.irr + 0.008, abs(max(values)) * 0.10 + 8),
                        fontsize=9, color=color, fontweight="bold", zorder=6)

    ax.axhline(0, color=COLOR_BASE, linewidth=1.4, zorder=2)
    if highlight_rate is not None:
        ax.axvline(highlight_rate, color=COLOR_HIGHLIGHT, linewidth=1.6,
                   linestyle="--", zorder=2,
                   label=f"资本成本 {highlight_rate:.2%}")
    ax.set_xlabel("折现率 r")
    ax.set_ylabel("净现值 NPV（万元）")
    ax.set_title(title, fontsize=13, fontweight="bold", pad=14)
    ax.xaxis.set_major_formatter(lambda x, _: f"{x:.0%}")
    ax.legend(loc="best", fontsize=8.5, ncol=2, framealpha=0.92)
    fig.tight_layout()
    return _save(fig, filename)


# ======================================================================
# 3. 敏感性分析 tornado 图（旋风图）
# ======================================================================
def plot_tornado(
    sensitivity: SensitivityResult,
    title: Optional[str] = None,
    filename: Optional[str] = None,
) -> Path:
    """绘制单因素敏感性分析 tornado 图（旋风图）。

    Parameters
    ----------
    sensitivity : SensitivityResult
        敏感性分析结果。
    title : str or None
        图标题，默认按项目自动生成。
    filename : str or None
        输出文件名，默认按项目编号自动生成。

    Returns
    -------
    pathlib.Path
        图片路径。

    Notes
    -----
    读图方法：

    * 纵轴为影响因素，**自上而下按影响幅度（swing）降序排列**，
      越靠上的因素越关键（图形呈"上宽下窄"的旋风状，故名 tornado 图）；
    * 中间红色竖线为基准 NPV；
    * 右侧蓝色条 = 因素向有利方向变动后的 NPV；
      左侧橙色条 = 因素向不利方向变动后的 NPV；
    * 若橙色条越过零线（绿色虚线），说明该因素一旦不利变动，
      项目将由可行变为不可行，属 **致命敏感因素**。

    折现率采用绝对百分点扰动（±5pp），初始投资与年现金流采用
    相对比例扰动（±20%），寿命采用 ±1 年 —— 不同因素的口径不同，
    因此图中在每个因素名称后标注了具体扰动幅度。
    """
    project = sensitivity.project
    factors = list(reversed(sensitivity.factors))   # 反转后 barh 使影响大者位于顶部
    base = sensitivity.base_npv
    y_positions = np.arange(len(factors))

    fig, ax = plt.subplots(figsize=(10.2, max(4.4, 1.15 * len(factors) + 2.0)))

    for i, f in enumerate(factors):
        adverse = f.adverse_npv
        favorable = f.favorable_npv
        # 不利方向（NPV 通常下降 → 向左）
        left_start = min(base, adverse)
        ax.barh(i, abs(base - adverse), left=left_start, height=0.52,
                color=COLOR_HIGHLIGHT, alpha=0.88, edgecolor="white",
                linewidth=0.8, zorder=3)
        # 有利方向
        right_start = min(base, favorable)
        ax.barh(i, abs(base - favorable), left=right_start, height=0.52,
                color="#2E5C8A", alpha=0.88, edgecolor="white",
                linewidth=0.8, zorder=3)

        # 端点数值标注：优先置于条形内部端点处，避免与 Y 轴标签重叠；
        # 条形过窄时改为置于条外，并依赖 ax.margins 预留的留白。
        span = max(abs(base), abs(adverse), abs(favorable)) or 1.0
        inside_threshold = span * 0.16
        for value, color_inside, color_outside in (
            (adverse, "#FFFFFF", "#B9530A"),
            (favorable, "#FFFFFF", "#1F4166"),
        ):
            bar_width = abs(base - value)
            if bar_width >= inside_threshold:
                # 条形内部，紧贴端点内侧
                ha = "left" if value <= base else "right"
                x = value + span * 0.012 * (1 if value <= base else -1)
                ax.text(x, i, f"{value:,.0f}", va="center", ha=ha,
                        fontsize=8.5, color=color_inside,
                        fontweight="bold", zorder=6)
            else:
                ha = "right" if value <= base else "left"
                x = value + span * 0.02 * (-1 if value <= base else 1)
                ax.text(x, i, f"{value:,.0f}", va="center", ha=ha,
                        fontsize=8.5, color=color_outside, zorder=6)

    # 基准 NPV 竖线（label 交由下方 legend handles 统一提供，避免图例重复）
    ax.axvline(base, color=COLOR_POSITIVE, linewidth=2.0, zorder=5)
    # 可行性零线
    ax.axvline(0, color=COLOR_NEGATIVE, linewidth=1.5, linestyle="--", zorder=4)

    labels = [
        f"{f.name}\n（{f.adverse_label.split('→')[0].strip()}）" for f in factors
    ]
    ax.set_yticks(y_positions)
    ax.set_yticklabels(labels, fontsize=9.2)
    ax.set_xlabel("净现值 NPV（万元）")
    ax.set_title(
        title or (f"{project.code}（{project.name}）敏感性分析 tornado 图\n"
                  f"基准折现率 {sensitivity.rate:.2%}｜"
                  f"IRR {sensitivity.base_irr:.2%}｜安全边际 {sensitivity.safety_margin * 100:.2f}pp｜"
                  f"抗风险等级「{sensitivity.grade}」" if sensitivity.base_irr is not None else ""),
        fontsize=12.5, fontweight="bold", pad=14,
    )
    ax.legend(handles=[
        Patch(facecolor=COLOR_HIGHLIGHT, label="不利方向变动"),
        Patch(facecolor="#2E5C8A", label="有利方向变动"),
        plt.Line2D([0], [0], color=COLOR_POSITIVE, linewidth=2, label=f"基准 NPV {base:,.0f}"),
        plt.Line2D([0], [0], color=COLOR_NEGATIVE, linewidth=1.5, linestyle="--",
                   label="临界线 NPV = 0"),
    ], loc="lower right", fontsize=8.8, framealpha=0.93)
    ax.margins(x=0.20, y=0.10)
    fig.tight_layout()
    return _save(fig, filename or f"03_tornado_{project.code}.png")


# ======================================================================
# 4. 现金流结构对比图
# ======================================================================
def plot_cash_flows(
    projects: Sequence[Project],
    title: str = "各项目现金流结构对比",
    filename: str = "04_cash_flows.png",
    rate: Optional[float] = None,
) -> Path:
    """绘制各项目分期现金流对比图。

    Parameters
    ----------
    projects : Sequence[Project]
        项目列表（建议 3~6 个，避免图例过密）。
    title : str
        图标题。
    filename : str
        输出文件名。
    rate : float or None
        折现率。提供时额外叠加"折现后现金流"虚线，直观展示时间价值损耗。

    Returns
    -------
    pathlib.Path
        图片路径。
    """
    fig, ax = plt.subplots(figsize=(10.4, 5.8))
    max_life = max(p.life for p in projects)

    for idx, p in enumerate(projects):
        color = PALETTE[idx % len(PALETTE)]
        xs = list(range(1, p.life + 1))
        ax.plot(xs, p.cash_flows, marker="o", markersize=5.2, linewidth=2.0,
                color=color, label=f"{p.code} {p.name[:10]}（{p.life}年）", zorder=3)
        if rate is not None:
            discounted = [cf / (1 + rate) ** t for t, cf in enumerate(p.cash_flows, 1)]
            ax.plot(xs, discounted, linestyle=":", linewidth=1.5, color=color,
                    alpha=0.75, zorder=2)

    ax.axhline(0, color=COLOR_BASE, linewidth=1.2, zorder=2)
    ax.set_xticks(range(1, max_life + 1))
    ax.set_xlabel("运营期（年）")
    ax.set_ylabel("净现金流（万元）")
    ax.set_title(title + (f"\n（虚线为按 {rate:.0%} 折现后的现金流）" if rate else ""),
                 fontsize=13, fontweight="bold", pad=14)
    ax.legend(loc="best", fontsize=8.8, framealpha=0.92)
    fig.tight_layout()
    return _save(fig, filename)


# ======================================================================
# 5. 双因素敏感性热力图
# ======================================================================
def plot_two_way_heatmap(
    project: Project,
    rate: float,
    matrix: List[List[float]],
    rate_axis: Sequence[float],
    cf_axis: Sequence[float],
    filename: Optional[str] = None,
) -> Path:
    """绘制"折现率 × 年现金流"双因素敏感性热力图。

    Parameters
    ----------
    project : Project
        项目。
    rate : float
        基准折现率（用于标题）。
    matrix : list of list of float
        NPV 矩阵，行对应现金流缩放系数、列对应折现率。
    rate_axis : Sequence[float]
        各列对应的折现率。
    cf_axis : Sequence[float]
        各行对应的现金流缩放系数。
    filename : str or None
        输出文件名。

    Returns
    -------
    pathlib.Path
        图片路径。

    Notes
    -----
    使用发散型色标：红色系表示 NPV 为正（可行区），绿色系表示 NPV 为负
    （不可行区），颜色深浅代表数值大小，两色交界处即为可行性分界线。
    """
    data = np.array(matrix, dtype=float)
    fig, ax = plt.subplots(figsize=(8.6, 6.2))
    vmax = float(np.nanmax(np.abs(data))) or 1.0

    im = ax.imshow(data, cmap="RdYlGn_r", aspect="auto",
                   vmin=-vmax, vmax=vmax, origin="lower")

    ax.set_xticks(range(len(rate_axis)))
    ax.set_xticklabels([f"{r:.1%}" for r in rate_axis], fontsize=9)
    ax.set_yticks(range(len(cf_axis)))
    ax.set_yticklabels([f"{c:.0%}" for c in cf_axis], fontsize=9)
    ax.set_xlabel("折现率")
    ax.set_ylabel("年现金流（相对基准的比例）")
    ax.set_title(f"{project.code}（{project.name}）双因素敏感性分析\n"
                 f"基准折现率 {rate:.2%}｜色标越红 NPV 越高、越绿越低",
                 fontsize=12.5, fontweight="bold", pad=13)

    # 单元格标注数值
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            value = data[i, j]
            if np.isnan(value):
                continue
            ax.text(j, i, f"{value:,.0f}", ha="center", va="center", fontsize=8.2,
                    color="white" if abs(value) > vmax * 0.55 else "#1A1A1A")
    # 标注基准点
    base_row = min(range(len(cf_axis)), key=lambda i: abs(cf_axis[i] - 1.0))
    base_col = min(range(len(rate_axis)), key=lambda j: abs(rate_axis[j] - rate))
    ax.add_patch(plt.Rectangle((base_col - 0.5, base_row - 0.5), 1, 1,
                               fill=False, edgecolor="#1A1A1A", linewidth=2.4, zorder=5))
    ax.text(base_col, base_row + 0.42, "基准", ha="center", va="bottom",
            fontsize=8, color="#1A1A1A", zorder=6)

    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
    cbar.set_label("NPV（万元）", fontsize=9.5)
    fig.tight_layout()
    return _save(fig, filename or f"05_dual_sensitivity_{project.code}.png")


# ======================================================================
# 6. 资本限额组合结果图
# ======================================================================
def plot_portfolio(
    comparison: Dict[str, PortfolioResult],
    budget: float,
    title: str = "资本限额下的项目组合优化结果",
    filename: str = "06_portfolio.png",
) -> Path:
    """绘制资本限额下的组合优化对比图（额度占用 + 组合 NPV）。

    Parameters
    ----------
    comparison : dict of str → PortfolioResult
        各方法的求解结果。
    budget : float
        资本限额。
    title : str
        图标题。
    filename : str
        输出文件名。

    Returns
    -------
    pathlib.Path
        图片路径。

    Notes
    -----
    左图：各方法入选项目的投资额堆叠条，配合限额红线，直观展示
    "排序法留下的闲置额度"；右图：各方法的组合 NPV 合计对比柱状图。
    """
    methods = list(comparison.keys())
    fig, axes = plt.subplots(1, 2, figsize=(13.0, 5.8),
                            gridspec_kw={"width_ratios": [1.55, 1.0]})

    # ---------- 左图：额度占用堆叠 ----------
    ax = axes[0]
    for i, m in enumerate(methods):
        result = comparison[m]
        offset = 0.0
        for k, ev in enumerate(result.selected):
            width = ev.project.initial_investment
            ax.barh(i, width, left=offset, height=0.5,
                    color=PALETTE[k % len(PALETTE)], edgecolor="white",
                    linewidth=1.0, zorder=3)
            if width / budget > 0.07:
                ax.text(offset + width / 2, i, ev.project.code, ha="center",
                        va="center", fontsize=8.5, color="white", fontweight="bold",
                        zorder=4)
            offset += width
        # 闲置额度
        if result.idle_budget > 1e-6:
            ax.barh(i, result.idle_budget, left=offset, height=0.5,
                    color="#D5D8DC", edgecolor="white", hatch="//", zorder=3)
            ax.text(offset + result.idle_budget / 2, i,
                    f"闲置 {result.idle_budget:,.0f}",
                    ha="center", va="center", fontsize=7.8, color="#5D6D7E", zorder=4)

    ax.axvline(budget, color=COLOR_POSITIVE, linewidth=2.0, linestyle="-",
               zorder=5, label=f"资本限额 {budget:,.0f} 万元")
    ax.set_yticks(range(len(methods)))
    ax.set_yticklabels(methods, fontsize=10)
    ax.set_xlabel("投资额（万元）")
    ax.set_title("额度占用结构（灰色斜纹为闲置额度）", fontsize=11.5, fontweight="bold")
    ax.legend(loc="lower right", fontsize=9)
    ax.margins(x=0.06)

    # ---------- 右图：组合 NPV 对比 ----------
    ax2 = axes[1]
    npvs = [comparison[m].total_npv for m in methods]
    best_value = max(npvs)
    colors = [COLOR_POSITIVE if v == best_value else COLOR_NEUTRAL for v in npvs]
    bars = ax2.bar(range(len(methods)), npvs, color=colors, width=0.5,
                   edgecolor="white", linewidth=1.0, zorder=3)
    for bar, value, m in zip(bars, npvs, methods):
        ax2.text(bar.get_x() + bar.get_width() / 2, value + max(npvs) * 0.02,
                 f"{value:,.1f}\n使用率 {comparison[m].utilization:.0%}",
                 ha="center", va="bottom", fontsize=9, zorder=4)
    ax2.set_xticks(range(len(methods)))
    ax2.set_xticklabels(methods, fontsize=10)
    ax2.set_ylabel("组合 NPV 合计（万元）")
    ax2.set_title("各方法组合 NPV 对比（红色为最优）", fontsize=11.5, fontweight="bold")
    ax2.margins(y=0.20)

    fig.suptitle(title, fontsize=13.5, fontweight="bold", y=1.0)
    fig.tight_layout()
    return _save(fig, filename)


# ======================================================================
# 7. 互斥组多指标对比
# ======================================================================
def plot_mutual_group(
    result: MutualGroupResult,
    rate: float,
    filename: Optional[str] = None,
) -> Path:
    """绘制互斥项目组的多指标对比图（NPV / 年金净流量 / IRR 三联图）。

    Parameters
    ----------
    result : MutualGroupResult
        互斥组优选结果。
    rate : float
        折现率（用于在 IRR 子图标注资本成本基准线）。
    filename : str or None
        输出文件名。

    Returns
    -------
    pathlib.Path
        图片路径。

    Notes
    -----
    三联图的设计意图在于 **直观暴露方法冲突**：当 NPV 子图选出的方案
    与 ANCF 子图（或 IRR 子图）不同时，柱状图中的红色高亮柱位置会
    发生移动，一眼即可看出冲突所在。
    """
    evals = result.evaluations
    codes = [e.project.code for e in evals]
    x = np.arange(len(codes))

    fig, axes = plt.subplots(1, 3, figsize=(14.0, 5.0))

    # ---------- NPV ----------
    npvs = [e.npv for e in evals]
    best_npv_code = result.best_by_npv.project.code
    axes[0].bar(x, npvs, width=0.5,
                color=[COLOR_POSITIVE if e.project.code == best_npv_code else "#AEB6BF"
                       for e in evals], zorder=3)
    for xi, v in zip(x, npvs):
        axes[0].text(xi, v + max(npvs) * 0.03, f"{v:,.1f}", ha="center",
                     va="bottom", fontsize=9)
    axes[0].set_title(f"NPV 法 → 选 {best_npv_code}", fontsize=11, fontweight="bold")
    axes[0].set_ylabel("净现值（万元）")

    # ---------- ANCF ----------
    ancfs = [e.ancf for e in evals]
    best_ancf_code = result.best_by_ancf.project.code
    axes[1].bar(x, ancfs, width=0.5,
                color=[COLOR_HIGHLIGHT if e.project.code == best_ancf_code else "#AEB6BF"
                       for e in evals], zorder=3)
    for xi, v in zip(x, ancfs):
        axes[1].text(xi, v + max(map(abs, ancfs)) * 0.03, f"{v:,.1f}", ha="center",
                     va="bottom", fontsize=9)
    axes[1].set_title(f"年金净流量法 → 选 {best_ancf_code}", fontsize=11, fontweight="bold")
    axes[1].set_ylabel("年金净流量（万元/年）")

    # ---------- IRR ----------
    irrs = [(e.irr if e.irr is not None else 0.0) for e in evals]
    best_irr_code = result.best_by_irr.project.code
    axes[2].bar(x, [v * 100 for v in irrs], width=0.5,
                color=["#2E5C8A" if e.project.code == best_irr_code else "#AEB6BF"
                       for e in evals], zorder=3)
    for xi, v, e in zip(x, irrs, evals):
        label = f"{v:.2%}" if e.irr is not None else "无实根"
        axes[2].text(xi, v * 100 + 0.6, label, ha="center", va="bottom", fontsize=9)
    axes[2].axhline(rate * 100, color=COLOR_POSITIVE, linewidth=1.6,
                    linestyle="--", zorder=4, label=f"资本成本 {rate:.1%}")
    axes[2].set_title(f"IRR 法 → 选 {best_irr_code}", fontsize=11, fontweight="bold")
    axes[2].set_ylabel("内含报酬率（%）")
    axes[2].legend(fontsize=9)

    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels(codes, fontsize=10)
        ax.margins(y=0.18)

    conflict = []
    if result.conflict_npv_irr:
        conflict.append("NPV 法与 IRR 法结论冲突")
    if result.conflict_npv_ancf:
        conflict.append("NPV 法与年金净流量法结论冲突")
    subtitle = "｜".join(conflict) if conflict else "三种方法结论一致"
    fig.suptitle(f"互斥组「{result.group}」多指标对比（{subtitle}）",
                 fontsize=13, fontweight="bold", y=1.02)
    fig.tight_layout()
    return _save(fig, filename or f"07_mutual_{result.group}.png")
