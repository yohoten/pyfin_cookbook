# -*- coding: utf-8 -*-
"""
analysis —— 财务报表分析模块集合

模块划分
--------
loader     数据装载（原始数据 -> 规范科目 × 年份 的报表 DataFrame）
verify     双数据源交叉核验
structure  项目结构分析（共同比 / 垂直分析）
trend      项目趋势分析（定基指数 + 环比增长率）
indicators 财务指标分析（偿债 / 营运 / 盈利 / 发展 / 现金）
dupont     杜邦分析（三因素 + 五因素 + 连环替代法定量归因）
charts     图表输出
"""

__all__ = ["loader", "verify", "structure", "trend", "indicators",
           "dupont", "charts"]
