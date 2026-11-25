import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1] / "skills/project-architect-skills"
SCRIPT = SKILL_DIR / "scripts/necessary_docs.py"


def local_tool():
    def entry(status, detail, source):
        return {"status": status, "detail": detail, "evidence": [source]}

    return {
        "scope": ["检索了仓库根和 docs/，阅读交接手册、入口和 Makefile"],
        "unread": [],
        "topics": {
            "purpose": entry("范围内未发现", "将订单导出为 CSV。", "docs/交接.md:3"),
            "requirements": entry("范围内未发现", "导出固定表头和全部订单。", "docs/交接.md:5"),
            "usage": entry("范围内未发现", "从根目录执行 make export。", "docs/交接.md:8"),
            "configuration": entry("不适用", "命令直接使用内置默认值。", "export.py:12"),
            "api": entry("不适用", "仅提供本地命令。", "docs/交接.md:3"),
            "architecture": entry("不适用", "一个脚本直接生成 CSV，无其他模块依赖。", "export.py:12"),
            "verification": entry("范围内未发现", "重放订单样例并核对表头。", "docs/样例.md:4"),
            "deployment": entry("不适用", "源码交付，仅在终端运行。", "docs/交接.md:3"),
        },
    }


def verification_gap():
    return {
        "status": "发现问题",
        "detail": "已介绍启动，未说明如何复核导出列名。",
        "evidence": ["docs/交接.md#本地开发", "Makefile:9"],
        "impact": "接手人改完列名后无法核对表头。",
        "placement": "docs/交接.md 的「本地开发」末尾补入 make check 的预期结果。",
    }


def run_report(record):
    return subprocess.run(
        [sys.executable, str(SCRIPT)], input=json.dumps(record, ensure_ascii=False),
        text=True, capture_output=True,
    )


