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
from report_fields import labeled_fields, records


BASIC = "目录结构"
GENERATED = "generated_artifact"
GENERATED_LABEL = "修改源与生成产物同步"
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


def artifact_section(artifacts):
    lines = ["", f"### {GENERATED_LABEL}"]
    states, limits = set(), []
    if not artifacts:
        return [*lines, "", "未查。未收到生成产物的核对记录。"], {"未查"}, ["生成产物未查"]
    for index, artifact in enumerate(artifacts):
        field = f"artifacts[{index}]"
        status = required_text(artifact.get("status"), f"{field}.status")
        if status not in (COVERED, GAP, PENDING, NOT_APPLICABLE):
            raise ValueError(f"{field}.status 无效")
        states.add(status)
        compared = status in (COVERED, GAP)
        lines.extend(["", f"**{status}**", ""])
        lines.extend(labeled_fields(artifact, field, (
            ("source", "修改源", compared), ("artifact", "交付产物", compared),
            ("consumer", "实际消费者", compared), ("operation", "生成与核对操作", compared),
            ("expected", "预期内容", compared), ("observed", "实际观察", compared),
            ("impact", "维护影响", status == GAP), ("reason", "原因", not compared),
        )))
        evidence = text_list(artifact.get("evidence"), f"{field}.evidence")
        lines.append(f"- 核对依据　{'、'.join(evidence)}")
        if status == PENDING:
            limits.append(f"生成产物：{artifact['reason']}")
    return lines, states, limits


def path_section(checks, notes):
    rows, suggestions, limits = [], [], []
    states = set()
    for check in checks:
        status, row, suggestion, reason = assess_path(check)
        states.add(status)
        if reason:
            limits.append(reason)
        rows.append(row)
        if suggestion:
            suggestions.append(suggestion)

    lines = []
    if rows:
        lines.extend([
            "", "### 路径对照", "",
            "| 实际路径 | 预期归属 | 结论 | 对照说明 | 核对依据 |",
            "| --- | --- | --- | --- | --- |", *rows,
        ])
    elif not notes:
        lines.extend(["", "路径归属未查。"])
        states.add("未查")
        limits.append("路径归属未查")
    if notes:
        lines.extend(["", "### 未核实的资料", "", *notes])
    if suggestions:
        lines.extend(["", "### 建议调整", "", *suggestions])
    return lines, states, limits


def render_report(record, *, as_json=False):
    if not isinstance(record, dict):
        raise ValueError("检查记录需要 JSON 对象")
    summary = project_summary(record["project"]) if "project" in record else []
    selected = selected_checks(record, (GENERATED,), BASIC)
    scope = text_list(record.get("scope"), "scope")
    notes = unread_notes(record.get("unread"))
    include_artifacts = GENERATED in selected or "artifacts" in record
    lines, states, limits = [], set(), []
    answers = {}
    if not selected or BASIC in selected:
        checks = records(record.get("checks", [] if include_artifacts else None), "checks")
        if not (checks or notes or include_artifacts):
            raise ValueError("checks 需要路径对照数组，尚无可核对路径时须提供 unread")
        lines, states, limits = path_section(checks, notes)
    elif notes:
        lines.extend(["", "### 未核实的资料", "", *notes])
    if include_artifacts:
        artifacts = records(record.get("artifacts", []), "artifacts")
        extra, artifact_states, artifact_limits = artifact_section(artifacts)
        lines.extend(extra)
        states.update(artifact_states)
        limits.extend(artifact_limits)
        if artifacts:
            answers[GENERATED] = overall_status(artifact_states, bool(artifact_limits or notes)), "、".join([*artifact_limits, *notes])
    status = overall_status(states, bool(notes) or PENDING in states)
    if notes or states - {"未查"}:
        answers[BASIC] = status, "、".join([*notes, *limits])
    lines = [
        f"## {BASIC}", "", *summary, f"**检查结果**　{status}",
        "", "### 已查范围", "", *(f"- {item}" for item in scope), *lines,
    ]
    return inspection_output(lines, selected, answers, as_json, BASIC, status)


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
