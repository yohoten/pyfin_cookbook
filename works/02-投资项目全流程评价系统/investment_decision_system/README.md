# 投资项目决策自动化评价系统

> 课程第 5 章实操项目：基于 Python + AI 的多项目批量评估与决策辅助系统
> 覆盖 **净现值(NPV)、内含报酬率(IRR)、互斥项目优选、资本限额下的项目分配、投资决策敏感性分析**

---

## 一、快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 一键运行全部 6 个测试案例（生成图表 + Markdown 报告 + Word 报告）
python main.py

# 3. 指定折现率
python main.py --rate 0.08

# 4. 只运行某个案例
python main.py --case CASE-3

# 5. 查看全部案例清单
python main.py --list

# 6. 运行单元测试（57 项断言）
python -m tests.test_all
```

运行完成后，产出文件位于 `outputs/`：

```
outputs/
├── data/
│   ├── projects.csv       各项目基础数据（含现金流明细）
│   └── evaluations.csv    全指标评价结果
├── figures/               39 张图表（PNG，200 DPI）
└── reports/
    ├── 投资项目决策评价报告.md       Markdown 报告
    └── 投资项目决策评价报告.docx     Word 报告（含表格与插图）
```

---

## 二、功能矩阵

| 题目要求 | 实现位置 | 说明 |
| :--- | :--- | :--- |
| NPV 计算函数（自定义投资/现金流/折现率） | `src/finance_core.py::npv` | 支持任意期数、不等额现金流、负折现率 |
| IRR 计算函数 | `src/finance_core.py::irr` | 网格扫描 + Brent 精解，**可捕获多重 IRR** |
| 互斥项目优选（NPV 法 / 年金净流量法） | `src/optimizer.py::select_mutually_exclusive` | 自动识别方法冲突，用增量 IRR 仲裁 |
| 资本限额项目组合优化（排序法 / 组合法） | `src/optimizer.py::ranking_method` / `combination_method` | 另附背包法（0-1 DP）交叉验证 |
| 敏感性分析（折现率/投资/现金流） | `src/sensitivity.py::one_way_sensitivity` | 含临界点分析与双因素矩阵 |
| AI 生成多项目现金流数据 | `src/ai_data_generator.py` | 6 行业原型 × 4 种现金流形态，固定种子可复现 |
| AI 生成决策建议 | `src/ai_advisor.py` | 规则引擎 + 可选大模型润色双通道 |
| NPV 对比柱状图 | `src/visualizer.py::plot_npv_comparison` | 红=可行 / 绿=不可行（国内惯例） |
| IRR 与折现率关系曲线 | `src/visualizer.py::plot_irr_vs_rate` | 曲线与横轴交点即 IRR |
| 敏感性 tornado 图（旋风图） | `src/visualizer.py::plot_tornado` | 按影响幅度降序，标注临界线 |
| 现金流结构对比图 | `src/visualizer.py::plot_cash_flows` | 叠加折现后现金流虚线 |
| 双因素敏感性热力图 | `src/visualizer.py::plot_two_way_heatmap` | 折现率 × 现金流，标注基准点 |
| 资本限额额度占用图 | `src/visualizer.py::plot_portfolio` | 直观展示排序法的闲置额度 |
| 互斥组多指标对比图 | `src/visualizer.py::plot_mutual_group` | NPV / ANCF / IRR 三联图暴露方法冲突 |
| 项目评价报告（Markdown / Word） | `src/report_generator.py` | 双格式导出，Word 含表格与插图 |

---

## 三、模块结构

```
investment_decision_system/
├── main.py                      主程序（命令行入口，一键全流程）
├── requirements.txt             依赖清单
├── README.md                    本文件
├── src/
│   ├── __init__.py              包说明与模块导航
│   ├── config.py                路径 / 中文字体 / 配色 / 默认参数 / AI 开关
│   ├── finance_core.py          核心算法：NPV、IRR、ANCF、PI、回收期、MIRR、增量 IRR
│   ├── models.py                数据结构：Project、Evaluation、IndustryProfile
│   ├── ai_data_generator.py     AI 生成多行业多周期现金流数据
│   ├── scenarios.py             6 个教学测试案例
│   ├── optimizer.py             互斥优选 + 资本限额组合优化（排序法/组合法/背包法）
│   ├── sensitivity.py           单因素、双因素敏感性分析与临界点分析
│   ├── ai_advisor.py            AI 决策建议生成（8 类风险规则 + 可选 LLM）
│   ├── visualizer.py            7 个绘图函数
│   └── report_generator.py      Markdown / Word 报告导出
├── tests/
│   └── test_all.py              55 项单元测试与案例断言
└── outputs/                     运行产物
```

---

## 四、测试案例一览

| 编号 | 案例名称 | 项目数 | 教学要点 / 刻意构造的陷阱 |
| :--- | :--- | :--- | :--- |
| CASE-1 | 独立项目可行性评价 | 2 | NPV 与 IRR 双判据；一正一负形成可行性对照 |
| CASE-2 | 互斥项目优选 | 4 | **(a) 规模冲突**：IRR 法选 MUT-P、NPV 法选 MUT-Q，须以 NPV 为准并用增量 IRR（ΔIRR=14.25%>10%）验证；**(b) 寿命冲突**：NPV 法选 MUT-Y、年金净流量法选 MUT-X，寿命不等必须用 ANCF |
| CASE-3 | 资本限额下的项目组合（限额 3000 万） | 8 | **排序法（PI 贪心）失效**：排序法得 1370 万元且闲置 200 万额度；组合穷举得全局最优 1460 万元（B+C），多创造 90 万元 |
| CASE-4 | 非常规现金流与多重 IRR | 3 | UNC-A 双根 **10% / 60%**，UNC-B 双根 **5% / 25%**；**NPV 与折现率非单调**（r 从 20% 升到 30%，NPV 反而从 55.56 升至 71.01 万元）；多重 IRR 时可行性只能由 NPV 判定 |
| CASE-5 | 投资决策敏感性分析 | 2 | 抗风险强 / 弱对照：SENS-S 安全边际 6.00pp，折现率升至 15% 时 NPV 仍为 +176.74；SENS-W 安全边际仅 0.70pp，折现率升至 15% 时 NPV **由 +139.35 转为 −737.07** |
| CASE-6 | AI 生成的多行业多周期项目批量评估 | 12 | 6 大行业（新能源/半导体/生物医药/消费零售/公用事业/数字软件）× 4 种现金流形态（稳定/成长/J曲线/周期），寿命跨度 5~15 年，验证批量自动化能力 |

---

## 五、核心方法说明

### 5.1 NPV 与 IRR

$$\text{NPV} = -I_0 + \sum_{t=1}^{n} \frac{CF_t}{(1+r)^t}, \qquad \text{IRR}: \text{NPV}(r) = 0$$

**现金流符号约定**：`cash_flows` 表示 t = 1..n 各期净现金流，`initial_investment` 用**正数**输入初始投资额（内部自动取负）。调用方只需按会计直觉填写"投入多少、每年收回多少"。

**IRR 求解策略**：IRR 方程本质是 n 次多项式，非常规现金流可能产生多解。本系统采用「**网格扫描 + Brent 精解**」——先在 (-99%, 500%] 上以 2000 点网格扫描 NPV 变号区间，再对每个区间用 `scipy.optimize.brentq` 精确定位，**可同时捕获全部实根**，并显式报出多重根告警。

### 5.2 年金净流量法（解决寿命不等）

$$\text{ANCF} = \frac{\text{NPV}}{\text{PVIFA}(r,n)} = \frac{\text{NPV} \cdot r}{1-(1+r)^{-n}}$$

把项目总 NPV 折算为"每年等额创造的价值"，使不同寿命的方案在统一口径下可比。

### 5.3 资本限额组合优化

| 方法 | 复杂度 | 最优性 | 适用场景 |
| :--- | :--- | :--- | :--- |
| 排序法（PI 贪心） | O(n log n) | ❌ 不保证 | 资金可分割、快速估算 |
| **组合法（DFS 穷举 + 剪枝）** | 剪枝后远小于 2ⁿ | ✅ **全局最优** | 项目数 ≤ 22（默认推荐） |
| 背包法（0-1 DP） | O(n × Budget) | ✅ 离散化后最优 | 项目数很多、额度量级可控 |

**为什么排序法会失效**：其隐含假设是"资金可任意分割"。当额度不可分割时，高 PI 的小额项目会先把额度打碎，导致剩余额度无法有效利用。

### 5.4 敏感性分析与安全边际

$$\text{安全边际} = \text{IRR} - r \quad(\text{百分点})$$

| 安全边际 | 抗风险等级 | 处置建议 |
| :--- | :--- | :--- |
| ≥ 8pp | 强 | 按计划推进 |
| 5~8pp | 较强 | 按计划推进 |
| 3~5pp | 中等 | 建立关键指标监控机制 |
| 1~3pp | 较弱 | 分期投入、设置折现率红线 |
| < 1pp | 极弱 | 谨慎决策，须锁定收益端不确定性 |

**扰动口径**：折现率按**绝对百分点 ±5pp**，初始投资与年现金流按**相对比例 ±20%**，项目寿命 ±1 年（不同因素口径不同，图表中逐一标注）。

---

## 六、AI 辅助功能说明

### 6.1 数据生成：为什么不用"让大模型直接编数字"

直接由大模型自由生成现金流存在两个致命问题：

1. **数量级不可控**——可能生成"投资 100 万、每年回收 800 万"这类违背商业常识的数据，使 NPV/IRR 结论失去教学意义；
2. **不可复现**——相同指令两次调用结果不同，无法支撑报告的结果复核。

因此本系统采用「**行业原型约束 + 参数化生成**」：先由行业知识构建参数区间（投资规模、寿命、现金回收效率、成长性、波动率、现金流形态），再在区间内采样并按 `steady / growth / jcurve / cycle` 四种形态生成现金流曲线，随机数使用固定种子。**同一份代码在任何机器上跑出完全一致的数据**。

### 6.2 决策建议：双通道架构

```
generate_advice(evaluation, sensitivity)
        │
   ┌────┴────┐
   ▼         ▼
