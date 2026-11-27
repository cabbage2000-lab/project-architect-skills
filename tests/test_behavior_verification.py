import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "skills/project-architect-skills/scripts/behavior_verification.py"
ENTRY = "订单导出"


def selected(*checks):
    return [{"check": check, "unit": ENTRY} for check in checks]


def record(*checks):
    run = {
        "status": "范围内未发现", "mode": "run", "operation": "Python 3，临时副本中运行 python export.py",
        "input": "空订单", "expected": "输出 CSV 表头", "basis": "README.md#导出",
        "observed": "仅输出 Customer 一行", "evidence": ["export.py:4"],
    }
    regression = {
        **run, "mode": "static", "operation": "核对测试发现规则和断言",
        "test": "tests/test_export.py::test_empty", "status": "发现问题",
        "observed": "只断言文件存在", "impact": "零字节文件也会通过",
        "evidence": ["Makefile:8", "tests/test_export.py:24"],
    }
    return {
        "entry": ENTRY, "selection": "用户指定", "selected": selected(*checks or ["行为验证"]),
        "checks": {"minimal_run": run.copy(), "business_rule": run.copy(), "regression": regression},
    }


def invoke(data, *flags, path=None):
    arguments = [sys.executable, "-B", str(SCRIPT), *flags]
    if path is not None:
        arguments.append(str(path))
    return subprocess.run(arguments, input=data, capture_output=True, text=True)


class BehaviorVerificationTests(unittest.TestCase):
    def packet(self, data):
        result = invoke(json.dumps(data), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_correct_output_and_weak_assertion_are_independent(self):
        packet = self.packet(record())
        report = packet["markdown"]
        self.assertEqual(packet["results"], [{**selected("行为验证")[0], "status": "已查"}])
        self.assertEqual(report.count("**范围内未发现**（已实跑）"), 2)
        self.assertIn("**发现问题**（仅静态核对）", report)
        self.assertIn("只断言文件存在", report)
        self.assertIn("tests/test_export.py::test_empty", report)

    def test_runtime_failure_preserves_separate_blocked_rule_and_regression(self):
        data = record()
        data["checks"]["minimal_run"].update(status="发现问题", observed="找不到 config.csv", impact="首次调用失败")
        data["checks"]["business_rule"] = {
            "mode": "static", "status": "待确认", "observed": "入口在加载资源时退出",
            "reason": "无法取得 CSV 输出", "evidence": ["export.py:3"],
        }
        packet = self.packet(data)
        self.assertIn("**发现问题**（已实跑）", packet["markdown"])
        self.assertIn("**待确认**（仅静态核对）", packet["markdown"])
        self.assertEqual(packet["results"][0]["status"], "部分已查")
        self.assertIn("无法取得 CSV 输出", packet["results"][0]["reason"])
        self.assertIn("只断言文件存在", packet["markdown"])

    def test_missing_checks_are_visible_in_full_and_scoped_reports(self):
        data = record("行为验证", "compatibility")
        del data["checks"]["business_rule"]
        packet = self.packet(data)
        basic, optional = packet["results"]
        self.assertEqual((basic["status"], optional["status"]), ("部分已查", "未查"))
        self.assertIn("契约兼容未查", basic["reason"])
        self.assertIn("业务行为符合约定未查", basic["reason"])
        data["checks"] = {}
        self.assertTrue(all(item["status"] == "未查" for item in self.packet(data)["results"]))

    def test_optional_checks_and_individual_dispatch(self):
        data = record()
        data["checks"]["compatibility"] = {
            **data["checks"]["business_rule"], "input": "旧版输入", "status": "发现问题",
            "observed": "拒绝已承诺的旧字段", "impact": "旧客户端不能导出",
        }
        data["checks"]["retry"] = {
            "mode": "static", "status": "不适用", "observed": "只读查询",
            "reason": "当前入口没有写入或重试机制", "evidence": ["export.py:2"],
        }
        self.assertIn("拒绝已承诺的旧字段", self.packet(data)["markdown"])
        data["selected"] = selected("retry")
        packet = self.packet(data)
        self.assertEqual(packet["results"], [{**selected("retry")[0], "status": "已查"}])
        self.assertIn("当前入口没有写入或重试机制", packet["markdown"])
        self.assertNotIn("旧客户端", packet["markdown"])
        self.assertNotIn("最小运行可复现", packet["markdown"])

    def test_invalid_evidence_never_emits_a_partial_report(self):
        for kind, changes in [
            ("business_rule", {"mode": "static"}), ("minimal_run", {"evidence": []}),
            ("minimal_run", {"basis": ""}), ("regression", {"test": ""}),
            ("regression", {"impact": ""}), ("business_rule", {"status": "待确认"}),
        ]:
            with self.subTest(kind=kind, changes=changes):
                data = record()
                data["checks"][kind].update(changes)
                result = invoke(json.dumps(data), "--json")
                self.assertEqual(result.returncode, 2)
                self.assertIn(kind, result.stderr)
                self.assertEqual(result.stdout, "")
        data = record()
        data["entry"] = "退款"
        result = invoke(json.dumps(data))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")

    def test_file_and_stdin_produce_identical_markdown(self):
        data = record()
        del data["selected"]
        payload = json.dumps(data, ensure_ascii=False)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "记录.json"
            path.write_text(payload, encoding="utf-8")
            result = invoke(None, path=path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, self.packet(data)["markdown"])

    def test_governance_report_accepts_four_or_five_sections_and_preserves_limits(self):
        kinds = ("必要文档", "架构图", "目录结构", "代码异味")
        coverage = {"selected": selected(*kinds), "results": [
            {**item, "status": "已查"} for item in selected(*kinds)
        ]}
        audit = [f"## {kind}\n已核对订单导出。" for kind in kinds]
        report = {"audit": audit, "plan": {"mode": "inspect", "candidates": [], "coverage": coverage},
                  "reviews": [], "guide": [], "guide_limit": "本样例只核对体检章节。"}
        data = record()
        del data["checks"]["business_rule"]
        packet = self.packet(data)
        with tempfile.TemporaryDirectory() as root:
            for count in (4, 5):
                if count == 5:
                    audit.append(packet["markdown"])
                    coverage["selected"].extend(data["selected"])
                    coverage["results"].extend(packet["results"])
                result = subprocess.run([sys.executable, "-B", str(SCRIPT.with_name("governance_report.py"))],
                                        cwd=root, input=json.dumps(report), text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f"本轮选定 {count} 项检查范围，完整核对 4 项", result.stdout)
                self.assertEqual("## 行为验证" in result.stdout, count == 5)
            self.assertIn("业务行为符合约定未查", result.stdout)
            self.assertEqual(list(Path(root).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
