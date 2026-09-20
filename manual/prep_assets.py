# -*- coding: utf-8 -*-
"""把手册要用的项目原生产物图表统一复制/压平到 manual/assets/img（ASCII 文件名）。"""
import json
import os
import sys
import unicodedata
from PIL import Image

SRC_ROOT = r"F:\（8）Desktop\财务会计实务与应用\Python财务应用\works"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "img")
os.makedirs(OUT_DIR, exist_ok=True)

SOURCES = {
    "p1": "01-货币时间价值与资本成本计算器/financial_calculator/outputs",
    "p2": "02-投资项目全流程评价系统/investment_decision_system/outputs/figures",
    "p3": "03-综合成本与经营决策分析平台/cost_decision_platform/output/charts",
    "p4": "04-财务报表分析报告/output/charts",
    "p5": "05-财务预测与预算管理实验报告/Yongding_Forecast_Budget_2026/output/charts",
    "p5qc": "05-财务预测与预算管理实验报告/Yongding_Forecast_Budget_2026/output/qc",
    "p3rep": "03-综合成本与经营决策分析平台/cost_decision_platform/output/reports",
}


def ascii_slug(stem: str) -> str:
    out = []
    for ch in stem:
        if ch.isascii() and (ch.isalnum() or ch in "-_"):
            out.append(ch)
        elif ord(ch) > 0x2000 and not ch.isascii():
            # 中文等非 ASCII：用 Unicode 名称的简短转写
            continue
        else:
            out.append("_")
    s = "".join(out).strip("_")
    return s or "fig"


manifest = {}
for code, rel in SOURCES.items():
    d = os.path.join(SRC_ROOT, rel.replace("/", os.sep))
    if not os.path.isdir(d):
        print("!! missing", d)
        continue
    for fn in sorted(os.listdir(d)):
        if not fn.lower().endswith(".png"):
            continue
        src = os.path.join(d, fn)
        stem = os.path.splitext(fn)[0]
        slug = ascii_slug(stem)
        name = f"{code}_{slug}.jpg"
        _n = 1
        while name in manifest:
            _n += 1
            name = f"{code}_{slug}_{_n}.jpg"
        try:
            im = Image.open(src)
        except Exception as e:  # noqa: BLE001
            print("!! unreadable", fn, e)
            continue
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(im, mask=im.split()[-1])
            im = bg
        else:
            im = im.convert("RGB")
        if im.width > 1800:
            h = round(im.height * 1800 / im.width)
            im = im.resize((1800, h), Image.LANCZOS)
        im.save(os.path.join(OUT_DIR, name), "JPEG", quality=88, optimize=True)
        manifest[name] = {"src": f"{code}/{fn}", "w": im.width, "h": im.height,
                          "kb": round(os.path.getsize(os.path.join(OUT_DIR, name)) / 1024)}
        print(f"{name:48} {im.width}x{im.height}  <-  {fn}")

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "img_manifest.json"),
          "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=1)
print("\ntotal:", len(manifest))

print("\n=== candidate fonts ===")
FDIR = r"C:\Windows\Fonts"
want = ("msyh", "simhei", "simsun", "simkai", "simfang", "deng", "simyou",
        "consol", "cascadia", "sarasa", "sourcehan", "noto", "malgun", "batang", "mingliu")
for fn in sorted(os.listdir(FDIR)):
    low = fn.lower()
    if any(w in low for w in want):
        p = os.path.join(FDIR, fn)
        print(f"{fn:26} {os.path.getsize(p)/1024/1024:7.2f}MB")
if hasattr(sys.stdout, "reconfigure"):
    pass
