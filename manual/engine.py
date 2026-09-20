# -*- coding: utf-8 -*-
"""
manual/engine.py —— 《Python 财务应用项目操作手册》排版引擎

自研轻量书籍排版（A4），版式参照《Hello 算法》中文 PDF：
  章首页（章号 + 章名 + Abstract 引言框）、x.y / x.y.z 编号小节、
  页眉（左章名 / 右手册简称）+ 页脚页码、点线目录（两趟排版保证页码正确）、
  图 x.y 居中图注、表 x.y、代码块、四类提示框、公式居中行。

关键实现：中文避头尾禁则断行 + 像素级排版（不依赖 fpdf 的自动换行）。
"""
from __future__ import annotations

import os
import re

from PIL import Image
from fpdf import FPDF

HERE = os.path.dirname(os.path.abspath(__file__))
ASSET_DIR = os.path.join(HERE, "assets", "img")
FIG_DIR = os.path.join(HERE, "assets", "fig")
FONT_DIR = r"C:\Windows\Fonts"

FONTS = {
    "cjk":  {"":  os.path.join(FONT_DIR, "Deng.ttf")},          # 等线：正文
    "hei":  {"":  os.path.join(FONT_DIR, "simhei.ttf")},        # 黑体：标题/强调
    "kai":  {"":  os.path.join(FONT_DIR, "simkai.ttf")},         # 楷体：章引言
    "fang": {"":  os.path.join(FONT_DIR, "simfang.ttf")},        # 仿宋：公式
    "mono": {"":  os.path.join(FONT_DIR, "consola.ttf"),
             "B": os.path.join(FONT_DIR, "consolab.ttf")},       # Consolas：代码
}

INK = (28, 30, 33)
INK_SOFT = (98, 104, 112)
ACCENT = (28, 74, 140)
RULE = (206, 212, 221)
CODE_BG = (246, 247, 249)
CODE_INK = (28, 40, 54)
TABLE_HEAD = (235, 240, 247)
TABLE_ALT = (249, 250, 252)
CAPTION = (96, 102, 110)

CALLOUT = {
    "tip":  ("#2E7D32", "#EDF6EC", "提示"),
    "info": ("#1F4E9B", "#EDF2FA", "说明"),
    "warn": ("#A9660A", "#FFF5E4", "注意"),
    "err":  ("#AE2B2B", "#FBEDED", "常见错误"),
    "do":   ("#4A2E86", "#F2EEFA", "动手做"),
}
PT2MM = 0.35277778

# 等线/黑体/Consolas 缺字形的符号，统一替换为等线已有的等价字形，避免 PDF 里出现空白
GLYPH_SUBS = {
    "✔": "√",   # 对勾 -> 根号（√）
    "✘": "×",   # 叉   -> 乘号（×）
    "⚠": "!",          # 警告 -> 感叹号
    "▶": "→",   # 实心三角 -> 箭头
    "−": "-",          # 数学减号 -> 连字符
    "✓": "√",   # 单勾
    " ": " ",          # 不换行空格
}


MARK = chr(1)


def prep_bold(text):
    """把 **粗体** 转成  标记，标记宽度为零且可跨行自动闭合。"""
    text = str(text)
    text = re.sub(r"\*\*([^*]+)\*\*", MARK + r"\1" + MARK, text)
    return text.replace("**", "")


def fix_glyphs(t):
    if not isinstance(t, str) or not t:
        return t
    for a, b in GLYPH_SUBS.items():
        if a in t:
            t = t.replace(a, b)
    return t


def _rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# ---------------------------------------------------------------------------
# 中文断行（禁则处理）
# ---------------------------------------------------------------------------
NO_START = set("。，、；：？！）〉》」』】〕»’”…·,.;:?!)}%】")
NO_END = set("（〈《「『【〔«‘“([{￥$")
_ASCII_RUN = re.compile(r"[A-Za-z0-9_@./#&+\-:%=\[\]()~*<>{}\\|]+")


def tokenize(s: str):
    out, i, n = [], 0, len(s)
    while i < n:
        ch = s[i]
        if ch == " ":
            j = i
            while j < n and s[j] == " ":
                j += 1
            out.append(" " * (j - i))
            i = j
        elif ch == "\t":
            out.append("    ")
            i += 1
        else:
            m = _ASCII_RUN.match(s, i)
            if m:
                out.append(m.group())
                i = m.end()
            else:
                out.append(ch)
                i += 1
    return out


