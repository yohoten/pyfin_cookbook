# -*- coding: utf-8 -*-
"""
analysis/dupont.py —— 杜邦分析
================================================================
杜邦分析把净资产收益率（ROE）拆解为可归因的驱动因素，
回答"高 / 低 ROE 究竟由什么造成"。

一、三因素模型
    ROE = 销售净利率 × 总资产周转率 × 权益乘数
        = (净利润 / 营业收入) × (营业收入 / 平均总资产)
          × (平均总资产 / 平均股东权益)
    三因素分别代表企业的 **盈利质量**、**资产效率**、**财务杠杆**。

二、五因素模型（进一步拆分盈利质量）
    ROE = 税负率 × 利息负担率 × 息税前利润率 × 总资产周转率 × 权益乘数
    其中 息税前利润 EBIT = 利润总额 + 利息费用。

三、连环替代法（因素分析）
    依次替换各因素并测算 ROE 变动额，量化每个因素对 ROE 变化的贡献，
    使"哪个因素在改善、哪个在拖累"可以定量表述。

一致性保证：所有分解式的乘积与 ROE 定义式严格相等，不产生残差。
"""

import numpy as np
import pandas as pd

import config as C
from . import loader


def _div(a, b):
    if a is None or b is None or np.isnan(a) or np.isnan(b) or b == 0:
        return np.nan
    return a / b


# ------------------------------------------------------------------
# 一、因素取值
# ------------------------------------------------------------------
def factors(balance, income, years) -> pd.DataFrame:
    """计算杜邦模型所需的各因素取值。"""
    records = []
    for y in years:
        npf = loader.get(income, "净利润", y)
        npf_p = loader.get(income, "归属于母公司股东的净利润", y)
        rev = loader.get(income, "营业收入", y)
        ebt = loader.get(income, "利润总额", y)
        interest = loader.get(income, "利息费用", y)
        if np.isnan(interest):
            interest = 0.0
        ebit = ebt + interest

        avg_ta = loader.avg_balance(balance, "资产总计", y)
        avg_eq = loader.avg_balance(balance, "股东权益合计", y)
        avg_pe = loader.avg_balance(balance, "归属于母公司股东权益合计", y)
        end_eq = loader.get(balance, "股东权益合计", y)
        end_pe = loader.get(balance, "归属于母公司股东权益合计", y)

        records.append({
            "年份": y,
            "净利润": npf,
            "归母净利润": npf_p,
            "营业收入": rev,
            "利润总额": ebt,
            "利息费用": interest,
            "息税前利润": ebit,
            "平均总资产": avg_ta,
            "平均股东权益": avg_eq,
            "平均归母权益": avg_pe,
            "期末股东权益": end_eq,
            "期末归母权益": end_pe,
            # 三因素
            "销售净利率": _div(npf, rev),
            "总资产周转率": _div(rev, avg_ta),
            "权益乘数": _div(avg_ta, avg_eq),
            # 五因素
            "税负率": _div(npf, ebt),
            "利息负担率": _div(ebt, ebit),
            "息税前利润率": _div(ebit, rev),
            # 结果
            "ROE": _div(npf, avg_eq),
            "ROE(期末权益口径)": _div(npf, end_eq),
            "ROE(归母)": _div(npf_p, avg_pe),
            "ROE(归母_期末)": _div(npf_p, end_pe),
            "ROA": _div(npf, avg_ta),
        })
    return pd.DataFrame(records).set_index("年份").T


# ------------------------------------------------------------------
# 二、分解结果表
# ------------------------------------------------------------------
def decompose(balance, income, years) -> pd.DataFrame:
    f = factors(balance, income, years)
    records = []
    for y in years:
        net_margin = f.at["销售净利率", y]
        turnover = f.at["总资产周转率", y]
        em = f.at["权益乘数", y]
        tax = f.at["税负率", y]
        interest_burden = f.at["利息负担率", y]
        ebit_margin = f.at["息税前利润率", y]
        records.append({
            "年份": y,
            "ROE": f.at["ROE", y],
            "ROE(归母)": f.at["ROE(归母)", y],
            "三因素_销售净利率": net_margin,
            "三因素_总资产周转率": turnover,
            "三因素_权益乘数": em,
            "三因素_乘积校验": net_margin * turnover * em,
            "五因素_税负率": tax,
            "五因素_利息负担率": interest_burden,
            "五因素_息税前利润率": ebit_margin,
            "五因素_总资产周转率": turnover,
            "五因素_权益乘数": em,
            "五因素_乘积校验": (tax * interest_burden * ebit_margin
                            * turnover * em),
        })
    return pd.DataFrame(records).set_index("年份").T


