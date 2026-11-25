import json
import subprocess
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "skills/project-architect-skills/scripts/governance_plan.py"


def candidate(title, target, **changes):
    return {
        "title": title,
        "target": target,
        "evidence": [target],
        "impact": "接手者无法从现有入口验证本轮改动。",
        "status": "可执行",
        "reason": "直接影响本轮的交接任务。",
        **changes,
    }


def ready(title, target):
    return candidate(
        title, target,
        scope=f"补写 {target}。",
        baseline="现有测试命令已通过，说明中尚未列出命令。",
        steps="在相应章节写入该命令。",
        acceptance="按说明运行命令并核对退出码为 0。",
        rollback="撤回本次新增段落并对照改前内容。",
    )


def run_plan(*candidates, mode="execute", preview=False):
    command = [sys.executable, "-B", str(SCRIPT)]
    if preview:
        command.append("--preview")
    return subprocess.run(
        command,
        input=json.dumps({"mode": mode, "candidates": candidates}, ensure_ascii=False),
        capture_output=True,
        text=True,
    )


class GovernancePlanTests(unittest.TestCase):
    def report(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def assert_invalid(self, result, field):
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn(field, result.stderr)

    def test_selects_first_three_eligible_candidates_and_retains_unselected_evidence(self):
        unresolved = candidate(
            "核实同名规则", "src/names.py::sort_names",
            status="待确认", reason="同名记录的业务口径尚无依据。",
        )
        plan = self.report(run_plan(
            ready("补写验证说明", "README.md#验证"),
            unresolved,
            ready("更新模块图", "docs/modules.md#依赖"),
            ready("补写运行示例", "README.md#运行"),
            ready("补写接口约定", "docs/api.md#导出"),
        ))
        plan_items = [line for line in plan.splitlines() if line.startswith(("### 1.", "### 2.", "### 3.", "### 4."))]
        self.assertEqual(plan_items, ["### 1. 补写验证说明", "### 2. 更新模块图", "### 3. 补写运行示例"])
        self.assertIn("| 核实同名规则 | 待确认 | 同名记录的业务口径尚无依据。", plan)
        self.assertIn(unresolved["target"], plan)
        self.assertIn("| 补写接口约定 | 暂缓 | 本轮已纳入 3 项", plan)
        self.assertIn("docs/api.md#导出", plan)

    def test_selected_item_keeps_its_baseline_and_replay_details(self):
        selected = ready("补写验证说明", "README.md#验证")
        plan = self.report(run_plan(selected))
        for field in ("reason", "impact", "scope", "baseline", "steps", "acceptance", "rollback"):
            with self.subTest(field=field):
                self.assertIn(selected[field], plan)

    def test_preview_preserves_plan_and_prompts_for_consent(self):
        candidates = (
            ready("补写验证说明", "README.md#验证"),
            ready("更新模块图", "docs/modules.md#依赖"),
            ready("补写运行示例", "README.md#运行"),
            ready("补写接口约定", "docs/api.md#导出"),
        )
        plan = self.report(run_plan(*candidates))
        preview = self.report(run_plan(*candidates, preview=True))
        body, prompt = preview.rstrip().rsplit("\n\n", 1)
        self.assertEqual(body, plan.rstrip().replace("本轮按以下顺序执行 3 项。", "本轮拟治理 3 项，待授权。"))
        self.assertEqual(prompt, "请在当前会话回复 **同意治理**，我会按以上计划逐项修复和验收。")

    def test_preview_without_selected_items_omits_consent_prompt(self):
        selected = ready("补写验证说明", "README.md#验证")
        blocked = candidate("整理导出路径", "src/export.py::export", status="待验证", reason="缺少输入样例。")
        for candidates, mode in (((), "execute"), ((blocked,), "execute"), ((selected,), "inspect")):
            with self.subTest(candidates=candidates, mode=mode):
                plan = self.report(run_plan(*candidates, mode=mode))
                self.assertEqual(self.report(run_plan(*candidates, mode=mode, preview=True)), plan)
                self.assertNotIn("同意治理", plan)

    def test_inspect_keeps_suggestions_without_scheduling_any_write(self):
        plan = self.report(run_plan(
            candidate("补写验证说明", "README.md#验证", status="未执行", reason="本轮只读。"),
            ready("更新模块图", "docs/modules.md#依赖"),
            candidate("改善导出入口", "src/export.py::export", status="待验证", reason="缺少输入样例。"),
            mode="inspect",
        ))
        self.assertNotIn("### 1.", plan)
        self.assertNotIn("**执行步骤**", plan)
        self.assertIn("| 补写验证说明 | 未执行 | 本轮只读。", plan)
        self.assertIn("| 更新模块图 | 未执行 |", plan)
        self.assertIn("| 改善导出入口 | 未执行 | 待验证。缺少输入样例。", plan)

    def test_empty_or_blocked_plan_has_no_execution(self):
        self.assertIn("本轮无可执行的治理事项。", self.report(run_plan()))
        plan = self.report(run_plan(candidate(
            "整理导出路径", "src/export.py::export", status="待验证", reason="无法重放导出结果。",
        )))
        self.assertIn("本轮无可执行的治理事项。", plan)
        self.assertIn("| 整理导出路径 | 待验证 | 无法重放导出结果。", plan)

    def test_repeated_target_rejects_the_whole_plan(self):
        result = run_plan(
            ready("补写模块关系图", "docs/modules.md#依赖"),
            ready("补画缺失连线", "docs/modules.md#依赖"),
        )
        self.assert_invalid(result, "candidates[1].target")

    def test_missing_evidence_or_execution_details_rejects_the_whole_plan(self):
        complete = ready("补写验证说明", "README.md#验证")
        incomplete = ready("补写接口约定", "docs/api.md#导出")
        for field in ("evidence", "scope", "baseline", "steps", "acceptance", "rollback"):
            with self.subTest(field=field):
                result = run_plan(complete, {key: value for key, value in incomplete.items() if key != field})
                self.assert_invalid(result, f"candidates[1].{field}")

    def test_unknown_mode_or_unclassified_execution_candidate_is_rejected(self):
        self.assert_invalid(run_plan(mode="draft"), "mode")
        for status in ("未知", "未执行"):
            with self.subTest(status=status):
                self.assert_invalid(run_plan(candidate("补写验证说明", "README.md#验证", status=status)), "status")
