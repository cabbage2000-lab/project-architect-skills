import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "skills/project-architect-skills/scripts"
KINDS = ("long_method", "deep_nested_logic", "bumpy_road", "complex_conditional", "complex_method")


def run_script(script, *arguments, **kwargs):
    return subprocess.run([sys.executable, "-B", str(SCRIPTS / script), *arguments],
                          text=True, capture_output=True, **kwargs)


def report_record(*methods):
    found = {finding["kind"] for method in methods for finding in method["findings"]}
    return {
        "scope": ["核对订单导出的本地 Python 源码。"],
        "unread": [],
        "checks": {
            kind: {"status": "发现问题" if kind in found else "范围内未发现", "detail": "按项目口径核对。"}
            for kind in KINDS
        },
        "methods": list(methods),
    }


def method_record(*findings, symbol="export_orders", start=8):
    return {
        "path": "src/export.py", "symbol": symbol, "start": start, "end": start + 20,
        "impact": "修改订单导出需要复核筛选和计价。", "findings": list(findings),
    }


def finding(kind, *evidence):
    return {"kind": kind, "detail": "核对源码与实际路径。", "evidence": list(evidence) or ["src/export.py:8–28"]}


class PythonSmellSignalTests(unittest.TestCase):
    def signals(self, files, *options, compare=False):
        with tempfile.TemporaryDirectory() as directory:
            for name, source in files.items():
                (Path(directory) / name).write_text(source, encoding="utf-8")
            paths = () if compare else files
            result = run_script("python_smell_signals.py", *options, *paths, cwd=directory)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_five_signal_types_and_negative_controls(self):
        source = "def long_method():\n" + "".join(f"    step_{index} = {index}\n" for index in range(40))
        source += textwrap.dedent("""
            def one_deep_region(items):
                for item in items:
                    if item:
                        while item:
                            if item < 0:
                                break
                            item -= 1

            def two_regions(items):
                for item in items:
                    if item:
                        print(item)
                for item in items:
                    if item < 0:
                        print(-item)

            def can_export(active, owner, admin, in_region):
                if active and (owner or admin) and in_region:
                    return True
                return False
        """)
        source += "\ndef many_decisions(value):\n" + "".join(
            f"    if value == {index}:\n        return {index}\n" for index in range(8)
        )
        long_file = "\n".join(f"def short_{index}():\n    return {index}\n" for index in range(60))
        result = self.signals({"orders.py": source, "many_short_functions.py": long_file})
        by_symbol = {method["symbol"]: method for method in result["methods"]}
        self.assertEqual(set(by_symbol), {"long_method", "one_deep_region", "two_regions", "can_export", "many_decisions"})
        self.assertEqual(result["files"][1], {"path": "many_short_functions.py", "methods": 60})
        self.assertEqual(by_symbol["long_method"]["signals"], {"long_method": {"code_lines": 40}})
        deep = by_symbol["one_deep_region"]["signals"]
        self.assertEqual(set(deep), {"deep_nested_logic"})
        self.assertEqual([level["kind"] for level in deep["deep_nested_logic"]["path"]], ["For", "If", "While", "If"])
        regions = by_symbol["two_regions"]["signals"]["bumpy_road"]["groups"][0]
        self.assertEqual(len(regions), 2)
        self.assertLess(regions[0]["end"], regions[1]["start"])
        conditions = by_symbol["can_export"]["signals"]["complex_conditional"]
        self.assertEqual(conditions[0]["terms"], 4)
        self.assertEqual(conditions[0]["expression"], "active and (owner or admin) and in_region")
        decisions = by_symbol["many_decisions"]["signals"]["complex_method"]
        self.assertEqual(decisions["decision_count"], 8)
        self.assertEqual(len({point["line"] for point in decisions["decisions"]}), 8)

    def test_elif_and_mutually_exclusive_suites_do_not_create_a_second_region(self):
        source = textwrap.dedent("""
            def choose(value, rows):
                if value == 1:
                    for row in rows:
                        if row:
                            print(row)
                elif value == 2:
                    for row in rows:
                        if row < 0:
                            print(-row)
                elif value == 3:
                    return 3
                else:
                    return 4
        """)
        result = self.signals({"choices.py": source}, "--min-depth", "3")
        signals = result["methods"][0]["signals"]
        self.assertEqual(set(signals), {"deep_nested_logic"})
        self.assertEqual(signals["deep_nested_logic"]["depth"], 3)

    def test_nested_functions_own_their_code_and_branches(self):
        source = textwrap.dedent('''
            class Exporter:
                def outer(self):
                    """Prepare the order export."""
                    # The callback is measured independently.
                    def inner(value):
                        if value:
                            if value > 0:
                                return value
                        return 0
                    return inner(1)
        ''')
        result = self.signals({"orders.py": source}, "--min-lines", "3", "--min-depth", "2")
        self.assertEqual(result["files"][0]["methods"], 2)
        self.assertEqual([method["symbol"] for method in result["methods"]], ["Exporter.outer.inner"])
        signals = result["methods"][0]["signals"]
        self.assertEqual(signals["long_method"]["code_lines"], 4)
        self.assertEqual(signals["deep_nested_logic"]["depth"], 2)

    def test_invalid_file_is_unread_while_valid_file_is_measured(self):
        result = self.signals({"broken.py": "def broken(:\n", "valid.py": "def valid():\n    return 1\n"})
        self.assertEqual(result["files"], [{"path": "valid.py", "methods": 1}])
        self.assertEqual(result["unread"][0]["source"], "broken.py")
        self.assertTrue(result["unread"][0]["reason"])

    def test_compare_uses_snapshot_and_reports_both_directions_without_line_noise(self):
        before = textwrap.dedent("""\
            def export(a, b, c, d, e):
                if a and b and c and d:
                    return 1
                return 0

            def legacy(a, b, c, d):
                return 1 if a and b and c and d else 0

            def unchanged(a, b, c, d):
                return 1 if a and b and c and d else 0
        """)
        after = textwrap.dedent("""\
            # The snapshot may already include edits made by the maintainer.
            def export(a, b, c, d, e):
                return 1 if a and b and c and d and e else 0

            def added(a, b, c, d):
                return 1 if a and b and c and d else 0

            def unchanged(a, b, c, d):
                return 1 if a and b and c and d else 0
        """)
        result = self.signals({"snapshot.py": before, "orders.py": after},
                              "--min-lines", "2", "--compare", "snapshot.py", "orders.py", compare=True)
        diff = result["comparisons"][0]
        methods = {method["symbol"]: method for method in diff["changes"]}
        self.assertEqual(set(methods), {"export", "legacy", "added"})
        self.assertEqual(methods["export"]["before_lines"], [1, 4])
        self.assertEqual(methods["export"]["after_lines"], [2, 3])
        self.assertEqual(methods["export"]["signals"], [
            {"kind": "complex_conditional", "status": "increased",
             "before": {"conditions": 1, "max_terms": 4}, "after": {"conditions": 1, "max_terms": 5}},
            {"kind": "long_method", "status": "removed", "before": {"code_lines": 3}, "after": None},
        ])
        self.assertEqual(methods["legacy"]["signals"][0]["status"], "removed")
        self.assertEqual(methods["added"]["signals"][0]["status"], "added")

    def test_compare_distinguishes_explicit_additions_unread_files_and_ambiguous_symbols(self):
        complex_source = "def f(a, b, c, d):\n    return 1 if a and b and c and d else 0\n"
        result = self.signals(
            {"valid.py": complex_source, "broken.py": "def f(:\n", "duplicates.py": complex_source * 2},
            "--compare", "-", "valid.py", "--compare", "valid.py", "-",
            "--compare", "broken.py", "valid.py", "--compare", "duplicates.py", "valid.py", compare=True,
        )
        added, removed, broken, duplicates = result["comparisons"]
        self.assertIsNone(added["changes"][0]["before_lines"])
        self.assertIsNone(removed["changes"][0]["after_lines"])
        self.assertEqual(broken["unread"][0]["side"], "before")
        self.assertEqual(broken["changes"], [])
        self.assertEqual(duplicates["ambiguous"], ["f"])
        self.assertEqual(duplicates["changes"], [])

    @unittest.skipUnless(sys.version_info >= (3, 10), "模式匹配需要 Python 3.10")
    def test_guarded_match_counts_decisions_without_counting_the_fallback(self):
        source = textwrap.dedent("""
            def choose(value, 启用, owner, admin, local):
                match value:
                    case 1 | 2:
                        return "known"
                    case _ if 启用 and (owner or admin) and local:
                        return "authorized"
                    case _ as fallback:
                        return fallback
        """)
        result = self.signals({"choices.py": source}, "--min-decisions", "1")
        signals = result["methods"][0]["signals"]
        self.assertEqual(signals["complex_method"]["decision_count"], 2)
        self.assertEqual(signals["complex_conditional"][0]["expression"], "启用 and (owner or admin) and local")


