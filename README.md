# Project Architect Skills

**English** | [简体中文](README.zh-CN.md)

Keep your codebase under control and easy to maintain as your AI-assisted development (vibe coding) project grows more complex.

Project Architect is a skill for **Codex, Claude Code, and WorkBuddy**. It checks documentation, architecture diagrams, repository layout, and code quality against the source. Before a handover or a change, it helps you find where to start, which callers depend on the current behavior, and how to verify the result.

## Quick start

**1. Install the skill.** Open the project you want to inspect and give your coding assistant this prompt.

> Install the project-architect-skills skill from https://github.com/cabbage2000-lab/project-architect-skills in the current project.

**2. Run a project health check.** Start a new conversation in the same project. In Claude Code, enter this command.

```text
/project-architect-skills Run a full project health check
```

The Chinese prompt is `/project-architect-skills 项目体检`. In Codex or WorkBuddy, say “Use project-architect-skills to run a full project health check.”

The first pass is read-only. You get scores for the areas assessed, evidence for each finding, and a proposed repair plan. Reply “Apply the proposed fixes” or `同意治理` to approve the plan. You can also name just the items you want fixed.

<details>
<summary>Project-level installation paths</summary>

Copy the entire `skills/project-architect-skills/` folder from this repository into the appropriate directory in the target project. This repository uses relative symlinks so you can also try it directly in a checkout that preserves them.

| Tool | Directory in the target project | How to invoke the skill |
| --- | --- | --- |
| Codex | `.agents/skills/` | `project-architect-skills` |
| Claude Code | `.claude/skills/` | `/project-architect-skills` |
| WorkBuddy Desktop | `.workbuddy/skills/` (tested on macOS with WorkBuddy 5.11.3) | `Use project-architect-skills to assess this project.` |

