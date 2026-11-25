# 目录结构检查判据

## 核对路径归属

1. 按[项目规模与取证范围](project-size.md)确定本轮要检查的目录、工作区和业务入口。沿根目录及模块自己的 README、贡献指南和 `AGENTS.md` 查找明确的目录职责。对照当前启用的工作区、构建、路由、包导出和测试配置，确认哪些规则实际约束文件位置，哪些规则只描述现状。按适用范围核实局部规则和明确例外。
2. 从实际文件路径、入口或调用位置核实文件职责，和适用规则逐项对照。记录实际路径、预期目录、规则出处和影响。沿用项目认可的测试布局，例如测试和被测源码共置。遇到生成文件、依赖目录、构建产物或链接入口时，先识别其用途，按对应约定判断。
3. 文件名或同类模块的布局只能提供归属线索。只找到惯例、适用规则相互冲突或相关配置无法读取时，将受影响路径的预期归属标为「待确认」，写明还需要核实的规则。资料缺口只影响依赖该资料的判断，保留已有独立证据的结论。适用范围内确实没有需验证的目录职责时，说明入口、结构和理由，记录「不适用」。

只有路径和适用规则均已核实，才报告符合或偏离约定。对偏离项给出可定位的预期位置，以及对导入、构建、测试发现或维护的具体影响。目录归属在本节判断，图中节点和关系在架构图检查中判断。

修订前复查目标路径和调用方。获得写入授权且可独立回退时，沿现有验收方法记录基线，成组调整路径、导入、构建和测试配置以及文档引用，再验证原入口和受影响的检查仍可通过。目标位置被占用或缺少验收条件时，记录受阻位置和待核实项。仅检查时把已确认的偏离和调整位置交给用户。

## 交给汇总脚本的记录

用 `python3 -B <本 Skill 目录>/scripts/directory_structure.py` 从标准输入读取 UTF-8 JSON，也可在命令末尾传入记录文件。宿主判断规则及路径归属，脚本输出「目录结构」Markdown。单独运行可传入与必要文档相同格式的 `project`，合并报告时只需在首个章节列规模。

- `scope` 为非空字符串数组，记录实际查过的位置。`unread` 的每项含 `source` 和 `reason`，用于说明可能影响本轮的未读资料，无则传 `[]`。
- `checks` 的每项含 `path`（实际路径）、`basis`（下表标识）、`detail`（规则内容或判断理由）、`evidence`（非空出处数组，含路径和行号或章节）。`expected` 记录预期路径或目录，`rule` 和 `convention` 必填。只看到部分目录且暂无可核对路径时，可传 `checks: []` 并提供 `unread`。

| `basis` | 含义 | 其他字段 |
| --- | --- | --- |
| `rule` | 已核实且适用的项目约定或配置 | `matches` 为 `true` 时符合，为 `false` 时偏离。偏离时 `expected` 给出可定位的调整位置，`impact` 写明影响。 |
| `convention` | 仅有同类目录布局等惯例 | `expected` 为推测位置，报告标为待确认。 |
| `unknown` | 规则冲突、资料受限或归属尚未核实 | 可记录暂拟的 `expected`，报告标为待确认。 |
| `not_applicable` | 该路径或范围无需检查目录归属 | 在 `detail` 和 `evidence` 写明结构依据。 |

### 最小示例

在本仓库根目录运行下列命令，用虚构的订单模块验证同目录测试和错放模块的报告。

```sh
python3 -B skills/code-architect-skills/scripts/directory_structure.py <<'JSON'
{
  "scope": ["读取 AGENTS.md 并核对 src/orders/ 和 src/shared/"],
  "unread": [],
  "checks": [
    {
      "path": "src/orders/test_export.py", "expected": "src/orders/", "basis": "rule", "matches": true,
      "detail": "测试与被测源码同目录。", "evidence": ["AGENTS.md:8", "src/orders/export.py:1"]
    },
    {
      "path": "src/shared/totals.py", "expected": "src/orders/totals.py", "basis": "rule", "matches": false,
      "detail": "订单独有的业务规则须放在订单模块。", "evidence": ["AGENTS.md:9", "src/shared/totals.py:4"],
      "impact": "维护者会在共享目录找到订单专用逻辑。调整时需同步更新导出入口的导入。"
    }
  ]
}
JSON
```

报告应标记共置测试符合约定，并只建议调整 `totals.py`。如果删去对应约定，仅能从同类模块推断归属，改用 `convention` 并引用实际样例，结果应为待确认。
