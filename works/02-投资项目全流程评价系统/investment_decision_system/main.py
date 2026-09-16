# -*- coding: utf-8 -*-
"""
main.py — 投资项目决策自动化评价系统（主程序）
====================================================================
一键完成「数据生成 → 指标计算 → 项目优选 → 资本分配 → 敏感性分析
→ 决策建议 → 图表输出 → 报告导出」的完整流程。

用法
----
::

    # 运行全部 6 个测试案例（默认）
    python main.py

    # 指定折现率为 8%
    python main.py --rate 0.08

    # 只运行指定案例
    python main.py --case CASE-3

    # 列出全部案例
    python main.py --list

    # 不生成 Word 报告（只出 Markdown 与图表）
    python main.py --no-docx

输出
----
::

    outputs/
    ├── data/       projects.csv、evaluations.csv
    ├── figures/    全部图表 PNG
    └── reports/    Markdown 报告 + Word 报告

命令行参数
----------
``--rate``      基准折现率，默认 0.10
``--case``      仅运行指定案例（可重复指定），默认全部
``--list``      列出全部案例后退出
``--no-docx``   跳过 Word 导出
``--ai-mode``   决策文案通道：rule / auto / llm，默认 auto
``--list``      列出案例清单
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import pandas as pd

# 兼容「python main.py」直接运行与「python -m investment_decision_system.main」
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from src import ai_advisor, scenarios, visualizer
    from src.ai_advisor import generate_batch_advice, summarize_advice
    from src.ai_data_generator import profiles_to_table
    from src.config import DATA_DIR, DEFAULT_RATE, FIGURE_DIR, REPORT_DIR
    from src.models import Evaluation
    from src.optimizer import optimize_portfolio, select_mutually_exclusive
    from src.report_generator import (
        CaseReport,
        ReportBundle,
        export_report,
        markdown_table,
    )
    from src.sensitivity import (
        one_way_sensitivity,
        rate_sensitivity_table,
        two_way_sensitivity,
    )
else:
    from . import ai_advisor, scenarios, visualizer
    from .ai_advisor import generate_batch_advice, summarize_advice
    from .ai_data_generator import profiles_to_table
    from .config import DATA_DIR, DEFAULT_RATE, FIGURE_DIR, REPORT_DIR
    from .models import Evaluation
    from .optimizer import optimize_portfolio, select_mutually_exclusive
    from .report_generator import CaseReport, ReportBundle, export_report, markdown_table
    from .sensitivity import (
        one_way_sensitivity,
        rate_sensitivity_table,
        two_way_sensitivity,
    )


# ======================================================================
# 一、工具函数
# ======================================================================
def _cash_flow_table(projects: Sequence) -> List[Dict]:
    """把项目的各期现金流展开为"行=项目、列=年份"的表格。

    Parameters
    ----------
    projects : Sequence[Project]
        项目列表。

    Returns
    -------
    list of dict
        适合直接渲染为 Markdown / Word 表格的行数据。
    """
    max_life = max(p.life for p in projects)
    rows = []
    for p in projects:
        row = {
            "项目编号": p.code,
            "初始投资(万元)": f"{p.initial_investment:,.2f}",
        }
        for t in range(1, max_life + 1):
            row[f"第{t}年"] = f"{p.cash_flows[t - 1]:,.2f}" if t <= p.life else "-"
        rows.append(row)
    return rows


def _print_section(title: str) -> None:
    """在控制台打印分节标题。"""
    print("\n" + "=" * 78)
    print(f"  {title}")
    print("=" * 78)


def _print_evaluation_table(evaluations: Sequence[Evaluation]) -> None:
    """在控制台打印评价结果简表。"""
    header = f"{'编号':<8}{'投资(万元)':>12}{'寿命':>5}{'NPV(万元)':>13}{'IRR':>10}{'ANCF':>11}{'PI':>8}{'结论':>8}"
    print(header)
    print("-" * 78)
    for e in evaluations:
        irr_text = f"{e.irr:.2%}" if e.irr is not None else "无实根"
        print(
            f"{e.project.code:<8}{e.project.initial_investment:>12,.0f}"
            f"{e.project.life:>5}{e.npv:>13,.1f}{irr_text:>10}"
            f"{e.ancf:>11,.1f}{e.pi:>8.3f}"
            f"{'可行' if e.feasible else '不可行':>8}"
        )


# ======================================================================
# 二、单案例流程
# ======================================================================
def run_case(scenario: scenarios.Scenario, case_index: int,
             make_advice: bool = True, use_llm: bool = False) -> CaseReport:
    """执行单个测试案例的完整评价流程。

    Parameters
    ----------
    scenario : Scenario
        案例定义。
    case_index : int
        案例序号（从 1 开始），用于图表文件命名。
    make_advice : bool
        是否生成 AI 决策建议。
    use_llm : bool
        决策建议是否尝试走大模型通道。

    Returns
    -------
    CaseReport
        该案例的完整报告数据。
    """
    rate = scenario.discount_rate
    projects = scenario.projects
    _print_section(f"案例 {scenario.key}：{scenario.name}（折现率 {rate:.2%}）")

    # ---------- 1. 全指标评价 ----------
    evaluations = [Evaluation.build(p, rate) for p in projects]
    _print_evaluation_table(evaluations)

    figures: List[Path] = []
    prefix = f"{case_index:02d}"

    # ---------- 2. 互斥项目优选 ----------
    mutual_results = select_mutually_exclusive(projects, rate)
    for mr in mutual_results:
        print(f"\n【互斥组 {mr.group}】{mr.recommendation.replace('**', '')}")
        if mr.incremental:
            print(f"  增量分析：{mr.incremental['判定']}")
        figures.append(visualizer.plot_mutual_group(
            mr, rate, f"{prefix}_{len(figures) + 1:02d}_{scenario.key}_mutual_{mr.group}.png"
        ))

    # ---------- 3. 资本限额组合优化 ----------
    portfolio = None
    if scenario.budget is not None:
        portfolio = optimize_portfolio(projects, rate, scenario.budget)
        print("\n【资本限额组合优化】")
        for key, result in portfolio.results.items():
            print(f"  {key}：入选 {result.codes}｜投资 {result.total_investment:,.0f} 万元｜"
                  f"NPV {result.total_npv:,.1f} 万元｜使用率 {result.utilization:.1%}")
        figures.append(visualizer.plot_portfolio(
            portfolio.results, scenario.budget,
            title=f"案例 {scenario.key}：{scenario.name}",
            filename=f"{prefix}_{len(figures) + 1:02d}_{scenario.key}_portfolio.png",
        ))

    # ---------- 4. 敏感性分析 ----------
    # 项目数过多时（如 CASE-6 的 12 个项目）只对前若干个项目出图，避免图表泛滥；
    # 但表格数据仍覆盖全部项目。
    chart_limit = 3
    sensitivity_results = []
    for idx, ev in enumerate(evaluations):
        sens = one_way_sensitivity(ev.project, rate)
        sensitivity_results.append(sens)
        if idx < chart_limit:
            figures.append(visualizer.plot_tornado(
                sens,
                filename=f"{prefix}_{len(figures) + 1:02d}_{scenario.key}_tornado_{ev.project.code}.png",
            ))

    # 双因素热力图：优先挑"最边缘"的项目（IRR 最接近折现率），教学价值最高
    candidates = [s for s in sensitivity_results if s.base_irr is not None and s.base_npv > 0]
    if candidates and len(projects) <= 4:
        target = min(candidates, key=lambda s: s.safety_margin)
        matrix, rate_axis, cf_axis = two_way_sensitivity(target.project, rate)
        figures.append(visualizer.plot_two_way_heatmap(
            target.project, rate, matrix, rate_axis, cf_axis,
            filename=f"{prefix}_{len(figures) + 1:02d}_{scenario.key}_dual_{target.project.code}.png",
        ))

    # ---------- 5. AI 决策建议 ----------
    advices = []
    if make_advice:
        sens_map = {s.project.code: s for s in sensitivity_results}
        advices = generate_batch_advice(
            evaluations, sens_map, budget=scenario.budget, use_llm=use_llm
        )
        print("\n【AI 决策建议摘要】")
        for a in advices:
            print(f"  {a.code}：{a.verdict}（风险 {a.risk_score}/100）｜{a.headline[:52]}…")
        print()
        print(summarize_advice(advices).replace("**", ""))

    # ---------- 6. 通用图表 ----------
    figures.append(visualizer.plot_npv_comparison(
        evaluations,
        title=f"案例 {scenario.key}：各项目 NPV 对比（折现率 {rate:.2%}）",
        filename=f"{prefix}_{len(figures) + 1:02d}_{scenario.key}_npv_comparison.png",
    ))
    figures.append(visualizer.plot_irr_vs_rate(
        evaluations,
        rate_max=0.45 if scenario.key != "CASE-4" else 0.35,
        title=f"案例 {scenario.key}：NPV 与折现率关系曲线（交点即 IRR）",
        filename=f"{prefix}_{len(figures) + 1:02d}_{scenario.key}_irr_vs_rate.png",
        highlight_rate=rate,
    ))
    if len(projects) <= 6:
        figures.append(visualizer.plot_cash_flows(
            projects,
            title=f"案例 {scenario.key}：各项目现金流结构对比",
            filename=f"{prefix}_{len(figures) + 1:02d}_{scenario.key}_cash_flows.png",
            rate=rate,
        ))

    # ---------- 7. 组装报告数据 ----------
    rate_table = (
        rate_sensitivity_table(sensitivity_results[0].project, rate)
        if sensitivity_results else []
    )
    return CaseReport(
        key=scenario.key,
        name=scenario.name,
        teaching_point=scenario.teaching_point,
        rate=rate,
        budget=scenario.budget,
        evaluations=evaluations,
        mutual_results=mutual_results,
        portfolio=portfolio,
        sensitivity_results=sensitivity_results,
        advices=advices,
        figures=figures,
        cash_flow_table=_cash_flow_table(projects),
        rate_sensitivity_table=rate_table,
    )


# ======================================================================
# 三、方法论与附录文案
# ======================================================================
def _method_notes() -> List[str]:
    """返回报告的方法论说明段落。"""
    return [
        "### 2.1 净现值法（NPV）\n"
        "计算式：`NPV = -I₀ + Σ(t=1..n) CFₜ / (1 + r)ᵗ`\n\n"
        "其中 I₀ 为初始投资，CFₜ 为第 t 期净现金流，r 为折现率（资本成本）。\n"
        "**判据**：NPV > 0 → 项目创造价值，方案可行；NPV ≤ 0 → 方案不可行。\n"
        "独立项目决策中，NPV 是唯一理论上无缺陷的判据，也是互斥项目优选的首选准则。",

        "### 2.2 内含报酬率法（IRR）\n"
        "计算式：求解 r 使 `NPV(r) = 0`，该 r 即为 IRR。\n\n"
        "本系统采用「网格扫描 + Brent 精解」的数值策略：先在 (-99%, 500%] 区间上\n"
        "以 2000 点网格扫描 NPV 的符号变化区间，再对每个变号区间用 Brent 法精确定位，\n"
        "**可同时捕获全部实根**，从而识别多重 IRR 异常情形。\n\n"
        "**判据**：IRR > 资本成本 → 方案可行。\n"
        "**局限**：非常规现金流（多次符号变化）可能导致 IRR 多解甚至无解，\n"
        "此时 IRR 指标失效，必须以 NPV 为准，并辅以 MIRR（修正内部报酬率）。",

        "### 2.3 年金净流量法（ANCF / 等额年金 EAA）\n"
        "计算式：`ANCF = NPV / PVIFA(r, n) = NPV × r / [1 - (1 + r)^(-n)]`\n\n"
        "**用途**：解决 **寿命期不同的互斥项目** 无法直接比较 NPV 的问题。\n"
        "该方法把项目总 NPV 折算为「每年等额创造的价值」，使不同寿命的方案\n"
        "在统一口径下可比。**判据**：ANCF 越大方案越优；ANCF > 0 项目可行。",

        "### 2.4 盈利能力指数与资本限额下的项目分配\n"
        "计算式：`PI = (NPV + I₀) / I₀`，表示单位投资额创造的现值。\n\n"
        "资本限额下求解最优投资组合的三种方法：\n\n"
        "1. **排序法**：按 PI 降序贪心装入。速度快，但隐含「资金可任意分割」假设，\n"
        "   当资本额度不可分割时会因额度碎片化而错过全局最优解；\n"
        "2. **组合法**：DFS 穷举全部可行组合（配合可行性剪枝与最优性剪枝），\n"
        "   **保证全局最优**，是本系统的推荐方法；\n"
        "3. **背包法**：把额度整数化后用 0-1 动态规划求解，复杂度 O(n × Budget)，\n"
        "   适用于项目数很多、穷举不可行的场景，用于交叉验证组合法结果。",

        "### 2.5 投资决策敏感性分析\n"
        "分析折现率、初始投资、年现金流、项目寿命四项因素变动对 NPV 的影响：\n\n"
        "* **单因素敏感性**：折现率按 **绝对百分点 ±5pp** 扰动，初始投资与年现金流\n"
        "  按 **相对比例 ±20%** 扰动，寿命按 ±1 年扰动（不同因素口径不同，需标注清楚）；\n"
        "* **临界点（盈亏平衡）分析**：求解使 NPV = 0 的临界折现率（数值上等于 IRR）、\n"
        "  初始投资上限、年现金流下限，并换算为「可承受的最大不利变动幅度」；\n"
        "* **安全边际**：`安全边际 = IRR − 资本成本`，用于量化抗风险能力；\n"
        "* **双因素联动**：折现率 × 年现金流 二维矩阵，识别可行区与不可行区的分界线。\n\n"
        "**tornado 图（旋风图）** 按各因素引起的 NPV 波动幅度降序排列，\n"
        "条形越长说明该因素越关键；若不利方向的条形越过 NPV = 0 临界线，\n"
        "则该因素一旦不利变动将直接导致项目失效，属 **致命敏感因素**。",

        "### 2.6 AI 辅助功能\n"
        "**（1）AI 生成测试数据**：采用「行业原型约束 + 参数化生成」策略，\n"
        "基于 6 个行业的真实资本投资特征（新能源、半导体、生物医药、消费零售、\n"
        "公用事业、数字软件）构建参数区间，再按 steady / growth / jcurve / cycle\n"
        "四种现金流形态生成项目数据，覆盖不同规模（700~9000 万元）、\n"
        "不同寿命（5~15 年）、不同风险等级。使用固定随机种子，**结果完全可复现**；\n"
        "该策略避免了直接由大模型自由生成数字所导致的数量级失真与不可复现问题。\n\n"
        "**（2）AI 生成决策建议**：采用「规则引擎 + 可选大模型润色」双通道架构。\n"
        "规则引擎基于 8 类风险规则（安全边际、折现率冲击、投资超支容错、\n"
        "现金流下滑容错、回收期占比、多重 IRR、现金流波动率、资本集中度）\n"
        "自动生成带具体数字的结论、风险提示与建议动作，**离线可用、零幻觉、可追溯**；\n"
        "若配置了大模型 API（`IDS_LLM_API_KEY`），则把已算好的结构化指标作为上下文\n"
        "交给模型润色表达，并强制约束「不得修改任何数字」。",

        "### 2.7 技术栈\n"
        "| 组件 | 用途 |\n"
        "| :--- | :--- |\n"
        "| Python 3.13 | 主语言 |\n"
        "| NumPy | 现金流向量化折现计算 |\n"
        "| SciPy | Brent 法求解 IRR 方程实根 |\n"
        "| pandas | 数据表组织与 CSV 导出 |\n"
        "| Matplotlib | 全部图表绘制（含中文字体配置）|\n"
        "| python-docx | Word 报告生成 |\n"
        "| AI（规则引擎 + 可选 LLM）| 数据生成与决策文案生成 |",
    ]


def _appendix() -> List[str]:
    """返回报告附录段落。"""
    profile_rows = profiles_to_table()
    return [
        "### 附录 A　AI 数据生成的行业原型参数表\n\n"
        "下表为 :mod:`src.ai_data_generator` 中 6 个行业的参数区间，"
        "CASE-6 的 12 个项目即由这些原型采样生成（固定随机种子，结果可复现）。\n\n"
        + markdown_table(profile_rows),

        "### 附录 B　程序包目录结构\n\n"
        "```\n"
        "investment_decision_system/\n"
        "├── main.py                      主程序（一键全流程）\n"
        "├── requirements.txt             依赖清单\n"
        "├── README.md                    使用说明\n"
        "├── src/\n"
        "│   ├── __init__.py              包说明与模块导航\n"
        "│   ├── config.py                路径/字体/配色/参数配置\n"
        "│   ├── finance_core.py          NPV、IRR、ANCF、PI、回收期、MIRR、增量IRR\n"
        "│   ├── models.py                Project / Evaluation 数据结构\n"
        "│   ├── ai_data_generator.py     AI 生成多行业多周期现金流数据\n"
        "│   ├── scenarios.py             6 个教学测试案例\n"
        "│   ├── optimizer.py             互斥优选 + 资本限额组合优化\n"
        "│   ├── sensitivity.py           敏感性分析与临界点分析\n"
        "│   ├── ai_advisor.py            AI 决策建议生成\n"
        "│   ├── visualizer.py            图表绘制\n"
        "│   └── report_generator.py      Markdown / Word 报告导出\n"
        "├── tests/\n"
        "│   └── test_all.py              单元测试与案例断言\n"
        "└── outputs/\n"
        "    ├── data/                    数据 CSV\n"
        "    ├── figures/                 图表 PNG\n"
        "    └── reports/                 报告 Markdown / Word\n"
        "```",

        "### 附录 C　环境依赖与复现方式\n\n"
        "```bash\n"
        "# 1. 安装依赖\n"
        "pip install -r requirements.txt\n\n"
        "# 2. 运行全部案例\n"
        "python main.py --rate 0.10\n\n"
        "# 3. 运行单元测试（校验 6 个案例的 30+ 项断言）\n"
        "python -m tests.test_all\n"
        "```\n\n"
        "依赖版本：Python ≥ 3.10、numpy ≥ 1.24、scipy ≥ 1.10、"
        "pandas ≥ 2.0、matplotlib ≥ 3.7、python-docx ≥ 1.1。",
    ]


# ======================================================================
# 四、主流程
# ======================================================================
def build_bundle(case_reports: Sequence[CaseReport], rate: float) -> ReportBundle:
    """把各案例报告组装成完整报告数据包。

    Parameters
    ----------
    case_reports : Sequence[CaseReport]
        各案例的报告数据。
    rate : float
        基准折现率。

    Returns
    -------
    ReportBundle
    """
    # 汇总全部建议，生成全局结论
    all_advices = [a for c in case_reports for a in c.advices]
    summary_parts: List[str] = []

    total_projects = sum(len(c.evaluations) for c in case_reports)
    feasible = sum(1 for c in case_reports for e in c.evaluations if e.feasible)
    summary_parts.append(
        f"本报告以基准折现率 **{rate:.2%}** 对 **{len(case_reports)} 个测试案例**、"
        f"共 **{total_projects} 个投资项目** 完成了 NPV、IRR、年金净流量、盈利能力指数、"
        f"回收期与 MIRR 的全指标自动化评价，其中 **{feasible} 个**项目在基准折现率下可行。"
    )
    if all_advices:
        summary_parts.append(summarize_advice(all_advices))

    # 关键发现
    findings: List[str] = []
    for c in case_reports:
        if c.key == "CASE-2" and c.mutual_results:
            conflicts = [mr.group for mr in c.mutual_results if mr.conflict_npv_irr or mr.conflict_npv_ancf]
            if conflicts:
                findings.append(
                    f"**{c.key}**：成功复现并解决了互斥项目优选中的两组经典冲突"
                    f"（{'、'.join(conflicts)}）——规模冲突组揭示 IRR 法在互斥决策中会给出错误信号，"
                    f"须以 NPV 为准并用增量 IRR 验证；寿命冲突组揭示 NPV 在寿命不等时不可直接比较，"
                    f"须改用年金净流量法。"
                )
        if c.key == "CASE-3" and c.portfolio is not None:
            ranking = c.portfolio.results.get("排序法")
            best = c.portfolio.best
            if ranking is not None and best.total_npv > ranking.total_npv:
                findings.append(
                    f"**{c.key}**：验证了 **排序法（PI 贪心）在资本额度不可分割时失效** —— "
                    f"排序法得到 {ranking.total_npv:,.0f} 万元并留下 {ranking.idle_budget:,.0f} 万元闲置额度，"
                    f"组合法穷举得到全局最优 {best.total_npv:,.0f} 万元"
                    f"（多创造价值 {best.total_npv - ranking.total_npv:,.0f} 万元）。"
                )
        if c.key == "CASE-4":
            multi = [e for e in c.evaluations if not e.irr_result.is_unique]
            if multi:
                detail = "；".join(
                    f"{e.project.code} 存在 {len(e.irr_result.all_roots)} 个 IRR"
                    f"（{'、'.join(f'{r:.2%}' for r in e.irr_result.all_roots)}）"
                    for e in multi
                )
                findings.append(
                    f"**{c.key}**：稳健求解器成功捕获多重 IRR —— {detail}，"
                    f"验证了「非常规现金流下 IRR 失效、必须以 NPV 为准」的结论。"
                )
        if c.key == "CASE-5":
            weak = [e for e in c.evaluations if e.irr is not None and e.irr - rate < 0.02]
            if weak:
                findings.append(
                    f"**{c.key}**：识别出边缘可行项目 "
                    f"{'、'.join(e.project.code for e in weak)} —— "
                    f"其 IRR 仅高于资本成本不足 2 个百分点，"
                    f"折现率上升 5 个百分点后 NPV 即由正转负，抗风险能力弱，"
                    f"建议分期投入并设置折现率红线。"
                )
    if findings:
        summary_parts.append("### 关键发现\n\n" + "\n\n".join(f"- {f}" for f in findings))

    return ReportBundle(
        title="投资项目决策自动化评价系统实验报告",
        subtitle="基于 Python + AI 的多项目批量评估与决策辅助｜第 5 章：NPV、IRR、项目优选、"
                 "资本分配与敏感性分析",
        rate=rate,
        cases=list(case_reports),
        summary="\n\n".join(summary_parts),
        method_notes=_method_notes(),
        appendix=_appendix(),
    )


def export_data(case_reports: Sequence[CaseReport]) -> Dict[str, Path]:
    """把项目数据与评价结果导出为 CSV。

    Parameters
    ----------
    case_reports : Sequence[CaseReport]
        各案例报告数据。

    Returns
    -------
    dict
        ``{"projects": Path, "evaluations": Path}``。
    """
    project_rows: List[Dict] = []
    evaluation_rows: List[Dict] = []
    for c in case_reports:
        for e in c.evaluations:
            row = e.project.to_dict()
            row = {"案例": c.key, **row}
            project_rows.append(row)
            eval_row = e.to_dict()
            eval_row = {"案例": c.key, **eval_row}
            evaluation_rows.append(eval_row)

    projects_path = DATA_DIR / "projects.csv"
    evaluations_path = DATA_DIR / "evaluations.csv"
    pd.DataFrame(project_rows).to_csv(projects_path, index=False, encoding="utf-8-sig")
    pd.DataFrame(evaluation_rows).to_csv(evaluations_path, index=False, encoding="utf-8-sig")
    return {"projects": projects_path, "evaluations": evaluations_path}


def main(argv: Optional[Sequence[str]] = None) -> int:
    """主程序入口。

    Parameters
    ----------
    argv : Sequence[str] or None
        命令行参数（None 时读取 sys.argv）。

    Returns
    -------
    int
        进程退出码，0 表示成功。
    """
    parser = argparse.ArgumentParser(
        description="投资项目决策自动化评价系统（NPV/IRR/互斥优选/资本分配/敏感性分析）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--rate", type=float, default=DEFAULT_RATE,
                        help=f"基准折现率（小数形式），默认 {DEFAULT_RATE}")
    parser.add_argument("--case", action="append", default=None,
                        help="仅运行指定案例，可重复指定，如 --case CASE-3 --case CASE-5")
    parser.add_argument("--list", action="store_true", help="列出全部案例后退出")
    parser.add_argument("--no-docx", action="store_true", help="跳过 Word 报告导出")
    parser.add_argument("--no-advice", action="store_true", help="跳过 AI 决策建议生成")
    parser.add_argument("--ai-mode", choices=["rule", "auto", "llm"], default=None,
                        help="决策文案通道，默认 auto（无 API Key 时自动降级为规则引擎）")
    args = parser.parse_args(argv)

    if args.ai_mode:
        # 通过环境变量控制，保持 config 的单一事实来源
        import os
        os.environ["IDS_AI_MODE"] = args.ai_mode
        ai_advisor.AI_MODE = args.ai_mode

    if args.list:
        print("\n可用测试案例：\n")
        for s in scenarios.all_cases(args.rate):
            budget = f"｜资本限额 {s.budget:,.0f} 万元" if s.budget else ""
            print(f"  {s.key}　{s.name}（{len(s.projects)} 个项目{budget}）")
            print(f"          知识点：{s.teaching_point}")
        return 0

    print("=" * 78)
    print("  投资项目决策自动化评价系统 v1.0")
    print(f"  NPV ｜ IRR ｜ 互斥项目优选 ｜ 资本限额组合优化 ｜ 敏感性分析")
    print(f"  基准折现率：{args.rate:.2%}　｜　AI 决策文案通道：{ai_advisor.AI_MODE}"
          f"{'（大模型可用）' if ai_advisor.LLM_AVAILABLE else '（未配置 API Key，使用规则引擎）'}")
    print("=" * 78)

    # ---------- 选择案例 ----------
    if args.case:
        selected = [scenarios.get_case(k, args.rate) for k in args.case]
    else:
        selected = scenarios.all_cases(args.rate)

    # ---------- 逐案例运行 ----------
    use_llm = (ai_advisor.AI_MODE == "llm")
    case_reports: List[CaseReport] = []
    for idx, scenario in enumerate(selected, start=1):
        report = run_case(scenario, idx, make_advice=not args.no_advice, use_llm=use_llm)
        case_reports.append(report)

    # ---------- 导出数据 ----------
    _print_section("导出数据与报告")
    data_paths = export_data(case_reports)
    for name, path in data_paths.items():
        print(f"  数据文件：{path}")

    # ---------- 组装并导出报告 ----------
    bundle = build_bundle(case_reports, args.rate)
    paths = export_report(bundle, basename="投资项目决策评价报告")
    print(f"  Markdown 报告：{paths['markdown']}")
    if args.no_docx:
        print("  Word 报告：已按参数跳过（--no-docx）")
    else:
        print(f"  Word 报告：{paths['docx']}")
    print(f"  图表目录：{FIGURE_DIR}")

    # ---------- 汇总统计 ----------
    _print_section("运行完成")
    total_figures = len(list(FIGURE_DIR.glob("*.png")))
    print(f"  案例数：{len(case_reports)}")
    print(f"  项目数：{sum(len(c.evaluations) for c in case_reports)}")
    print(f"  图表数：{total_figures}")
    print(f"  报告输出：{REPORT_DIR}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
