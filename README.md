# cookbook：《Python 在财务管理中的应用》课程笔记及实践

本仓库是《Python 在财务管理中的应用》课程的学习实践合集，包含课程课件、随堂代码、财务领域实用脚本、5 个综合实验项目，以及配套编写的项目操作手册。

- **代码托管**：GitHub（远程名 `origin`）与 Gitee（远程名 `gitee`）双远程，主分支 `main`
- **在线主页**：[GitHub Pages 介绍网站](https://yohoten.github.io/pyfin_cookbook/)（仓库根目录 `index.html`；手册阅读页为 `manual.html`）
- **开源许可**：[木兰宽松许可证，第 2 版](LICENSE)（Mulan PSL v2）
- **子模块**：01、03、05 三个综合项目以 Git 子模块形式引入，克隆后需额外初始化（见「快速开始」）

## 目录结构

```text
Python财务应用/
├── 01-Python基础应用/              # 随堂练习 Notebook（5 份，覆盖第 1–6 课）
├── 02-Python高级应用/ … 12-Python在财务中的综合应用/    # 11 个占位空目录（待随课程补充）
│
├── works/                          # ★ 综合实验项目（5 个）
│   ├── 01-货币时间价值与资本成本计算器/financial_calculator/          （子模块）
│   ├── 02-投资项目全流程评价系统/investment_decision_system/
│   ├── 03-综合成本与经营决策分析平台/cost_decision_platform/           （子模块）
│   ├── 04-财务报表分析报告/finstate_analysis_report/
│   └── 05-财务预测与预算管理实验报告/Yongding_Forecast_Budget_2026/   （子模块）
│
├── manual/                         # ★ 项目操作手册（编写工程 + 三稿成稿）
├── docs/                           # 课程课件（雨课堂抓取）：12 章 44 份 PDF
├── cases/财务自动化案例集/          # 财务自动化案例集（16 个案例，未纳入版本控制）
├── report/                         # 课程实践报告（模板与成稿，已排除版本控制）
│
├── LICENSE                         # 木兰宽松许可证 第 2 版
├── .gitmodules                     # 子模块定义（3 个）
├── .gitignore
└── README.md
```

每个 `works/<项目>/` 下另附课程下发的 `实践要求.txt`，与项目实现一一对应。

## 快速开始

### 1. 克隆（含子模块）

```bash
git clone git@github.com:yohoten/pyfin_cookbook.git     # 或 https://gitee.com/yohoten/pyfin_cookbook.git
cd pyfin_cookbook
git submodule update --init --recursive                 # 拉取 01 / 03 / 05 的子模块内容
```

未执行 `git submodule update` 时，`works/01-.../financial_calculator`、`works/03-.../cost_decision_platform`、`works/05-.../Yongding_Forecast_Budget_2026` 三个目录为空。项目 02、04 的代码直接存放在本仓库中，不涉及子模块。

### 2. 运行某个综合项目

各项目依赖独立，请进入对应项目目录后按其 `requirements.txt` 安装：

```bash
cd works/03-综合成本与经营决策分析平台/cost_decision_platform

python -m venv .venv                 # 或 py -3.9 -m venv .venv
.venv\Scripts\activate               # Windows；macOS / Linux 用 source .venv/bin/activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

python main.py
```

## 综合项目（`works/`）

| # | 项目 | 简介 | 入口 |
|---|------|------|------|
| 01 | [货币时间价值与资本成本计算器](works/01-货币时间价值与资本成本计算器/financial_calculator/) | 现值/终值/年金、债务与股权资本成本、WACC 计算；三层校验 + 7 类图表 + tkinter 图形界面 | `main.py`（`--demo` 一键场景、`--gui` 图形界面；Windows 可双击 `financial_calculator_gui.pyw`） |
| 02 | [投资项目全流程评价系统](works/02-投资项目全流程评价系统/investment_decision_system/) | NPV/IRR/回收期等指标全流程计算、单方案与多方案比选、敏感性与情景分析 | `main.py`（测试：`python -m tests.test_all`） |
| 03 | [综合成本与经营决策分析平台](works/03-综合成本与经营决策分析平台/cost_decision_platform/) | 成本核算、ABC 成本法、本量利分析与短期经营决策，自动生成图表与分析底稿 | `main.py` |
| 04 | [财务报表分析报告](works/04-财务报表分析报告/finstate_analysis_report/) | 采集美的集团（000333.SZ）三张报表，完成比率/结构/趋势/杜邦分析与 HTML 报告 | `run_all.py`（数据采集：`fetch_data.py`） |
| 05 | [财务预测与预算管理实验报告](works/05-财务预测与预算管理实验报告/Yongding_Forecast_Budget_2026/) | 基于永鼎股份（600105）历史报表的销售预测、2026 年预算编制与情景/敏感性分析 | `run_all.py`（八步流水线：`src/s1…s8`） |

每个项目目录内均有独立的 `README.md`（用法与设计说明）与 `.gitignore`（忽略生成物与缓存）；01、02 另附开发报告与测试用例。

## 项目操作手册（`manual/`）

`manual/` 是《Python 财务应用项目操作手册》的**编写工程**，而非单纯文档目录：由 `engine.py`（排版引擎）+ `c00_front.py`~`c06_report.py`（分章内容）+ `make_figs.py`（插图生成）+ `prep_assets.py`（素材准备）+ `build_manual.py`（总装）从源码直接生成成稿，版式参照《Hello 算法》中文 PDF。

```bash
cd manual
python build_manual.py               # 输出 Python财务应用项目操作手册.pdf
```

成稿清单：`（编写指导版）.docx`（初稿）、`（编写指导版·第二稿）.docx`、`（编写指导版·第三稿）.docx / .pdf`（最新），另有插图 `-插图.pptx` 与《手册表达与排版优化方案》；`qa/`~`qa4/`、`shots/` 为逐版页面渲染质检截图，`hello-algo-1.1.0-zh-python-Hello算法.pdf` 为版式参照的第三方资料。

## 其他内容

- **`docs/`**：雨课堂课件抓取交付，共 12 章 44 份 PDF（第 1 章 6 份、第 5 章 5 份，其余各 2–4 份），逐课件清单见 [docs/README.md](docs/README.md)。
- **`cases/财务自动化案例集/`**：16 个财务自动化案例（表格数据处理、Excel 工作簿运维、数据可视化、财务软件模拟操作、报告与流水处理、数据库与机器学习），每个案例自带 `README.md`、`data/`（输入）与 `output/`（产物）。索引与环境说明见 [cases/财务自动化案例集/README.md](cases/财务自动化案例集/README.md)。该目录为第三方公开教学材料，未纳入版本控制。
- **`report/`**：课程实践报告模板与本人在读期间的成稿（DOCX / PDF）。

## 环境与依赖

- **Python**：3.9 及以上。项目 01、02 已在 Python 3.9.13 实测通过（numpy 2.0.2 / pandas 2.3.3 / matplotlib 3.9.4）；项目 05 在 `requirements.txt` 中锁定较新的精确版本，建议搭配较新的解释器使用。准确口径以各项目 `requirements.txt` 与项目内 `README.md` 的实测环境说明为准。
- **图形界面**：项目 01 的 GUI 依赖 `tkinter`（Python 官方安装包自带）与 `Pillow`。
- **网络**：
  - 项目 04 `fetch_data.py` 需联网（东方财富 F10 为主源、新浪财经为核对源），采集结果落盘 `data/raw/`，后续分析完全离线。
  - 项目 05 首次运行需联网抓取数据，仓库已内置 2026-09 的数据快照；无网络时可用 `python run_all.py --skip-fetch` 基于快照离线复现。
- **pip 镜像**：国内环境建议追加 `-i https://pypi.tuna.tsinghua.edu.cn/simple`。

## Git 约定

- **子模块维护**：`works/01`、`works/03`、`works/05` 为子模块，指向各自独立的 GitHub 仓库。在其内部改动时，须先在子仓库提交并推送，再回根仓库提交子模块指针更新；拉取他人更新后需执行 `git submodule update --init --recursive`。
- 根目录 `.gitignore` 统一忽略 Python 缓存、虚拟环境、各项目的 `output(s)/` 生成物、IDE / 系统杂项文件。
- `cases/财务自动化案例集/`（第三方材料）已整体排除在版本控制之外。
- `report/` 已写入忽略规则：此后新增报告不再入库；仓库中已有的 3 份报告仍保留跟踪状态。如需彻底移出版本控制，执行 `git rm -r --cached report`。
- `02-`~`12-` 章节目录当前为本地空占位目录（Git 不跟踪空目录），随课程进度补充随堂代码后即可纳入。
