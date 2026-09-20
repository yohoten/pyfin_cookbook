# -*- coding: utf-8 -*-
"""manual/make_figs.py —— 绘制手册自绘插图（架构、流程、决策树）。输出到 manual/assets/fig/"""
from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, Polygon

FONT = r"C:\Windows\Fonts\Deng.ttf"
FONT_B = r"C:\Windows\Fonts\simhei.ttf"
font_manager.fontManager.addfont(FONT)
font_manager.fontManager.addfont(FONT_B)
plt.rcParams["font.family"] = "DengXian"
plt.rcParams["axes.unicode_minus"] = False

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fig")
os.makedirs(OUT, exist_ok=True)

BLUE = "#1C4A8C"
LBLUE = "#EAF1FA"
MID = "#4A7EBB"
GRAY = "#5B6470"
LGRAY = "#F2F4F7"
AMBER = "#A9660A"
LAMBER = "#FFF3E0"
GREEN = "#2E7D32"
LGREEN = "#E9F5EA"
RED = "#AE2B2B"
LRED = "#FBEDED"
INK = "#1C1E21"
SCALE = 1.28  # 全局字号放大系数（相对盒子尺寸）


def canvas(w=12.0, h=5.6):
    fig = plt.figure(figsize=(w, h), dpi=200)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    return fig, ax


def box(ax, x, y, w, h, text, fc=LBLUE, ec=BLUE, tc=INK, fs=9.2, bold=False, r=1.6,
        lw=1.0, align="center", va="center", z=3):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                fc=fc, ec=ec, lw=lw, zorder=z, mutation_aspect=1))
    weight = "bold" if bold else "normal"
    fs = fs * SCALE
    if align == "center":
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
                color=tc, zorder=z + 1, fontweight=weight, linespacing=1.45)
    else:
        ax.text(x + 1.2, y + h / 2, text, ha="left", va="center", fontsize=fs, color=tc,
                zorder=z + 1, fontweight=weight, linespacing=1.45)


def label(ax, x, y, text, fs=8.4, color=GRAY, ha="center", va="center", bold=False):
    ax.text(x, y, text, fontsize=fs * SCALE, color=color, ha=ha, va=va, linespacing=1.4,
            fontweight="bold" if bold else "normal")


def arrow(ax, p1, p2, color=BLUE, style="-|>", lw=1.4, rad=0.0, ls="-", z=2):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle=style, mutation_scale=13, lw=lw,
                                 color=color, linestyle=ls, zorder=z,
                                 connectionstyle=f"arc3,rad={rad}"))


def save(fig, name):
    p = os.path.join(OUT, name)
    fig.savefig(p, dpi=200, facecolor="white")
    plt.close(fig)
    print("fig:", name)


# ---------------------------------------------------------------------------
def fig01_map():
    fig, ax = canvas(12.6, 6.4)
    label(ax, 50, 94, "works/ 五个综合实验项目 · 课程章节与交付物地图", fs=13.5,
          color=BLUE, bold=True)
    rows = [
        ("项目一", "货币时间价值与资本成本计算器", "第 3、4 章",
         "复利/年金 · 债务/股权成本 · WACC · 还款计划", "7 图 + 3 表 + GUI", BLUE, LBLUE),
        ("项目二", "投资项目全流程评价系统", "第 5 章",
         "NPV/IRR/ANCF · 互斥优选 · 资本限额 · 敏感性", "39 图 + Word 报告", MID, "#EDF3FA"),
        ("项目三", "综合成本与经营决策分析平台", "第 7、8、9 章",
         "归集分配 · 成本计算 · 差异分析 · 本量利 · 短期决策", "17 图 + 2 份底稿",
         GREEN, LGREEN),
        ("项目四", "财务报表分析报告（美的集团）", "第 10 章",
         "结构 · 趋势 · 40 项指标 · 杜邦分解与归因", "12 图 + 15 表工作簿 + HTML", AMBER, LAMBER),
        ("项目五", "财务预测与预算管理（永鼎股份）", "第 11 章",
         "十年历史分析 · 五模型预测 · 全面预算 · 情景与敏感性", "16 图 + Word 报告",
         "#4A2E86", "#F1EDFA"),
    ]
    y = 78
    for tag, name, chap, what, out, ec, fc in rows:
        box(ax, 3, y, 9, 11, tag, fc=ec, ec=ec, tc="white", fs=10.2, bold=True)
        box(ax, 13, y, 24, 11, name, fc=fc, ec=ec, fs=10.0, bold=True, align="left")
        box(ax, 37.6, y, 8.4, 11, chap, fc="white", ec=GRAY, fs=9.0)
        box(ax, 46.6, y, 30, 11, what, fc="white", ec=ec, fs=7.8, align="left")
        box(ax, 77.2, y, 19.6, 11, out, fc=LGRAY, ec=GRAY, fs=8.0, align="left")
        y -= 14.4
    label(ax, 50, 3.4, "箭头方向即学习顺序：先算清资金的时间价值（项目一）→ 会评单个项目（项目二）→ "
                       "会算成本与短期决策（项目三）→ 会读整张报表（项目四）→ 会做预测与预算（项目五）",
          fs=8.6)
    save(fig, "fig01_项目地图.png")


