# 项目治理架构师

[![最新版本](https://img.shields.io/github/v/release/cabbage2000-lab/project-architect-skills)](https://github.com/cabbage2000-lab/project-architect-skills/releases/latest)
[![MIT 许可证](https://img.shields.io/badge/License-MIT-blue)](LICENSE)
[![支持 Codex、Claude Code 和 WorkBuddy](https://img.shields.io/badge/Tools-Codex%20%7C%20Claude%20Code%20%7C%20WorkBuddy-0f766e)](#快速开始)

[English](README.md) | **简体中文**

专门解决 AI 辅助开发（Vibe Coding）进入深水区后，项目容易失控、难以维护的痛点。

## 项目背景

随着 AI 编程能力的普及，人人皆可编码，项目往往从一个灵感（Idea）起步便迅速进入研发阶段。然而，随着项目的不断迭代与代码量的激增，当系统达到一定体量后，AI 的介入往往会显得力不从心。面对复杂的功能需求，AI 常常需要多轮追问才能理解上下文，且极易出现逻辑漂移或实现偏差。

究其根本，是因为当前的 AI 缺乏主动的架构治理意识——它不会主动进行代码重构、架构设计，也难以自发地清理代码坏味道或检查文档与引用的缺失。这些重复且耗时的工程化操作，往往是项目演进的瓶颈。当然，一旦我们下达明确的指令，AI 能够出色地完成这些任务。

这些专业的工程化与架构设计能力，通常是具备深厚计算机工程基础的专业人员所必备的，但对于非专业开发者而言，往往难以独立驾驭。这正是本项目的初衷：通过系统化的治理手段弥补这一鸿沟，引导 AI 主动执行这些关键操作，让 Vibe Coding 在项目规模化后依然能够顺畅、高效地运转。

## 项目原理

这个 Skill 把项目治理拆成取证、判断、修复和复核。AI 根据当前项目的源码、文档、配置和测试判断问题及其影响，Python 脚本负责校验检查记录并生成报告。[完整工作流程](skills/project-architect-skills/SKILL.md#治理流程)

1. **按项目情况确定范围。** 先盘点项目规模和主要入口，再按用户目标检查工程文档、软件架构、仓库结构、代码质量和关键行为。全面体检覆盖五项，专项问题只查相关模块或入口。
2. **用仓库里的证据确认问题。** 各项检查按对应的专家指引取证。例如，沿源码核对架构图中的调用关系，用项目配置判断测试目录是否放对。发现要能定位到文件、章节或代码符号，证据不足的结论标为「待确认」。
3. **按维护影响安排修复。** 将同一根因的多条发现合并，优先处理妨碍启动、定位入口或验证改动的问题。计划写清改动范围、改前状态、验收方法和回退办法。体检和计划预览保持只读，获得授权后按获批事项执行。
4. **沿原检查范围复核。** 逐项验收，并按原判据重新检查。报告保留改前依据、改后结果和维护导读，方便下一位接手者找到修改入口、相关调用方和验证方法。

### 为什么有效

项目越大，影响一次改动的约束就越可能分散在不同文件里。AI 只看当前打开的代码，容易漏掉调用方依赖的行为或项目的测试约定。这个 Skill 把「检查一下项目」拆成可以用仓库证据回答的问题，并在改动前写清验收时要看到的结果。这样，AI 能指出问题具体影响哪一步，维护者也能独立核对修复是否解决了原问题。

例如，项目的测试命令只扫描 `tests/`，放在仓库根目录的测试文件就会被漏掉。对照测试命令和文件路径可以定位这个缺口。把文件移到约定目录后，再用同一条命令确认该用例已被执行。

再比如，订单模块重构后，README 的源码链接仍指向已删除的目录，架构图也保留了旧的调用关系。AI 可能沿失效路径反复搜索，把无关的搜索结果带进上下文，也可能依照旧图漏查真正受影响的调用方。按当前源码修正链接和图件，能让后续会话从实际入口开始，减少重复查找和过时信息对判断的干扰。

## 快速开始

**1. 让 AI 安装。** 用 Codex、Claude Code 或 WorkBuddy 打开你想检查的项目，把下面这句话发给 AI。

> 请帮我把「项目治理架构师」安装到当前项目，装好后告诉我。项目地址是 https://github.com/cabbage2000-lab/project-architect-skills

**2. 运行项目体检（最常用）。** 安装好后，在目标项目里新开对话。在 Claude Code 中输入下面这条命令。

```text
/project-architect-skills 项目体检
```

在 Codex 或 WorkBuddy 中，也可以直接输入「项目评估」。

体检先只读检查工程文档、软件架构、仓库结构、代码质量和关键行为。行为验证默认沿一条代表性入口核对最小运行、业务预期和测试断言，分别标明已实跑或仅静态核对。报告指出每个问题的出处、影响哪项维护操作，以及哪些问题值得优先修复。看过计划后，回复 **同意治理** 即可开始修复，也可以只选其中几项。

<details>
<summary>供 AI 安装时查看</summary>

将来源项目中的 `skills/project-architect-skills/` 整个复制到目标项目的技能目录。本仓库通过相对符号链接提供各工具的入口，Git 检出时保留符号链接即可直接试用。

| 工具 | 目标项目中的技能目录 | 新会话中显式调用 |
| --- | --- | --- |
| Codex | `.agents/skills/` | `project-architect-skills` |
| Claude Code | `.claude/skills/` | `/project-architect-skills` |
| WorkBuddy 桌面端 | `.workbuddy/skills/`（macOS 5.11.3 实测） | `用 project-architect-skills 评估当前项目` |

WorkBuddy 使用 `.codebuddy/` 项目级代码开发配置时，复制到 `.codebuddy/skills/`。安装后，从所选目录打开 `project-architect-skills/SKILL.md`，确认旁边有 `agents/`、`references/` 和 `scripts/`。[Claude Code 技能说明](https://code.claude.com/docs/en/skills) · [WorkBuddy 项目配置](https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Project#项目级代码开发配置)

</details>

## 使用示例

按手头的任务选一条提示词。在 Codex 或 WorkBuddy 中，把开头的 `/project-architect-skills` 换成「用 project-architect-skills」。

| 使用场景 | Claude Code 提示词 |
| --- | --- |
| 全面体检 | `/project-architect-skills 全面体检` |
| 行为验证 | `/project-architect-skills 只做行为验证，检查空订单导出的结果，以及现有测试能否发现表头丢失` |
| 提交前检查 | `/project-architect-skills 本次改动体检，看看这次改动漏了哪些调用方、文档或测试` |
| 检查提交范围 | `/project-architect-skills 本次改动体检，检查 main...feature` |
| 文档体检 | `/project-architect-skills 文档体检` |
| 本项目缺失文档检查 | `/project-architect-skills 本项目缺哪些必要文档，列出建议补写项和依据` |
| 补文档 | `/project-architect-skills 补一份本地启动指南，写清启动和验证步骤` |
| 架构图体检 | `/project-architect-skills 架构图体检` |
| 本项目缺失架构图检查 | `/project-architect-skills 本项目缺哪些必要架构图，列出建议补画的图和依据` |
| 补架构图 | `/project-architect-skills 根据源码补一张架构图，画清主要模块及调用关系` |
| 项目结构检查 | `/project-architect-skills 项目结构体检` |
| 代码重构检查 | `/project-architect-skills 找出值得重构的代码，给出理由和验证方法` |

本次改动体检默认只读检查已暂存、未暂存和未被 Git 忽略的新文件。报告列出行为变化、受影响的位置和提交前还需执行的验证。指定 `A..B` 比较两个提交的内容，`A...B` 检查从共同祖先到 B 的改动。[本次改动体检](skills/project-architect-skills/references/change-check.md)

## 怎样读体检报告

先看**哪些问题会影响你手头的事**。比如，README 里的启动命令指向一个已删除的文件，报告会标出是哪一条命令、它会让新人卡在哪一步。

「待确认」表示证据还不足以判断。例如，测试手册无法访问时，报告会标明哪些验证步骤仍需核实。若已确认保密文档或图件因 Git 忽略规则未随仓库交付，其交付检查记为「不适用」。公开资料里已核实的失效步骤仍会列出。

报告会显示在对话里。想留一份，可以说「请保存这次报告」。同意修复后，报告默认保存在项目的 `docs/project-architect-report.md`。[查看一份报告示例](docs/project-architect-report.md)

## 验证模块

如果你修改了这个 Skill，可以在本仓库根目录运行全部测试。完整测试需要 Python 3.10+ 和可从 `PATH` 调用的 Git，只用 Python 标准库。

```sh
python3 -B -m unittest discover -s tests -v
```

最后一行显示 `OK` 表示全部用例通过。`OK (skipped=N)` 表示有 N 项跳过，原因在对应的用例旁。例如 Python 3.9 会跳过模式匹配测试，找不到 Git 会跳过 Git 历史测试。

<details>
<summary>在任一支持的工具中验证只读检查</summary>

修改 `SKILL.md` 或检查判据后，可用一份有运行说明的临时项目检查取证和报告交付。先在终端创建样例。

```sh
smoke_project=$(mktemp -d)
cat > "$smoke_project/README.md" <<'EOF'
# 姓名整理

把一组姓名整理成列表。在项目根目录用 Python 3 运行 `python3 names.py`。
EOF
cat > "$smoke_project/names.py" <<'EOF'
names = ["Bob", "Ada", "Bob"]
print(", ".join(sorted(set(names))))
EOF
printf '%s\n' "$smoke_project"
```

在以本仓库为工作目录的会话中输入「用 project-architect-skills 只读检查 `<临时目录路径>` 的必要文档」，将占位符换成终端输出的路径。会话应给出报告。复核以下三点。

- 「启动或最小使用示例」显示「范围内未发现」，依据指向临时项目的运行说明。
- 「验证改动的方法」显示「发现问题」，缺口类型为「缺少说明」。补写建议指向临时项目的 `README.md`，可记录运行后的预期输出 `Ada, Bob`。
- 终端执行 `ls -A "$smoke_project"`，目录清单应只有 `README.md` 和 `names.py`。

</details>

<details>
<summary>在临时仓库验证默认治理（以 Codex 为例）</summary>

在本仓库根目录运行以下命令。这个样例的 README 缺少验收说明，单元测试也放错了目录，两项修复可以分别验收。

```sh
governance_project=$(mktemp -d)
mkdir -p "$governance_project/.agents/skills"
cp -R skills/project-architect-skills "$governance_project/.agents/skills/"
cat > "$governance_project/AGENTS.md" <<'EOF'
# 样例仓库约定

本项目只维护 `names.py` 及其测试。`names.py` 是仓库根目录的命令行入口，单元测试固定放在 `tests/`。`.agents/skills/` 存放已安装的工具。
EOF
cat > "$governance_project/README.md" <<'EOF'
# 姓名整理

对内置姓名去重并按字母顺序排列。在仓库根目录运行 `python3 -B names.py`。
EOF
cat > "$governance_project/names.py" <<'EOF'
names = ["Bob", "Ada", "Bob"]
print(", ".join(sorted(set(names))))
EOF
cat > "$governance_project/test_names.py" <<'EOF'
import subprocess
import sys
import unittest


class NamesTests(unittest.TestCase):
    def test_names(self):
        output = subprocess.check_output([sys.executable, "-B", "names.py"], text=True)
        self.assertEqual(output.strip(), "Ada, Bob")
EOF
git -C "$governance_project" init -q
git -C "$governance_project" add .
git -C "$governance_project" -c user.name=Fixture -c user.email=fixture@example.invalid \
  commit -qm '保存样例基线'
(cd "$governance_project" && python3 -B names.py && python3 -B -m unittest discover -s . -p test_names.py)
printf '%s\n' "$governance_project"
```

在可写的 Codex 会话中打开输出的临时目录，输入 `project-architect-skills`。在支持子 Agent 的宿主中，核对五项体检是否各自加载了对应的专家定义，并有独立的派发与回传记录，计划在汇总后统一展示。核对体检摘要和待授权计划，列出的两项分别指向 `README.md` 和 `test_names.py`。在临时仓库根目录运行 `git status --short`，应无输出。随后在同一会话回复 **同意治理**，完成后核对以下结果。

- `README.md` 增加验收步骤及预期输出。`test_names.py` 移到 `tests/`。
- 在临时仓库根目录运行 `python3 -B names.py`，仍输出 `Ada, Bob`。运行 `python3 -B -m unittest discover -s tests`，1 项通过。
- `docs/project-architect-report.md` 包含五项体检、两项已通过的执行复核和维护导读。两项改动都有各自的改前基线和验收证据。

另建一份相同的临时仓库，收到授权提示后回复「不同意治理」。会话应交付检查结果和未执行的建议，`git status --short` 仍无输出。

</details>

## 开源协议

本项目采用 [MIT 许可证](LICENSE)。
