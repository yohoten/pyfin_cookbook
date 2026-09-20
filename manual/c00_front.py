# -*- coding: utf-8 -*-
"""manual/c00_front.py —— 前言 + 第 1 章（环境与通用约定）"""
from __future__ import annotations

ROOT = r"F:\（8）Desktop\财务会计实务与应用\Python财务应用\works"


def front(doc):
    doc.chapter(None, "前言：怎样用这本手册", abstract=(
        "这本手册不是教材的复述，而是一份“照着做就能跑通”的操作记录。"
        "它把 works/ 目录下五个 Python 财务项目的启动方式、输入口径、"
        "参数含义、结果读法与踩坑位置逐一写清楚，"
        "让没有编程基础的财务专业学生也能独立完成全部实验。"))

    doc.h2("0.1", "这本手册解决什么问题")
    doc.para(
        "works/ 下的五个项目是《Python 在财务管理中的应用》课程的综合性实验作业：每个项目都自带源码、"
        "示例数据、图表与报告输出。它们的共同特点是**程序已经写完，但需要有人把它跑起来、"
        "把结果读明白、再写进实验报告**。真正卡住同学的往往不是财务知识，而是下面这些琐碎问题：")
    doc.bullets([
        "终端里输入 python main.py 提示“不是内部或外部命令”，或者 ModuleNotFoundError；",
        "不知道哪些参数要填小数（0.06）、哪些要填百分数（6%），结果算出错一位的利率；",
        "图表生成出来中文全是方框，或者图保存在了意料之外的文件夹；",
        "程序跑出一大堆表格，不知道哪一个才是作业要求的答案；",
        "把结果抄进报告时口径写错（元/万元/亿元混用），被老师判为“数据不可复现”。",
    ])
    doc.para(
        "本手册针对这五类问题给出确定答案：所有命令、参数默认值、输出文件名与关键数值，"
        "都是从项目源码与已生成产物中逐条核对而来，并在正文中标明出处。"
        "你既可以按章节顺序从头做到尾，也可以只翻到自己要做的那一个项目。")

    doc.h2("0.2", "五个项目的定位与阅读顺序")
    doc.para("下表按“先打基础、再做决策、后成报告”的顺序排列五个项目，"
             "也是本手册第 2 至第 6 章的顺序。")
    doc.table(
        ["章", "项目文件夹", "程序入口", "对应课程知识", "主要产物"],
        [["第 2 章", "01-货币时间价值与资本成本计算器", "main.py / gui.py", "第 3、4 章：复利年金、资本成本",
          "7 张图 + 3 个 Excel + 图形界面"],
         ["第 3 章", "02-投资项目全流程评价系统", "main.py", "第 5 章：NPV/IRR/互斥/资本限额/敏感性",
          "39 张图 + Markdown/Word 报告"],
         ["第 4 章", "03-综合成本与经营决策分析平台", "main.py", "第 7、8、9 章：成本核算、差异分析、短期决策",
          "17 张图 + 2 份 Excel 底稿 + 2 份报告"],
         ["第 5 章", "04-财务报表分析报告", "run_all.py", "第 10 章：结构、趋势、指标、杜邦分析",
          "12 张图 + 15 表工作簿 + HTML 报告"],
         ["第 6 章", "05-财务预测与预算管理实验报告", "run_all.py", "第 11 章：预测、预算、本量利、情景",
          "16 张图 + Word/PDF 实验报告"]],
        widths=[0.9, 3.0, 1.5, 2.9, 2.3],
        caption="表 0-1　五个项目的入口与产物一览",
        aligns=["C", "L", "C", "L", "L"],
        note="入口列写的是最常用的那一个脚本；项目一另有 gui.py 图形界面与 .pyw 双击启动方式，见 2.6 节。")
    doc.figure("fig01_项目地图.png", "图 0-1　五个项目的知识定位与交付物地图", src="本手册自绘")

    doc.h2("0.3", "全书约定")
    doc.para("为了让你不必反复猜测，全书统一采用下面的书写方式。")
    doc.table(
        ["写法", "含义"],
        [["等宽灰底方块中的文字", "需要在终端里输入的命令，或程序输出的原文。以 $ 开头的行表示要敲的命令，"
          "不带 $ 的行是程序回显，不要一起输入。"],
         ["「　」内的中文", "界面上看到的按钮、页签、字段名称，例如点击「计算并生成图表」。"],
         ["路径中的 \\ 与 /", "两者都表示 Windows 路径分隔符，终端里都可以使用；本手册在命令行中统一写 \\，"
          "在正文叙述中统一写 /。"],
         ["**加粗**", "需要特别注意的口径、数值或操作结果。"],
         ["提示 / 说明 / 注意 / 常见错误 / 动手做", "五种侧栏框。前三种是解释与背景，"
          "第四种列出最常见的报错及对策，第五种是给你自己动手验证的小任务。"]],
        widths=[2.2, 6.0], caption="表 0-2　本手册的书写约定", aligns=["L", "L"])

    doc.h3("0.3.1", "利率与金额的口径")
    doc.para("五个项目对“利率”的写法并不完全一致，这是最容易造成结果差 100 倍的地方，"
             "本手册在每一处都会明确标注：")
    doc.table(
        ["项目", "利率输入形式", "金额单位", "举例"],
        [["项目一", "小数（0.06 表示 6%）", "元（资本结构字段建议万元，只用于算比重）",
          "年利率 6% 填 0.06"],
         ["项目二", "小数（--rate 0.1 表示 10%）", "万元（案例数据全部以万元计）", "折现率 8% 填 0.08"],
         ["项目三", "小数（内部数据）", "元", "单价 380 元、固定成本 1,200,000 元"],
         ["项目四", "不使用利率", "元计算、亿元展示", "报表原始单位为元"],
         ["项目五", "小数（比率类指标）", "元计算、亿元展示", "成本率 0.8679 表示 86.79%"]],
        widths=[1.1, 2.3, 2.6, 2.2], caption="表 0-3　五个项目的参数口径差异", aligns=["C", "L", "L", "L"])
    doc.callout("warn", "",
                "把 6% 输成 6 是项目一最高频的错误。程序会在**第二层（硬边界）**直接拦下它，"
                "并给出“错在哪里 + 为什么错 + 怎么改”的三段式提示；"
                "但**如果你绕过校验直接改代码传参，就会得到一个 600% 的荒谬结果**。"
                "任何时候看到“终值大得离谱”，先回去检查利率是不是小数。")

    doc.h2("0.4", "最短路径：如果你只有 30 分钟")
    doc.para("若时间紧张，可以按下面这条最短路径先拿到一份能交差的产物，之后再逐章补齐理解。")
    doc.numbered([
        "确认 Python 可用：在终端执行 python -V，能显示版本号即可（1.3 节）。",
        "进入项目一目录并安装依赖：pip install pandas numpy matplotlib openpyxl pillow（1.6 节）。",
        "在项目一目录执行 python main.py --demo，等待 10 秒左右，outputs/ 目录出现 7 张 PNG 与 2 个 Excel。",
        "把 09_计算结果汇总.xlsx 与其中 2—3 张图复制进实验报告，并在报告里写清运行命令与参数（第 7 章）。",
        "依次对二、三、四、五项目重复第 3 步，各自的一键命令分别是："
        "python main.py、python main.py --scenario all、python run_all.py、python run_all.py --skip-fetch。",
    ])
    doc.callout("tip", "",
                "五个项目的一键命令都是“**在主程序所在目录执行一条命令，产物自动落盘**”。"
                "记住这一点，后面的章节只是把这条命令展开讲清楚。")