def fig02_env():
    fig, ax = canvas(12.6, 5.2)
    label(ax, 50, 92, "第一次跑通任意项目：四步法", fs=13.5, color=BLUE, bold=True)
    steps = [
        ("① 装 Python", "官方安装包\n勾选 Add python.exe\nto PATH\n\n验证：python -V\n      pip -V", BLUE, LBLUE),
        ("② 建虚拟环境", "在项目目录内执行\npython -m venv .venv\n\n作用：依赖隔离\n      不污染系统 Python", MID, "#EDF3FA"),
        ("③ 装依赖", "激活后执行\npip install -r\n  requirements.txt\n\n建议加清华镜像", GREEN, LGREEN),
        ("④ 跑主程序", "python main.py\npython run_all.py\n\n产物写入\noutputs/ 或 output/", AMBER, LAMBER),
    ]
    x = 4
    for i, (t, d, ec, fc) in enumerate(steps):
        box(ax, x, 46, 21, 13, t, fc=ec, ec=ec, tc="white", fs=11.4, bold=True)
        box(ax, x, 12, 21, 32, d, fc=fc, ec=ec, fs=9.0)
        if i < 3:
            arrow(ax, (x + 21.6, 52), (x + 24.4, 52), lw=1.8)
        x += 24
    label(ax, 50, 5.0, "四个项目用 main.py，两个项目用 run_all.py；无论哪个入口，"
                       "第 ① ② ③ 步完全相同。", fs=8.8)
    save(fig, "fig02_环境四步.png")


def fig03_venv():
    fig, ax = canvas(12.4, 4.4)
    label(ax, 50, 90, "虚拟环境：创建、激活与提示符变化（Windows PowerShell）", fs=12.6,
          color=BLUE, bold=True)
    box(ax, 3, 26, 27, 42, "", fc=LGRAY, ec=GRAY)
    label(ax, 16.5, 74, "① 创建", fs=9.6, color=INK, bold=True)
    ax.text(4.6, 62, "cd works\\01-…\\financial_calculator\npython -m venv .venv",
            fontsize=10.0, color=INK, va="top", linespacing=1.5)
    ax.text(4.6, 46, ".venv\\\n  Scripts\\python.exe\n  Scripts\\activate\n  Lib\\site-packages\\",
            fontsize=9.6, color=GRAY, va="top", linespacing=1.5)
    box(ax, 33, 26, 27, 42, "", fc=LGRAY, ec=GRAY)
    label(ax, 46.5, 74, "② 激活", fs=9.6, color=INK, bold=True)
    ax.text(34.6, 62, ".venv\\Scripts\\activate", fontsize=10.0, color=INK, va="top", linespacing=1.5)
    ax.text(34.6, 50, "提示符前出现 (.venv)\n\n(.venv) PS ...> python -V\n(.venv) PS ...> pip -V",
            fontsize=9.6, color=GREEN, va="top", linespacing=1.5)
    box(ax, 63, 26, 34, 42, "", fc=LGRAY, ec=GRAY)
    label(ax, 80, 74, "③ 安装并运行", fs=9.6, color=INK, bold=True)
    ax.text(64.6, 62, "pip install -r requirements.txt \\\n    -i https://pypi.tuna.tsinghua.edu.cn/simple\n"
                      "python main.py --demo",
            fontsize=10.0, color=INK, va="top", linespacing=1.5)
    ax.text(64.6, 40, "退出：deactivate\n删除：直接删掉 .venv 目录即可", fontsize=8.0,
            color=GRAY, va="top", linespacing=1.6)
    arrow(ax, (30.4, 47), (32.8, 47), lw=1.6)
    arrow(ax, (60.4, 47), (62.8, 47), lw=1.6)
    label(ax, 50, 12, "同一台机器上五个项目的依赖版本互不干扰；\n"
                      "若跳过 ① ②，pip 会把包装进全局 Python，版本冲突时只能全部重装。", fs=8.6)
    save(fig, "fig03_虚拟环境.png")


