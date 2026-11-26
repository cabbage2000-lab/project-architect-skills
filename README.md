# project-architect-skills（项目治理架构师）

这个 Codex Skill 帮助接手项目的人检查必要文档、架构图、目录结构和代码异味。各项是否适用取决于项目用途、交付方式和本轮维护任务。

## 项目背景

有了 AI，越来越多人能把自己的想法做成软件。项目迭代几轮后，哪怕只想改一个小功能，也常常要先把项目背景重新讲一遍。这段逻辑还有哪些地方在用？当初为什么这样设计？当答案散落在代码、文档和过去的对话里，开发者就得反复补充说明，AI 也容易漏掉已有约束，让改动偏离预期。

这个项目把工程师接手和维护软件时常用的方法整理成一套 AI 可以执行的检查。它会对照文档、架构图和源码，帮你发现哪些说明已经过时、哪些模块彼此依赖。这样，即使是第一次维护一个持续迭代的项目，你也能和 AI 一起判断该从哪里改、会影响什么、怎样验证结果，让 Vibe Coding 在项目变大后依然顺畅。

## 使用

本仓库已配置项目级 Skill 入口。在其他项目使用时，将 `skills/project-architect-skills` 整个目录复制到目标项目的 `.agents/skills/`，然后在该项目的 Codex 会话中输入

```text
project-architect-skills
```

单独输入命令会检查全部四项。有具体维护任务时，可以直接用自己的话提问。

## 使用场景与提问示例

第一次用，可以直接问：

> 项目评估

