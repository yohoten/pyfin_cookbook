# -*- coding: utf-8 -*-
"""
config.py — 全局配置模块
====================================================================
统一管理路径、matplotlib 中文字体、默认财务参数。

设计说明
--------
* 所有模块通过 ``from .config import ...`` 复用本配置，避免硬编码；
* 中文字体优先使用 Microsoft YaHei，回退 SimHei，解决 matplotlib
  默认字体无法渲染中文（显示为方框）的常见问题；
* 负号显示单独设置 ``axes.unicode_minus = False``，否则负号会变成方块。
"""

from __future__ import annotations

import os
from pathlib import Path

# ----------------------------------------------------------------------
# 一、路径配置
# ----------------------------------------------------------------------
# BASE_DIR 指向程序包根目录（investment_decision_system/）
BASE_DIR: Path = Path(__file__).resolve().parent.parent

OUTPUT_DIR: Path = BASE_DIR / "outputs"
FIGURE_DIR: Path = OUTPUT_DIR / "figures"   # 图表输出目录
REPORT_DIR: Path = OUTPUT_DIR / "reports"   # 报告输出目录（Markdown / Word）
DATA_DIR: Path = OUTPUT_DIR / "data"        # 中间数据输出目录（CSV）

for _d in (OUTPUT_DIR, FIGURE_DIR, REPORT_DIR, DATA_DIR):
    _d.mkdir(parents=True, exist_ok=True)


# ----------------------------------------------------------------------
# 二、matplotlib 全局样式（含中文字体）
# ----------------------------------------------------------------------
def setup_matplotlib_chinese() -> None:
    """配置 matplotlib 支持中文显示与高质量出图。

    该函数需在 **任何绘图动作之前** 调用一次。重复调用无副作用。

    Returns
    -------
    None
    """
    import matplotlib

    # 无界面后端：保证在服务器 / 无显示器环境下也能正常出图
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # 字体候选：Windows 常见的微软雅黑、黑体；Linux/macOS 下自动回退
    plt.rcParams["font.sans-serif"] = [
        "Microsoft YaHei", "SimHei", "Noto Sans CJK SC",
        "WenQuanYi Zen Hei", "Arial Unicode MS", "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False   # 正常显示负号
    plt.rcParams["figure.dpi"] = 120             # 屏幕/文档显示清晰度
    plt.rcParams["savefig.dpi"] = 200            # 导出分辨率
    plt.rcParams["savefig.bbox"] = "tight"       # 自动裁剪留白
    plt.rcParams["figure.facecolor"] = "white"   # 白底，便于插入报告
    plt.rcParams["axes.facecolor"] = "white"
    plt.rcParams["axes.grid"] = True
    plt.rcParams["grid.alpha"] = 0.3
    plt.rcParams["grid.linestyle"] = "--"
    plt.rcParams["axes.edgecolor"] = "#5A5A5A"
    plt.rcParams["axes.labelsize"] = 11
    plt.rcParams["font.size"] = 10


# ----------------------------------------------------------------------
# 三、配色方案（统一视觉语言）
# ----------------------------------------------------------------------
# 遵循中国财务/股市惯例：正向收益用红色系，负向/亏损用绿色系
COLOR_POSITIVE = "#C0392B"   # 正 NPV / 可行：红
COLOR_NEGATIVE = "#27AE60"   # 负 NPV / 不可行：绿
COLOR_BASE = "#2C3E50"       # 基准线：深蓝灰
COLOR_HIGHLIGHT = "#E67E22"  # 强调：橙
COLOR_NEUTRAL = "#7F8C8D"    # 中性：灰

# 多项目对比调色板（10 色，够用且区分度高）
PALETTE = [
    "#2E5C8A", "#C0392B", "#E67E22", "#16A085", "#8E44AD",
    "#D35400", "#2980B9", "#7F8C8D", "#F39C12", "#27AE60",
]


# ----------------------------------------------------------------------
# 四、默认财务参数
# ----------------------------------------------------------------------
# 折现率基准取值依据：以教材例题常用口径 10% 作为默认基准折现率
DEFAULT_RATE: float = 0.10

# 资本成本上下限（用于 IRR 与折现率关系曲线的横轴范围）
RATE_CURVE_MIN: float = 0.00
RATE_CURVE_MAX: float = 0.50

# 敏感性分析默认扰动幅度（±20%）
SENSITIVITY_DELTA: float = 0.20


# ----------------------------------------------------------------------
# 五、AI 辅助开关
# ----------------------------------------------------------------------
# AI 决策建议生成模式：
#   "auto"  → 有可用大模型 API 时调用大模型，否则降级为内置规则引擎
#   "rule"  → 强制使用内置规则引擎（离线可复现，推荐用于作业提交）
#   "llm"   → 强制使用大模型（需配置环境变量，失败会抛错）
AI_MODE: str = os.environ.get("IDS_AI_MODE", "auto")

# 大模型 API 配置（可选）。未配置时 ai_advisor 自动降级为规则引擎。
AI_API_KEY: str = os.environ.get("IDS_LLM_API_KEY", "")
AI_BASE_URL: str = os.environ.get("IDS_LLM_BASE_URL", "https://api.openai.com/v1")
AI_MODEL: str = os.environ.get("IDS_LLM_MODEL", "gpt-4o-mini")

# 数据生成随机种子：固定种子保证结果可复现（作业评测友好）
RANDOM_SEED: int = 20260914