def fig04_validation():
    fig, ax = canvas(12.2, 5.4)
    label(ax, 50, 92, "项目一的三层参数校验与三段式报错", fs=13, color=BLUE, bold=True)
    layers = [
        ("L1 类型层", "是否为空 / 能否转成数字（阻断）\n拦截：abc、空回车、1.2.3", BLUE, LBLUE),
        ("L2 边界层", "是否落在硬边界（阻断计算）\n拦截：6% 误输成 6、β=120、税率 2.5", MID, "#EDF3FA"),
        ("L3 合理性层", "数值合法但极端（仅警告）\n提示：利率 0.5、β=3.0、年数 80", GREEN, LGREEN),
    ]
    x = 4
    for t, d, ec, fc in layers:
        box(ax, x, 50, 26, 12, t, fc=ec, ec=ec, tc="white", fs=11, bold=True)
        box(ax, x, 26, 26, 22, d, fc=fc, ec=ec, fs=9.0)
        x += 30
    box(ax, 4, 4, 86, 14, "三段式报错：错在哪里（哪个字段）＋ 为什么错（违反哪条口径）＋ 应如何修正（正确示例）",
        fc=LAMBER, ec=AMBER, fs=9.6, bold=True)
    arrow(ax, (17, 25), (17, 19), color=AMBER, lw=1.2)
    arrow(ax, (50, 25), (50, 19), color=AMBER, lw=1.2)
    arrow(ax, (83, 25), (83, 19), color=AMBER, lw=1.2)
    label(ax, 50, 68, "输入 → 校验 → 计算 → 解读 → 导出：任一层未通过都不会进入计算，"
                      "命令行与图形界面共用同一套 validators", fs=9.0, color=GRAY)
    save(fig, "fig04_三层校验.png")


def fig05_arch1():
    fig, ax = canvas(12.4, 6.0)
    label(ax, 50, 93, "项目一分层架构：GUI 与 CLI 共用同一内核", fs=13, color=BLUE, bold=True)
    box(ax, 4, 72, 44, 13, "交互层\nmain.py（菜单/场景函数）　gui.py（tkinter，捕获 stdout）",
        fc=LBLUE, ec=BLUE, fs=9.2)
    box(ax, 52, 72, 44, 13, "单文件版（历史归档）\nfinancial_calculator.pyw / _optimized.pyw",
        fc=LGRAY, ec=GRAY, fs=9.0)
    box(ax, 4, 52, 92, 12, "计算内核　core.py：13 个纯函数（复利/年金/YTM/CAPM/DDM/WACC/等额本息）",
        fc=BLUE, ec=BLUE, tc="white", fs=9.6, bold=True)
    box(ax, 4, 34, 44, 12, "校验与解读　validators.py\nRULES 三层校验 + interpret_* 业务解读",
        fc=LGREEN, ec=GREEN, fs=9.0)
    box(ax, 52, 34, 44, 12, "可视化　visualize.py\n8 个绘图函数（Agg 后端，中文字体）",
        fc=LAMBER, ec=AMBER, fs=9.0)
    box(ax, 4, 14, 92, 12, "导出　report.py → outputs/ 下 7 张 PNG + 07/09/10 三个 Excel + 计算结果汇总.md",
        fc="#F1EDFA", ec="#4A2E86", fs=9.2)
    for x in (26, 74):
        arrow(ax, (x, 71.6), (x, 64.6), lw=1.4)
    arrow(ax, (26, 51.6), (26, 46.6), lw=1.4)
    arrow(ax, (74, 51.6), (74, 46.6), lw=1.4)
    arrow(ax, (26, 33.6), (26, 26.6), lw=1.4, color="#4A2E86")
    arrow(ax, (74, 33.6), (74, 26.6), lw=1.4, color="#4A2E86")
    label(ax, 50, 5, "test_cases.py 直接调用 core.py，不经过交互层——因此命令行没装 matplotlib 也能跑通自检。",
          fs=8.6, color=GRAY)
    save(fig, "fig05_项目一架构.png")


