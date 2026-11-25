# 代码异味检查判据

## 取证与判断

按[项目规模与取证范围](project-size.md)选定本轮的源码和业务路径。沿入口读取函数、调用方和相关测试，排除与本轮无关的生成物及第三方代码。采用当前项目实际配置的语言规则或可复现的试点口径。记录已读范围、用到的规则和实际观测值。可见范围受限时列出未读位置及原因。

按实际函数声明定位方法，报告相对路径、限定名和起止行。只把能说明具体维护影响的信号列为发现。同一函数保留各类别证据，合为一项治理候选。

| 标识 | 类别 | 确认所需证据 |
| --- | --- | --- |
| `long_method` | 长方法 | 方法体有效代码行数、计数口径，以及需要跨越的处理阶段。 |
| `deep_nested_logic` | 深层嵌套 | 一条实际路径经过的分支或循环位置、最大深度，以及深入后需记住的外层判断。 |
| `bumpy_road` | 多段嵌套逻辑 | 同一路径上前后独立的至少两段嵌套逻辑，各自的起止位置、职责及可分别验证的行为。单段深嵌套和互斥分支各自只提供局部信号。 |
| `complex_conditional` | 复杂条件表达式 | 单条表达式、可辨认的子条件及其组合，附一组容易误判的输入或边界。 |
| `complex_method` | 复杂方法 | 决策点、需要覆盖的主要路径和维护影响。项目有可靠的圈复杂度口径时可一并记录。 |

方法级结论按五类分别给出「发现问题」「范围内未发现」「待确认」或「不适用」。待确认和不适用写明理由。只看到长文件、长行、相似代码或测量值越线时，先核对具体方法和业务语义。保留已证实的局部发现，并写明未覆盖的范围。

## Python 结构信号

有 Python 源码时，可在目标仓库根目录向 [python_smell_signals.py](../scripts/python_smell_signals.py) 传入本轮选定的文件。它基于本地 Python AST 和词法记号，输出已读文件、方法数、信号位置与未读原因。使用支持目标源码语法的解释器。其他语言使用该项目的工具或逐项核对源码，并记录对应的测量口径。

以下命令可在本 Skill 仓库根目录运行。

```sh
python3 -B skills/project-architect-skills/scripts/python_smell_signals.py \
  skills/project-architect-skills/scripts/necessary_docs.py
```

默认试点口径如下。按目标项目的有效规则可覆盖四个阈值，将本轮实际值写入记录。

| 信号 | 默认口径 |
| --- | --- |
| 长方法 | `--min-lines 40`。数函数体内存在代码记号起点的行，排除空行、注释、文档字符串和独立的嵌套函数或类定义。 |
| 深层嵌套 | `--min-depth 4`。沿 `if`、`for`、`async for`、`while` 和 `match` 计层，`elif` 与所在 `if` 同层。 |
| 多段嵌套逻辑 | 同一语句块内有至少两段依次排列、各自包含至少两层控制结构的区间。用源码确认两段是否在同一可达路径上、能否独立验收。 |
| 复杂条件表达式 | `--min-terms 4`。按单个 `if`、`while`、条件表达式或 `match` 守卫统计 `and`、`or` 的叶子条件。`not` 不增加项数，链式比较按一项。 |
| 复杂方法 | `--min-decisions 8`。统计 `if`、`elif`、循环、异常处理分支、条件表达式和 `match` 的有条件分支。记录为结构决策点数。 |

## 模块层面的关联诊断

沿同一业务路径核对以下证据，单独记录模块级发现。

- `architecture_drift`（架构漂移）引用项目认可的依赖或分层约定和实际违反约定的调用位置。只有目录惯例时，将预期边界标为待确认。
- `mixed_responsibilities`（职责混杂）指出同一文件的不同业务职责、各自的变化原因和能独立验收的拆分点。阶段明确、职责单一的大文件按其实际职责判断。
- `duplicate_logic`（逻辑重复）对照至少两处实现及各自调用者，核对同一业务规则和漏改影响。历史策略、兼容路径或条件分支有独立规则时，保留各自的实现和依据。

根据维护影响决定优先顺序，把同一改动可以处理的问题合并到治理计划。开始重构前，在现有入口建立行为基线并记录回退位置。验证结构发生预期变化，同时核对主要调用方、分支和用户可见输出。证据或验收条件不足时保留发现和原因。

## 交给汇总脚本的记录

用 `python3 -B <本 Skill 目录>/scripts/code_smells.py` 从标准输入读取 UTF-8 JSON，也可传入记录文件。脚本将确认的证据汇总为「代码异味」Markdown。单独运行可提供与必要文档检查相同格式的 `project`，合并报告时只需在首个章节记录规模。

- `scope` 为非空字符串数组，记录实际已读路径、方法和语言口径。`unread` 的每项含 `source` 和 `reason`，无则传 `[]`。
- `checks` 以五类标识为键。每项含 `status` 和 `detail`，结论与 `methods` 中已确认的类别一致。
- `methods` 每项含 `path`、`symbol`、正整数起止行 `start` 与 `end`、`impact`，以及非空 `findings`。每条发现含 `kind`、`detail` 和非空 `evidence` 出处数组。多段嵌套逻辑给出两个以上不同区间。同一 `path`、`symbol`、`start` 的各类发现放在同一项。可附一句 `suggestion`。无已确认发现时传 `[]`。
- `modules` 可省略。每项含模块诊断 `kind`、`title`、`status`、`detail` 和出处数组 `evidence`。`发现问题` 另含 `impact` 和至少两处不同依据，可附 `suggestion`。

### 最小示例

在本仓库根目录运行下列命令。样例记录同一函数的两类发现，报告保留两个标签并生成一项候选。

```sh
python3 -B skills/project-architect-skills/scripts/code_smells.py <<'JSON'
{
  "scope": ["核对订单导出入口和本地试点的 Python AST 信号"],
  "unread": [],
  "checks": {
    "long_method": {"status": "范围内未发现", "detail": "已读方法体均少于 40 代码行。"},
    "deep_nested_logic": {"status": "发现问题", "detail": "导出入口有 4 层控制结构。"},
    "bumpy_road": {"status": "范围内未发现", "detail": "已读入口只有一段连续深嵌套。"},
    "complex_conditional": {"status": "发现问题", "detail": "授权条件组合了 4 项业务判断。"},
    "complex_method": {"status": "范围内未发现", "detail": "已读方法结构决策点数少于 8。"}
  },
  "methods": [{
    "path": "src/orders/export.py", "symbol": "export_orders", "start": 8, "end": 22,
    "impact": "调整某类订单的导出条件时，需要同时还原筛选和授权规则。",
    "findings": [
      {"kind": "deep_nested_logic", "detail": "循环、状态判断、区域循环、授权分支共 4 层。", "evidence": ["src/orders/export.py:9–15"]},
      {"kind": "complex_conditional", "detail": "active and (owner or admin) and in_region。需核对停用的管理员是否一律拒绝。", "evidence": ["src/orders/export.py:15"]}
    ]
  }]
}
JSON
```