# ------------------------------------------------------------------
# 三、连环替代法归因
# ------------------------------------------------------------------
def attribution(balance, income, years, base_year=None, target_year=None):
    """
    三因素 & 五因素连环替代法：量化各因素变动对 ROE 变化的贡献。

    返回 DataFrame：index = 因素名, columns = 贡献（百分点）
    """
    if base_year is None:
        base_year = years[-2]
    if target_year is None:
        target_year = years[-1]

    f = factors(balance, income, years)

    def run(names):
        old = [f.at[n, base_year] for n in names]
        new = [f.at[n, target_year] for n in names]
        base_val = float(np.prod(old))
        records = []
        cur = list(old)
        prev_val = base_val
        for i, name in enumerate(names):
            cur[i] = new[i]
            val = float(np.prod(cur))
            records.append({"因素": name,
                            "基期值": old[i], "报告期值": new[i],
                            "影响(pp)": (val - prev_val) * 100})
            prev_val = val
        total = (prev_val - base_val) * 100
        return pd.DataFrame(records), base_val * 100, prev_val * 100, total

    tri_names = ["销售净利率", "总资产周转率", "权益乘数"]
    tri, tri_base, tri_new, tri_total = run(tri_names)

    five_names = ["税负率", "利息负担率", "息税前利润率",
                  "总资产周转率", "权益乘数"]
    five, five_base, five_new, five_total = run(five_names)

    tri = tri.set_index("因素")
    five = five.set_index("因素")
    meta = {
        "基期年份": base_year,
        "报告期年份": target_year,
        "三因素_ROE基期(%)": tri_base,
        "三因素_ROE报告期(%)": tri_new,
        "三因素_ROE变动(pp)": tri_total,
        "五因素_ROE基期(%)": five_base,
        "五因素_ROE报告期(%)": five_new,
        "五因素_ROE变动(pp)": five_total,
    }
    return {"三因素": tri, "五因素": five, "meta": meta, "factors": f}


# ------------------------------------------------------------------
# 四、杜邦体系树（供图表与报告使用）
# ------------------------------------------------------------------
def tree(balance, income, years, year) -> dict:
    """生成杜邦分解树的数据结构，用于绘制体系图。"""
    f = factors(balance, income, years)
    return {
        "year": year,
        "ROE": f.at["ROE", year],
        "ROE(归母)": f.at["ROE(归母)", year],
        "净利润": f.at["净利润", year],
        "营业收入": f.at["营业收入", year],
        "平均总资产": f.at["平均总资产", year],
        "平均股东权益": f.at["平均股东权益", year],
        "销售净利率": f.at["销售净利率", year],
        "总资产周转率": f.at["总资产周转率", year],
        "权益乘数": f.at["权益乘数", year],
        "税负率": f.at["税负率", year],
        "利息负担率": f.at["利息负担率", year],
        "息税前利润率": f.at["息税前利润率", year],
        "资产负债率": _div(loader.get(balance, "负债合计", year),
                       loader.get(balance, "资产总计", year)),
        "销售毛利率": _div(
            loader.get(income, "营业收入", year)
            - loader.get(income, "营业成本", year),
            loader.get(income, "营业收入", year)),
        "ROA": f.at["ROA", year],
    }


def summary_table(balance, income, years) -> pd.DataFrame:
    """报告用汇总表：三因素 + 五因素逐年对比（百分数格式化）。"""
    d = decompose(balance, income, years)
    label_map = {
        "ROE": "净资产收益率 ROE",
        "ROE(归母)": "归母净资产收益率",
        "三因素_销售净利率": "① 销售净利率",
        "三因素_总资产周转率": "② 总资产周转率（次）",
        "三因素_权益乘数": "③ 权益乘数（倍）",
        "五因素_税负率": "① 税负率（净利润/利润总额）",
        "五因素_利息负担率": "② 利息负担率（利润总额/EBIT）",
        "五因素_息税前利润率": "③ 息税前利润率（EBIT/营业收入）",
        "五因素_总资产周转率": "④ 总资产周转率（次）",
        "五因素_权益乘数": "⑤ 权益乘数（倍）",
    }
    rows = []
    for key, label in label_map.items():
        if key not in d.index:
            continue
        row = {"项目": label}
        for y in years:
            v = d.at[key, y]
            if pd.isna(v):
                row[y] = "—"
            elif "倍" in label or "次" in label:
                row[y] = "{:,.3f}".format(v)
            else:
                row[y] = "{:,.2f}%".format(v * 100)
        rows.append(row)
    return pd.DataFrame(rows)
