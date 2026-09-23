# -*- coding: utf-8 -*-
"""
publish_docs.py — 把 outputs/ 的定稿产物发布到 docs/（交付资产）
====================================================================
``outputs/`` 是**运行产物**目录（被 .gitignore 忽略，每次运行都会覆写）；
``docs/`` 是**交付资产**目录（纳入版本库，供评审方直接查看）。

本脚本负责把前者定稿的内容同步到后者，并完成两件容易出错的事：

1. **按报告发布后的新位置重写插图链接**
   报告生成时以自身所在目录为基准写链接，因此 ``outputs/reports/xxx.md``
   里是 ``../figures/a.png``；复制到 ``docs/`` 后深度少一层，必须改写成
   ``figures/a.png``，否则 39 张图全部断链。
2. **校验链接确实 100% 可达**
   这是防止"报告进了仓库、图没进"的最后一道闸门，校验不通过则退出码非 0。

用法::

    python tools/publish_docs.py              # 发布（含链接重写与校验）
    python tools/publish_docs.py --dry-run    # 只显示将执行的操作
    python tools/publish_docs.py --no-rewrite # 不重写链接（报告与图片同深度时使用）

典型流程::

    1. python main.py                    # 生成产物到 outputs/
    2. python -m tests.test_all          # 确认全绿
    3. python tools/publish_docs.py      # 发布到 docs/
    4. git add docs && git commit        # 提交

退出码：0 成功；1 存在缺失的源文件或插图链接校验失败。
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "outputs"
DOCS_DIR = BASE_DIR / "docs"

FIGURE_SRC = OUTPUT_DIR / "figures"
FIGURE_DST = DOCS_DIR / "figures"
DATA_SRC = OUTPUT_DIR / "data"
DATA_DST = DOCS_DIR / "data"
REPORT_SRC = OUTPUT_DIR / "reports"

IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def _copy_tree(src: Path, dst: Path, pattern: str, dry_run: bool,
               clean: bool = True) -> list:
    """把 ``src`` 下匹配 ``pattern`` 的文件复制到 ``dst``。

    Parameters
    ----------
    src, dst : Path
        源目录与目标目录。
    pattern : str
        glob 模式，如 ``"*.png"``。
    dry_run : bool
        只统计不复制。
    clean : bool
        是否先清空目标目录中同类文件（保证 docs 内不残留已删除的旧图）。

    Returns
    -------
    list of Path
        已复制（或计划复制）的源文件路径列表。
    """
    files = sorted(src.glob(pattern))
    if not files or dry_run:
        return files
    dst.mkdir(parents=True, exist_ok=True)
    if clean:
        for old in dst.glob(pattern):
            old.unlink()
    for item in files:
        shutil.copy2(item, dst / item.name)
    return files


def rewrite_links(report: Path, figure_dir: Path) -> int:
    """按报告发布后的位置重写插图链接。

    只重写"目标文件名能在 ``figure_dir`` 中找到"的链接，其余保持原样
    （避免误改外部图片或示意链接）。

    Parameters
    ----------
    report : Path
        已发布到目标位置的 Markdown 报告路径。
    figure_dir : Path
        目标位置下的图片目录。

    Returns
    -------
    int
        实际改写的链接数量。
    """
    text = report.read_text(encoding="utf-8")
    available = {p.name for p in figure_dir.glob("*.png")}
    changed = 0

    def _replace(match: "re.Match") -> str:
        nonlocal changed
        alt, link = match.group(1), match.group(2)
        name = Path(link).name
        if name not in available:
            return match.group(0)
        try:
            new_link = os.path.relpath(figure_dir / name, start=report.parent)
        except ValueError:          # 跨驱动器（Windows）保守处理
            return match.group(0)
        new_link = Path(new_link).as_posix()
        if new_link != link:
            changed += 1
            return f"![{alt}]({new_link})"
        return match.group(0)

    new_text = IMAGE_PATTERN.sub(_replace, text)
    if changed:
        report.write_text(new_text, encoding="utf-8")
    return changed


def verify_links(report: Path) -> tuple:
    """校验报告中的插图链接是否全部可达。

    Returns
    -------
    (int, list of str)
        ``(链接总数, 不可达链接列表)``。
    """
    text = report.read_text(encoding="utf-8")
    links = IMAGE_PATTERN.findall(text)
    broken = [
        link for _, link in links
        if not (report.parent / link).resolve().exists()
    ]
    return len(links), broken


def main(argv=None) -> int:
    """执行发布流程，返回进程退出码。"""
    parser = argparse.ArgumentParser(
        description="把 outputs/ 的定稿产物发布到 docs/（交付资产目录）",
    )
    parser.add_argument("--dry-run", action="store_true", help="只显示将执行的操作")
    parser.add_argument("--no-rewrite", action="store_true",
                        help="不重写插图链接（仅当报告与图片目录同深度时使用）")
    args = parser.parse_args(argv)

    issues: list = []

    print("=" * 74)
    print("  发布交付资产：outputs/ → docs/")
    print("=" * 74)

    # ---------- 1. 报告（Markdown / Word） ----------
    reports = sorted(REPORT_SRC.glob("投资项目决策评价报告.*"))
    md_reports = [p for p in reports if p.suffix == ".md"]
    if not md_reports:
        issues.append("outputs/reports/ 下没有 Markdown 报告，请先运行 python main.py")

    for path in reports:
        size_kb = path.stat().st_size / 1024
        print(f"  [报告] {path.name:38s} {size_kb:10,.1f} KB → docs/")
        if not args.dry_run:
            DOCS_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, DOCS_DIR / path.name)

    # ---------- 2. 图表 ----------
    figure_files = _copy_tree(FIGURE_SRC, FIGURE_DST, "*.png", args.dry_run)
    print(f"  [图表] {len(figure_files)} 张 PNG → docs/figures/")
    if not figure_files:
        issues.append("outputs/figures/ 下没有 PNG，请先运行 python main.py")

    # ---------- 3. 数据 ----------
    data_files = _copy_tree(DATA_SRC, DATA_DST, "*.csv", args.dry_run)
    print(f"  [数据] {len(data_files)} 个 CSV → docs/data/")
    if not data_files:
        issues.append("outputs/data/ 下没有 CSV，请先运行 python main.py")

    print("-" * 74)
    if args.dry_run:
        print("  （--dry-run：跳过链接重写与校验）")
        return 1 if issues else 0

    # ---------- 4. 重写插图链接（发布后位置与生成时不同） ----------
    if not args.no_rewrite:
        for md in md_reports:
            target = DOCS_DIR / md.name
            if target.exists():
                count = rewrite_links(target, FIGURE_DST)
                print(f"  [链接] {target.name}：重写 {count} 处（→ figures/xxx.png）")

    # ---------- 5. 校验链接可达性 ----------
    for md in md_reports:
        target = DOCS_DIR / md.name
        if not target.exists():
            continue
        total, broken = verify_links(target)
        if broken:
            print(f"  ✗ {target.name}：{len(broken)}/{total} 处插图链接不可达")
            for link in broken[:5]:
                print(f"      - {link}")
            issues.append(f"{target.name} 存在 {len(broken)} 处断链插图")
        else:
            print(f"  ✓ {target.name}：{total}/{total} 处插图链接全部可达")

    print("-" * 74)
    if issues:
        print("  发布未完成，存在问题：")
        for item in issues:
            print(f"    · {item}")
        return 1
    print("  发布完成。下一步：git add docs && git commit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
