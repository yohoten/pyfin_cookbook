# -*- coding: utf-8 -*-
"""
analysis/structure.py —— 项目结构分析（共同比分析 / 垂直分析）
================================================================
把各科目金额换算为"占总体基数的百分比"，观察报表的内部构成，
并比较 2023 → 2025 年结构的变化（百分点，pp）。

基数选择
--------
* 资产负债表：资产类科目 / 资产总计；负债类科目 / 负债合计；
  所有者权益类科目 / 股东权益合计。
* 利润表：各项目 / 营业总收入（唯一基数的"目标利润表"）。
* 现金流量表：流入类项目 / 现金流入总量；流出类项目 / 现金流出总量。
"""

import numpy as np
import pandas as pd

import config as C
from . import loader


# ------------------------------------------------------------------
# 结构性汇总口径（口径固定，便于跨年可比）
# ------------------------------------------------------------------
ASSET_GROUPS = {
    "经营性资产":
        ["应收票据", "应收账款", "应收款项融资", "预付款项", "其他应收款",
         "存货", "合同资产"],
    "长期经营资产":
        ["固定资产", "在建工程", "使用权资产", "无形资产", "商誉",
         "长期待摊费用"],
}
LIAB_GROUPS = {
    "经营性负债":
        ["应付票据", "应付账款", "合同负债", "应付职工薪酬", "应交税费",
         "其他应付款", "其他流动负债"],
    "有息负债":
        ["短期借款", "一年内到期的非流动负债", "长期借款", "应付债券",
         "租赁负债"],
}


def _group_sum(balance, items, year):
    total, missing = 0.0, []
    for item in items:
        v = loader.get(balance, item, year)
        if np.isnan(v):
            missing.append(item)
        else:
            total += v
    return total, missing


# ------------------------------------------------------------------
# 资产负债表结构
# ------------------------------------------------------------------
def balance_structure(balance: pd.DataFrame, years) -> pd.DataFrame:
    base_all = {y: loader.get(balance, "资产总计", y) for y in years}
    base_liab = {y: loader.get(balance, "负债合计", y) for y in years}
    base_eq = {y: loader.get(balance, "股东权益合计", y) for y in years}

    liab_start = C.STATEMENT_ITEMS["balance"].index("短期借款")
    eq_start = C.STATEMENT_ITEMS["balance"].index("实收资本(股本)")

    records = []
    for idx, item in enumerate(C.STATEMENT_ITEMS["balance"]):
        if idx >= eq_start:
            base = base_eq
            section = "所有者权益"
        elif idx >= liab_start:
            base = base_liab
            section = "负债"
        else:
            base = base_all
            section = "资产"

        row = {"项目": item, "类别": section}
        for year in years:
            value = loader.get(balance, item, year)
            row["%d(亿元)" % year] = round(value / C.UNIT_YI, 2)
            row["%d占比" % year] = (value / base[year]
                                    if base[year] else np.nan)
        for i in range(1, len(years)):
            row["%d→%d变动(pp)" % (years[i - 1], years[i])] = (
                (row["%d占比" % years[i]] - row["%d占比" % years[i - 1]]) * 100
                if not np.isnan(row["%d占比" % years[i]])
                and not np.isnan(row["%d占比" % years[i - 1]]) else np.nan)
        records.append(row)
    return pd.DataFrame(records)


