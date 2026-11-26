# project-architect-skills（项目治理架构师）

这个 Codex Skill 帮助接手项目的人检查必要文档、架构图、目录结构和代码异味。各项是否适用取决于项目用途、交付方式和本轮维护任务。

## 使用

本仓库已配置项目级 Skill 入口。在其他项目使用时，将 `skills/project-architect-skills` 整个目录复制到目标项目的 `.agents/skills/`，然后在该项目的 Codex 会话中输入

```text
project-architect-skills
```

单独输入命令会检查全部四项。也可以直接描述维护问题，主 Agent 会判断要核实什么，只将相关问题派给下表中对应的专家。每位专家在独立的只读上下文中取证，交回检查章节、治理候选及出处。

| 专家定义 | 负责的检查 |
| --- | --- |
| [项目文档专家](skills/project-architect-skills/agents/project-documentation-expert.md) | 必要文档能否支持接手者运行、验证和维护项目 |
| [架构专家](skills/project-architect-skills/agents/architecture-expert.md) | 架构图是否符合实现，实际调用是否遵守项目认可的分层约定 |
| [目录专家](skills/project-architect-skills/agents/directory-expert.md) | 文件路径是否符合项目约定和生效配置 |
| [代码整洁专家](skills/project-architect-skills/agents/clean-code-expert.md) | 长方法、深层嵌套、多段嵌套逻辑、复杂条件表达式和复杂方法 |

主 Agent 合并重复发现，按维护影响推荐本轮修复事项。计划列出改动范围、基线、验收方法和回退办法。在同一会话回复 **同意治理** 后，助手按计划逐项修复和验收。[治理计划](skills/project-architect-skills/references/governance-plan.md)

例如，输入「README 里的订单调用图和代码对得上吗？」会交给架构专家。输入「新人能照说明跑通测试吗？订单测试放的位置也帮我看一下」会分别交给项目文档专家和目录专家。也可以直接限定范围，例如「用 project-architect-skills 请目录专家只读检查 tests/ 的归属」。

输入「只核对订单和退款有没有违反分层约定」，会分别登记两个模块的架构漂移检查。报告对每项给出结论，缺少约定时列为「待确认」，某个模块未回传时列为「未查」。只问测试说明或某一种代码异味时，也可按点名的主题交付。[专项检查记录](skills/project-architect-skills/references/governance-plan.md#检查范围记录)

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
