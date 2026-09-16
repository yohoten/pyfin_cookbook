# -*- coding: utf-8 -*-
"""
analysis/loader.py —— 数据装载
================================================================
把 data/raw/ 下的原始数据装载为统一的三张报表 DataFrame。

输出约定
--------
* 索引 index  = 规范科目名（中文，见 config.COLUMNS）
* 列   columns = 年份（int，如 2025），代表该年 12-31 / 全年
* 值   value   = 人民币元（float）；原始缺失记 NaN

关键设计
--------
loader 是唯一的"口径转换层"：上游（JSON / HTML）的单位、字段名差异
全部在此收敛，下游分析模块只面对"中文科目名 × 年份 × 元"。
"""

import json
import os

import numpy as np
import pandas as pd

import config as C
import fs_parser as P


# ------------------------------------------------------------------
# 主数据源：东方财富
# ------------------------------------------------------------------
def _load_em_json(statement: str):
    path = os.path.join(C.RAW_DIR, "em_%s.json" % C.EM_REPORT_NAMES[statement])
    if not os.path.exists(path):
        raise FileNotFoundError("缺少东方财富数据文件：%s\n"
                                "请先运行 python fetch_data.py" % path)
    with open(path, encoding="utf-8") as fh:
        payload = json.load(fh)
    return payload["result"]["data"]


def load_from_eastmoney(statement: str, years=None) -> pd.DataFrame:
    """东方财富 JSON -> 规范科目 × 年份 的 DataFrame（单位：元）。"""
    records = _load_em_json(statement)
    # 只保留年报（12-31）
    records = [r for r in records if str(r.get("REPORT_DATE", ""))[5:10] == "12-31"]
    by_year = {int(str(r["REPORT_DATE"])[:4]): r for r in records}

    if years is None:
        years = sorted(by_year.keys())

    rows = {}
    for cn_name, (field, _) in C.COLUMNS.items():
        series = {}
        for year in years:
            rec = by_year.get(year)
            value = rec.get(field) if rec else None
            series[year] = float(value) if isinstance(value, (int, float)) else np.nan
        # 该科目在所有目标年度均为空 -> 不属于本表
        if not all(np.isnan(v) for v in series.values()):
            rows[cn_name] = series

    df = pd.DataFrame(rows).T
    df = df.reindex(columns=years)
    df.index.name = "科目"
    return df


# ------------------------------------------------------------------
# 核对数据源：新浪财经
# ------------------------------------------------------------------
def load_from_sina(statement: str, years=None) -> pd.DataFrame:
    """新浪 HTML -> 规范科目 × 年份 的 DataFrame（单位：元）。"""
    if years is None:
        years = C.ALL_YEARS
    file_kind = C.SINA_FILE_KIND[statement]

    parsed_by_year = {}
    for year in years:
        path = os.path.join(C.RAW_DIR, "vfd_%s_%s_%d.html"
                            % (C.COMPANY["sina_code"], file_kind, year))
        if not os.path.exists(path):
            continue
        try:
            parsed_by_year[year] = P.parse_year(
                C.RAW_DIR, statement, year, C.COMPANY["sina_code"], file_kind)
        except Exception:                            # noqa: BLE001
            continue

    rows = {}
    for cn_name, (_, aliases) in C.COLUMNS.items():
        if not aliases:
            continue
        series = {}
        found = False
        for year in years:
            parsed = parsed_by_year.get(year)
            value = None
            if parsed:
                for alias in aliases:
                    value = P.query(parsed, alias)
                    if value is not None:
                        break
            if value is not None:
                found = True
            series[year] = value * C.SINA_UNIT_SCALE if value is not None else np.nan
        if found:
            rows[cn_name] = series

    df = pd.DataFrame(rows).T
    df = df.reindex(columns=years)
    df.index.name = "科目"
    return df


# ------------------------------------------------------------------
# 汇总装载
# ------------------------------------------------------------------
def load_all(years=None, save_csv=True) -> dict:
    """
    装载三张报表（东方财富口径为主）。

    返回
    ----
    dict: {"balance": df, "income": df, "cashflow": df}
    """
    if years is None:
        years = C.ALL_YEARS

    statements = {}
    for st in ("balance", "income", "cashflow"):
        df = load_from_eastmoney(st, years)
        statements[st] = df
        if save_csv:
            df.to_csv(os.path.join(C.PROCESSED_DIR, "%s.csv" % st),
                      encoding="utf-8-sig", float_format="%.2f")
    return statements


# ------------------------------------------------------------------
# 取值辅助
# ------------------------------------------------------------------
def get(df: pd.DataFrame, item: str, year: int, default=np.nan) -> float:
    """安全取数：科目不存在或为 NaN 时返回 default。"""
    if item not in df.index:
        return default
    value = df.at[item, year] if year in df.columns else np.nan
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return default
    return float(value)


def avg_balance(df: pd.DataFrame, item: str, year: int) -> float:
    """
    计算平均余额 = (期初 + 期末) / 2。
    期初即上一年年末；上一年数据缺失时退化为期末余额。
    """
    end = get(df, item, year)
    begin = get(df, item, year - 1)
    if np.isnan(begin):
        return end
    if np.isnan(end):
        return begin
    return (begin + end) / 2.0


def fmt_yi(value, digits=2) -> str:
    """金额格式化：元 -> 亿元字符串。"""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "—"
    return ("{:,.%df}" % digits).format(value / C.UNIT_YI)


def fmt_pct(value, digits=2, signed=False) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "—"
    fmt = "{:+.%df}%%" % digits if signed else "{:,.%df}%%" % digits
    return fmt.format(value * 100)
