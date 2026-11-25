---
name: project-architect-skills
description: 检查本地项目的必要文档、架构图、目录结构和代码异味，展示治理计划并在用户确认后修复。适用于 project-architect-skills 命令、基于项目证据的检查与修订，局部或批量重构、SOLID 诊断与设计模式应用，以及回复「同意治理」继续本轮计划。
---

# 项目治理架构师

在目标项目的编码助手会话中输入 `project-architect-skills` 默认检查必要文档、架构图、目录结构和代码异味。用户指定某一项时，在选定范围内执行该项。以当前仓库和会话中已有的维护任务为准，遵守用户限定的目录和读写权限。

用户指定重构目标时，以该目标进入代码治理流程。SOLID 评估与设计模式选型按[设计判据](references/code-smells.md#solid-原则与设计模式)取证；局部清理、跨文件重命名、常量提取和旧 API 迁移按[专项重构](references/refactoring.md)选择变换及验收方式。

1. 在检查前，按[项目规模与取证范围](references/project-size.md)盘点当前仓库，判断规模，记录依据并确定本轮优先核对的入口和模块。
2. 按所选项读取对应判据：[必要文档](references/necessary-documents.md)、[架构图](references/architecture-diagrams.md)、[目录结构](references/directory-structure.md)或[代码异味](references/code-smells.md)。核实各项是否适用，记录维护者受阻的步骤、确切出处和未核实的资料。同一图件缺口保留在「架构图」，同一函数的各类异味合为一项。
3. 用 `python3 -B` 通过标准输入将证据交给各项的汇总脚本：[necessary_docs.py](scripts/necessary_docs.py)、[architecture_diagrams.py](scripts/architecture_diagrams.py)、[directory_structure.py](scripts/directory_structure.py) 和 [code_smells.py](scripts/code_smells.py)。合并选中项的 Markdown 章节，在首个章节记录项目规模。脚本路径相对于本 Skill，证据路径相对于目标仓库。环境无法运行 Python 时，按各项判据交付结论和建议。
4. 在体检后按[治理计划判据](references/governance-plan.md)汇总候选并排序。对相关源码和测试按 [Git 变更证据](references/git-change-history.md)只读取证，供候选排序和导读核对使用。用 [governance_plan.py](scripts/governance_plan.py) 生成计划。默认命令用 `execute` 拟定至多三项及各自的改动范围、基线、验收和回退办法。仅检查、用户限定只读或仓库不可写时用 `inspect`。体检、基线取证和计划预览保持目标仓库只读。Python 不可用时按同一判据生成计划。
5. 计划有可执行事项且尚未获得对应授权时，在当前会话交付体检摘要和治理计划预览，列出目标仓库、拟改位置及验收方式，提示「请回复『同意治理』，我会按以上计划逐项修复和验收。」用计划脚本的 `--preview` 生成带提示的章节。保留本轮体检、计划及范围作为会话上下文，结束本轮回复并等待确认。等待期间保持目标仓库只读。用户已明确授权计划中的具体修复时，沿用该授权。只读检查或无可执行事项时，直接进入导读。
6. 用户在同一会话回复「同意治理」或明确批准后，沿用本轮计划继续。只处理获批的事项，按[执行复核](references/execution-and-handover.md#逐项执行与复核)重查现状、保留改前状态、逐项修复并验收。已解决的事项直接跳过，拟变更超出获批范围时先展示新范围并等待确认。部分批准时，其余已列事项记为「暂缓」，不递补。用户拒绝时按 `inspect` 交付，注明拟修复事项未获批准。收到「同意治理」时若没有可核对的待授权计划，先重新取证并展示计划。
7. 按[维护导读与交付](references/execution-and-handover.md#导读与报告交付)重读当前入口及调用方，给出下次维护的自查步骤。用 [governance_report.py](scripts/governance_report.py) 汇总体检、计划、复核和导读。再次启动治理时从当前仓库重新判断规模并取证。

作为流水线的一项检查时，返回所选检查章节和已确认的候选，交给调用方合并。治理获批或用户明确要求保存报告且仓库可写时，用 `--write` 交付到 `docs/project-architect-report.md`。其余情况以及脚本返回报告正文时，将完整 Markdown 正文原样放入最终回复。环境无法运行 Python 时，按判据汇总报告并沿用同样的交付和覆盖条件。
