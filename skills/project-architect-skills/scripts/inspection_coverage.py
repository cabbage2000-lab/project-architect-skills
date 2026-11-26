"""按派发前的检查项和模块核对回传范围。"""

from necessary_docs import required_text, table_row


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