For a WorkBuddy project using `.codebuddy/` configuration, copy the skill into `.codebuddy/skills/`. In the chosen directory, `project-architect-skills/SKILL.md` should sit alongside the `agents/`, `references/`, and `scripts/` directories. [Claude Code skills](https://code.claude.com/docs/en/skills) · [WorkBuddy project configuration](https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Project#项目级代码开发配置)

</details>

## Usage examples

Pick one question for a focused assessment. In Codex or WorkBuddy, replace the leading `/project-architect-skills` with `Use project-architect-skills to`.

| Reviewer | Claude Code prompt |
| --- | --- |
| All four reviewers | `/project-architect-skills Run a full project health check` |
| Engineering documentation | `/project-architect-skills Find missing handover steps and duplicated instructions` |
| Architecture decision records | `/project-architect-skills Check whether the order storage choice and its trade-offs are documented` |
| Recommend documentation | `/project-architect-skills Which handover documents should a newcomer have for a project this size?` |
| Write a specific document | `/project-architect-skills Write a local setup guide for a newcomer in docs/getting-started.md` |
| Software architecture | `/project-architect-skills Check the architecture diagram against the actual calls in the code` |
| Recommend architecture diagrams | `/project-architect-skills Which diagrams would help a newcomer understand a project this size?` |
| Draw a specific view | `/project-architect-skills Draw the order export sequence in Mermaid in docs/order-export.md` |
| Repository structure | `/project-architect-skills Check source and test locations against this project's conventions` |
| Code quality | `/project-architect-skills Identify the function most worth refactoring and give me a test case` |

## Project background

As AI coding tools become widely available, anyone can write code, and projects can quickly move from an idea to active development. As a project goes through more iterations and its codebase grows, AI starts to struggle. For complex features, AI often needs several rounds of clarifying questions to understand the context, and the logic or implementation can easily drift from the original intent.

AI rarely takes the initiative to maintain a project's architecture. It seldom refactors code, revisits architectural decisions, cleans up code smells, or checks for missing documentation and references on its own. These repetitive, time-consuming engineering tasks often become bottlenecks as a project evolves. Given clear instructions, AI can handle them well.

Software professionals build these engineering and architecture skills on a strong foundation in computer engineering. Developers without that background may find it hard to do this work on their own. This project helps bridge that gap by giving AI a structured way to carry out these tasks, so vibe coding stays smooth and efficient as projects grow.

## Reading the report

When a project keeps confidential documents or diagrams at Git-ignored paths, their absence from the checkout carries no penalty. Independently verified errors in public instructions still count.

Start with the operation you need to complete. If a README tells a new maintainer to run a deleted file, the report identifies the failing command and the step it blocks.

A full check scores four areas, up to 25 points each. The total is normalized to 100 across applicable areas. A focused check scores only the requested areas. The report scripts use Chinese labels. For example, `待补查` means the reviewer needs more evidence to assign a score. [Scoring rules](skills/project-architect-skills/references/health-score.md)

A read-only report appears in the conversation. Ask “Save this report” to keep a copy. After approved repairs, the default output is `docs/project-architect-report.md` in the target project. [Example report](docs/project-architect-report.md)

## Testing

Run the test suite from the root of this repository. The complete suite requires Python 3.10 or later and Git on your `PATH`. The Python code uses the standard library.

```sh
python3 -B -m unittest discover -s tests -v
```

The final line is `OK` when all tests pass. If it reads `OK (skipped=N)`, check the reasons next to the skipped cases. For example, Python 3.9 skips the pattern-matching test, and the Git history tests require Git.

<details>
<summary>Try a read-only documentation check</summary>

Create a temporary project with a working usage example.

```sh
smoke_project=$(mktemp -d)
cat > "$smoke_project/README.md" <<'EOF'
# Name list

Run `python3 names.py` from the project root to print the sorted names.
EOF
cat > "$smoke_project/names.py" <<'EOF'
names = ["Bob", "Ada", "Bob"]
print(", ".join(sorted(set(names))))
EOF
printf '%s\n' "$smoke_project"
```

From a conversation opened in **this** repository, ask “Use project-architect-skills to check the handover documentation in `<temporary project path>`. Keep the check read-only.” Substitute the path printed above.

- The usage check should cite the working example and report `范围内未发现` (no issue found in scope).
- The verification check should report `发现问题` (issue found). The README tells readers how to run the program but does not tell them what output to expect. The suggested addition should identify `Ada, Bob` as the expected result.
- Run `ls -A "$smoke_project"`. The directory should still contain only `README.md` and `names.py`.

</details>

<details>
<summary>Try the repair workflow in a temporary Codex project</summary>

From this repository's root, create a project with two independently verifiable issues. Its README lacks acceptance instructions and its test file sits outside the directory specified in its own project guidelines.

```sh
governance_project=$(mktemp -d)
mkdir -p "$governance_project/.agents/skills"
cp -R skills/project-architect-skills "$governance_project/.agents/skills/"
cat > "$governance_project/AGENTS.md" <<'EOF'
# Project conventions

This project maintains names.py and its tests. Run names.py from the project root.
Unit tests belong in tests/. Installed skills live in .agents/skills/.
EOF
cat > "$governance_project/README.md" <<'EOF'
# Name list

Run `python3 -B names.py` from the project root to print the unique names in alphabetical order.
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
  commit -qm 'Save fixture baseline'
(cd "$governance_project" && python3 -B names.py && python3 -B -m unittest discover -s . -p test_names.py)
printf '%s\n' "$governance_project"
```

Open the printed path in a writable Codex session and enter `project-architect-skills`. When the host supports subagents, check that all four reviewers load their definitions and return findings before the plan appears. The plan should identify `README.md` and `test_names.py`. At this point, `git status --short` in the temporary project should produce no output.

Approve the two repairs in the same conversation. Verify each result in the temporary project.

- `README.md` includes a verification command and its expected result. The test has moved to `tests/`.
- `python3 -B names.py` still prints `Ada, Bob`. Running `python3 -B -m unittest discover -s tests` runs and passes one test.
- `docs/project-architect-report.md` covers the four assessments, the baseline and verification result for each repair, and guidance for the next maintainer.

To check the decline path, create a fresh fixture and decline the proposed repairs. The session should deliver the findings and recommendations, and `git status --short` should still produce no output.

</details>

## License

Released under the [MIT License](LICENSE).
