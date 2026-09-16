# -*- coding: utf-8 -*-
"""
analysis/charts.py —— 图表输出
================================================================
使用 matplotlib 生成报告插图（PNG，150 dpi），统一浅色底、中文字体。

配色约定（遵循 A 股习惯）
------------------------
* 正向 / 增长：红色系
* 负向 / 下降：绿色系
* 中性主色：深蓝
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

import numpy as np

import config as C
from . import loader


# ------------------------------------------------------------------
# 环境初始化
# ------------------------------------------------------------------
def setup_style():
    """选择可用的中文字体并设定统一风格。"""
    available = {f.name for f in font_manager.fontManager.ttflist}
    chosen = next((f for f in C.FONT_CANDIDATES if f in available), None)
    if chosen:
        plt.rcParams["font.sans-serif"] = [chosen] + C.FONT_CANDIDATES
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 150
    plt.rcParams["savefig.dpi"] = 150
    plt.rcParams["figure.facecolor"] = "white"
    plt.rcParams["axes.facecolor"] = "white"
    plt.rcParams["axes.edgecolor"] = "#BFBFBF"
    plt.rcParams["axes.labelcolor"] = "#333333"
    plt.rcParams["text.color"] = "#333333"
    plt.rcParams["xtick.color"] = "#555555"
    plt.rcParams["ytick.color"] = "#555555"
    plt.rcParams["axes.grid"] = True
    plt.rcParams["grid.color"] = "#E5E5E5"
    plt.rcParams["grid.linewidth"] = 0.8
    plt.rcParams["axes.axisbelow"] = True
    plt.rcParams["legend.frameon"] = False
    plt.rcParams["font.size"] = 10
    return chosen


def _save(fig, name):
    path = os.path.join(C.CHART_DIR, name)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  [图表] %s" % name)
    return path


# ------------------------------------------------------------------
# 1. 资产结构（100% 堆叠）
# ------------------------------------------------------------------
def chart_asset_structure(balance, years):
    from . import structure as S
    labels = ["货币资金", "经营性资产", "长期经营资产",
              "其他资产（投资性及其他）"]
    data = {lab: [] for lab in labels}
    for y in years:
        total = loader.get(balance, "资产总计", y)
        cash = loader.get(balance, "货币资金", y)
        op = sum(S._group_sum(balance, S.ASSET_GROUPS["经营性资产"], y)[0:1])
        lg = sum(S._group_sum(balance, S.ASSET_GROUPS["长期经营资产"], y)[0:1])
        data["货币资金"].append(cash / total * 100)
        data["经营性资产"].append(op / total * 100)
        data["长期经营资产"].append(lg / total * 100)
        data["其他资产（投资性及其他）"].append(
            (total - cash - op - lg) / total * 100)

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.6),
                             gridspec_kw={"width_ratios": [1.25, 1]})
    ax = axes[0]
    bottom = np.zeros(len(years))
    colors = [C.COLOR_MAIN, C.COLOR_SUB, C.COLOR_ACCENT, "#B0BEC5"]
    for (lab, vals), color in zip(data.items(), colors):
        vals = np.array(vals)
        ax.bar([str(y) for y in years], vals, bottom=bottom,
               label=lab, color=color, width=0.55)
        for i, v in enumerate(vals):
            if v > 4:
                ax.text(i, bottom[i] + v / 2, "%.1f%%" % v, ha="center",
                        va="center", fontsize=8.5, color="white")
        bottom += vals
    ax.set_title("资产结构演变（占总资产比重）", fontsize=12,
                 color=C.COLOR_MAIN, pad=12)
    ax.set_ylabel("占比 (%)")
    ax.set_ylim(0, 100)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=2,
              fontsize=8.5)

    # 右图：资产总额与同比
    ax2 = axes[1]
    totals = [loader.get(balance, "资产总计", y) / C.UNIT_YI for y in years]
    growth = [np.nan] + [(totals[i] / totals[i - 1] - 1) * 100
                         for i in range(1, len(years))]
    ax2.bar([str(y) for y in years], totals, color=C.COLOR_SUB, width=0.5,
            label="资产总计（亿元）")
    for i, v in enumerate(totals):
        ax2.text(i, v * 1.01, "%.0f" % v, ha="center", fontsize=8.5)
    ax2.set_ylabel("亿元")
    ax2.set_ylim(0, max(totals) * 1.25)
    axb = ax2.twinx()
    axb.plot([str(y) for y in years], growth, marker="o",
             color=C.COLOR_ACCENT, lw=1.8, label="同比增速")
    axb.set_ylabel("同比 (%)", color=C.COLOR_ACCENT)
    axb.grid(False)
    ax2.set_title("资产规模与增速", fontsize=12, color=C.COLOR_MAIN, pad=12)
    h1, l1 = ax2.get_legend_handles_labels()
    h2, l2 = axb.get_legend_handles_labels()
    ax2.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=8.5)
    return _save(fig, "01_asset_structure.png")


# ------------------------------------------------------------------
# 2. 负债与权益结构
# ------------------------------------------------------------------
def chart_liab_equity(balance, years):
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.6))
    ax = axes[0]
    op, ib, ot = [], [], []
    for y in years:
        total = loader.get(balance, "负债合计", y)
        from . import structure as S
        op.append(S._group_sum(balance, S.LIAB_GROUPS["经营性负债"], y)[0]
                  / total * 100)
        ib.append(S._group_sum(balance, S.LIAB_GROUPS["有息负债"], y)[0]
                  / total * 100)
        ot.append(100 - op[-1] - ib[-1])
    xs = [str(y) for y in years]
    ax.bar(xs, op, color=C.COLOR_MAIN, width=0.5, label="经营性负债")
    ax.bar(xs, ib, bottom=op, color=C.COLOR_ACCENT, width=0.5, label="有息负债")
    ax.bar(xs, ot, bottom=np.array(op) + np.array(ib), color="#B0BEC5",
           width=0.5, label="其他负债")
    for i, y in enumerate(years):
        ax.text(i, op[i] / 2, "%.1f%%" % op[i], ha="center", va="center",
                fontsize=8.5, color="white")
        ax.text(i, op[i] + ib[i] / 2, "%.1f%%" % ib[i], ha="center",
                va="center", fontsize=8.5, color="white")
    ax.set_title("负债结构（占负债合计比重）", fontsize=12,
                 color=C.COLOR_MAIN, pad=12)
    ax.set_ylabel("占比 (%)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=3,
              fontsize=8.5)

    ax2 = axes[1]
    em, dr = [], []
    for y in years:
        ta = loader.get(balance, "资产总计", y)
        tl = loader.get(balance, "负债合计", y)
        te = loader.get(balance, "股东权益合计", y)
        em.append(ta / te)
        dr.append(tl / ta * 100)
    ax2.plot(xs, em, marker="s", color=C.COLOR_MAIN, lw=1.8, label="权益乘数(倍)")
    for i, v in enumerate(em):
        ax2.text(i, v + 0.02, "%.3f" % v, ha="center", fontsize=8.5,
                 color=C.COLOR_MAIN)
    ax2.set_ylabel("权益乘数（倍）", color=C.COLOR_MAIN)
    ax2.set_ylim(min(em) * 0.9, max(em) * 1.08)
    axb = ax2.twinx()
    axb.plot(xs, dr, marker="o", color=C.COLOR_ACCENT, lw=1.8,
             label="资产负债率(%)")
    axb.set_ylabel("资产负债率 (%)", color=C.COLOR_ACCENT)
    axb.grid(False)
    ax2.set_title("财务杠杆水平", fontsize=12, color=C.COLOR_MAIN, pad=12)
    h1, l1 = ax2.get_legend_handles_labels()
    h2, l2 = axb.get_legend_handles_labels()
    ax2.legend(h1 + h2, l1 + l2, loc="lower right", fontsize=8.5)
    return _save(fig, "02_liability_equity_structure.png")


# ------------------------------------------------------------------
# 3. 利润表结构演变
# ------------------------------------------------------------------
def chart_income_structure(income, years):
    items = ["营业成本", "税金及附加", "销售费用", "管理费用", "研发费用",
             "财务费用", "营业利润", "所得税费用", "净利润"]
    fig, ax = plt.subplots(figsize=(12.5, 4.8))
    x = np.arange(len(years))
    width = 0.14
    for i, item in enumerate(items):
        vals = []
        for y in years:
            base = loader.get(income, "营业总收入", y)
            vals.append(loader.get(income, item, y) / base * 100)
        color = C.PALETTE[i % len(C.PALETTE)]
        ax.bar(x + (i - (len(items) - 1) / 2) * width, vals, width,
               label=item, color=color)
    ax.set_xticks(x)
    ax.set_xticklabels([str(y) for y in years])
    ax.set_ylabel("占营业总收入比重 (%)")
    ax.set_title("利润表项目结构（占营业总收入比重）", fontsize=12,
                 color=C.COLOR_MAIN, pad=12)
    ax.legend(ncol=5, fontsize=8.5, loc="upper center",
              bbox_to_anchor=(0.5, -0.08))
    return _save(fig, "03_income_structure.png")


# ------------------------------------------------------------------
# 4. 收入与利润趋势
# ------------------------------------------------------------------
def chart_revenue_profit(income, years):
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.6))
    xs = [str(y) for y in years]
    ax = axes[0]
    rev = [loader.get(income, "营业总收入", y) / C.UNIT_YI for y in years]
    npf = [loader.get(income, "归属于母公司股东的净利润", y) / C.UNIT_YI
           for y in years]
    ax.bar([x for x in range(len(years))], rev, width=0.38, color=C.COLOR_MAIN,
           label="营业总收入")
    ax.bar([x + 0.38 for x in range(len(years))], npf, width=0.38,
           color=C.COLOR_ACCENT, label="归母净利润")
    for i, v in enumerate(rev):
        ax.text(i, v * 1.015, "%.0f" % v, ha="center", fontsize=8)
    for i, v in enumerate(npf):
        ax.text(i + 0.38, v * 1.015, "%.0f" % v, ha="center", fontsize=8)
    ax.set_xticks([i + 0.19 for i in range(len(years))])
    ax.set_xticklabels(xs)
    ax.set_ylabel("亿元")
    ax.set_ylim(0, max(rev) * 1.18)
    ax.set_title("营业总收入与归母净利润", fontsize=12, color=C.COLOR_MAIN,
                 pad=12)
    ax.legend(fontsize=9)

    ax2 = axes[1]
    rev_g = [np.nan] + [(rev[i] / rev[i - 1] - 1) * 100
                        for i in range(1, len(years))]
    npf_g = [np.nan] + [(npf[i] / npf[i - 1] - 1) * 100
                        for i in range(1, len(years))]
    ax2.plot(xs, rev_g, marker="o", lw=2, color=C.COLOR_MAIN,
             label="营业总收入同比")
    ax2.plot(xs, npf_g, marker="s", lw=2, color=C.COLOR_ACCENT,
             label="归母净利润同比")
    for i, (a, b) in enumerate(zip(rev_g, npf_g)):
        if not np.isnan(a):
            ax2.text(i, a + 0.7, "%.1f%%" % a, ha="center", fontsize=8,
                     color=C.COLOR_MAIN)
        if not np.isnan(b):
            ax2.text(i, b - 1.6, "%.1f%%" % b, ha="center", fontsize=8,
                     color=C.COLOR_ACCENT)
    ax2.axhline(0, color="#999999", lw=0.9, ls="--")
    ax2.set_ylabel("同比增速 (%)")
    ax2.set_title("收入与利润增速对比", fontsize=12, color=C.COLOR_MAIN,
                  pad=12)
    ax2.legend(fontsize=9)
    return _save(fig, "04_revenue_profit_trend.png")


# ------------------------------------------------------------------
# 5. 定基指数趋势
# ------------------------------------------------------------------
def chart_index_trend(balance, income, cashflow, years):
    series = [
        ("营业总收入", income), ("归母净利润", income),
        ("资产总计", balance), ("归母股东权益", balance),
        ("经营活动现金流净额", cashflow),
    ]
    fig, ax = plt.subplots(figsize=(11.5, 5.0))
    for (label, df), color in zip(series, C.PALETTE):
        item = "归属于母公司股东的净利润" if label == "归母净利润" else label
        item = "归属于母公司股东权益合计" if label == "归母股东权益" else item
        item = "经营活动产生的现金流量净额" if label == "经营活动现金流净额" else item
        base = loader.get(df, item, years[0])
        idx = [loader.get(df, item, y) / base * 100 for y in years]
        ax.plot([str(y) for y in years], idx, marker="o", lw=2, label=label,
                color=color)
        ax.text(len(years) - 1.05, idx[-1], " %.0f" % idx[-1], fontsize=8.5,
                color=color, va="center")
    ax.axhline(100, color="#999999", lw=1, ls="--")
    ax.set_ylabel("%d年 = 100" % years[0])
    ax.set_title("主要项目定基指数趋势（%d年=100）" % years[0], fontsize=12,
                 color=C.COLOR_MAIN, pad=12)
    ax.legend(fontsize=9, loc="upper left")
    return _save(fig, "05_index_trend.png")


# ------------------------------------------------------------------
# 6. 现金流量三项净额
# ------------------------------------------------------------------
def chart_cashflow(cashflow, years):
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.6))
    xs = [str(y) for y in years]
    ax = axes[0]
    x = np.arange(len(years))
    op = [loader.get(cashflow, "经营活动产生的现金流量净额", y) / C.UNIT_YI
          for y in years]
    iv = [loader.get(cashflow, "投资活动产生的现金流量净额", y) / C.UNIT_YI
          for y in years]
    fn = [loader.get(cashflow, "筹资活动产生的现金流量净额", y) / C.UNIT_YI
          for y in years]
    ax.bar(x - 0.26, op, 0.26, color=C.COLOR_UP, label="经营活动")
    ax.bar(x, iv, 0.26, color=C.COLOR_SUB, label="投资活动")
    ax.bar(x + 0.26, fn, 0.26, color=C.COLOR_DOWN, label="筹资活动")
    ax.axhline(0, color="#666666", lw=0.9)
    ax.set_xticks(x)
    ax.set_xticklabels(xs)
    ax.set_ylabel("亿元")
    ax.set_title("三类活动现金流量净额", fontsize=12, color=C.COLOR_MAIN,
                 pad=12)
    ax.legend(fontsize=9)

    ax2 = axes[1]
    cfo = [loader.get(cashflow, "经营活动产生的现金流量净额", y) / C.UNIT_YI
           for y in years]
    capex = [loader.get(cashflow,
                        "购建固定资产、无形资产和其他长期资产支付的现金", y)
             / C.UNIT_YI for y in years]
    fcf = [a - b for a, b in zip(cfo, capex)]
    ax2.bar(x - 0.19, cfo, 0.38, color=C.COLOR_MAIN, label="经营活动现金流净额")
    ax2.bar(x + 0.19, fcf, 0.38, color=C.COLOR_ACCENT, label="自由现金流")
    for i, v in enumerate(fcf):
        ax2.text(i + 0.19, v + (14 if v >= 0 else -30), "%.0f" % v,
                 ha="center", fontsize=8)
    ax2.axhline(0, color="#666666", lw=0.9)
    ax2.set_xticks(x)
    ax2.set_xticklabels(xs)
    ax2.set_ylabel("亿元")
    ax2.set_title("经营现金流与自由现金流", fontsize=12, color=C.COLOR_MAIN,
                  pad=12)
    ax2.legend(fontsize=9)
    return _save(fig, "06_cashflow_structure.png")


# ------------------------------------------------------------------
# 7. 偿债能力
# ------------------------------------------------------------------
def chart_solvency(ind_df, years):
    sub = ind_df[ind_df["类别"] == "偿债能力"].set_index("指标")
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.6))
    xs = [str(y) for y in years]
    ax = axes[0]
    for name, color, marker in (("流动比率", C.COLOR_MAIN, "o"),
                                ("速动比率", C.COLOR_SUB, "s"),
                                ("现金比率", C.COLOR_ACCENT, "^")):
        vals = [sub.at[name, y] for y in years]
        ax.plot(xs, vals, marker=marker, lw=2, color=color, label=name)
        for i, v in enumerate(vals):
            ax.text(i, v + 0.015, "%.2f" % v, ha="center", fontsize=8,
                    color=color)
    ax.set_ylabel("倍")
    ax.set_title("短期偿债能力", fontsize=12, color=C.COLOR_MAIN, pad=12)
    ax.legend(fontsize=9)

    ax2 = axes[1]
    dr = [sub.at["资产负债率", y] * 100 for y in years]
    pr = [sub.at["产权比率", y] for y in years]
    ax2.bar(xs, dr, color=C.COLOR_SUB, width=0.45, label="资产负债率(%)")
    for i, v in enumerate(dr):
        ax2.text(i, v + 1.2, "%.2f%%" % v, ha="center", fontsize=8.5)
    ax2.set_ylim(0, max(dr) * 1.22)
    ax2.set_ylabel("%")
    axb = ax2.twinx()
    axb.plot(xs, pr, marker="o", lw=1.8, color=C.COLOR_ACCENT, label="产权比率(倍)")
    axb.set_ylabel("倍", color=C.COLOR_ACCENT)
    axb.grid(False)
    ax2.set_title("长期偿债能力与资本结构", fontsize=12, color=C.COLOR_MAIN,
                 pad=12)
    h1, l1 = ax2.get_legend_handles_labels()
    h2, l2 = axb.get_legend_handles_labels()
    ax2.legend(h1 + h2, l1 + l2, fontsize=9, loc="lower right")
    return _save(fig, "07_solvency.png")


# ------------------------------------------------------------------
# 8. 营运能力
# ------------------------------------------------------------------
def chart_operating(ind_df, years):
    sub = ind_df[ind_df["类别"] == "营运能力"].set_index("指标")
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.6))
    xs = [str(y) for y in years]
    ax = axes[0]
    for name, color, marker in (("应收账款周转天数", C.COLOR_MAIN, "o"),
                                ("存货周转天数", C.COLOR_SUB, "s"),
                                ("应付账款周转天数", C.COLOR_ACCENT, "^"),
                                ("现金转换周期", C.COLOR_UP, "D")):
        vals = [sub.at[name, y] for y in years]
        ax.plot(xs, vals, marker=marker, lw=2, color=color, label=name)
    ax.set_ylabel("天")
    ax.set_title("周转天数与现金转换周期", fontsize=12, color=C.COLOR_MAIN,
                 pad=12)
    ax.legend(fontsize=8.5)

    ax2 = axes[1]
    for name, color, marker in (("总资产周转率", C.COLOR_MAIN, "o"),
                                ("流动资产周转率", C.COLOR_SUB, "s"),
                                ("存货周转率", C.COLOR_ACCENT, "^")):
        vals = [sub.at[name, y] for y in years]
        ax2.plot(xs, vals, marker=marker, lw=2, color=color, label=name)
        for i, v in enumerate(vals):
            ax2.text(i, v + 0.06, "%.2f" % v, ha="center", fontsize=8,
                     color=color)
    ax2.set_ylabel("次")
    ax2.set_title("资产周转效率", fontsize=12, color=C.COLOR_MAIN, pad=12)
    ax2.legend(fontsize=8.5)
    return _save(fig, "08_operating_efficiency.png")


# ------------------------------------------------------------------
# 9. 盈利能力
# ------------------------------------------------------------------
def chart_profitability(ind_df, years):
    sub = ind_df[ind_df["类别"] == "盈利能力"].set_index("指标")
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.6))
    xs = [str(y) for y in years]
    ax = axes[0]
    for name, color, marker in (("销售毛利率", C.COLOR_MAIN, "o"),
                                ("营业利润率", C.COLOR_SUB, "s"),
                                ("销售净利率", C.COLOR_ACCENT, "^")):
        vals = [sub.at[name, y] * 100 for y in years]
        ax.plot(xs, vals, marker=marker, lw=2, color=color, label=name)
        for i, v in enumerate(vals):
            ax.text(i, v + 0.35, "%.2f%%" % v, ha="center", fontsize=8,
                    color=color)
    ax.set_ylabel("%")
    ax.set_title("销售利润率", fontsize=12, color=C.COLOR_MAIN, pad=12)
    ax.legend(fontsize=9)

    ax2 = axes[1]
    roe = [sub.at["净资产收益率(ROE)", y] * 100 for y in years]
    roep = [sub.at["归母净资产收益率", y] * 100 for y in years]
    roa = [sub.at["总资产净利率(ROA)", y] * 100 for y in years]
    x = np.arange(len(years))
    ax2.bar(x - 0.19, roe, 0.38, color=C.COLOR_MAIN, label="ROE（全部权益）")
    ax2.bar(x + 0.19, roa, 0.38, color=C.COLOR_ACCENT, label="ROA")
    ax2.plot(x, roep, marker="D", lw=2, color=C.COLOR_UP, label="归母ROE")
    for i, v in enumerate(roe):
        ax2.text(i - 0.19, v + 0.4, "%.1f" % v, ha="center", fontsize=8)
    ax2.set_xticks(x)
    ax2.set_xticklabels(xs)
    ax2.set_ylabel("%")
    ax2.set_ylim(0, max(roe) * 1.25)
    ax2.set_title("资本回报水平", fontsize=12, color=C.COLOR_MAIN, pad=12)
    ax2.legend(fontsize=9)
    return _save(fig, "09_profitability.png")


# ------------------------------------------------------------------
# 10. 杜邦三因素
# ------------------------------------------------------------------
def chart_dupont(dtable, years):
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.6))
    xs = [str(y) for y in years]
    x = np.arange(len(years))
    ax = axes[0]
    nm = [dtable.at["三因素_销售净利率", y] * 100 for y in years]
    to = [dtable.at["三因素_总资产周转率", y] for y in years]
    em = [dtable.at["三因素_权益乘数", y] for y in years]
    ax.bar(x - 0.26, nm, 0.26, color=C.COLOR_MAIN, label="销售净利率(%)")
    ax.bar(x, to, 0.26, color=C.COLOR_SUB, label="总资产周转率(次)")
    ax.bar(x + 0.26, em, 0.26, color=C.COLOR_ACCENT, label="权益乘数(倍)")
    for i in range(len(years)):
        ax.text(i - 0.26, nm[i] + 0.2, "%.2f" % nm[i], ha="center", fontsize=7.5)
        ax.text(i, to[i] + 0.02, "%.3f" % to[i], ha="center", fontsize=7.5)
        ax.text(i + 0.26, em[i] + 0.02, "%.3f" % em[i], ha="center",
                fontsize=7.5)
    ax.set_xticks(x)
    ax.set_xticklabels(xs)
    ax.set_title("杜邦三因素演变", fontsize=12, color=C.COLOR_MAIN, pad=12)
    ax.legend(fontsize=8.5)
    ax.set_ylim(0, max(max(nm), max(em)) * 1.25)

    ax2 = axes[1]
    roe = [dtable.at["ROE", y] * 100 for y in years]
    roep = [dtable.at["ROE(归母)", y] * 100 for y in years]
    ax2.plot(xs, roe, marker="o", lw=2.2, color=C.COLOR_MAIN, label="ROE")
    ax2.plot(xs, roep, marker="s", lw=2.2, color=C.COLOR_ACCENT,
             label="归母ROE")
    for i, v in enumerate(roe):
        ax2.text(i, v + 0.35, "%.2f%%" % v, ha="center", fontsize=8.5,
                 color=C.COLOR_MAIN)
    ax2.set_ylabel("%")
    ax2.set_title("净资产收益率", fontsize=12, color=C.COLOR_MAIN, pad=12)
    ax2.legend(fontsize=9)
    return _save(fig, "10_dupont_factors.png")


# ------------------------------------------------------------------
# 11. 杜邦归因瀑布图
# ------------------------------------------------------------------
def chart_dupont_waterfall(tri_attr, meta):
    y0 = meta["三因素_ROE基期(%)"]
    y1 = meta["三因素_ROE报告期(%)"]
    labels = ["%d ROE" % meta["基期年份"]] + \
             [str(i) for i in tri_attr.index] + \
             ["%d ROE" % meta["报告期年份"]]
    contrib = list(tri_attr["影响(pp)"])
    fig, ax = plt.subplots(figsize=(10.5, 4.8))
    colors = [C.COLOR_MAIN] + [C.COLOR_UP if c >= 0 else C.COLOR_DOWN
                               for c in contrib] + [C.COLOR_ACCENT]
    running = y0
    positions = []
    for i, c in enumerate(contrib):
        bottom = running
        ax.bar(i + 1, c, bottom=bottom, color=colors[i + 1], width=0.55)
        ax.plot([i + 0.72, i + 1.28], [running + c, running + c],
                color="#999999", lw=0.9, ls=":")
        ax.text(i + 1, bottom + c + (0.12 if c >= 0 else -0.3),
                "%+.2fpp" % c, ha="center", fontsize=9,
                color=C.COLOR_UP if c >= 0 else C.COLOR_DOWN)
        running += c
    ax.bar(0, y0, color=C.COLOR_MAIN, width=0.55)
    ax.bar(len(contrib) + 1, y1, color=C.COLOR_ACCENT, width=0.55)
    ax.text(0, y0 + 0.12, "%.2f%%" % y0, ha="center", fontsize=9.5)
    ax.text(len(contrib) + 1, y1 + 0.12, "%.2f%%" % y1, ha="center",
            fontsize=9.5)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(["基期 ROE\n(%d)" % meta["基期年份"]] +
                       [l.replace("三因素_", "") for l in
                        [str(i) for i in tri_attr.index]] +
                       ["报告期 ROE\n(%d)" % meta["报告期年份"]],
                       fontsize=9)
    ax.set_ylabel("ROE (%)")
    ax.set_title("杜邦三因素连环替代法归因（%d → %d）"
                 % (meta["基期年份"], meta["报告期年份"]),
                 fontsize=12, color=C.COLOR_MAIN, pad=12)
    ax.set_ylim(min(y0, y1) * 0.92, max(y0, y1) * 1.10)
    return _save(fig, "11_dupont_waterfall.png")


# ------------------------------------------------------------------
# 12. 股东回报
# ------------------------------------------------------------------
def chart_shareholder(balance, income, cashflow, years):
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.6))
    xs = [str(y) for y in years]
    ax = axes[0]
    eps = [loader.get(income, "基本每股收益", y) for y in years]
    bps = [loader.get(balance, "归属于母公司股东权益合计", y)
           / loader.get(balance, "实收资本(股本)", y) for y in years]
    ax.bar([str(y) for y in years], bps, color=C.COLOR_SUB, width=0.45,
           label="每股净资产(元)")
    ax2 = ax.twinx()
    ax2.plot(xs, eps, marker="o", lw=2, color=C.COLOR_ACCENT,
             label="基本每股收益(元)")
    ax2.grid(False)
    ax.set_ylabel("每股净资产（元）")
    ax2.set_ylabel("每股收益（元）", color=C.COLOR_ACCENT)
    for i, v in enumerate(bps):
        ax.text(i, v + 0.3, "%.2f" % v, ha="center", fontsize=8.5)
    for i, v in enumerate(eps):
        ax2.text(i, v + 0.08, "%.2f" % v, ha="center", fontsize=8.5,
                 color=C.COLOR_ACCENT)
    ax.set_ylim(0, max(bps) * 1.2)
    ax2.set_ylim(0, max(eps) * 1.3)
    ax.set_title("每股净资产与每股收益", fontsize=12, color=C.COLOR_MAIN,
                 pad=12)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, fontsize=9, loc="upper left")

    axb = axes[1]
    div = [loader.get(cashflow, "分配股利、利润或偿付利息支付的现金", y)
           / C.UNIT_YI for y in years]
    npf = [loader.get(income, "归属于母公司股东的净利润", y) / C.UNIT_YI
           for y in years]
    payout = [d / n * 100 for d, n in zip(div, npf)]
    axb.bar(xs, npf, color=C.COLOR_SUB, width=0.45, label="归母净利润(亿元)")
    axc = axb.twinx()
    axc.plot(xs, payout, marker="s", lw=2, color=C.COLOR_UP,
             label="分红及付息占归母净利比(%)")
    axc.grid(False)
    axb.set_ylabel("亿元")
    axc.set_ylabel("%", color=C.COLOR_UP)
    for i, v in enumerate(payout):
        axc.text(i, v + 1.5, "%.1f%%" % v, ha="center", fontsize=8.5,
                 color=C.COLOR_UP)
    axb.set_title("股东回报水平", fontsize=12, color=C.COLOR_MAIN, pad=12)
    h1, l1 = axb.get_legend_handles_labels()
    h2, l2 = axc.get_legend_handles_labels()
    axb.legend(h1 + h2, l1 + l2, fontsize=9, loc="upper left")
    return _save(fig, "12_shareholder_return.png")
