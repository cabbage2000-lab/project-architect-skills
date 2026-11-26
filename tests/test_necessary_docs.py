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
            "agent_instructions": [entry("不适用", "已查开发流程未见使用 AI 编程工具。", "docs/交接.md:8")],
            "architecture": entry("不适用", "一个脚本直接生成 CSV，无其他模块依赖。", "export.py:12"),
            "verification": entry("范围内未发现", "重放订单样例并核对表头。", "docs/样例.md:4"),
            "deployment": entry("不适用", "源码交付，仅在终端运行。", "docs/交接.md:3"),
            "redundancy": [{
                "status": "范围内未发现", "detail": "交接手册只链接验收样例，预期表头集中在样例中。",
                "evidence": ["docs/交接.md:10", "docs/样例.md:4"],
            }],
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


def repeated_configuration():
    return {
        "status": "发现问题", "detail": "两处各自维护了同一版本的配置表，部署手册是配置入口。",
        "evidence": ["docs/部署.md#配置", "README.md#运行参数"],
        "impact": "默认端口变化时需要更新两张表。",
        "placement": "将 README 的配置表改为正文链接，保留本地端口占用时的处理步骤。",
    }


def run_report(record, *args, cwd=None):
    return subprocess.run(
        [sys.executable, "-B", str(SCRIPT), *args], input=json.dumps(record, ensure_ascii=False),
        text=True, capture_output=True, cwd=cwd,
    )


