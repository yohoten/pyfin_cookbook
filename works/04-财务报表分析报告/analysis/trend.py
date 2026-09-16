# -*- coding: utf-8 -*-
"""
analysis/trend.py —— 项目趋势分析
================================================================
从三个角度刻画各报表项目的时间趋势：

1. **定基指数**：以 2021 年 = 100，反映相对基期的累计变动幅度；
2. **环比增长率**：逐年同比变动率，反映变动节奏；
3. **复合年均增长率（CAGR）**：区间内年均复合增速，消除单年波动。

同时给出"结构弹性"指标：某科目 CAGR 与营业总收入 CAGR 之差，
用于识别哪些项目在加速扩张、哪些在相对收缩。
"""

import numpy as np
import pandas as pd

import config as C
from . import loader


def _cagr(begin, end, periods):
    if begin is None or end is None or periods <= 0:
        return np.nan
    if np.isnan(begin) or np.isnan(end) or begin <= 0 or end <= 0:
        return np.nan
    return (end / begin) ** (1.0 / periods) - 1.0


def trend_table(df: pd.DataFrame, items, years,
                base_year: int = None) -> pd.DataFrame:
    """生成「绝对额 + 定基指数 + 环比增速」三维趋势表。"""
    if base_year is None:
        base_year = years[0]
    records = []
    for item in items:
        if item not in df.index:
            continue
        row = {"项目": item}
        values = {y: loader.get(df, item, y) for y in years}
        base = values.get(base_year)
        for year in years:
            row["%d(亿元)" % year] = round(values[year] / C.UNIT_YI, 2)
            row["%d定基指数" % year] = (values[year] / base * 100
                                     if base and not np.isnan(base)
                                     and not np.isnan(values[year]) else np.nan)
            if year == years[0]:
                row["%d同比" % year] = np.nan
            else:
                prev = values[years[years.index(year) - 1]]
                row["%d同比" % year] = ((values[year] - prev) / abs(prev)
                                     if prev and not np.isnan(prev)
                                     and not np.isnan(values[year]) else np.nan)
        row["CAGR"] = _cagr(values[years[0]], values[years[-1]],
                            len(years) - 1)
        records.append(row)
    return pd.DataFrame(records)


def revenue_linkage(df: pd.DataFrame, years) -> float:
    """以营业总收入为基准的增长中枢（CAGR）。"""
    income_series = df.loc["营业总收入"] if "营业总收入" in df.index else None
    if income_series is None:
        return np.nan
    return _cagr(income_series[years[0]], income_series[years[-1]],
                 len(years) - 1)


def growth_ranking(df: pd.DataFrame, items, years) -> pd.DataFrame:
    """
    按 CAGR 排序，并给出相对营业总收入 CAGR 的"超额增速"。
    """
    table = trend_table(df, items, years)
    if table.empty:
        return table
    ref = None
    if "营业总收入" in items and "营业总收入" in df.index:
        s = df.loc["营业总收入"]
        ref = _cagr(s[years[0]], s[years[-1]], len(years) - 1)
        table.loc[table["项目"] == "营业总收入", "CAGR"] = ref
    table["超额增速(vs营收CAGR)"] = table["CAGR"] - ref if ref is not None else np.nan
    return table.sort_values("CAGR", ascending=False).reset_index(drop=True)


# ------------------------------------------------------------------
# 关键增长指标（供报告与图表使用）
# ------------------------------------------------------------------
def key_growth(income: pd.DataFrame, balance: pd.DataFrame,
               cashflow: pd.DataFrame, years) -> pd.DataFrame:
    metrics = {
        "营业总收入": ("income", "营业总收入"),
        "营业收入": ("income", "营业收入"),
        "营业成本": ("income", "营业成本"),
        "毛利率贡献(收入-成本)": (None, None),
        "销售费用": ("income", "销售费用"),
        "管理费用": ("income", "管理费用"),
        "研发费用": ("income", "研发费用"),
        "营业利润": ("income", "营业利润"),
        "利润总额": ("income", "利润总额"),
        "净利润": ("income", "净利润"),
        "归母净利润": ("income", "归属于母公司股东的净利润"),
        "资产总计": ("balance", "资产总计"),
        "股东权益合计": ("balance", "股东权益合计"),
        "归母股东权益": ("balance", "归属于母公司股东权益合计"),
        "存货": ("balance", "存货"),
        "应收账款": ("balance", "应收账款"),
        "合同负债": ("balance", "合同负债"),
        "经营活动现金流净额": ("cashflow", "经营活动产生的现金流量净额"),
    }
    pools = {"income": income, "balance": balance, "cashflow": cashflow}

    records = []
    for name, (stmt, item) in metrics.items():
        if stmt is None:
            values = {y: (loader.get(income, "营业收入", y)
                          - loader.get(income, "营业成本", y)) for y in years}
        else:
            values = {y: loader.get(pools[stmt], item, y) for y in years}
        row = {"指标": name}
        for year in years:
            row["%d(亿元)" % year] = round(values[year] / C.UNIT_YI, 2)
        for i in range(1, len(years)):
            prev, cur = values[years[i - 1]], values[years[i]]
            row["%d同比" % years[i]] = ((cur - prev) / abs(prev)
                                     if prev and not np.isnan(prev)
                                     and not np.isnan(cur) else np.nan)
        row["CAGR"] = _cagr(values[years[0]], values[years[-1]], len(years) - 1)
        records.append(row)
    return pd.DataFrame(records)