规则引擎    大模型通道
(离线可用)  (需 IDS_LLM_API_KEY)
```

**为什么以规则引擎为主通道**：

1. **可复现**——同数据永远产生同结论，报告结论可复核；
2. **零幻觉**——所有数字直接来自计算引擎，不存在编造数字的风险；
3. **离线可用**——不依赖网络与 API Key；
4. **可解释**——每条风险提示都能追溯到具体规则。

大模型通道仅作为**文案润色层**：把已算好的结构化指标交给模型润色表达，并强制约束"不得修改任何数字"。

**8 类风险规则**：安全边际、折现率冲击、投资超支容错、现金流下滑容错、回收期占比、多重 IRR、现金流波动率、资本集中度。

### 6.3 启用大模型（可选）

```bash
# Linux / macOS
export IDS_LLM_API_KEY="sk-..."
export IDS_LLM_BASE_URL="https://api.openai.com/v1"
export IDS_LLM_MODEL="gpt-4o-mini"
python main.py --ai-mode llm

# Windows PowerShell
$env:IDS_LLM_API_KEY="sk-..."
python main.py --ai-mode llm
```

未配置 Key 时自动降级为规则引擎，**不会报错、不影响运行**。

---

## 七、扩展用法

### 7.1 作为库调用

```python
from src import finance_core as fc

