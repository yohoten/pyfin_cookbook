# -*- coding: utf-8 -*-
"""
test_all.py — 全流程自动化测试
====================================================================
覆盖六类断言，全部数值均可由 README「关键数值复核对照表」手工复算：

1. **核心算法数值**（:class:`TestCoreNumbers`）
   NPV / IRR / 多重 IRR / 互斥优选 / 资本限额 —— 对照手工计算；
2. **案例级指标**（:class:`TestCaseMetrics`）
   6 个案例共 31 个项目的 NPV / IRR / ANCF / PI 与可行项目数；
3. **决策逻辑**（:class:`TestDecisionLogic`）
   互斥冲突识别、增量 IRR 仲裁、排序法失效、背包法与组合法一致性；
4. **敏感性与临界点**（:class:`TestSensitivity`）
   安全边际、折现率冲击方向、临界点数学自洽性；
5. **AI 辅助功能**（:class:`TestAiFeature`）
   数据生成可复现性、建议文案方向与数字一致性；
6. **边界与交付一致性**（:class:`TestBoundary` / :class:`TestDeliverables`）
   退化输入必须给出明确错误或优雅降级；报告插图链接必须可达。

运行::

    python -m tests.test_all -v
"""

from __future__ import annotations

import os
import re
import sys
import unittest
from pathlib import Path

# 兼容「python -m tests.test_all」与「python tests/test_all.py」两种运行方式
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src import ai_advisor, ai_data_generator, finance_core as fc, optimizer as opt, scenarios
from src.models import Evaluation, Project
from src.sensitivity import one_way_sensitivity

RATE = 0.10


# ======================================================================
# 一、核心算法数值
# ======================================================================
class TestCoreNumbers(unittest.TestCase):
    """对照手工计算的数值断言（README「关键数值复核对照表」）。"""

    def test_npv_reference(self):
        """NPV(10%, [500,500,500], 1000) = 500×PVIFA(10%,3) − 1000 = 243.4260"""
        self.assertAlmostEqual(fc.npv(RATE, [500.0] * 3, 1000.0), 243.4260, places=3)

    def test_irr_reference(self):
        """PVIFA(r,3) = 2 → r = 23.3752%"""
        self.assertAlmostEqual(fc.irr([500.0] * 3, 1000.0), 0.233752, places=5)

    def test_irr_residual_near_zero(self):
        """IRR 回代 NPV 必须≈0（求解精度自检）。"""
        result = fc.irr_details([500.0] * 3, 1000.0)
        self.assertLess(abs(result.npv_at_irr), 1e-6)

    def test_npv_zero_rate(self):
        """零折现率时 NPV = ΣCF − I₀，与折现无关。"""
        self.assertAlmostEqual(fc.npv(0.0, [100.0, 200.0, 300.0], 400.0), 200.0, places=9)

    def test_pvifa_reference(self):
        """PVIFA(10%, 3) = (1 − 1.1⁻³) / 0.1 = 2.486852"""
        self.assertAlmostEqual(fc.pvifa(RATE, 3), 2.486852, places=6)

    def test_ancf_reference(self):
        """ANCF = NPV / PVIFA = 243.4260 / 2.486852 = 97.8852"""
        self.assertAlmostEqual(fc.annuity_net_cash_flow(243.4260, RATE, 3), 97.8852, places=3)

    def test_pi_reference(self):
        """PI = (NPV + I₀) / I₀ = (900 + 1800) / 1800 = 1.5"""
        self.assertAlmostEqual(fc.profitability_index(900.0, 1800.0), 1.5, places=9)

    def test_multiple_irr_roots(self):
        """UNC-A：解 3520x² − 5400x + 2000 = 0 → x = 5/11、5/8 → 10% / 60%"""
        result = fc.irr_details([5400.0, -3520.0], 2000.0)
        self.assertFalse(result.is_unique)
        self.assertEqual(len(result.all_roots), 2)
        self.assertAlmostEqual(result.all_roots[0], 0.10, places=6)
        self.assertAlmostEqual(result.all_roots[1], 0.60, places=6)

    def test_npv_non_monotonic(self):
        """UNC-A 的 NPV 关于 r 非单调：r 从 20% 升到 30%，NPV 反而上升。"""
        npv_20 = fc.npv(0.20, [5400.0, -3520.0], 2000.0)
        npv_30 = fc.npv(0.30, [5400.0, -3520.0], 2000.0)
        self.assertGreater(npv_30, npv_20)

    def test_unc_a_peak_npv(self):
        """UNC-A 最大 NPV = +71.02 万元（出现在 r ≈ 30.37%，由 NPV′(r)=0 解得）。"""
        best = max(
            (fc.npv(r / 10000.0, [5400.0, -3520.0], 2000.0), r / 10000.0)
            for r in range(2800, 3300)
        )
        self.assertAlmostEqual(best[0], 71.02, places=1)
        self.assertAlmostEqual(best[1], 0.3037, places=3)

    def test_mirr_positive_for_conventional(self):
        """常规现金流项目的 MIRR 应为有限正值且低于 IRR。"""
        irr = fc.irr([500.0] * 3, 1000.0)
        mirr = fc.mirr([500.0] * 3, 1000.0, RATE, RATE)
        self.assertTrue(0.0 < mirr < irr)

    def test_payback_reference(self):
        """静态回收期：投资 1000、年流入 500 → 2 年整。"""
        self.assertAlmostEqual(fc.payback_period([500.0] * 3, 1000.0), 2.0, places=9)

    def test_discounted_payback_slower_than_static(self):
        """动态回收期必然不短于静态回收期。"""
        static = fc.payback_period([500.0] * 3, 1000.0)
        dynamic = fc.discounted_payback_period([500.0] * 3, 1000.0, RATE)
        self.assertGreater(dynamic, static)