# ---------------------------------------------------------------------------
# 主文档类
# ---------------------------------------------------------------------------
class Manual(FPDF):
    def __init__(self, book_short: str, book_title: str):
        super().__init__("P", "mm", "A4")
        self.book_short = book_short
        self.book_title = book_title
        self.chapter_title = ""
        self.page_label_start = 1     # 正文从第几页开始计页码
        self.entries: list[dict] = []  # 目录条目
        self.fig_no = 0
        self.tab_no = 0
        self._toc_pages = 0
        self.set_margins(23, 25, 23)
        self.set_auto_page_break(False)
        self.set_line_width(0.22)
        self.set_compression(True)
        for fam, styles in FONTS.items():
            for st, path in styles.items():
                if os.path.exists(path):
                    self.add_font(fam, st, path)
        self.set_fallback_fonts(["cjk"])

    # ---------------------------------------------------------------- 页版式
    def text(self, x, y, txt="*", *args, **kwargs):
        return super().text(x, y, fix_glyphs(txt), *args, **kwargs)

    def header(self):
        if self.page_no() <= self._skip_header:
            return
        self.set_font("cjk", size=8.0)
        self.set_text_color(*INK_SOFT)
        left = self.chapter_title or self.book_short
        y = 13.0
        self.text(self.l_margin, y, left)
        w = self.get_string_width(left)
        if w > self.epw * 0.7:
            pass
        self.text(self.w - self.r_margin - self.get_string_width(self.book_short), y, self.book_short)
        self.set_draw_color(*RULE)
        self.set_line_width(0.2)
        self.line(self.l_margin, y + 2.2, self.w - self.r_margin, y + 2.2)
        self.set_line_width(0.22)

    def footer(self):
        if self.page_no() <= self._skip_header:
            return
        self.set_y(self.h - self.b_margin + 2.5)
        self.set_font("cjk", size=8.8)
        self.set_text_color(*INK_SOFT)
        self.cell(self.epw, 4, str(self.page_no()), align="C")

    def new_page(self, chapter_header: str | None = None):
        if chapter_header is not None:
            self.chapter_title = chapter_header
        self.add_page()

    def open_cover(self, title, subtitle, meta_lines):
        """封面页。"""
        self._skip_header = 1
        self.add_page()
        self.set_font("hei", size=9.5)
        self.set_text_color(*INK_SOFT)
        self.text(self.l_margin, 40, "SCNet · 课程实践配套文档")
        self.set_draw_color(*ACCENT)
        self.set_line_width(1.4)
        self.line(self.l_margin, 46, self.l_margin + 30, 46)
        self.set_line_width(0.22)
        self.set_font("hei", size=34)
        self.set_text_color(*INK)
        self.set_xy(self.l_margin, 96)
        self.multi_cell(self.epw, 15, title, align="L", new_x="LMARGIN", new_y="NEXT")
        self.set_font("cjk", size=14.5)
        self.set_text_color(*ACCENT)
        self.set_xy(self.l_margin, self.get_y() + 4)
        self.multi_cell(self.epw, 9, subtitle, new_x="LMARGIN", new_y="NEXT")
        self.set_font("cjk", size=10.6)
        self.set_text_color(*INK_SOFT)
        y = self.h - 96
        for ln in meta_lines:
            self.text(self.l_margin, y, ln)
            y += 7.2
        return self

    # ---------------------------------------------------------------- 工具
    @property
    def top_y(self):
        """新页起始可用 y（页眉下方）。"""
        return self.t_margin + 10.0

    def _sw(self, s, font, size):
        self.set_font(font, size=size)
        return self.get_string_width(s)

    def _wrap(self, text, font, size, maxw, indent=0.0):
        text = prep_bold(text)
        segs = str(text).split(chr(10))
        if len(segs) == 1:
            return self._wrap_one(segs[0], font, size, maxw, indent)
        out = []
        for i, seg in enumerate(segs):
            out.extend(self._wrap_one(seg, font, size, maxw, indent if i == 0 else 0.0))
        return out or [""]

    def _wrap_one(self, text, font, size, maxw, indent=0.0):
        self.set_font(font, size=size)
        toks = tokenize(text)
        lines, cur, curw = [], [], 0.0
        avail = maxw - indent
        def push():
            nonlocal cur, curw
            while cur and cur[-1] == " ":
                cur.pop()
            lines.append("".join(cur))
            cur, curw = [], 0.0
        for tok in toks:
            tw = 0.0 if tok == MARK else self.get_string_width(tok)
            if curw + tw <= avail + 0.3:
                cur.append(tok)
                curw += tw
                continue
            if tok == " ":
                push()
                avail = maxw
                continue
            if tw > maxw:                       # 超长 token：硬切
                if cur:
                    push()
                pieces, piece = [], ""
                for ch in tok:
                    if self.get_string_width(piece + ch) > maxw:
                        pieces.append(piece)
                        piece = ch
                    else:
                        piece += ch
                if piece:
                    pieces.append(piece)
                if len(pieces) > 1:
                    lines.extend(pieces[:-1])
                    cur, curw = [pieces[-1]], self.get_string_width(pieces[-1])
                else:
                    cur, curw = pieces, self.get_string_width("".join(pieces))
                avail = maxw
                continue
            if tok[0] in NO_START and cur:      # 避头：标点不能行首
                move = cur.pop()
                line = "".join(cur).rstrip()
                lines.append(line)
                cur, curw = [move, tok], self.get_string_width(move + tok)
                avail = maxw
                continue
            if cur and cur[-1] and cur[-1][-1] in NO_END:   # 避尾：前引号不能行尾
                move = cur.pop()
                lines.append("".join(cur).rstrip())
                cur, curw = [move, tok], self.get_string_width(move + tok)
                avail = maxw
                continue
            push()
            cur, curw = [tok], tw
            avail = maxw
        while cur and cur[-1] == " ":
            cur.pop()
        if cur:
            lines.append("".join(cur))
        lines = [ln for ln in lines] or [""]
        # 跨行的粗体标记：上一行未闭合则本行补开，本行未闭合则补闭
        out, pending = [], False
        for ln in lines:
            if pending and not ln.startswith(MARK):
                ln = MARK + ln
            if ln.count(MARK) % 2:
                ln = ln.rstrip() + MARK
                pending = True
            else:
                pending = False
            out.append(ln)
        return out

    def _space(self, mm):
        if mm:
            self.set_y(self.get_y() + mm)

    def need(self, mm):
        if self.get_y() + mm > self.h - self.b_margin:
            self.new_page()

    @staticmethod
    def _runs(text, base_font):
        parts = re.split("(" + MARK + "[^" + MARK + "]+" + MARK + ")", str(text))
        out = []
        for p in parts:
            if not p:
                continue
            if len(p) >= 2 and p[0] == MARK and p[-1] == MARK:
                body = p[1:-1].replace(MARK, "")
                if body:
                    out.append((body, "hei"))
            else:
                body = p.replace(MARK, "")
                if body:
                    out.append((body, base_font))
        return out or [(str(text).replace(MARK, ""), base_font)]

    def _put_line(self, ln, x, y, font, size, color, justify_to=None):
        runs = self._runs(ln, font)
        if justify_to:
            lw = sum(self._sw(t, f, size) for t, f in runs)
            nrun = len(runs)
            nsp = sum(1 for t, _ in runs if t == " ")
            extra = justify_to - lw
            gap = extra / (nsp if nsp else max(nrun - 1, 1)) if extra > 0 and nrun > 1 else 0
        else:
            gap = 0
        self.set_text_color(*color)
        for t, f in runs:
            self.set_font(f, size=size)
            if f == "hei":
                self.set_text_color(*color)
            self.text(x, y, t)
            x += self.get_string_width(t) + (gap if t == " " else 0)

    def run_width(self, ln, font, size):
        return sum(self._sw(t, f, size) for t, f in self._runs(ln, font))

    # ---------------------------------------------------------------- 段落
    def para(self, text, size=10.5, lead=1.62, indent=0.0, font="cjk", color=INK,
             justify=True, after=2.8, before=0.0, align="L", wrap=True):
        self.need(size * 0.3528 * lead * 2.2)
        self._space(before)
        maxw = self.epw - indent
        lines = self._wrap(text, font, size, maxw, indent) if wrap else [text]
        lh = size * PT2MM * lead
        y = self.get_y()
        for i, ln in enumerate(lines):
            x = self.l_margin + (indent if i == 0 else 0)
            lw = self.run_width(ln, font, size)
            if align == "C":
                x = self.l_margin + (maxw - lw) / 2
            elif align == "R":
                x = self.l_margin + maxw - lw
            jt = None
            if justify and align == "L" and i < len(lines) - 1:
                jt = maxw - indent if i > 0 else maxw
            self._put_line(ln, x, y + size * PT2MM, font, size, color,
                           justify_to=jt)
            y += lh
        self.set_y(y + after)

    def gap(self, mm=3.0):
        self._space(mm)

    def rule(self, color=RULE, w=None):
        self.need(6)
        self.set_draw_color(*color)
        y = self.get_y() + 1.5
        self.line(self.l_margin, y, self.l_margin + (w or self.epw), y)
        self.set_y(y + 3.5)

    # ---------------------------------------------------------------- 标题
    def chapter(self, no, title, abstract=""):
        label = f"第 {no} 章" if no is not None else ""
        self.new_page(chapter_header=(f"{label}　{title}" if no is not None else title))
        self.fig_no = 0
        self.tab_no = 0
        self.set_y(58)
        self.set_font("hei", size=13)
        self.set_text_color(*ACCENT)
        self.text(self.l_margin, 62, label)
        self.set_font("hei", size=26)
        self.set_text_color(*INK)
        self.text(self.l_margin, 62 + 13, title)
        self.set_draw_color(*ACCENT)
        self.set_line_width(1.0)
        yl = 62 + 13 + 9
        self.line(self.l_margin, yl, self.l_margin + 44, yl)
        self.set_line_width(0.22)
        self.set_y(yl + 10)
        self.entries.append({"level": 0, "name": f"{label}　{title}".strip(), "page": self.page_no()})
        self.start_section(f"{label} {title}".strip(), level=0)
        if abstract:
            self.box("kai", abstract, head="Abstract", kind="abstract")

    def h2(self, num, title, before=6.5):
        self.need(26)
        self._space(before)
        self.set_font("hei", size=15)
        self.set_text_color(*INK)
        y = self.get_y()
        self.text(self.l_margin, y + 5.6, f"{num}　{title}")
        self.set_draw_color(*RULE)
        self.set_line_width(0.35)
        self.line(self.l_margin, y + 8.4, self.w - self.r_margin, y + 8.4)
        self.set_line_width(0.22)
        self.set_y(y + 11.2)
        self.entries.append({"level": 1, "name": f"{num}　{title}", "page": self.page_no()})
        self.start_section(f"{num} {title}", level=1)

    def h3(self, num, title, before=4.5):
        self.need(20)
        self._space(before)
        self.set_font("hei", size=12)
        self.set_text_color(*ACCENT)
        self.text(self.l_margin, self.get_y() + 4.8, f"{num}　{title}")
        self.set_y(self.get_y() + 7.4)
        self.entries.append({"level": 2, "name": f"{num}　{title}", "page": self.page_no()})
        self.start_section(f"{num} {title}", level=2)

    def h4(self, title, before=3.5):
        self.need(14)
        self._space(before)
        self.set_font("hei", size=10.8)
        self.set_text_color(*INK)
        self.text(self.l_margin, self.get_y() + 4.2, title)
        self.set_y(self.get_y() + 6.2)

    def step(self, n, title, before=5.0):
        """操作步骤小标题：带圆形序号。"""
        self.need(20)
        self._space(before)
        y = self.get_y()
        self.set_fill_color(*ACCENT)
        self.set_text_color(255, 255, 255)
        self.set_font("hei", size=9.6)
        self.circle(x=self.l_margin + 3.4, y=y + 3.6, r=3.4, style="F")
        w = self.get_string_width(str(n))
        self.text(self.l_margin + 3.4 - w / 2, y + 3.6 + 3.4, str(n))
        self.set_text_color(*INK)
        self.set_font("hei", size=11.4)
        self.text(self.l_margin + 9.4, y + 6.0, title)
        self.set_y(y + 9.6)

    def circle(self, x, y, r, style="F"):
        # fpdf2 无 circle：用贝塞尔近似
        k = 0.5522847498 * r
        self.ellipse(x - r, y - r, 2 * r, 2 * r, style=style)

    # ---------------------------------------------------------------- 框
    def box(self, body_font, body, head="", kind="info", items=None, rows=None,
            before=2.0, after=3.4, size=9.9, bullets_font=None):
        """带底色与左色条的提示框 / 章引言框。"""
        if kind == "abstract":
            fg, bg, line = INK_SOFT, (249, 250, 252), ACCENT
            head_font, head_size = "hei", 11.0
            body_size = 11.6
        else:
            c = CALLOUT[kind]
            fg, bg, default_head = _rgb(c[0]), _rgb(c[1]), c[2]
            head = head or default_head
            line = fg
            head_font, head_size = "hei", 10.0
            body_size = size
        pad = 4.2
        inner = self.epw - 2 * pad - 2.6
        self.set_font(body_font, size=body_size)
        lines = self._wrap(body, body_font, body_size, inner) if body else []
        lh = body_size * PT2MM * 1.62
        ih = 0.0
        item_lines = []
        if items:
            for it in items:
                ls = self._wrap(it, body_font, body_size, inner - 4.6)
                item_lines.append(ls)
                ih += len(ls) * lh
        hh = (head_size * PT2MM * 1.4 + 2.6) if head else 0
        total = pad * 2 + hh + len(lines) * lh + ih
        self.need(min(total + 3, 48))
        self._space(before)
        x0, y0 = self.l_margin, self.get_y()
        self.set_fill_color(*bg)
        self.set_draw_color(*bg)
        self.rect(x0, y0, self.epw, total, style="F")
        self.set_draw_color(*line)
        self.set_line_width(1.0)
        self.rect(x0, y0, 1.1, total, style="FD")
        self.set_line_width(0.22)
        y = y0 + pad
        if head:
            self.set_font(head_font, size=head_size)
            self.set_text_color(*line if kind != "abstract" else INK_SOFT)
            self.text(x0 + pad + 2.6, y + head_size * PT2MM, head)
            y += head_size * PT2MM * 1.4 + 2.6
        self.set_font(body_font, size=body_size)
        for ln in lines:
            self._put_line(ln, x0 + pad + 2.6, y + body_size * PT2MM, body_font, body_size,
                           INK if kind != "abstract" else INK_SOFT)
            y += lh
        if items:
            self.set_font(bullets_font or "cjk", size=body_size)
            self.set_text_color(*line if kind != "abstract" else INK_SOFT)
            for ls in item_lines:
                self.text(x0 + pad + 2.6, y + body_size * PT2MM, "•")
                self.set_font(body_font, size=body_size)
                self._put_line(ls[0], x0 + pad + 7.2, y + body_size * PT2MM, body_font, body_size, INK)
                for extra in ls[1:]:
                    y += lh
                    self._put_line(extra, x0 + pad + 7.2, y + body_size * PT2MM, body_font,
                                   body_size, INK)
                y += lh
        self.set_y(y0 + total + after)
        self.set_text_color(*INK)

    def callout(self, kind, head, body="", items=None):
        self.box("cjk", body, head=head, kind=kind, items=items)

    # ---------------------------------------------------------------- 列表
    def bullets(self, items, size=10.3, lead=1.6, marker="•", indent=5.2, after=2.6,
                font="cjk", color=INK):
        lh = size * PT2MM * lead
        self.need(lh * 1.6)
        self._space(0.8)
        for it in items:
            lines = self._wrap(it, font, size, self.epw - indent)
            y = self.get_y()
            self.set_font("cjk", size=size)
            self.set_text_color(*ACCENT)
            self.text(self.l_margin + indent - 4.6, y + size * PT2MM, marker)
            self.set_text_color(*color)
            for i, ln in enumerate(lines):
                self._put_line(ln, self.l_margin + indent, y + size * PT2MM + i * lh, font, size,
                               color)
            self.set_y(y + lh * len(lines) + 1.0)
            self.need(lh * 1.4)
        self._space(after)

    def checklist(self, items, size=10.3, lead=1.6, after=2.6, font="cjk", color=INK):
        """提交前自检清单：用方框符号作项目符号。"""
        return self.bullets(items, size=size, lead=lead, marker=chr(0x25A1),
                            after=after, font=font, color=color)

    def numbered(self, items, size=10.3, lead=1.6, start=1, indent=7.6, after=2.6,
                 font="cjk", color=INK, bold_marker=True):
        lh = size * PT2MM * lead
        self.need(lh * 1.6)
        self._space(0.8)
        for i, it in enumerate(items, start):
            mk = f"{i}."
            lines = self._wrap(it, font, size, self.epw - indent)
            y = self.get_y()
            self.set_font("hei" if bold_marker else font, size=size)
            self.set_text_color(*ACCENT)
            self.text(self.l_margin + indent - self.get_string_width(mk) - 1.6,
                      y + size * PT2MM, mk)
            self.set_text_color(*color)
            for j, ln in enumerate(lines):
                self._put_line(ln, self.l_margin + indent, y + size * PT2MM + j * lh, font, size,
                               color)
            self.set_y(y + lh * len(lines) + 1.0)
            self.need(lh * 1.4)
        self._space(after)

    # ---------------------------------------------------------------- 代码
    def code(self, text, size=9.0, lead=1.46, after=3.4, tag="", maxw=None,
             indent=4.0, wrap=True):
        raw = text.rstrip("\n").split("\n")
        lines = []
        self.set_font("mono", size=size)
        lim = (maxw or self.epw) - 2 * indent
        for ln in raw:
            if wrap:
                while self.get_string_width(ln) > lim and len(ln) > 2:
                    cut = len(ln)
                    while cut > 1 and self.get_string_width(ln[:cut]) > lim - 6:
                        cut -= 1
                    lines.append(ln[:cut])
                    ln = "      " + ln[cut:].lstrip()
            lines.append(ln)
        lh = size * PT2MM * lead
        total = len(lines) * lh + 7.2
        self.need(min(total, 55))
        self._space(1.0)
        y0 = self.get_y()
        self.set_fill_color(*CODE_BG)
        self.rect(self.l_margin, y0, self.epw, total, style="F")
        self.set_draw_color(*RULE)
        self.set_line_width(0.2)
        self.rect(self.l_margin, y0, self.epw, total, style="D")
        self.set_line_width(0.22)
        if tag:
            self.set_font("hei", size=7.8)
            self.set_text_color(*INK_SOFT)
            self.text(self.l_margin + indent, y0 + 4.6, tag)
        y = y0 + (8.6 if tag else 4.0)
        for ln in lines:
            self._code_line(ln, self.l_margin + indent, y + size * PT2MM, size)
            y += lh
        self.set_y(y0 + total + after)

    _CJK = re.compile("([\u2e80-\uffef\u3000-\u303f]+)")

    def mixed_text(self, x, y, text, size, base_font="mono", color=None):
        """按 CJK / 非 CJK 分段绘制，解决等宽字体缺中文字形的问题。"""
        if color is not None:
            self.set_text_color(*color)
        for seg in self._CJK.split(text):
            if not seg:
                continue
            fam = "cjk" if self._CJK.fullmatch(seg) else base_font
            self.set_font(fam, size=size)
            self.text(x, y, seg)
            x += self.get_string_width(seg)
        return x

    _COMMENT_AT = re.compile(r"(?<![\w/\\-])(#|//)")

    def _code_line(self, text, x, y, size):
        cut = None
        for m in self._COMMENT_AT.finditer(text):
            if m.group(1) == "#" and "'" in text[:m.start()] or '"' in text[:m.start()]:
                continue
            cut = m.start()
            break
        if text.lstrip().startswith(("#", "//")) and cut == (len(text) - len(text.lstrip())):
            cut = len(text) - len(text.lstrip())
        self.set_font("mono", size=size)
        if cut is None:
            self.mixed_text(x, y, text, size)
        else:
            self.mixed_text(x, y, text[:cut], size, color=CODE_INK)
            w = 0.0
            for seg in self._CJK.split(text[:cut]):
                if not seg:
                    continue
                fam = "cjk" if self._CJK.fullmatch(seg) else "mono"
                self.set_font(fam, size=size)
                w += self.get_string_width(seg)
            self.mixed_text(x + w, y, text[cut:], size, color=_rgb("#7A8794"))

    def terminal(self, prompt_lines, **kw):
        """模拟终端输出（深色底）。"""
        text = "\n".join(prompt_lines)
        lines = text.rstrip("\n").split("\n")
        size = kw.get("size", 8.6)
        lh = size * PT2MM * 1.5
        total = len(lines) * lh + 7
        self.need(min(total, 55))
        y0 = self.get_y()
        self.set_fill_color(28, 33, 40)
        self.rect(self.l_margin, y0, self.epw, total, style="F")
        y = y0 + 4.2
        for ln in lines:
            if ln.startswith("$") or ln.startswith(">"):
                col = (126, 204, 156)
            elif ln.lstrip().startswith("!"):
                col = (238, 190, 96)
            elif ln.lstrip().startswith("×") or "Error" in ln or "Traceback" in ln:
                col = (240, 152, 142)
            else:
                col = (226, 232, 240)
            self.mixed_text(self.l_margin + 4, y + size * PT2MM, ln[:130], size, color=col)
            y += lh
        self.set_y(y0 + total + 3.2)
        self.set_text_color(*INK)

    # ---------------------------------------------------------------- 表格
    @staticmethod
    def _cell_x(xx, wd, wdt, al, pad):
        if al == "C":
            return xx + (wd - wdt) / 2
        if al == "R":
            return xx + wd - pad - wdt
        return xx + pad

    def table(self, header, rows, widths=None, size=9.0, head_size=9.0, lead=1.42,
              caption="", aligns=None, note="", zebra=True, cont_caption=True):
        ncol = len(header) if header else max(len(r) for r in rows)
        for r in rows:
            if len(r) < ncol:
                r = list(r) + [""] * (ncol - len(r))
        rows = [list(r) + [""] * (ncol - len(r)) for r in rows]
        if widths is None:
            widths = [1.0] * ncol
        tot = sum(widths)
        widths = [w / tot * self.epw for w in widths]
        aligns = (aligns or ["L"] * ncol)
        pad = 1.9
        if caption:
            self.tab_no += 1
            self.need(14)
            self._space(2.2)
            self.set_font("hei", size=9.4)
            self.set_text_color(*CAPTION)
            self.text(self.l_margin, self.get_y() + 4.2, caption)
            self.set_y(self.get_y() + 6.4)

        def hl(txt, col, font, fs):
            return self._wrap(str(txt), font, fs, widths[col] - 2 * pad)

        hh = 0.0
        if header:
            hh = max(len(hl(t, c, "hei", head_size)) for c, t in enumerate(header)) * \
                (head_size * PT2MM * lead) + 2 * pad
        heights = []
        for r in rows:
            nl = max(len(hl(r[c], c, "cjk", size)) for c in range(ncol))
            heights.append(max(size * PT2MM * lead + 2.6, nl * size * PT2MM * lead + 2 * pad))

        def draw_head(y):
            if not header or hh == 0:
                return y
            self.set_fill_color(*TABLE_HEAD)
            self.set_draw_color(*RULE)
            self.rect(self.l_margin, y, self.epw, hh, style="FD")
            xx = self.l_margin
            for c, t in enumerate(header):
                ls = hl(t, c, "hei", head_size)
                yy = y + pad
                for ln in ls:
                    wdt = self.run_width(ln, "hei", head_size)
                    tx = self._cell_x(xx, widths[c], wdt, aligns[c], pad)
                    self._put_line(ln, tx, yy + head_size * PT2MM, "hei", head_size, INK)
                    yy += head_size * PT2MM * lead
                xx += widths[c]
            return y + hh

        self.need(hh + (heights[0] if heights else 6) + 4)
        y = draw_head(self.get_y())
        for ri, (r, hgt) in enumerate(zip(rows, heights)):
            if y + hgt > self.h - self.b_margin:
                self.new_page()
                y = self.get_y()
                if caption and cont_caption:
                    self.set_font("cjk", size=8.4)
                    self.set_text_color(*INK_SOFT)
                    self.text(self.l_margin, y + 3.6, caption + "（续）")
                    y += 6.4
                y = draw_head(y)
            if zebra and ri % 2 == 1:
                self.set_fill_color(*TABLE_ALT)
                self.rect(self.l_margin, y, self.epw, hgt, style="F")
            self.set_draw_color(*RULE)
            self.set_line_width(0.2)
            self.rect(self.l_margin, y, self.epw, hgt, style="D")
            self.set_line_width(0.22)
            xx = self.l_margin
            for c in range(ncol):
                if c:
                    self.set_draw_color(*RULE)
                    self.line(xx, y, xx, y + hgt)
                yy = y + pad
                for ln in hl(r[c], c, "cjk", size):
                    wdt = self.run_width(ln, "cjk", size)
                    self._put_line(ln, self._cell_x(xx, widths[c], wdt, aligns[c], pad),
                                   yy + size * PT2MM, "cjk", size, INK)
                    yy += size * PT2MM * lead
                xx += widths[c]
            y += hgt
        self.set_y(y + 1.4)
        if note:
            self.set_font("cjk", size=8.4)
            self.set_text_color(*INK_SOFT)
            lh2 = 8.4 * PT2MM * 1.45
            for ln in self._wrap(note, "cjk", 8.4, self.epw):
                self.text(self.l_margin, self.get_y() + 8.4 * PT2MM, ln)
                self.set_y(self.get_y() + lh2)
        self._space(2.6)
        self.set_text_color(*INK)

    # ---------------------------------------------------------------- 插图
    def figure(self, img, caption, width=None, maxh=112.0, src=""):
        path = img if os.path.isabs(img) else (
            os.path.join(ASSET_DIR, img) if not img.startswith("fig") else os.path.join(FIG_DIR, img))
        for cand in (path, os.path.join(ASSET_DIR, img), os.path.join(FIG_DIR, img)):
            if os.path.exists(cand):
                path = cand
                break
        if not os.path.exists(path):
            raise FileNotFoundError("缺少插图文件：" + path)
        with Image.open(path) as im:
            iw, ih = im.size
        ar = ih / iw
        w = min(width or self.epw, self.epw)
        h = w * ar
        if h > maxh:
            h = maxh
            w = h / ar
        block = h + 14 + (4 if src else 0)
        if block > (self.h - self.b_margin - self.get_y()):
            if block < (self.h - self.b_margin - self.top_y):
                self.new_page()
        self._space(2.2)
        x = self.l_margin + (self.epw - w) / 2
        y = self.get_y()
        self.set_draw_color(*RULE)
        self.set_line_width(0.2)
        self.image(path, x, y, w=w, h=h)
        self.rect(x, y, w, h, style="D")
        self.set_y(y + h + 1.6)
        self.fig_no += 1
        self.set_font("cjk", size=9.2)
        self.set_text_color(*CAPTION)
        cap = caption if caption.startswith("图") else caption
        for ln in self._wrap(cap, "cjk", 9.2, self.epw - 4):
            lw = self.get_string_width(ln)
            self.text(self.l_margin + (self.epw - lw) / 2, self.get_y() + 9.2 * PT2MM * 1.05, ln)
            self.set_y(self.get_y() + 9.2 * PT2MM * 1.5)
        if src:
            self.set_font("cjk", size=7.8)
            self.set_text_color(*INK_SOFT)
            lw = self.get_string_width(src)
            self.text(self.l_margin + (self.epw - lw) / 2, self.get_y() + 7.8 * PT2MM, src)
            self.set_y(self.get_y() + 7.8 * PT2MM * 1.5)
        self.set_text_color(*INK)
        self._space(3.0)

    def formula(self, text, note="", size=11.4, before=2.4, after=3.4):
        self.need(14)
        self._space(before)
        self.set_font("cjk", size=size)
        self.set_text_color(*INK)
        lh = size * PT2MM * 1.55
        lines = [text]
        y = self.get_y()
        for ln in lines:
            lw = self.get_string_width(ln)
            self.text(self.l_margin + (self.epw - lw) / 2, y + size * PT2MM * 1.15, ln)
            y += lh
        if note:
            self.set_font("cjk", size=8.5)
            self.set_text_color(*INK_SOFT)
            for ln in self._wrap(note, "cjk", 8.5, self.epw - 16):
                lw = self.get_string_width(ln)
                self.text(self.l_margin + (self.epw - lw) / 2, y + 8.5 * PT2MM, ln)
                y += 8.5 * PT2MM * 1.45
        self.set_y(y + after)
        self.set_text_color(*INK)

    # ---------------------------------------------------------------- 目录
    def draw_toc(self, entries, n_pages):
        """按上一趟收集到的条目手绘目录，占满 n_pages 页。"""
        self.chapter_title = "目　录"
        self.add_page()
        self.set_font("hei", size=22)
        self.set_text_color(*INK)
        self.set_y(26)
        self.text(self.l_margin, self.get_y() + 9, "目　录")
        self.set_y(self.get_y() + 16)
        line_h = {0: 9.2, 1: 7.7, 2: 6.8}
        fonts = {0: ("hei", 10.8), 1: ("cjk", 9.7), 2: ("cjk", 8.9)}
        y = self.get_y()
        bottom = self.h - self.b_margin - 2
        first = True
        for e in entries:
            lvl = min(e["level"], 2)
            fam, size = fonts[lvl]
            indent = {0: 0, 1: 5, 2: 13}[lvl]
            name, page = e["name"], str(e["page"])
            if y + line_h[lvl] > bottom:
                self.add_page()
                y = self.t_margin + 8
            w = self._sw(name, fam, size)
            pw = self._sw(page, "cjk", size)
            while indent + w + 7 + pw > self.epw and size > 7.0:
                size -= 0.2
                w = self._sw(name, fam, size)
                pw = self._sw(page, "cjk", size)
            self.set_font(fam, size=size)
            self.set_text_color(*(INK if lvl != 2 else INK_SOFT))
            self.text(self.l_margin + indent, y + size * PT2MM * 1.15, name)
            x1 = self.l_margin + indent + w + 2.0
            x2 = self.w - self.r_margin - pw - 1.4
            self.set_text_color(*RULE)
            dw = self._sw("·", fam, size)
            while x1 < x2:
                self.text(x1, y + size * PT2MM * 1.15, "·")
                x1 += dw
            self.set_text_color(*(INK if lvl != 2 else INK_SOFT))
            self.set_font("cjk", size=size)
            self.text(self.w - self.r_margin - pw, y + size * PT2MM * 1.15, page)
            y += line_h[lvl]
            if lvl == 0 and not first:
                y += 1.6
            first = False
        while self.page_no() - 1 < n_pages:
            self.add_page()
        self.toc_pages_used = self.page_no() - 1
        return self.page_no()