def chapter1(doc):
    doc.chapter(1, "开工之前：环境与通用约定", abstract=(
        "工欲善其事，必先利其器。本章把五个项目共同需要的环境一次配好："
        "Python 解释器、虚拟环境、第三方库、中文字体与目录习惯，"
        "并给出六个项目通用的“首次运行自检清单”。"
        "配好一次，后面五章都不用再回头折腾环境。"))

    doc.h2("1.1", "先看清楚要装什么")
    doc.para("五个项目全部基于 Python 3，依赖的第三方库高度重合。下表是**从各项目的 "
             "requirements.txt 与 import 语句中逐个核对**得到的依赖矩阵。")
    doc.table(
        ["库", "作用", "项目一", "项目二", "项目三", "项目四", "项目五"],
        [["numpy", "数值计算、对数与幂运算", "√", "√", "√", "√", "√"],
         ["pandas", "表格读写、数据清洗", "√", "√", "√", "√", "√"],
         ["matplotlib", "绘制图表", "√", "√", "√", "√", "√"],
         ["openpyxl", "读写 .xlsx（含多工作表）", "√", "—", "√", "√", "—"],
         ["python-docx", "生成 Word 报告", "—", "√", "—", "—", "√"],
         ["Pillow", "GUI 图片缩放、界面截图", "√", "—", "—", "—", "√"],
         ["scipy", "线性规划（场景二资源最优组合）", "—", "—", "√", "—", "—"],
         ["statsmodels", "ARIMA 与指数平滑", "—", "—", "—", "—", "√"],
         ["requests", "抓取公开财务数据", "—", "—", "—", "√", "—"],
         ["lxml / bs4", "解析新浪报表页面", "—", "—", "—", "√", "—"]],
        widths=[1.5, 3.0, 0.85, 0.85, 0.85, 0.85, 0.85],
        caption="表 1-1　依赖矩阵（√ 表示该项目运行时需要）",
        aligns=["L", "L", "C", "C", "C", "C", "C"],
        note="tkinter 随 Python 官方安装包自带，不需要用 pip 安装。项目五的数据抓取走的是命令行数据接口，"
             "若网络受限可用 --skip-fetch 使用仓库内已落盘的原始数据（见 6.2 节）。")

    doc.h2("1.2", "目录与文件的组织习惯")
    doc.para("五个项目的目录结构风格接近，都遵循“**入口脚本 + 功能模块 + 输出目录**”三段式。"
             "以项目一为例：")
    doc.code(
        "financial_calculator/\n"
        "├─ main.py                 入口：命令行菜单与 6 个场景\n"
        "├─ gui.py                  入口：tkinter 图形界面（捕获 stdout 复用内核）\n"
        "├─ core.py                 计算内核：13 个纯函数，无界面依赖\n"
        "├─ validators.py           三层参数校验 + 业务解读文字\n"
        "├─ visualize.py            8 个绘图函数（Agg 后端）\n"
        "├─ report.py               Excel / Markdown 导出\n"
        "├─ test_cases.py           自检用例（断言 + 用例簿）\n"
        "├─ requirements.txt        依赖清单\n"
        "└─ outputs/                所有产物的落盘位置（脚本自动创建）",
        tag="目录结构")
    doc.callout("info", "",
                "五个项目都把输出目录锚定在**脚本自身所在目录**，而不是终端当前目录。"
                "也就是说，无论你在哪个文件夹里敲命令，图和数据永远出现在项目自己的 outputs/（或 output/）下。"
                "这一点对排错很重要：找不到产物时，先去项目目录里看，不要在当前目录翻。")

    doc.h2("1.3", "安装 Python 解释器")
    doc.step(1, "确认是否已装")
    doc.terminal(["$ python -V", "Python 3.12.4", "$ pip -V",
                  "pip 24.0 from C:\\Python312\\Lib\\site-packages\\pip (python 3.12)"])
    doc.para("若提示“不是内部或外部命令”，请先用 py 启动器试一次：py -V。"
             "能出版本号说明 Python 已安装但 PATH 未配置，见 1.9 节问题 2。")
    doc.step(2, "下载安装包")
    doc.para("到 python.org 的 Downloads 页面下载 Windows 64 位安装包（建议 3.10 及以上；"
             "五个项目的代码在 3.9—3.12 下均可运行）。")
    doc.step(3, "安装时勾选 Add python.exe to PATH")
    doc.para("安装向导第一屏底部有 **Add python.exe to PATH** 复选框，必须勾选，"
             "否则后续所有 python 命令都无法识别。随后选择 Install Now 即可，"
             "tkinter、pip、IDLE 都会一起装上。")
    doc.step(4, "打开终端并验证")
    doc.para("Windows 上按 Win 键输入 powershell 回车。"
             "若你的系统里同时装了多个 Python，可用 py -3.12 指定版本。")
    doc.callout("warn", "",
                "Windows 自带的“应用执行别名”会把 python 命令指向 Microsoft Store。"
                "如果输入 python 后弹出商店窗口，请在“设置 → 应用 → 高级应用设置 → 应用执行别名”中"
                "关闭 python.exe 与 python3.exe 两个别名。")

    doc.h2("1.4", "虚拟环境：一次配好，五处通用")
    doc.para("虚拟环境（venv）是在项目目录下建一个独立的 Python 副本目录，"
             "把依赖装进这个目录，从而不污染系统 Python，也便于不同项目使用不同版本的库。"
             "课程实验里它不是强制要求，但一旦某天 pip 装坏了环境，你会庆幸自己用了它。")
    doc.figure("fig03_虚拟环境.png", "图 1-1　虚拟环境的创建、激活与提示符变化", src="本手册自绘")
    doc.table(
        ["终端类型", "创建", "激活", "退出"],
        [["PowerShell", "python -m venv .venv", ".venv\\Scripts\\activate", "deactivate"],
         ["CMD（命令提示符）", "python -m venv .venv", ".venv\\Scripts\\activate.bat", "deactivate"],
         ["Git Bash", "python -m venv .venv", "source .venv/Scripts/activate", "deactivate"],
         ["macOS / Linux", "python3 -m venv .venv", "source .venv/bin/activate", "deactivate"]],
        widths=[1.6, 2.0, 2.6, 1.2], caption="表 1-2　各终端下的虚拟环境命令",
        aligns=["L", "L", "L", "C"])
    doc.callout("err", "",
                "PowerShell 报“在此系统上禁止运行脚本”时，说明执行策略限制了 .ps1/.psm1。"
                "两种解决办法：改用 CMD 终端激活；或以管理员身份执行一次 "
                "Set-ExecutionPolicy -Scope CurrentUser RemoteSigned 后重新打开终端。")

    doc.h2("1.5", "VS Code 里的工作方式（推荐）")
    doc.para("如果你不想在终端里来回切换目录，用 VS Code 打开**项目文件夹本身**是最省心的做法："
             "右下角选择解释器（第一次要指向刚装的 Python 或 .venv），"
             "在文件顶部菜单 Terminal → New Terminal 打开的终端会自动位于项目目录，"
             "编辑器右上角的 ▶ 运行按钮等价于在终端里执行 python 当前文件。")
    doc.bullets([
        "文件 → 将文件夹添加到工作区：一次把 works/ 下五个项目都加进来，便于横向对照；",
        "Ctrl + Shift + P → Python: Select Interpreter：切换解释器，注意选中的就是终端里 python 指向的那个；",
        "在 .vscode/settings.json 里设 \"python.analysis.extraPaths\" 指向项目目录，可消除“找不到模块”的红色波浪线"
        "（这只是编辑器提示，不影响运行）。",
    ])

    doc.h2("1.6", "安装依赖")
    doc.para("每个项目都自带 requirements.txt，优先用它：")
    doc.code("# 方式一：用项目自带清单（推荐）\npip install -r requirements.txt\n\n"
             "# 方式二：一次性装齐五个项目的常用库\n"
             "pip install numpy pandas matplotlib openpyxl python-docx scipy requests\n",
             tag="pip")
    doc.para("国内网络下建议加镜像参数，否则常见超时后 pip 会反复重试：")
    doc.code("pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple",
             tag="国内镜像")
    doc.callout("tip", "",
                "如果只需要跑通命令行计算与出图，项目一可以只装 pandas、numpy、matplotlib、openpyxl 四个库；"
                "Pillow 只在图形界面（gui.py）缩放图片和截图时用到，缺失时程序会自动降级而不报错。")

    doc.h2("1.7", "中文字体：图表不乱码的关键")
    doc.para("matplotlib 默认字体不含中文字形，因此五个项目都在代码里显式设置了中文字体候选列表。"
             "下表是**从各项目源码中抄出的真实候选顺序**，程序会逐个尝试、命中即用。")
    doc.table(
        ["项目", "源码中设置的中文字体候选", "Windows 是否自带"],
        [["项目一", "Microsoft YaHei、SimHei、Noto Sans CJK SC、WenQuanYi Zen Hei", "是（雅黑/黑体）"],
         ["项目二", "Microsoft YaHei、SimHei、Noto Sans CJK SC、WenQuanYi Zen Hei、"
                   "Arial Unicode MS、DejaVu Sans", "是"],
         ["项目三", "Microsoft YaHei、SimHei", "是"],
         ["项目四", "Microsoft YaHei、SimHei、Noto Sans CJK SC", "是"],
         ["项目五", "Microsoft YaHei、SimHei、SimSun、KaiTi、Arial Unicode MS", "是"]],
        widths=[1.1, 4.6, 1.6], caption="表 1-3　各项目 matplotlib 中文字体候选",
        aligns=["C", "L", "C"],
        note="Windows 中文字体位于 C:\\Windows\\Fonts；若你用的是精简版系统或 Linux，"
             "需要先安装 Noto Sans CJK SC（思源黑体），否则图上的中文会显示成方框。")
    doc.para("验证字体是否生效，最省事的办法是跑一次“一定会出图”的命令，然后放大检查图上的标题："
             "项目一用 python main.py --scene 1，项目二用 python main.py --case CASE-1。"
             "标题、坐标轴、图例三处都正常显示中文，才算通过。")

    doc.h2("1.8", "首次运行自检清单")
    doc.para("下面这份清单请逐项打勾。它覆盖了我在这五个项目里见过的全部环境类问题，"
             "做完这六项，后续章节就不会再被环境问题打断。")
    doc.table(
        ["#", "检查项", "命令或判断依据", "不通过时"],
        [["1", "Python 版本 ≥ 3.9", "python -V", "1.3 节重装并勾选 PATH"],
         ["2", "pip 可用且指向同一解释器", "pip -V（路径应与 python -V 一致）", "改用 python -m pip"],
         ["3", "五个核心库可导入",
          "python -c \"import numpy, pandas, matplotlib, openpyxl\"", "1.6 节安装"],
         ["4", "tkinter 可用（项目一 GUI）", "python -c \"import tkinter\"", "重装 Python 或改用命令行版"],
         ["5", "中文字体存在", "python -c \"import matplotlib.font_manager as fm;"
          "print([f for f in {x.name for x in fm.fontManager.ttflist} if 'YaHei' in f or 'Hei' in f])\"",
          "1.7 节装字体"],
         ["6", "输出目录可写", "在项目目录里新建一个 txt 再删除", "换到非只读盘符，或关闭杀毒软件实时防护"]],
        widths=[0.35, 1.9, 3.9, 1.8], caption="表 1-4　首次运行前的六项自检",
        aligns=["C", "L", "L", "L"])
    doc.callout("do", "",
                "把第 3、5 两项合并成一条命令试一次：\n"
                "python -c \"import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt;"
                "plt.rcParams['font.sans-serif']=['Microsoft YaHei']; plt.plot([1,2],[3,1]);"
                "plt.title('中文测试'); plt.savefig('_font_test.png')\"\n"
                "运行后项目目录里会出现 _font_test.png，打开看标题是不是“中文测试”。"
                "确认无误后把这个测试文件删掉即可。")

    doc.h2("1.9", "环境类常见问题")
    doc.h3("1.9.1", "'python' 不是内部或外部命令")
    doc.para("原因：安装时未勾选 Add python.exe to PATH。三种解法按推荐度排序：")
    doc.numbered([
        "改用 py 启动器：把命令里的 python 换成 py（py -m pip install …、py main.py）；",
        "重装 Python 并勾选 PATH 复选框；",
        "手工把 Python 安装目录与其下 Scripts 目录加入系统环境变量 Path，然后**重新打开**终端。",
    ])
    doc.h3("1.9.2", "ModuleNotFoundError: No module named 'pandas'")
    doc.para("原因：pip 装到的解释器与运行脚本的解释器不是同一个。判断方法是把两条命令对照看：")
    doc.terminal(["$ python -c \"import sys; print(sys.executable)\"",
                  "C:\\Users\\me\\works\\01-…\\.venv\\Scripts\\python.exe",
                  "$ pip -V",
                  "pip 24.0 from C:\\Python312\\Lib\\site-packages\\pip (python 3.12)"])
    doc.para("两者路径不一致即确诊。统一办法：始终用 python -m pip install …，"
             "这样 pip 一定装进当前 python 指向的解释器。")
    doc.h3("1.9.3", "cd 命令跨盘符失败")
    doc.para("在 CMD 里从 C 盘切到 F 盘需要带 /d：cd /d F:\\（8）Desktop\\…。"
             "PowerShell 不需要。此外，works 的父目录名里带有中文括号（8），"
             "整条路径含中文与空格，**请务必给路径加引号**：")
    doc.code('cd "F:\\（8）Desktop\\财务会计实务与应用\\Python财务应用\\works\\01-货币时间价值与资本成本计算器\\'
             'financial_calculator"', tag="进入项目一目录")
    doc.callout("tip", "",
                "最省事的输入方式：在资源管理器中打开项目文件夹，在地址栏输入 cmd 回车，"
                "就会在当前目录打开命令行；或按住 Shift 在文件夹空白处右键 → “在此处打开 PowerShell 窗口”。")
    doc.h3("1.9.4", "产物文件被占用：PermissionError")
    doc.para("Excel 打开着 09_计算结果汇总.xlsx 时再次运行程序，写入会失败并抛出 PermissionError。"
             "关闭 Excel 即可。同理，图片被 Windows 照片查看器锁定时，覆盖写入也会失败。")
    doc.h3("1.9.5", "matplotlib 报找不到后端或无窗口")
    doc.para("五个项目出图全部使用无窗口后端（matplotlib.use(\"Agg\")），"
             "因此**不会弹出图表窗口**，图是直接写成 PNG 文件的。"
             "如果你以为“没弹窗口 = 没出图”，请到 outputs/ 目录按修改时间排序看一眼。")

    doc.h2("1.10", "本章小结")
    doc.bullets([
        "五个项目共用 Python 3 + numpy/pandas/matplotlib 三件套，差异只在 openpyxl、python-docx、scipy、"
        "statsmodels、requests 这几个按需安装的库上；",
        "输出目录锚定脚本自身位置，产物永远在项目目录下的 outputs/ 或 output/；",
        "利率一律填小数、金额单位在各项目间不同，抄结果前先确认口径（表 0-3）；",
        "中文字体靠源码里的候选列表自动匹配，Windows 自带雅黑/黑体即可通过；",
        "环境类报错（找不到模块、找不到命令、乱码、写文件失败）与业务口径类问题要分开处理，"
        "先分清再动手，见第 8 章排障总表。",
    ])
    doc.callout("do", "",
                "现在就把表 1-4 的六项自检做一遍，并在项目一目录里成功执行一次 "
                "python main.py --demo。看到 outputs/ 下出现 7 张 PNG 与 2 个 Excel，本章就算真正过关了。")
