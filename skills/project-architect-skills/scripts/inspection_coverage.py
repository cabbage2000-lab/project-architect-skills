"""按派发前的检查项和模块核对回传范围。"""

import json

from report_fields import required_text, table_row


def indexed_units(rows, field):
    if not isinstance(rows, list):
        raise ValueError(f"coverage.{field} 需要数组")
    units = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"coverage.{field} 需要检查项和范围记录")
        key = tuple(required_text(row.get(name), f"coverage.{field}.{name}") for name in ("check", "unit"))
        if key in units:
            raise ValueError(f"coverage.{field} 中的检查范围重复：{key}")
        units[key] = row
    return units


def selected_checks(record, supported):
    """一份专家取证记录对应一个模块，复用派发清单中的原始键。"""
    if "selected" not in record:
        return {}
    pairs = indexed_units(record["selected"], "selected")
    if len({unit for check, unit in pairs}) != 1:
        raise ValueError("selected 需要同一模块或入口的非空清单，不同模块分别提交记录")
    selected = {check: unit for check, unit in pairs}
    unknown = selected.keys() - supported.keys()
    if unknown:
        raise ValueError(f"selected 含不支持的专项检查：{'、'.join(sorted(unknown))}")
    return selected


def inspection_output(lines, selected, answers, as_json):
    results = []
    for check, unit in selected.items():
        row = {"check": check, "unit": unit}
        if check not in answers:
            row.update(status="未查", reason="未收到该范围的检查结果")
        elif answers[check]:
            row.update(status="部分已查", reason=answers[check])
        else:
            row["status"] = "已查"
        results.append(row)
    if selected:
        scope = [{"check": check, "unit": unit} for check, unit in selected.items()]
        lines.extend(["", "### 专项核对", "", *coverage_lines({"selected": scope, "results": results})])
    markdown = "\n".join(lines).rstrip("\n") + "\n"
    if as_json:
        return json.dumps({"markdown": markdown, "results": results}, ensure_ascii=False) + "\n"
    return markdown


def coverage_lines(coverage):
    if not isinstance(coverage, dict):
        raise ValueError("coverage 需要范围记录")
    selected = indexed_units(coverage.get("selected"), "selected")
    results = indexed_units(coverage.get("results"), "results")
    excluded = indexed_units(coverage.get("excluded", []), "excluded")
    if results.keys() - selected.keys():
        raise ValueError("coverage.results 含选定范围以外的回传")
    if excluded.keys() & selected.keys():
        raise ValueError("coverage.excluded 与选定范围重叠")

    rows = []
    completed = 0
    for check, unit in selected:
        result = results.get((check, unit))
        if result is None:
            status, reason = "未查", "未收到该范围的检查结果"
        else:
            status = result.get("status")
            if status not in ("已查", "部分已查", "未查"):
                raise ValueError("coverage.results.status 需要已查、部分已查或未查")
            reason = "" if status == "已查" else required_text(result.get("reason"), "coverage.results.reason")
        completed += status == "已查"
        rows.append(table_row((check, unit, status, reason)))
    for (check, unit), row in excluded.items():
        rows.append(table_row((check, unit, "范围外", required_text(row.get("reason"), "coverage.excluded.reason"))))
    return [
        f"本轮选定 {len(selected)} 项检查范围，完整核对 {completed} 项。",
        "", "| 检查项 | 模块或入口 | 核对情况 | 原因 |", "| --- | --- | --- | --- |", *rows, "",
    ]