# ======================================================================
# 二、案例级指标
# ======================================================================
class TestCaseMetrics(unittest.TestCase):
    """6 个案例 31 个项目的关键指标（对照 README §四 与 §十）。"""

    @classmethod
    def setUpClass(cls):
        cls.cases = {s.key: s for s in scenarios.all_cases(RATE)}

    def _evaluations(self, key: str):
        scenario = self.cases[key]
        return {e.project.code: e for e in
                (Evaluation.build(p, RATE) for p in scenario.projects)}

    def test_case_count(self):
        """必须有 6 个案例、共 31 个项目。"""
        self.assertEqual(len(self.cases), 6)
        total = sum(len(s.projects) for s in self.cases.values())
        self.assertEqual(total, 31)

    def test_case1_independent(self):
        """CASE-1：IND-A 可行、IND-B 不可行（一正一负形成对照）。"""
        evs = self._evaluations("CASE-1")
        self.assertAlmostEqual(evs["IND-A"].npv, 198.6563, places=3)
        self.assertTrue(evs["IND-A"].feasible)
        self.assertAlmostEqual(evs["IND-B"].npv, -202.8967, places=3)
        self.assertFalse(evs["IND-B"].feasible)

    def test_case2_mutually_exclusive(self):
        """CASE-2：规模冲突组 NPV 选 MUT-Q、IRR 选 MUT-P；寿命组 ANCF 选 MUT-X。"""
        evs = self._evaluations("CASE-2")
        self.assertAlmostEqual(evs["MUT-P"].npv, 119.0834, places=3)
        self.assertAlmostEqual(evs["MUT-Q"].npv, 221.6379, places=3)
        self.assertAlmostEqual(evs["MUT-X"].ancf, 30.3926, places=3)
        # 规模冲突：NPV 与 IRR 给出相反排序
        self.assertGreater(evs["MUT-Q"].npv, evs["MUT-P"].npv)
        self.assertGreater(evs["MUT-P"].irr, evs["MUT-Q"].irr)
        # 寿命冲突：NPV 选 MUT-Y，ANCF 选 MUT-X
        self.assertGreater(evs["MUT-Y"].npv, evs["MUT-X"].npv)
        self.assertGreater(evs["MUT-X"].ancf, evs["MUT-Y"].ancf)
        self.assertEqual(sum(1 for e in evs.values() if e.feasible), 4)

    def test_case3_capital_rationing_metrics(self):
        """CASE-3：8 个项目全部可行，CAP-A 的 NPV 恰为 900（构造值）。"""
        evs = self._evaluations("CASE-3")
        self.assertEqual(len(evs), 8)
        self.assertAlmostEqual(evs["CAP-A"].npv, 900.0, places=2)
        self.assertAlmostEqual(evs["CAP-A"].pi, 1.5, places=4)
        self.assertEqual(sum(1 for e in evs.values() if e.feasible), 8)

    def test_case4_unconventional(self):
        """CASE-4：UNC-A / UNC-B 各 2 个实根；可行性只由 NPV 判定。"""
        evs = self._evaluations("CASE-4")
        self.assertEqual(len(evs["UNC-A"].irr_result.all_roots), 2)
        self.assertEqual(len(evs["UNC-B"].irr_result.all_roots), 2)
        self.assertFalse(evs["UNC-A"].irr_result.is_unique)
        # UNC-A 在 10% 处 NPV 恰为 0 → 不可行；UNC-B NPV > 0 → 可行（尽管 IRR=5% < 10%）
        self.assertAlmostEqual(evs["UNC-A"].npv, 0.0, places=6)
        self.assertFalse(evs["UNC-A"].feasible)
        self.assertTrue(evs["UNC-B"].feasible)
        self.assertLess(evs["UNC-B"].irr, RATE)
        self.assertEqual(sum(1 for e in evs.values() if e.feasible), 1)

    def test_case5_sensitivity_metrics(self):
        """CASE-5：SENS-S 安全边际 6.00pp、SENS-W 仅 0.70pp。"""
        evs = self._evaluations("CASE-5")
        self.assertAlmostEqual(evs["SENS-S"].irr, 0.159965, places=6)
        self.assertAlmostEqual(evs["SENS-W"].irr, 0.107044, places=6)
        sens_s = one_way_sensitivity(evs["SENS-S"].project, RATE)
        sens_w = one_way_sensitivity(evs["SENS-W"].project, RATE)
        self.assertAlmostEqual(sens_s.safety_margin * 100, 6.00, places=1)
        self.assertAlmostEqual(sens_w.safety_margin * 100, 0.70, places=1)
        self.assertEqual(sens_s.grade, "较强")
        self.assertEqual(sens_w.grade, "极弱")

    def test_case6_batch_reproducible(self):
        """CASE-6：AI 生成的 12 个项目全部可行，且两组生成结果完全一致（固定种子）。"""
        evs = self._evaluations("CASE-6")
        self.assertEqual(len(evs), 12)
        self.assertEqual(sum(1 for e in evs.values() if e.feasible), 12)
        again = [Evaluation.build(p, RATE).npv for p in self.cases["CASE-6"].projects]
        first = [evs[p.code].npv for p in self.cases["CASE-6"].projects]
        self.assertEqual(len(again), len(first))
        for a, b in zip(first, again):
            self.assertAlmostEqual(a, b, places=9)

    def test_feasible_counts_all_cases(self):
        """全部案例的可行项目数（对照 README §0.2 基线）。"""
        expected = {"CASE-1": 1, "CASE-2": 4, "CASE-3": 8,
                    "CASE-4": 1, "CASE-5": 2, "CASE-6": 12}
        actual = {}
        for key, scenario in self.cases.items():
            actual[key] = sum(
                1 for p in scenario.projects if Evaluation.build(p, RATE).feasible
            )
        self.assertEqual(actual, expected)