def fig06_menu1():
    fig, ax = canvas(12.2, 6.0)
    label(ax, 50, 96, "项目一命令行菜单：编号 → 场景 → 产物", fs=13, color=BLUE, bold=True)
    items = [
        ("1", "复利终值 / 现值", "01_复利增长曲线.png"),
        ("2", "年金终值 / 现值", "02_年金现金流时间轴.png"),
        ("3", "债权资本成本", "03_债权资本成本曲线.png"),
        ("4", "股权资本成本", "（CAPM/DDM 结果表）"),
        ("5", "WACC", "04/05/06 三张图"),
        ("6", "贷款还款计划", "07_….xlsx + 08_….png"),
        ("8", "一键运行全部", "09_汇总.xlsx + 汇总.md"),
        ("0", "退出", "—"),
    ]
    y = 78
    for k, name, out in items:
        box(ax, 6, y, 7, 9, k, fc=BLUE, ec=BLUE, tc="white", fs=10.5, bold=True, r=1.2)
        box(ax, 15, y, 34, 9, name, fc=LGRAY, ec=GRAY, fs=9.4, align="left")
        box(ax, 52, y, 42, 9, out, fc=LBLUE, ec=BLUE, fs=8.8, align="left")
        arrow(ax, (49.4, y + 4.5), (51.6, y + 4.5), lw=1.0)
        y -= 9.4
    label(ax, 76, 88.5, "产物写入 outputs/", fs=8.6, color=BLUE, bold=True)
    label(ax, 24, 88.5, "输入编号后回车", fs=8.6, color=GRAY)
    label(ax, 50, 2.5, "交互过程中任何时候输入 q 并回车，可放弃当前计算并返回主菜单。", fs=8.6)
    save(fig, "fig06_项目一菜单.png")


def fig07_arch2():
    fig, ax = canvas(12.6, 5.8)
    label(ax, 50, 93, "项目二全流程：一条命令跑完 6 个案例", fs=13, color=BLUE, bold=True)
    stages = [("scenarios.py\n6 个案例", LBLUE, BLUE), ("finance_core\nNPV/IRR/ANCF/PI/MIRR", "#EDF3FA", MID),
              ("optimizer\n互斥优选 + 组合优化", LGREEN, GREEN), ("sensitivity\n单/双因素 + 临界点", LAMBER, AMBER),
              ("ai_advisor\n8 类风险规则", "#F1EDFA", "#4A2E86"), ("visualizer\n7 类图 39 张", "#FBEDED", RED)]
    x = 3
    for t, fc, ec in stages:
        box(ax, x, 58, 15, 18, t, fc=fc, ec=ec, fs=8.4)
        if x < 85:
            arrow(ax, (x + 15.4, 67), (x + 16.8, 67), lw=1.3)
        x += 16.6
    box(ax, 3, 30, 46, 18, "导出层\nreport_generator.py → Markdown + Word（python-docx）\n"
                            "data/*.csv → projects.csv、evaluations.csv", fc=LGRAY, ec=GRAY, fs=8.6)
    box(ax, 53, 30, 44, 18, "配置层\nconfig.py：默认折现率 0.10、DPI 200、中文字体候选、\n"
                            "AI 开关（IDS_AI_MODE / IDS_LLM_API_KEY）、随机种子 20260914",
        fc=LBLUE, ec=BLUE, fs=8.6)
    arrow(ax, (50, 57.4), (26, 48.6), lw=1.1, color=GRAY)
    arrow(ax, (50, 57.4), (75, 48.6), lw=1.1, color=GRAY)
    box(ax, 3, 8, 94, 13, "运行：python main.py [--rate 0.08] [--case CASE-3] [--no-docx] [--no-advice] "
                          "[--ai-mode rule|auto|llm] [--list]", fc=LAMBER, ec=AMBER, fs=9.4, bold=True)
    label(ax, 50, 2.5, "任何一步失败都会在终端以「案例 CASE-N：…」分节标题定位；"
                       "产物目录在导入 config 时即自动创建，无需手工 mkdir。", fs=8.5, color=GRAY)
    save(fig, "fig07_项目二流程.png")


