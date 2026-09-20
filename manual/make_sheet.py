# -*- coding: utf-8 -*-
"""把 qa 目录下的页面截图拼成检查用拼图。"""
import os
import sys

from PIL import Image

d = sys.argv[1]
names = sorted(f for f in os.listdir(d) if f.startswith("p") and f.endswith(".png"))
if len(sys.argv) > 2:
    pick = set(sys.argv[2].split(","))
    names = [n for n in names if n[1:4].lstrip("p") in pick or n in pick]
cellw = int(sys.argv[3]) if len(sys.argv) > 3 else 620
cols = int(sys.argv[4]) if len(sys.argv) > 4 else 3
imgs = []
for n in names:
    im = Image.open(os.path.join(d, n)).convert("RGB")
    w, h = im.size
    imgs.append((n, im.resize((cellw, int(h * cellw / w)))))
rh = max(i.size[1] for _, i in imgs)
rows = (len(imgs) + cols - 1) // cols
sheet = Image.new("RGB", (cols * cellw, rows * rh), (235, 236, 238))
for k, (n, im) in enumerate(imgs):
    sheet.paste(im, ((k % cols) * cellw, (k // cols) * rh))
out = os.path.join(d, "sheet.jpg")
sheet.save(out, quality=82)
print(out, sheet.size, [n for n, _ in imgs])