# ======================================================================
# 三、决策逻辑
# ======================================================================
class TestDecisionLogic(unittest.TestCase):
    """互斥优选与资本限额组合优化的决策正确性。"""

    @classmethod
    def setUpClass(cls):
        cls.case2 = scenarios.get_case("CASE-2", RATE)
        cls.case3 = scenarios.get_case("CASE-3", RATE)

    def test_mutual_conflict_detected(self):
        """CASE-2 的两组冲突必须都被识别出来。"""
        groups = {mr.group: mr for mr in opt.select_mutually_exclusive(self.case2.projects, RATE)}
        self.assertIn("MUT-SCALE", groups)
        self.assertIn("MUT-LIFE", groups)
        self.assertTrue(groups["MUT-SCALE"].conflict_npv_irr)     # NPV 与 IRR 冲突
        self.assertTrue(groups["MUT-LIFE"].conflict_npv_ancf)     # NPV 与 ANCF 冲突

    def test_incremental_irr_arbitration(self):
        """规模冲突组：增量 IRR = 14.25% > 10%，应选大投资方案 MUT-Q。"""
        groups = {mr.group: mr for mr in opt.select_mutually_exclusive(self.case2.projects, RATE)}
        inc = groups["MUT-SCALE"].incremental
        self.assertIsNotNone(inc)
        self.assertEqual(inc["增量投资额(万元)"], 1500.0)
        self.assertEqual(inc["增量IRR"], "14.25%")
        self.assertIn("MUT-Q", groups["MUT-SCALE"].recommendation)

    def test_life_conflict_uses_ancf(self):
        """寿命冲突组：必须改用年金净流量法，选择 MUT-X。"""
        groups = {mr.group: mr for mr in opt.select_mutually_exclusive(self.case2.projects, RATE)}
        self.assertIn("MUT-X", groups["MUT-LIFE"].recommendation)

    def test_ranking_method_fails(self):
        """排序法（PI 贪心）在额度不可分割时失效：得 CAP-A + CAP-D，闲置 200 万。"""
        result = opt.ranking_method(self.case3.projects, RATE, self.case3.budget)
        self.assertEqual(result.codes, "CAP-A + CAP-D")
        self.assertAlmostEqual(result.total_npv, 1370.0, places=1)
        self.assertAlmostEqual(result.idle_budget, 200.0, places=6)

    def test_combination_method_global_optimum(self):
        """组合法穷举得全局最优：CAP-B + CAP-C，组合 NPV 1460。"""
        result = opt.combination_method(self.case3.projects, RATE, self.case3.budget)
        self.assertEqual(result.codes, "CAP-B + CAP-C")
        self.assertAlmostEqual(result.total_npv, 1460.0, places=1)

    def test_combination_beats_ranking(self):
        """组合法必须严格优于排序法（这正是 CASE-3 的教学要点）。"""
        ranking = opt.ranking_method(self.case3.projects, RATE, self.case3.budget)
        combination = opt.combination_method(self.case3.projects, RATE, self.case3.budget)
        self.assertGreater(combination.total_npv, ranking.total_npv)
        self.assertAlmostEqual(combination.total_npv - ranking.total_npv, 90.0, places=1)

    def test_knapsack_matches_combination(self):
        """背包法（0-1 DP）与组合法必须给出相同的组合 NPV —— 交叉验证最优性。"""
        combination = opt.combination_method(self.case3.projects, RATE, self.case3.budget)
        knapsack = opt.knapsack_method(self.case3.projects, RATE, self.case3.budget)
        self.assertAlmostEqual(knapsack.total_npv, combination.total_npv, places=6)

    def test_knapsack_matches_combination_on_random_set(self):
        """随机构造的 12 个项目上，两法仍必须一致（避免只对 CASE-3 调参）。"""
        projects = [
            Project(
                code=f"R{i:02d}", name=f"随机项目{i}", industry="测试",
                initial_investment=800.0 + 700.0 * ((i * 37) % 11),
                cash_flows=[300.0 + 60.0 * ((i + t) % 9) for t in range(3 + i % 6)],
            )
            for i in range(12)
        ]
        combination = opt.combination_method(projects, RATE, 6000.0)
        knapsack = opt.knapsack_method(projects, RATE, 6000.0)
        self.assertAlmostEqual(knapsack.total_npv, combination.total_npv, places=6)

    def test_portfolio_no_over_budget(self):
        """最优组合的合计投资不得超过资本限额。"""
        report = opt.optimize_portfolio(self.case3.projects, RATE, self.case3.budget)
        self.assertLessEqual(report.best.total_investment, self.case3.budget + 1e-6)
        self.assertGreaterEqual(report.best.idle_budget, 0.0)

    def test_negative_npv_projects_excluded(self):
        """负 NPV 项目不得进入任何组合（CASE-1 含一个负 NPV 项目）。"""
        case1 = scenarios.get_case("CASE-1", RATE)
        result = opt.combination_method(case1.projects, RATE, 5000.0)
        self.assertNotIn("IND-B", result.codes)

    def test_zero_budget_returns_empty(self):
        """额度为 0 是合法输入：三种方法都应返回空组合而非报错。"""
        for method in (opt.ranking_method, opt.combination_method, opt.knapsack_method):
            result = method(self.case3.projects, RATE, 0.0)
            self.assertEqual(len(result.selected), 0)
            self.assertAlmostEqual(result.total_npv, 0.0, places=9)
            self.assertAlmostEqual(result.idle_budget, 0.0, places=9)