def fig08_decision():
    fig, ax = canvas(12.4, 6.2)
    label(ax, 50, 94, "投资项目该用哪个判据？——项目二内置的决策路径", fs=13, color=BLUE, bold=True)
    box(ax, 34, 78, 32, 10, "待判断的项目集合", fc=BLUE, ec=BLUE, tc="white", fs=10, bold=True)
    box(ax, 6, 58, 26, 11, "相互独立\n（可同做）", LGRAY, GRAY, fs=9.2)
    box(ax, 37, 58, 26, 11, "互斥\n（只能选一个）", LGRAY, GRAY, fs=9.2)
    box(ax, 68, 58, 26, 11, "资金有限额", LGRAY, GRAY, fs=9.2)
    for x in (19, 50, 81):
        arrow(ax, (50, 77.4), (x, 69.6), lw=1.2)
    box(ax, 4, 40, 30, 12, "NPV ≥ 0 且 IRR ≥ r\n两者一致 → 可行", LGREEN, GREEN, fs=8.8)
    box(ax, 30.5, 40, 15, 12, "寿命相同\n比 NPV", LBLUE, BLUE, fs=8.6)
    box(ax, 46.5, 40, 15, 12, "寿命不同\n比 ANCF", LBLUE, BLUE, fs=8.6)
    box(ax, 66, 40, 30, 12, "排序法（PI 贪心）\n组合法（DFS）\n背包法（0-1 DP）", "#F1EDFA", "#4A2E86", fs=8.6)
    arrow(ax, (19, 57.4), (19, 52.6), lw=1.1, color=GREEN)
    arrow(ax, (38, 57.4), (38, 52.6), lw=1.1, color=BLUE)
    arrow(ax, (54, 57.4), (54, 52.6), lw=1.1, color=BLUE)
    arrow(ax, (81, 57.4), (81, 52.6), lw=1.1, color="#4A2E86")
    box(ax, 4, 18, 92, 14, "例外：非常规现金流（± 号变化 ≥ 2 次）→ IRR 可能有多根，"
                            "此时可行性只由 NPV 判定（CASE-4 的教学要点）",
        fc=LRED, ec=RED, fs=9.4, bold=True)
    label(ax, 50, 8, "规模冲突时用增量 IRR 仲裁：ΔIRR > r 才值得多投的那部分钱；"
                     "寿命冲突时 NPV 不再可比，必须折算成年金净流量。", fs=8.6, color=GRAY)
    label(ax, 50, 3.0, "对应实现：src/optimizer.py、src/models.py::Evaluation.build", fs=8.0, color=GRAY)
    save(fig, "fig08_判据选择.png")


def fig09_arch3():
    fig, ax = canvas(12.6, 6.6)
    label(ax, 50, 95, "项目三：场景一（成本核算链）与场景二（短期决策）", fs=13, color=BLUE, bold=True)
    label(ax, 6, 84, "场景一 · 2026 年 8 月成本核算", fs=10, color=GREEN, ha="left", bold=True)
    chain1 = ["费用归集分配\n材料/人工/制造", "辅助生产三法\n直接/交互/代数", "作业成本法\nABC vs 传统",
              "产品成本计算\n品种/分批/分步", "标准成本差异\n两/三差异法", "混合成本分解\n高低点/回归",
              "本量利分析\n保本/保利/敏感"]
    x = 5
    for i, t in enumerate(chain1):
        box(ax, x, 64, 12.4, 15, t, fc=LGREEN if i % 2 == 0 else "#F2F9F2", ec=GREEN, fs=7.4)
        if i < 6:
            arrow(ax, (x + 12.6, 71.5), (x + 13.6, 71.5), lw=1.0, color=GREEN)
        x += 13.4
    label(ax, 6, 55, "场景二 · 2026 年 9 月经营决策", fs=10, color=AMBER, ha="left", bold=True)
    chain2 = ["特殊订单\n剩余产能内/外", "约束资源\n排序法 + 线性规划", "产品定价\n成本加成/目标成本",
              "自制或外购\n含机会成本", "亏损停产\n可避免固定成本", "综合方案对比\n差别损益同口径"]
    x = 4
    for i, t in enumerate(chain2):
        box(ax, x, 35, 14.5, 15, t, fc=LAMBER if i % 2 == 0 else "#FFF9EF", ec=AMBER, fs=7.6)
        if i < 5:
            arrow(ax, (x + 14.7, 42.5), (x + 15.5, 42.5), lw=1.0, color=AMBER)
        x += 15.7
    box(ax, 5, 14, 55, 14, "支撑模块\nrounding.py 会计舍入（round_half_up / 先算后舍 / 倒挤）\n"
                            "ai_assistant.py 数据生成 + 差异归因 + 决策文案（策略模式）",
        fc=LBLUE, ec=BLUE, fs=8.4)
    box(ax, 62, 14, 33, 14, "输出\n17 张图 + 2 份 Excel 底稿（32/22 表）\n+ 2 份 Markdown 报告", fc=LGRAY, ec=GRAY, fs=8.4)
    arrow(ax, (58, 42), (64, 28), lw=1.0, color=GRAY)
    label(ax, 50, 5, "运行：python main.py --scenario 1 | 2 | all；"
                     "每一步的表名（表1-1 … 表2-14）与 Markdown 报告章节一一对应。", fs=8.6, color=GRAY)
    save(fig, "fig09_项目三链条.png")