def _render_once(book_title, subtitle, meta_lines, content_fn, out, short, toc_entries,
                 toc_pages):
    pdf = Manual(short, book_title)
    pdf.set_title(book_title)
    pdf.set_author("依据 works/ 五个综合项目的源码与运行产物整理")
    pdf.set_subject("《Python 在财务管理中的应用》综合实验项目操作手册")
    pdf.set_keywords("Python, 财务管理, 操作手册, 货币时间价值, WACC, NPV, IRR, 本量利, 杜邦分析, 财务预测")
    pdf._skip_header = 1
    pdf.open_cover(book_title, subtitle, meta_lines)
    pdf.draw_toc(toc_entries, toc_pages)
    content_fn(pdf)
    if out:
        pdf.output(out)
    return pdf


def build(book_title, subtitle, meta_lines, content_fn, out_pdf, short="Python 财务应用操作手册",
          toc_pages=None, log=True, max_pass=8):
    """多趟排版：逐趟修正目录页数与页码，直到目录条目与预留页数同时收敛。"""
    import copy
    entries, n = [], (toc_pages or 4)
    for it in range(max_pass):
        pdf = _render_once(book_title, subtitle, meta_lines, content_fn, None, short,
                           copy.deepcopy(entries), n)
        new_entries = copy.deepcopy(pdf.entries)
        used = pdf.toc_pages_used
        if log:
            print(f"pass {it + 1}: toc_pages={n} used={used} entries={len(new_entries)} "
                  f"pages={pdf.pages_count}")
        converged = (used == n) and (new_entries == entries)
        entries = new_entries
        n = max(used, 1)
        if converged:
            break
    _render_once(book_title, subtitle, meta_lines, content_fn, out_pdf, short, entries, n)
    if log:
        print("written:", out_pdf, round(os.path.getsize(out_pdf) / 1024 / 1024, 2), "MB",
              "toc_pages:", n)
    return out_pdf
