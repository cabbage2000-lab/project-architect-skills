"""将实际路径与归属依据汇总为目录结构质检章节。"""

import argparse
import json
import sys
from pathlib import Path

from inspection_coverage import inspection_output, selected_checks
from necessary_docs import (
    COVERED, GAP, NOT_APPLICABLE, PENDING, overall_status, project_summary, required_text,
    table_row, text_list, unread_notes,
)


BASIS_LABELS = {
    "rule": "明确约定",
    "convention": "目录惯例",
    "unknown": "归属待核实",
    "not_applicable": "适用性依据",
}
STATUS_LABELS = {COVERED: "符合约定", GAP: "偏离约定", PENDING: PENDING, NOT_APPLICABLE: NOT_APPLICABLE}


def assess_path(check):
    if not isinstance(check, dict):
        raise ValueError("checks 的每项需要路径对照记录")
    path = required_text(check.get("path"), "checks.path")
    basis = required_text(check.get("basis"), "checks.basis")
    if basis not in BASIS_LABELS:
        raise ValueError(f"checks.basis 含未知类型 {basis}")
    detail = required_text(check.get("detail"), "checks.detail")
    evidence = text_list(check.get("evidence"), "checks.evidence")
    expected = check.get("expected")
    if basis in ("rule", "convention") or expected is not None:
        expected = required_text(expected, "checks.expected")

    status = PENDING
    if basis == "rule":
        matches = check.get("matches")
        if not isinstance(matches, bool):
            raise ValueError("明确约定的 checks.matches 需要 true 或 false")
        status = COVERED if matches else GAP
    elif basis == "not_applicable":
        status = NOT_APPLICABLE

    placement = expected or "—"
    if status == PENDING:
        placement = f"{expected}（待确认）" if expected else PENDING
    row = table_row((path, placement, STATUS_LABELS[status], f"{BASIS_LABELS[basis]}。{detail}", "、".join(evidence)))
    suggestion = None
    if status == GAP:
        impact = required_text(check.get("impact"), "checks.impact")
        suggestion = f"- **{path} → {expected}**　{impact}"
    reason = f"{path}：{detail}" if status == PENDING else ""
    return status, row, suggestion, reason


def render_report(record, *, as_json=False):
    if not isinstance(record, dict):
        raise ValueError("检查记录需要 JSON 对象")
    summary = project_summary(record["project"]) if "project" in record else []
    selected = selected_checks(record, (), "目录结构")
    scope = text_list(record.get("scope"), "scope")
    notes = unread_notes(record.get("unread"))
    checks = record.get("checks")
    if not isinstance(checks, list) or not (checks or notes):
        raise ValueError("checks 需要路径对照数组，尚无可核对路径时须提供 unread")

    states = set()
    gaps = list(notes)
    rows = []
    suggestions = []
    for check in checks:
        status, row, suggestion, reason = assess_path(check)
        states.add(status)
        if reason:
            gaps.append(reason)
        rows.append(row)
        if suggestion:
            suggestions.append(suggestion)

    status = overall_status(states, bool(notes) or PENDING in states)
    lines = [
        "## 目录结构", "", *summary,
        f"**检查结果**　{status}",
        "", "### 已查范围", "", *(f"- {item}" for item in scope),
    ]
    if rows:
        lines.extend([
            "", "### 路径对照", "",
            "| 实际路径 | 预期归属 | 结论 | 对照说明 | 核对依据 |",
            "| --- | --- | --- | --- | --- |", *rows,
        ])
    if notes:
        lines.extend(["", "### 未核实的资料", "", *notes])
    if suggestions:
        lines.extend(["", "### 建议调整", "", *suggestions])
    return inspection_output(lines, selected, {"目录结构": "、".join(gaps)}, as_json, "目录结构")


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
        parser.exit(2, f"目录结构记录无法汇总（{error}）\n")
    sys.stdout.write(report)


if __name__ == "__main__":
    main()
