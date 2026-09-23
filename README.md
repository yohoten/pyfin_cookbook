# cookbook：《Python 在财务管理中的应用》课程笔记及实践

本仓库是《Python 在财务管理中的应用》课程的学习实践合集，包含课程课件、随堂代码、财务领域实用脚本，以及 5 个综合实验项目。

## 目录结构

```text
Python财务应用/
├── 01-Python基础应用/        # 随堂练习（Jupyter Notebook）
├── 02-Python高级应用/        # 占位（待补充）
├── 03-货币时间价值/ ~ 12-Python在财务中的综合应用/   # 占位（待补充）
├── docs/                     # 课程课件（雨课堂抓取，12 章 44 份课件）
├── cases/财务自动化案例集/    # 财务自动化案例集（16 个自包含案例）
├── report/                   # 课程实践报告（模板与成稿）
├── works/                    # ★ 综合实验项目（5 个）
└── README.md
```

## 综合项目（`works/`）

| # | 项目 | 简介 | 入口 |
|---|------|------|------|
| 01 | [货币时间价值与资本成本计算器](works/01-货币时间价值与资本成本计算器/financial_calculator/) | 现值/终值/年金/资本成本计算，含 GUI 与可视化 | `main.py`（GUI：`financial_calculator.pyw`） |
| 02 | [投资项目全流程评价系统](works/02-投资项目全流程评价系统/investment_decision_system/) | NPV/IRR/回收期等投资评价指标的全流程计算与决策 | `main.py` |
| 03 | [综合成本与经营决策分析平台](works/03-综合成本与经营决策分析平台/cost_decision_platform/) | 成本核算、ABC 成本法、本量利分析与短期经营决策，自动生成图表与分析底稿 | `main.py` |
| 04 | [财务报表分析报告](works/04-财务报表分析报告/) | 抓取上市公司财报数据，自动完成比率分析、杜邦分析并生成 HTML 报告 | `run_all.py`（数据获取：`fetch_data.py`） |
| 05 | [财务预测与预算管理实验报告](works/05-财务预测与预算管理实验报告/Yongding_Forecast_Budget_2026/) | 基于历史报表的销售预测、2026 年预算编制与情景/敏感性分析 | `run_all.py` |

每个项目目录内均有独立的 `README.md`（用法与设计说明）与 `.gitignore`（忽略生成物与缓存）。

## 环境与运行

各项目依赖独立，请进入对应项目目录后按其 `requirements.txt` 安装：

```bash
cd works/03-综合成本与经营决策分析平台/cost_decision_platform
'python -m venv .venv' or 'py -3.9 venv .venv'
.venv\Scripts\activate
pip install -r requirements.txt -i https://mirrors.tuna.tsinghua.edu.cn/
python main.py
```

基础环境：Python 3.10+；04、05 项目需要网络访问以获取财报数据。

## 其他内容

- **`docs/`**：雨课堂课件抓取交付（PPTX / PDF），逐课件清单见 [docs/README.md](docs/README.md)。
- **`cases/财务自动化案例集/`**：16 个财务自动化案例（表格数据处理、Excel 工作簿运维、数据可视化、财务软件模拟操作、报告与流水处理、数据库与机器学习），每个案例自带 `README.md`、`data/`（输入）与 `output/`（产物）。索引与环境说明见 [cases/财务自动化案例集/README.md](cases/财务自动化案例集/README.md)。该目录为第三方公开教学材料，未纳入版本控制。

## Git 约定

- 根目录 `.gitignore` 统一忽略 Python 缓存、虚拟环境、各项目的 `output(s)/` 生成物、IDE/系统杂项文件。
- 02–12 章节目录为占位，随课程进度逐步补充随堂代码。
