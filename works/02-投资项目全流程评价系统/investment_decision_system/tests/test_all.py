# -*- coding: utf-8 -*-
"""
test_all.py — 单元测试与案例断言
====================================================================
运行方式::

    python -m tests.test_all          # 直接运行（无需 pytest）
    python -m pytest tests/ -v        # 使用 pytest 运行

测试覆盖
--------
1. **核心算法正确性**：NPV、IRR、ANCF、PI、回收期、MIRR、增量 IRR
   均对照手工计算结果断言（容差 1e-4 量级）；
2. **数值稳健性**：多重 IRR 的捕获、IRR 回代精度、边界条件；
3. **决策逻辑正确性**：互斥项目的两组经典冲突、排序法失效、
   背包法与组合法一致性；
4. **敏感性与临界点**：折现率 ±5pp 冲击、临界投资上限的数学自洽性；
5. **AI 辅助与数据可复现性**：决策文案结论方向、固定种子下的数据复现；
6. **端到端可运行性**：全部 6 个案例可完整跑通并产出图表与报告。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# 允许以「python -m tests.test_all」或「python tests/test_all.py」两种方式运行
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src import finance_core as fc
from src import scenarios, visualizer
from src.ai_advisor import VERDICT_EDGE, VERDICT_INFEASIBLE, generate_advice
from src.ai_data_generator import generate_projects
from src.models import Evaluation, Project
from src.optimizer import (
    combination_method,
    knapsack_method,
    optimize_portfolio,
    ranking_method,
    select_mutually_exclusive,
)
from src.sensitivity import one_way_sensitivity, risk_grade

RATE = 0.10


# ======================================================================
# 一、核心算法测试
# ======================================================================
class TestFinanceCore(unittest.TestCase):
    """NPV / IRR / 辅助指标的数值正确性测试。"""

    def test_npv_basic(self):
        """NPV 基础计算：对照手工折现结果。"""
        # 500 × PVIFA(10%, 3) = 500 × 2.486852 = 1243.426
        self.assertAlmostEqual(fc.npv(0.10, [500, 500, 500], 1000), 243.4261, places=3)

    def test_npv_manual_expansion(self):
        """NPV 逐步折现验证：CF 不等额情形。"""
        # 280/1.1 + 300/1.21 + 320/1.331 + 340/1.4641 + 360/1.61051 - 1000
        expected = (280 / 1.1 + 300 / 1.21 + 320 / 1.331
                    + 340 / 1.4641 + 360 / 1.61051 - 1000)
        self.assertAlmostEqual(fc.npv(0.10, [280, 300, 320, 340, 360], 1000),
                               expected, places=6)

    def test_npv_zero_rate(self):
        """折现率为 0 时 NPV 退化为净现金流总和。"""
        self.assertAlmostEqual(fc.npv(0.0, [300, 300, 300], 800), 100.0, places=9)

    def test_npv_negative_rate(self):
        """负折现率应可计算（0 > r > -100%）。"""
        value = fc.npv(-0.05, [500, 500, 500], 1000)
        self.assertGreater(value, 243.4261)   # 折现率越低 NPV 越大

    def test_npv_rate_below_minus_one_raises(self):
        """折现率 ≤ -100% 应抛出 ValueError。"""
        with self.assertRaises(ValueError):
            fc.npv(-1.0, [500], 1000)

    def test_irr_annuity_consistency(self):
        """IRR 与年金现值系数反解一致：PVIFA(r,3) = 1000/500 = 2。"""
        r = fc.irr([500, 500, 500], 1000)
        self.assertIsNotNone(r)
        self.assertAlmostEqual(fc.pvifa(r, 3), 2.0, places=8)
        self.assertAlmostEqual(r, 0.233752, places=5)

    def test_irr_residual_is_zero(self):
        """IRR 回代 NPV 应约等于 0（数值精度自检）。"""
        flows = [280, 300, 320, 340, 360]
        r = fc.irr(flows, 1000)
        self.assertIsNotNone(r)
        self.assertAlmostEqual(fc.npv(r, flows, 1000), 0.0, places=6)

    def test_irr_no_real_root(self):
        """现金流全部为负时 IRR 无实根。"""
        self.assertIsNone(fc.irr([-100, -100], 1000))

    def test_irr_multiple_roots_detected(self):
        """多重 IRR 检测：-1000, 2300, -1320 应有两个实根 10% 与 20%。"""
        # 方程 -1000 + 2300/(1+r) - 1320/(1+r)^2 = 0
        result = fc.irr_details([2300, -1320], 1000)
        self.assertFalse(result.is_unique)
        self.assertEqual(len(result.all_roots), 2)
        self.assertAlmostEqual(result.all_roots[0], 0.10, places=6)
        self.assertAlmostEqual(result.all_roots[1], 0.20, places=6)
        # 两个根回代均应接近 0
        for r in result.all_roots:
            self.assertAlmostEqual(fc.npv(r, [2300, -1320], 1000), 0.0, places=5)

    def test_irr_multiple_roots_second_case(self):
        """第二个多重 IRR 案例：-2000, 4600, -2625 的两个根为 5% 与 25%。"""
        result = fc.irr_details([4600, -2625], 2000)
        self.assertFalse(result.is_unique)
        self.assertEqual(len(result.all_roots), 2)
        self.assertAlmostEqual(result.all_roots[0], 0.05, places=6)
        self.assertAlmostEqual(result.all_roots[1], 0.25, places=6)

    def test_annuity_net_cash_flow(self):
        """年金净流量 = NPV / PVIFA(r, n)。"""
        npv_value = fc.npv(0.10, [260] * 6, 1000)
        ancf = fc.annuity_net_cash_flow(npv_value, 0.10, 6)
        self.assertAlmostEqual(npv_value, 132.3678, places=3)
        self.assertAlmostEqual(ancf, npv_value / 4.3552607, places=6)
        self.assertAlmostEqual(ancf, 30.3924, places=3)

    def test_profitability_index(self):
        """盈利能力指数 PI = (NPV + I0) / I0。"""
        # 450 × PVIFA(10%, 3) = 1119.083 > 1000，NPV 为正、PI > 1
        npv_value = fc.npv(0.10, [450, 450, 450], 1000)
        pi = fc.profitability_index(npv_value, 1000)
        self.assertAlmostEqual(pi, (npv_value + 1000) / 1000, places=9)
        self.assertGreater(pi, 1.0)
        self.assertAlmostEqual(pi, 1.119083, places=5)

    def test_payback_period_with_interpolation(self):
        """静态回收期的线性插值：投资 1000，前两年各 400，第三年 400 → 2.5 年。"""
        self.assertAlmostEqual(fc.payback_period([400, 400, 400], 1000), 2.5, places=9)

    def test_payback_period_not_recovered(self):
        """寿命内未收回投资应返回 None。"""
        self.assertIsNone(fc.payback_period([100, 100], 1000))

    def test_discounted_payback_period(self):
        """动态回收期应长于静态回收期（450×3 在 10% 下 PV=1119 > 1000，可收回）。"""
        flows = [450, 450, 450]
        static = fc.payback_period(flows, 1000)
        dynamic = fc.discounted_payback_period(flows, 1000, 0.10)
        self.assertIsNotNone(dynamic)
        self.assertGreater(dynamic, static)
        self.assertAlmostEqual(static, 1000 / 450, places=9)

    def test_discounted_payback_none_when_pv_insufficient(self):
        """现金流现值合计不足投资额时，动态回收期应为 None。"""
        # 400 × PVIFA(10%, 3) = 994.74 < 1000，折现后永远收不回
        self.assertIsNone(fc.discounted_payback_period([400, 400, 400], 1000, 0.10))
        # 但静态回收期仍可正常计算
        self.assertAlmostEqual(fc.payback_period([400, 400, 400], 1000), 2.5, places=9)

    def test_mirr_unique_and_reasonable(self):
        """MIRR 应为有限值且落在合理区间。"""
        value = fc.mirr([2300, -1320], 1000, 0.10, 0.10)
        self.assertTrue(-1.0 < value < 10.0)

    def test_incremental_irr(self):
        """增量 IRR：大方案减小方案的增量现金流报酬率。"""
        result = fc.incremental_irr([450] * 3, [1250, 1100, 900], 1000, 2500)
        self.assertIsNotNone(result.irr)
        # 增量投资 1500，增量现金流 800 / 650 / 450
        self.assertAlmostEqual(
            fc.npv(result.irr, [800, 650, 450], 1500), 0.0, places=5
        )


# ======================================================================
# 二、互斥项目优选测试
# ======================================================================
class TestMutualExclusion(unittest.TestCase):
    """互斥项目优选的两组经典冲突测试。"""

    @classmethod
    def setUpClass(cls):
        cls.scenario = scenarios.case_2_mutually_exclusive(RATE)
        cls.results = {r.group: r for r in select_mutually_exclusive(
            cls.scenario.projects, RATE)}

    def test_scale_conflict_group(self):
        """规模冲突组：IRR 法选 MUT-P，NPV 法选 MUT-Q，构成冲突。"""
        r = self.results["MUT-SCALE"]
        self.assertTrue(r.same_life)
        self.assertEqual(r.best_by_npv.project.code, "MUT-Q")
        self.assertEqual(r.best_by_irr.project.code, "MUT-P")
        self.assertTrue(r.conflict_npv_irr)
        # 数值校验
        self.assertAlmostEqual(r.best_by_npv.npv, 221.6378, places=3)
        self.assertAlmostEqual(r.best_by_npv.npv, 221.6378, places=3)
        p_eval = next(e for e in r.evaluations if e.project.code == "MUT-P")
        self.assertAlmostEqual(p_eval.npv, 119.0832, places=3)
        # IRR 由 PVIFA(r, 3) = 1000/450 = 2.2222 反解，约 16.65%
        self.assertAlmostEqual(p_eval.irr, 0.1665, places=4)

    def test_scale_conflict_incremental_analysis(self):
        """增量 IRR 分析应给出方向性判定（增量投资划算 → 选大方案）。"""
        r = self.results["MUT-SCALE"]
        self.assertIsNotNone(r.incremental)
        self.assertEqual(r.incremental["小投资方案"], "MUT-P")
        self.assertEqual(r.incremental["大投资方案"], "MUT-Q")
        self.assertIn("MUT-Q", r.incremental["判定"])

    def test_life_conflict_group(self):
        """寿命冲突组：NPV 法选 MUT-Y，年金净流量法选 MUT-X。"""
        r = self.results["MUT-LIFE"]
        self.assertFalse(r.same_life)
        self.assertEqual(r.best_by_npv.project.code, "MUT-Y")
        self.assertEqual(r.best_by_ancf.project.code, "MUT-X")
        self.assertTrue(r.conflict_npv_ancf)
        # 数值校验
        self.assertAlmostEqual(r.best_by_npv.npv, 136.1418, places=3)
        x_eval = next(e for e in r.evaluations if e.project.code == "MUT-X")
        self.assertAlmostEqual(x_eval.npv, 132.3678, places=3)
        self.assertAlmostEqual(x_eval.ancf, 30.3924, places=3)

    def test_no_incremental_analysis_when_lives_differ(self):
        """寿命不等的互斥组不得输出增量 IRR 分析（避免与年金净流量法结论冲突）。"""
        r = self.results["MUT-LIFE"]
        self.assertFalse(r.same_life)
        self.assertIsNone(r.incremental)

    def test_recommendation_mentions_ancf_for_unequal_life(self):
        """寿命不等时建议文案必须提及年金净流量法。"""
        r = self.results["MUT-LIFE"]
        self.assertIn("年金净流量法", r.recommendation)

    def test_no_group_returns_empty(self):
        """无互斥标签的项目不产生互斥组。"""
        projects = [Project("A", "a", "x", 100, [50, 50])]
        self.assertEqual(select_mutually_exclusive(projects, RATE), [])


# ======================================================================
# 三、资本限额组合优化测试
# ======================================================================
class TestCapitalRationing(unittest.TestCase):
    """资本限额下的项目组合优化测试。"""

    @classmethod
    def setUpClass(cls):
        cls.scenario = scenarios.case_3_capital_rationing(RATE)
        cls.budget = cls.scenario.budget
        cls.projects = cls.scenario.projects

    def test_ranking_method_result(self):
        """排序法应选中 CAP-A + CAP-D，投资 2800，NPV ≈ 1370。"""
        result = ranking_method(self.projects, RATE, self.budget)
        self.assertEqual(result.codes.replace(" ", ""), "CAP-A+CAP-D")
        self.assertAlmostEqual(result.total_investment, 2800.0, places=0)
        self.assertAlmostEqual(result.total_npv, 1370.05, delta=3.0)
        self.assertAlmostEqual(result.idle_budget, 200.0, places=0)

    def test_combination_method_beats_ranking(self):
        """组合法应优于排序法：最优组合 NPV ≈ 1460，优于 1370。"""
        ranking = ranking_method(self.projects, RATE, self.budget)
        combo = combination_method(self.projects, RATE, self.budget)
        self.assertGreater(combo.total_npv, ranking.total_npv)
        self.assertAlmostEqual(combo.total_npv, 1460.0, delta=3.0)
        self.assertAlmostEqual(combo.total_investment, 3000.0, places=0)
        # 全局最优组合为 CAP-B + CAP-C
        self.assertEqual(set(combo.selected[i].project.code for i in range(len(combo.selected))),
                         {"CAP-B", "CAP-C"})

    def test_combination_respects_budget(self):
        """任何可行组合的投资额都不得超过资本限额。"""
        combo = combination_method(self.projects, RATE, self.budget)
        self.assertLessEqual(combo.total_investment, self.budget + 1e-6)

    def test_knapsack_matches_combination(self):
        """背包法结果应与组合法一致（离散化误差 < 1 万元）。"""
        combo = combination_method(self.projects, RATE, self.budget)
        knap = knapsack_method(self.projects, RATE, self.budget, unit=1.0)
        self.assertAlmostEqual(knap.total_npv, combo.total_npv, delta=1.0)

    def test_optimize_portfolio_comparison_text(self):
        """综合优化报告应指认排序法失效并给出差额。"""
        report = optimize_portfolio(self.projects, RATE, self.budget)
        self.assertIn("排序法", report.results)
        self.assertIn("组合法", report.results)
        self.assertEqual(report.best.method, "组合法（DFS 穷举 + 剪枝）")
        self.assertIn("排序法未能取得最优解", report.comparison)

    def test_budget_larger_than_total_selects_all_positive(self):
        """限额充足时应选中全部正 NPV 项目。"""
        result = combination_method(self.projects, RATE, 99999.0)
        positive = [p for p in self.projects
                    if Evaluation.build(p, RATE).npv > 0]
        self.assertEqual(len(result.selected), len(positive))


# ======================================================================
# 四、敏感性分析与临界点测试
# ======================================================================
class TestSensitivity(unittest.TestCase):
    """敏感性分析、临界点与风险等级的测试。"""

    @classmethod
    def setUpClass(cls):
        cls.case5 = scenarios.case_5_sensitivity(RATE)
        cls.strong = next(p for p in cls.case5.projects if p.code == "SENS-S")
        cls.weak = next(p for p in cls.case5.projects if p.code == "SENS-W")

    def test_base_npv_values(self):
        """两个敏感性案例项目的基准 NPV 应与设计值一致。"""
        self.assertAlmostEqual(self.strong.npv(RATE), 1229.66, delta=2.0)
        self.assertAlmostEqual(self.weak.npv(RATE), 139.35, delta=2.0)

    def test_irr_values(self):
        """IRR 应与设计值一致（强项目 ≈16.00%，弱项目 ≈10.70%）。"""
        self.assertAlmostEqual(self.strong.irr(), 0.1600, delta=0.001)
        self.assertAlmostEqual(self.weak.irr(), 0.1070, delta=0.001)

    def test_rate_shock_flips_weak_project(self):
        """折现率上升 5pp 后，弱项目 NPV 由正转负（核心风险提示场景）。"""
        weak_npv_at_15 = self.weak.npv(0.15)
        self.assertLess(weak_npv_at_15, 0)
        self.assertGreater(self.weak.npv(RATE), 0)
        strong_npv_at_15 = self.strong.npv(0.15)
        self.assertGreater(strong_npv_at_15, 0)   # 强项目仍为正

    def test_sensitivity_flags_critical_factor(self):
        """弱项目的折现率因素应被标记为 critical（击穿临界点）。"""
        sens = one_way_sensitivity(self.weak, RATE, delta=0.20, rate_delta_pp=0.05)
        rate_factor = next(f for f in sens.factors if f.name == "折现率")
        self.assertTrue(rate_factor.critical)

        sens_strong = one_way_sensitivity(self.strong, RATE, delta=0.20, rate_delta_pp=0.05)
        rate_factor_strong = next(f for f in sens_strong.factors if f.name == "折现率")
        self.assertFalse(rate_factor_strong.critical)

    def test_tornado_ordering_is_descending(self):
        """tornado 图数据必须按 NPV 波动幅度降序排列。"""
        sens = one_way_sensitivity(self.weak, RATE)
        swings = [f.swing for f in sens.factors]
        self.assertEqual(swings, sorted(swings, reverse=True))

    def test_safety_margin_and_grade(self):
        """安全边际与风险等级的映射关系。"""
        sens_strong = one_way_sensitivity(self.strong, RATE)
        self.assertAlmostEqual(sens_strong.safety_margin, self.strong.irr() - RATE, places=8)
        self.assertIn(sens_strong.grade, {"强", "较强", "中等", "较弱", "极弱"})
        # 等级划分边界测试
        self.assertEqual(risk_grade(0.10), "强")
        self.assertEqual(risk_grade(0.06), "较强")
        self.assertEqual(risk_grade(0.04), "中等")
        self.assertEqual(risk_grade(0.02), "较弱")
        self.assertEqual(risk_grade(0.005), "极弱")

    def test_breakeven_investment_limit_is_self_consistent(self):
        """临界投资上限处 NPV 必须为 0（数学自洽性验证）。"""
        from src.sensitivity import breakeven_analysis
        be = breakeven_analysis(self.strong, RATE)
        limit = be["初始投资上限"]["现值合计数值"]
        npv_at_limit = fc.npv(RATE, self.strong.cash_flows, limit)
        self.assertAlmostEqual(npv_at_limit, 0.0, places=6)
        # 展示用字段与数值字段应一致
        self.assertAlmostEqual(be["初始投资上限"]["现值合计(万元)"], limit, places=2)

    def test_breakeven_cash_flow_limit_is_self_consistent(self):
        """年现金流下界处 NPV 必须为 0。"""
        from src.sensitivity import breakeven_analysis
        be = breakeven_analysis(self.strong, RATE)
        scale = be["年现金流下限"]["最低现金流系数数值"]
        scaled = [cf * scale for cf in self.strong.cash_flows]
        self.assertAlmostEqual(fc.npv(RATE, scaled, self.strong.initial_investment),
                               0.0, places=6)

    def test_two_way_matrix_shape_and_base_point(self):
        """双因素矩阵形状正确，且中心点等于基准 NPV。"""
        from src.sensitivity import two_way_sensitivity
        matrix, rate_axis, cf_axis = two_way_sensitivity(self.strong, RATE)
        self.assertEqual(len(matrix), len(cf_axis))
        self.assertEqual(len(matrix[0]), len(rate_axis))
        mid_i = cf_axis.index(1.0)
        mid_j = rate_axis.index(RATE)
        self.assertAlmostEqual(matrix[mid_i][mid_j], self.strong.npv(RATE), places=6)


# ======================================================================
# 五、AI 辅助与数据生成测试
# ======================================================================
class TestAIAssistance(unittest.TestCase):
    """AI 数据生成的可复现性与决策建议的正确性。"""

    def test_generated_projects_reproducible(self):
        """固定随机种子下，两次生成的数据必须完全一致。"""
        a = generate_projects(count_per_industry=2)
        b = generate_projects(count_per_industry=2)
        self.assertEqual(len(a), len(b))
        for pa, pb in zip(a, b):
            self.assertEqual(pa.code, pb.code)
            self.assertEqual(pa.initial_investment, pb.initial_investment)
            self.assertEqual(pa.cash_flows, pb.cash_flows)

    def test_generated_projects_cover_industries_and_lives(self):
        """生成数据应覆盖多行业与多寿命（跨度 ≥ 8 年）。"""
        projects = generate_projects(count_per_industry=2)
        self.assertGreaterEqual(len(projects), 12)
        self.assertGreaterEqual(len({p.industry for p in projects}), 6)
        lives = [p.life for p in projects]
        self.assertGreaterEqual(max(lives) - min(lives), 8)

    def test_generated_cash_flows_are_plausible(self):
        """生成数据应符合商业常识：投资规模与现金流数量级匹配。"""
        for p in generate_projects(count_per_industry=2):
            positive = [cf for cf in p.cash_flows if cf > 0]
            self.assertTrue(positive, f"{p.code} 无正向现金流")
            # 年均现金流不应超过初始投资的 60%（否则回收期过短，不合常理）
            self.assertLess(sum(p.cash_flows) / p.life,
                            p.initial_investment * 0.6,
                            f"{p.code} 现金回收效率异常")

    def test_advice_for_infeasible_project(self):
        """NPV 为负的项目应给出"不可行"结论。"""
        scenario = scenarios.case_1_independent_projects(RATE)
        bad = next(p for p in scenario.projects if p.code == "IND-B")
        ev = Evaluation.build(bad, RATE)
        advice = generate_advice(ev)
        self.assertEqual(advice.verdict, VERDICT_INFEASIBLE)
        self.assertGreater(advice.risk_score, 0)
        self.assertTrue(any("否决" in a for a in advice.actions))

    def test_advice_for_edge_project(self):
        """边缘可行项目应给出"谨慎推进"结论并提示折现率风险。"""
        scenario = scenarios.case_5_sensitivity(RATE)
        weak = next(p for p in scenario.projects if p.code == "SENS-W")
        ev = Evaluation.build(weak, RATE)
        advice = generate_advice(ev)
        self.assertEqual(advice.verdict, VERDICT_EDGE)
        self.assertTrue(any("折现率上升风险" in r for r in advice.risks))
        # 风险提示必须包含"由正转负"的判断题
        self.assertTrue(any("由正转负" in r for r in advice.risks))

    def test_advice_flags_multiple_irr(self):
        """多重 IRR 项目应触发指标失效提示。"""
        scenario = scenarios.case_4_unconventional_cash_flow(RATE)
        multi = next(p for p in scenario.projects if p.code == "UNC-A")
        ev = Evaluation.build(multi, RATE)
        advice = generate_advice(ev)
        self.assertTrue(any("指标失效" in r or "多重" in r or "实根" in r
                            for r in advice.risks))

    def test_advice_contains_no_placeholder(self):
        """生成的文案中不得出现未填充的占位符或符号格式错误。"""
        for scenario in scenarios.all_cases(RATE):
            for p in scenario.projects[:2]:
                advice = generate_advice(Evaluation.build(p, RATE))
                text = advice.headline + "".join(advice.reasons) + "".join(advice.risks)
                for token in ("{", "}", "None", "nan", "NaN", "+-", "--"):
                    self.assertNotIn(token, text, f"{p.code} 文案含异常字符 {token}")
                self.assertGreater(len(advice.reasons), 3)

    def test_infeasible_project_no_misleading_risk_wording(self):
        """负 NPV 项目不得输出"折现率风险（可控）"这类误导性话术。"""
        scenario = scenarios.case_4_unconventional_cash_flow(RATE)
        unc_c = next(p for p in scenario.projects if p.code == "UNC-C")
        self.assertLess(unc_c.npv(RATE), 0)          # 前提：该项目 NPV 为负
        advice = generate_advice(Evaluation.build(unc_c, RATE))
        text = "".join(advice.risks)
        self.assertNotIn("风险（可控）", text)
        self.assertTrue(any("可行性风险" in r or "收入水平风险" in r or "投资规模风险" in r
                            for r in advice.risks))

    def test_full_advice_text_has_no_broken_sign(self):
        """全部案例的完整文案不得出现 "+-" 型符号拼接错误。"""
        for scenario in scenarios.all_cases(RATE):
            for p in scenario.projects:
                advice = generate_advice(Evaluation.build(p, RATE))
                text = (advice.headline + "".join(advice.reasons)
                        + "".join(advice.risks) + "".join(advice.actions))
                self.assertNotIn("+-", text, f"{p.code} 出现符号格式错误")
                self.assertNotIn("**None", text, f"{p.code} 出现 None 占位")


# ======================================================================
# 六、案例完整性与端到端测试
# ======================================================================
class TestScenariosAndEndToEnd(unittest.TestCase):
    """案例库完整性与端到端可运行性。"""

    def test_at_least_five_cases(self):
        """测试案例数量必须 ≥ 5（题目要求）。"""
        cases = scenarios.all_cases(RATE)
        self.assertGreaterEqual(len(cases), 5)
        keys = [c.key for c in cases]
        self.assertEqual(len(keys), len(set(keys)), "案例编号不得重复")

    def test_case_types_cover_requirements(self):
        """案例必须覆盖题目要求的三类情境：独立、互斥、资本限额组合。"""
        cases = {c.key: c for c in scenarios.all_cases(RATE)}
        # 独立项目
        self.assertTrue(any(p.mutual_group is None for p in cases["CASE-1"].projects))
        # 互斥项目
        self.assertTrue(any(p.mutual_group for p in cases["CASE-2"].projects))
        # 资本限额下的多项目组合
        self.assertIsNotNone(cases["CASE-3"].budget)
        self.assertGreaterEqual(len(cases["CASE-3"].projects), 5)

    def test_every_project_evaluates_without_error(self):
        """全部案例的每个项目都能完成全指标评价。"""
        for scenario in scenarios.all_cases(RATE):
            for p in scenario.projects:
                ev = Evaluation.build(p, RATE)
                self.assertIsInstance(ev.npv, float)
                self.assertIsInstance(ev.pi, float)
                self.assertIsInstance(ev.feasible, bool)

    def test_case_4_detects_unconventional_cash_flow(self):
        """CASE-4 的非常规现金流项目应被正确定位为多次符号变化。"""
        scenario = scenarios.case_4_unconventional_cash_flow(RATE)
        unconv = [p for p in scenario.projects if p.has_unconventional_sign_changes > 1]
        self.assertGreaterEqual(len(unconv), 2)
        for p in unconv:
            self.assertFalse(p.irr_details().is_unique)

    def test_case_4_double_roots(self):
        """CASE-4 两个项目各自的 IRR 双根应与设计值一致。"""
        scenario = scenarios.case_4_unconventional_cash_flow(RATE)
        unc_a = next(p for p in scenario.projects if p.code == "UNC-A")
        unc_b = next(p for p in scenario.projects if p.code == "UNC-B")
        roots_a = unc_a.irr_details().all_roots
        roots_b = unc_b.irr_details().all_roots
        self.assertEqual(len(roots_a), 2)
        self.assertAlmostEqual(roots_a[0], 0.10, places=6)
        self.assertAlmostEqual(roots_a[1], 0.60, places=6)
        self.assertEqual(len(roots_b), 2)
        self.assertAlmostEqual(roots_b[0], 0.05, places=6)
        self.assertAlmostEqual(roots_b[1], 0.25, places=6)

    def test_case_4_npv_non_monotonic(self):
        """UNC-A 的 NPV 与折现率非单调：折现率上升，NPV 反而先上升。"""
        scenario = scenarios.case_4_unconventional_cash_flow(RATE)
        unc_a = next(p for p in scenario.projects if p.code == "UNC-A")
        npv_10 = unc_a.npv(0.10)
        npv_20 = unc_a.npv(0.20)
        npv_30 = unc_a.npv(0.30)
        # 10% 与 60% 均为根，中间区间的 NPV 为正，且 30% 处最大
        self.assertAlmostEqual(npv_10, 0.0, places=6)
        self.assertAlmostEqual(unc_a.npv(0.60), 0.0, places=6)
        self.assertGreater(npv_20, 0)
        self.assertGreater(npv_30, npv_20)          # 折现率 20%→30%，NPV 上升（反直觉）
        self.assertAlmostEqual(npv_30, 71.01, delta=0.5)
        self.assertLess(unc_a.npv(0.70), 0)         # 超过第二个根后重新转负

    def test_multiple_irr_uses_npv_only_for_feasibility(self):
        """多重 IRR 项目的可行性必须仅由 NPV 判定，不得套用 IRR > r 规则。"""
        scenario = scenarios.case_4_unconventional_cash_flow(RATE)
        unc_b = next(p for p in scenario.projects if p.code == "UNC-B")
        ev = Evaluation.build(unc_b, RATE)
        # 主 IRR（5%）低于资本成本 10%，但 NPV = +12.40 > 0，应判可行
        self.assertLess(ev.irr, RATE)
        self.assertGreater(ev.npv, 0)
        self.assertTrue(ev.feasible)

    def test_case_4_conventional_project_has_unique_irr(self):
        """CASE-4 的常规对照项目 IRR 应唯一且低于资本成本。"""
        scenario = scenarios.case_4_unconventional_cash_flow(RATE)
        normal = next(p for p in scenario.projects if p.code == "UNC-C")
        detail = normal.irr_details()
        self.assertTrue(detail.is_unique)
        self.assertLess(detail.irr, RATE)
        self.assertFalse(Evaluation.build(normal, RATE).feasible)

    def test_figures_generated(self):
        """图表生成函数可正常产出文件。"""
        scenario = scenarios.case_1_independent_projects(RATE)
        evaluations = [Evaluation.build(p, RATE) for p in scenario.projects]
        path = visualizer.plot_npv_comparison(
            evaluations, filename="test_npv_comparison.png"
        )
        self.assertTrue(path.exists())
        self.assertGreater(path.stat().st_size, 5000)   # 文件非空且包含真实图像数据
        path.unlink()   # 清理测试产物


def load_tests(loader, tests, pattern):  # pragma: no cover
    """支持 unittest 自动发现。"""
    suite = unittest.TestSuite()
    for cls in (TestFinanceCore, TestMutualExclusion, TestCapitalRationing,
                TestSensitivity, TestAIAssistance, TestScenariosAndEndToEnd):
        suite.addTests(loader.loadTestsFromTestCase(cls))
    return suite


if __name__ == "__main__":
    unittest.main(verbosity=2)
