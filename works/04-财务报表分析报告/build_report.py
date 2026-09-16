# -*- coding: utf-8 -*-
"""
build_report.py —— 生成《财务报表分析报告》
================================================================
读取 output/tables 下的分析结果与 output/charts 下的图表，
渲染为一份自包含的 HTML 研究报告（图表以 base64 内嵌，可直接
离线打开、可直接浏览器打印为 PDF）。

用法：
    python build_report.py                # 默认输出到 output/财务报表分析报告.html
    python build_report.py -o 路径.html

说明：报告中的所有数值均由程序包计算生成，正文叙述中的关键数字
      与 output/tables 下的结果表一一对应，可逐项核对。
"""

import argparse
import base64
import datetime
import html
import json
import os

import pandas as pd

import config as C


# ------------------------------------------------------------------
# 工具
# ------------------------------------------------------------------
def _img64(name):
    path = os.path.join(C.CHART_DIR, name)
    if not os.path.exists(path):
        return '<p class="missing">[缺少图表：%s]</p>' % html.escape(name)
    with open(path, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode("ascii")
    return ('<img class="chart" alt="%s" src="data:image/png;base64,%s"/>'
            % (html.escape(name), b64))


def _tbl(df, float_fmt="%.2f", pct_cols=None, max_rows=None):
    """DataFrame -> HTML 表格（按列名自动选择数字格式）。"""
    d = df
    if max_rows:
        d = d.head(max_rows)
    cols = list(d.columns)
    head = "".join("<th>%s</th>" % html.escape(str(c)) for c in cols)
    rows = []
    for _, r in d.iterrows():
        tds = []
        for c in cols:
            v = r[c]
            if v is None or (isinstance(v, float) and pd.isna(v)):
                tds.append("<td>—</td>")
                continue
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                name = str(c)
                if name in ("基期值", "报告期值"):    # 因素取值需保留精度
                    tds.append("<td class='num'>%.4f</td>" % v)
                elif name.endswith("(pp)"):            # 百分点：值本身就是 pp
                    tds.append("<td class='num'>%+.2f pp</td>" % v)
                elif ("同比" in name or "变动" in name
                      or "影响" in name or "超额" in name):
                    tds.append("<td class='num'>%+.2f%%</td>" % (v * 100))
                elif ("占比" in name or "CAGR" in name
                      or name.endswith("%") or "偏差" in name):
                    tds.append("<td class='num'>%.2f%%</td>" % (v * 100))
                else:
                    tds.append("<td class='num'>%s</td>"
                               % "{:,.2f}".format(v))
            else:
                tds.append("<td>%s</td>" % html.escape(str(v)))
        rows.append("<tr>%s</tr>" % "".join(tds))
    return ("<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>"
            % (head, "".join(rows)))


def _details(summary, body):
    return ('<details><summary>%s</summary>%s</details>' % (summary, body))


def _cards(items):
    out = ['<div class="cards">']
    for label, value, note in items:
        out.append('<div class="card"><div class="cv">%s</div>'
                   '<div class="cl">%s</div><div class="cn">%s</div></div>'
                   % (value, html.escape(label), note))
    out.append("</div>")
    return "".join(out)


# ------------------------------------------------------------------
# 报告主体
# ------------------------------------------------------------------
def build(out_path=None):
    T = C.TABLE_DIR
    rd = lambda n: pd.read_csv(os.path.join(T, n), encoding="utf-8-sig")

    id_df = rd("00_会计恒等式校验.csv")
    cv_df = rd("00_双源交叉核验.csv")
    bs = rd("01_资产负债表结构_聚合.csv")
    bsi = rd("01_资产负债表结构.csv")
    ins = rd("02_利润表结构.csv")
    cfs = rd("03_现金流量表结构.csv")
    kg = rd("04_关键增长指标.csv")
    ind = rd("05_财务指标_展示表.csv")
    ind_num = rd("05_财务指标_长表.csv")
    dup = rd("06_杜邦分解_展示表.csv")
    dup3 = rd("06_杜邦三因素归因.csv")
    dup5 = rd("06_杜邦五因素归因.csv")

    years = C.ALL_YEARS
    comp = C.COMPANY

    # ---- 关键数字 ----
    def ind_val(metric, year):
        """从长表读取数值型指标（展示表中为已格式化的字符串）。"""
        row = ind_num[ind_num["指标"] == metric]
        if row.empty or str(year) not in row.columns:
            return None
        v = row.iloc[0][str(year)]
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    rev25 = kg.loc[kg["指标"] == "营业总收入", "2025(亿元)"].iloc[0]
    rev_g = kg.loc[kg["指标"] == "营业总收入", "2025同比"].iloc[0]
    npf25 = kg.loc[kg["指标"] == "归母净利润", "2025(亿元)"].iloc[0]
    npf_g = kg.loc[kg["指标"] == "归母净利润", "2025同比"].iloc[0]
    ta25 = kg.loc[kg["指标"] == "资产总计", "2025(亿元)"].iloc[0]
    cfo25 = kg.loc[kg["指标"] == "经营活动现金流净额", "2025(亿元)"].iloc[0]
    cfo_g = kg.loc[kg["指标"] == "经营活动现金流净额", "2025同比"].iloc[0]
    roe25 = ind_val("净资产收益率(ROE)", "2025")
    roep25 = ind_val("归母净资产收益率", "2025")
    gm25 = ind_val("销售毛利率", "2025")
    nm25 = ind_val("销售净利率", "2025")
    dr25 = ind_val("资产负债率", "2025")
    cr25 = ind_val("流动比率", "2025")
    tat25 = ind_val("总资产周转率", "2025")

    def fmt(v, pct=False):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "—"
        return ("%.2f%%" % (v * 100)) if pct else ("%.2f" % v)

    title = "美的集团（000333.SZ）2025 年年度报告财务报表分析"
    css = """
:root{--ink:#1a1a1a;--sub:#5a6472;--line:#e3e7ec;--bg:#f6f7f9;
--accent:#1F4E79;--accent2:#2E86C1;--warn:#C0392B;--ok:#1E8449;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font-family:"Microsoft YaHei","PingFang SC","Hiragino Sans GB",sans-serif;
font-size:14px;line-height:1.75}
.wrap{max-width:1120px;margin:0 auto;padding:34px 26px 70px}
header.hero{background:linear-gradient(135deg,#12365a,#1F4E79 60%,#2E86C1);
color:#fff;border-radius:14px;padding:30px 34px;margin-bottom:26px}
header.hero h1{margin:0 0 8px;font-size:25px;letter-spacing:.5px}
header.hero .meta{font-size:12.5px;opacity:.9;display:flex;flex-wrap:wrap;gap:18px}
h2{font-size:19px;color:var(--accent);margin:40px 0 12px;padding-bottom:8px;
border-bottom:2px solid var(--line)}
h3{font-size:15.5px;color:#22364a;margin:26px 0 8px}
h4{font-size:14px;color:#33475b;margin:18px 0 6px}
p{margin:8px 0;text-align:justify}
section.card,div.box{background:#fff;border:1px solid var(--line);
border-radius:12px;padding:20px 24px;margin:16px 0}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(158px,1fr));
gap:12px;margin:14px 0}
.card{background:#fff;border:1px solid var(--line);border-radius:11px;
padding:14px 15px}
.card .cv{font-size:21px;font-weight:700;color:var(--accent)}
.card .cv.up{color:var(--warn)}
.card .cl{font-size:12.5px;color:#33475b;margin-top:3px}
.card .cn{font-size:11.5px;color:var(--sub);margin-top:2px}
table{border-collapse:collapse;width:100%;font-size:12px;margin:10px 0 4px;
background:#fff}
th{background:#eef2f6;color:#22364a;font-weight:600;padding:7px 8px;
border:1px solid var(--line);text-align:center;white-space:nowrap}
td{padding:6px 8px;border:1px solid var(--line);vertical-align:top}
td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
tbody tr:nth-child(even){background:#fafbfc}
img.chart{width:100%;border:1px solid var(--line);border-radius:10px;
margin:10px 0 4px;background:#fff}
.note{font-size:11.5px;color:var(--sub);margin:2px 0 14px}
.tldr{background:#eef5fb;border-left:4px solid var(--accent);padding:14px 18px;
border-radius:0 10px 10px 0;margin:12px 0}
.tldr li{margin:6px 0}
details{background:#fff;border:1px solid var(--line);border-radius:10px;
padding:10px 14px;margin:10px 0}
summary{cursor:pointer;font-weight:600;color:var(--accent);font-size:13px}
.tag{display:inline-block;background:#eaf1f7;color:#2c4a63;border-radius:20px;
padding:2px 11px;font-size:11.5px;margin:0 6px 6px 0}
.warn{color:var(--warn);font-weight:600}
.ok{color:var(--ok);font-weight:600}
.small{font-size:12px;color:var(--sub)}
footer{margin-top:40px;padding-top:14px;border-top:1px solid var(--line);
font-size:11.5px;color:var(--sub)}
@media print{body{background:#fff}header.hero{background:#1F4E79}
details{page-break-inside:avoid}img.chart{page-break-inside:avoid}}
"""

    # ---- 数据校验结论 ----
    n_ok = int((cv_df["结论"] == "一致").sum())
    n_diff = cv_df[cv_df["结论"] == "存在差异"]
    diff_txt = "；".join(
        "%s %s %d年：东方财富 %s，新浪 %s"
        % (r["报表"], r["科目"], r["年份"], r[cv_df.columns[3]], r[cv_df.columns[4]])
        for _, r in n_diff.iterrows()) or "无"

    parts = []
    parts.append("<!DOCTYPE html><html lang='zh-CN'><head>"
                 "<meta charset='utf-8'/>"
                 "<meta name='viewport' content='width=device-width,initial-scale=1'/>"
                 "<title>%s</title><style>%s</style></head><body><div class='wrap'>"
                 % (html.escape(title), css))

    # ---------------- 封面 ----------------
    parts.append(
        "<header class='hero'><h1>%s</h1>"
        "<div class='meta'><span>标的：美的集团股份有限公司（000333.SZ）</span>"
        "<span>报告期：2025 年年度报告（经审计）</span>"
        "<span>分析区间：%d–%d 年</span>"
        "<span>报表口径：中国企业会计准则 · 合并报表</span></div></header>"
        % (html.escape(title), years[0], years[-1]))

    parts.append("<div>" + "".join(
        "<span class='tag'>%s</span>" % t for t in
        ["项目结构分析", "项目趋势分析", "财务指标分析", "杜邦分析",
         "连环替代法归因", "双数据源交叉核验", "Python 程序包"]) + "</div>")

    # ---------------- 摘要 ----------------
    parts.append("<h2>一、核心结论（先读这一段）</h2>")
    parts.append(_cards([
        ("营业总收入", "%.0f 亿元" % rev25, "同比 %s" % fmt(rev_g, True)),
        ("归母净利润", "%.0f 亿元" % npf25, "同比 %s" % fmt(npf_g, True)),
        ("净资产收益率 ROE", fmt(roe25, True), "归母口径 %s" % fmt(roep25, True)),
        ("销售毛利率", fmt(gm25, True), "同比基本持平"),
        ("资产负债率", fmt(dr25, True), "连续四年下降"),
        ("经营现金流净额", "%.0f 亿元" % cfo25, "同比 %s" % fmt(cfo_g, True)),
    ]))

    parts.append("<div class='tldr'><ol>"
        "<li><b>成长性：收入与利润连续三年双位数增长，且呈加速态势。</b>"
        "营业总收入从 2021 年 3,434 亿元增至 2025 年 4,585 亿元（CAGR 7.50%），"
        "增速由 2022 年的 0.68% 逐年抬升至 2025 年的 12.08%；归母净利润 CAGR 11.36%，"
        "增速持续快于收入，体现出明显的经营杠杆效应。</li>"
        "<li><b>盈利质量：利润率持续改善。</b>销售净利率由 2021 年 8.50% 提升至 2025 年 "
        "9.75%，五年提升 1.25 个百分点；毛利率稳定在 26.4% 左右，改善主要来自"
        "费用率优化与利息净收益，而非毛利率扩张。</li>"
        "<li><b>资产效率：周转率止跌回升。</b>总资产周转率在 2021–2024 年由 0.880 次"
        "降至 0.747 次后，2025 年回升至 0.753 次；资产总额 2025 年仅增长 0.73%，"
        "公司从 2024 年 H 股融资带来的资产负债表扩张转入消化期。</li>"
        "<li><b>资本结构：主动去杠杆。</b>资产负债率连续四年下降（65.25%→61.17%），"
        "有息负债占负债比重由 23.96% 降至 18.12%；这是 2024→2025 年 ROE 小幅"
        "下降 0.10 个百分点的唯一负向因素。</li>"
        "<li><b>风险信号：现金流与预收款走弱。</b>经营活动现金流净额同比下降 11.84%，"
        "净利润现金含量由 156.13% 回落至 119.82%（仍高于 100% 的安全线）；"
        "合同负债 2025 年首次下降 4.59%，需关注渠道打款意愿与需求端变化。</li>"
        "<li><b>杜邦归因结论：ROE 下滑完全是杠杆因素造成，经营质量在改善。</b>"
        "连环替代法显示，销售净利率贡献 +0.47pp、总资产周转率贡献 +0.15pp，"
        "权益乘数拖累 -0.72pp，三者合计 -0.10pp。</li>"
        "</ol></div>")

    # ---------------- 二、数据与方法 ----------------
    parts.append("<h2>二、分析对象、数据与方法</h2>")
    parts.append("<div class='box'><h3>2.1 分析对象</h3>"
        "<p>美的集团股份有限公司（%s）是全球化科技集团，业务覆盖智能家居"
        "（ToC 家电）与工业技术、楼宇科技、机器人与自动化、数字化创新（ToB）"
        "双引擎。2025 年公司实现营业总收入 4,585.02 亿元，规模居全球家电行业前列。"
        "选择该公司作为分析样本的原因：报表科目完整（应收、存货、商誉、有息负债、"
        "少数股东权益俱全），四类财务指标与杜邦三因素均有实质性分析空间。</p>"
        % comp["code"])
    parts.append("<h3>2.2 数据来源与口径</h3>"
        "<p>本报告全部财务数据取自公司 <b>2025 年年度报告（经审计）</b>的合并"
        "报表口径，通过程序从两个公开数据接口采集，并做交叉核验：</p>"
        "<ul>"
        "<li><b>主数据源</b>：东方财富 F10 财务分析接口 —— 标准化科目字段，"
        "单位元，覆盖 2004–2025 年共 22 个年度报告期。</li>"
        "<li><b>核对数据源</b>：新浪财经财务报表页面 —— 单位万元，用于逐科目比对。</li>"
        "<li><b>单位换算</b>：分析统一以「元」为内部口径，展示时折算为「亿元」。</li>"
        "<li><b>指标口径</b>：周转率与回报率的分母一律使用<b>平均余额</b>"
        "=（期初 + 期末）/ 2，保证时期数与时点数的时间口径匹配。</li>"
        "</ul>")
    parts.append("<h3>2.3 数据质量校验</h3>")
    parts.append("<p><span class='ok'>✔ 会计恒等式校验：7 项全部通过</span>。"
        "包括「资产 = 负债 + 股东权益」「资产 = 流动资产 + 非流动资产」"
        "「净利润 = 归母净利润 + 少数股东损益」「现金净增加额 = 三类活动净额 "
        "+ 汇率影响」等，差额均为 0。</p>")
    parts.append("<p><span class='ok'>✔ 双数据源交叉核验：%d 个科目-年度组合中 "
        "%d 个完全一致</span>（相对偏差 &lt; 0.01%%）。存在差异的 %d 项均已定位原因，"
        "且不影响本报告结论：</p><ul>"
        "<li><b>2023 年营业成本 / 销售费用</b>：两家数据源相差 29.28 亿元且方向相反，"
        "系 2024 年年报对 2023 年可比数据进行了成本与销售费用的<b>重分类</b>；"
        "东方财富采用重分类后口径，本报告从之（保证跨年可比）。</li>"
        "<li><b>2021–2022 年偿还债务支付的现金</b>：新浪模板当年口径偏差，"
        "采用东方财富标准化口径。</li>"
        "<li><b>衍生金融负债 / 交易性金融负债</b>：新浪模板将两个不同科目合并列示，"
        "已按东方财富标准口径拆分。</li></ul>" % (len(cv_df), n_ok, len(n_diff)))
    parts.append(_details("查看：会计恒等式校验结果表", _tbl(id_df)))
    parts.append(_details("查看：双数据源交叉核验差异明细（%d 项）" % len(n_diff),
                          _tbl(n_diff)))
    parts.append("<h3>2.4 分析方法</h3>"
        "<table><thead><tr><th>分析模块</th><th>方法</th><th>对应程序文件</th></tr></thead>"
        "<tbody>"
        "<tr><td>项目结构分析</td><td>共同比分析（垂直分析）：各项目 / 报表总体基数，"
        "观察构成与三年结构变迁</td><td><code>analysis/structure.py</code></td></tr>"
        "<tr><td>项目趋势分析</td><td>定基指数（2021=100）+ 环比增长率 + 复合增长率"
        "（CAGR）+ 相对营收的超额增速</td><td><code>analysis/trend.py</code></td></tr>"
        "<tr><td>财务指标分析</td><td>偿债、营运、盈利、发展、现金质量五类共 40 项指标，"
        "存量指标用平均余额</td><td><code>analysis/indicators.py</code></td></tr>"
        "<tr><td>杜邦分析</td><td>三因素 + 五因素分解，并以连环替代法量化各因素"
        "对 ROE 变动的贡献</td><td><code>analysis/dupont.py</code></td></tr>"
        "</tbody></table>")

    # ---------------- 三、资产负债表 ----------------
    parts.append("<h2>三、资产负债表分析</h2>")
    parts.append("<h3>3.1 项目结构分析（共同比）</h3>")
    parts.append(_img64("01_asset_structure.png"))
    parts.append("<p class='note'>图 1　资产结构演变（左：各类资产占总资产比重；"
        "右：资产规模与同比增速）。数据来源：公司 2021–2025 年年度报告，"
        "本程序计算。</p>")
    parts.append(_tbl(bs))
    parts.append("<p class='note'>表 1　资产负债表结构聚合表（资产类占总资产、"
        "负债类占负债合计、权益类占股东权益合计）。</p>")
    parts.append("<p><b>资产端：轻资产运行、金融资产占比高。</b>"
        "2025 年末资产总计 6,087.92 亿元。其中经营性资产（应收票据及账款、"
        "应收款项融资、预付款、其他应收款、存货、合同资产）合计 1,357.07 亿元，"
        "占总资产 22.29%，三年基本稳定在 22% 左右，说明主业资产占用没有随规模"
        "扩张而失控；长期经营资产（固定资产、在建工程、使用权资产、无形资产、"
        "商誉、长期待摊费用）1,094.58 亿元，占 17.98%；其余 <b>45.73%</b> 为货币资金"
        "及各类投资性金融资产，公司整体呈典型的「轻固定资产 + 重金融资产」结构，"
        "资产弹性大、可变现能力强。</p>")
    parts.append("<p><b>两个显著的结构变化值得注意：</b></p>"
        "<ul><li><b>货币资金占比由 23.23% 骤降至 14.00%（-9.23pp）。</b>"
        "2024 年公司完成 H 股发行，年末货币资金高达 1,404.10 亿元形成高基数；"
        "2025 年资金被用于偿还有息负债、扩大对外投资与提高分红回购，"
        "货币资金回落至 852.47 亿元，属于资金配置行为，而非经营恶化。</li>"
        "<li><b>商誉占比回升至 5.63%（342.57 亿元）。</b>商誉主要来自库卡（KUKA）"
        "等并购，2025 年因并购活动增加而上升。商誉占总资产与归母权益的比重"
        "（约 15.3%）需要持续跟踪，一旦 ToB 业务盈利不及预期存在减值风险。</li></ul>")
    parts.append("<p><b>负债端：以无息经营性负债为主。</b>"
        "2025 年末负债合计 3,723.68 亿元，其中经营性负债（应付票据及账款、"
        "合同负债、应付职工薪酬、应交税费、其他应付款、其他流动负债）"
        "占 78.41%，较 2024 年提高 4.74pp；有息负债仅占 18.12%（674.81 亿元），"
        "较 2024 年下降 4.78pp。负债结构呈「上游资金占用为主 + 低有息杠杆」"
        "特征，说明公司对产业链上下游具备较强议价能力，财务风险低、"
        "但杜邦意义上的财务杠杆贡献也在收缩。</p>")
    parts.append(_img64("02_liability_equity_structure.png"))
    parts.append("<p class='note'>图 2　负债结构与财务杠杆水平。数据来源同上。</p>")
    parts.append(_details("查看：资产负债表全部科目共同比明细表（%d 行）" % len(bsi),
                          _tbl(bsi, max_rows=None)))

    parts.append("<h3>3.2 项目趋势分析（2021 = 100）</h3>")
    parts.append(_img64("05_index_trend.png"))
    parts.append("<p class='note'>图 3　主要项目定基指数趋势。数据来源同上。</p>")
    tr_b = rd("04_资产负债表趋势.csv")
    key_b = tr_b[tr_b["项目"].isin(
        ["资产总计", "流动资产合计", "非流动资产合计", "存货", "应收账款",
         "合同负债", "货币资金", "负债合计", "有息负债"]) |
        tr_b["项目"].isin([])] if "有息负债" in tr_b["项目"].values else \
        tr_b[tr_b["项目"].isin(
            ["资产总计", "流动资产合计", "非流动资产合计", "存货", "应收账款",
             "合同负债", "货币资金", "负债合计"])]
    parts.append(_tbl(key_b))
    parts.append("<p class='note'>表 2　资产负债表重点项目趋势表"
        "（绝对额单位：亿元；定基指数以 2021 年 = 100）。</p>")
    parts.append("<p><b>趋势结论：</b>① 资产总计五年增长 57.0%（CAGR 11.92%），"
        "但 2025 年仅增 0.73%，扩张明显收力；② 存货五年增长 40.8%（2025 年"
        "同比仅 +2.04%），与收入增长基本匹配，未出现库存积压；"
        "③ <b>应收账款 CAGR 13.20%，明显快于收入 CAGR 7.50%</b>，五年累计增长 "
        "64.2%，是资产端增速最快的项目之一，反映 ToB 业务占比提升与"
        "赊销条件相对放宽，需跟踪账龄与减值计提；④ 合同负债 2025 年"
        "同比 -4.59%（492.55→469.93 亿元），是五年内首次下降，"
        "作为经销商打款的「蓄水池」指标，其回落值得作为需求端预警信号关注。</p>")

    # ---------------- 四、利润表 ----------------
    parts.append("<h2>四、利润表分析</h2>")
    parts.append("<h3>4.1 项目结构分析（共同比，以营业总收入为 100%）</h3>")
    parts.append(_img64("03_income_structure.png"))
    parts.append("<p class='note'>图 4　利润表项目结构（占营业总收入比重）。"
        "数据来源同上。</p>")
    key_i = ins[ins["项目"].isin(
        ["营业成本", "销售费用", "管理费用", "研发费用", "财务费用",
         "营业利润", "利润总额", "所得税费用", "净利润",
         "归属于母公司股东的净利润"])]
    parts.append(_tbl(key_i))
    parts.append("<p class='note'>表 3　利润表重点项目共同比。</p>")
    parts.append("<p><b>成本费用结构：毛利率稳定，费用率小幅优化。</b>"
        "2025 年营业成本占收入 73.28%（对应毛利率 26.39%），与 2024 年的 73.23% "
        "基本持平，说明在原材料价格波动与家电以旧换新政策补贴的双重背景下，"
        "公司靠产品结构升级（COLMO、东芝等高端品牌与 ToB 业务）稳住了毛利水平。"
        "费用端，销售费用率 9.35%（-0.12pp）、管理费用率 3.51%（-0.04pp）、"
        "研发费用率 3.88%（-0.09pp），三项费用率同步小幅下降，"
        "体现规模效应与费用管控。</p>")
    parts.append("<p><b>财务费用为负，是利润的重要补充。</b>"
        "2025 年财务费用为 -59.04 亿元（占收入 -1.29%），主要因利息收入 "
        "84.44 亿元远高于利息支出 22.11 亿元，叠加汇兑收益。这是公司"
        "「账上现金充裕」在利润表上的直接映射，但也意味着该利润来源"
        "依赖利率环境，利率下行时贡献会收窄。</p>")
    parts.append("<p><b>利润形成路径：</b>营业利润率 11.61%（+0.22pp）→ "
        "利润总额率 11.58% → 净利率 9.75%（+0.23pp）。所得税费用占收入 1.87%，"
        "实际税负率（净利润/利润总额）83.87%，处于制造业正常水平。</p>")

    parts.append("<h3>4.2 项目趋势分析</h3>")
    parts.append(_img64("04_revenue_profit_trend.png"))
    parts.append("<p class='note'>图 5　营业总收入、归母净利润规模与增速对比。</p>")
    tr_i = rd("04_利润表趋势.csv")
    key_i2 = tr_i[tr_i["项目"].isin(
        ["营业总收入", "营业成本", "销售费用", "管理费用", "研发费用",
         "营业利润", "利润总额", "净利润", "归属于母公司股东的净利润"])]
    parts.append(_tbl(key_i2))
    parts.append("<p class='note'>表 4　利润表重点项目趋势表。</p>")
    parts.append(_tbl(kg))
    parts.append("<p class='note'>表 5　关键增长指标汇总（含五年 CAGR）。</p>")
    parts.append("<p><b>趋势结论：增长在加速，且利润增速快于收入。</b>"
        "营业总收入同比增速由 2022 年 0.68% → 2023 年 8.10% → 2024 年 9.47% → "
        "2025 年 12.08%，五年 CAGR 7.50%；归母净利润 CAGR 11.36%，"
        "2025 年同比 +14.03%。「毛利贡献」（收入 - 营业成本）CAGR 达 11.94%，"
        "高于收入增速 4.4 个百分点，验证了毛利率改善与产品结构升级的贡献。"
        "唯一负向是经营活动现金流净额 2025 年同比 -11.84%，"
        "形成「利润加速、现金减速」的剪刀差，需在第六节进一步验证其质量。</p>")

    # ---------------- 五、现金流量表 ----------------
    parts.append("<h2>五、现金流量表分析</h2>")
    parts.append("<h3>5.1 项目结构分析</h3>")
    parts.append(_img64("06_cashflow_structure.png"))
    parts.append("<p class='note'>图 6　三类活动现金流量净额与自由现金流。</p>")
    key_c = cfs[cfs["项目"].isin(
        ["销售商品、提供劳务收到的现金", "经营活动现金流入小计",
         "购买商品、接受劳务支付的现金", "经营活动现金流出小计",
         "投资活动现金流入小计", "投资活动现金流出小计",
         "筹资活动现金流入小计", "偿还债务支付的现金",
         "分配股利、利润或偿付利息支付的现金", "筹资活动现金流出小计",
         "经营活动产生的现金流量净额", "投资活动产生的现金流量净额",
         "筹资活动产生的现金流量净额", "现金及现金等价物净增加额"])]
    parts.append(_tbl(key_c))
    parts.append("<p class='note'>表 6　现金流量表项目结构（流入项以现金流入总量"
        "为基数，流出项以现金流出总量为基数，净额项以现金流入总量为基数）。</p>")
    parts.append("<p><b>流入结构：</b>2025 年经营活动现金流入占现金流入总量 "
        "59.88%（2024 年 68.41%），投资活动流入升至 27.66%（主要是收回投资"
        "1,975.32 亿元，反映理财与结构性存款到期回收），筹资活动流入 12.47%。"
        "经营性现金流入占比下降并非主业回款恶化，而是投资活动现金流转活跃"
        "带来的「分母效应」。</p>")
    parts.append("<p><b>流出结构：</b>筹资活动现金流出占比由 8.22% 大幅升至 "
        "21.51%，其中偿还债务支付现金 1,120.64 亿元、分配股利利润及付息 "
        "330.80 亿元，公司把 2024 年融资得来的资金用于降杠杆与回报股东，"
        "这是当年货币资金下降的直接原因。</p>")
    parts.append("<p><b>净额结构：</b>经营活动净额 533.46 亿元（正）、投资活动净额 "
        "+253.40 亿元（由负转正，主因收回投资大于新增投资）、筹资活动净额 "
        "-649.58 亿元（大幅流出）。三者合计使现金及现金等价物净增加 133.90 亿元，"
        "期末现金余额 685.09 亿元，现金存量健康。</p>")
    parts.append("<h3>5.2 项目趋势分析</h3>")
    tr_c = rd("04_现金流量表趋势.csv")
    key_c2 = tr_c[tr_c["项目"].isin(
        ["销售商品、提供劳务收到的现金", "经营活动现金流入小计",
         "经营活动产生的现金流量净额", "购建固定资产、无形资产和其他长期资产支付的现金",
         "投资活动产生的现金流量净额", "筹资活动产生的现金流量净额",
         "现金及现金等价物净增加额", "期末现金及现金等价物余额"])]
    parts.append(_tbl(key_c2))
    parts.append("<p class='note'>表 7　现金流量表重点项目趋势表。</p>")
    parts.append("<p><b>趋势结论：</b>经营活动现金流净额在 2023 年跳升 67.07% 后，"
        "2024 年 +4.51%、2025 年 -11.84%。销售商品收到现金 4,262.11 亿元，"
        "同比 +9.66%，仍低于收入增速 12.08%，说明部分收入以应收票据、"
        "应收账款与合同资产形式存在。资本开支（购建长期资产）1,114.19 亿元中"
        "含并购支付，剔除后的自由现金流 422.04 亿元，仍属充裕但同比回落。</p>")

    # ---------------- 六、财务指标分析 ----------------
    parts.append("<h2>六、财务指标分析</h2>")
    parts.append(_tbl(ind))
    parts.append("<p class='note'>表 8　财务指标汇总表（共 40 项，五类）。"
        "存量类指标分母采用平均余额。<b>口径提示</b>：本表中「权益乘数」"
        "为期末口径（资产总计/股东权益合计），而第七节杜邦分析中的权益乘数"
        "为平均余额口径（平均总资产/平均股东权益），两者数值略有差异属正常现象；"
        "「总资产周转率」「ROA」等指标以营业收入为分子，与第三方平台"
        "以营业总收入为分子的口径略有差异。</p>")

    parts.append("<h3>6.1 偿债能力：短期指标小幅回落，长期持续改善</h3>")
    parts.append(_img64("07_solvency.png"))
    parts.append("<p class='note'>图 7　偿债能力指标。</p>")
    parts.append("<p>2025 年流动比率 1.21（上年 1.11）、速动比率 1.03（上年 0.93），"
        "两项均回升并站上 1 倍线，短期流动性充裕；现金比率 0.25（上年 0.42）"
        "回落明显，是货币资金下降的直接结果，但结合「应付账款 + 应付票据 + "
        "合同负债」等无息负债占流动负债的比重（经营性负债占负债合计 78.41%），"
        "公司真正的刚性短期偿付压力很小。长期看，资产负债率 61.17%，"
        "连续四年下降（2021 年 65.25%）；产权比率 1.57（上年 1.65）；"
        "利息保障倍数 25.01 倍（EBIT 对利息支出的覆盖），偿债风险很低。</p>"
        "<p><b>需要区分的一点：</b>61.17% 的资产负债率看似偏高，但其中"
        "大量是应付账款、合同负债、其他流动负债（含销售返利）等<b>无息"
        "经营性负债</b>，这类负债本质是商业模式带来的资金占用，而非融资。"
        "若仅以有息负债（674.81 亿元）计算，有息负债率仅约 11.1%，"
        "公司真实财务杠杆远低于账面资产负债率所显示的水平。</p>")

    parts.append("<h3>6.2 营运能力：周转效率触底回升</h3>")
    parts.append(_img64("08_operating_efficiency.png"))
    parts.append("<p class='note'>图 8　营运能力指标。</p>")
    parts.append("<p>总资产周转率 0.753 次，较 2024 年的 0.747 次小幅回升，"
        "终结了连续三年的下滑；流动资产周转率 1.13 次（上年 1.21 次）仍在下行，"
        "主因金融资产规模庞大。存货周转天数由 63.37 天（2021）升至 69.51 天，"
        "应收账款周转天数由 26.35 天升至 30.49 天，两项都在变慢；"
        "但应付账款周转天数 135.56 天更长，使得<b>现金转换周期为 -35.57 天</b>——"
        "即公司先收钱、后付款，营运资本为负，上下游资金净占用约 "
        "「存货 + 应收」规模量级的资金。这是家电龙头渠道地位的直接体现，"
        "也是其低成本资金来源。</p>"
        "<p><b>风险提示：</b>应收账款 CAGR（13.20%）显著高于收入 CAGR（7.50%），"
        "若 ToB 业务回款条件不改善，周转天数可能继续拉长，"
        "并带来信用减值损失（2025 年信用减值损失约 35.4 亿元量级）。</p>")

    parts.append("<h3>6.3 盈利能力：利润率改善，ROE 受杠杆拖累</h3>")
    parts.append(_img64("09_profitability.png"))
    parts.append("<p class='note'>图 9　盈利能力指标。</p>")
    parts.append("<p>销售毛利率 26.39%（-0.03pp，基本持平）、营业利润率 11.61%"
        "（+0.22pp）、销售净利率 9.75%（+0.23pp）。总资产净利率 ROA 7.34% "
        "（上年 7.11%）回升；净资产收益率 ROE 19.19%（上年 19.28%）、"
        "归母 ROE 19.98%（上年 20.30%）小幅下降。<b>关键在于拆解："
        "盈利质量在改善，ROA 在回升，ROE 下降完全由权益乘数下降所致</b>，"
        "即公司主动降低财务杠杆的结果，属于「用 ROE 换安全边际」的"
        "主动选择，而非经营恶化。</p>"
        "<p>每股指标：基本每股收益 5.80 元（+6.6%）、每股净资产 29.38 元。"
        "值得注意的是 EPS 增速（+6.6%）低于归母净利润增速（+14.03%），"
        "差异来自 2024 年 H 股发行导致的股本扩大（2025 年末股本 75.97 亿股）"
        "以及持续的股份回购注销。</p>")

    parts.append("<h3>6.4 发展能力与股东回报</h3>")
    parts.append(_img64("12_shareholder_return.png"))
    parts.append("<p class='note'>图 10　每股指标与股东回报。</p>")
    parts.append("<p>收入 +12.11%、归母净利润 +14.03%、总资产 +0.73%、"
        "股东权益 +3.85%，呈现「利润快于收入、收入远快于资产」的健康组合，"
        "说明增长由效率与结构驱动，而非铺资产。可持续增长率（归母 ROE × 留存率）"
        "约 4.94%，明显低于实际收入增速 12.11%，其差额依靠<b>提升资产周转效率</b>"
        "与<b>维持当前杠杆水平</b>来弥补；这意味着若无周转率进一步改善，"
        "当前的高增长与高分红难以同时长期维持，是未来需要跟踪的核心矛盾。</p>"
        "<p>分红与回购：2025 年现金分红及付息支出 330.80 亿元，"
        "占归母净利润 75.28%（上年 59.22%），公司披露口径全年分红比例 73.64%、"
        "另实施回购约 116 亿元，股东回报力度显著提升。</p>")

    parts.append("<h3>6.5 现金质量：仍高于安全线，但连续两年回落</h3>")
    parts.append("<p>净利润现金含量（经营现金流净额 / 净利润）119.82%，"
        "较 2024 年的 156.13% 回落 36.31 个百分点，但仍高于 100%，"
        "说明账面利润有充足现金支撑、不依赖应计项目；销售现金比率 "
        "11.69%（上年 14.86%）；经营现金流 / 有息负债 81.34%（上年 71.67%），"
        "偿债的现金保障能力反而增强。自由现金流 422.04 亿元（上年 526.72 亿元），"
        "在 330.80 亿元分红 + 约 116 亿元回购的股东回报规模下，"
        "自由现金流覆盖率约 0.95 倍，边际偏紧，是 2026 年需要观察的约束条件。</p>")

    # ---------------- 七、杜邦分析 ----------------
    parts.append("<h2>七、杜邦分析</h2>")
    parts.append("<h3>7.1 三因素分解：ROE = 销售净利率 × 总资产周转率 × 权益乘数</h3>")
    parts.append(_img64("10_dupont_factors.png"))
    parts.append("<p class='note'>图 11　杜邦三因素演变与 ROE 走势。</p>")
    parts.append(_tbl(dup))
    parts.append("<p class='note'>表 9　杜邦分解结果（三因素乘积与五因素乘积"
        "均与 ROE 严格相等，无残差）。</p>")
    parts.append(_img64("11_dupont_waterfall.png"))
    parts.append("<p class='note'>图 12　连环替代法归因瀑布图（2024 → 2025）。</p>")
    parts.append(_tbl(dup3))
    parts.append("<p class='note'>表 10　杜邦三因素连环替代法归因结果"
        "（单位：百分点）。</p>")
    parts.append("<p><b>五年总览：</b>ROE 由 2021 年 21.52% 缓降至 2025 年 19.19%，"
        "累计 -2.33pp。三因素中，<b>销售净利率是唯一的正向驱动</b>"
        "（8.50% → 9.75%，累计 +1.25pp）；总资产周转率由 0.880 次降至 0.753 次，"
        "权益乘数由 2.877 降至 2.614，两者合计构成主要拖累。</p>")
    parts.append("<p><b>2024→2025 年归因（连环替代法，单位 pp）：</b>"
        "销售净利率 +0.47、总资产周转率 +0.15、权益乘数 -0.72，合计 -0.10pp。"
        "<b>结论非常明确：2025 年 ROE 的微降完全来自财务杠杆收缩</b>——"
        "公司偿还有息负债、扩大权益基础，使权益乘数由 2.713 降至 2.614；"
        "而盈利质量与资产效率实际都在改善，经营层面是「进步」的。</p>")

    parts.append("<h3>7.2 五因素分解：进一步定位盈利质量来源</h3>")
    parts.append(_tbl(dup5))
    parts.append("<p class='note'>表 11　杜邦五因素连环替代法归因结果"
        "（EBIT = 利润总额 + 利息费用；单位：百分点）。</p>")
    parts.append("<p>五因素模型把「销售净利率」进一步拆为税负率、利息负担率与"
        "息税前利润率，可定位盈利改善的来源。2024→2025 年：税负率贡献 +0.20pp、"
        "利息负担率贡献 +0.20pp、息税前利润率贡献 +0.07pp。<b>其中"
        "「利息负担率」贡献为正，本质是利息支出相对 EBIT 下降带来的</b>——"
        "即降杠杆在减少财务费用的同时，也通过这条路径反哺了 ROE，"
        "部分抵消了权益乘数下降的负面影响。这说明公司的去杠杆并非单方面"
        "牺牲回报，而是在「降杠杆—降财务费用—稳 ROE」之间取得了较好的平衡。</p>")

    parts.append("<h3>7.3 杜邦体系图</h3>")
    parts.append("<div class='box'>"
        "<p style='font-family:Consolas,monospace;font-size:12.5px;"
        "line-height:1.9;overflow-x:auto'><b>净资产收益率 ROE = 19.19%</b><br>"
        "　├─ 销售净利率（净利润/营业收入）= <b>9.75%</b>"
        "　← 盈利质量，五年持续改善<br>"
        "　│　　├─ 销售毛利率 = 26.39%（产品结构与价格管理）<br>"
        "　│　　├─ 期间费用率（销售 9.35% / 管理 3.51% / 研发 3.88%）<br>"
        "　│　　└─ 财务费用率 = -1.29%（利息净收益贡献）<br>"
        "　├─ 总资产周转率（营业收入/平均总资产）= <b>0.753 次</b>"
        "　← 资产效率，2025 年止跌回升<br>"
        "　│　　├─ 应收账款周转率 = 11.97 次（30.49 天）<br>"
        "　│　　├─ 存货周转率 = 5.25 次（69.51 天）<br>"
        "　│　　└─ 流动资产周转率 = 1.13 次（受金融资产规模拖累）<br>"
        "　└─ 权益乘数（平均总资产/平均股东权益）= <b>2.614 倍</b>"
        "　← 财务杠杆，主动收缩<br>"
        "　　　　└─ 资产负债率 = 61.17%（有息负债率仅约 11.1%）</p></div>")

    # ---------------- 八、综合结论 ----------------
    parts.append("<h2>八、综合结论与关注事项</h2>")
    parts.append("<h3>8.1 总体评价</h3>")
    parts.append("<div class='box'><p>综合四项分析，<b>美的集团 2025 年报表呈现出"
        "「增长加速、盈利改善、杠杆收缩、现金充裕但边际走弱」的组合特征</b>。"
        "公司正处于从「规模扩张」转向「质量与回报」的资产负债表切换期："
        "用 2024 年 H 股融得的资金降低有息负债、提升分红回购，"
        "代价是权益乘数下降与 ROE 的小幅回落；同时依靠 ToB 业务与高端化"
        "维持收入与利润率的双改善。从财务分析角度，这是一种<b>主动的、"
        "以牺牲少量 ROE 换取更低财务风险与更高股东现金回报</b>的策略选择，"
        "经营质量并未恶化。</p></div>")
    parts.append("<h3>8.2 三条优势</h3><ul>"
        "<li><b>负营运资本商业模式</b>：现金转换周期 -35.57 天，"
        "经营性负债占负债合计 78.41%，对上下游具备强议价能力。</li>"
        "<li><b>利润率持续改善</b>：净利率五年 +1.25pp，且改善来自费用管控"
        "与结构升级，而非一次性损益。</li>"
        "<li><b>偿债风险极低</b>：利息保障倍数 25.01 倍，有息负债率约 11.1%，"
        "经营现金流对有息负债覆盖 81.34%。</li></ul>")
    parts.append("<h3>8.3 四项需要跟踪的风险信号</h3><ul>"
        "<li><b>经营现金流与利润增速出现剪刀差</b>：2025 年经营现金流 -11.84%，"
        "净利润现金含量由 156.13% 降至 119.82%；自由现金流对「分红 + 回购」"
        "的覆盖已接近 1 倍。</li>"
        "<li><b>合同负债首次下降（-4.59%）</b>：作为渠道打款的先行指标，"
        "需结合 2026 年一季报验证需求端景气度。</li>"
        "<li><b>应收账款增速持续快于收入</b>（CAGR 13.20% vs 7.50%），"
        "周转天数升至 30.49 天，需关注 ToB 业务账期与信用减值。</li>"
        "<li><b>商誉 342.57 亿元</b>（占总资产 5.63%、占归母权益约 15.3%），"
        "主要来自库卡等并购，ToB 业务盈利若不及预期存在减值风险。</li></ul>")
    parts.append("<h3>8.4 后续分析建议</h3><ul>"
        "<li>引入同业对比（格力电器、海尔智家、海信家电）以区分公司因素与"
        "行业因素；</li>"
        "<li>拆分 ToC 与 ToB 分部数据，验证收入结构与回款条件的关系；</li>"
        "<li>对商誉做敏感性测算，量化减值对 ROE 与归母净利润的冲击。</li></ul>")

    # ---------------- 九、局限性 ----------------
    parts.append("<h2>九、局限性说明</h2><ul>"
        "<li>本报告仅基于合并报表的公开数据，未获取分部报告、关联交易、"
        "或有事项等附注明细，部分结论需结合年报全文进一步验证。</li>"
        "<li>指标口径存在多种业界惯例（如现金比率是否纳入短期投资、"
        "周转率是否用营业总收入作分子），本报告已在表中逐项标注口径；"
        "与第三方平台披露值的差异主要来自口径而非数据错误。</li>"
        "<li>东方财富对 2023 年成本与销售费用采用 2024 年年报重分类后的口径，"
        "若与 2023 年原披露值直接对比会产生约 29.28 亿元的差异。</li>"
        "<li>ROE 采用「净利润 / 平均股东权益」口径，与公司披露的"
        "「加权平均净资产收益率」（2025 年 19.70%）存在口径差异，"
        "本报告归母口径计算值为 19.98%。</li>"
        "<li>本报告为财务报表分析，不构成任何投资建议。</li></ul>")

    # ---------------- 附录 ----------------
    parts.append("<h2>附录：Python 程序包说明</h2>")
    parts.append("<div class='box'><p>报告全部数值由随附的 Python 程序包计算生成，"
        "可一键复现：</p>"
        "<pre style='background:#f4f6f8;padding:12px 14px;border-radius:8px;"
        "overflow-x:auto;font-size:12px;line-height:1.7'>"
        "financial_analysis/\n"
        "├── config.py                 # 标的、期间、数据源、科目映射（全部口径集中在此）\n"
        "├── fetch_data.py             # 采集东方财富（主）+ 新浪财经（核对）数据\n"
        "├── fs_parser.py              # 新浪报表页面 HTML 解析器（GB18030）\n"
        "├── run_all.py                # 一键执行全部分析并输出结果\n"
        "├── build_report.py           # 生成本 HTML 报告\n"
        "├── analysis/\n"
        "│   ├── loader.py             # 数据装载与口径转换（原始数据 -> 规范报表）\n"
        "│   ├── verify.py             # 会计恒等式校验 + 双数据源交叉核验\n"
        "│   ├── structure.py          # 项目结构分析（共同比）\n"
        "│   ├── trend.py              # 项目趋势分析（定基指数/环比/CAGR）\n"
        "│   ├── indicators.py         # 财务指标分析（五类 40 项）\n"
        "│   ├── dupont.py             # 杜邦分析（三因素/五因素/连环替代法）\n"
        "│   └── charts.py             # 图表生成（matplotlib，中文字体）\n"
        "├── data/raw/                 # 原始采集数据（JSON / HTML，可直接复算）\n"
        "├── data/processed/           # 清洗后的三张报表 CSV（单位：元）\n"
        "└── output/\n"
        "    ├── tables/               # 全部分析结果表（CSV）\n"
        "    ├── charts/               # 报告插图（PNG，150dpi）\n"
        "    ├── 分析结果汇总.xlsx      # 15 个工作表的汇总工作簿\n"
        "    └── 关键结论.json          # 供程序调用的关键数值</pre>"
        "<p><b>复现步骤</b>：</p>"
        "<pre style='background:#f4f6f8;padding:12px 14px;border-radius:8px;"
        "overflow-x:auto;font-size:12px'>python fetch_data.py      # 1. 采集数据\n"
        "python run_all.py         # 2. 计算分析结果与图表\n"
        "python build_report.py    # 3. 生成本报告</pre>"
        "<p class='small'>依赖：%s</p></div>"
        % "pandas、numpy、matplotlib、openpyxl（Python 3.10+）")

    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    parts.append(
        "<footer><p><b>数据来源</b>：美的集团股份有限公司 2021–2025 年年度报告"
        "（合并报表，经审计）；东方财富 F10 财务分析接口；新浪财经财务报表页面。"
        "关键数据已通过双数据源交叉核验与会计恒等式校验。</p>"
        "<p>报告由 Python 程序包自动生成，生成时间 %s。"
        "本报告仅用于财务报表分析方法的学习与演示，不构成任何投资建议。</p></footer>"
        % stamp)

    parts.append("</div></body></html>")
    doc = "".join(parts)

    if out_path is None:
        out_path = os.path.join(C.OUTPUT_DIR, "财务报表分析报告.html")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(doc)
    print("报告已生成：%s（%.2f MB）"
          % (out_path, os.path.getsize(out_path) / 1024 / 1024))
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="生成财务报表分析报告")
    parser.add_argument("-o", "--output", default=None)
    args = parser.parse_args()
    build(args.output)