# ======================================================================
# 四、敏感性与临界点
# ======================================================================
class TestSensitivity(unittest.TestCase):
    """敏感性分析、临界点分析与安全边际的数学自洽性。"""

    @classmethod
    def setUpClass(cls):
        case5 = scenarios.get_case("CASE-5", RATE)
        cls.strong, cls.weak = case5.projects

    def test_swing_descending(self):
        """tornado 图按 swing 降序排列 —— 排序键必须单调不增。"""
        sens = one_way_sensitivity(self.strong, RATE)
        swings = [f.swing for f in sens.factors]
        self.assertEqual(swings, sorted(swings, reverse=True))

    def test_rate_shock_direction(self):
        """折现率上升 5pp：抗风险强项目 NPV 仍为正，弱项目由正转负。"""
        sens_s = one_way_sensitivity(self.strong, RATE)
        sens_w = one_way_sensitivity(self.weak, RATE)
        rate_s = next(f for f in sens_s.factors if f.name == "折现率")
        rate_w = next(f for f in sens_w.factors if f.name == "折现率")
        self.assertGreater(rate_s.adverse_npv, 0.0)      # 强项目仍然可行
        self.assertLess(rate_w.adverse_npv, 0.0)         # 弱项目被击穿
        self.assertFalse(rate_s.critical)
        self.assertTrue(rate_w.critical)

    def test_safety_margin_equals_irr_minus_rate(self):
        """安全边际 ≡ IRR − 资本成本。"""
        sens = one_way_sensitivity(self.strong, RATE)
        self.assertAlmostEqual(sens.safety_margin, sens.base_irr - RATE, places=9)

    def test_adverse_worse_than_favorable(self):
        """每个因素的不利方向 NPV 都应低于有利方向。"""
        for project in (self.strong, self.weak):
            for factor in one_way_sensitivity(project, RATE).factors:
                self.assertLess(factor.adverse_npv, factor.favorable_npv)

    def test_breakeven_rate_equals_irr(self):
        """「折现率最大可上升幅度」≡ IRR − 基准折现率（临界折现率即 IRR）。"""
        sens = one_way_sensitivity(self.strong, RATE)
        limit_pp = sens.breakeven.get("折现率最大可上升幅度(pp)")
        self.assertIsNotNone(limit_pp)
        self.assertAlmostEqual(limit_pp, (sens.base_irr - RATE) * 100, places=6)

    def test_breakeven_npv_is_zero(self):
        """把初始投资抬到临界上限，NPV 应近似为 0。"""
        sens = one_way_sensitivity(self.strong, RATE)
        limit = sens.breakeven.get("初始投资最大可上升幅度")
        self.assertIsNotNone(limit)
        critical_inv = self.strong.initial_investment * (1.0 + limit)
        npv_at_critical = fc.npv(RATE, self.strong.cash_flows, critical_inv)
        self.assertAlmostEqual(npv_at_critical, 0.0, places=4)

    def test_breakeven_cash_flow_npv_is_zero(self):
        """把年现金流压到临界下限，NPV 应近似为 0。"""
        sens = one_way_sensitivity(self.strong, RATE)
        limit = sens.breakeven.get("年现金流最大可下降幅度")
        self.assertIsNotNone(limit)
        scaled = [c * (1.0 - limit) for c in self.strong.cash_flows]
        self.assertAlmostEqual(fc.npv(RATE, scaled, self.strong.initial_investment),
                               0.0, places=4)

    def test_two_way_matrix_monotonic_in_rate(self):
        """双因素矩阵：现金流固定时（同一行），折现率越高 NPV 越低。"""
        from src.sensitivity import two_way_sensitivity
        matrix, rate_axis, cf_axis = two_way_sensitivity(self.strong, RATE)
        self.assertEqual(len(matrix), len(cf_axis))
        for row in matrix:
            self.assertEqual(len(row), len(rate_axis))
            self.assertEqual(row, sorted(row, reverse=True))

    def test_life_factor_skipped_for_single_period(self):
        """单期项目不该生成「项目寿命」因素（避免 nan 参与排序）。"""
        single = Project(code="ONE", name="单期项目", industry="测试",
                         initial_investment=100.0, cash_flows=[300.0])
        names = [f.name for f in one_way_sensitivity(single, RATE).factors]
        self.assertNotIn("项目寿命", names)
        # 且不得有任何 nan 混进 swing
        for factor in one_way_sensitivity(single, RATE).factors:
            self.assertFalse(factor.swing != factor.swing)