class NecessaryDocsTests(unittest.TestCase):
    def report(self, record):
        result = run_report(record)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_manual_and_linked_example_cover_handoff_without_readme(self):
        report = self.report(local_tool())
        self.assertIn("**检查结果**　范围内未发现", report)
        self.assertIn("| 验证改动的方法 | 范围内未发现 | 重放订单样例并核对表头。 | docs/样例.md:4 |", report)
        self.assertIn("| 必要配置 | 不适用 | 命令直接使用内置默认值。 | export.py:12 |", report)
        self.assertNotIn("项目规模", report)
        self.assertNotIn("建议补写", report)

    def test_project_size_precheck_uses_the_larger_tier(self):
        cases = (
            ("0", "0", "小项目"),
            ("1", "50", "小项目"),
            ("2", "20", "中等项目"),
            ("1", "51", "中等项目"),
            ("5", "500", "中等项目"),
            ("6", "1", "大项目"),
            ("1", "501", "大项目"),
            ("-", "501", "大项目"),
            ("2", "-", "待确认"),
            ("-", "-", "待确认"),
        )
        for units, files, expected in cases:
            with self.subTest(units=units, files=files):
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), "--project-size", units, files],
                    text=True, capture_output=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), expected)

    def test_report_lists_project_size_and_focus_before_actual_scope(self):
        record = local_tool()
        record["project"] = {
            "units": 6, "files": 60,
            "evidence": ["workspace.yaml 列出六个应用"],
            "focus": "订单导出和共享 CSV 模块",
        }
        report = self.report(record)
        self.assertIn("**项目规模**　大项目（独立维护单元 6 个，自维护文件 60 个）", report)
        self.assertIn("**规模依据**　workspace.yaml 列出六个应用", report)
        self.assertLess(
            report.index("**本轮检查重点**　订单导出和共享 CSV 模块"),
            report.index("### 已查范围"),
        )

    def test_invalid_project_counts_do_not_produce_output(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--project-size", "-1", "20"],
            text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("非负整数", result.stderr)

        record = local_tool()
        record["project"] = {"units": True, "files": 20, "evidence": ["Makefile"], "focus": "导出"}
        result = run_report(record)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("units", result.stderr)

    def test_only_confirmed_gap_has_impact_and_placement(self):
        record = local_tool()
        gap = verification_gap()
        record["topics"]["verification"] = gap
        report = self.report(record)
        self.assertIn("**检查结果**　发现问题", report)
        self.assertEqual(report.count("| 发现问题 |"), 1)
        self.assertIn("docs/交接.md#本地开发、Makefile:9", report)
        self.assertIn(gap["impact"], report)
        self.assertIn(gap["placement"], report)
        self.assertNotIn("架构图", report)

    def test_report_distinguishes_confirmed_gap_kinds(self):
        cases = (
            ("missing", "缺少说明", "手册没有验证步骤。"),
            ("incomplete", "内容不完整", "测试小节只有模板提示和空表格。"),
            ("stale", "与实现不符", "手册中的测试命令已从 Makefile 移除。"),
        )
        for kind, label, detail in cases:
            with self.subTest(kind=kind):
                record = local_tool()
                record["topics"]["verification"] = {**verification_gap(), "gap_kind": kind, "detail": detail}
                report = self.report(record)
                self.assertIn(f"| 验证改动的方法 | 发现问题 | **{label}**　{detail}", report)

    def test_documented_example_renders_a_report(self):
        example = SKILL_DIR / "references/examples/necessary-docs-record.json"
        result = subprocess.run([sys.executable, str(SCRIPT), str(example)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("## 必要文档\n"))
        checklist, suggestions = result.stdout.split("### 建议补写\n")
        category_headings = [line for line in checklist.splitlines() if line.startswith("#### ")]
        self.assertEqual(category_headings, [
            "#### 产品文档", "#### 技术文档", "#### 架构文档", "#### 测试文档", "#### 部署文档",
        ])
        architecture, testing = checklist.split("#### 架构文档\n")[1].split("#### 测试文档\n")
        self.assertIn("| 模块职责与依赖 | 发现问题 | **缺少说明**", architecture)
        self.assertIn("| 验证改动的方法 | 发现问题 | **内容不完整**", testing)
        self.assertIn("#### 架构文档\n\n- **模块职责与依赖**", suggestions)
        self.assertIn("#### 测试文档\n\n- **验证改动的方法**", suggestions)
        self.assertEqual(suggestions.count("#### "), 2)

    def test_legacy_record_marks_new_checks_pending(self):
        record = local_tool()
        del record["topics"]["requirements"]
        del record["topics"]["architecture"]
        report = self.report(record)
        self.assertIn("**检查结果**　待确认", report)
        self.assertIn("| 项目用途 | 范围内未发现 |", report)
        self.assertIn("| 主要流程与业务规则 | 待确认 | 旧版记录未包含此项", report)
        self.assertIn("| 模块职责与依赖 | 待确认 | 旧版记录未包含此项", report)
        self.assertNotIn("建议补写", report)

    def test_unread_architecture_reference_preserves_confirmed_product_gap(self):
        record = local_tool()
        record["topics"]["requirements"] = {
            "status": "发现问题", "gap_kind": "missing", "detail": "手册缺少空订单的导出规则。",
            "evidence": ["docs/交接.md:5", "tests/test_export.py:18"], "impact": "无法确认空订单的预期结果。",
            "placement": "在 docs/交接.md 的「导出规则」补入空订单示例。",
        }
        record["topics"]["architecture"] = {
            "status": "发现问题", "gap_kind": "incomplete",
            "detail": "交接手册只有链接，正文未查到模块职责。",
            "evidence": ["docs/交接.md:14"],
            "impact": "无法判断订单读取模块的调用方。",
            "placement": "在 docs/交接.md 的「模块职责」补入调用关系。",
        }
        record["unread"] = [{
            "source": "docs/交接.md:14 链接的模块说明", "reason": "本轮无法访问",
            "topics": ["architecture"],
        }]
        report = self.report(record)
        self.assertIn("**检查结果**　发现问题", report)
        self.assertIn("**项目资料完整性**　待确认", report)
        self.assertIn("| 模块职责与依赖 | 待确认 |", report)
        self.assertIn("| 主要流程与业务规则 | 发现问题 | **缺少说明**", report)
        suggestions = report.split("### 建议补写\n")[1]
        self.assertIn("#### 产品文档\n\n- **主要流程与业务规则**", suggestions)
        self.assertNotIn("架构文档", suggestions)

    def test_unknown_gap_kind_does_not_produce_a_report(self):
        record = local_tool()
        record["topics"]["verification"] = {**verification_gap(), "gap_kind": "unknown"}
        result = run_report(record)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("verification.gap_kind", result.stderr)

    def test_unread_reference_only_affects_its_topic(self):
        record = local_tool()
        record["topics"]["verification"] = {**verification_gap(), "gap_kind": "incomplete"}
        record["topics"]["api"] = {
            "status": "发现问题", "detail": "开放了导出接口，手册中缺少调用示例。",
            "evidence": ["docs/交接.md:3", "api.py:7"], "impact": "无法发起第一次调用。",
            "placement": "docs/交接.md 的「集成」小节。",
        }
        record["unread"] = [{
            "source": "docs/交接.md:14 链接的验收手册", "reason": "本轮无法访问",
            "topics": ["verification"],
        }]
        report = self.report(record)
        self.assertIn("**检查结果**　发现问题", report)
        self.assertIn("**项目资料完整性**　待确认", report)
        self.assertIn("| 验证改动的方法 | 待确认 |", report)
        self.assertIn("| 启动或最小使用示例 | 范围内未发现 |", report)
        self.assertIn("本轮无法访问", report)
        self.assertNotIn("**内容不完整**", report)
        self.assertNotIn(verification_gap()["placement"], report)
        self.assertIn(record["topics"]["api"]["placement"], report)

    def test_partial_repository_cannot_prove_project_wide_absence(self):
        record = local_tool()
        record["project"] = {
            "units": None, "files": None,
            "evidence": ["仓库根不可见，无法盘点全项目"],
            "focus": "订单子目录的导出流程",
        }
        record["scope"] = ["只读到 packages/orders/ 及其本地手册"]
        record["unread"] = [{"source": "仓库根文档及其他手册", "reason": "超出可见目录"}]
        record["topics"]["verification"] = verification_gap()
        report = self.report(record)
        self.assertIn("**项目规模**　待确认", report)
        self.assertIn("**检查结果**　待确认", report)
        self.assertIn("| 验证改动的方法 | 待确认 |", report)
        self.assertIn("| 项目用途 | 范围内未发现 |", report)
        self.assertNotIn("建议补写", report)

    def test_conflicting_sources_are_pending_without_a_candidate(self):
        record = local_tool()
        record["topics"]["configuration"] = {
            "status": "待确认", "detail": "两个运行入口对路径的要求不同，当前交付入口待核实。",
            "evidence": ["docs/交接.md:6", "export.py:12", "preview.py:9"],
        }
        report = self.report(record)
        self.assertIn("**项目资料完整性**　待确认", report)
        self.assertIn("当前交付入口待核实", report)
        self.assertNotIn("建议补写", report)

    def test_new_evidence_clears_old_candidate(self):
        record = local_tool()
        verified = record["topics"]["verification"]
        record["topics"]["verification"] = verification_gap()
        self.assertIn("建议补写", self.report(record))
        record["topics"]["verification"] = verified
        self.assertNotIn("建议补写", self.report(record))

    def test_invalid_or_incomplete_evidence_never_produces_a_report(self):
        for field in ("evidence", "detail", "status", "impact", "placement"):
            with self.subTest(field=field):
                record = local_tool()
                item = verification_gap()
                del item[field]
                record["topics"]["verification"] = item
                result = run_report(record)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertIn(field, result.stderr)

    def test_only_necessary_document_topics_can_enter_this_check(self):
        for field in ("usage", "architecture", "diagram"):
            with self.subTest(field=field):
                record = local_tool()
                if field in record["topics"]:
                    del record["topics"][field]
                else:
                    record["topics"][field] = verification_gap()
                result = run_report(record)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertIn("topics", result.stderr)

    def test_utf8_file_input_matches_stdin_and_preserves_table_columns(self):
        record = local_tool()
        record["topics"]["usage"]["detail"] = "输入包含 A|B\n并检查两列。"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "交接记录.json"
            path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, self.report(record))
        self.assertIn(r"A\|B 并检查两列。", result.stdout)


if __name__ == "__main__":
    unittest.main()
