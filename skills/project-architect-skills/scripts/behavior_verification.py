"""校验一个业务入口或一组共享规则的入口的行为取证记录。"""

import argparse
import json
import sys
from pathlib import Path

from inspection_coverage import inspection_output, selected_checks
from necessary_docs import COVERED, GAP, NOT_APPLICABLE, PENDING, overall_status, project_summary
from report_fields import labeled_fields, records, required_text, table_row, text_list


BASIC = "行为验证"
DEFAULT_CHECKS = {
    "minimal_run": "最小运行可复现",
    "business_rule": "业务行为符合约定",
    "regression": "回归验证有效",
}
SPECIALTY_LABELS = {
    "cross_entry": "跨入口业务规则一致性", "data_migration": "存量数据迁移与恢复",
    "concurrent_writes": "并发写入一致性", "access_scope": "权限与数据隔离",
    "failure_diagnostics": "失败可诊断性",
}
CHECKS = {**DEFAULT_CHECKS, "compatibility": "契约兼容", "retry": "中断与重试", **SPECIALTY_LABELS}
MODES = {"run": "已实跑", "static": "仅静态核对"}
RUN_FIELDS = {
    "data_migration": (("before", "迁移前数据"), ("after", "升级后的核对结果"), ("recovery", "恢复结果或恢复约定")),
    "concurrent_writes": (("overlap", "独立操作的重叠依据"), ("outcomes", "各操作结果"), ("final_state", "最终状态")),
    "access_scope": (("allowed", "允许样例及结果"), ("restricted", "受限样例及结果"), ("state", "受限操作后的状态")),
    "failure_diagnostics": (("signal", "调用方看到的失败信号"), ("location", "依据提示或日志能定位到的位置")),
}


def cross_entry_lines(item, conclusive):
    rows = []
    seen = set()
    for index, run in enumerate(records(item.get("entries", []), "cross_entry.entries")):
        field = f"cross_entry.entries[{index}]"
        name, operation, observed = (
            required_text(run.get(key), f"{field}.{key}") for key in ("entry", "operation", "observed")
        )
        if name in seen:
            raise ValueError(f"{field}.entry 重复：{name}")
        seen.add(name)
        rows.append(table_row((name, operation, observed)))
    if conclusive and len(rows) < 2:
        raise ValueError("cross_entry.entries 至少需要两个不同入口的实跑结果")
    if not rows:
        return []
    return ["", "| 入口 | 同一样例的操作 | 实际结果 |", "| --- | --- | --- |", *rows]


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
    lines.extend(labeled_fields(item, kind, fields))
    lines.extend(labeled_fields(item, kind, (
        (key, label, conclusive) for key, label in RUN_FIELDS.get(kind, ())
    )))
    evidence = text_list(item.get("evidence"), f"{kind}.evidence")
    lines.append(f"- 核对依据　{'、'.join(evidence)}")
    reason = ""
    if status in (PENDING, NOT_APPLICABLE):
        reason = required_text(item.get("reason"), f"{kind}.reason")
        lines.append(f"- 原因　{reason}")
    if kind == "cross_entry":
        lines.extend(cross_entry_lines(item, conclusive))
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
        answers[kind] = state, reason
        if reason:
            limits.append(f"{label}：{reason}")

    status = overall_status(states, bool(limits))
    if BASIC in dispatched and answers:
        answers[BASIC] = status, "、".join(limits)
    summary = project_summary(record["project"]) if "project" in record else []
    lines = [
        f"## {BASIC}", "", *summary,
        f"**检查结果**　{status}", "",
        f"**入口**　{entry}", "", f"**选取依据**　{selection}", "", *sections,
    ]
    return inspection_output(lines, dispatched, answers, as_json, BASIC, status)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", nargs="?", type=Path, help="检查记录 JSON，默认读取标准输入")
    parser.add_argument("--json", action="store_true", help="返回质检章节和检查范围记录")
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