# ======================================================================
# 五、AI 辅助功能
# ======================================================================
class TestAiFeature(unittest.TestCase):
    """AI 数据生成与决策建议的可用性、可复现性与方向正确性。"""

    def test_data_generation_reproducible(self):
        """同一模块内连续两次生成结果必须完全一致（固定随机种子）。"""
        first = ai_data_generator.generate_projects(count_per_industry=2)
        second = ai_data_generator.generate_projects(count_per_industry=2)
        self.assertEqual(len(first), len(second))
        for a, b in zip(first, second):
            self.assertEqual(a.code, b.code)
            self.assertAlmostEqual(a.initial_investment, b.initial_investment, places=9)
            self.assertEqual(list(a.cash_flows), list(b.cash_flows))

    def test_profile_table_complete(self):
        """行业原型表必须覆盖 6 个行业，且字段齐备。"""
        rows = ai_data_generator.profiles_to_table()
        self.assertEqual(len(rows), 6)
        required = {"行业原型", "投资规模区间(万元)", "寿命区间(年)", "现金回收效率",
                    "成长率", "波动率", "现金流形态", "风险等级"}
        for row in rows:
            self.assertTrue(required.issubset(row.keys()), f"缺字段：{required - set(row)}")
            self.assertIn("~", row["投资规模区间(万元)"])
            self.assertIn("~", row["寿命区间(年)"])
        # 四种现金流形态应全部出现过（steady / growth / jcurve / cycle）
        patterns = {row["现金流形态"] for row in rows}
        self.assertIn("稳定型", patterns)
        self.assertIn("成长型", patterns)

    def test_advice_direction_for_feasible_project(self):
        """可行项目的建议必须归类为「可行」、不可行项目为「不可行」，风险评分在 0~100。"""
        case = scenarios.get_case("CASE-1", RATE)
        evals = [Evaluation.build(p, RATE) for p in case.projects]
        sens = {e.project.code: one_way_sensitivity(e.project, RATE) for e in evals}
        advices = ai_advisor.generate_batch_advice(evals, sens)
        by_code = {a.code: a for a in advices}
        self.assertTrue(by_code["IND-A"].verdict.startswith("可行"))
        self.assertTrue(by_code["IND-B"].verdict.startswith("不可行"))
        for advice in advices:
            self.assertTrue(0 <= advice.risk_score <= 100)

    def test_advice_numbers_traceable(self):
        """建议文案中的风险评分必须能追溯到规则引擎（离线可复现，无幻觉数字）。"""
        case = scenarios.get_case("CASE-5", RATE)
        evals = [Evaluation.build(p, RATE) for p in case.projects]
        sens = {e.project.code: one_way_sensitivity(e.project, RATE) for e in evals}
        first = ai_advisor.generate_batch_advice(evals, sens)
        second = ai_advisor.generate_batch_advice(evals, sens)
        for a, b in zip(first, second):
            self.assertEqual(a.risk_score, b.risk_score)
            self.assertEqual(a.headline, b.headline)
            self.assertEqual(a.verdict, b.verdict)

    def test_summarize_advice_non_empty(self):
        """汇总文案必须包含项目总数与可行/不可行计数。"""
        case = scenarios.get_case("CASE-1", RATE)
        evals = [Evaluation.build(p, RATE) for p in case.projects]
        sens = {e.project.code: one_way_sensitivity(e.project, RATE) for e in evals}
        text = ai_advisor.summarize_advice(ai_advisor.generate_batch_advice(evals, sens))
        self.assertTrue(text.strip())
        self.assertIn("2", text)

    def test_ai_mode_defaults_to_rule_without_key(self):
        """未配置 API Key 时必须降级为规则引擎，且不抛错。"""
        self.assertFalse(ai_advisor.LLM_AVAILABLE)
        case = scenarios.get_case("CASE-1", RATE)
        evals = [Evaluation.build(p, RATE) for p in case.projects]
        sens = {e.project.code: one_way_sensitivity(e.project, RATE) for e in evals}
        advices = ai_advisor.generate_batch_advice(evals, sens, use_llm=False)
        self.assertTrue(all(a.generated_by for a in advices))