def balance_group_summary(balance: pd.DataFrame, years) -> pd.DataFrame:
    """资产 / 负债 / 权益三大类内部的结构化聚合。"""
    records = []
    for name, items in ASSET_GROUPS.items():
        rec = {"类别": "资产", "项目": name}
        for year in years:
            total, _ = _group_sum(balance, items, year)
            base = loader.get(balance, "资产总计", year)
            rec["%d(亿元)" % year] = round(total / C.UNIT_YI, 2)
            rec["%d占比" % year] = total / base if base else np.nan
        records.append(rec)

    for name, items in LIAB_GROUPS.items():
        rec = {"类别": "负债", "项目": name}
        for year in years:
            total, _ = _group_sum(balance, items, year)
            base = loader.get(balance, "负债合计", year)
            rec["%d(亿元)" % year] = round(total / C.UNIT_YI, 2)
            rec["%d占比" % year] = total / base if base else np.nan
        records.append(rec)

    # 互斥余项：确保各组之和 + 余项 = 总计，便于交叉验证
    rec = {"类别": "资产", "项目": "货币资金"}
    for year in years:
        v = loader.get(balance, "货币资金", year)
        base = loader.get(balance, "资产总计", year)
        rec["%d(亿元)" % year] = round(v / C.UNIT_YI, 2)
        rec["%d占比" % year] = v / base if base else np.nan
    records.append(rec)

    rec = {"类别": "资产", "项目": "其他资产（投资性资产及其他）"}
    for year in years:
        base = loader.get(balance, "资产总计", year)
        known = loader.get(balance, "货币资金", year)
        for items in ASSET_GROUPS.values():
            known += _group_sum(balance, items, year)[0]
        rec["%d(亿元)" % year] = round((base - known) / C.UNIT_YI, 2)
        rec["%d占比" % year] = (base - known) / base if base else np.nan
    records.append(rec)

    rec = {"类别": "负债", "项目": "其他负债（递延及其他）"}
    for year in years:
        base = loader.get(balance, "负债合计", year)
        known = 0.0
        for items in LIAB_GROUPS.values():
            known += _group_sum(balance, items, year)[0]
        rec["%d(亿元)" % year] = round((base - known) / C.UNIT_YI, 2)
        rec["%d占比" % year] = (base - known) / base if base else np.nan
    records.append(rec)

    rec = {"类别": "权益", "项目": "归属于母公司股东权益"}
    for year in years:
        v = loader.get(balance, "归属于母公司股东权益合计", year)
        base = loader.get(balance, "股东权益合计", year)
        rec["%d(亿元)" % year] = round(v / C.UNIT_YI, 2)
        rec["%d占比" % year] = v / base if base else np.nan
    records.append(rec)

    rec = {"类别": "权益", "项目": "少数股东权益"}
    for year in years:
        v = loader.get(balance, "少数股东权益", year)
        base = loader.get(balance, "股东权益合计", year)
        rec["%d(亿元)" % year] = round(v / C.UNIT_YI, 2)
        rec["%d占比" % year] = v / base if base else np.nan
    records.append(rec)

    df = pd.DataFrame(records)
    for i in range(1, len(years)):
        df["%d→%d变动(pp)" % (years[i - 1], years[i])] = (
            (df["%d占比" % years[i]] - df["%d占比" % years[i - 1]]) * 100)
    return df


# ------------------------------------------------------------------
# 利润表结构
# ------------------------------------------------------------------
def income_structure(income: pd.DataFrame, years) -> pd.DataFrame:
    base = {y: loader.get(income, "营业总收入", y) for y in years}
    records = []
    for item in C.STATEMENT_ITEMS["income"]:
        row = {"项目": item}
        for year in years:
            value = loader.get(income, item, year)
            row["%d(亿元)" % year] = round(value / C.UNIT_YI, 2)
            row["%d占比" % year] = value / base[year] if base[year] else np.nan
        for i in range(1, len(years)):
            row["%d→%d变动(pp)" % (years[i - 1], years[i])] = (
                (row["%d占比" % years[i]] - row["%d占比" % years[i - 1]]) * 100
                if not np.isnan(row["%d占比" % years[i]])
                and not np.isnan(row["%d占比" % years[i - 1]]) else np.nan)
        records.append(row)
    return pd.DataFrame(records)


# ------------------------------------------------------------------
# 现金流量表结构
# ------------------------------------------------------------------
INFLOW_ITEMS = ["销售商品、提供劳务收到的现金", "收到的税费返还",
                "收回投资收到的现金", "取得投资收益收到的现金",
                "吸收投资收到的现金", "取得借款收到的现金"]
OUTFLOW_ITEMS = ["购买商品、接受劳务支付的现金",
                 "支付给职工以及为职工支付的现金", "支付的各项税费",
                 "购建固定资产、无形资产和其他长期资产支付的现金",
                 "投资所支付的现金", "偿还债务支付的现金",
                 "分配股利、利润或偿付利息支付的现金"]
NET_ITEMS = ["经营活动产生的现金流量净额", "投资活动产生的现金流量净额",
             "筹资活动产生的现金流量净额", "现金及现金等价物净增加额"]


