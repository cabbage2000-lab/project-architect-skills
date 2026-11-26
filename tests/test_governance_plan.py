import json
import subprocess
import sys
import tempfile
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


class GovernancePlanTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / "docs").mkdir()
        for name in ("README.md", "docs/modules.md", "docs/api.md"):
            (self.root / name).write_text("# 运行\n## 验证\n", encoding="utf-8")

    def run_plan(self, *candidates, mode="execute", preview=False, as_json=False, **fields):
        command = [sys.executable, "-B", str(SCRIPT)]
        if preview:
            command.append("--preview")
        if as_json:
            command.append("--json")
        return subprocess.run(
            command, cwd=self.root,
            input=json.dumps({"mode": mode, "candidates": candidates, **fields}, ensure_ascii=False),
            capture_output=True, text=True,
        )

    def report(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def assert_invalid(self, result, field):
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn(field, result.stderr)

    def test_keeps_all_recommended_items_in_order_and_explains_other_findings(self):
        unresolved = candidate(
            "核实同名规则", "src/names.py::sort_names",
            status="待确认", reason="同名记录的业务口径尚无依据。",
        )
        plan = self.report(self.run_plan(
            ready("补写验证说明", "README.md#验证"),
            unresolved,
            ready("更新模块图", "docs/modules.md#依赖"),
            candidate("统一示例排版", "docs/examples.md", status="暂缓", reason="排版不影响本轮交接。"),
            ready("补写运行示例", "README.md#运行"),
            ready("补写接口约定", "docs/api.md#导出"),
        ))
        selected, remaining = plan.split("### 未纳入本轮执行")
        plan_items = [line for line in selected.splitlines() if line.startswith("### ")]
        self.assertEqual(plan_items, [
            "### 1. 补写验证说明", "### 2. 更新模块图", "### 3. 补写运行示例", "### 4. 补写接口约定",
        ])
        self.assertIn("| 核实同名规则 | 待确认 | 同名记录的业务口径尚无依据。", plan)
        self.assertIn(unresolved["target"], plan)
        self.assertIn("| 统一示例排版 | 暂缓 | 排版不影响本轮交接。", remaining)

    def test_selected_item_keeps_its_baseline_and_replay_details(self):
        selected = ready("补写验证说明", "README.md#验证")
        plan = self.report(self.run_plan(selected))
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
        plan = self.report(self.run_plan(*candidates))
        preview = self.report(self.run_plan(*candidates, preview=True))
        body, prompt = preview.rstrip().rsplit("\n\n", 1)
        self.assertEqual(body, plan.rstrip().replace("本轮按以下顺序执行 4 项。", "本轮拟治理 4 项，待授权。"))
        self.assertEqual(prompt, "请在当前会话回复 **同意治理**，我会按以上计划逐项修复和验收。")

    def test_preview_without_selected_items_omits_consent_prompt(self):
        selected = ready("补写验证说明", "README.md#验证")
        blocked = candidate("整理导出路径", "src/export.py::export", status="待验证", reason="缺少输入样例。")
        for candidates, mode in (((), "execute"), ((blocked,), "execute"), ((selected,), "inspect")):
            with self.subTest(candidates=candidates, mode=mode):
                plan = self.report(self.run_plan(*candidates, mode=mode))
                self.assertEqual(self.report(self.run_plan(*candidates, mode=mode, preview=True)), plan)
                self.assertNotIn("同意治理", plan)

    def test_inspect_keeps_suggestions_without_scheduling_any_write(self):
        plan = self.report(self.run_plan(
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
        self.assertIn("本轮无可执行的治理事项。", self.report(self.run_plan()))
        plan = self.report(self.run_plan(candidate(
            "整理导出路径", "src/export.py::export", status="待验证", reason="无法重放导出结果。",
        )))
        self.assertIn("本轮无可执行的治理事项。", plan)
        self.assertIn("| 整理导出路径 | 待验证 | 无法重放导出结果。", plan)

    def test_repeated_target_rejects_the_whole_plan(self):
        result = self.run_plan(
            ready("补写模块关系图", "docs/modules.md#依赖"),
            ready("补画缺失连线", "docs/modules.md#依赖"),
        )
        self.assert_invalid(result, "candidates[1].target")

    def test_missing_evidence_or_execution_details_rejects_the_whole_plan(self):
        complete = ready("补写验证说明", "README.md#验证")
        incomplete = ready("补写接口约定", "docs/api.md#导出")
        for field in ("evidence", "scope", "baseline", "steps", "acceptance", "rollback"):
            with self.subTest(field=field):
                result = self.run_plan(complete, {key: value for key, value in incomplete.items() if key != field})
                self.assert_invalid(result, f"candidates[1].{field}")

    def test_unknown_mode_or_unclassified_execution_candidate_is_rejected(self):
        self.assert_invalid(self.run_plan(mode="draft"), "mode")
        for status in ("未知", "未执行"):
            with self.subTest(status=status):
                self.assert_invalid(self.run_plan(candidate("补写验证说明", "README.md#验证", status=status)), "status")

    def test_unlocatable_only_source_is_pending_without_authorization(self):
        item = ready("核对入口", "入口")
        (self.root / "docs/link.md").symlink_to(SCRIPT)
        for source in ("README.md:999999", "README.md:2–1", "README.md:0", "`README.md#L1-L3`",
                       "docs/link.md:1", "docs/gone.md", "`docs/missing file.md`",
                       "missing.py::run", "absent.md#运行", "../outside.py:1"):
            with self.subTest(source=source):
                result = self.run_plan({**item, "evidence": [source]}, preview=True, as_json=True)
                packet = json.loads(self.report(result))
                self.assertEqual(packet["plan"]["candidates"][0]["status"], "待确认")
                self.assertIn(source, packet["markdown"])
                self.assertNotIn("同意治理", packet["markdown"])

    def test_observations_cannot_replace_failed_local_sources(self):
        item = ready("核对入口", "入口")
        notes = ["命令观察：python -V 已打印版本", "https://example.org/spec", "专家现场核对记录"]
        for sources, status in ((notes, "可执行"), (["README.md:99", *notes, "docs/gone.md"], "待确认")):
            with self.subTest(status=status):
                result = self.run_plan({**item, "evidence": sources}, preview=True, as_json=True)
                packet = json.loads(self.report(result))
                checked = packet["plan"]["candidates"][0]
                self.assertEqual(checked["status"], status)
                self.assertEqual(checked["evidence"], sources)
                self.assertEqual("同意治理" in packet["markdown"], status == "可执行")

    def test_independent_sources_and_failed_reference_survive_plan_replay(self):
        sources = ["README.md:1–2", "README.md#L2", "命令观察：python -V 已打印版本", "https://example.org/spec#usage"]
        first = {**ready("核对运行入口", "入口"), "evidence": sources + ["README.md:99"]}
        other = {**ready("核对模块", "旧模块"), "evidence": ["docs/gone.md:4"]}
        packet = json.loads(self.report(self.run_plan(first, other, preview=True, as_json=True)))
        approved, pending = packet["plan"]["candidates"]
        self.assertEqual(approved["evidence"], sources)
        self.assertIn("README.md:99", approved["reason"])
        self.assertEqual(pending["status"], "待确认")
        (self.root / "README.md").rename(self.root / "GUIDE.md")
        (self.root / "docs/gone.md").write_text("新增\n" * 5, encoding="utf-8")
        record = {"audit": ["## 必要文档"], "plan": packet["plan"], "guide": [], "guide_limit": "已移动入口。",
                  "reviews": [{"target": "入口", "status": "已解决", "reason": "已核对移动后的入口。"}]}
        result = subprocess.run([sys.executable, "-B", str(SCRIPT.with_name("governance_report.py"))],
                                cwd=self.root, input=json.dumps(record), text=True, capture_output=True)
        report = self.report(result)
        self.assertIn("### 1. 核对运行入口", report)
        self.assertIn("| 核对模块 | 待确认 |", report)