# ======================================================================
# 六、边界与退化输入
# ======================================================================
class TestBoundary(unittest.TestCase):
    """退化输入必须给出明确错误或优雅降级，而不是崩溃或静默错值。"""

    def test_npv_invalid_rate(self):
        """折现率 ≤ −100% 无意义，应抛 ValueError。"""
        with self.assertRaises(ValueError):
            fc.npv(-1.5, [100.0], 100.0)

    def test_pvifa_zero_periods(self):
        """期数为 0 时年金现值系数无定义。"""
        with self.assertRaises(ValueError):
            fc.pvifa(RATE, 0)

    def test_pi_zero_investment(self):
        """零投资无法定义 PI（应抛错，由 Evaluation.build 负责降级）。"""
        with self.assertRaises(ValueError):
            fc.profitability_index(100.0, 0.0)

    def test_empty_cash_flows_raises_clear_error(self):
        """空现金流项目：必须抛出带项目编号的明确错误。"""
        project = Project(code="Z2", name="空现金流", industry="测试",
                          initial_investment=100.0, cash_flows=[])
        with self.assertRaises(ValueError) as ctx:
            Evaluation.build(project, RATE)
        self.assertIn("Z2", str(ctx.exception))

    def test_zero_investment_degrades_without_crash(self):
        """零投资项目：降级为 PI 不适用，NPV/IRR 照常计算，不中断流程。"""
        project = Project(code="Z1", name="零投资", industry="测试",
                          initial_investment=0.0, cash_flows=[100.0, 100.0])
        evaluation = Evaluation.build(project, RATE)
        self.assertFalse(evaluation.pi == evaluation.pi)        # PI 为 nan
        self.assertAlmostEqual(evaluation.npv, 173.5537, places=3)
        self.assertTrue(evaluation.feasible)
        self.assertEqual(evaluation.to_dict()["盈利能力指数PI"], "不适用")

    def test_degenerate_project_does_not_break_batch(self):
        """批量评价中混入一个退化项目，其余项目结果不受影响。"""
        case = scenarios.get_case("CASE-1", RATE)
        projects = list(case.projects) + [
            Project(code="BAD", name="空现金流", industry="测试",
                    initial_investment=100.0, cash_flows=[])
        ]
        results, skipped = [], []
        for project in projects:
            try:
                results.append(Evaluation.build(project, RATE))
            except ValueError as exc:
                skipped.append(str(exc))
        self.assertEqual(len(results), len(case.projects))
        self.assertEqual(len(skipped), 1)
        self.assertEqual(results[0].project.code, "IND-A")

    def test_all_zero_cash_flow_irr_is_none(self):
        """全零现金流：NPV 恒为 0，IRR 无定义，应返回 None。"""
        self.assertIsNone(fc.irr([0.0, 0.0], 0.0))
        self.assertEqual(fc.irr_all_roots([0.0, 0.0], 0.0), [])

    def test_single_period_irr_exact(self):
        """单期现金流有解析解：CF₁/I₀ − 1 = 2.0，必须精确到机器精度。"""
        self.assertEqual(fc.irr([300.0], 100.0), 2.0)

    def test_single_period_irr_below_lower_bound(self):
        """单期现金流 IRR < −99% 时视为无实根（超出搜索下界）。"""
        self.assertIsNone(fc.irr([0.5], 100.0))

    def test_negative_budget_rejected(self):
        """负资本限额应被拒绝（此前会返回负的闲置额度）。"""
        case = scenarios.get_case("CASE-3", RATE)
        for method in (opt.ranking_method, opt.combination_method, opt.knapsack_method):
            with self.assertRaises(ValueError):
                method(case.projects, RATE, -100.0)
        with self.assertRaises(ValueError):
            opt.optimize_portfolio(case.projects, RATE, -100.0)

    def test_nan_budget_rejected(self):
        """NaN 额度应被拒绝，而不是产出 nan 报表。"""
        case = scenarios.get_case("CASE-3", RATE)
        with self.assertRaises(ValueError):
            opt.ranking_method(case.projects, RATE, float("nan"))

    def test_empty_projects_returns_empty_portfolio(self):
        """空项目列表：应返回空组合而非崩溃。"""
        result = opt.combination_method([], RATE, 3000.0)
        self.assertEqual(len(result.selected), 0)
        self.assertAlmostEqual(result.total_npv, 0.0, places=9)

    def test_cash_flow_table_empty(self):
        """空项目列表的现金流表应为空，不抛错。"""
        from main import _cash_flow_table
        self.assertEqual(_cash_flow_table([]), [])

    def test_negative_investment_rejected(self):
        """初始投资额必须用正数输入（符号由内部处理），负数应给出明确错误。"""
        with self.assertRaises(ValueError) as ctx:
            fc.npv(RATE, [0.0], -100.0)
        self.assertIn("正数", str(ctx.exception))


