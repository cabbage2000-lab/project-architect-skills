"""判断项目规模，或将交接证据汇总为必要文档体检章节。"""

import argparse
import json
import sys
from pathlib import Path


DOCUMENT_TOPICS = {
    "产品文档": {
        "purpose": "项目用途",
        "requirements": "主要流程与业务规则",
    },
    "技术文档": {
        "usage": "启动或最小使用示例",
        "configuration": "必要配置",
        "api": "API 说明",
    },
    "架构文档": {"architecture": "模块职责与依赖"},
    "测试文档": {"verification": "验证改动的方法"},
    "部署文档": {"deployment": "部署说明"},
}
TOPICS = {key: label for topics in DOCUMENT_TOPICS.values() for key, label in topics.items()}
LEGACY_TOPICS = {"purpose", "usage", "configuration", "verification", "deployment", "api"}
COVERED = "范围内未发现"
GAP = "发现问题"
PENDING = "待确认"
NOT_APPLICABLE = "不适用"
GAP_KINDS = {
    "missing": "缺少说明",
    "incomplete": "内容不完整",
    "stale": "与实现不符",
}


def required_text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} 需要非空文本")
    return " ".join(value.strip().splitlines())


def text_list(value, field):
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} 需要非空文本数组")
    return [required_text(item, field) for item in value]


def classify_project(units, files):
    for field, count in (("units", units), ("files", files)):
        if count is not None and (type(count) is not int or count < 0):
            raise ValueError(f"{field} 需要非负整数或未核实值")
    if (units is not None and units >= 6) or (files is not None and files > 500):
        return "大项目"
    if units is None or files is None:
        return PENDING
    if units >= 2 or files > 50:
        return "中等项目"
    return "小项目"


def project_summary(project):
    if not isinstance(project, dict):
        raise ValueError("project 需要规模记录")
    units = project.get("units")
    files = project.get("files")
    size = classify_project(units, files)
    evidence = text_list(project.get("evidence"), "project.evidence")
    focus = required_text(project.get("focus"), "project.focus")
    units_label = "待核实" if units is None else f"{units} 个"
    files_label = "待核实" if files is None else f"{files} 个"
    return [
        f"**项目规模**　{size}（独立维护单元 {units_label}，自维护文件 {files_label}）",
        "", f"**规模依据**　{'、'.join(evidence)}",
        "", f"**本轮检查重点**　{focus}",
        "",
    ]


def unread_sources(entries):
    if not isinstance(entries, list):
        raise ValueError("unread 需要数组，相关资料均已核对时传入 []")
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("unread 的每项需要 source 和 reason")
        source = required_text(entry.get("source"), "unread.source")
        reason = required_text(entry.get("reason"), "unread.reason")
        yield entry, source, reason


def unread_notes(entries):
    return [f"- {source}（{reason}）。" for _, source, reason in unread_sources(entries)]


def read_limits(entries):
    notes = []
    affected = {key: [] for key in TOPICS}
    for entry, source, reason in unread_sources(entries):
        keys = text_list(entry.get("topics", list(TOPICS)), "unread.topics")
        for key in keys:
            if key not in TOPICS:
                raise ValueError(f"unread.topics 含未知检查项 {key}")
            affected[key].append(source)
        labels = "、".join(TOPICS[key] for key in keys)
        notes.append(f"{source}（{reason}）。涉及{labels}。")
    return notes, affected


def table_row(cells):
    return "| " + " | ".join(cell.replace("|", r"\|") for cell in cells) + " |"


