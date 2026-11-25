import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "skills/project-architect-skills/scripts/architecture_diagrams.py"


def architecture_record():
    return {
        "scope": ["通查 README、docs/ 与 src/ 的订单导出入口。"],
        "need": {"status": "需要", "detail": "维护导出需追踪订单读取。", "evidence": ["src/export.py:8"]},
        "unread": [],
        "diagrams": [],
    }


def implementation_diagram(*results):
    return {
        "source": "README.md:9",
        "kind": "implementation",
        "checks": [
            {
                "claim": claim,
                "result": result,
                "detail": detail,
                "evidence": ["src/export.py:8"],
            }
            for claim, result, detail in results
        ],
    }


PRODUCT_DIAGRAM = {
    "source": "docs/flow.drawio#下载流程",
    "kind": "product",
    "detail": "图中列出了选择订单与下载操作。",
}
UNREAD_REFERENCE = {
    "source": "README.md:6 的实现视图 https://docs.example/architecture",
    "reason": "链接无法访问",
}
REPAIR = {
    "impact": "接手者无法判断导出调用哪个订单读取模块。",
    "placement": "README.md 的架构说明",
    "changes": ["画出 export → orders，依据 src/export.py:8。"],
}


def run_report(record, *args):
    return subprocess.run(
        [sys.executable, "-B", str(SCRIPT), *args],
        input=json.dumps(record, ensure_ascii=False),
        capture_output=True,
        text=True,
    )


class ArchitectureDiagramTests(unittest.TestCase):
    def report(self, record):
        result = run_report(record)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("## 架构图\n"))
        return result.stdout

    def test_documented_implementation_relation_covers_scope(self):
        record = architecture_record()
        record["diagrams"] = [implementation_diagram(("export → orders", "一致", "导出入口调用订单读取。"))]
        record["project"] = {
            "units": 1, "files": 2,
            "evidence": ["一个导出工具，两个自有脚本。"], "focus": "导出依赖",
        }
        report = self.report(record)
        self.assertIn("**项目规模**　小项目", report)
        self.assertIn("**检查结果**　范围内未发现", report)
        self.assertIn("| README.md:9 | 实现视图 | export → orders | 一致 |", report)
        self.assertNotIn("建议修订", report)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "架构图记录.json"
            path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            from_file = run_report({}, str(path))
        self.assertEqual(from_file.returncode, 0, from_file.stderr)
        self.assertEqual(from_file.stdout, report)

    def test_distinguishes_missing_diagram_from_product_only(self):
        cases = (
            ([], "已查范围内缺少实现视图"),
            ([PRODUCT_DIAGRAM], "已查范围仅有产品功能图，缺少实现视图"),
        )
        for diagrams, conclusion in cases:
            with self.subTest(diagrams=diagrams):
                report = self.report({**architecture_record(), "diagrams": diagrams, "repair": REPAIR})
                self.assertIn(f"**检查结果**　发现问题。{conclusion}", report)
                self.assertEqual(report.count("### 建议修订"), 1)
                self.assertIn(REPAIR["changes"][0], report)

    def test_unread_reference_prevents_unfounded_missing_diagram(self):
        for diagrams in ([], [PRODUCT_DIAGRAM]):
            with self.subTest(diagrams=diagrams):
                record = {**architecture_record(), "diagrams": diagrams, "unread": [UNREAD_REFERENCE]}
                report = self.report(record)
                self.assertIn("**检查结果**　待确认", report)
                self.assertIn(UNREAD_REFERENCE["source"], report)
                self.assertIn(UNREAD_REFERENCE["reason"], report)
                self.assertNotIn("建议修订", report)

    def test_proven_stale_relations_survive_unread_and_share_one_candidate(self):
        record = architecture_record()
        record["unread"] = [UNREAD_REFERENCE]
        record["diagrams"] = [implementation_diagram(
            ("export → cache", "与实现不符", "实际调用 orders。"),
            ("orders → export", "与实现不符", "调用方向是 export → orders。"),
        )]
        record["repair"] = REPAIR
        report = self.report(record)
        self.assertIn("**检查结果**　发现问题", report)
        self.assertIn("**资料完整性**　待确认", report)
        self.assertIn("export → cache | 与实现不符", report)
        self.assertIn("orders → export | 与实现不符", report)
        self.assertEqual(report.count("### 建议修订"), 1)

    def test_missing_key_relation_and_unresolved_relation_have_distinct_results(self):
        for result, status in (("缺少关键关系", "发现问题"), ("待确认", "待确认")):
            with self.subTest(result=result):
                record = architecture_record()
                record["diagrams"] = [implementation_diagram(("export → orders", result, "对照导出入口。"))]
                record["repair"] = REPAIR
                report = self.report(record)
                self.assertIn(f"**检查结果**　{status}", report)
                self.assertEqual("### 建议修订" in report, status == "发现问题")

    def test_single_entry_without_module_boundary_is_not_applicable(self):
        record = architecture_record()
        record["need"] = {"status": "不适用", "detail": "单一入口直接打印结果。", "evidence": ["hello.py:1"]}
        report = self.report(record)
        self.assertIn("**检查结果**　不适用", report)
        self.assertIn("hello.py:1", report)
        self.assertNotIn("建议修订", report)

    def test_invalid_record_never_outputs_a_partial_report(self):
        base = architecture_record()
        cases = (
            ({**base, "need": {"status": "未知"}}, "need.status"),
            ({**base, "diagrams": [{"source": "README.md:9", "kind": "implementation"}]}, "diagrams.checks"),
            ({**base, "unread": [{"source": "README.md:6"}]}, "unread.reason"),
            (base, "repair"),
            ({**base, "repair": {**REPAIR, "changes": []}}, "repair.changes"),
        )
        for record, field in cases:
            with self.subTest(field=field):
                result = run_report(record)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertIn(field, result.stderr)