def fig10_pipeline4():
    fig, ax = canvas(12.6, 6.0)
    label(ax, 50, 94, "项目四数据流水线：抓得到 → 校得准 → 算得清 → 写得成", fs=13,
          color=BLUE, bold=True)
    cols = [
        ("采集", ["fetch_data.py", "东方财富 F10（主）", "单位：元", "新浪财经页面（核对）", "单位：万元",
                  "fs_parser.py 解析 GB18030"], BLUE, LBLUE),
        ("落盘", ["data/raw/*.json", "data/raw/*.html", "data/processed/", "income / balance /", "cashflow 三张 CSV"],
         MID, "#EDF3FA"),
        ("校验", ["verify.py", "7 项会计恒等式", "双源逐科目核验", "output/tables/00_*.csv"], RED, LRED),
        ("分析", ["structure 共同比", "trend 定基/环比/CAGR", "indicators 40 项指标", "dupont 三/五因素"],
         GREEN, LGREEN),
        ("成稿", ["charts.py 12 张图", "分析结果汇总.xlsx", "（15 个工作表）", "build_report.py", "→ HTML 单文件报告"],
         AMBER, LAMBER),
    ]
    x = 3.5
    for title, lines, ec, fc in cols:
        box(ax, x, 74, 18, 9, title, fc=ec, ec=ec, tc="white", fs=10.4, bold=True)
        box(ax, x, 24, 18, 48, "\n".join(lines), fc=fc, ec=ec, fs=8.2)
        if x < 84:
            arrow(ax, (x + 18.3, 48), (x + 19.4, 48), lw=1.5)
        x += 19.6
    box(ax, 3.5, 6, 92.5, 12, "一键运行：python fetch_data.py → python run_all.py [--no-charts] "
                              "[--years 2023 2024 2025] → python build_report.py [-o 自定义.html]",
        fc=LGRAY, ec=GRAY, fs=9.2, bold=True)
    label(ax, 50, 1.5, "抓取结果全部落盘，分析阶段只读本地文件；断网时可直接跳到第 2 步。", fs=8.4,
          color=GRAY)
    save(fig, "fig10_项目四流水线.png")


def fig11_dupont():
    fig, ax = canvas(12.2, 5.4)
    label(ax, 50, 92, "杜邦分解树（项目四 7.1 节所画的就是这棵树）", fs=13, color=BLUE, bold=True)
    box(ax, 38, 72, 24, 12, "ROE\n净利润 / 平均股东权益", fc=BLUE, ec=BLUE, tc="white", fs=9.4, bold=True)
    kids = [("销售净利率", "净利润 / 营业收入", 6, 46), ("总资产周转率", "营业收入 / 平均总资产", 37, 46),
            ("权益乘数", "平均总资产 / 平均股东权益", 68, 46)]
    for name, f, x, y in kids:
        box(ax, x, y, 26, 12, f"{name}\n{f}", fc=LBLUE, ec=BLUE, fs=8.8)
        arrow(ax, (50, 71.4), (x + 13, y + 12.6), lw=1.2)
    box(ax, 6, 22, 26, 14, "盈利质量\n（利润表）", fc=LGREEN, ec=GREEN, fs=8.8)
    box(ax, 37, 22, 26, 14, "营运效率\n（两张表配合）", fc=LAMBER, ec=AMBER, fs=8.8)
    box(ax, 68, 22, 26, 14, "财务杠杆\n（资产负债表）", fc="#F1EDFA", ec="#4A2E86", fs=8.8)
    for x in (19, 50, 81):
        arrow(ax, (x, 45.4), (x, 36.6), lw=1.0, color=GRAY)
    label(ax, 50, 10, "五因素分解把销售净利率进一步拆成：税前利润率 × 实际所得税率 × 息税前利润率，"
                      "用于区分“经营改善”与“杠杆贡献”。", fs=8.6)
    label(ax, 50, 4, "口径要点：分母一律用平均余额；周转率分子用「营业收入」而非「营业总收入」，"
                     "因此 净利率 × 周转率 = ROA 严格成立、分解无残差。", fs=8.6, color=RED)
    save(fig, "fig11_杜邦树.png")


