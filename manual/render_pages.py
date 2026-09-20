# -*- coding: utf-8 -*-
"""把 PDF 前若干页渲染成 PNG，用于目视复核。"""
import os
import sys

import pypdfium2 as pdfium

pdf_path = sys.argv[1]
out_dir = sys.argv[2]
pages = [int(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else [1]
os.makedirs(out_dir, exist_ok=True)
doc = pdfium.PdfDocument(pdf_path)
for n in pages:
    page = doc[n - 1]
    bmp = page.render(scale=1.6)
    img = bmp.to_pil()
    p = os.path.join(out_dir, f"p{n:03d}.png")
    img.save(p)
    print(p, img.size)
