# Repository Guidelines（仓库贡献指南）

## 产物精简原则

本 Skill 充分发挥模型的理解、判断和归纳能力，根据项目实际情况和任务目标决定产物的内容与详略。文档、报告、图表和示例只保留理解结论、执行操作和复核结果所需的信息。不得为了填满模板、凑篇幅或形式上完成任务而添加套话、重复内容或无实际用途的段落。

## 项目结构

本项目提供一个可在 Codex、Claude Code 和 WorkBuddy 中使用的 Skill，用于核对交接文档、架构图、目录结构、代码异味和关键行为。修改 Skill 时，请编辑 `skills/project-architect-skills/` 下的源文件。各工具的项目级入口都通过相对符号链接指向该目录，位置与调用方式见 [README 快速开始](README.zh-CN.md#快速开始)。

- `SKILL.md` 定义检查流程，按检查项路由到 `agents/` 下的五份专家定义。专家定义说明职责、取证方法和回传内容。
- `references/necessary-documents.md` 定义文档类别、各类检查项、状态标签和 JSON 检查记录的格式。
- `scripts/necessary_docs.py` 校验检查记录，并生成 Markdown 报告。
- `references/architecture-diagrams.md` 定义图件取证、源码对照和修订流程。`scripts/architecture_diagrams.py` 校验对照记录并汇总架构图章节。
- `references/directory-structure.md` 定义路径归属判据。`scripts/directory_structure.py` 汇总实际路径、适用约定和调整建议。
- `references/code-smells.md` 定义异味和模块诊断判据。`scripts/python_smell_signals.py` 提取 Python 结构信号，`scripts/code_smells.py` 汇总证据和治理候选。
- `references/behavior-verification.md` 定义运行、业务规则和回归断言的取证方法。`scripts/behavior_verification.py` 校验单入口记录并生成行为验证章节。
- `references/git-change-history.md` 说明怎样用 `scripts/git_change_history.py` 提取本地热点和共变线索。
- `references/change-check.md` 定义本次改动体检的取证与交付方式。`scripts/change_check.py` 列出未提交改动或指定 Git 提交范围。
- `references/governance-plan.md` 定义候选排序与纳入条件。`scripts/governance_plan.py` 校验并汇总本轮计划。
- `references/execution-and-handover.md` 定义复核、回退与导读。`scripts/governance_report.py` 汇总各阶段并交付报告。

测试位于仓库根目录的 `tests/`，各版本的产品需求文档（PRD）位于 `docs/`。更新架构图时，先编辑 `docs/diagrams/` 中的 `.drawio` 源文件，再导出 PRD 引用的同名 PNG。

## 本地开发命令

在仓库根目录执行以下命令。完整运行测试需要 Python 3.10+ 和可从 `PATH` 调用的 `git`，无需第三方 Python 包。

- `python3 -B -m unittest discover -s tests -v` 运行测试并显示每个用例的结果。全量通过时显示 `OK`。若显示 `OK (skipped=N)`，请核对 N 项跳过原因，见 [README 的验证说明](README.zh-CN.md#验证模块)。
- `python3 -B skills/project-architect-skills/scripts/necessary_docs.py record.json` 读取检查记录并将报告写到标准输出。将 `record.json` 替换为实际文件路径，省略路径则从标准输入读取。可先运行[最小示例](skills/project-architect-skills/references/necessary-documents.md#最小可运行示例)。

在项目会话中输入 `用 project-architect-skills 只读检查代码异味` 可查看单项诊断。单独调用此 Skill 时，助手会检查五项并展示拟修复事项。回复「同意治理」后，助手按获批范围执行和复核。

## 编码风格与命名

Python 代码使用四个空格缩进。函数和模块使用 `snake_case`，常量使用 `UPPER_SNAKE_CASE`。仓库未配置格式化工具或静态检查工具，请沿用相邻代码的排版。修改「待确认」等报告标签时，同步更新检查判据、报告脚本和相关测试。

## 测试指南

使用 `unittest`，测试文件按 `tests/test_*.py` 命名，测试方法按 `test_<行为>` 命名。通过子进程调用命令行入口。输入有效时核对报告内容，输入无效时检查退出码、标准错误和标准输出，确认脚本没有输出残缺的报告。

修改未读资料的处理逻辑时，用一份无法访问的测试手册验证结果。若它是验证方法的唯一出处，该项应标为「待确认」，其他有独立证据的结论应予保留。

## 提交与合并请求

建议用简短的动宾短语作为提交标题，例如 `修正测试手册不可访问时的验证状态`。

合并请求应写明改动针对哪个交接场景，并附上实际运行的测试命令和结果。有相关议题时附上链接。若改动影响报告内容，摘录修改前后的片段，方便审阅者核对。