def assess_topic(key, item, unread_sources):
    if not isinstance(item, dict):
        raise ValueError(f"topics.{key} 需要检查记录")
    status = required_text(item.get("status"), f"{key}.status")
    if status not in (COVERED, GAP, PENDING, NOT_APPLICABLE):
        raise ValueError(f"{key}.status 含未知状态 {status}")
    detail = required_text(item.get("detail"), f"{key}.detail")
    evidence = text_list(item.get("evidence"), f"{key}.evidence")

    label = TOPICS[key]
    candidate = None
    if status == GAP and unread_sources:
        status = PENDING
        detail = f"已查范围内的记录为「{detail}」。仍需核对{'、'.join(unread_sources)}。"
    elif status == GAP:
        impact = required_text(item.get("impact"), f"{key}.impact")
        placement = required_text(item.get("placement"), f"{key}.placement")
        if "gap_kind" in item:
            kind = required_text(item["gap_kind"], f"{key}.gap_kind")
            if kind not in GAP_KINDS:
                raise ValueError(f"{key}.gap_kind 含未知缺口类型 {kind}")
            detail = f"**{GAP_KINDS[kind]}**　{detail}"
        candidate = f"- **{label}**　{impact} **补写位置**　{placement}"
    return status, table_row((label, status, detail, "、".join(evidence))), candidate


def overall_status(states, incomplete):
    if GAP in states:
        return GAP
    if incomplete:
        return PENDING
    if states == {NOT_APPLICABLE}:
        return NOT_APPLICABLE
    return COVERED


def render_report(record):
    if not isinstance(record, dict):
        raise ValueError("检查记录需要 JSON 对象")
    summary = project_summary(record["project"]) if "project" in record else []
    scope = text_list(record.get("scope"), "scope")
    notes, affected = read_limits(record.get("unread"))
    topics = record.get("topics")
    if not isinstance(topics, dict) or topics.keys() not in (TOPICS.keys(), LEGACY_TOPICS):
        raise ValueError(f"topics 需要完整的检查项 {'、'.join(TOPICS)}，也兼容旧版六项记录")

    sections = []
    suggestions = []
    states = set()
    for category, checks in DOCUMENT_TOPICS.items():
        rows = []
        candidates = []
        for key, label in checks.items():
            if key in topics:
                status, row, candidate = assess_topic(key, topics[key], affected[key])
            else:
                status = PENDING
                row = table_row((label, status, "旧版记录未包含此项，需补查。", "—"))
                candidate = None
            states.add(status)
            rows.append(row)
            if candidate:
                candidates.append(candidate)

        sections.extend([
            "", f"#### {category}", "",
            "| 内容 | 状态 | 当前结论 | 核对依据 |",
            "| --- | --- | --- | --- |",
            *rows,
        ])
        if candidates:
            suggestions.extend(["", f"#### {category}", "", *candidates])

    incomplete = bool(notes) or PENDING in states
    lines = [
        "## 必要文档", "",
        *summary,
        f"**检查结果**　{overall_status(states, incomplete)}",
        "", f"**项目资料完整性**　{PENDING if incomplete else '已核对本轮相关资料'}",
        "", "### 已查范围", "",
        *(f"- {location}" for location in scope),
        "", "### 按文档类别检查", *sections,
    ]
    if notes:
        lines.extend(["", "### 未核实的资料", "", *(f"- {note}" for note in notes)])
    if suggestions:
        lines.extend(["", "### 建议补写", *suggestions])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", nargs="?", type=Path, help="检查记录 JSON，默认读取标准输入")
    parser.add_argument(
        "--project-size", nargs=2, metavar=("UNITS", "FILES"),
        help="按独立维护单元数和自维护文件数判断规模，未知值用 -",
    )
    args = parser.parse_args()
    if args.project_size is not None:
        if args.record is not None:
            parser.error("--project-size 不能与检查记录路径同时使用")
        try:
            units, files = (None if value == "-" else int(value) for value in args.project_size)
            size = classify_project(units, files)
        except ValueError:
            parser.error("UNITS 和 FILES 需要非负整数或 -")
        print(size)
        return

    try:
        if args.record is None:
            record = json.load(sys.stdin)
        else:
            record = json.loads(args.record.read_text(encoding="utf-8"))
        report = render_report(record)
    except (OSError, ValueError) as error:
        parser.exit(2, f"检查记录无法汇总（{error}）\n")
    sys.stdout.write(report)


if __name__ == "__main__":
    main()
