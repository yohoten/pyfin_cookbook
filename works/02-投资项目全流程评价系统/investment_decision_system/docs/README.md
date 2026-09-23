# docs/ — 交付资产说明

本目录存放**正式提交版**的报告与图表（实践要求 §五「提交的材料：1. 报告 2. Python 程序包」）。

## 与 `outputs/` 的区别

| 目录 | 性质 | 是否纳入版本库 | 说明 |
| :--- | :--- | :--- | :--- |
| `docs/` | **交付资产**，由 `outputs/` 定稿后发布而来 | ✅ 纳入 | 评审方 clone 后可直接查看，无需运行程序 |
| `outputs/` | **运行产物**，每次 `python main.py` 都会覆写 | ❌ 忽略 | 生成源，可随时清空重建 |

> **为什么要分两个目录**：早期版本的 `.gitignore` 直接忽略整个 `outputs/`，
> 而报告的唯一形态恰好就在 `outputs/reports/` 下 —— 结果远程仓库里只有源码，
> 没有报告、没有图表。把"生成产物"与"交付资产"分开放，运行多少次都不会污染交付物。

## 目录内容

| 路径 | 内容 |
| :--- | :--- |
| `投资项目决策评价报告.md` | Markdown 报告（插图以 `figures/` 为相对基准，链接 100% 可达） |
| `投资项目决策评价报告.docx` | Word 报告（图表已嵌入文档，独立于本目录） |
| `figures/` | 全部图表 PNG（200 DPI），与报告中引用的文件名一一对应 |
| `data/` | `projects.csv`、`evaluations.csv`（项目基础数据与全指标评价结果） |

## 更新流程

```bash
# 1. 重新生成产物（写入 outputs/）
python main.py

# 2. 确认回归全绿
python -m tests.test_all

# 3. 把定稿产物发布到本目录（自动校验插图链接可达性）
python tools/publish_docs.py

# 4. 提交
git add docs && git commit -m "更新交付报告与图表"
```

## 注意事项

* **不要手工编辑本目录下的报告与图表**。它们是生成物，下次发布会被覆盖。
  需要改内容请改 `src/` 下的代码，需要改口径请改 `main.py` 的 `_method_notes()`。
* 报告中的插图链接基准是**报告自身所在目录**（见 `src/report_generator.py::_rel_image`），
  因此同一份报告放在 `outputs/reports/` 或 `docs/` 下，链接都成立 —— 这是 `publish_docs.py`
  能直接复制而不改写链接的前提。
* 若某次运行后图表数量变化，`docs/figures/` 会自动清空重建，不会残留旧图。
