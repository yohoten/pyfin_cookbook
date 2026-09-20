# -*- coding: utf-8 -*-
"""检查系统字体对手册中用到的特殊符号的字形覆盖情况。"""
import os
from fontTools.ttLib import TTFont

FD = "C:/Windows/Fonts/"
need = {0x25B6: "▶", 0x26A0: "⚠", 0x2212: "−", 0x2714: "✔", 0x2718: "✘", 0x2022: "•",
        0x2192: "→", 0x2264: "≤", 0x2265: "≥", 0x00D7: "×", 0x00F7: "÷", 0x221A: "√",
        0x03C3: "σ", 0x2211: "∑", 0x03B2: "β", 0x221E: "∞", 0x2500: "─", 0x2550: "═",
        0x25CF: "●", 0x00A0: "NBSP", 0x2014: "—", 0x2018: "‘", 0x201C: "“", 0x2026: "…"}
cands = ["seguisym.ttf", "simsun.ttc", "Deng.ttf", "simhei.ttf", "arialuni.ttf",
         "NotoSansCJK-Regular.ttc", "msyh.ttc", "MSyhbd.ttc", "segoeui.ttf",
         "NotoSansSymbols2-Regular.ttf", "sylfaen.ttf", "Ebrima.ttf"]
for c in cands:
    p = FD + c
    if not os.path.exists(p):
        print("no file :", c)
        continue
    try:
        f = TTFont(p, fontNumber=0)
        cmap = f.getBestCmap()
        miss = "".join(ch for cp, ch in need.items() if cp not in cmap)
        print(f"{c:32s} missing: {miss or 'none'}")
    except Exception as e:
        print(f"{c:32s} ERR {type(e).__name__}: {e}")