# 基础计算
npv = fc.npv(0.10, [500, 500, 500], 1000)        # 243.43
irr = fc.irr([500, 500, 500], 1000)               # 0.2338 (23.38%)

# 多重 IRR 诊断
result = fc.irr_details([5400, -3520], 2000)
print(result.all_roots)                            # [0.10, 0.60]
print(result.is_unique)                            # False

# 年金净流量（寿命不同项目的可比口径）
ancf = fc.annuity_net_cash_flow(npv, 0.10, 3)
```

### 7.2 自定义项目

```python
from src.models import Project, Evaluation

p = Project(
    code="MY-01", name="我的项目", industry="制造业",
    initial_investment=3000.0,
    cash_flows=[700, 800, 900, 1000, 1100],
    risk_level="中",
)
ev = Evaluation.build(p, rate=0.10)
print(ev.to_dict())
```

### 7.3 自定义案例

在 `src/scenarios.py` 中新增一个 `@dataclass Scenario` 构造函数并加入 `all_cases()` 即可自动纳入全流程。

---

## 八、环境要求

| 组件 | 版本要求 | 用途 |
| :--- | :--- | :--- |
| Python | ≥ 3.10 | 主语言（开发环境 3.13.14） |
| NumPy | ≥ 1.24 | 现金流向量化折现 |
| SciPy | ≥ 1.10 | Brent 法求解 IRR 方程实根 |
| pandas | ≥ 2.0 | 数据表组织与 CSV 导出 |
| Matplotlib | ≥ 3.7 | 图表绘制（自动配置中文字体） |
| python-docx | ≥ 1.1 | Word 报告生成 |

**中文字体**：程序会自动尝试 `Microsoft YaHei` → `SimHei` → `Noto Sans CJK SC` → `WenQuanYi Zen Hei`，并设置 `axes.unicode_minus = False` 保证负号正常显示，因此图表中不会出现方框乱码。

---

## 九、常见问题

**Q1：图表中文字显示为方框？**
检查系统是否安装中文字体。Linux 下可安装：`sudo apt install fonts-noto-cjk`。

**Q2：`python main.py` 运行很慢？**
主要耗时在 20 张 200 DPI 图表的渲染与 Word 报告生成，通常 2~3 分钟。可先跑单案例验证：`python main.py --case CASE-1`。

**Q3：多重 IRR 项目为什么判"可行"但 IRR 低于资本成本？**
这正是 CASE-4 的教学要点。IRR 多重根时"选哪个根代表 IRR"无客观标准，套用 `IRR > r` 规则会得出与 NPV 相反的结论。本系统对此做了特殊处理：**多重 IRR 项目的可行性仅由 NPV 判定**（见 `src/models.py::Evaluation.build`）。

**Q4：如何修改资本限额？**
编辑 `src/scenarios.py::case_3_capital_rationing` 中 `Scenario.budget` 字段。

---

## 十、验证情况

```
$ python -m tests.test_all
Ran 57 tests in 5.323s
OK
```

测试覆盖：核心算法数值正确性（对照手工计算）、数值稳健性（多重 IRR 捕获、回代精度）、决策逻辑（互斥冲突、排序法失效、背包法一致性）、敏感性与临界点数学自洽性、AI 文案方向正确性与数据可复现性、端到端可运行性。

**关键数值复核对照表**（均可手工验算）：

| 校验项 | 期望值 | 实算值 | 结论 |
| :--- | :--- | :--- | :--- |
| NPV(10%, [500,500,500], 1000) | 243.4261 | 243.4261 | ✅ |
| IRR([500,500,500], 1000) | PVIFA(r,3)=2 → 23.3752% | 23.3752% | ✅ |
| CASE-2 规模组 MUT-P NPV / IRR | 119.0832 / 16.65% | 119.08 / 16.65% | ✅ |
| CASE-2 寿命组 MUT-X ANCF | 30.3924 | 30.39 | ✅ |
| CASE-2 增量 IRR（P→Q） | — | 14.25%（>10%，选 Q） | ✅ |
| CASE-3 排序法 NPV | 1370 | 1370.03 | ✅ |
| CASE-3 组合法 NPV（B+C） | 1460 | 1460.01 | ✅ |
| CASE-4 UNC-A 双根 | 10% / 60% | 10.0000% / 60.0000% | ✅ |
| CASE-4 UNC-A 最大 NPV | — | 71.01（r≈30%） | ✅ |
| CASE-5 SENS-S / SENS-W IRR | 16.00% / 10.70% | 15.9965% / 10.7044% | ✅ |
| CASE-5 SENS-W 折现率 +5pp 后 NPV | 由正转负 | +139.35 → −737.07 | ✅ |
