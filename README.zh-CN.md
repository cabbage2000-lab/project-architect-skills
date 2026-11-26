# 项目治理架构师

[English](README.md) | **简体中文**

让 Vibe Coding 在项目变大后依然顺畅。准备改功能时，它帮你找出该从哪里改、哪些地方也会受影响，以及改完怎么验证。

## 项目背景

随着 AI 编程能力的普及，人人皆可编码，项目往往从一个灵感（Idea）起步便迅速进入研发阶段。然而，随着项目的不断迭代与代码量的激增，当系统达到一定体量后，AI 的介入往往会显得力不从心。面对复杂的功能需求，AI 常常需要多轮追问才能理解上下文，且极易出现逻辑漂移或实现偏差。

究其根本，是因为当前的 AI 缺乏主动的架构治理意识——它不会主动进行代码重构、架构设计，也难以自发地清理代码坏味道或检查文档与引用的缺失。这些重复且耗时的工程化操作，往往是项目演进的瓶颈。当然，一旦我们下达明确的指令，AI 能够出色地完成这些任务。

这些专业的工程化与架构设计能力，通常是具备深厚计算机工程基础的专业人员所必备的，但对于非专业开发者而言，往往难以独立驾驭。这正是本项目的初衷：通过系统化的治理手段弥补这一鸿沟，引导 AI 主动执行这些关键操作，让 Vibe Coding 在项目规模化后依然能够顺畅、高效地运转。

## 快速开始

**1. 让 AI 安装。** 用 Codex、Claude Code 或 WorkBuddy 打开你想检查的项目，把下面这句话发给 AI。

> 请帮我把「项目治理架构师」安装到当前项目，装好后告诉我。项目地址是 https://github.com/cabbage2000-lab/project-architect-skills

**2. 运行项目体检（最常用）。** 安装好后，在目标项目里新开对话。在 Claude Code 中输入下面这条命令。

```text
/project-architect-skills 项目体检
```

在 Codex 或 WorkBuddy 中，也可以直接输入「项目评估」。

体检会先只读检查工程文档、软件架构、仓库结构和代码质量，给出评分、问题依据和建议优先修复的事项。看过计划后，回复 **同意治理** 即可开始修复，也可以只选其中几项。

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

在 Claude Code 中任选一行即可开始评估。在 Codex 或 WorkBuddy 中，把开头的 `/project-architect-skills` 换成「用 project-architect-skills」即可。

| 专家 | 可以直接输入 |
| --- | --- |
| 四位专家一起评估 | `/project-architect-skills 项目体检` |
| 工程文档专家 | `/project-architect-skills 检查交接文档缺了什么、哪些说明重复` |
| 软件架构专家 | `/project-architect-skills 核对架构图和代码里的实际调用是否一致` |
| 仓库结构专家 | `/project-architect-skills 按项目约定检查源码和测试有没有放错目录` |
| 代码质量专家 | `/project-architect-skills 找出最值得重构的函数，给出验证用例` |

## 怎样读体检报告

先看**哪些问题会影响你手头的事**。比如，README 里的启动命令指向一个已删除的文件，报告会标出是哪一条命令、它会让新人卡在哪一步。

再看分数。全面体检分为工程文档、软件架构、仓库结构和代码质量四项，每项满分 25 分，按适用项折算为百分制。只问一个问题时，只给相关部分打分。「待补查」表示现有资料还不足以判断。[评分规则](skills/project-architect-skills/references/health-score.md)

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

在可写的 Codex 会话中打开输出的临时目录，输入 `project-architect-skills`。在支持子 Agent 的宿主中，核对四项体检是否各自加载了对应的专家定义，并有独立的派发与回传记录，计划在汇总后统一展示。核对体检摘要和待授权计划，列出的两项分别指向 `README.md` 和 `test_names.py`。在临时仓库根目录运行 `git status --short`，应无输出。随后在同一会话回复 **同意治理**，完成后核对以下结果。

- `README.md` 增加验收步骤及预期输出。`test_names.py` 移到 `tests/`。
- 在临时仓库根目录运行 `python3 -B names.py`，仍输出 `Ada, Bob`。运行 `python3 -B -m unittest discover -s tests`，1 项通过。
- `docs/project-architect-report.md` 包含四项体检、两项已通过的执行复核和维护导读。两项改动都有各自的改前基线和验收证据。

另建一份相同的临时仓库，收到授权提示后回复「不同意治理」。会话应交付检查结果和未执行的建议，`git status --short` 仍无输出。

</details>

## 开源协议

本项目采用 [MIT 许可证](LICENSE)。