class NecessaryDocsTests(unittest.TestCase):
    def report(self, record):
        result = run_report(record)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_focused_document_only_renders_the_requested_theme(self):
        item = {"check": "verification", "unit": "订单导出"}
        record = {"selected": [item], "scope": ["README.md 和导出样例"], "unread": [],
                  "topics": {"verification": verification_gap()}}
        result = run_report(record, "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads(result.stdout)
        self.assertEqual(packet["results"], [{**item, "status": "已查"}])
        self.assertIn(verification_gap()["placement"], packet["markdown"])
        self.assertNotIn("#### 技术文档", packet["markdown"])
        record["unread"] = [{"source": "测试手册", "reason": "无法读取", "topics": ["verification"]}]
        result = run_report(record, "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads(result.stdout)
        self.assertIn("| 验证改动的方法 | 待确认 |", packet["markdown"])
        self.assertIn("测试手册", packet["results"][0]["reason"])
        self.assertNotIn("### 建议补写", packet["markdown"])

    def test_missing_document_topic_is_unchecked_even_when_another_is_answered(self):
        record = local_tool()
        record["selected"] = [{"check": kind, "unit": "订单"} for kind in ("verification", "usage")]
        del record["topics"]["verification"]
        report = self.report(record)
        self.assertIn("| verification | 订单 | 未查 |", report)
        self.assertIn("| 启动或最小使用示例 | 范围内未发现 |", report)
        self.assertIn("**检查结果**　部分已查", report)
        self.assertNotIn("### 文档冗余", report)

    def test_manual_and_linked_example_cover_handoff_without_readme(self):
        report = self.report(local_tool())
        self.assertIn("**检查结果**　范围内未发现", report)
        self.assertIn("| 验证改动的方法 | 范围内未发现 | 重放订单样例并核对表头。 | docs/样例.md:4 |", report)
        self.assertIn("| 必要配置 | 不适用 | 命令直接使用内置默认值。 | export.py:12 |", report)
        self.assertIn("| AI 编程工具项目指引 | 不适用 |", report)
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
                    [sys.executable, "-B", str(SCRIPT), "--project-size", units, files],
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
            [sys.executable, "-B", str(SCRIPT), "--project-size", "-1", "20"],
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
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), str(example)], capture_output=True, text=True)
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
        self.assertIn("| Claude Code 项目指引 | 范围内未发现 |", checklist)
        self.assertIn("| Codex 项目指引 | 发现问题 | **缺少说明**", checklist)
        self.assertIn("在仓库根补建 AGENTS.md", suggestions)
        self.assertNotIn("Claude Code", suggestions)
        self.assertEqual(suggestions.count("#### "), 3)
        redundancy = checklist.split("### 文档冗余\n")[1]
        self.assertIn("README.md#导出规则、docs/操作手册.md#CSV 格式", redundancy)
        self.assertIn("保留 README.md#导出规则", redundancy)
        self.assertIn("手册独有的对账示例", redundancy)

    def test_focused_agent_instructions_keep_independent_tool_findings(self):
        task = {"check": "agent_instructions", "unit": "仓库根的开发工具"}
        gaps = [{
            "tool": tool, "status": "发现问题", "gap_kind": "missing",
            "detail": f"开发约定指定的 {path} 缺失。", "evidence": ["README.md#开发协作", "命令观察：已枚举根目录"],
            "impact": "启动时无法取得仓库的测试约定。", "placement": f"补建 {path}，引用测试手册。",
        } for tool, path in (("Claude Code", "CLAUDE.md"), ("Codex", "AGENTS.md"))]
        record = {"selected": [task], "scope": ["仓库根和开发约定"], "unread": [],
                  "topics": {"agent_instructions": gaps}}
        for unread in ([], [{"source": ".claude/", "reason": "无权列出目录"}]):
            with self.subTest(unread=unread):
                gaps[0]["unread"] = unread
                result = run_report(record, "--json")
                self.assertEqual(result.returncode, 0, result.stderr)
                packet = json.loads(result.stdout)
                expected = ["待确认" if unread else "发现问题", "发现问题"]
                self.assertEqual([item["status"] for item in packet["assessments"]], expected)
                self.assertEqual(packet["results"][0]["status"], "部分已查" if unread else "已查")
                self.assertNotIn("验证改动的方法", packet["markdown"])
                suggestions = packet["markdown"].split("### 建议补写")[1]
                self.assertEqual(gaps[0]["placement"] in suggestions, not unread)
                self.assertIn(gaps[1]["placement"], suggestions)

    def test_agent_instructions_reject_empty_results_and_unattributed_findings(self):
        task = {"check": "agent_instructions", "unit": "仓库根"}
        for value in ([], {}, [None], [verification_gap()]):
            with self.subTest(value=value):
                result = run_report({"selected": [task], "scope": ["仓库根"], "unread": [],
                                     "topics": {"agent_instructions": value}}, "--json")
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertIn("agent_instructions", result.stderr)

    def test_focused_redundancy_reports_cross_document_and_same_document_groups(self):
        task = {"check": "redundancy", "unit": "部署说明"}
        first = repeated_configuration()
        second = {
            "status": "发现问题", "detail": "同一手册的两节完整重述回滚步骤，发布流程指向回滚章节。",
            "evidence": ["docs/部署.md#回滚", "docs/部署.md#常见问题"],
            "impact": "回滚顺序变化时容易漏改常见问题。", "placement": "将常见问题的步骤替换为回滚章节链接。",
        }
        record = {"scope": ["README.md 和 docs/部署.md"], "unread": [], "selected": [task],
                  "topics": {"redundancy": [first, second]}}
        result = run_report(record, "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads(result.stdout)
        self.assertEqual(packet["results"], [{**task, "status": "已查"}])
        rows = [line for line in packet["markdown"].splitlines() if line.startswith("| 发现问题 |")]
        self.assertEqual(len(rows), 2)
        for row, comparison in zip(rows, (first, second)):
            self.assertIn(comparison["impact"], row)
            self.assertIn("、".join(comparison["evidence"]), row)
            self.assertIn(f"保留 {comparison['evidence'][0]}", row)
            self.assertIn(comparison["placement"], row)
        self.assertNotIn("### 按文档类别检查", packet["markdown"])
        self.assertNotIn("### 建议补写", packet["markdown"])

    def test_unread_manual_preserves_confirmed_pair_and_only_that_merge_suggestion(self):
        record = local_tool()
        task = {"check": "redundancy", "unit": "部署说明"}
        record["selected"] = [task]
        confirmed = repeated_configuration()
        record["topics"]["redundancy"].extend([confirmed, {
            "status": "待确认", "detail": "尚未读到值班手册的正文，无法判定其适用版本。",
            "evidence": ["docs/交接.md#值班手册"],
        }])
        record["unread"] = [{"source": "值班手册", "reason": "访问受限", "topics": ["redundancy"]}]
        result = run_report(record, "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads(result.stdout)
        report = packet["markdown"]
        self.assertIn("**检查结果**　发现问题", report)
        self.assertIn("**项目资料完整性**　待确认", report)
        self.assertIn(confirmed["placement"], report)
        self.assertIn("| 范围内未发现 | 交接手册只链接验收样例，预期表头集中在样例中。 | docs/交接.md:10、docs/样例.md:4 | — |", report)
        self.assertIn("| 待确认 | 尚未读到值班手册的正文，无法判定其适用版本。 | docs/交接.md#值班手册 | — |", report)
        self.assertEqual(packet["results"][0]["status"], "部分已查")
        self.assertIn("待核对值班手册", packet["results"][0]["reason"])

    def test_invalid_redundancy_records_do_not_render_a_partial_report(self):
        valid = repeated_configuration()
        for comparisons, field in (
            ([], "topics.redundancy"),
            (valid, "topics.redundancy"),
            ([valid, {**valid, "evidence": ["README.md:3"]}], "redundancy.evidence"),
            ([{**valid, "evidence": ["README.md:3", " README.md:3 "]}], "redundancy.evidence"),
            ([{**valid, "placement": ""}], "redundancy.placement"),
            ([{**valid, "impact": ""}], "redundancy.impact"),
        ):
            with self.subTest(comparisons=comparisons):
                record = local_tool()
                record["topics"]["redundancy"] = comparisons
                result = run_report(record)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertIn(field, result.stderr)

    def test_previous_full_record_reports_agent_instructions_as_pending(self):
        record = local_tool()
        del record["topics"]["agent_instructions"]
        record["selected"] = [{"check": "必要文档", "unit": "订单导出"}]
        report = self.report(record)
        self.assertIn("| AI 编程工具项目指引 | 待确认 |", report)
        self.assertIn("| 必要文档 | 订单导出 | 部分已查 |", report)
        self.assertNotIn("建议补写", report)

    def test_old_eight_topic_record_and_missing_focused_result_do_not_claim_coverage(self):
        record = local_tool()
        del record["topics"]["agent_instructions"]
        del record["topics"]["redundancy"]
        report = self.report(record)
        self.assertIn("**检查结果**　待确认", report)
        self.assertIn("旧版记录未包含文档冗余检查", report)
        self.assertIn("| 验证改动的方法 | 范围内未发现 |", report)
        record["selected"] = [{"check": "redundancy", "unit": "文档"}]
        report = self.report(record)
        self.assertIn("**检查结果**　未查", report)
        self.assertIn("| redundancy | 文档 | 未查 |", report)

    def test_legacy_record_marks_new_checks_pending(self):
        record = local_tool()
        del record["topics"]["agent_instructions"]
        del record["topics"]["redundancy"]
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

    def test_unread_manual_cannot_be_the_only_evidence_for_verification(self):
        manual = "docs/验收手册.md"
        task = {"check": "verification", "unit": "订单导出"}
        record = local_tool()
        record["selected"] = [task]
        record["unread"] = [{"source": manual, "reason": "链接目标不存在", "topics": ["verification"]}]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "orders.csv").write_text("order_id\nA1\n", encoding="utf-8")
            command = "from pathlib import Path; print(Path('orders.csv').read_text().splitlines()[0])"
            (root / "README.md").write_text(f'运行 python3 -B -c "{command}"，应输出 order_id。\n', encoding="utf-8")
            self.assertEqual(subprocess.check_output([sys.executable, "-B", "-c", command], cwd=root, text=True),
                             "order_id\n")
            self.assertFalse((root / manual).exists())
            cases = [
                ([manual], "待确认"),
                ([f"{manual}:7–9", f"`{manual}`#验收"], "待确认"),
                ([f"{manual}#验收", "README.md:1"], "范围内未发现"),
            ]
            for evidence, status in cases:
                with self.subTest(evidence=evidence):
                    record["topics"]["verification"]["evidence"] = evidence
                    result = run_report(record, "--json", cwd=root)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    packet = json.loads(result.stdout)
                    self.assertIn(f"| 验证改动的方法 | {status} |", packet["markdown"])
                    self.assertEqual(packet["results"], [{**task, "status": "部分已查", "reason": f"待核对{manual}"}])

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

    def test_unread_reference_preserves_proven_stale_gap_in_same_topic(self):
        record = local_tool()
        record["topics"]["verification"] = {
            **verification_gap(),
            "gap_kind": "stale",
            "detail": "README 中的 make check 已从 Makefile 移除。",
            "evidence": ["README.md:10", "Makefile:1"],
            "placement": "更新 README 中失效的 make check 命令。",
        }
        record["unread"] = [{
            "source": "独立的验收手册", "reason": "本轮无法访问", "topics": ["verification"],
        }]
        report = self.report(record)
        self.assertIn("**检查结果**　发现问题", report)
        self.assertIn("**项目资料完整性**　待确认", report)
        self.assertIn("| 验证改动的方法 | 发现问题 | **与实现不符**", report)
        self.assertIn("独立的验收手册（本轮无法访问）", report)
        self.assertIn("更新 README 中失效的 make check 命令。", report.split("### 建议补写\n")[1])

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
            result = subprocess.run([sys.executable, "-B", str(SCRIPT), str(path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, self.report(record))
        self.assertIn(r"A\|B 并检查两列。", result.stdout)


if __name__ == "__main__":
    unittest.main()
