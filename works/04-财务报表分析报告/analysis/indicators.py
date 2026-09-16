# -*- coding: utf-8 -*-
"""
analysis/indicators.py —— 财务指标分析
================================================================
按偿债能力、营运能力、盈利能力、发展能力、现金质量五个维度计算指标。

口径约定（与教材一致，且各指标之间保持内在一致性）
--------------------------------------------------
* 存量类指标（周转率、ROA、ROE）的分母一律使用 **平均余额**
  =（上年年末余额 + 本年年末余额）/ 2，以保证分子（时期数）与分母
  （时点数）的时间口径匹配。
* 「营业收入」为利润表口径的营业收入（不含其他业务收入的
  "营业总收入"差额部分），用于周转率与利润率的分子。
  因此  销售净利率 × 总资产周转率 = 净利润 / 平均总资产 = ROA
  在数学上严格成立，杜邦分解不产生残差。
* 每股指标的分母使用期末股本（实收资本，面值 1 元），
  每股收益直接取报表披露值。
"""

import numpy as np
import pandas as pd

import config as C
from . import loader


# ------------------------------------------------------------------
def _safe_div(a, b):
    if a is None or b is None:
        return np.nan
    if np.isnan(a) or np.isnan(b) or b == 0:
        return np.nan
    return a / b


