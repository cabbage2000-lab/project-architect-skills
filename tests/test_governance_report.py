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
        "evidence": ["orders_page.py:4", "export.py:1"],
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
        (self.root / "export.py").write_text("def download_orders():\n    return 'Customer'\n", encoding="utf-8")
        (self.root / "orders_page.py").write_text(
            "from export import download_orders\n\ndef download():\n    return download_orders()\n", encoding="utf-8",
        )

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
        (self.root / "csv_format.py").write_text("def format_csv():\n    return 'Customer'\n", encoding="utf-8")
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

    def test_historical_scoring_fields_do_not_change_report(self):
        record = report_record()
        expected = self.report(record)
        legacy = {"version": 3, "scope": "full", "assessments": []}
        record["plan"]["scoring"] = legacy
        record["reassessment"] = legacy
        self.assertEqual(self.report(record), expected)

    def test_structure_signal_observations_are_advisory_and_require_behavior_checks(self):
        code = candidate("export.py::download_orders", "提取 CSV 格式化")
        observation = "export.py::download_orders 的结构决策点由 8 增至 9。"
        review = {
            "target": code["target"], "status": "通过", "kind": "code", "changes": "提取了格式化。",
            "structure_delta": [observation],
            "checks": [check("structure", "核对入口", "调用新函数", "发现调用")],
        }
        record = report_record([code], [review])
        self.invalid(record, "reviews[0].checks")
        review["checks"].append(check("behavior", "重放样例", "CSV 不变", "两个样例一致"))
        report = self.report(record)
        self.assertIn(observation, report)
        self.assertIn("两个样例一致", report)
        self.assertIn("**结果**　通过", report)

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
        before = {path: path.read_bytes() for path in self.root.iterdir()}
        report = self.report(report_record([candidate("README.md#验证", "补写验证说明")], mode="inspect"))
        self.assertIn("| 补写验证说明 | 未执行 |", report)
        self.assertNotIn("## 执行复核", report)
        self.assertIn("## 维护导读", report)
        self.assertEqual({path: path.read_bytes() for path in self.root.iterdir()}, before)

    def test_full_report_rejects_stale_guide_before_publication(self):
        for entry, field in (
            (guide(entry="gone.py::download"), "guide[0].entry"),
            (guide(evidence=["orders_page.py:4", "export.py:99"]), "guide[0].evidence"),
        ):
            with self.subTest(field=field):
                self.invalid(report_record(entries=[entry]), field)

    def test_standalone_guide_from_file_or_stdin_only_prints_the_guide(self):
        module = self.root / "export.py"
        module.write_text("COLUMNS = ('订单号', '客户')\n", encoding="utf-8")
        callers = ["orders.py", "reconciliation.py"]
        for name in callers:
            (self.root / name).write_text("from export import COLUMNS\n", encoding="utf-8")
        record = {"guide": [guide(entry="export.py::COLUMNS", callers="订单页和对账页共享列定义。",
                                  evidence=["export.py:1", *(name + ":1" for name in callers)])]}
        path = self.root / REPORT
        path.parent.mkdir()
        path.write_bytes(b"existing handover\n")
        payload = self.root / "guide.json"
        payload.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        report = self.report(record, "--guide-only")
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--guide-only", str(payload)],
                                cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report, result.stdout)
        self.assertEqual([line for line in report.splitlines() if line.startswith("## ")], ["## 维护导读"])
        self.assertIn("**当前入口**　export.py::COLUMNS", report)
        self.assertIn("reconciliation.py:1", report)
        self.assertIn("自查步骤", report)
        self.assertNotIn("同意治理", report)
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_standalone_guide_reports_visible_limits_and_cannot_publish_a_governance_report(self):
        record = {"guide": [], "guide_limit": "只读到 README，尚需核对业务入口。"}
        self.assertIn(record["guide_limit"], self.report(record, "--guide-only"))
        for args in ((), ("--guide-only", "--write")):
            result = run_report(record, self.root, *args)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
        self.assertFalse((self.root / REPORT).exists())

    def test_standalone_guide_rejects_unverified_targets_and_stale_local_references(self):
        (self.root / "export.py").write_text("COLUMNS = []\n", encoding="utf-8")
        current = guide(entry="export.py::COLUMNS", evidence=["export.py:1"])
        cases = (
            ({"guide": [{**current, "target": "计划新增的入口"}]}, "target"),
            ({"guide": [{**current, "entry": "future.py::columns"}]}, "entry"),
            ({"guide": [{**current, "entry": "https://example.invalid/guide"}]}, "entry"),
            ({"guide": [{**current, "evidence": ["export.py:1", "export.py:99"]}]}, "evidence"),
            ({"guide": []}, "guide_limit"),
            ([], "JSON"),
        )
        for record, field in cases:
            with self.subTest(record=record):
                result = run_report(record, self.root, "--guide-only")
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertIn(field, result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_empty_guide_records_the_visible_limit(self):
        record = report_record(entries=[])
        self.invalid(record, "guide_limit")
        record["guide_limit"] = "只读到 docs/，调用方需在源码开放后核对。"
        self.assertIn(record["guide_limit"], self.report(record))

    def test_coverage_accounts_for_missing_returns_separately_from_exclusions(self):
        units = [{"check": "代码异味", "unit": name} for name in ("订单", "支付", "退款")]
        docs = {"check": "必要文档", "unit": "订单"}
        coverage = {
            "selected": [*units, docs],
            "results": [{**units[0], "status": "已查"}, {**units[1], "status": "部分已查", "reason": "回调未读"},
                        {**docs, "status": "未查", "reason": "未取得手册"}],
            "excluded": [{"check": "代码异味", "unit": "归档", "reason": "本轮只查现役入口"}],
        }
        record = report_record(mode="inspect")
        record["plan"]["coverage"] = coverage
        report = self.report(record)
        self.assertIn("选定 4 项检查范围，完整核对 1 项", report)
        self.assertIn("| 代码异味 | 退款 | 未查 | 未收到", report)
        self.assertIn("| 代码异味 | 支付 | 部分已查 | 回调未读 |", report)
        self.assertIn("| 必要文档 | 订单 | 未查 | 未取得手册 |", report)
        self.assertIn("| 代码异味 | 归档 | 范围外 |", report)
        for field, value in [
            ("selected", [docs, docs]), ("results", [coverage["results"][0]] * 2),
            ("results", [{**docs, "status": "未查"}]),
            ("results", [{"check": "目录结构", "unit": "退款", "status": "已查"}]),
            ("excluded", [{**docs, "reason": "范围冲突"}]),
        ]:
            with self.subTest(field=field, value=value):
                record["plan"]["coverage"] = {**coverage, field: value}
                self.invalid(record, "coverage")

    def test_all_returns_missing_can_report_the_gaps_without_a_fabricated_section(self):
        record = report_record(mode="inspect", entries=[])
        record.update(audit=[], guide_limit="尚未取得取证结果。")
        unit = {"check": "代码异味", "unit": "退款"}
        record["plan"]["coverage"] = {"selected": [unit], "results": []}
        report = self.report(record)
        self.assertIn("| 代码异味 | 退款 | 未查 | 未收到", report)
        self.assertNotIn("范围内未发现", report)
        record["plan"]["coverage"]["results"].append({**unit, "status": "已查"})
        self.invalid(record, "audit")

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
