# -*- coding: utf-8 -*-
"""
report_generator.py — 项目评价报告生成
====================================================================
本模块把全流程计算结果渲染为可交付的报告文件，支持两种格式：

* **Markdown（.md）** —— 轻量、可版本管理、便于直接粘贴进作业平台；
* **Word（.docx）**   —— 通过 ``python-docx`` 生成，含目录结构、
  标题层级、数据表格与插图，可直接打印或提交。

报告结构（两种格式一致）
------------------------------------------------------------------
1. 报告封面信息与核心摘要
2. 评价方法与判据说明（含公式）
3. 各测试案例详解
   - 3.1 项目基础数据
   - 3.2 全指标评价结果
   - 3.3 互斥项目优选结论（如适用）
   - 3.4 资本限额组合优化（如适用）
   - 3.5 敏感性分析（含 tornado 图与临界值）
   - 3.6 AI 决策建议
4. 总体结论
5. 附录：数据生成依据 / 依赖清单 / 复现方式
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from .ai_advisor import DecisionAdvice
from .config import REPORT_DIR
from .models import Evaluation
from .optimizer import MutualGroupResult, OptimizationReport
from .sensitivity import SensitivityResult

__all__ = ["CaseReport", "ReportBundle", "markdown_table",
           "render_markdown", "render_docx", "export_report"]

# Word 文档使用的中文字体
_CN_FONT = "Microsoft YaHei"


# ======================================================================
# 一、报告数据结构
# ======================================================================
@dataclass
class CaseReport:
    """单个案例的报告内容。

    Attributes
    ----------
    key : str
        案例编号。
    name : str
        案例名称。
    teaching_point : str
        对应知识点。
    rate : float
        基准折现率。
    budget : float or None
        资本限额。
    evaluations : list of Evaluation
        全部项目的评价结果。
    mutual_results : list of MutualGroupResult
        互斥组优选结果。
    portfolio : OptimizationReport or None
        资本限额组合优化结果。
    sensitivity_results : list of SensitivityResult
        敏感性分析结果。
    advices : list of DecisionAdvice
        决策建议。
    figures : list of Path
        本案例关联的图片文件。
    cash_flow_table : list of dict
        项目现金流明细表。
    rate_sensitivity_table : list of dict
        折现率敏感性明细（可选）。
    skipped : list of dict
        因数据异常被跳过的项目，每项形如
        ``{"项目编号": ..., "项目名称": ..., "异常原因": ...}``（可选）。
    """

    key: str
    name: str
    teaching_point: str
    rate: float
    budget: Optional[float]
    evaluations: List[Evaluation] = field(default_factory=list)
    mutual_results: List[MutualGroupResult] = field(default_factory=list)
    portfolio: Optional[OptimizationReport] = None
    sensitivity_results: List[SensitivityResult] = field(default_factory=list)
    advices: List[DecisionAdvice] = field(default_factory=list)
    figures: List[Path] = field(default_factory=list)
    cash_flow_table: List[Dict] = field(default_factory=list)
    rate_sensitivity_table: List[Dict] = field(default_factory=list)
    skipped: List[Dict] = field(default_factory=list)


@dataclass
class ReportBundle:
    """完整报告数据包。

    Attributes
    ----------
    title : str
        报告标题。
    subtitle : str
        副标题。
    rate : float
        全局基准折现率。
    cases : list of CaseReport
        各案例报告。
    summary : str
        总体结论文字（Markdown）。
    method_notes : list of str
        方法论说明条目。
    appendix : list of str
        附录条目。
    generated_at : str
        生成时间。
    """

    title: str
    subtitle: str
    rate: float
    cases: List[CaseReport] = field(default_factory=list)
    summary: str = ""
    method_notes: List[str] = field(default_factory=list)
    appendix: List[str] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )


# ======================================================================
# 二、Markdown 工具
# ======================================================================
def markdown_table(rows: Sequence[Dict], headers: Optional[Sequence[str]] = None,
                   align_right: bool = True) -> str:
    """把字典列表渲染为 Markdown 表格。

    Parameters
    ----------
    rows : Sequence[dict]
        每行一个字典，键为列名。
    headers : Sequence[str] or None
        指定列顺序。None 时使用首行的键顺序。
    align_right : bool
        数值列是否右对齐（默认右对齐，便于阅读）。

    Returns
    -------
    str
        Markdown 表格字符串；``rows`` 为空时返回提示文字。

    Notes
    -----
    单元格内的 ``|`` 会被转义为 ``\\|``，避免破坏表格结构。
    """
    if not rows:
        return "_（无数据）_"
    cols = list(headers) if headers else list(rows[0].keys())
    lines = [
        "| " + " | ".join(str(c) for c in cols) + " |",
        "|" + "|".join(":---:" for _ in cols) + "|",
    ]
    for row in rows:
        cells = []
        for c in cols:
            value = row.get(c, "")
            text = str(value).replace("|", "\\|").replace("\n", " ")
            cells.append(text)
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _fmt(value: Optional[float], digits: int = 2, suffix: str = "") -> str:
    """安全格式化数字，None 显示为 ``-``。"""
    if value is None:
        return "-"
    return f"{value:,.{digits}f}{suffix}"


def _rel_image(fig_path: Path, report_path: Path) -> str:
    """计算图片相对 **报告文件自身** 的路径（统一正斜杠，跨平台）。

    Parameters
    ----------
    fig_path : Path
        图片文件的绝对路径。
    report_path : Path
        报告文件的绝对路径（尚未写入也可以）。

    Returns
    -------
    str
        可直接写入 Markdown 图片语法的相对路径，如 ``../figures/01_xxx.png``。

    Notes
    -----
    基准取 **报告所在目录** 而非程序包根目录，因此报告无论输出到
    ``outputs/reports/``、``docs/`` 还是临时目录，图片链接都成立。
    早期版本用 ``REPORT_DIR.parent.parent`` 作基准，导致报告写在
    ``outputs/reports/`` 时链接整体多出一层 ``outputs/``（39 处全部断链）。
    """
    try:
        rel = os.path.relpath(Path(fig_path), start=Path(report_path).parent)
    except ValueError:          # 不同驱动器（Windows 跨盘）时无法求相对路径
        return Path(fig_path).as_posix()
    return Path(rel).as_posix()


# ======================================================================
# 三、Markdown 渲染
# ======================================================================
def _case_markdown(case: CaseReport, index: int, report_path: Path) -> str:
    """渲染单个案例的 Markdown 小节。

    Parameters
    ----------
    case : CaseReport
        案例报告数据。
    index : int
        案例序号（从 1 开始）。
    report_path : Path
        报告文件的最终路径，用于计算插图相对链接（见 :func:`_rel_image`）。
    """
    parts: List[str] = []
    parts.append(f"## {index}. 案例 {case.key}：{case.name}")
    parts.append("")
    parts.append(f"**对应知识点**：{case.teaching_point}")
    parts.append("")
    info = [f"基准折现率：**{case.rate:.2%}**"]
    if case.budget is not None:
        info.append(f"资本限额：**{case.budget:,.0f} 万元**")
    info.append(f"项目数量：**{len(case.evaluations)} 个**")
    parts.append("｜".join(info))
    parts.append("")

    if case.skipped:
        detail = "；".join(
            f"{s['项目编号']}（{s['异常原因']}）" for s in case.skipped
        )
        parts.append(
            f"> ⚠️ **数据异常、已跳过评价的项目（{len(case.skipped)} 个）**：{detail}。"
            f"其余 {len(case.evaluations)} 个项目评价结果不受影响。"
        )
        parts.append("")

    # ---------- 3.1 项目基础数据 ----------
    parts.append("### 项目基础数据")
    parts.append("")
    base_rows = []
    for p in [e.project for e in case.evaluations]:
        base_rows.append({
            "项目编号": p.code,
            "项目名称": p.name,
            "所属行业": p.industry,
            "初始投资(万元)": f"{p.initial_investment:,.2f}",
            "寿命(年)": p.life,
            "风险等级": p.risk_level,
            "互斥组": p.mutual_group or "-",
            "现金流符号变化次数": p.has_unconventional_sign_changes,
        })
    parts.append(markdown_table(base_rows))
    parts.append("")

    if case.cash_flow_table:
        parts.append("**各期净现金流明细（万元）**")
        parts.append("")
        parts.append(markdown_table(case.cash_flow_table))
        parts.append("")

    # ---------- 3.2 评价结果 ----------
    parts.append("### 全指标评价结果")
    parts.append("")
    eval_rows = [e.to_dict() for e in case.evaluations]
    parts.append(markdown_table(eval_rows))
    parts.append("")

    # ---------- 3.3 互斥优选 ----------
    if case.mutual_results:
        parts.append("### 互斥项目优选")
        parts.append("")
        for mr in case.mutual_results:
            parts.append(f"#### 互斥组「{mr.group}」")
            parts.append("")
            rows = [{
                "方案": e.project.code,
                "方案名称": e.project.name,
                "投资(万元)": f"{e.project.initial_investment:,.2f}",
                "寿命(年)": e.project.life,
                "NPV(万元)": f"{e.npv:,.2f}",
                "年金净流量(万元/年)": f"{e.ancf:,.2f}",
                "IRR": f"{e.irr:.2%}" if e.irr is not None else "无实根",
            } for e in mr.evaluations]
            parts.append(markdown_table(rows))
            parts.append("")
            parts.append(f"**决策建议**：{mr.recommendation}")
            parts.append("")
            if mr.incremental:
                parts.append("**增量 IRR 分析**")
                parts.append("")
                parts.append(markdown_table([mr.incremental]))
                parts.append("")

    # ---------- 3.4 资本限额组合优化 ----------
    if case.portfolio is not None:
        parts.append("### 资本限额下的项目组合优化")
        parts.append("")
        rows = [case.portfolio.results[k].to_dict() for k in case.portfolio.results]
        parts.append(markdown_table(rows))
        parts.append("")
        best = case.portfolio.best
        parts.append(
            f"**最优组合**：{' + '.join(e.project.code for e in best.selected)}"
            f"（合计投资 {best.total_investment:,.2f} 万元，"
            f"组合 NPV {best.total_npv:,.2f} 万元，"
            f"额度使用率 {best.utilization:.2%}）"
        )
        parts.append("")
        parts.append("**方法对比分析**")
        parts.append("")
        parts.append(case.portfolio.comparison)
        parts.append("")

    # ---------- 3.5 敏感性分析 ----------
    if case.sensitivity_results:
        parts.append("### 敏感性分析")
        parts.append("")
        for sens in case.sensitivity_results:
            p = sens.project
            irr_text = f"{sens.base_irr:.2%}" if sens.base_irr is not None else "无实根"
            parts.append(f"#### {p.code}（{p.name}）")
            parts.append("")
            parts.append(
                f"基准 NPV **{sens.base_npv:,.2f} 万元**｜IRR **{irr_text}**｜"
                f"安全边际 **{sens.safety_margin * 100:+.2f} 个百分点**｜"
                f"抗风险等级「**{sens.grade}**」"
            )
            parts.append("")
            rows = []
            for f in sens.factors:
                rows.append({
                    "影响因素": f.name,
                    "不利变动": f.adverse_label,
                    "不利变动后NPV(万元)": f"{f.adverse_npv:,.2f}",
                    "有利变动": f.favorable_label,
                    "有利变动后NPV(万元)": f"{f.favorable_npv:,.2f}",
                    "NPV波动幅度(万元)": f"{f.swing:,.2f}",
                    "是否击穿临界点": "⚠️ 是（NPV 转负）" if f.critical else "否",
                })
            parts.append(markdown_table(rows))
            parts.append("")
            be = sens.breakeven
            if be:
                parts.append("**临界点分析（NPV = 0 的临界条件）**")
                parts.append("")
                be_rows = [
                    {"临界项": "临界折现率（= IRR）",
                     "数值": be.get("关键临界值", {}).get("折现率最大可上升幅度(pp)", "") and
                             f"{sens.base_irr:.2%}" if sens.base_irr is not None else "-",
                     "含义": "折现率超过该值后项目由可行转为不可行"},
                    {"临界项": "初始投资上限",
                     "数值": f"可上升 {be.get('关键临界值', {}).get('初始投资最大可上升幅度', 0):.2%}",
                     "含义": "投资超支超过该幅度后 NPV 转负"},
                    {"临界项": "年现金流下限",
                     "数值": f"可下降 {be.get('关键临界值', {}).get('年现金流最大可下降幅度', 0):.2%}",
                     "含义": "现金流下滑超过该幅度后 NPV 转负"},
                ]
                parts.append(markdown_table(be_rows))
                parts.append("")

        if case.rate_sensitivity_table:
            parts.append("**折现率敏感性明细（以首个项目为例）**")
            parts.append("")
            parts.append(markdown_table(case.rate_sensitivity_table))
            parts.append("")

    # ---------- 3.6 AI 决策建议 ----------
    if case.advices:
        parts.append("### AI 辅助决策建议")
        parts.append("")
        for a in case.advices:
            parts.append(a.to_markdown())
            parts.append("")

    # ---------- 图表 ----------
    if case.figures:
        parts.append("### 案例图表")
        parts.append("")
        for fig_path in case.figures:
            parts.append(f"![{fig_path.stem}]({_rel_image(fig_path, report_path)})")
            parts.append("")

    return "\n".join(parts)


def render_markdown(bundle: ReportBundle, output_path: Optional[Path] = None) -> Path:
    """渲染完整 Markdown 报告。

    Parameters
    ----------
    bundle : ReportBundle
        报告数据包。
    output_path : Path or None
        输出路径。None 时使用 ``outputs/reports/<标题>.md``。

    Returns
    -------
    pathlib.Path
        生成的文件路径。

    Notes
    -----
    插图链接以 **报告文件自身所在目录** 为基准计算（见 :func:`_rel_image`），
    因此报告输出到 ``outputs/reports/`` 或 ``docs/`` 等任意位置时链接均可达。
    """
    path = output_path or (REPORT_DIR / f"{bundle.title}.md")
    lines: List[str] = []
    lines.append(f"# {bundle.title}")
    lines.append("")
    lines.append(f"**{bundle.subtitle}**")
    lines.append("")
    lines.append(f"> 报告生成时间：{bundle.generated_at}　｜　基准折现率：{bundle.rate:.2%}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ---------- 总体结论 ----------
    lines.append("## 一、总体结论")
    lines.append("")
    lines.append(bundle.summary)
    lines.append("")

    # ---------- 方法论 ----------
    if bundle.method_notes:
        lines.append("## 二、评价方法与判据说明")
        lines.append("")
        for note in bundle.method_notes:
            lines.append(note)
            lines.append("")

    # ---------- 案例 ----------
    lines.append("## 三、测试案例详解")
    lines.append("")
    for idx, case in enumerate(bundle.cases, start=1):
        lines.append(_case_markdown(case, idx, path))
        lines.append("")
        lines.append("---")
        lines.append("")

    # ---------- 附录 ----------
    if bundle.appendix:
        lines.append("## 四、附录")
        lines.append("")
        for item in bundle.appendix:
            lines.append(item)
            lines.append("")

    content = "\n".join(lines)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ======================================================================
# 四、Word 渲染（python-docx）
# ======================================================================
def _set_run_font(run, size: float = 10.5, bold: bool = False,
                  color: Optional[RGBColor] = None, font: str = _CN_FONT) -> None:
    """设置 run 的中西文字体（中文需单独设置 eastAsia）。"""
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = rpr.makeelement(qn("w:rFonts"), {})
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), font)
    rfonts.set(qn("w:ascii"), font)
    rfonts.set(qn("w:hAnsi"), font)


def _add_paragraph(doc, text: str, size: float = 10.5, bold: bool = False,
                   align=None, color: Optional[RGBColor] = None,
                   space_after: float = 6.0):
    """添加一个带中文字体设置的段落。"""
    para = doc.add_paragraph()
    if align is not None:
        para.alignment = align
    para.paragraph_format.space_after = Pt(space_after)
    para.paragraph_format.line_spacing = 1.35
    run = para.add_run(text)
    _set_run_font(run, size=size, bold=bold, color=color)
    return para


def _add_heading(doc, text: str, level: int = 1):
    """添加标题（使用自定义中文字体，避免默认样式渲染异常）。"""
    heading = doc.add_heading(level=level)
    run = heading.add_run(text)
    size = {1: 16.0, 2: 14.0, 3: 12.5, 4: 11.5}.get(level, 11.0)
    _set_run_font(run, size=size, bold=True,
                  color=RGBColor(0x1F, 0x3A, 0x5F) if level <= 2 else RGBColor(0x2C, 0x3E, 0x50))
    return heading


def _add_table(doc, rows: Sequence[Dict], headers: Optional[Sequence[str]] = None,
               font_size: float = 8.5):
    """向 Word 文档添加数据表格。

    Parameters
    ----------
    doc : docx.Document
        文档对象。
    rows : Sequence[dict]
        数据行。
    headers : Sequence[str] or None
        列顺序。
    font_size : float
        正文字号（列多时自动缩小）。
    """
    if not rows:
        _add_paragraph(doc, "（无数据）", size=9)
        return
    cols = list(headers) if headers else list(rows[0].keys())
    # 列数多时适当缩小字号，保证表格能放进页面宽度
    actual_size = font_size if len(cols) <= 8 else max(6.5, font_size - 1.2)

    table = doc.add_table(rows=1, cols=len(cols))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    # 表头
    header_cells = table.rows[0].cells
    for i, col in enumerate(cols):
        header_cells[i].text = ""
        para = header_cells[i].paragraphs[0]
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = para.add_run(str(col))
        _set_run_font(run, size=actual_size, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))
        # 表头底色
        shading = header_cells[i]._tc.get_or_add_tcPr().makeelement(
            qn("w:shd"), {qn("w:val"): "clear", qn("w:color"): "auto",
                          qn("w:fill"): "2E5C8A"})
        header_cells[i]._tc.get_or_add_tcPr().append(shading)

    # 数据行
    for row_data in rows:
        cells = table.add_row().cells
        for i, col in enumerate(cols):
            value = row_data.get(col, "")
            cells[i].text = ""
            para = cells[i].paragraphs[0]
            para.paragraph_format.space_after = Pt(1)
            run = para.add_run(str(value).replace("**", ""))
            _set_run_font(run, size=actual_size)
    doc.add_paragraph()


def _add_figure(doc, image_path: Path, width_cm: float = 15.5, caption: str = "") -> None:
    """插入居中图片并附图注。"""
    if not image_path.exists():
        _add_paragraph(doc, f"（图片缺失：{image_path.name}）", size=9)
        return
    doc.add_picture(str(image_path), width=Cm(width_cm))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    if caption:
        _add_paragraph(doc, caption, size=9, align=WD_ALIGN_PARAGRAPH.CENTER,
                       color=RGBColor(0x60, 0x6A, 0x74))


def render_docx(bundle: ReportBundle, output_path: Optional[Path] = None) -> Path:
    """渲染完整 Word 报告（含表格与插图）。

    Parameters
    ----------
    bundle : ReportBundle
        报告数据包。
    output_path : Path or None
        输出路径。None 时使用 ``outputs/reports/<标题>.docx``。

    Returns
    -------
    pathlib.Path
        生成的 .docx 文件路径。
    """
    doc = Document()

    # 页面设置：A4 + 合理页边距
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(2.4)
    section.right_margin = Cm(2.4)
    section.top_margin = Cm(2.2)
    section.bottom_margin = Cm(2.2)

    # ---------- 封面 ----------
    _add_paragraph(doc, bundle.title, size=20, bold=True,
                   align=WD_ALIGN_PARAGRAPH.CENTER, space_after=10)
    _add_paragraph(doc, bundle.subtitle, size=12,
                   align=WD_ALIGN_PARAGRAPH.CENTER, space_after=18)
    _add_paragraph(doc,
                   f"报告生成时间：{bundle.generated_at}　｜　基准折现率：{bundle.rate:.2%}",
                   size=10, align=WD_ALIGN_PARAGRAPH.CENTER,
                   color=RGBColor(0x60, 0x6A, 0x74), space_after=18)

    # ---------- 一、总体结论 ----------
    _add_heading(doc, "一、总体结论", level=1)
    for para_text in bundle.summary.split("\n\n"):
        _add_paragraph(doc, para_text.replace("**", ""))

    # ---------- 二、方法论 ----------
    if bundle.method_notes:
        _add_heading(doc, "二、评价方法与判据说明", level=1)
        for note in bundle.method_notes:
            for line in note.split("\n"):
                _add_paragraph(doc, line.replace("**", "").replace("`", ""))

    # ---------- 三、案例详解 ----------
    _add_heading(doc, "三、测试案例详解", level=1)
    for idx, case in enumerate(bundle.cases, start=1):
        _add_heading(doc, f"{idx}. 案例 {case.key}：{case.name}", level=2)
        _add_paragraph(doc, f"对应知识点：{case.teaching_point}", size=10,
                       color=RGBColor(0x44, 0x44, 0x44))
        info = [f"基准折现率 {case.rate:.2%}"]
        if case.budget is not None:
            info.append(f"资本限额 {case.budget:,.0f} 万元")
        info.append(f"项目数量 {len(case.evaluations)} 个")
        _add_paragraph(doc, "｜".join(info), size=10,
                       color=RGBColor(0x44, 0x44, 0x44))

        if case.skipped:
            detail = "；".join(
                f"{s['项目编号']}（{s['异常原因']}）" for s in case.skipped
            )
            _add_paragraph(
                doc,
                f"⚠️ 数据异常、已跳过评价的项目（{len(case.skipped)} 个）：{detail}。"
                f"其余 {len(case.evaluations)} 个项目评价结果不受影响。",
                size=9.5, color=RGBColor(0xB0, 0x3A, 0x2B),
            )

        # 项目基础数据
        _add_heading(doc, "项目基础数据", level=3)
        base_rows = [{
            "项目编号": p.code, "项目名称": p.name, "所属行业": p.industry,
            "初始投资(万元)": f"{p.initial_investment:,.2f}",
            "寿命(年)": p.life, "风险等级": p.risk_level,
            "互斥组": p.mutual_group or "-",
            "符号变化": p.has_unconventional_sign_changes,
        } for p in [e.project for e in case.evaluations]]
        _add_table(doc, base_rows)

        if case.cash_flow_table:
            _add_paragraph(doc, "各期净现金流明细（万元）", size=10, bold=True)
            _add_table(doc, case.cash_flow_table)

        # 评价结果
        _add_heading(doc, "全指标评价结果", level=3)
        _add_table(doc, [e.to_dict() for e in case.evaluations])

        # 互斥优选
        if case.mutual_results:
            _add_heading(doc, "互斥项目优选", level=3)
            for mr in case.mutual_results:
                _add_paragraph(doc, f"互斥组「{mr.group}」", size=11, bold=True)
                rows = [{
                    "方案": e.project.code, "方案名称": e.project.name,
                    "投资(万元)": f"{e.project.initial_investment:,.2f}",
                    "寿命(年)": e.project.life,
                    "NPV(万元)": f"{e.npv:,.2f}",
                    "年金净流量(万元/年)": f"{e.ancf:,.2f}",
                    "IRR": f"{e.irr:.2%}" if e.irr is not None else "无实根",
                } for e in mr.evaluations]
                _add_table(doc, rows)
                _add_paragraph(doc, f"决策建议：{mr.recommendation.replace('**', '')}")
                if mr.incremental:
                    _add_paragraph(doc, "增量 IRR 分析", size=10, bold=True)
                    _add_table(doc, [mr.incremental])

        # 资本限额组合
        if case.portfolio is not None:
            _add_heading(doc, "资本限额下的项目组合优化", level=3)
            _add_table(doc, [case.portfolio.results[k].to_dict()
                             for k in case.portfolio.results])
            best = case.portfolio.best
            _add_paragraph(
                doc,
                f"最优组合：{' + '.join(e.project.code for e in best.selected)}"
                f"（合计投资 {best.total_investment:,.2f} 万元，"
                f"组合 NPV {best.total_npv:,.2f} 万元，"
                f"额度使用率 {best.utilization:.2%}）",
                bold=True,
            )
            for line in case.portfolio.comparison.split("\n"):
                if line.strip():
                    _add_paragraph(doc, line.replace("**", ""))

        # 敏感性分析
        if case.sensitivity_results:
            _add_heading(doc, "敏感性分析", level=3)
            for sens in case.sensitivity_results:
                p = sens.project
                irr_text = f"{sens.base_irr:.2%}" if sens.base_irr is not None else "无实根"
                _add_paragraph(doc, f"{p.code}（{p.name}）", size=11, bold=True)
                _add_paragraph(
                    doc,
                    f"基准 NPV {sens.base_npv:,.2f} 万元｜IRR {irr_text}｜"
                    f"安全边际 {sens.safety_margin * 100:+.2f} 个百分点｜"
                    f"抗风险等级「{sens.grade}」",
                )
                rows = [{
                    "影响因素": f.name,
                    "不利变动": f.adverse_label,
                    "不利变动后NPV(万元)": f"{f.adverse_npv:,.2f}",
                    "有利变动": f.favorable_label,
                    "有利变动后NPV(万元)": f"{f.favorable_npv:,.2f}",
                    "NPV波动幅度(万元)": f"{f.swing:,.2f}",
                    "击穿临界点": "是" if f.critical else "否",
                } for f in sens.factors]
                _add_table(doc, rows)
            if case.rate_sensitivity_table:
                _add_paragraph(doc, "折现率敏感性明细（以首个项目为例）", size=10, bold=True)
                _add_table(doc, case.rate_sensitivity_table)

        # AI 决策建议
        if case.advices:
            _add_heading(doc, "AI 辅助决策建议", level=3)
            for a in case.advices:
                _add_paragraph(doc, f"{a.code}｜{a.name}", size=11, bold=True)
                _add_paragraph(
                    doc,
                    f"结论：{a.verdict}（风险评分 {a.risk_score}/100，文案通道：{a.generated_by}）",
                    bold=True,
                )
                _add_paragraph(doc, a.headline)
                _add_paragraph(doc, "决策依据：", size=10, bold=True)
                for r in a.reasons:
                    _add_paragraph(doc, f"· {r.replace('**', '')}", size=10)
                if a.risks:
                    _add_paragraph(doc, "风险点提示：", size=10, bold=True)
                    for r in a.risks:
                        _add_paragraph(doc, f"· {r.replace('**', '')}", size=10)
                if a.actions:
                    _add_paragraph(doc, "建议动作：", size=10, bold=True)
                    for r in a.actions:
                        _add_paragraph(doc, f"· {r.replace('**', '')}", size=10)

        # 图表
        if case.figures:
            _add_heading(doc, "案例图表", level=3)
            for fig_path in case.figures:
                _add_figure(doc, fig_path, caption=fig_path.stem.replace("_", " "))

    # ---------- 四、附录 ----------
    if bundle.appendix:
        _add_heading(doc, "四、附录", level=1)
        for item in bundle.appendix:
            for line in item.split("\n"):
                _add_paragraph(doc, line.replace("**", "").replace("`", ""))

    path = output_path or (REPORT_DIR / f"{bundle.title}.docx")
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    return path


# ======================================================================
# 五、统一出口
# ======================================================================
def export_report(bundle: ReportBundle, basename: Optional[str] = None) -> Dict[str, Path]:
    """同时导出 Markdown 与 Word 两种格式的报告。

    Parameters
    ----------
    bundle : ReportBundle
        报告数据包。
    basename : str or None
        输出文件名（不含扩展名）。None 时使用报告标题。

    Returns
    -------
    dict
        ``{"markdown": Path, "docx": Path}``。
    """
    name = basename or bundle.title
    md_path = render_markdown(bundle, REPORT_DIR / f"{name}.md")
    docx_path = render_docx(bundle, REPORT_DIR / f"{name}.docx")
    return {"markdown": md_path, "docx": docx_path}