def compute(balance: pd.DataFrame, income: pd.DataFrame,
            cashflow: pd.DataFrame, years) -> pd.DataFrame:
    """计算全部财务指标，返回「类别 × 指标 × 年份」长表。"""
    records = []

    def add(category, name, unit, values, formula=""):
        row = {"类别": category, "指标": name, "单位": unit, "计算口径": formula}
        for year in years:
            row[year] = values.get(year, np.nan)
        records.append(row)

    # ---------------- 1. 偿债能力 ----------------
    cur, quick, cash_ratio, debt_ratio = {}, {}, {}, {}
    equity_ratio, em, icr = {}, {}, {}
    for y in years:
        ca = loader.get(balance, "流动资产合计", y)
        cl = loader.get(balance, "流动负债合计", y)
        inv = loader.get(balance, "存货", y)
        cash = loader.get(balance, "货币资金", y)
        tfa = loader.get(balance, "交易性金融资产", y)
        ta = loader.get(balance, "资产总计", y)
        tl = loader.get(balance, "负债合计", y)
        te = loader.get(balance, "股东权益合计", y)
        cur[y] = _safe_div(ca, cl)
        quick[y] = _safe_div(ca - inv, cl)
        cash_ratio[y] = _safe_div(cash + (0 if np.isnan(tfa) else tfa), cl)
        debt_ratio[y] = _safe_div(tl, ta)
        equity_ratio[y] = _safe_div(tl, te)
        em[y] = _safe_div(ta, te)
        interest = loader.get(income, "利息费用", y)
        ebt = loader.get(income, "利润总额", y)
        icr[y] = (_safe_div(ebt + interest, interest)
                  if not np.isnan(interest) and interest > 0 else np.nan)

    add("偿债能力", "流动比率", "倍", cur, "流动资产合计 / 流动负债合计")
    add("偿债能力", "速动比率", "倍", quick,
        "(流动资产合计 - 存货) / 流动负债合计")
    add("偿债能力", "现金比率", "倍", cash_ratio,
        "(货币资金 + 交易性金融资产) / 流动负债合计")
    add("偿债能力", "资产负债率", "%", debt_ratio, "负债合计 / 资产总计")
    add("偿债能力", "产权比率", "倍", equity_ratio, "负债合计 / 股东权益合计")
    add("偿债能力", "权益乘数", "倍", em, "资产总计 / 股东权益合计")
    add("偿债能力", "利息保障倍数", "倍", icr,
        "(利润总额 + 利息费用) / 利息费用")

    # ---------------- 2. 营运能力 ----------------
    ar_to, ar_days, inv_to, inv_days = {}, {}, {}, {}
    ca_to, fa_to, ta_to, ap_to, ap_days, ccc = {}, {}, {}, {}, {}, {}
    for y in years:
        rev = loader.get(income, "营业收入", y)
        cogs = loader.get(income, "营业成本", y)
        ar_to[y] = _safe_div(rev, loader.avg_balance(balance, "应收账款", y))
        ar_days[y] = 365 / ar_to[y] if not np.isnan(ar_to[y]) else np.nan
        inv_to[y] = _safe_div(cogs, loader.avg_balance(balance, "存货", y))
        inv_days[y] = 365 / inv_to[y] if not np.isnan(inv_to[y]) else np.nan
        ca_to[y] = _safe_div(rev, loader.avg_balance(balance, "流动资产合计", y))
        fa_to[y] = _safe_div(rev, loader.avg_balance(balance, "固定资产", y))
        ta_to[y] = _safe_div(rev, loader.avg_balance(balance, "资产总计", y))
        ap_avg = (loader.avg_balance(balance, "应付账款", y)
                  + (0 if np.isnan(loader.avg_balance(balance, "应付票据", y))
                     else loader.avg_balance(balance, "应付票据", y)))
        ap_to[y] = _safe_div(cogs, ap_avg)
        ap_days[y] = 365 / ap_to[y] if not np.isnan(ap_to[y]) else np.nan
        ccc[y] = (inv_days[y] + ar_days[y] - ap_days[y]
                  if not any(np.isnan(v) for v in
                             (inv_days[y], ar_days[y], ap_days[y])) else np.nan)

    add("营运能力", "应收账款周转率", "次", ar_to,
        "营业收入 / 平均应收账款")
    add("营运能力", "应收账款周转天数", "天", ar_days, "365 / 应收账款周转率")
    add("营运能力", "存货周转率", "次", inv_to, "营业成本 / 平均存货")
    add("营运能力", "存货周转天数", "天", inv_days, "365 / 存货周转率")
    add("营运能力", "应付账款周转率", "次", ap_to,
        "营业成本 / 平均(应付账款 + 应付票据)")
    add("营运能力", "应付账款周转天数", "天", ap_days, "365 / 应付账款周转率")
    add("营运能力", "现金转换周期", "天", ccc,
        "存货周转天数 + 应收账款周转天数 - 应付账款周转天数")
    add("营运能力", "流动资产周转率", "次", ca_to,
        "营业收入 / 平均流动资产")
    add("营运能力", "固定资产周转率", "次", fa_to,
        "营业收入 / 平均固定资产")
    add("营运能力", "总资产周转率", "次", ta_to, "营业收入 / 平均总资产")

    # ---------------- 3. 盈利能力 ----------------
    gross, op_margin, net_margin, cost_profit = {}, {}, {}, {}
    roa, roe, roe_parent, eps, bps, dps_ratio = {}, {}, {}, {}, {}, {}
    for y in years:
        rev = loader.get(income, "营业收入", y)
        cogs = loader.get(income, "营业成本", y)
        op = loader.get(income, "营业利润", y)
        npf = loader.get(income, "净利润", y)
        npf_p = loader.get(income, "归属于母公司股东的净利润", y)
        total_cost = loader.get(income, "营业总成本", y)
        gross[y] = _safe_div(rev - cogs, rev)
        op_margin[y] = _safe_div(op, rev)
        net_margin[y] = _safe_div(npf, rev)
        cost_profit[y] = _safe_div(npf, total_cost)
        avg_ta = loader.avg_balance(balance, "资产总计", y)
        avg_eq = loader.avg_balance(balance, "股东权益合计", y)
        avg_pe = loader.avg_balance(balance, "归属于母公司股东权益合计", y)
        roa[y] = _safe_div(npf, avg_ta)
        roe[y] = _safe_div(npf, avg_eq)
        roe_parent[y] = _safe_div(npf_p, avg_pe)
        eps[y] = loader.get(income, "基本每股收益", y)
        bps[y] = _safe_div(
            loader.get(balance, "归属于母公司股东权益合计", y),
            loader.get(balance, "实收资本(股本)", y))
        # 股利支付率（现金分红 / 归母净利润）
        div = loader.get(cashflow, "分配股利、利润或偿付利息支付的现金", y)
        dps_ratio[y] = _safe_div(div, npf_p)

    add("盈利能力", "销售毛利率", "%", gross, "(营业收入 - 营业成本) / 营业收入")
    add("盈利能力", "营业利润率", "%", op_margin, "营业利润 / 营业收入")
    add("盈利能力", "销售净利率", "%", net_margin, "净利润 / 营业收入")
    add("盈利能力", "成本费用利润率", "%", cost_profit,
        "净利润 / 营业总成本")
    add("盈利能力", "总资产净利率(ROA)", "%", roa, "净利润 / 平均总资产")
    add("盈利能力", "净资产收益率(ROE)", "%", roe,
        "净利润 / 平均股东权益合计")
    add("盈利能力", "归母净资产收益率", "%", roe_parent,
        "归母净利润 / 平均归属于母公司股东权益")
    add("盈利能力", "基本每股收益", "元", eps, "报表披露值")
    add("盈利能力", "每股净资产", "元",
        bps, "归母股东权益 / 期末股本")
    add("盈利能力", "现金分红占归母净利比", "%", dps_ratio,
        "分配股利、利润或偿付利息支付的现金 / 归母净利润")

    # ---------------- 4. 发展能力 ----------------
    rev_g, npf_g, npf_p_g, ta_g, eq_g, cfo_g, sgr = {}, {}, {}, {}, {}, {}, {}
    for i, y in enumerate(years):
        if i == 0:
            for d in (rev_g, npf_g, npf_p_g, ta_g, eq_g, cfo_g, sgr):
                d[y] = np.nan
            continue
        p = years[i - 1]
        rev_g[y] = _safe_div(loader.get(income, "营业收入", y)
                             - loader.get(income, "营业收入", p),
                             abs(loader.get(income, "营业收入", p)))
        npf_g[y] = _safe_div(loader.get(income, "净利润", y)
                             - loader.get(income, "净利润", p),
                             abs(loader.get(income, "净利润", p)))
        npf_p_g[y] = _safe_div(loader.get(income, "归属于母公司股东的净利润", y)
                               - loader.get(income, "归属于母公司股东的净利润", p),
                               abs(loader.get(income, "归属于母公司股东的净利润", p)))
        ta_g[y] = _safe_div(loader.get(balance, "资产总计", y)
                            - loader.get(balance, "资产总计", p),
                            abs(loader.get(balance, "资产总计", p)))
        eq_g[y] = _safe_div(loader.get(balance, "股东权益合计", y)
                            - loader.get(balance, "股东权益合计", p),
                            abs(loader.get(balance, "股东权益合计", p)))
        cfo_g[y] = _safe_div(loader.get(cashflow, "经营活动产生的现金流量净额", y)
                             - loader.get(cashflow, "经营活动产生的现金流量净额", p),
                             abs(loader.get(cashflow, "经营活动产生的现金流量净额", p)))
        # 可持续增长率 = ROE × 利润留存率
        payout = dps_ratio.get(y, np.nan)
        retain = 1 - payout if not np.isnan(payout) else np.nan
        sgr[y] = roe_parent.get(y, np.nan) * retain

    add("发展能力", "营业收入增长率", "%", rev_g, "本期营业收入 / 上期 - 1")
    add("发展能力", "净利润增长率", "%", npf_g, "本期净利润 / 上期 - 1")
    add("发展能力", "归母净利润增长率", "%", npf_p_g,
        "本期归母净利润 / 上期 - 1")
    add("发展能力", "总资产增长率", "%", ta_g, "本期资产总计 / 上期 - 1")
    add("发展能力", "股东权益增长率", "%", eq_g, "本期股东权益 / 上期 - 1")
    add("发展能力", "经营现金流增长率", "%", cfo_g,
        "本期经营活动现金流净额 / 上期 - 1")
    add("发展能力", "可持续增长率", "%", sgr,
        "归母ROE ×（1 - 现金分红占归母净利比）")

    # ---------------- 5. 现金质量 ----------------
    cash_sales, ni_cash, cfo_cl, cfo_debt, fcf, fcf_margin = {}, {}, {}, {}, {}, {}
    for y in years:
        rev = loader.get(income, "营业收入", y)
        npf = loader.get(income, "净利润", y)
        cfo = loader.get(cashflow, "经营活动产生的现金流量净额", y)
        capex = loader.get(cashflow,
                           "购建固定资产、无形资产和其他长期资产支付的现金", y)
        cl = loader.get(balance, "流动负债合计", y)
        debt = (loader.get(balance, "短期借款", y)
                + loader.get(balance, "一年内到期的非流动负债", y)
                + loader.get(balance, "长期借款", y)
                + loader.get(balance, "应付债券", y))
        cash_sales[y] = _safe_div(cfo, rev)
        ni_cash[y] = _safe_div(cfo, npf)
        cfo_cl[y] = _safe_div(cfo, cl)
        cfo_debt[y] = _safe_div(cfo, debt)
        fcf[y] = cfo - capex
        fcf_margin[y] = _safe_div(cfo - capex, rev)

    add("现金质量", "销售现金比率", "%", cash_sales,
        "经营活动现金流净额 / 营业收入")
    add("现金质量", "净利润现金含量", "%", ni_cash,
        "经营活动现金流净额 / 净利润")
    add("现金质量", "经营现金流/流动负债", "%", cfo_cl,
        "经营活动现金流净额 / 流动负债合计")
    add("现金质量", "经营现金流/有息负债", "%", cfo_debt,
        "经营活动现金流净额 / 有息负债")
    add("现金质量", "自由现金流(亿元)", "亿元", fcf,
        "经营活动现金流净额 - 购建长期资产支付的现金")
    add("现金质量", "自由现金流/营业收入", "%", fcf_margin,
        "自由现金流 / 营业收入")

    df = pd.DataFrame(records)

    # 单位换算与格式处理
    pct_items = df["单位"] == "%"
    years_cols = [y for y in years if y in df.columns]
    for y in years_cols:
        df[y] = df[y].astype(float)
    for idx in df.index:
        if df.at[idx, "单位"] == "亿元":
            for y in years_cols:
                df.at[idx, y] = df.at[idx, y] / C.UNIT_YI
    return df


def by_category(df: pd.DataFrame) -> dict:
    """拆分为 {类别: 子表}。"""
    return {cat: sub.reset_index(drop=True)
            for cat, sub in df.groupby("类别", sort=False)}


def to_display(df: pd.DataFrame, years) -> pd.DataFrame:
    """生成便于阅读的展示表：% 类指标以百分数呈现。"""
    out = df.copy()
    for y in years:
        col = []
        for _, row in out.iterrows():
            v = row[y]
            if pd.isna(v):
                col.append("—")
            elif row["单位"] == "%":
                col.append("{:,.2f}%".format(v * 100))
            elif row["单位"] == "亿元":
                col.append("{:,.2f}".format(v))
            elif row["单位"] == "倍":
                col.append("{:,.2f}".format(v))
            elif row["单位"] == "天":
                col.append("{:,.2f}".format(v))
            else:
                col.append("{:,.2f}".format(v))
        out["%d" % y] = col
    return out[["类别", "指标", "单位"] + ["%d" % y for y in years] +
               ["计算口径"]]
