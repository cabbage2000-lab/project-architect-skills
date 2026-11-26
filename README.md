# 项目治理架构师

让 Vibe Coding 在项目变大后依然顺畅。准备改功能时，它帮你找出该从哪里改、哪些地方也会受影响，以及改完怎么验证。

## 项目背景

刚开始用 AI 做软件，加一个功能可能只要几轮对话。做过几版以后，哪怕只是给订单表加一列「退款金额」，也可能遇到这些麻烦。

| 痛点 | 为什么会积累 | 最后会遇到什么 |
|---|---|---|
| 文档里的引用失效 | AI 移动了文件，却容易漏掉其他手册里指向它的链接和命令。 | 新人照着 README 操作，第一步就找不到文件。 |
| 代码越来越臃肿 | 加功能时，复制一段现成代码很快，重复的部分却很少回头整理。 | 页面、导出表和对账单各算一次退款，改漏一处，三个金额就对不上。 |
| 架构图跟不上代码 | 退款流程改了，图上还画着原来的步骤。 | 退款到账慢了，AI 沿着旧图排查，找错了地方。 |
| 相似功能越加越多 | 你说「加个退款导出」，AI 容易顺着做，很少先问现有导出能否满足。 | 用户面对两个相似的按钮，不知道该点哪个；以后两套功能都要维护。 |
| 项目背景要反复解释 | 「部分退款怎么算」只在上次对话里讨论过，项目里没留下原因。 | 换个会话，你又得从头讲一遍，否则 AI 可能改掉当初有意保留的规则。 |
| 改一处会影响哪里，说不清 | 同一个算金额的函数，后来又被月末对账用上了。 | 原本只想改页面上的退款金额，却连对账单也一起改了。 |
| 改完心里没底 | 每次只试新功能，旧用法没有留下可以重复检查的例子。 | 新列显示正常，直到客户拿到旧订单的账单，才发现退款被多算了一次。 |
| **Token 消耗越来越大，小功能越改越慢** | 为了弄清现状，AI 要反复读文件，你要补讲背景，改错了还得再来一轮。 | 同样是给订单表加一列，现在要多花好几轮对话才能改对。 |

项目治理架构师会对照当前的文档、图和代码，指出哪些说明已经失效、哪些地方共用同一条规则，并给出改完可以实际核对的例子。你可以先看结果，再决定这次值得改什么。

## 快速开始

**1. 让 AI 安装。** 用 Codex、Claude Code 或 WorkBuddy 打开你想检查的项目，把本工具的项目链接或下载好的文件夹路径和下面这句话一起发给 AI。

> 请帮我把「项目治理架构师」（project-architect-skills）安装到当前项目，装好后告诉我。

**2. 开始检查。** 安装好后，在同一个项目里新开对话，输入：

> 项目评估

AI 会先给你看检查结果和修复建议。想让它动手，就回复 **同意治理**。有多项建议时，也可以只选其中几项。

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

## 使用

下面用订单项目举例。选一个你正拿不准的问题，换成自己的模块名或文件名。要显式调用，可以在问题前加上「请用 project-architect-skills 检查」。

**工程文档专家 · 两份手册能合并到什么程度？**

> README 和操作手册各有一张订单 CSV 列序表。它们讲的是同一版导出吗？下次加列，我想只维护一张表。请指出规则该留在哪个章节，另一处哪些内容可以换成链接，哪些对账步骤还得留下。

仓库自带的样例里，README 的「导出规则」是约定的维护入口。操作手册可以链接到这张表，同时保留手册独有的对账示例。[查看样例检查记录](skills/project-architect-skills/references/examples/necessary-docs-record.json)

**软件架构专家 · 这条箭头画错了吗？**

> 图上画着「订单 → 退款」，同事说两边靠消息队列联系。这条箭头表示代码调用还是事件流向？请对照图例，从取消订单的入口追到退款开始处理的位置，再核对项目允许的依赖方向。该修图、改代码，还是保留现状？请指出决定这一点的连线和源码位置。

**仓库结构专家 · 测试移了位置，CI 还会跑它吗？**

> 我把「部分退款」用例从订单源码旁移到了 `tests/`，CI 还是绿的。请用 CI 实际采用的测试命令核对，这条用例有没有执行？结合订单模块自己的目录约定，判断该保留新位置、把文件移回去，还是调整测试发现规则。

**代码质量专家 · 两段退款计算能共用一个函数吗？**

> 订单导出和月末对账各算一次退款金额，我想把计算合并。假设两条明细分摊后各退 0.005 元，两个入口分别在哪一步舍入，最后各记几分钱？请用现有测试或业务约定核对，再指出哪段逻辑可以共用，以及重构后两边各要验什么结果。

**四位专家一起检查 · 交接前只够先修一项**

> 用 project-architect-skills 评估订单导出。新人接手后的第一个任务是加一列退款金额，交接前我只来得及先修一个问题。请四位专家围绕这个任务取证，把同一原因造成的发现合并计分。哪一项最值得先修？请给出它卡住的具体步骤，以及修完后可以重跑的验收方法，等我选定再动手。

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