def cashflow_structure(cashflow: pd.DataFrame, years) -> pd.DataFrame:
    total_in = {y: (loader.get(cashflow, "经营活动现金流入小计", y)
                    + loader.get(cashflow, "投资活动现金流入小计", y)
                    + loader.get(cashflow, "筹资活动现金流入小计", y))
                for y in years}
    total_out = {y: (loader.get(cashflow, "经营活动现金流出小计", y)
                     + loader.get(cashflow, "投资活动现金流出小计", y)
                     + loader.get(cashflow, "筹资活动现金流出小计", y))
                 for y in years}

    records = []
    for item in INFLOW_ITEMS + ["经营活动现金流入小计", "投资活动现金流入小计",
                                "筹资活动现金流入小计"]:
        row = {"项目": item, "方向": "流入", "基数": "现金流入总量"}
        for year in years:
            v = loader.get(cashflow, item, year)
            row["%d(亿元)" % year] = round(v / C.UNIT_YI, 2)
            row["%d占比" % year] = v / total_in[year] if total_in[year] else np.nan
        records.append(row)

    for item in OUTFLOW_ITEMS + ["经营活动现金流出小计", "投资活动现金流出小计",
                                 "筹资活动现金流出小计"]:
        row = {"项目": item, "方向": "流出", "基数": "现金流出总量"}
        for year in years:
            v = loader.get(cashflow, item, year)
            row["%d(亿元)" % year] = round(v / C.UNIT_YI, 2)
            row["%d占比" % year] = v / total_out[year] if total_out[year] else np.nan
        records.append(row)

    for item in NET_ITEMS:
        row = {"项目": item, "方向": "净额", "基数": "现金流入总量"}
        for year in years:
            v = loader.get(cashflow, item, year)
            row["%d(亿元)" % year] = round(v / C.UNIT_YI, 2)
            row["%d占比" % year] = v / total_in[year] if total_in[year] else np.nan
        records.append(row)

    df = pd.DataFrame(records)
    for i in range(1, len(years)):
        df["%d→%d变动(pp)" % (years[i - 1], years[i])] = (
            (df["%d占比" % years[i]] - df["%d占比" % years[i - 1]]) * 100)
    return df


# ------------------------------------------------------------------
# 结构分析关键结论指标
# ------------------------------------------------------------------
def key_metrics(balance: pd.DataFrame, income: pd.DataFrame,
                cashflow: pd.DataFrame, year: int) -> dict:
    total_asset = loader.get(balance, "资产总计", year)
    total_liab = loader.get(balance, "负债合计", year)
    total_eq = loader.get(balance, "股东权益合计", year)
    cur_asset = loader.get(balance, "流动资产合计", year)
    cur_liab = loader.get(balance, "流动负债合计", year)
    noncur_asset = loader.get(balance, "非流动资产合计", year)
    noncur_liab = loader.get(balance, "非流动负债合计", year)

    operating_asset = _group_sum(balance, ASSET_GROUPS["经营性资产"], year)[0]
    long_asset = _group_sum(balance, ASSET_GROUPS["长期经营资产"], year)[0]
    operating_liab = _group_sum(balance, LIAB_GROUPS["经营性负债"], year)[0]
    interest_liab = _group_sum(balance, LIAB_GROUPS["有息负债"], year)[0]
    goodwill = loader.get(balance, "商誉", year)
    cash = loader.get(balance, "货币资金", year)

    return {
        "年份": year,
        "资产总计(亿元)": total_asset / C.UNIT_YI,
        "流动资产占比": cur_asset / total_asset,
        "非流动资产占比": noncur_asset / total_asset,
        "货币资金占比": cash / total_asset,
        "经营性资产占比": operating_asset / total_asset,
        "长期经营资产占比": long_asset / total_asset,
        "商誉占比": goodwill / total_asset,
        "负债合计(亿元)": total_liab / C.UNIT_YI,
        "流动负债占比(占负债)": cur_liab / total_liab,
        "非流动负债占比(占负债)": noncur_liab / total_liab,
        "经营性负债占比(占负债)": operating_liab / total_liab,
        "有息负债占比(占负债)": interest_liab / total_liab,
        "股东权益占比": total_eq / total_asset,
    }