def fig12_pipeline5():
    fig, ax = canvas(12.8, 5.8)
    label(ax, 50, 93, "项目五八阶段流水线（run_all.py 的编排顺序）", fs=13, color=BLUE, bold=True)
    st = [("s1 抓数", "腾讯自选股 CLI\n→ data/raw/*.md"), ("s2 清洗", "季度→年度面板\n倒轧其他经营损益"),
          ("s3 历史", "比率/CAGR/MAD\n十年统计特征"), ("s4 预测", "5 模型+滚动回测\n误差倒数加权"),
          ("s5 预算", "成本性态分解\n利润表/现金流/季度"), ("s6 图表", "16 张 PNG\n160 dpi"),
          ("s7 报告", "Word：7 章 4 附录\n23 表 16 图"), ("s8 质检", "结构/版式/文本\n三类检查")]
    x = 2.5
    for i, (t, d) in enumerate(st):
        ec = [BLUE, MID, GREEN, AMBER, "#4A2E86", RED, "#0F7B7B", GRAY][i]
        box(ax, x, 62, 11.2, 9, t, fc=ec, ec=ec, tc="white", fs=8.8, bold=True)
        box(ax, x, 34, 11.2, 24, d, fc=LGRAY, ec=ec, fs=7.4)
        if i < 7:
            arrow(ax, (x + 11.4, 66.5), (x + 12.4, 66.5), lw=1.1)
        x += 12.4
    box(ax, 2.5, 12, 60, 14, "常用开关：--skip-fetch（用本地快照，不联网）　--no-docx（只出图表与中间表）\n"
                             "单模块调试：python src/s2_pipeline.py、python src/s8_qc.py",
        fc=LBLUE, ec=BLUE, fs=8.6)
    box(ax, 65, 12, 32.5, 14, "交付链：docx → tools/docx2pdf.ps1\n（Word 刷新目录域）→ render_pages.py 目视核验",
        fc=LAMBER, ec=AMBER, fs=8.4)
    label(ax, 50, 4, "全部结论与图表均由程序产出，报告即程序的输出；改一处假设，重跑一次即可全篇一致。",
          fs=8.6, color=GRAY)
    save(fig, "fig12_项目五流水线.png")


def fig13_forecast():
    fig, ax = canvas(12.2, 5.2)
    label(ax, 50, 92, "组合预测：五个模型如何合成一个数", fs=13, color=BLUE, bold=True)
    models = ["CAGR\n复合增长", "OLS\n线性趋势", "Holt 阻尼\n指数平滑", "ARIMA\n(1,1,1)", "MEAN5\n近五年均值"]
    x = 5
    for m in models:
        box(ax, x, 62, 17, 14, m, fc=LBLUE, ec=BLUE, fs=8.6)
        arrow(ax, (x + 8.5, 61.4), (50, 46), lw=0.9, color=GRAY)
        x += 18.2
    box(ax, 26, 30, 48, 14, "滚动回测（2022/2023/2024 为预测起点）\n计算样本外 MAPE → 按误差倒数定权重",
        fc=LGREEN, ec=GREEN, fs=9.0)
    box(ax, 12, 8, 34, 14, "2026E 点估计\n组合值", fc=BLUE, ec=BLUE, tc="white", fs=9.4, bold=True)
    box(ax, 54, 8, 34, 14, "90% 区间\nσ = √(σ²回测 + σ²模型分歧)", fc=AMBER, ec=AMBER, tc="white", fs=9.0,
        bold=True)
    arrow(ax, (40, 29.4), (29, 22.6), lw=1.2)
    arrow(ax, (60, 29.4), (71, 22.6), lw=1.2)
    save(fig, "fig13_组合预测.png")