# ======================================================================
# 七、交付一致性
# ======================================================================
class TestDeliverables(unittest.TestCase):
    """交付物的一致性：报告插图链接可达、docs 资产齐备、自述数字与实物相符。"""

    @staticmethod
    def _check_image_links(report_path: Path) -> tuple:
        """返回 (链接总数, 不可达链接列表)。"""
        text = report_path.read_text(encoding="utf-8")
        links = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text)
        broken = []
        for link in links:
            target = (report_path.parent / link).resolve()
            if not target.exists():
                broken.append(link)
        return len(links), broken

    def test_outputs_report_image_links_reachable(self):
        """outputs/reports 下的 Markdown 报告，插图链接必须 100% 可达（P0-2）。"""
        report = _PROJECT_ROOT / "outputs" / "reports" / "投资项目决策评价报告.md"
        if not report.exists():
            self.skipTest("报告尚未生成，先运行 python main.py")
        total, broken = self._check_image_links(report)
        self.assertGreater(total, 0, "报告里应当有插图")
        self.assertEqual(broken, [], f"存在断链插图：{broken[:3]}")

    def test_docs_report_image_links_reachable(self):
        """docs/ 下的交付版报告，插图链接同样必须 100% 可达。"""
        report = _PROJECT_ROOT / "docs" / "投资项目决策评价报告.md"
        if not report.exists():
            self.skipTest("docs/ 尚未发布，先运行 python tools/publish_docs.py")
        total, broken = self._check_image_links(report)
        self.assertGreater(total, 0)
        self.assertEqual(broken, [], f"存在断链插图：{broken[:3]}")

    def test_rel_image_is_relative_to_report(self):
        """_rel_image 应以报告自身目录为基准（而非程序包根目录）。"""
        from src.report_generator import _rel_image
        fig = _PROJECT_ROOT / "outputs" / "figures" / "x.png"
        report = _PROJECT_ROOT / "outputs" / "reports" / "r.md"
        self.assertEqual(_rel_image(fig, report), "../figures/x.png")

    def test_tests_package_importable(self):
        """tests 包必须可导入（README 第 6 条命令依赖它）。"""
        import tests  # noqa: F401
        self.assertTrue((_PROJECT_ROOT / "tests" / "test_all.py").exists())

    def test_gitignore_keeps_outputs_ignored(self):
        """.gitignore 必须继续忽略运行时产物目录 outputs/。"""
        gitignore = (_PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertRegex(gitignore, r"(?m)^outputs/")

    def test_pyproject_declares_tools(self):
        """pyproject.toml 应声明 ruff 与 mypy 配置。"""
        pyproject = _PROJECT_ROOT / "pyproject.toml"
        self.assertTrue(pyproject.exists())
        text = pyproject.read_text(encoding="utf-8")
        self.assertIn("[tool.ruff]", text)
        self.assertIn("[tool.mypy]", text)

    def test_readme_numbers_match_reality(self):
        """README 自述的断言数、图表数必须与实物一致（P2-2）。"""
        readme = (_PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        # 断言数：README 中声明的数字必须等于本文件的用例数
        numbers = set(int(n) for n in re.findall(r"(\d+)\s*项(?:单元测试与案例)?断言", readme))
        numbers |= set(int(n) for n in re.findall(r"Ran (\d+) tests", readme))
        if numbers:
            self.assertEqual(numbers, {_count_tests()})
        # 图表数：若 outputs 已有产物，README 声明的数量必须等于目录中的 PNG 数
        figures = list((_PROJECT_ROOT / "outputs" / "figures").glob("*.png"))
        if figures:
            declared = set(int(n) for n in re.findall(r"(\d+)\s*张(?:200 DPI)?图表", readme))
            if declared:
                self.assertEqual(declared, {len(figures)})


def _count_tests() -> int:
    """统计本测试文件中的用例数量。"""
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    return suite.countTestCases()


# ======================================================================
if __name__ == "__main__":
    unittest.main(verbosity=2)
