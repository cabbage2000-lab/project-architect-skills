import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "skills/project-architect-skills/scripts"
DOC_KEYS = ("purpose", "requirements", "usage", "configuration", "api", "architecture", "verification", "deployment")
SMELL_KEYS = ("long_method", "deep_nested_logic", "bumpy_road", "complex_conditional", "complex_method")
UNIT = "本地工具"
CLEAR = "范围内未发现"
NA = "不适用"


def conclusion(status=CLEAR, evidence="tool.py:1", detail="按当前入口核对。", **extra):
    return {"status": status, "detail": detail, "evidence": [evidence], **extra}


def problem(root_id="test-command", severity="需要绕行", source="README.md:2"):
    return conclusion("发现问题", source, "验收说明引用了已移除的命令。", root_id=root_id,
                      severity=severity, impact="运行说明中的命令失败，须直接调用测试入口。", placement="README 的检查步骤")


def dispatched(check, unit=UNIT):
    return {"check": check, "unit": unit}


def expert_record(check, **fields):
    return {"scope": [UNIT], "unread": [], "selected": [dispatched(check)], **fields}


def project_records(manual="README.md", verification=None):
    topics = {name: conclusion(evidence=f"{manual}:1") for name in DOC_KEYS}
    topics["agent_instructions"] = [{"tool": "Codex", **conclusion(evidence="AGENTS.md:1")}]
    topics["redundancy"] = [conclusion(NA, f"{manual}:1", "只有一本手册。")]
    if verification is not None:
        topics["verification"] = verification
    return {
        "necessary_docs": expert_record("必要文档", topics=topics),
        "architecture_diagrams": expert_record("架构图", need=conclusion(NA, detail="单入口直接返回姓名。"), diagrams=[]),
        "directory_structure": expert_record("目录结构", checks=[{
            "path": "tests/test_tool.py", "expected": "tests/", "basis": "rule", "matches": True,
            "detail": "按约定从 tests 发现测试。", "evidence": ["tests/test_tool.py:1", "AGENTS.md:1"],
        }]),
        "code_smells": expert_record("代码异味", methods=[], checks={name: conclusion() for name in SMELL_KEYS}),
    }


def assessment(check, entry, unit=UNIT):
    return {**dispatched(check, unit), **entry}


def from_rows(keys, rows, scope="scoped"):
    return {"mode": "inspect", "candidates": [],
            "coverage": {"selected": keys, "results": [{**key, "status": "已查"} for key in keys]},
            "scoring": {"version": 2, "scope": scope, "assessments": rows}}


class HealthScoreTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "tests").mkdir()
        for name, body in {
            "README.md": "姓名工具\npython missing.py\n", "AGENTS.md": "用 Codex 维护姓名工具时，测试固定放在 tests/。\n",
            "tool.py": "def name():\n    return 'Ada'\n",
            "tests/test_tool.py": "import unittest\nfrom tool import name\n"
                                  "class Names(unittest.TestCase):\n"
                                  "    def test_name(self):\n        self.assertEqual(name(), 'Ada')\n",
        }.items():
            (self.root / name).write_text(body, encoding="utf-8")

    def cli(self, script, data, *args, invalid=None):
        proc = subprocess.run([sys.executable, "-B", str(SCRIPTS / f"{script}.py"), *args],
                              cwd=self.root, input=json.dumps(data), text=True, capture_output=True)
        if invalid is not None:
            self.assertEqual(proc.returncode, 2, proc.stderr)
            self.assertEqual(proc.stdout, "")
            self.assertIn(invalid, proc.stderr)
            return
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout) if "--json" in args else proc.stdout

    def inspect(self, records):
        selected, results, facts, audit = [], [], [], []
        for script, record in records.items():
            packet = self.cli(script, record, "--json")
            selected.extend(record["selected"])
            results.extend(packet["results"])
            facts.extend(packet["assessments"])
            audit.append(packet["markdown"])
        plan = from_rows(selected, facts, "full")
        plan["coverage"]["results"] = results
        return plan, audit

    def preview(self, plan, **options):
        return self.cli("governance_plan", plan, "--preview", "--json", **options)

    def final_record(self, packet, after=None, audit=None):
        data = {"audit": ["## 专项检查"] if audit is None else audit, "plan": packet["plan"], "reviews": [],
                "guide": [], "guide_limit": "检查范围见体检章节。"}
        if after is not None:
            data["reassessment"] = {**after["scoring"], "coverage": after["coverage"]}
        return data

    def test_four_experts_preview_write_and_reassess_after_a_file_move(self):
        plan, audit = self.inspect(project_records(verification=problem()))
        plan.update(mode="execute", candidates=[{
            "target": "test-command", "title": "补正验收命令", "evidence": ["README.md:2"],
            "status": "可执行", "impact": "说明中的命令失效。", "reason": "修复验收入口。",
            "scope": "使用手册", "steps": "替换命令。", "baseline": "原命令退出码为 2。",
            "acceptance": "按手册跑通测试。", "rollback": "恢复原手册。",
        }])
        packet = self.preview(plan)
        baseline = packet["markdown"].split("\n\n## 治理计划")[0]
        self.assertIn("93.3/100（实得 70/75）", baseline)
        self.assertIn("| 软件架构 | 不适用 |", baseline)
        self.assertIn("| 工程文档 | 20/25 |", baseline)
        self.assertIn("同意治理", packet["markdown"])
        self.assertFalse((self.root / "docs").exists())
        old = subprocess.run([sys.executable, "missing.py"], cwd=self.root, capture_output=True)
        self.assertEqual(old.returncode, 2)
        manual = self.root / "GUIDE.md"
        (self.root / "README.md").rename(manual)
        manual.write_text("姓名工具\npython -B -m unittest discover -s tests\n", encoding="utf-8")
        replay = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests"],
                                cwd=self.root, capture_output=True, text=True)
        self.assertEqual(replay.returncode, 0, replay.stderr)
        verified = conclusion(CLEAR, "GUIDE.md:2", "按新手册运行，1 项测试通过。", resolves=["test-command"])
        after, _ = self.inspect(project_records("GUIDE.md", verified))
        record = self.final_record(packet, after, audit)
        record["reviews"] = [{"target": "test-command", "status": "通过", "kind": "handover",
                              "changes": "在新手册写入验收命令。", "checks": [{
                                  "kind": "handover", "operation": "运行手册命令", "expected": "测试通过",
                                  "observed": replay.stderr.strip(), "result": "通过",
                              }]}]
        report = self.cli("governance_report", record)
        self.assertTrue(report.startswith("# 项目治理报告\n\n" + baseline))
        self.assertIn("100/100（实得 75/75）", report)
        self.assertIn("93.3 → 100（+6.7 分）", report)
        self.assertIn("test-command 已消除。按新手册运行，1 项测试通过。（GUIDE.md:2）", report)
        path = self.cli("governance_report", record, "--write").strip()
        self.assertTrue((self.root / path).read_text(encoding="utf-8").endswith(report))
        del record["reassessment"]
        self.assertIn("尚未收到原范围的复查记录", self.cli("governance_report", record))

    def test_one_blocker_and_cross_expert_duplicates_charge_the_owner_once(self):
        records = project_records()
        weaker = {**problem("wrong-edge", "轻微"), "owner": "架构"}
        records["necessary_docs"]["topics"]["architecture"] = weaker
        records["architecture_diagrams"].update(
            need=conclusion("需要"), diagrams=[{"source": "README.md:1", "kind": "implementation", "checks": [{
                "claim": "调用方向", "result": "与实现不符", "detail": "调用方画反。", "evidence": ["tool.py:1"],
            }]}], repair={**problem("wrong-edge", "阻断"), "changes": ["改正箭头。"], "impact": "无法按图定位回调。"})
        plan, _ = self.inspect(records)
        report = self.preview(plan)["markdown"]
        self.assertIn("85/100", report)
        self.assertIn("**阻断操作**　无法按图定位回调。", report)
        self.assertIn("| 软件架构 | 10/25 |", report)
        self.assertIn("| 工程文档 | 25/25 |", report)
        self.assertEqual(report.count("| wrong-edge |"), 1)
        detail = next(line for line in report.splitlines() if "| wrong-edge |" in line)
        for source in ("README.md:1", "README.md:2", "tool.py:1"):
            self.assertIn(source, detail)

    def test_scoped_floor_and_three_smells_on_one_method(self):
        checks = {kind: conclusion("发现问题") for kind in SMELL_KEYS[:3]}
        records = expert_record("代码异味", methods=[{
            "path": "tool.py", "symbol": "name", "start": 1, "end": 2,
            "root_id": "name-logic", "severity": "轻微", "impact": "需重复核对分支。",
            "findings": [{"kind": kind, "detail": "已核对分支。", "evidence": ["tool.py:1", "tool.py:2"]}
                         for kind in checks],
        }], checks=checks)
        keys = [dispatched(kind) for kind in checks]
        records["selected"] = keys
        packet = self.cli("code_smells", records, "--json")
        report = self.preview(from_rows(keys, packet["assessments"]))["markdown"]
        self.assertIn("| 代码质量 | 23/25 |", report)
        self.assertEqual(report.count("| name-logic |"), 1)
        self.assertNotIn("**本轮总分**", report)
        rows = [assessment("verification", problem(key, "阻断")) for key in ("first", "second")]
        report = self.preview(from_rows([dispatched("verification")], rows))["markdown"]
        self.assertIn("| 工程文档 | 0/25 |", report)
        self.assertIn("累计扣 30 分，按 25 分封顶", report)

    def test_embedded_architecture_drift_counts_even_when_no_diagram_is_needed(self):
        records = project_records()
        drift = {**problem("dependency", "需要绕行"), "kind": "architecture_drift", "title": "工具绕过公共入口",
                 "evidence": ["AGENTS.md:1", "tool.py:1"]}
        records["code_smells"]["modules"] = [drift]
        plan, _ = self.inspect(records)
        preview = self.preview(plan)
        self.assertIn("95/100（实得 95/100）", preview["markdown"])
        self.assertIn("| 软件架构 | 20/25 |", preview["markdown"])
        self.assertIn("| 代码质量 | 25/25 |", preview["markdown"])
        only_code, _ = self.inspect({"code_smells": records["code_smells"]})
        only_code["scoring"]["scope"] = "scoped"
        scoped = self.preview(only_code)
        self.assertIn("| 软件架构 | 20/25 | architecture_drift /", scoped["markdown"])
        records["code_smells"]["selected"].append(dispatched("architecture_drift"))
        separately_selected, _ = self.inspect({"code_smells": records["code_smells"]})
        separately_selected["scoring"]["scope"] = "scoped"
        final = self.cli("governance_report", self.final_record(scoped, separately_selected))
        self.assertIn("检查范围已变化", final)
        self.assertNotIn("**专项分数变化**", final)
        after, _ = self.inspect(project_records())
        final = self.cli("governance_report", self.final_record(preview, after))
        self.assertIn("检查范围已变化", final)
        self.assertNotIn("**总分变化**", final)

    def test_an_unread_only_source_leaves_other_deductions_and_dimensions_visible(self):
        records = project_records(verification=conclusion(evidence="docs/manual.md#测试"))
        records["necessary_docs"]["topics"]["usage"] = problem("usage", "需要绕行")
        records["necessary_docs"]["unread"] = [{"source": "docs/manual.md", "reason": "无法读取", "topics": ["verification"]}]
        plan, _ = self.inspect(records)
        packet = self.preview(plan)
        self.assertIn("**本轮总分**　待补查", packet["markdown"])
        self.assertIn("| 工程文档 | 待补查 |", packet["markdown"])
        self.assertIn("docs/manual.md", packet["markdown"])
        self.assertIn("| usage | 工程文档 | 需要绕行 | 5 |", packet["markdown"])
        self.assertIn("| 仓库结构 | 25/25 |", packet["markdown"])
        fact = next(row for row in packet["plan"]["scoring"]["assessments"] if row["criterion"] == "verification")
        self.assertEqual(fact["status"], "待确认")

    def test_partial_missing_and_excluded_coverage_cannot_create_a_score(self):
        plan, _ = self.inspect(project_records())
        plan["coverage"]["selected"].append(dispatched("目录结构", "退款"))
        plan["coverage"]["excluded"] = [{**dispatched("目录结构", "归档"), "reason": "属于其他工具。"}]
        report = self.preview(plan)["markdown"]
        self.assertIn("| 仓库结构 | 待补查 |", report)
        self.assertIn("退款：未收到", report)
        self.assertIn("待补查", report)
        focused = from_rows([dispatched("verification")], [assessment("verification", conclusion())], scope="full")
        self.assertIn("未选定基础检查", self.preview(focused)["markdown"])
        plan["scoring"]["assessments"] = [r for r in plan["scoring"]["assessments"] if r["criterion"] != "verification"]
        self.assertIn("缺少判据 verification", self.preview(plan)["markdown"])

    def test_all_not_applicable_and_missing_or_ungraded_facts(self):
        plan, _ = self.inspect(project_records())
        for fact in plan["scoring"]["assessments"]:
            fact["status"] = NA
        self.assertIn("**本轮总分**　无适用维度", self.preview(plan)["markdown"])
        row = assessment("verification", problem())
        for key, value in (("severity", None), ("root_id", None), ("evidence", []),
                           ("evidence", ["gone.md:99"]), ("evidence", ["已经看过了"])):
            with self.subTest(key=key, value=value):
                fact = {**row, key: value}
                if value is None:
                    del fact[key]
                focused = from_rows([dispatched("verification")], [fact])
                first = self.preview(focused)
                self.assertIn("| 工程文档 | 待补查 |", first["markdown"])
                report = self.cli("governance_report", self.final_record(first))
                self.assertIn("| 工程文档 | 待补查 |", report)

    def test_unread_redundancy_pair_and_ungraded_cross_dimension_finding(self):
        records = project_records()
        records["necessary_docs"]["topics"]["redundancy"] = [{
            **problem("duplicate", "轻微"), "evidence": ["README.md:1", "AGENTS.md:1"],
        }]
        records["necessary_docs"]["unread"] = [{"source": "AGENTS.md", "reason": "本次未能读取", "topics": ["redundancy"]}]
        other = problem("wrong-graph")
        other.pop("severity")
        records["necessary_docs"]["topics"]["architecture"] = {**other, "owner": "架构"}
        plan, _ = self.inspect(records)
        packet = self.preview(plan)
        self.assertNotIn("| duplicate |", packet["markdown"])
        self.assertIn("| 软件架构 | 待补查 |", packet["markdown"])
        self.assertIn("| 仓库结构 | 25/25 |", packet["markdown"])
        self.assertIn("| 软件架构 | 待补查 |", self.cli("governance_report", self.final_record(packet)))

    def test_changed_new_and_unreviewed_findings(self):
        key = dispatched("verification")
        initial = from_rows([key], [assessment("verification", problem())])
        packet = self.preview(initial)
        after = from_rows([key], [assessment("verification", problem(severity="轻微")),
                                  assessment("verification", problem("new", "阻断"))])
        report = self.cli("governance_report", self.final_record(packet, after))
        self.assertIn("工程文档 -12 分", report)
        self.assertIn("从工程文档「需要绕行」变为工程文档「轻微」", report)
        self.assertIn("新增根因 new", report)
        after["scoring"]["assessments"] = [assessment("verification", conclusion())]
        report = self.cli("governance_report", self.final_record(packet, after))
        self.assertIn("test-command 缺少复查结论", report)
        self.assertNotIn("**专项分数变化**", report)
        after["scoring"]["assessments"][0].update(evidence=["gone.md:1"], resolves=["test-command"])
        report = self.cli("governance_report", self.final_record(packet, after))
        self.assertIn("待核实出处", report)
        self.assertNotIn("test-command 已消除", report)
        after["scoring"]["assessments"] = [
            assessment("verification", conclusion(resolves=["test-command"])),
            assessment("verification", problem("new", "轻微")),
        ]
        report = self.cli("governance_report", self.final_record(packet, after))
        self.assertIn("test-command 已消除", report)
        self.assertIn("新增根因 new", report)
        self.assertIn("工程文档 +3 分", report)

    def test_change_requires_identical_version_scope_and_applicable_dimensions(self):
        plan, _ = self.inspect(project_records())
        baseline = self.preview(plan)
        after = deepcopy(plan)
        architect = next(row for row in after["scoring"]["assessments"] if row["check"] == "架构图")
        architect["status"] = CLEAR
        report = self.cli("governance_report", self.final_record(baseline, after))
        self.assertIn("适用维度已变化", report)
        self.assertNotIn("**总分变化**", report)
        scoped = from_rows([dispatched("purpose")], [assessment("purpose", conclusion())])
        report = self.cli("governance_report", self.final_record(baseline, scoped))
        self.assertIn("检查范围已变化", report)
        after["scoring"]["version"] = 1
        report = self.cli("governance_report", self.final_record(baseline, after))
        self.assertIn("规则版本已变化", report)
        self.assertNotIn("**总分变化**", report)

    def test_new_full_check_requires_tool_instructions_and_replays_original_v1_score(self):
        plan, _ = self.inspect(project_records())
        plan["scoring"]["assessments"] = [
            item for item in plan["scoring"]["assessments"] if item["criterion"] != "agent_instructions"
        ]
        self.assertIn("缺少判据 agent_instructions", self.preview(plan)["markdown"])
        plan["scoring"]["version"] = 1
        baseline = self.preview(plan)
        self.assertIn("100/100", baseline["markdown"])
        self.assertIn("100/100", self.cli("governance_report", self.final_record(baseline)))

    def test_invalid_records_and_conflicting_roots_reject_the_whole_report(self):
        key = dispatched("verification")
        row = assessment("verification", problem())
        for update, error in (({"owner": "其他"}, "owner"), ({"severity": "高"}, "severity"),
                              ({"check": "usage"}, "检查范围"), ({"criterion": "架构图"}, "criterion")):
            with self.subTest(update=update):
                self.preview(from_rows([key], [{**row, **update}]), invalid=error)
        plan = from_rows([key, dispatched("目录结构")],
                         [row, assessment("目录结构", problem())])
        self.preview(plan, invalid="owner 不一致")
        packet = self.preview(from_rows([key], [row]))
        after = from_rows([key], [assessment("verification", conclusion(resolves=["unrelated"]))])
        self.cli("governance_report", self.final_record(packet, after), "--write", invalid="resolves")
        self.assertFalse((self.root / "docs").exists())

    def test_same_module_clean_check_cannot_close_another_criterion(self):
        initial, _ = self.inspect(project_records(verification=problem()))
        records = project_records()
        records["necessary_docs"]["topics"]["purpose"]["resolves"] = ["test-command"]
        after, _ = self.inspect(records)
        self.cli("governance_report", self.final_record(self.preview(initial), after), invalid="原检查范围和判据")

    def test_inspect_and_deferred_candidates_share_the_same_score(self):
        key = dispatched("verification")
        plan = from_rows([key], [assessment("verification", problem())])
        plan["candidates"] = [{"target": "run-tests", "title": "补测试说明", "evidence": ["README.md:2"],
                               "impact": "说明需要绕行。", "reason": "待维护者排期。", "status": "暂缓"}]
        readonly = self.preview(plan)
        plan["mode"] = "execute"
        deferred = self.preview(plan)
        for packet in (readonly, deferred):
            self.assertIn("| 工程文档 | 20/25 |", packet["markdown"])
            self.assertNotIn("同意治理", packet["markdown"])
        self.assertEqual(readonly["plan"]["scoring"], deferred["plan"]["scoring"])

    def test_direct_report_checks_sources_and_frozen_pending_survives_a_later_file(self):
        key = dispatched("verification")
        plan = from_rows([key], [assessment("verification", problem(source="future.md:1"))])
        raw = self.final_record({"plan": plan})
        self.assertIn("| 工程文档 | 待补查 |", self.cli("governance_report", raw))
        frozen = self.final_record(self.preview(plan))
        (self.root / "future.md").write_text("已补录的观察\n", encoding="utf-8")
        self.assertIn("| 工程文档 | 待补查 |", self.cli("governance_report", frozen))
        self.assertIn("| 工程文档 | 20/25 |", self.cli("governance_report", raw))


if __name__ == "__main__":
    unittest.main()
