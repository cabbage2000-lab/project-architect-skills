import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "skills/project-architect-skills/scripts/governance_report.py"
REPORT = Path("docs/project-architect-report.md")


def candidate(target, title):
    return {
        "target": target, "title": title, "evidence": [target],
        "impact": "接手人需要定位并验证导出。", "status": "可执行", "reason": "影响本轮导出维护。",
        "scope": target, "baseline": "样例输出已保存。", "steps": "更新计划位置。",
        "acceptance": "从导出入口重放固定输入。", "rollback": "恢复本项改前状态后重跑。",
    }


def check(kind, operation, expected, observed, result="通过"):
    return {"kind": kind, "operation": operation, "expected": expected, "observed": observed, "result": result}


def guide(**fields):
    return {
        "task": "修改导出列名", "entry": "export.py::download_orders", "callers": "orders_page.py::download",
        "evidence": ["orders_page.py:8", "export.py:4"],
        "checks": ["导出空订单，应只得到表头。", "导出含引号的客户名，确认仍落在同一列。"],
        **fields,
    }


def report_record(candidates=(), reviews=(), entries=None, mode="execute"):
    return {
        "audit": ["## 必要文档\n\n缺少导出验证说明。", "## 代码异味\n\n导出入口同时负责取数和转义。"],
        "plan": {"mode": mode, "candidates": list(candidates)},
        "reviews": list(reviews),
        "guide": [guide()] if entries is None else entries,
    }


def run_report(record, root, *args):
    return subprocess.run(
        [sys.executable, "-B", str(SCRIPT), *args], cwd=root,
        input=json.dumps(record, ensure_ascii=False), text=True, capture_output=True,
    )


class GovernanceReportTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def report(self, record, *args):
        result = run_report(record, self.root, *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def invalid(self, record, field):
        result = run_report(record, self.root, "--write")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn(field, result.stderr)
        self.assertFalse((self.root / "docs").exists())

    def test_combines_plan_reviews_and_verified_guide(self):
        doc = candidate("README.md#验证", "补写验证说明")
        code = candidate("export.py::download_orders", "提取 CSV 格式化")
        reviews = [
            {"target": doc["target"], "status": "通过", "kind": "handover", "changes": "README.md 新增验证小节。",
             "checks": [check("handover", "执行 README 中的 python3 -B export.py", "空订单仅表头", "输出 Customer\\r\\n")]},
            {"target": code["target"], "status": "通过", "kind": "code", "changes": "新增 csv_format.py::format_csv。",
             "checks": [check("structure", "核对下载入口", "调用 format_csv", "export.py:12 调用了 format_csv"),
                        check("behavior", "重放空订单及带引号样例", "输出与改前逐字节一致", "两个样例一致")]},
        ]
        report = self.report(report_record(
            [doc, code], reviews, [guide(entry="csv_format.py::format_csv", target=code["target"])],
        ))
        headings = [line for line in report.splitlines() if line.startswith("## ")]
        self.assertEqual(headings, ["## 必要文档", "## 代码异味", "## 治理计划", "## 执行复核", "## 维护导读"])
        self.assertIn("两个样例一致", report)
        self.assertIn("**当前入口**　csv_format.py::format_csv", report)
        self.assertIn("orders_page.py::download", report)
        self.assertIn("2. 导出含引号的客户名", report)

    def test_code_cannot_pass_without_structure_and_behavior(self):
        code = candidate("export.py::download_orders", "提取 CSV 格式化")
        review = {"target": code["target"], "status": "通过", "kind": "code", "changes": "提取了格式化。",
                  "checks": [check("structure", "核对入口", "调用新函数", "发现调用")]}
        self.invalid(report_record([code], [review]), "reviews[0].checks")

    def test_regression_requires_evidence_and_disallows_rolled_back_entry(self):
        code = candidate("export.py::download_orders", "提取 CSV 格式化")
        review = {"target": code["target"], "status": "发现差异", "changes": "尝试将转义提取到 csv_format.py。",
                  "checks": [check("behavior", '导出 Ann "AJ"', 'Ann ""AJ""', 'Ann "AJ"', "发现差异")],
                  "preexisting": "改前 UI 截图测试也因缺少浏览器跳过。"}
        self.invalid(report_record([code], [review]), "reviews[0].rollback")
        review["rollback"] = {"status": "已回退", "evidence": "恢复 export.py，重放引号样例与改前一致。"}
        self.invalid(report_record([code], [review], [guide(
            entry="csv_format.py::format_csv", target=code["target"],
        )]), "guide[0].target")
        report = self.report(report_record([code], [review]))
        self.assertIn('Ann ""AJ""', report)
        self.assertIn("**改前已有差异**", report)
        self.assertIn("**回退复核**　已回退", report)
        self.assertIn("**当前入口**　export.py::download_orders", report)

    def test_failed_check_requires_regression_status(self):
        doc = candidate("README.md#验证", "补写验证说明")
        for status in ("待确认", "待验证", "暂缓", "已解决"):
            with self.subTest(status=status):
                review = {
                    "target": doc["target"], "status": status, "reason": "复查前的记录。",
                    "checks": [check("handover", "重放用例", "成功", "失败", "发现差异")],
                }
                self.invalid(report_record([doc], [review]), "reviews[0].status")

    def test_reviews_follow_selection_order_and_require_skipping_reason(self):
        doc = candidate("README.md#验证", "补写验证说明")
        code = candidate("export.py::download_orders", "提取 CSV 格式化")
        changed = {"target": doc["target"], "status": "已解决", "reason": "复核时发现 README 已补写。"}
        blocked = {"target": code["target"], "status": "待验证", "reason": "样例文件已由用户移动，无法重放。"}
        self.invalid(report_record([doc, code], [changed]), "reviews")
        self.invalid(report_record([doc, code], [blocked, changed]), "reviews[0].target")
        self.assertIn(blocked["reason"], self.report(report_record([doc, code], [changed, blocked])))

    def test_read_only_report_with_no_execution_still_includes_guide(self):
        report = self.report(report_record([candidate("README.md#验证", "补写验证说明")], mode="inspect"))
        self.assertIn("| 补写验证说明 | 未执行 |", report)
        self.assertNotIn("## 执行复核", report)
        self.assertIn("## 维护导读", report)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_empty_guide_records_the_visible_limit(self):
        record = report_record(entries=[])
        self.invalid(record, "guide_limit")
        record["guide_limit"] = "只读到 docs/，调用方需在源码开放后核对。"
        self.assertIn(record["guide_limit"], self.report(record))

    def test_managed_report_updates_but_manual_changes_are_preserved(self):
        path = self.root / REPORT
        self.assertEqual(self.report(report_record(), "--write").strip(), str(REPORT))
        original = path.read_bytes()
        self.assertEqual(self.report(report_record(), "--write").strip(), str(REPORT))
        self.assertEqual(path.read_bytes(), original)
        updated = report_record(entries=[guide(task="调整下载入口")])
        self.assertEqual(self.report(updated, "--write").strip(), str(REPORT))
        self.assertIn("调整下载入口", path.read_text(encoding="utf-8"))
        path.write_bytes(path.read_bytes() + "\n人工交接备注\n".encode("utf-8"))
        manual = path.read_bytes()
        record = report_record()
        self.assertEqual(self.report(record, "--write"), self.report(record))
        self.assertEqual(path.read_bytes(), manual)

    def test_renamed_report_can_refresh_a_valid_legacy_marker(self):
        path = self.root / REPORT
        record = report_record()
        self.assertEqual(self.report(record, "--write").strip(), str(REPORT))
        original = path.read_bytes()
        legacy = original.replace(b"<!-- project-architect-skills sha256=", b"<!-- code-architect-skills sha256=", 1)
        edited = legacy + "人工交接备注\n".encode("utf-8")
        path.write_bytes(edited)
        self.assertEqual(self.report(record, "--write"), self.report(record))
        self.assertEqual(path.read_bytes(), edited)
        path.write_bytes(legacy)
        self.assertEqual(self.report(record, "--write").strip(), str(REPORT))
        self.assertEqual(path.read_bytes(), original)

    def test_existing_unmanaged_report_and_symlink_destination_are_preserved(self):
        docs = self.root / "docs"
        docs.mkdir()
        path = self.root / REPORT
        path.write_text("人工报告\n", encoding="utf-8")
        record = report_record()
        expected = self.report(record)
        self.assertEqual(self.report(record, "--write"), expected)
        self.assertEqual(path.read_text(encoding="utf-8"), "人工报告\n")
        path.unlink()
        target = self.root / "separate-report.md"
        path.symlink_to(target)
        self.assertEqual(self.report(record, "--write"), expected)
        self.assertTrue(path.is_symlink())
        self.assertFalse(target.exists())