| 使用场景 | 可以这样问 | 你会拿到什么 |
| --- | --- | --- |
| 刚接手一个项目 | 我下周要接手这个仓库。先做一次全面体检，哪些问题最值得先修？ | 文档、架构、目录和代码四项的检查结果与评分，以及按维护影响排序的修复计划。 |
| 改功能前找入口 | 我要给订单 CSV 加一列「退款金额」。从哪个函数改起？哪些页面会用到这个导出？改完怎么验？ | 入口函数、实际调用方的源码位置，以及可重放的验证步骤。[维护导读](skills/project-architect-skills/references/execution-and-handover.md#独立维护导读) |
| 把项目交给新人 | 新同事只看 README 能跑通订单测试吗？README 和操作手册都写了测试步骤，以后该维护哪一份？ | 缺失或过期的步骤、重复说明所在的章节，以及建议保留的正文和链接位置。[文档冗余判据](skills/project-architect-skills/references/necessary-documents.md#文档冗余) |
| 团队混用 AI 编程工具 | 我们在仓库根目录用 Claude Code 和 Codex。它们各自会读到哪份项目指引？缺了该补在哪里？ | 按工具列出使用依据，以及实际生效的指引（如 `CLAUDE.md`、`AGENTS.md`）或应补建的路径。[项目指引判据](skills/project-architect-skills/references/necessary-documents.md#ai-编程工具项目指引) |
| 核对架构图和分层约定 | README 画的是订单服务调用退款服务，代码里也是这个方向吗？这条调用符合仓库的分层约定吗？ | 图中箭头对应的实际调用位置，以及按项目约定核实的结论。找不到约定时，分层判断列为「待确认」。[专项检查记录](skills/project-architect-skills/references/governance-plan.md#检查范围记录) |
| 决定测试文件放哪里 | 订单导出的测试现在放在仓库根目录。按项目约定该放在哪？移动后，现有测试命令还能找到它吗？ | 目录约定、测试发现配置和建议路径，以及验证测试仍会执行的命令。 |
| 准备重构复杂方法 | 订单导出循环里好几层判断，哪些分支可以简化？先给我看计划，尤其是怎么验证跳过的订单仍然会被跳过。 | 具体分支、建议拆分的步骤，以及用于对照改前改后行为的输入和预期结果。 |

在本仓库的 Codex 会话中，可以直接复制这句提问。

```text
我想调整体检报告里的扣分规则。请只读追踪 skills/project-architect-skills/scripts/health_score.py，指出从哪里改、计划预览和最终报告在哪里用到它，以及该跑哪些测试。
```

## 检查分工与治理流程

主 Agent 根据问题选择对应的专家。每位专家在独立的只读上下文中取证，交回检查章节、治理候选及出处。

| 专家定义 | 负责的检查 |
| --- | --- |
| [工程文档专家](skills/project-architect-skills/agents/engineering-documentation-expert.md) | 交接说明是否够用，同一文档或多份手册是否重复维护相同内容 |
| [软件架构专家](skills/project-architect-skills/agents/software-architecture-expert.md) | 架构图是否符合实现，实际调用是否遵守项目认可的分层约定 |
| [仓库结构专家](skills/project-architect-skills/agents/repository-structure-expert.md) | 文件路径是否符合项目约定和生效配置 |
| [代码质量专家](skills/project-architect-skills/agents/code-quality-expert.md) | 哪些方法或分支难以维护，怎样重构并验证原有行为 |

主 Agent 合并重复发现，按维护影响推荐本轮修复事项。计划列出改动范围、基线、验收方法和回退办法。在同一会话选择或回复 **同意治理** 后，助手按计划逐项修复和验收。有多项时也可以逐项选择。[治理计划](skills/project-architect-skills/references/governance-plan.md)

制定计划或执行中遇到需要你决定的业务规则、兼容要求或验收目标时，助手会用 Ask User Question 给出选择题。每题的首项标为「推荐」，说明推荐理由和各选项的影响。工具不可用时，可在会话中回复选项字母或名称。等待答复期间，只暂停依赖该决定的改动。[治理选择题及表头兼容示例](skills/project-architect-skills/references/governance-plan.md#治理选择题)

**体检评分**随计划预览或只读报告一起交付。也可以输入「给项目打分」或「只给订单的测试说明打分」。全面体检展示四项各 25 分的明细及总分，专项只展示所查范围的维度分。每笔扣分可追到具体操作和出处，证据不足的维度标为「待补查」。[评分规则与可运行的专项示例](skills/project-architect-skills/references/health-score.md)

例如，一个姓名工具经核实无需架构图，README 里的验收命令失效，但直接使用测试入口可以跑通。预览列出工程文档 20/25、仓库结构 25/25、代码质量 25/25，实得 **70/75，折算 93.3/100**。回复「同意治理」后，助手补正命令，从手册跑通测试并复查原范围，最终报告在同一根因下给出新出处，显示 **93.3 → 100，提升 6.7 分**。在本仓库运行 `python3 -B -m unittest discover -s tests -p test_health_score.py -v` 可重放该场景。

默认体检包含文档冗余和 AI 编程工具项目指引检查。专项检查可以限定专家、主题和模块，例如「请仓库结构专家只读检查 tests/ 的归属」。同时问到测试说明和文件归属时，工程文档专家和仓库结构专家分别核对。单问改动入口时直接交付维护导读，同时要求检查或重构时，导读随治理报告一起交付。

检查前先判断项目规模。小项目通查相关资料，中等项目分模块核对，大项目优先检查主要业务路径和跨模块依赖。预览和最终报告按检查项列出选定的模块或入口，漏交的范围标为「未查」。判档和取证方式见[项目规模与取证范围](skills/project-architect-skills/references/project-size.md)。

有足够的本地 Git 历史时，变更热点为影响相近的治理候选提供排序依据，共变记录帮助定位需要核实的调用方和测试。修改 Python 代码时，复核会用实际改前快照对照改后的结构信号，并记录行为验收结果。 [Git 变更证据](skills/project-architect-skills/references/git-change-history.md) · [Python 增量对照](skills/project-architect-skills/references/execution-and-handover.md#python-结构信号增量对照)

报告列出规模依据、已查范围、逐项结论、治理计划和复核结果。拟执行项会核对本地引用的位置，唯一出处越界时标为「待确认」。建议合并、删除或替换既有行为时，先用相关调用方、契约或测试查找反例。维护导读给出下次改动的入口、受影响的调用方和自查方法。治理获批后，报告默认保存到目标项目的 `docs/project-architect-report.md`。只做检查、没有可执行项或拒绝治理时，默认在会话交付全文。用户也可以单独要求保存本次报告。写入受限或已有同名人工报告时，助手在会话交付全文。[执行复核与维护导读](skills/project-architect-skills/references/execution-and-handover.md)

需要重构时，可以输入「用 project-architect-skills 检查订单导出循环的嵌套，给出简化计划」。助手会选取能检验改动的输入，例如混合可导出和应跳过的订单，记录原入口的结果。获批后逐步重构并重放样例；涉及跨文件改名时，先核对定义、调用点和配置引用。这套做法吸收自 Claude Code 的重构专家说明。[上游 refactoring-expert](https://github.com/luanquangminh/claude-skill/blob/85ebeee29a6b32085d56e8b7022d5673b1760fe6/agents/refactoring-expert.md) · [本项目执行判据](skills/project-architect-skills/references/execution-and-handover.md#局部与跨文件重构)

也可以指定重构任务，例如「只读评估运费模块是否适合策略模式」或「把导出模块迁移到新版 SDK，先预览所有受影响的调用」。Skill 会对照现有契约和调用方选择手法，获批后执行并在报告中交付结构与行为验证。[SOLID 取证](skills/project-architect-skills/references/code-smells.md#solid-原则与设计模式) · [支持的重构与迁移](skills/project-architect-skills/references/refactoring.md)

## 验证模块

在本仓库根目录运行以下命令。完整运行测试需要 Python 3.10 或更高版本，并且能从 `PATH` 调用 `git`。无需安装第三方 Python 包。

```sh
python3 -B -m unittest discover -s tests -v
```

全部用例执行并通过时，最后一行显示 `OK`。`OK (skipped=N)` 表示已执行的用例通过，另有 N 项被跳过。Python 3.9 会跳过模式匹配测试；找不到 `git` 时会跳过 Git 历史测试。可在 `-v` 输出中查看具体用例和跳过原因。

检查记录和可运行的示例见[必要文档](skills/project-architect-skills/references/necessary-documents.md)、[架构图](skills/project-architect-skills/references/architecture-diagrams.md)、[目录结构](skills/project-architect-skills/references/directory-structure.md)和[代码异味](skills/project-architect-skills/references/code-smells.md)检查判据。

### 在 Codex 会话中验证只读检查

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

在本仓库的 Codex 会话中输入「用 project-architect-skills 只读检查 `<临时目录路径>` 的必要文档」，将占位符换成终端输出的路径。会话应给出报告。复核以下三点。

- 「启动或最小使用示例」显示「范围内未发现」，依据指向临时项目的运行说明。
- 「验证改动的方法」显示「发现问题」，缺口类型为「缺少说明」。补写建议指向临时项目的 `README.md`，可记录运行后的预期输出 `Ada, Bob`。
- 终端执行 `ls -A "$smoke_project"`，目录清单应只有 `README.md` 和 `names.py`。

### 在临时仓库验证默认治理

在本仓库根目录运行以下命令。样例有两个可独立验收的问题：README 缺少验收说明，单元测试放在了仓库根目录。

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
