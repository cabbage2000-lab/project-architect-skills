import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "skills/project-architect-skills/scripts/directory_structure.py"

COLOCATED_TEST = {
    "path": "src/orders/test_export.py",
    "expected": "src/orders/",
    "basis": "rule",
    "matches": True,
    "detail": "测试与被测源码同目录。",
    "evidence": ["AGENTS.md:8", "src/orders/export.py:1"],
}
MISPLACED_MODULE = {
    "path": "src/shared/totals.py",
    "expected": "src/orders/totals.py",
    "basis": "rule",
    "matches": False,
    "detail": "订单专用业务逻辑归属订单模块。",
    "evidence": ["AGENTS.md:9", "src/shared/totals.py:4"],
    "impact": "调整时应同步更新导出入口的导入。",
}


def directory_record(*checks):
    return {"scope": ["核对订单导出及共享目录。"], "unread": [], "checks": list(checks)}


def run_report(record, *args):
    return subprocess.run(
        [sys.executable, "-B", str(SCRIPT), *args],
        input=json.dumps(record, ensure_ascii=False),
        capture_output=True,
        text=True,
    )


class DirectoryStructureTests(unittest.TestCase):
    def report(self, record):
        result = run_report(record)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_project_rules_allow_colocated_tests_and_flag_misplaced_code(self):
        report = self.report(directory_record(COLOCATED_TEST, MISPLACED_MODULE))
        self.assertIn("| src/orders/test_export.py | src/orders/ | 符合约定 |", report)
        self.assertIn("| src/shared/totals.py | src/orders/totals.py | 偏离约定 |", report)
        self.assertIn("AGENTS.md:9、src/shared/totals.py:4", report)
        suggestions = report.split("### 建议调整\n", 1)[1]
        self.assertIn("src/shared/totals.py → src/orders/totals.py", suggestions)
        self.assertIn(MISPLACED_MODULE["impact"], suggestions)
        self.assertNotIn("test_export.py", suggestions)

    def test_similar_layout_without_a_rule_leaves_placement_pending(self):
        convention = {
            **MISPLACED_MODULE,
            "basis": "convention",
            "detail": "对账模块把自己的计价逻辑放在模块目录。",
            "evidence": ["src/reconciliation/totals.py:4"],
        }
        report = self.report(directory_record(convention))
        self.assertIn("| src/shared/totals.py | src/orders/totals.py（待确认） | 待确认 |", report)
        self.assertIn("src/reconciliation/totals.py:4", report)
        self.assertNotIn("偏离约定", report)
        self.assertNotIn("### 建议调整", report)

    def test_unread_rule_preserves_independent_confirmed_deviation(self):
        unknown = {
            "path": "tools/test_export.py",
            "basis": "unknown",
            "detail": "工具专用的测试配置无法读取，适用规则仍需核实。",
            "evidence": ["tools/README.md:5"],
        }
        record = directory_record(unknown, MISPLACED_MODULE)
        record["unread"] = [{"source": "tools/pyproject.toml", "reason": "当前不可访问"}]
        report = self.report(record)
        self.assertIn("**检查结果**　发现问题", report)
        self.assertIn("| tools/test_export.py | 待确认 | 待确认 |", report)
        self.assertIn("tools/pyproject.toml（当前不可访问）", report)
        suggestions = report.split("### 建议调整\n", 1)[1]
        self.assertIn("src/shared/totals.py", suggestions)
        self.assertNotIn("tools/test_export.py", suggestions)

    def test_inaccessible_scope_can_report_pending_without_inspected_paths(self):
        record = directory_record()
        record["unread"] = [{"source": "src/orders/", "reason": "超出可见范围"}]
        report = self.report(record)
        self.assertIn("**检查结果**　待确认", report)
        self.assertIn("src/orders/（超出可见范围）", report)

    def test_single_entry_without_directory_roles_can_be_not_applicable(self):
        record = directory_record({
            "path": "hello.py",
            "basis": "not_applicable",
            "detail": "单一脚本直接输出结果，没有其他目录职责。",
            "evidence": ["hello.py:1"],
        })
        report = self.report(record)
        self.assertIn("**检查结果**　不适用", report)
        self.assertNotIn("### 建议调整", report)

    def test_utf8_file_input_matches_stdin(self):
        record = directory_record(COLOCATED_TEST)
        record["project"] = {"units": 1, "files": 2, "evidence": ["两个源码文件"], "focus": "订单导出"}
        report = self.report(record)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "目录结构.json"
            path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            result = run_report({}, str(path))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, report)
        self.assertIn("**项目规模**　小项目", report)
        self.assertIn("**检查结果**　范围内未发现", report)

    def test_generated_artifact_can_be_scoped_or_combined_with_path_coverage(self):
        record = directory_record(MISPLACED_MODULE)
        scope = {"check": "generated_artifact", "unit": "订单 SDK"}
        record["selected"] = [scope]
        artifact = {
            "status": "发现问题", "source": "orders.json", "artifact": "sdk/orders.py",
            "consumer": "应用安装的订单 SDK", "operation": "在同版临时副本中运行 make sdk 并比较字段",
            "expected": "新 SDK 的备注可省略", "observed": "随包 SDK 强制备注必填",
            "impact": "创建订单要求多余字段", "evidence": ["Makefile:9", "sdk/orders.py:3"],
        }
        record["artifacts"] = [artifact]
        packet = json.loads(run_report(record, "--json").stdout)
        self.assertEqual(packet["results"], [{**scope, "status": "已查"}])
        self.assertIn(artifact["observed"], packet["markdown"])
        self.assertNotIn(MISPLACED_MODULE["path"], packet["markdown"])
        for key in artifact:
            bad = {**record, "artifacts": [{k: v for k, v in artifact.items() if k != key}]}
            result = run_report(bad, "--json")
            self.assertEqual((result.returncode, result.stdout), (2, ""))
            self.assertIn(key, result.stderr)
        record["selected"].insert(0, {**scope, "check": "目录结构"})
        del record["artifacts"]
        packet = json.loads(run_report(record, "--json").stdout)
        self.assertIn("**检查结果**　发现问题", packet["markdown"])
        self.assertEqual([r["status"] for r in packet["results"]], ["部分已查", "未查"])

    def test_artifact_only_preserves_inapplicable_and_blocked_results(self):
        scope = {"check": "generated_artifact", "unit": "报告"}
        record = {"scope": ["产物清单"], "selected": [scope], "unread": []}
        self.assertIn("**检查结果**　未查", self.report(record))
        for status, coverage in (("不适用", "已查"), ("待确认", "部分已查")):
            record["artifacts"] = [{"status": status, "reason": "交付依据", "evidence": ["README.md:2"]}]
            packet = json.loads(run_report(record, "--json").stdout)
            self.assertEqual(packet["results"][0]["status"], coverage)
            self.assertIn(f"**检查结果**　{status}", packet["markdown"])

    def test_missing_rule_evidence_or_repair_details_produce_no_partial_report(self):
        cases = (
            (directory_record(), "checks"),
            (directory_record({**COLOCATED_TEST, "basis": "guess"}), "checks.basis"),
            (directory_record({**COLOCATED_TEST, "evidence": []}), "checks.evidence"),
            (directory_record({**COLOCATED_TEST, "matches": 1}), "checks.matches"),
            (directory_record({**MISPLACED_MODULE, "expected": None}), "checks.expected"),
            (directory_record({**MISPLACED_MODULE, "impact": ""}), "checks.impact"),
        )
        for record, field in cases:
            with self.subTest(field=field):
                result = run_report(record)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertIn(field, result.stderr)
