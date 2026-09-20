# -*- coding: utf-8 -*-
"""单独验证 fpdf2 回退字体能否渲染 ✔ ✘ ⚠ ▶ −。"""
import os
from fpdf import FPDF

FD = "C:/Windows/Fonts/"
pdf = FPDF("P", "mm", "A4")
pdf.add_font("cjk", "", FD + "Deng.ttf")
pdf.add_font("sym", "", FD + "seguisym.ttf")
pdf.set_fallback_fonts(["sym", "cjk"])
pdf.add_page()
pdf.set_font("cjk", size=20)
pdf.text(20, 30, "fallback test: A ✔ B ✘ C ⚠ D ▶ E − F • G → H ≤ I ∑")
pdf.set_font("cjk", size=20)
pdf.text(20, 45, "no fallback path: " + "".join([]) + "✔")
pdf.output(os.path.join(os.path.dirname(os.path.abspath(__file__)), "qa", "fallback_test.pdf"))
print("done")