class CodeSmellReportTests(unittest.TestCase):
    def report(self, record):
        result = run_script("code_smells.py", input=json.dumps(record, ensure_ascii=False))
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def packet(self, record):
        result = run_script("code_smells.py", "--json", input=json.dumps(record))
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_focused_drift_flows_through_preview_and_report_by_unit(self):
        orders = {"check": "architecture_drift", "unit": "订单"}
        refunds = {**orders, "unit": "退款"}
        entry = {"kind": orders["check"], "title": "订单直接访问存储", "status": "发现问题",
                 "detail": "订单入口绕过仓储接口。", "impact": "更换存储需修改业务层。",
                 "evidence": ["docs/layers.md:6", "src/order.py:19"]}
        record = {"selected": [orders], "scope": ["订单业务入口"], "unread": [], "modules": [entry]}
        packet = self.packet(record)
        self.assertEqual(packet["results"], [{**orders, "status": "已查", "verdict": "未通过"}])
        self.assertNotIn("### 方法级检查", packet["markdown"])
        for source in entry["evidence"]:
            self.assertIn(source, packet["markdown"])
        plan = {"mode": "inspect", "candidates": [],
                "coverage": {"selected": [orders, refunds], "results": packet["results"]}}
        preview = run_script("governance_plan.py", "--preview", "--json", input=json.dumps(plan))
        self.assertEqual(preview.returncode, 0, preview.stderr)
        preview = json.loads(preview.stdout)
        final = run_script("governance_report.py", input=json.dumps({
            "audit": [packet["markdown"]], "plan": preview["plan"], "reviews": [],
            "guide": [], "guide_limit": "退款模块尚待核对。",
        }))
        self.assertEqual(final.returncode, 0, final.stderr)
        for output in (preview["markdown"], final.stdout):
            self.assertIn("| architecture_drift | 退款 | 未查 |", output)
            self.assertIn("| architecture_drift | 订单 | 已查 |", output)

    def test_unrelated_checks_cannot_answer_a_requested_diagnosis(self):
        record = report_record()
        record["selected"] = [{"check": "architecture_drift", "unit": "订单"}]
        packet = self.packet(record)
        self.assertEqual(packet["results"][0]["status"], "未查")
        self.assertIn("**检查结果**　未查", packet["markdown"])
        self.assertNotIn("范围内未发现", packet["markdown"])
        record["modules"] = [{"kind": "architecture_drift", "title": "存储依赖", "status": "待确认",
                              "detail": "尚未取得分层约定。", "evidence": ["orders.py:3"]}]
        packet = self.packet(record)
        self.assertEqual(packet["results"][0]["status"], "部分已查")
        self.assertIn("分层约定", packet["results"][0]["reason"])
        self.assertIn("**检查结果**　待确认", packet["markdown"])
        record["modules"][0].update(status="范围内未发现", detail="可见入口符合约定。")
        record["unread"] = [{"source": "另一个订单入口", "reason": "目录不可见"}]
        packet = self.packet(record)
        self.assertEqual(packet["results"][0]["status"], "部分已查")
        self.assertIn("另一个订单入口", packet["results"][0]["reason"])

    def test_selected_method_and_missing_module_keep_the_confirmed_finding(self):
        record = report_record(method_record(finding("long_method"), finding("complex_method")))
        record["selected"] = [{"check": kind, "unit": "导出"} for kind in ("long_method", "srp")]
        packet = self.packet(record)
        self.assertEqual([row["status"] for row in packet["results"]], ["已查", "未查"])
        self.assertIn("**检查结果**　发现问题", packet["markdown"])
        self.assertIn("export_orders", packet["markdown"])
        self.assertNotIn("复杂方法", packet["markdown"])

    def test_invalid_focused_selection_and_unsubstantiated_drift_emit_no_report(self):
        item = {"check": "architecture_drift", "unit": "订单"}
        for selected in ([], [item, item], [dict(item, check="typo")], [item, dict(item, unit="退款")]):
            with self.subTest(selected=selected):
                result = run_script("code_smells.py", "--json", input=json.dumps(dict(report_record(), selected=selected)))
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertIn("selected", result.stderr)
        record = dict(report_record(), selected=[item], modules=[{
            "kind": "architecture_drift", "title": "依赖方向", "status": "发现问题", "detail": "跨层调用。",
            "impact": "牵动上层。", "evidence": ["src/order.py:19"],
        }])
        result = run_script("code_smells.py", "--json", input=json.dumps(record))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")

    def test_same_function_retains_all_labels_with_one_candidate(self):
        record = report_record(method_record(finding("long_method"), finding("complex_method")))
        report = self.report(record)
        self.assertIn("| 长方法 | 发现问题 |", report)
        self.assertIn("| 复杂方法 | 发现问题 |", report)
        self.assertEqual(report.count("- **src/export.py:8–28 `export_orders`**"), 1)
        self.assertIn("- **长方法**", report)
        self.assertIn("- **复杂方法**", report)

    def test_partial_scope_preserves_all_confirmed_candidates(self):
        record = report_record(*(
            method_record(finding("deep_nested_logic"), symbol=f"method_{index}", start=index * 30)
            for index in range(1, 5)
        ))
        record["unread"] = [{"source": "src/billing.py", "reason": "只读到导出模块"}]
        record["checks"]["long_method"]["status"] = "待确认"
        report = self.report(record)
        self.assertIn("**检查结果**　发现问题", report)
        self.assertIn("| 长方法 | 待确认 |", report)
        self.assertIn("src/billing.py（只读到导出模块）", report)
        self.assertEqual(report.count("- **src/export.py:"), 4)

    def test_module_diagnoses_distinguish_independent_business_rules(self):
        record = report_record()
        record["modules"] = [
            {"kind": "architecture_drift", "title": "订单层", "status": "发现问题", "detail": "订单层直接调用存储。",
             "evidence": ["docs/layers.md:6", "src/order.py:19"], "impact": "切换存储需改业务层。"},
            {"kind": "mixed_responsibilities", "title": "订单导出", "status": "发现问题", "detail": "取数和列格式各自演进。",
             "evidence": ["src/export.py:8", "src/export.py:32"], "impact": "排版改动需阅读存储代码。"},
            {"kind": "duplicate_logic", "title": "两处价格换算", "status": "发现问题", "detail": "同一币种规则重复。",
             "evidence": ["src/billing.py:18", "src/report.py:41"], "impact": "调整货币舍入时易漏改。"},
            {"kind": "duplicate_logic", "title": "历史与当前订单", "status": "范围内未发现", "detail": "两者适用不同版本的计价规则。",
             "evidence": ["src/legacy.py:4", "src/current.py:7"], "suggestion": "合并两个实现。"},
        ]
        report = self.report(record)
        self.assertIn("架构漂移 · 订单层", report)
        self.assertIn("职责混杂 · 订单导出", report)
        self.assertIn("逻辑重复 · 两处价格换算", report)
        self.assertIn("历史与当前订单**　范围内未发现", report)
        self.assertNotIn("合并两个实现", report)

    def test_substitution_finding_preserves_both_contract_and_implementation_evidence(self):
        record = report_record()
        record["modules"] = [{
            "kind": "lsp", "title": "只读存储的写操作", "status": "发现问题",
            "detail": "父类允许保存空值，子类拒绝相同输入。",
            "evidence": ["src/store.py:8", "src/cache.py:19"],
            "impact": "同一调用方更换实现后会收到异常。",
            "suggestion": "分别使用两个实现重放空值样例。",
        }]
        report = self.report(record)
        for expected in ("LSP", "src/store.py:8", "src/cache.py:19", "重放空值样例"):
            self.assertIn(expected, report)
        record["modules"][0]["evidence"].pop()
        result = run_script("code_smells.py", input=json.dumps(record))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")

    def test_invalid_findings_cannot_emit_a_partial_report(self):
        one_region = report_record(method_record(finding("bumpy_road")))
        method = method_record(finding("complex_method"))
        duplicate = report_record(method, method)
        unsupported = report_record()
        unsupported["checks"]["long_method"]["status"] = "发现问题"
        for record, error in ((one_region, "至少两处"), (duplicate, "须合并"), (unsupported, "证据一致")):
            with self.subTest(error=error):
                result = run_script("code_smells.py", input=json.dumps(record, ensure_ascii=False))
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertIn(error, result.stderr)
