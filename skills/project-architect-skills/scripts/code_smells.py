"""将方法级代码异味和模块诊断的证据汇总为 Markdown。"""

import argparse
import json
import sys
from pathlib import Path

from inspection_coverage import inspection_output, selected_checks
from necessary_docs import (
    COVERED, GAP, NOT_APPLICABLE, PENDING, overall_status, project_summary, required_text,
    table_row, text_list, unread_sources,
)


SMELLS = {
    "long_method": "长方法",
    "deep_nested_logic": "深层嵌套",
    "bumpy_road": "多段嵌套逻辑",
    "complex_conditional": "复杂条件表达式",
    "complex_method": "复杂方法",
}
MODULE_ISSUES = {
    "srp": "单一职责原则（SRP）",
    "ocp": "开闭原则（OCP）",
    "lsp": "里氏替换原则（LSP）",
    "isp": "接口隔离原则（ISP）",
    "dip": "依赖倒置原则（DIP）",
    "long_parameter_list": "长参数列表",
    "large_class": "大类",
    "data_clumps": "重复参数组",
    "feature_envy": "依恋其他类的数据",
    "inappropriate_intimacy": "类间过度耦合",
    "shotgun_surgery": "单个变化分散到多处",
    "divergent_change": "多种变化集中于一处",
    "refused_bequest": "拒用继承能力",
    "architecture_drift": "架构漂移",
    "mixed_responsibilities": "职责混杂",
    "duplicate_logic": "逻辑重复",
}
STATUSES = (COVERED, GAP, PENDING, NOT_APPLICABLE)


def method_findings(methods, selected):
    if not isinstance(methods, list):
        raise ValueError("methods 需要数组，无已确认的方法级发现时传入 []")
    lines, known_methods, found = [], set(), set()
    for method in methods:
        if not isinstance(method, dict):
            raise ValueError("methods 的每项需要函数记录")
        path = required_text(method.get("path"), "methods.path")
        symbol = required_text(method.get("symbol"), "methods.symbol")
        start, end = method.get("start"), method.get("end")
        if type(start) is not int or type(end) is not int or not 1 <= start <= end:
            raise ValueError("methods.start 和 methods.end 需要有效的函数起止行号")
        identity = path, symbol, start
        if identity in known_methods:
            raise ValueError(f"同一函数的发现须合并到一项：{path}:{start} {symbol}")
        known_methods.add(identity)
        impact = required_text(method.get("impact"), "methods.impact")
        findings = method.get("findings")
        if not isinstance(findings, list) or not findings:
            raise ValueError("methods.findings 需要非空数组")
        method_lines = []
        for finding in findings:
            if not isinstance(finding, dict):
                raise ValueError("methods.findings 的每项需要异味证据")
            kind = required_text(finding.get("kind"), "methods.findings.kind")
            if kind not in SMELLS:
                raise ValueError(f"methods.findings.kind 含未知类型 {kind}")
            if selected and kind not in selected:
                continue
            detail = required_text(finding.get("detail"), "methods.findings.detail")
            evidence = text_list(finding.get("evidence"), "methods.findings.evidence")
            if kind == "bumpy_road" and len(set(evidence)) < 2:
                raise ValueError("多段嵌套逻辑需要至少两处独立代码位置")
            found.add(kind)
            method_lines.append(f"  - **{SMELLS[kind]}**　{detail}（{'、'.join(evidence)}）")
        if not method_lines:
            continue
        lines.extend([f"- **{path}:{start}–{end} `{symbol}`**　{impact}", *method_lines])
        if "suggestion" in method:
            suggestion = required_text(method["suggestion"], "methods.suggestion")
            lines.append(f"  - 建议　{suggestion}")
    return lines, found


def check_rows(checks, found, selected):
    if not isinstance(checks, dict) or checks.keys() - SMELLS.keys():
        raise ValueError("checks 需要由已知方法异味组成的对象")
    if not selected and checks.keys() != SMELLS.keys():
        raise ValueError(f"checks 需要完整的五类异味：{'、'.join(SMELLS)}")
    if found - checks.keys():
        raise ValueError("checks 缺少已提交函数级证据对应的检查状态")
    rows, states, answers = [], set(), {}
    for kind, label in SMELLS.items():
        if selected and (kind not in selected or kind not in checks):
            continue
        check = checks[kind]
        if not isinstance(check, dict) or check.get("status") not in STATUSES:
            raise ValueError(f"checks.{kind}.status 需要有效的检查状态")
        status = check["status"]
        if (status == GAP) != (kind in found):
            raise ValueError(f"checks.{kind}.status 需要与函数级证据一致")
        detail = required_text(check.get("detail"), f"checks.{kind}.detail")
        states.add(status)
        answers[kind] = detail if status == PENDING else ""
        if status != GAP and "evidence" in check:
            evidence = text_list(check["evidence"], f"checks.{kind}.evidence")
            detail += f"（{'、'.join(evidence)}）"
        rows.append(table_row((label, status, detail)))
    return rows, states, answers


