# -*- coding: utf-8 -*-
"""引擎冒烟测试：验证字体、断行、提示框、表格、插图、目录与页码。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import ASSET_DIR, build  # noqa


def content(p):
    p.chapter(1, "样例章节", "这是一段用于验证楷体引言框的文字，包含 English、数字 12345 "
                         "与标点符号，测试断行与禁则是否正常工作，例如句末的句号不能被放到行首。")
    p.h2("1.1", "正文与禁则测试")
    p.para("这是一段较长的中文正文，用来验证像素级断行与两端对齐效果。Python 3.11 版本要求、"
           "pandas.DataFrame 输入、**加粗术语**、以及 `code` 之类的混排都需要正常工作。"
           "括号（全角）与引号“弯引号”在行首行尾的处理称为避头尾禁则，是中文排版的基本要求。")
    p.callout("tip", "提示", "这一格用于演示提示框：绿色左边条 + 浅色底。")
    p.callout("warn", "注意", "口径类提醒。**利率一律输入小数**，例如 6% 要输入 0.06。",
             items=["第一条要点：计息次数 m 必须是正整数；",
                    "第二条要点：金额单位在 WACC 场景下是万元，不是元。"])
    p.callout("err", "常见错误", "ModuleNotFoundError: No module named 'pandas' —— 虚拟环境未激活。")
    p.h3("1.1.1", "代码块")
    p.code("# 安装依赖\npython -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple\n"
           "python main.py --demo   # 一键跑全部场景并出图", tag="命令行")
    p.terminal(["$ python main.py", "请选择功能编号: 5", "✔ WACC 敏感性热力图已生成：outputs/05_WACC敏感性分析.png"])
    p.h3("1.1.2", "列表与表格")
    p.bullets(["复利终值 / 现值（支持年、季、月、日复利）；", "年金终值 / 现值（普通年金 / 预付年金）；",
               "加权平均资本成本 WACC（含敏感性分析）。"])
    p.numbered(["进入项目目录；", "创建并激活虚拟环境；", "安装依赖；", "运行主程序。"])
    p.table(["参数类型", "输入格式", "示例"],
            [["利率 / 税率 / 增长率", "小数", "6% → 0.06"], ["期数 / 年数", "正整数", "10 年 → 10"],
             ["金额", "数值（元）", "100 万 → 1000000"], ["计息次数 m", "1=年 2=半年 4=季 12=月", "月计息 → 12"]],
            widths=[2.2, 2.2, 2.0], caption="表 1.1　输入口径约定", aligns=["L", "L", "L"],
            note="资料来源：works/01-…/financial_calculator/README.md「输入口径」。")
    p.formula("FV = PV × (1 + r/m)^(m·n)", note="其中 m 为每年计息次数，n 为年数。")
    imgs = [f for f in os.listdir(ASSET_DIR) if f.startswith("p1_")]
    if imgs:
        p.figure(imgs[0], f"图 1.1　样例插图（项目原生输出）：{imgs[0]}", maxh=80)
    p.h2("1.2", "第二小节以测试目录多页")
    for i in range(14):
        p.para(f"填充段落 {i + 1}：验证跨页时表格与段落的续排行为，以及页眉页脚在每一页的重复。"
               "这里刻意写长一些，以便制造分页。The quick brown fox jumps over the lazy dog. " * 2)


build("排版引擎冒烟测试", "副标题：图文混排验证", ["版本 v0.1", "日期 2026-09-18"], content,
      os.path.join(os.path.dirname(os.path.abspath(__file__)), "smoke.pdf"))
