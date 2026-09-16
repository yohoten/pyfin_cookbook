# -*- coding: utf-8 -*-
"""
run_all.py —— 一键执行全部分析
================================================================
用法：
    python run_all.py                # 完整运行（含图表）
    python run_all.py --no-charts    # 只出数据表
    python run_all.py --years 2023 2024 2025

产出（output/ 目录）：
    tables/*.csv        各项分析结果表
    charts/*.png        报告插图
    分析结果汇总.xlsx    全部表格合并为一个工作簿
    关键结论.json       供报告引用的关键数值
"""

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

import config as C
from analysis import charts, dupont, indicators, loader, structure, trend, verify


def _jsonable(obj):
    """把 pandas / numpy 对象递归转换为可 JSON 序列化的原生类型。"""
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, pd.Series):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, pd.DataFrame):
        return {str(k): _jsonable(v) for k, v in obj.to_dict().items()}
    if isinstance(obj, np.ndarray):
        return [_jsonable(v) for v in obj.tolist()]
    if isinstance(obj, (list, tuple, set)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        return None if np.isnan(obj) else float(obj)
    if obj is None:
        return None
    return str(obj)


def main(argv=None):
    parser = argparse.ArgumentParser(description="美的集团 2025 年报财务分析")
    parser.add_argument("--no-charts", action="store_true", help="跳过图表生成")
    parser.add_argument("--years", nargs="+", type=int, default=C.ALL_YEARS)
    args = parser.parse_args(argv)

    years = args.years
    detail_years = [y for y in C.DETAIL_YEARS if y in years] or years

    print("=" * 70)
    print(" 财务报表分析程序包")
    print(" 标的：%s（%s）  报告期：%d 年年度报告"
          % (C.COMPANY["name"], C.COMPANY["code"], C.COMPANY["report_year"]))
    print(" 分析区间：%d – %d" % (years[0], years[-1]))
    print("=" * 70)

    # ---------------- 1. 装载 ----------------
    print("\n[1] 装载报表数据（%s）" % C.SOURCE_NOTE["em"])
    sts = loader.load_all(years)
    balance, income, cashflow = sts["balance"], sts["income"], sts["cashflow"]
    print("    资产负债表 %d 个科目 / 利润表 %d 个科目 / 现金流量表 %d 个科目"
          % (len(balance), len(income), len(cashflow)))

    # ---------------- 2. 数据校验 ----------------
    print("\n[2] 数据质量校验")
    id_df = verify.check_identity(balance, income, cashflow, years)
    id_df.to_csv(os.path.join(C.TABLE_DIR, "00_会计恒等式校验.csv"),
                 index=False, encoding="utf-8-sig")
    print("    会计恒等式校验：%d 项，结论 %s"
          % (len(id_df), "、".join(sorted(set(id_df["结论"])))))
    cv_df = verify.cross_validate(years)
    if not cv_df.empty:
        cv_df.to_csv(os.path.join(C.TABLE_DIR, "00_双源交叉核验.csv"),
                     index=False, encoding="utf-8-sig")
        cv_summary = verify.summary(cv_df)
        print("    双源交叉核验：%d 个科目-年份组合，一致 %d，基本一致 %d，"
              "存在差异 %d，单边缺失 %d"
              % (cv_summary["total"], cv_summary["一致"],
                 cv_summary["基本一致"], cv_summary["存在差异"],
                 cv_summary["单边缺失"]))
    else:
        cv_summary = {}
        print("    双源交叉核验：新浪数据缺失，已跳过")

    # ---------------- 3. 结构分析 ----------------
    print("\n[3] 项目结构分析（共同比分析）")
    bs = structure.balance_structure(balance, detail_years)
    bs.to_csv(os.path.join(C.TABLE_DIR, "01_资产负债表结构.csv"),
              index=False, encoding="utf-8-sig")
    bg = structure.balance_group_summary(balance, detail_years)
    bg.to_csv(os.path.join(C.TABLE_DIR, "01_资产负债表结构_聚合.csv"),
              index=False, encoding="utf-8-sig")
    ins = structure.income_structure(income, detail_years)
    ins.to_csv(os.path.join(C.TABLE_DIR, "02_利润表结构.csv"),
               index=False, encoding="utf-8-sig")
    cfs = structure.cashflow_structure(cashflow, detail_years)
    cfs.to_csv(os.path.join(C.TABLE_DIR, "03_现金流量表结构.csv"),
               index=False, encoding="utf-8-sig")
    key_struct = pd.DataFrame(
        [structure.key_metrics(balance, income, cashflow, y)
         for y in detail_years])
    key_struct.to_csv(os.path.join(C.TABLE_DIR, "03_结构分析关键指标.csv"),
                      index=False, encoding="utf-8-sig")
    print("    资产负债表 / 利润表 / 现金流量表结构表已生成")

    # ---------------- 4. 趋势分析 ----------------
    print("\n[4] 项目趋势分析（定基指数 + 环比 + CAGR）")
    tr_b = trend.trend_table(balance, C.STATEMENT_ITEMS["balance"], years,
                            C.BASE_YEAR)
    tr_b.to_csv(os.path.join(C.TABLE_DIR, "04_资产负债表趋势.csv"),
                index=False, encoding="utf-8-sig")
    tr_i = trend.trend_table(income, C.STATEMENT_ITEMS["income"], years,
                            C.BASE_YEAR)
    tr_i.to_csv(os.path.join(C.TABLE_DIR, "04_利润表趋势.csv"),
                index=False, encoding="utf-8-sig")
    tr_c = trend.trend_table(cashflow, C.STATEMENT_ITEMS["cashflow"], years,
                            C.BASE_YEAR)
    tr_c.to_csv(os.path.join(C.TABLE_DIR, "04_现金流量表趋势.csv"),
                index=False, encoding="utf-8-sig")
    kg = trend.key_growth(income, balance, cashflow, years)
    kg.to_csv(os.path.join(C.TABLE_DIR, "04_关键增长指标.csv"),
              index=False, encoding="utf-8-sig")
    revenue_cagr = None
    if "营业总收入" in income.index:
        s = income.loc["营业总收入"]
        revenue_cagr = ((s[years[-1]] / s[years[0]]) ** (1 / (len(years) - 1))
                        - 1)
    print("    三年/五年趋势表已生成；营业总收入 CAGR = %s"
          % ("—" if revenue_cagr is None else "%.2f%%" % (revenue_cagr * 100)))

    # ---------------- 5. 财务指标分析 ----------------
    print("\n[5] 财务指标分析（偿债 / 营运 / 盈利 / 发展 / 现金质量）")
    ind = indicators.compute(balance, income, cashflow, years)
    ind.to_csv(os.path.join(C.TABLE_DIR, "05_财务指标_长表.csv"),
               index=False, encoding="utf-8-sig")
    ind_disp = indicators.to_display(ind, years)
    ind_disp.to_csv(os.path.join(C.TABLE_DIR, "05_财务指标_展示表.csv"),
                    index=False, encoding="utf-8-sig")
    print("    共 %d 项指标 × %d 个年度" % (len(ind), len(years)))

    # ---------------- 6. 杜邦分析 ----------------
    print("\n[6] 杜邦分析（三因素 / 五因素 / 连环替代法）")
    dup_tab = dupont.decompose(balance, income, years)
    dup_tab.to_csv(os.path.join(C.TABLE_DIR, "06_杜邦分解表.csv"),
                   encoding="utf-8-sig")
    dup_sum = dupont.summary_table(balance, income, years)
    dup_sum.to_csv(os.path.join(C.TABLE_DIR, "06_杜邦分解_展示表.csv"),
                   index=False, encoding="utf-8-sig")
    attr = dupont.attribution(balance, income, years)
    attr["三因素"].to_csv(os.path.join(C.TABLE_DIR,
                                     "06_杜邦三因素归因.csv"),
                        encoding="utf-8-sig")
    attr["五因素"].to_csv(os.path.join(C.TABLE_DIR,
                                     "06_杜邦五因素归因.csv"),
                        encoding="utf-8-sig")
    with open(os.path.join(C.TABLE_DIR, "06_杜邦归因_元数据.json"), "w",
              encoding="utf-8") as fh:
        json.dump(_jsonable(attr["meta"]), fh, ensure_ascii=False, indent=2)
    print("    ROE %s → %s，变动 %s"
          % ("%.2f%%" % attr["meta"]["三因素_ROE基期(%)"],
             "%.2f%%" % attr["meta"]["三因素_ROE报告期(%)"],
             "%+.2fpp" % attr["meta"]["三因素_ROE变动(pp)"]))

    # ---------------- 7. 图表 ----------------
    chart_paths = []
    if not args.no_charts:
        print("\n[7] 生成图表")
        font = charts.setup_style()
        print("    中文字体：%s" % font)
        chart_paths = [
            charts.chart_asset_structure(balance, years),
            charts.chart_liab_equity(balance, years),
            charts.chart_income_structure(income, years),
            charts.chart_revenue_profit(income, years),
            charts.chart_index_trend(balance, income, cashflow, years),
            charts.chart_cashflow(cashflow, years),
            charts.chart_solvency(ind, years),
            charts.chart_operating(ind, years),
            charts.chart_profitability(ind, years),
            charts.chart_dupont(dup_tab, years),
            charts.chart_dupont_waterfall(attr["三因素"], attr["meta"]),
            charts.chart_shareholder(balance, income, cashflow, years),
        ]

    # ---------------- 8. 汇总 Excel ----------------
    print("\n[8] 汇总输出")
    sheets = {
        "会计恒等式校验": id_df,
        "资产负债表结构": bs,
        "资产负债表结构聚合": bg,
        "利润表结构": ins,
        "现金流量表结构": cfs,
        "结构分析关键指标": key_struct,
        "资产负债表趋势": tr_b,
        "利润表趋势": tr_i,
        "现金流量表趋势": tr_c,
        "关键增长指标": kg,
        "财务指标": ind_disp,
        "杜邦分解": dup_sum.reset_index().rename(columns={"index": "项目"}),
        "杜邦三因素归因": attr["三因素"].reset_index(),
        "杜邦五因素归因": attr["五因素"].reset_index(),
    }
    if not cv_df.empty:
        sheets["双源交叉核验"] = cv_df
    xlsx = os.path.join(C.OUTPUT_DIR, "分析结果汇总.xlsx")
    with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name[:31], index=False)
    print("    Excel 汇总表：%s（%d 个工作表）" % (xlsx, len(sheets)))

    # ---------------- 9. 关键结论 JSON ----------------
    facts = {
        "公司": C.COMPANY,
        "分析区间": years,
        "数据来源": C.SOURCE_NOTE,
        "数据校验": {
            "会计恒等式": id_df.to_dict("records"),
            "双源核验汇总": cv_summary,
        },
        "结构分析关键指标": key_struct.to_dict("records"),
        "关键增长指标": kg.to_dict("records"),
        "财务指标": ind_disp.to_dict("records"),
        "杜邦分解": dup_tab.round(6).to_dict(),
        "杜邦归因": {
            "三因素": attr["三因素"].round(6).to_dict(),
            "五因素": attr["五因素"].round(6).to_dict(),
            "meta": attr["meta"],
        },
        "杜邦树": {str(y): dupont.tree(balance, income, years, y)
                 for y in years},
        "图表": [os.path.basename(p) for p in chart_paths],
    }
    facts_path = os.path.join(C.OUTPUT_DIR, "关键结论.json")
    with open(facts_path, "w", encoding="utf-8") as fh:
        json.dump(_jsonable(facts), fh, ensure_ascii=False, indent=2)
    print("    关键结论：%s" % facts_path)
    print("\n全部完成。输出目录：%s" % C.OUTPUT_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