def fig14_trouble():
    fig, ax = canvas(12.6, 6.4)
    label(ax, 50, 95, "跑不通时的排障顺序（先环境、再输入、最后代码）", fs=13, color=BLUE, bold=True)
    box(ax, 36, 80, 28, 10, "程序报错 / 无输出", fc=RED, ec=RED, tc="white", fs=10.4, bold=True)
    branches = [
        ("ModuleNotFoundError", "虚拟环境未激活\n或依赖未装\n→ pip install -r\n  requirements.txt", 2.5, BLUE, LBLUE),
        ("python 不是内部命令", "PATH 未勾选\n→ 重装并勾选\n  或改用 py -3", 22, MID, "#EDF3FA"),
        ("图表中文乱码", "系统缺中文字体\n→ 装思源黑体\n  或微软雅黑", 41.5, GREEN, LGREEN),
        ("PermissionError", "Excel 正打开产物\n→ 关闭文件后\n  重新运行", 61, AMBER, LAMBER),
        ("抓数失败 / 超时", "网络或接口变更\n→ 用本地快照\n  跳过抓取", 80.5, RED, LRED),
    ]
    for txt, fix, x, ec, fc in branches:
        box(ax, x, 54, 17, 11, txt, fc=ec, ec=ec, tc="white", fs=8.0, bold=True)
        box(ax, x, 30, 17, 22, fix, fc=fc, ec=ec, fs=8.0)
        arrow(ax, (50, 79.4), (x + 8.5, 65.6), lw=1.0)
    box(ax, 4, 10, 92, 14, "判据：报错信息里出现的是「找不到模块/找不到文件/编码/网络」还是「数值不合理」。"
                           "前三类都是环境问题，最后一类才是口径问题——先分清，再动手改代码。",
        fc=LGRAY, ec=GRAY, fs=9.0, bold=True)
    label(ax, 50, 3, "第 8 章给出按症状索引的完整排障总表，可直接对照自查。", fs=8.6, color=GRAY)
    save(fig, "fig14_排障顺序.png")


def fig15_report():
    fig, ax = canvas(12.4, 5.4)
    label(ax, 50, 92, "五个项目的产物如何拼成一份课程报告", fs=13, color=BLUE, bold=True)
    rows = [("报告章节", "取用项目", "直接可用的产物", "还要自己补的"),
            ("计算原理与口径", "项目一", "7 张图 + 09_汇总.xlsx", "把默认示例参数换成自己题目的参数"),
            ("方案评价", "项目二", "MD/Word 报告 + 39 图", "案例结论与本企业背景的对应关系"),
            ("成本与短期决策", "项目三", "2 份 MD 报告 + 2 份 Excel 底稿", "把模拟数据替换为车间真实数据"),
            ("报表分析", "项目四", "HTML 报告 + 15 表工作簿", "结论段的自己的判断与风险提示"),
            ("预测与预算", "项目五", "Word 报告（23 表 16 图）", "情景假设的行业依据")]
    y = 74
    for i, r in enumerate(rows):
        fc = BLUE if i == 0 else (LGRAY if i % 2 else "white")
        tc = "white" if i == 0 else INK
        box(ax, 4, y, 20, 9, r[0], fc=fc, ec=GRAY, tc=tc, fs=8.8, bold=(i == 0), align="left", r=0.6)
        box(ax, 24.4, y, 12, 9, r[1], fc=fc, ec=GRAY, tc=tc, fs=8.8, bold=(i == 0), r=0.6)
        box(ax, 36.8, y, 32, 9, r[2], fc=fc, ec=GRAY, tc=tc, fs=8.6, bold=(i == 0), align="left", r=0.6)
        box(ax, 69.2, y, 27, 9, r[3], fc=fc, ec=GRAY, tc=tc, fs=8.6, bold=(i == 0), align="left", r=0.6)
        y -= 9.6
    label(ax, 50, 12, "引用图表时务必同时标注：运行命令、参数口径（小数还是百分数）、单位（元 / 万元 / 亿元）、"
                      "数据来源与生成日期。", fs=8.8, color=RED)
    save(fig, "fig15_报告拼装.png")


if __name__ == "__main__":
    for fn in (fig01_map, fig02_env, fig03_venv, fig04_validation, fig05_arch1, fig06_menu1,
               fig07_arch2, fig08_decision, fig09_arch3, fig10_pipeline4, fig11_dupont,
               fig12_pipeline5, fig13_forecast, fig14_trouble, fig15_report):
        fn()
    print("done ->", OUT)
