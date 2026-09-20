# -*- coding: utf-8 -*-
"""manual/build_manual.py —— 组装并输出《Python 财务应用项目操作手册》PDF"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import build  # noqa: E402

import c00_front  # noqa: E402
import c01_project1  # noqa: E402

MODULES = []
try:
    import c02_project2
    MODULES.append(c02_project2)
except ImportError:
    pass
try:
    import c03_project3
    MODULES.append(c03_project3)
except ImportError:
    pass
try:
    import c04_project4
    MODULES.append(c04_project4)
except ImportError:
    pass
try:
    import c05_project5
    MODULES.append(c05_project5)
except ImportError:
    pass
try:
    import c06_report
    MODULES.append(c06_report)
except ImportError:
    pass

TITLE = "Python 财务应用项目操作手册"
SUBTITLE = "works/ 五个综合实验项目 · 从环境搭建到结果复核的保姆级指南"
META = [
    "适用对象：《Python 在财务管理中的应用》课程学生、实验指导教师",
    "覆盖项目：货币时间价值与资本成本计算器 · 投资项目全流程评价系统 · 综合成本与经营决策分析平台",
    "　　　　　财务报表分析报告（美的集团 000333.SZ） · 财务预测与预算管理（永鼎股份 600105）",
    "编写依据：五个项目的全部源码、README 与已生成产物，关键数值均经逐条复算核对",
    "版式参照：《Hello 算法》中文 PDF（图注编号、提示框、章首引言、点线目录）",
    "整理日期：2026 年 9 月",
]


def content(doc):
    c00_front.front(doc)
    c00_front.chapter1(doc)
    c01_project1.chapter2(doc)
    for m in MODULES:
        for fn in ("chapter3", "chapter4", "chapter5", "chapter6", "chapter7",
                   "chapter8", "appendix"):
            f = getattr(m, fn, None)
            if f:
                f(doc)


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "Python财务应用项目操作手册.pdf")
    build(TITLE, SUBTITLE, META, content, out)
