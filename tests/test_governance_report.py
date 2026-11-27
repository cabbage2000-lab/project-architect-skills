import json
import re
import shlex
import shutil
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

    def summary_record(self, *outcomes):
        record = report_record(mode="inspect")
        checks = ("必要文档", "架构图", "目录结构", "代码异味", "行为验证")
        rows = [{"check": name, "unit": "导出工具"} for name in checks[:len(outcomes)]]
        record["plan"]["coverage"] = {
            "selected": rows, "results": [{**row, "status": "已查"} for row in rows],
        }
        record["summary"] = [
            {"check": row["check"], "status": status, "detail": f"{row['check']}的核对结果。"}
            for row, status in zip(rows, outcomes)
        ]
        return record

    def test_summary_only_shows_check_table_and_conclusion_without_writing(self):
        record = self.summary_record(*(["通过"] * 5))
        before = {p: p.read_bytes() for p in self.root.iterdir()}
        report = self.report(record, "--summary")
        self.assertEqual(report.count("| ✅ 通过 |"), 5)
        self.assertTrue(report.startswith("| 质检项 | 是否通过 | 说明 |\n"))
        self.assertEqual(len(report.strip().splitlines()), 9)
        self.assertIn("暂无需要修复的问题", report)
        self.assertNotIn("治理计划", report)
        self.assertNotIn("维护导读", report)
        self.assertEqual({p: p.read_bytes() for p in self.root.iterdir()}, before)
        full = self.report(record)
        self.assertIn(report.strip(), full)
        self.assertIn("## 维护导读", full)

    def test_summary_preserves_failures_uncertainty_and_not_applicable(self):
        record = self.summary_record("未通过", "待确认", "未查", "不适用", "通过")
        record["summary"][0]["detail"] = "export.py 中的 A | B 两处表头需统一。"
        report = self.report(record, "--summary")
        for status in ("❌ 未通过", "待确认", "未查", "不适用", "✅ 通过"):
            self.assertIn(f"| {status} |", report)
        self.assertIn(r"A \| B", report)
        self.assertIn("1 项未通过", report)
        self.assertIn("2 项待确认或未查", report)
        self.assertNotIn("暂无需要修复", report)
        pending = self.report(self.summary_record("通过", "待确认"), "--summary")
        self.assertIn("暂不能判定全部通过", pending)
        excluded = self.report(self.summary_record("不适用"), "--summary")
        self.assertIn("质检项均不适用", excluded)

    def test_specialty_summary_displays_the_name_and_preserves_dispatch_ids(self):
        record = self.summary_record("通过", "待确认")
        coverage = record["plan"]["coverage"]
        for rows in (coverage["selected"], coverage["results"], record["summary"]):
            for row, key in zip(rows, ("cross_entry", "generated_artifact")):
                row["check"] = key
        report = self.report(record, "--summary")
        self.assertIn("| 跨入口业务规则一致性 | ✅ 通过 |", report)
        self.assertIn("| 修改源与生成产物同步 | 待确认 |", report)
        self.assertIn("| cross_entry |", self.report(record))

    def test_summary_requires_explicit_complete_verdicts(self):
        for change in ("missing", "empty", "duplicate", "omitted", "unknown", "coverage_only"):
            with self.subTest(change=change):
                record = self.summary_record("通过", "通过")
                if change == "missing":
                    del record["summary"]
                elif change == "empty":
                    record["summary"] = []
                elif change == "duplicate":
                    record["summary"][1] = record["summary"][0].copy()
                elif change == "omitted":
                    record["summary"].pop()
                elif change == "unknown":
                    record["summary"][0]["check"] = "未选中的检查"
                else:
                    record["summary"][0]["status"] = "已查"
                result = run_report(record, self.root, "--summary")
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertIn("summary", result.stderr)

    def test_summary_cannot_pass_incomplete_or_unreturned_modules(self):
        for state in ("部分已查", "未查", None):
            for verdict in ("通过", "不适用"):
                with self.subTest(state=state, verdict=verdict):
                    record = self.summary_record(verdict)
                    coverage = record["plan"]["coverage"]
                    second = {"check": "必要文档", "unit": "另一个入口"}
                    coverage["selected"].append(second)
                    if state:
                        coverage["results"].append({**second, "status": state, "reason": "缺少资料"})
                    result = run_report(record, self.root, "--summary")
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(result.stdout, "")
                    self.assertIn("summary", result.stderr)
                    record["summary"][0]["status"] = "待确认"
                    self.assertIn("暂不能判定全部通过", self.report(record, "--summary"))

    def test_summary_preview_needs_no_execution_reviews_or_guide(self):
        record = self.summary_record("未通过")
        record["plan"].update(mode="execute", candidates=[candidate("export.py", "修正导出表头")])
        for field in ("audit", "reviews", "guide"):
            del record[field]
        self.assertIn("1 项未通过", self.report(record, "--summary"))
        self.assertFalse((self.root / REPORT).exists())

    def test_expert_verdict_reaches_both_reports_through_the_plan(self):
        example = SCRIPT.parents[1] / "references/examples/necessary-docs-record.json"
        source = json.loads(example.read_text(encoding="utf-8"))
        docs = {"check": "必要文档", "unit": "订单"}
        source["selected"] = [docs]

        def packet(script, record, *options):
            output = subprocess.check_output(
                [sys.executable, "-B", str(SCRIPT.with_name(script)), *options, "--json"],
                input=json.dumps(record), text=True, cwd=self.root,
            )
            return json.loads(output)

        expert = packet("necessary_docs.py", source)
        self.assertIn("**检查结果**　发现问题", expert["markdown"])
        coverage = {"selected": [docs, {**docs, "unit": "退款"}], "results": expert["results"]}
        plan = packet("governance_plan.py", {"mode": "inspect", "candidates": [], "coverage": coverage}, "--preview")
        record = report_record()
        record.update(plan=plan["plan"], audit=[expert["markdown"]],
                      summary=[{"check": "必要文档", "detail": "缺少验证说明。"}])
        for options in (("--summary",), ()):
            text = self.report(record, *options)
            self.assertIn("❌ 未通过", text)
            self.assertIn("退款（未查）", text)
        record["summary"][0]["status"] = "通过"
        self.invalid(record, "与专家回传不符")
        result = run_report(record, self.root, "--summary")
        self.assertEqual((result.returncode, result.stdout), (2, ""))

    def test_verdict_aggregation_preserves_applicability_and_missing_modules(self):
        for verdicts, expected in [
            (["不适用", "不适用"], "不适用"), (["通过", "不适用"], "✅ 通过"),
            (["通过", "待确认"], "待确认"), (["通过", "未查"], "待确认"),
            (["未查", "未查"], "未查"), (["未通过", "待确认"], "❌ 未通过"),
        ]:
            with self.subTest(verdicts=verdicts):
                record = self.summary_record("通过")
                del record["summary"][0]["status"]
                selected = [{"check": "必要文档", "unit": unit} for unit in ("订单", "退款")]
                results = []
                for unit, verdict in zip(selected, verdicts):
                    if verdict == "未查":
                        continue
                    status = "部分已查" if verdict == "待确认" else "已查"
                    results.append({**unit, "status": status, "verdict": verdict, "reason": "手册未读"})
                record["plan"]["coverage"] = {"selected": selected, "results": results}
                self.assertIn(f"| 必要文档 | {expected} |", self.report(record, "--summary"))

    def test_known_failure_in_legacy_module_survives_new_successful_return(self):
        record = self.summary_record("未通过")
        coverage = record["plan"]["coverage"]
        second = {"check": "必要文档", "unit": "退款"}
        coverage["selected"].append(second)
        coverage["results"].append({**second, "status": "已查", "verdict": "通过"})
        self.assertIn("❌ 未通过", self.report(record, "--summary"))
        del record["summary"][0]["status"]
        self.assertIn("| 待确认 |", self.report(record, "--summary"))

    def test_summary_cannot_publish_or_bypass_full_report_publication_checks(self):
        record = self.summary_record("通过")
        record["guide"][0]["entry"] = "gone.py::download"
        self.assertIn("暂无需要修复", self.report(record, "--summary"))
        result = run_report(record, self.root, "--write")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("guide[0].entry", result.stderr)
        for flags in (("--summary", "--write"), ("--summary", "--guide-only")):
            result = run_report(self.summary_record("通过"), self.root, *flags)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
        self.assertFalse((self.root / REPORT).exists())

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

    @unittest.skipUnless(shutil.which("sh"), "需要 sh 重放多行导读命令")
    def test_multiline_command_copied_from_each_guide_detects_wrong_output(self):
        python = shlex.quote(sys.executable)
        command = f"{python} -B export.py\n{python} -B - <<'PY'\nfrom export import download_orders\n" \
                  "if download_orders() != 'Customer':\n    raise SystemExit(1)\n# ~~~~\nPY"
        record = report_record(entries=[guide(checks=[command.replace("\n", "\r\n")])])
        for options in (("--guide-only",), ()):
            with self.subTest(options=options):
                path = self.root / "export.py"
                path.write_text("def download_orders(): return 'Customer'\n")
                report = self.report(record, *options)
                match = re.search(r"^(~{3,})\n(.*?)\n\1$", report, re.MULTILINE | re.DOTALL)
                self.assertIsNotNone(match)
                copied = match.group(2)
                self.assertEqual(copied, command)
                self.assertEqual(subprocess.run(["sh", "-c", copied], cwd=self.root).returncode, 0)
                path.write_text("def download_orders(): return 'Other'\n")
                self.assertEqual(subprocess.run(["sh", "-c", copied], cwd=self.root).returncode, 1)

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

    def test_independent_replay_is_visible_in_guide_summary_and_full_report(self):
        record = self.summary_record("通过")
        replay = {
            "guide_task": guide()["task"], "task": "调整客户列", "reviewer": "新上下文工程文档专家",
            "independent": True, "status": "通过", "entry": "export.py::download_orders",
            "callers": "orders_page.py 的下载读取表头", "operation": "从订单页导出一份空订单",
            "expected": "表头恰为 Customer", "observed": "得到 Customer，错误列名会使表头断言失败",
            "evidence": ["orders_page.py:3", "export.py:2"],
        }
        record["guide_replay"] = replay
        for mode in (("--guide-only",), ("--summary",), ()):
            result = self.report(record, *mode)
            self.assertIn("维护导读独立复验", result)
            self.assertIn(replay["observed"], result)
        for key, bad_value in (("independent", False), ("independent", 1), ("reviewer", ""),
                               ("guide_task", "另一条导读"), ("entry", "gone.py"), ("callers", ""),
                               ("evidence", ["orders_page.py:300"]), ("expected", "")):
            with self.subTest(field=key):
                self.invalid({**record, "guide_replay": {**replay, key: bad_value}}, f"guide_replay.{key}")

    def test_failed_or_blocked_handover_identifies_the_step_and_supersedes_clean_summary(self):
        record = self.summary_record("通过")
        record["guide_replay"] = {
            "guide_task": guide()["task"], "task": "调整列名", "status": "未通过", "independent": True,
            "reviewer": "接手者", "operation": "按导读运行下载验证", "observed": "只检查文件存在",
            "reason": "无法分辨表头是否正确", "evidence": ["orders_page.py:3"],
        }
        result = self.report(record, "--summary")
        self.assertIn("维护导读独立复验未通过", result)
        self.assertNotIn("暂无需要修复", result)
        self.assertIn("无法分辨表头", self.report(record))
        record.update(guide=[], guide_limit="当前只有仓库索引。", guide_replay={
            "task": "修改导出", "status": "待确认", "reason": "还没有独立复验上下文。",
        })
        self.assertIn("待确认", self.report(record, "--guide-only"))
        result = self.report(record, "--summary")
        self.assertIn("维护导读独立复验待确认", result)
        self.assertNotIn("无需修复", result)

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

    def test_completed_editor_saves_at_publication_and_restoration_are_preserved(self):
        # At each actual file replacement, let an independent save finish first.
        runner = """
import os
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import governance_report
import report_publication

edits = iter(sys.argv[2:])
replace = report_publication.replace_with_backup
def finish_save(source, target, backup):
    edit = next(edits, None)
    if edit == 'append':
        with target.open('ab') as handle:
            handle.write(b'first manual note')
    elif edit:
        saved = target.with_name('editor.tmp')
        saved.write_bytes(edit.encode())
        os.replace(saved, target)
    return replace(source, target, backup)
report_publication.replace_with_backup = finish_save
sys.argv = ['governance_report.py', '--write']
governance_report.main()
"""
        updated = report_record(entries=[guide(task="调整下载入口")])
        fallback = self.report(updated)
        target = self.root / REPORT
        for edits in (["append"], ["editor replacement"], ["append", "second manual version"]):
            with self.subTest(edits=edits):
                self.report(report_record(), "--write")
                before = target.read_bytes()
                result = subprocess.run([sys.executable, "-B", "-c", runner, str(SCRIPT.parent), *edits],
                                        cwd=self.root, input=json.dumps(updated), capture_output=True, text=True)
                self.assertEqual((result.returncode, result.stdout), (0, fallback), result.stderr)
                expected = before + b"first manual note" if edits[0] == "append" else edits[0].encode()
                self.assertEqual(target.read_bytes(), expected)
                saved = [p for p in target.parent.rglob("*") if p.is_file() and p != target]
                self.assertEqual([p.read_bytes() for p in saved], [e.encode() for e in edits[1:]])
                if saved:
                    self.assertIn(str(saved[0].relative_to(self.root)), result.stderr)
                target.unlink()

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