def module_findings(entries, selected):
    if not isinstance(entries, list):
        raise ValueError("modules 需要数组")
    lines, states, answers = [], set(), {}
    for item in entries:
        if not isinstance(item, dict) or item.get("status") not in STATUSES:
            raise ValueError("modules 的每项需要有效的检查状态")
        status = item["status"]
        kind = required_text(item.get("kind"), "modules.kind")
        if kind not in MODULE_ISSUES:
            raise ValueError(f"modules.kind 含未知类型 {kind}")
        if selected and kind not in selected:
            continue
        title = required_text(item.get("title"), "modules.title")
        detail = required_text(item.get("detail"), "modules.detail")
        evidence = text_list(item.get("evidence"), "modules.evidence")
        if status == GAP and len(set(evidence)) < 2:
            raise ValueError("已确认的模块诊断需要至少两处依据")
        display_evidence = evidence
        if status == GAP and selected and kind == "architecture_drift":
            if evidence[0] == evidence[1]:
                raise ValueError("架构漂移需要分别给出分层约定和实际调用的出处")
            display_evidence = [f"分层约定 {evidence[0]}", f"实际调用 {evidence[1]}", *evidence[2:]]
        lines.append(f"- **{MODULE_ISSUES[kind]} · {title}**　{status}。{detail}（{'、'.join(display_evidence)}）")
        if status == GAP:
            impact = required_text(item.get("impact"), "modules.impact")
            lines.append(f"  - 维护影响　{impact}")
            if "suggestion" in item:
                suggestion = required_text(item["suggestion"], "modules.suggestion")
                lines.append(f"  - 建议　{suggestion}")
        states.add(status)
        answers.setdefault(kind, "")
        if status == PENDING:
            answers[kind] = detail
    return lines, states, answers


def render_report(record, *, as_json=False):
    if not isinstance(record, dict):
        raise ValueError("检查记录需要 JSON 对象")
    summary = project_summary(record["project"]) if "project" in record else []
    scope = text_list(record.get("scope"), "scope")
    notes = [f"{source}（{reason}）" for _, source, reason in unread_sources(record.get("unread"))]
    dispatched = selected_checks(record, SMELLS | MODULE_ISSUES, "代码异味")
    selected = {} if "代码异味" in dispatched else dispatched
    methods, found = method_findings(record.get("methods", [] if selected else None), selected)
    rows, states, answers = check_rows(record.get("checks", {}), found, selected)
    modules, module_states, module_answers = module_findings(record.get("modules", []), selected)
    answers.update(module_answers)
    states.update(module_states)
    if dispatched and notes:
        for kind, reason in answers.items():
            answers[kind] = reason or "尚未核对" + "、".join(notes)
    if selected.keys() - answers.keys():
        states.add("未查")
    coverage_incomplete = bool(notes) or PENDING in states

    heading = "## 架构依赖检查" if selected.keys() == {"architecture_drift"} else "## 代码异味"
    lines = [
        heading, "", *summary,
        f"**检查结果**　{overall_status(states, coverage_incomplete)}",
        "", "### 已查范围", "", *(f"- {source}" for source in scope),
    ]
    if rows:
        lines.extend(["", "### 方法级检查", "", "| 异味 | 状态 | 核对口径与结论 |",
                      "| --- | --- | --- |", *rows])
    if methods:
        lines.extend(["", "### 方法级治理候选", "", *methods])
    if modules:
        lines.extend(["", "### 模块层面关联诊断", "", *modules])
    if notes:
        lines.extend(["", "### 未核实的资料", "", *(f"- {note}。" for note in notes)])
    return inspection_output(lines, dispatched, answers, as_json, "代码异味")


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
        parser.exit(2, f"代码异味记录无法汇总（{error}）\n")
    sys.stdout.write(report)


if __name__ == "__main__":
    main()
