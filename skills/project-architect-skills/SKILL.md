---
name: project-architect-skills
description: 检查本地项目的必要文档、架构图、目录结构和代码异味，生成治理计划并在已有授权内执行。适用于 project-architect-skills 命令和基于项目证据的检查与修订。
---

# 项目治理架构师

在目标项目的编码助手会话中输入 `project-architect-skills` 默认检查必要文档、架构图、目录结构和代码异味。用户指定某一项时，在选定范围内执行该项。以当前仓库和会话中已有的维护任务为准，遵守用户限定的目录和读写权限。

1. 在检查前，按[项目规模与取证范围](references/project-size.md)盘点当前仓库，判断规模，记录依据并确定本轮优先核对的入口和模块。
2. 按所选项读取对应判据：[必要文档](references/necessary-documents.md)、[架构图](references/architecture-diagrams.md)、[目录结构](references/directory-structure.md)或[代码异味](references/code-smells.md)。核实各项是否适用，记录维护者受阻的步骤、确切出处和未核实的资料。同一图件缺口保留在「架构图」，同一函数的各类异味合为一项。
3. 用 `python3 -B` 通过标准输入将证据交给各项的汇总脚本：[necessary_docs.py](scripts/necessary_docs.py)、[architecture_diagrams.py](scripts/architecture_diagrams.py)、[directory_structure.py](scripts/directory_structure.py) 和 [code_smells.py](scripts/code_smells.py)。合并选中项的 Markdown 章节，在首个章节记录项目规模。脚本路径相对于本 Skill，证据路径相对于目标仓库。环境无法运行 Python 时，按各项判据交付结论和建议。
4. 独立调用在体检后按[治理计划判据](references/governance-plan.md)汇总候选并排序，用 [governance_plan.py](scripts/governance_plan.py) 生成一份计划。默认命令或用户要求修订时使用 `execute`，改动前确定至多三项及各自的基线、验收和回退办法。仅检查、用户限定只读或仓库不可写时使用 `inspect`，交付诊断及未执行的建议。只读取证须保持目标仓库只读。Python 不可用时，按同一判据生成计划章节。
5. 按[执行复核](references/execution-and-handover.md#逐项执行与复核)在已有授权内逐项处理。每项重查现状、保留改前状态、核对实际差异并完成验收，再处理下一项。出现回归时记录失败样例，只撤回本项可安全分离的编辑并复核结果。没有执行事项时直接进入导读。
6. 按[维护导读与交付](references/execution-and-handover.md#导读与报告交付)重读当前入口及调用方，给出下次维护的自查步骤。用 [governance_report.py](scripts/governance_report.py) 汇总体检、计划、复核和导读。再次调用时从当前仓库重新判断规模并取证。

作为流水线的一项检查时，返回所选检查章节和已确认的候选，交给调用方合并。独立调用默认用 `--write` 将本轮报告写入目标仓库的 `docs/project-architect-report.md` 并给出路径。用户限定只读、仓库不可写或脚本返回报告正文时，将完整 Markdown 正文原样放入最终回复。环境无法运行 Python 时，按判据汇总报告并沿用同样的交付和覆盖条件。
