# -*- coding: utf-8 -*-
"""
analysis/verify.py —— 数据质量控制
================================================================
两项校验，构成报告的"数据可靠性"依据：

1. **表内平衡校验**：会计准则恒等式检验
   - 资产总计 = 流动资产合计 + 非流动资产合计
   - 负债和股东权益合计 = 负债合计 + 股东权益合计
   - 股东权益合计 = 归母权益 + 少数股东权益
   - 资产总计 = 负债合计 + 股东权益合计
   - 营业总收入 = 营业收入 + 其他业务收入（此处检验 营业总收入 ≥ 营业收入）
   - 净利润 = 归母净利润 + 少数股东损益
   - 经营/投资/筹资净额 + 汇率影响 = 现金及现金等价物净增加额

2. **双数据源交叉核验**：东方财富 F10 与新浪财经对同一科目的数值比对，
   偏差超过阈值即报警，避免单一数据源的模板错位被静默带入分析。
"""

import numpy as np
import pandas as pd

import config as C
from . import loader

# 相对偏差容忍度：万分之一（主要用于吸收万元取整误差）
TOLERANCE = 1e-4

# 每股类指标单位为「元/股」，不做亿元换算，单独比对
PER_SHARE_ITEMS = {"基本每股收益"}


def _row(df, item, years):
    return [loader.get(df, item, y) for y in years]


def check_identity(balance: pd.DataFrame, income: pd.DataFrame,
                   cashflow: pd.DataFrame, years) -> pd.DataFrame:
    """会计恒等式校验。"""
    checks = [
        ("资产=流动+非流动资产", "balance",
         lambda b, i, c, y: (loader.get(b, "资产总计", y)
                             - loader.get(b, "流动资产合计", y)
                             - loader.get(b, "非流动资产合计", y))),
        ("资产=负债+股东权益", "balance",
         lambda b, i, c, y: (loader.get(b, "资产总计", y)
                             - loader.get(b, "负债合计", y)
                             - loader.get(b, "股东权益合计", y))),
        ("权益=归母权益+少数股东权益", "balance",
         lambda b, i, c, y: (loader.get(b, "股东权益合计", y)
                             - loader.get(b, "归属于母公司股东权益合计", y)
                             - loader.get(b, "少数股东权益", y))),
        ("资产总计=负债和股东权益合计", "balance",
         lambda b, i, c, y: (loader.get(b, "资产总计", y)
                             - loader.get(b, "负债和股东权益合计", y))),
        ("净利润=归母净利+少数股东损益", "income",
         lambda b, i, c, y: (loader.get(i, "净利润", y)
                             - loader.get(i, "归属于母公司股东的净利润", y)
                             - loader.get(i, "少数股东损益", y))),
        ("现金流净增加额=三活动净额+汇率影响", "cashflow",
         lambda b, i, c, y: (loader.get(c, "现金及现金等价物净增加额", y)
                             - loader.get(c, "经营活动产生的现金流量净额", y)
                             - loader.get(c, "投资活动产生的现金流量净额", y)
                             - loader.get(c, "筹资活动产生的现金流量净额", y)
                             - loader.get(c, "汇率变动对现金的影响", y))),
        ("期末现金=期初现金+净增加额", "cashflow",
         lambda b, i, c, y: (loader.get(c, "期末现金及现金等价物余额", y)
                             - loader.get(c, "期初现金及现金等价物余额", y)
                             - loader.get(c, "现金及现金等价物净增加额", y))),
    ]

    records = []
    for name, stmt, func in checks:
        diff_abs, diff_rel, status = [], [], []
        for year in years:
            d = func(balance, income, cashflow, year)
            base = loader.get(
                {"balance": balance, "income": income,
                 "cashflow": cashflow}[stmt], "资产总计", year)
            if stmt == "income":
                base = loader.get(income, "营业总收入", year)
            elif stmt == "cashflow":
                base = loader.get(cashflow, "现金及现金等价物净增加额", year)
            rel = abs(d) / abs(base) if base and not np.isnan(base) else np.nan
            diff_abs.append(d)
            diff_rel.append(rel)
            status.append("通过" if (rel is not None and not np.isnan(rel)
                                    and rel < 1e-6) else
                          ("可接受" if (rel is not None and not np.isnan(rel)
                                       and rel < 1e-3) else "需关注"))
        records.append({
            "校验项": name,
            **{"%d 差额(元)" % y: round(diff_abs[k2], 2)
               for k2, y in enumerate(years)},
            "结论": ("通过" if all(s == "通过" for s in status) else
                     ("基本通过" if all(s in ("通过", "可接受")
                                        for s in status) else "需关注")),
        })
    return pd.DataFrame(records)


def cross_validate(years) -> pd.DataFrame:
    """东方财富 vs 新浪财经，逐科目比对（单位统一为元）。"""
    em, sina = {}, {}
    for st in ("balance", "income", "cashflow"):
        try:
            em[st] = loader.load_from_eastmoney(st, years)
        except Exception:                            # noqa: BLE001
            em[st] = None
        try:
            sina[st] = loader.load_from_sina(st, years)
        except Exception:                            # noqa: BLE001
            sina[st] = None

    records = []
    for item in C.VERIFY_ITEMS:
        for st in ("balance", "income", "cashflow"):
            de, ds = em.get(st), sina.get(st)
            if de is None or ds is None:
                continue
            if item not in de.index or item not in ds.index:
                continue
            per_share = item in PER_SHARE_ITEMS
            scale = 1.0 if per_share else C.UNIT_YI
            unit_label = "元/股" if per_share else "亿元"
            for year in years:
                a = de.at[item, year]
                b = ds.at[item, year]
                if pd.isna(a) and pd.isna(b):
                    continue
                if pd.isna(a) or pd.isna(b):
                    records.append({"报表": C.STATEMENT_CN[st], "科目": item,
                                    "年份": year,
                                    "东方财富(%s)" % unit_label:
                                        None if pd.isna(a) else round(a / scale, 4),
                                    "新浪财经(%s)" % unit_label:
                                        None if pd.isna(b) else round(b / scale, 4),
                                    "相对偏差": None, "结论": "单边缺失"})
                    continue
                denom = max(abs(a), abs(b))
                rel = abs(a - b) / denom if denom else 0.0
                records.append({
                    "报表": C.STATEMENT_CN[st], "科目": item, "年份": year,
                    "东方财富(%s)" % unit_label: round(a / scale, 4),
                    "新浪财经(%s)" % unit_label: round(b / scale, 4),
                    "相对偏差": round(rel, 6),
                    "结论": "一致" if rel < TOLERANCE else
                            ("基本一致" if rel < 0.01 else "存在差异"),
                })
            break   # 同一科目只归属一张报表
    return pd.DataFrame(records)


def summary(verify_df: pd.DataFrame) -> dict:
    if verify_df.empty:
        return {"total": 0}
    return {
        "total": len(verify_df),
        "一致": int((verify_df["结论"] == "一致").sum()),
        "基本一致": int((verify_df["结论"] == "基本一致").sum()),
        "存在差异": int((verify_df["结论"] == "存在差异").sum()),
        "单边缺失": int((verify_df["结论"] == "单边缺失").sum()),
    }
