"""将图件和源码对照记录汇总为架构图体检章节。"""

import argparse
import json
import sys
from pathlib import Path

from inspection_coverage import assessment, inspection_output, selected_checks
from necessary_docs import (
    COVERED, GAP, NOT_APPLICABLE, PENDING, project_summary, required_text, table_row, text_list, unread_notes,
)


REQUIRED = "需要"
MATCH = "一致"
STALE = "与实现不符"
OMISSION = "缺少关键关系"


def diagram_rows(diagrams):
    if not isinstance(diagrams, list):
        raise ValueError("diagrams 需要数组，未找到图件时传入 []")
    rows = []
    comparisons = []
    for diagram in diagrams:
        if not isinstance(diagram, dict):
            raise ValueError("diagrams 的每项需要图件记录")
        source = required_text(diagram.get("source"), "diagrams.source")
        kind = diagram.get("kind")
        if kind == "product":
            detail = required_text(diagram.get("detail"), "diagrams.detail")
            rows.append(table_row((source, "产品功能图", "—", "—", detail, "—")))
            continue
        if kind != "implementation":
            raise ValueError("diagrams.kind 需要 implementation 或 product")
        checks = diagram.get("checks")
        if not isinstance(checks, list) or not checks:
            raise ValueError("实现视图的 diagrams.checks 需要非空数组")
        for check in checks:
            if not isinstance(check, dict):
                raise ValueError("diagrams.checks 的每项需要对照记录")
            claim = required_text(check.get("claim"), "diagrams.checks.claim")
            result = required_text(check.get("result"), "diagrams.checks.result")
            if result not in (MATCH, STALE, OMISSION, PENDING):
                raise ValueError(f"diagrams.checks.result 含未知状态 {result}")
            detail = required_text(check.get("detail"), "diagrams.checks.detail")
            evidence = text_list(check.get("evidence"), "diagrams.checks.evidence")
            rows.append(table_row((source, "实现视图", claim, result, detail, "、".join(evidence))))
            comparisons.append((result, f"{claim}。{detail}", [source, *evidence], check))
    return rows, comparisons


def assess_diagrams(need, results, has_diagrams, has_unread):
    if STALE in results:
        return GAP, "实现视图与当前实现不符，差异见图件对照。"
    if need == NOT_APPLICABLE:
        return NOT_APPLICABLE, "本轮范围内无需交接模块关系，依据见适用性说明。"
    if need == PENDING:
        return PENDING, "本轮是否需要实现视图仍需核实。"
    if OMISSION in results:
        if has_unread:
            return PENDING, "已读图件缺少关键关系，尚需核对其余相关资料。"
        return GAP, "实现视图缺少本轮交接需要的关键关系。"
    if PENDING in results:
        return PENDING, "图中与本轮范围相关的关系尚未核实。"
    if MATCH in results:
        return COVERED, "已核实本轮范围内的关键关系。"
    if has_unread:
        return PENDING, "可见资料不足以确认本轮范围内是否有实现视图。"
    if has_diagrams:
        return GAP, "已查范围仅有产品功能图，缺少实现视图。"
    return GAP, "已查范围内缺少实现视图。"


def diagram_assessments(need, status, conclusion, comparisons, unread, repair, diagrams):
    if status == NOT_APPLICABLE:
        return [assessment("架构图", status, need["detail"], need["evidence"], need)]
    observations = []
    for result, detail, sources, check in comparisons:
        if result == STALE or (result == OMISSION and not unread and need["status"] == REQUIRED):
            observations.append(assessment("架构图", GAP, detail, sources, {**repair, **check}))
        else:
            outcome = COVERED if result == MATCH else PENDING
            observations.append(assessment("架构图", outcome, detail, sources, check))
    if not observations or need["status"] == PENDING:
        # 缺图时，适用性依据和已检索的产品图支持这个范围的结论。
        outcome = PENDING if need["status"] == PENDING else status
        sources = [*need["evidence"], *(diagram["source"] for diagram in diagrams)]
        observations.append(assessment("架构图", outcome, f"{need['detail']} {conclusion}", sources,
                                       repair if outcome == GAP else need))
    return observations


def render_report(record, *, as_json=False):
    if not isinstance(record, dict):
        raise ValueError("检查记录需要 JSON 对象")
    summary = project_summary(record["project"]) if "project" in record else []
    selected = selected_checks(record, (), "架构图")
    scope = text_list(record.get("scope"), "scope")
    need = record.get("need")
    if not isinstance(need, dict) or need.get("status") not in (REQUIRED, NOT_APPLICABLE, PENDING):
        raise ValueError("need.status 需要为需要、不适用或待确认")
    detail = required_text(need.get("detail"), "need.detail")
    evidence = "、".join(text_list(need.get("evidence"), "need.evidence"))
    rows, comparisons = diagram_rows(record.get("diagrams"))
    results = {item[0] for item in comparisons}
    notes = unread_notes(record.get("unread"))
    status, conclusion = assess_diagrams(need["status"], results, bool(rows), bool(notes))
    completeness = PENDING if notes or PENDING in results or status == PENDING else "已核对本轮相关资料"

    lines = [
        "## 架构图", "", *summary,
        f"**检查结果**　{status}。{conclusion}",
        "", f"**资料完整性**　{completeness}",
        "", f"**适用性**　{need['status']}。{detail}（{evidence}）",
        "", "### 已查范围", "", *(f"- {item}" for item in scope),
    ]
    if rows:
        lines.extend([
            "", "### 图件对照", "",
            "| 图件位置 | 类型 | 核对内容 | 结果 | 说明 | 核对依据 |",
            "| --- | --- | --- | --- | --- | --- |", *rows,
        ])
    if notes:
        lines.extend(["", "### 未核实的资料", "", *notes])
    repair = {}
    if status == GAP:
        repair = record.get("repair")
        if not isinstance(repair, dict):
            raise ValueError("确认缺口时需要 repair")
        impact = required_text(repair.get("impact"), "repair.impact")
        placement = required_text(repair.get("placement"), "repair.placement")
        changes = text_list(repair.get("changes"), "repair.changes")
        lines.extend([
            "", "### 建议修订", "", f"**维护影响**　{impact}",
            "", f"**修订位置**　{placement}", "", *(f"- {change}" for change in changes),
        ])
    observations = diagram_assessments(need, status, conclusion, comparisons, notes, repair, record["diagrams"])
    gaps = [*notes, *(item["detail"] for item in observations if item["status"] == PENDING)]
    return inspection_output(lines, selected, {"架构图": "、".join(gaps)}, as_json, "架构图", observations)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", nargs="?", type=Path, help="检查记录 JSON，默认读取标准输入")
    parser.add_argument("--json", action="store_true", help="返回章节、覆盖记录和评分依据")
    args = parser.parse_args()
    try:
        if args.record is None:
            record = json.load(sys.stdin)
        else:
            record = json.loads(args.record.read_text(encoding="utf-8"))
        report = render_report(record, as_json=args.json)
    except (OSError, ValueError) as error:
        parser.exit(2, f"架构图记录无法汇总（{error}）\n")
    sys.stdout.write(report)


if __name__ == "__main__":
    main()
