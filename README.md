# project-architect-skills（项目治理架构师）

这个 Codex Skill 帮助接手项目的人检查必要文档、架构图、目录结构和代码异味。各项是否适用取决于项目用途、交付方式和本轮维护任务。

## 使用

本仓库已配置项目级 Skill 入口。在其他项目使用时，将 `skills/project-architect-skills` 整个目录复制到目标项目的 `.agents/skills/`，然后在该项目的 Codex 会话中输入

```text
project-architect-skills
```

默认调用先只读完成四项体检，随后展示体检摘要和至多三项拟修复事项。计划给出改动范围、改前基线、验收方法和回退办法。确认后，在同一会话回复 **同意治理**，助手会按计划逐项修复和验收。已有维护任务可以直接附上，例如「我要改订单导出的列名」。只想查看某项诊断时，可以输入「用 project-architect-skills 只读检查代码异味」或指定其他检查项。[治理计划](skills/project-architect-skills/references/governance-plan.md)

检查前先判断项目规模。小项目通查相关资料，中等项目分模块核对，大项目优先检查主要业务路径和跨模块依赖。判档和取证方式见[项目规模与取证范围](skills/project-architect-skills/references/project-size.md)。

报告列出规模依据、已查范围、逐项结论、治理计划和复核结果。待确认、待验证或暂缓的事项保留证据和原因。维护导读给出下次改动的入口、受影响的调用方和自查方法。治理获批后，报告默认保存到目标项目的 `docs/project-architect-report.md`。只读、没有可执行项、拒绝治理或需要保留同名人工报告时，全文在会话交付。[执行复核与维护导读](skills/project-architect-skills/references/execution-and-handover.md)

## 验证模块

在本仓库根目录运行以下命令。测试与报告汇总脚本均使用 Python 3 标准库。

```sh
python3 -B -m unittest discover -s tests -v
```

测试通过时，最后一行显示 `OK`。检查记录和可运行的示例见[必要文档](skills/project-architect-skills/references/necessary-documents.md)、[架构图](skills/project-architect-skills/references/architecture-diagrams.md)、[目录结构](skills/project-architect-skills/references/directory-structure.md)和[代码异味](skills/project-architect-skills/references/code-smells.md)检查判据。

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

在可写的 Codex 会话中打开输出的临时目录，输入 `project-architect-skills`。先核对体检摘要和待授权计划都已展示，列出的两项分别指向 `README.md` 和 `test_names.py`。在临时仓库根目录运行 `git status --short`，应无输出。随后在同一会话回复 **同意治理**，完成后核对以下结果。

- `README.md` 增加验收步骤及预期输出。`test_names.py` 移到 `tests/`。
- 在临时仓库根目录运行 `python3 -B names.py`，仍输出 `Ada, Bob`。运行 `python3 -B -m unittest discover -s tests`，1 项通过。
- `docs/project-architect-report.md` 包含四项体检、两项已通过的执行复核和维护导读。两项改动都有各自的改前基线和验收证据。

另建一份相同的临时仓库，收到授权提示后回复「不同意治理」。会话应交付检查结果和未执行的建议，`git status --short` 仍无输出。
