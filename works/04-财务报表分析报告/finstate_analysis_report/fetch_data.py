# -*- coding: utf-8 -*-
"""
fetch_data.py —— 数据采集
================================================================
从两个公开数据源采集美的集团三张报表的年度数据：

* 主数据源：东方财富 F10 财务分析接口（JSON，标准化科目字段，单位：元）
* 核对数据源：新浪财经财务报表页面（HTML，单位：万元）

用法：
    python fetch_data.py            # 采集 2021-2025 年数据
    python fetch_data.py --years 2021 2022 2023 2024 2025

说明：采集结果落盘到 data/raw/，后续分析完全基于本地文件，
      保证报告结果可复现，且不依赖运行时的网络状态。
"""

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request

import config as C


def _http_get(url: str, headers: dict, timeout: int = 40) -> bytes:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


# ------------------------------------------------------------------
# 主数据源：东方财富
# ------------------------------------------------------------------
def fetch_eastmoney(statement: str, out_dir: str) -> str:
    """抓取某一张报表的全部年度记录（JSON）。"""
    params = {
        "reportName": C.EM_REPORT_NAMES[statement],
        "columns": "ALL",
        "filter": C.EM_FILTER.format(secucode=C.COMPANY["code"]),
        "pageNumber": "1",
        "pageSize": "100",
        "sortTypes": "-1",
        "sortColumns": "REPORT_DATE",
        "source": "HSF10",
        "client": "PC",
    }
    url = C.EM_API + "?" + urllib.parse.urlencode(params)
    raw = _http_get(url, C.EM_HEADERS)
    payload = json.loads(raw.decode("utf-8"))
    result = payload.get("result") or {}
    records = result.get("data") or []
    if not records:
        raise RuntimeError("东方财富接口未返回数据：%s" % statement)

    path = os.path.join(out_dir, "em_%s.json" % C.EM_REPORT_NAMES[statement])
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    print("  [东方财富] %-9s %2d 个年度报告期 -> %s"
          % (C.STATEMENT_CN[statement], len(records), os.path.basename(path)))
    return path


# ------------------------------------------------------------------
# 核对数据源：新浪财经
# ------------------------------------------------------------------
def fetch_sina(statement: str, year: int, out_dir: str) -> str:
    """抓取新浪财经某一年度的报表页面（HTML，GB18030 编码）。"""
    url = C.SINA_URL.format(kind=C.SINA_FILE_KIND[statement],
                            code=C.COMPANY["sina_code"], year=year)
    raw = _http_get(url, C.EM_HEADERS)
    path = os.path.join(out_dir, "vfd_%s_%s_%d.html"
                        % (C.COMPANY["sina_code"],
                           C.SINA_FILE_KIND[statement], year))
    with open(path, "wb") as fh:
        fh.write(raw)
    return path


# ------------------------------------------------------------------
def main(argv=None):
    parser = argparse.ArgumentParser(description="采集美的集团财务报表数据")
    parser.add_argument("--years", nargs="+", type=int,
                        default=C.ALL_YEARS,
                        help="需要采集的新浪页面年份（用于交叉核验）")
    parser.add_argument("--skip-sina", action="store_true",
                        help="跳过新浪数据采集")
    args = parser.parse_args(argv)

    out_dir = C.RAW_DIR
    os.makedirs(out_dir, exist_ok=True)

    print("=" * 66)
    print("数据采集：%s（%s）" % (C.COMPANY["name"], C.COMPANY["code"]))
    print("=" * 66)

    print("\n[1/2] 主数据源 —— 东方财富 F10（标准化科目，单位：元）")
    for st in ("balance", "income", "cashflow"):
        try:
            fetch_eastmoney(st, out_dir)
        except Exception as exc:                     # noqa: BLE001
            print("  [警告] %s 采集失败：%s" % (C.STATEMENT_CN[st], exc))
        time.sleep(0.4)

    if not args.skip_sina:
        print("\n[2/2] 核对数据源 —— 新浪财经（单位：万元）")
        for st in ("balance", "income", "cashflow"):
            for year in args.years:
                try:
                    fetch_sina(st, year, out_dir)
                except Exception as exc:             # noqa: BLE001
                    print("  [警告] %s %d 采集失败：%s"
                          % (C.STATEMENT_CN[st], year, exc))
                time.sleep(0.3)
            print("  [新浪财经] %-9s %d 个年度页面完成" % (C.STATEMENT_CN[st],
                                                          len(args.years)))

    print("\n采集完成，原始数据目录：%s" % out_dir)


if __name__ == "__main__":
    sys.exit(main())
