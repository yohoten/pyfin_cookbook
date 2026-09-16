# -*- coding: utf-8 -*-
"""
investment_decision_system — 投资项目决策自动化评价系统
====================================================================
对应课程第 5 章：净现值(NPV)、内含报酬率(IRR)、互斥项目优选、
资本限额下的项目分配、投资决策敏感性分析。

模块导航
--------
======================  ==========================================================
模块                     职责
======================  ==========================================================
:mod:`config`            路径、字体、配色、默认参数、AI 开关
:mod:`finance_core`      核心算法：NPV / IRR / ANCF / PI / 回收期 / MIRR / 增量IRR
:mod:`models`            数据结构：Project / Evaluation / IndustryProfile
:mod:`ai_data_generator` AI 生成多行业多周期现金流数据
:mod:`scenarios`         6 个教学测试案例（含独立、互斥、限额、多重根）
:mod:`optimizer`         互斥优选 + 资本限额组合优化（排序法/组合法/背包法）
:mod:`sensitivity`       单因素、双因素敏感性分析与临界点分析
:mod:`ai_advisor`        AI 决策建议生成（规则引擎 + 可选大模型通道）
:mod:`visualizer`        全部图表绘制
:mod:`report_generator`  Markdown / Word 报告导出
======================  ==========================================================

快速开始
--------
直接运行主程序::

    python main.py

或按案例单独运行::

    python main.py --case CASE-3 --rate 0.10

或在代码中调用::

    from src import finance_core as fc

    npv = fc.npv(0.10, [500, 500, 500], 1000)   # 243.43
    irr = fc.irr([500, 500, 500], 1000)          # 0.2338
"""

from __future__ import annotations

__version__ = "1.0.0"
__all__ = [
    "config",
    "finance_core",
    "models",
    "ai_data_generator",
    "scenarios",
    "optimizer",
    "sensitivity",
    "ai_advisor",
    "visualizer",
    "report_generator",
]
