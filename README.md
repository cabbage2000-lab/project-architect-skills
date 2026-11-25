# code-architect-skills

这个 Codex Skill 帮助接手项目的人检查必要文档和架构图。它核对交接说明是否够用，并把图中的模块及其关系与当前实现对照。各项是否适用取决于项目用途、交付方式和本轮维护任务。

## 使用

本仓库已配置项目级 Skill 入口。在其他项目使用时，将 `skills/code-architect-skills` 整个目录复制到目标项目的 `.agents/skills/`，然后在该项目的 Codex 会话中输入

```text
code-architect-skills
```

默认调用会检查两项，并在已有授权内修订可验证的缺口。已有维护任务可以直接附上，例如「我要改订单导出的列名」。只想查看某项诊断时，输入「用 code-architect-skills 只读检查必要文档」或「用 code-architect-skills 只读检查架构图」。

检查前先判断项目规模。小项目通查相关资料，中等项目分模块核对，大项目优先检查主要业务路径和跨模块依赖。判档和取证方式见[项目规模与取证范围](skills/code-architect-skills/references/project-size.md)。

报告列出规模依据、已查范围、逐项结论和修订建议。架构图章节给出图件出处、与源码对照的节点或关系，以及仍需核实的资料。默认报告路径为目标项目的 `docs/code-architect-report.md`。只读或需要保留同名人工报告时，全文在会话交付。

## 验证模块

在本仓库根目录运行以下命令。测试与报告汇总脚本均使用 Python 3 标准库。

```sh
python3 -B -m unittest discover -s tests -v
```

测试通过时，最后一行显示 `OK`。检查记录格式和可运行的汇总示例见[必要文档检查判据](skills/code-architect-skills/references/necessary-documents.md)和[架构图检查判据](skills/code-architect-skills/references/architecture-diagrams.md)。

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

在本仓库的 Codex 会话中输入「用 code-architect-skills 只读检查 `<临时目录路径>` 的必要文档」，将占位符换成终端输出的路径。会话应给出报告。复核以下三点。

- 「启动或最小使用示例」显示「范围内未发现」，依据指向临时项目的运行说明。
- 「验证改动的方法」显示「发现问题」，缺口类型为「缺少说明」。补写建议指向临时项目的 `README.md`，可记录运行后的预期输出 `Ada, Bob`。
- 终端执行 `ls -A "$smoke_project"`，目录清单应只有 `README.md` 和 `names.py`。
