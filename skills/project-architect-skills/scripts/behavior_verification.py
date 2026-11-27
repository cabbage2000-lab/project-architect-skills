"""校验一个实际入口的行为取证记录，生成体检章节。"""

import argparse
import json
import sys
from pathlib import Path

from inspection_coverage import inspection_output, selected_checks
from necessary_docs import COVERED, GAP, NOT_APPLICABLE, PENDING, overall_status, project_summary
from report_fields import required_text, text_list


BASIC = "行为验证"
DEFAULT_CHECKS = {
    "minimal_run": "最小运行可复现",
    "business_rule": "业务行为符合约定",
    "regression": "回归验证有效",
}
CHECKS = {**DEFAULT_CHECKS, "compatibility": "契约兼容", "retry": "中断与重试"}
MODES = {"run": "已实跑", "static": "仅静态核对"}


def render_check(kind, item):
    if not isinstance(item, dict):
        raise ValueError(f"{kind} 需要取证记录")
    status = required_text(item.get("status"), f"{kind}.status")
    mode = required_text(item.get("mode"), f"{kind}.mode")
    if status not in (COVERED, GAP, PENDING, NOT_APPLICABLE) or mode not in MODES:
        raise ValueError(f"{kind} 的结论或取证方式无效")
    conclusive = status in (COVERED, GAP)
    if conclusive and mode == "static" and kind != "regression":
        raise ValueError(f"{kind} 的运行结果需要实跑证据")

    lines = [f"### {CHECKS[kind]}", "", f"**{status}**（{MODES[mode]}）", ""]
    fields = (
        ("operation", "操作与环境", conclusive or mode == "run"),
        ("input", "输入", conclusive or mode == "run"),
        ("expected", "预期", conclusive),
        ("basis", "预期出处", conclusive),
        ("observed", "观察", True),
        ("test", "关联用例或检索范围", conclusive and kind == "regression"),
        ("impact", "维护影响", status == GAP),
    )
    for field, label, needed in fields:
        if needed or field in item:
            value = required_text(item.get(field), f"{kind}.{field}")
            lines.append(f"- {label}　{value}")
    evidence = text_list(item.get("evidence"), f"{kind}.evidence")
    lines.append(f"- 核对依据　{'、'.join(evidence)}")
    reason = ""
    if status in (PENDING, NOT_APPLICABLE):
        reason = required_text(item.get("reason"), f"{kind}.reason")
        lines.append(f"- 原因　{reason}")
    return lines, status, reason if status == PENDING else ""


def render_report(record, *, as_json=False):
    if not isinstance(record, dict):
        raise ValueError("检查记录需要 JSON 对象")
    entry = required_text(record.get("entry"), "entry")
    selection = required_text(record.get("selection"), "selection")
    dispatched = selected_checks(record, CHECKS, BASIC)
    if dispatched and entry not in dispatched.values():
        raise ValueError("entry 应与本份派发清单的 unit 一致")
    checks = record.get("checks")
    if not isinstance(checks, dict) or checks.keys() - CHECKS.keys():
        raise ValueError("checks 需要由已知行为检查项组成的对象")

    requested = set(dispatched) - {BASIC}
    if BASIC in dispatched or not dispatched:
        requested.update(DEFAULT_CHECKS)
        requested.update(checks)
    sections = []
    states = set()
    answers = {}
    limits = []
    for kind, label in CHECKS.items():
        if kind not in requested:
            continue
        if kind not in checks:
            sections.extend([f"### {label}", "", "未查。未收到此项的取证记录。", ""])
            states.add("未查")
            limits.append(f"{label}未查")
            continue
        lines, state, reason = render_check(kind, checks[kind])
        sections.extend([*lines, ""])
        states.add(state)
        answers[kind] = reason
        if reason:
            limits.append(f"{label}：{reason}")

    if BASIC in dispatched and answers:
        answers[BASIC] = "、".join(limits)
    summary = project_summary(record["project"]) if "project" in record else []
    lines = [
        f"## {BASIC}", "", *summary,
        f"**检查结果**　{overall_status(states, bool(limits))}", "",
        f"**入口**　{entry}", "", f"**选取依据**　{selection}", "", *sections,
    ]
    return inspection_output(lines, dispatched, answers, as_json, BASIC)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", nargs="?", type=Path, help="检查记录 JSON，默认读取标准输入")
    parser.add_argument("--json", action="store_true", help="返回体检章节和检查范围记录")
    args = parser.parse_args()
    try:
        if args.record is None:
            record = json.load(sys.stdin)
        else:
            record = json.loads(args.record.read_text(encoding="utf-8"))
        report = render_report(record, as_json=args.json)
    except (OSError, ValueError) as error:
        parser.exit(2, f"行为验证记录无法汇总（{error}）\n")
    sys.stdout.write(report)


if __name__ == "__main__":
    main()
