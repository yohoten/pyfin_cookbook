# -*- coding: utf-8 -*-
"""
fs_parser.py —— 财务报表页面解析器
================================================================
把新浪财经 vFD_* 报表页面（HTML 表格）解析成结构化字典。

解析后结构：
    {
        "2025-12-31": {"营业总收入": 45850240.70, "营业成本": ..., ...},
        "2025-09-30": {...},
        ...
    }
数值单位与页面一致（万元）；折算在 loader 中统一完成。

设计要点
--------
1. 新浪对「现金流量表」页面沿用了 id="ProfitStatementNewTable0"，
   因此不按固定 id 取表，而是自动识别页面中第一个 *NewTable* 表格。
2. 页面编码为 GB18030，需显式解码，否则中文科目名会乱码。
3. 空值 / "--" 表示该科目当期不存在或不适用，按缺失处理（None），
   由 loader 决定是补零还是不参与计算。
"""

import html
import os
import re

_TABLE_ID_RE = re.compile(r'<table[^>]*id="([A-Za-z]+NewTable\d+)"', re.S)
_MISSING_TOKENS = {"", "--", "-", "—", "－", "N/A", "nan", "None"}


def _clean(cell: str) -> str:
    """剥离 HTML 标签、还原实体、压缩空白。"""
    text = re.sub(r"<[^>]+>", "", cell)
    text = html.unescape(text)
    text = text.replace("\xa0", " ").replace("\u3000", " ")
    return text.strip()


def _to_float(text: str):
    """把单元格文本转成 float；缺失值返回 None。"""
    s = _clean(text).replace(",", "").replace(" ", "")
    if s in _MISSING_TOKENS:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _read_html(path: str) -> str:
    with open(path, "rb") as fh:
        raw = fh.read()
    for enc in ("gb18030", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("gb18030", "ignore")


def _extract_table(page: str, table_id: str = None) -> str:
    """取出指定 id 的表格；未指定时自动识别页面中的第一张 *NewTable* 表。"""
    if table_id is None:
        hit = _TABLE_ID_RE.search(page)
        if not hit:
            raise ValueError("页面中未找到财务报表表格（*NewTable*）")
        table_id = hit.group(1)
    pattern = r'<table[^>]*id="%s"[^>]*>(.*?)</table>' % re.escape(table_id)
    hit = re.search(pattern, page, re.S)
    if not hit:
        raise ValueError("未找到表格 id=%s" % table_id)
    return hit.group(1)


def _iter_rows(table_html: str):
    """逐行产出单元格文本列表（只取 <td>，忽略表头 <th>）。"""
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if tds:
            yield [_clean(x) for x in tds]


def _normalize_item(name: str) -> str:
    """统一科目名写法，消除全角括号、序号前缀、缩进等干扰。"""
    s = name.strip()
    s = s.replace("（", "(").replace("）", ")")
    s = s.replace("：", ":")
    s = re.sub(r"^\d+[、.]\s*", "", s)          # 去 "1、" "3." 前缀
    s = re.sub(r"^[一二三四五六七八九十]+[、.]\s*", "", s)  # 去 "一、" 前缀
    s = re.sub(r"\s+", "", s)
    return s


def parse_statement_file(path: str, table_id: str = None) -> dict:
    """
    解析单个报表页面。

    返回
    ----
    dict: {报表日期: {科目名: 金额(万元)}}
    """
    page = _read_html(path)
    table = _extract_table(page, table_id)
    rows = list(_iter_rows(table))
    if not rows:
        raise ValueError("表格为空: %s" % path)

    # 第一行形如 ['报表日期', '2025-12-31', '2025-09-30', ...]
    header = rows[0]
    dates = [d for d in header[1:] if d]

    result = {}
    for row in rows[1:]:
        name = _normalize_item(row[0])
        if not name:
            continue
        values = row[1:]
        # 仅有一个单元格的行是分区标题（如「流动资产」），跳过
        if not values:
            continue
        for idx, date in enumerate(dates):
            value = _to_float(values[idx]) if idx < len(values) else None
            result.setdefault(date, {})[name] = value
    return result


def parse_year(raw_dir: str, kind: str, year: int, code: str,
               file_kind: str) -> dict:
    """
    解析某一年度某个报表页面，只保留该年 12-31（年度报告）的数据。

    参数
    ----
    kind : 报表类型标识（balance / income / cashflow），仅用于报错提示
    file_kind : 磁盘文件名中的报表标识（BalanceSheet 等）
    """
    path = os.path.join(raw_dir, "vfd_%s_%s_%d.html" % (code, file_kind, year))
    if not os.path.exists(path):
        raise FileNotFoundError("缺少原始数据文件：%s" % path)
    parsed = parse_statement_file(path)
    target = "%d-12-31" % year
    if target not in parsed:
        raise ValueError("%s 页面未包含 %s 的数据，实际可用日期：%s"
                         % (kind, target, sorted(parsed.keys())))
    return parsed[target]


def query(parsed: dict, alias: str):
    """按别名查询某一科目的全年数值；未命中返回 None。"""
    key = _normalize_item(alias)
    if key in parsed:
        return parsed[key]
    for k, v in parsed.items():
        if key and (key in k or k in key):
            return v
    return None
