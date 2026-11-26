"""用已核实的体检记录计算四项得分，保留可重放的治理前基线。"""

from collections import defaultdict
from dataclasses import dataclass, field

from code_smells import MODULE_ISSUES, SMELLS
from inspection_coverage import coverage_units
from necessary_docs import COVERED, GAP, NOT_APPLICABLE, PENDING, TOPICS, V1_DOCUMENT_TOPICS, V2_DOCUMENT_TOPICS
from plan_evidence import check_sources
from report_fields import records, required_text, table_row, text_list


VERSION = 3
BASIC = {"必要文档": "必要文档", "架构图": "架构", "目录结构": "目录结构", "代码异味": "代码异味"}
DIMENSIONS = tuple(BASIC.values())
DIMENSION_LABELS = {"必要文档": "工程文档", "架构": "软件架构", "目录结构": "仓库结构", "代码异味": "代码质量"}
CHECK_DIMENSION = {
    **BASIC, **dict.fromkeys(TOPICS, "必要文档"), **dict.fromkeys(SMELLS | MODULE_ISSUES, "代码异味"),
    "architecture_drift": "架构",
}
FULL_CRITERIA_BY_VERSION = {
    1: {"必要文档": V1_DOCUMENT_TOPICS, "代码异味": SMELLS.keys()},
    2: {"必要文档": V2_DOCUMENT_TOPICS, "代码异味": SMELLS.keys()},
    VERSION: {"必要文档": TOPICS.keys(), "代码异味": SMELLS.keys()},
}
PENALTIES = {"轻微": 2, "需要绕行": 5, "阻断": 15}
MAX_POINTS = 25


@dataclass
class Dimension:
    units: list = field(default_factory=list)
    gaps: list = field(default_factory=list)
    not_applicable: list = field(default_factory=list)
    applicable: bool = False
    deductions: int = 0

    @property
    def points(self):
        if self.gaps or not self.applicable:
            return None
        return max(0, MAX_POINTS - self.deductions)


@dataclass
class Finding:
    owner: str
    severity: str
    detail: str
    impact: str
    evidence: list
    origins: set


@dataclass
class Snapshot:
    version: int
    scope: str
    selected: set
    excluded: set
    module_checks: set
    dimensions: dict
    findings: dict
    resolutions: dict

    @property
    def total(self):
        if self.scope != "full" or any(dim.gaps for dim in self.dimensions.values()):
            return None
        points = [dim.points for dim in self.dimensions.values() if dim.applicable]
        if points:
            return round(100 * sum(points) / (MAX_POINTS * len(points)), 1)
        return None


def checked_assessment(item, selected, results, root):
    check = required_text(item.get("check"), "assessments.check")
    unit = required_text(item.get("unit"), "assessments.unit")
    key = check, unit
    if key not in selected or results.get(key, {}).get("status", "未查") == "未查":
        raise ValueError(f"assessments 的 {key} 需要对应选定且已回传的检查范围")
    criterion = required_text(item.get("criterion", check), "assessments.criterion")
    if criterion != check and not (
        (check == "必要文档" and criterion in TOPICS) or
        (check == "代码异味" and (criterion in SMELLS or criterion in MODULE_ISSUES))
    ):
        raise ValueError(f"assessments.criterion {criterion} 超出 {check} 的判据")
    status = item.get("status")
    if status not in (COVERED, NOT_APPLICABLE, GAP, PENDING):
        raise ValueError("assessments.status 需要已核实的检查结论或待确认")
    detail = required_text(item.get("detail"), "assessments.detail")
    sources = item.get("evidence", [])
    evidence = [] if sources == [] else list(dict.fromkeys(text_list(sources, "assessments.evidence")))
    row = dict(check=check, unit=unit, criterion=criterion, status=status, detail=detail, evidence=evidence)
    if status == GAP:
        row["impact"] = required_text(item.get("impact"), "assessments.impact")
        for name in ("root_id", "severity"):
            if name in item:
                row[name] = required_text(item[name], f"assessments.{name}")
        if "severity" in row and row["severity"] not in PENALTIES:
            raise ValueError("assessments.severity 需要轻微、需要绕行或阻断")
    if status == GAP or (status == PENDING and "owner" in item):
        row["owner"] = required_text(item.get("owner", CHECK_DIMENSION[criterion]), "assessments.owner")
        if row["owner"] not in DIMENSIONS:
            raise ValueError("assessments.owner 需要四项评分维度之一")
    if "resolves" in item:
        if status not in (COVERED, NOT_APPLICABLE):
            raise ValueError("assessments.resolves 需要复查确认解决的结论")
        row["resolves"] = text_list(item["resolves"], "assessments.resolves")

    if status != PENDING:
        issues = []
        if root is not None and evidence:
            _, issues = check_sources(evidence, root, require_reference=True)
        if issues or not evidence:
            reason = "待核实出处：" + "、".join(issues) if issues else "缺少核对出处"
            row.update(status=PENDING, detail=f"{detail}（{reason}）")
            row.pop("resolves", None)
    return row


def assess_unit(key, result, rows, dim, groups, resolutions, required_criteria):
    check, unit = key
    label = f"{check} / {unit}"
    dim.units.append(label)
    if result.get("status") != "已查":
        reason = required_text(result.get("reason", "未收到该范围的检查结果"), "coverage.results.reason")
        dim.gaps.append(f"{label}：{reason}")
    if not rows:
        if result.get("status") == "已查":
            dim.gaps.append(f"{label} 缺少评分依据")
        return
    missing = required_criteria - {row["criterion"] for row in rows}
    if missing:
        dim.gaps.append(f"{label} 缺少判据 {'、'.join(sorted(missing))}")
    for row in rows:
        status = row["status"]
        if status == PENDING:
            dim.gaps.append(f"{unit}：{row['detail']}")
            continue
        if status == NOT_APPLICABLE:
            dim.not_applicable.append(f"{row['detail']}（{'、'.join(row['evidence'])}）")
        else:
            dim.applicable = True
        for root_id in row.get("resolves", []):
            resolutions[root_id].append(row)
        if status == GAP:
            if not row.get("root_id") or not row.get("severity"):
                dim.gaps.append(f"{unit}：{row['impact']}（待核实根因或影响档位）")
            else:
                groups[row["root_id"]].append(row)


def merge_finding(root_id, rows):
    owners = {row["owner"] for row in rows}
    if len(owners) != 1:
        raise ValueError(f"根因 {root_id} 的 assessments.owner 不一致，请核定主责维度")
    strongest = max(rows, key=lambda row: PENALTIES[row["severity"]])
    impacts = dict.fromkeys(row["impact"] for row in rows if row["severity"] == strongest["severity"])
    evidence = list(dict.fromkeys(source for row in rows for source in row["evidence"]))
    origins = {(row["check"], row["unit"], row["criterion"]) for row in rows}
    return Finding(strongest["owner"], strongest["severity"], strongest["detail"], "、".join(impacts), evidence, origins)


def prepare_score(scoring, coverage, *, root=None):
    """初次取证传 root 验证出处，重放时只使用计划已冻结的结论。"""
    version = scoring.get("version") if isinstance(scoring, dict) else None
    if type(version) is not int or version not in FULL_CRITERIA_BY_VERSION:
        raise ValueError("scoring.version 需要支持的规则版本 1、2 或 3")
    scope = scoring.get("scope")
    if scope not in ("full", "scoped"):
        raise ValueError("scoring.scope 需要 full 或 scoped")
    selected, results, excluded = coverage_units(coverage)
    unknown = {check for check, unit in selected} - CHECK_DIMENSION.keys()
    if unknown:
        raise ValueError(f"评分范围含未知检查项 {'、'.join(sorted(unknown))}")
    rows = [checked_assessment(item, selected, results, root)
            for item in records(scoring.get("assessments"), "scoring.assessments")]
    by_unit = defaultdict(dict)
    module_checks = set()
    checks = {check for check, unit in selected}
    used = {CHECK_DIMENSION[check] for check in checks}
    for row in rows:
        name = CHECK_DIMENSION[row["criterion"]]
        used.add(name)
        by_unit[row["check"], row["unit"]].setdefault(name, []).append(row)
        if row["check"] == "代码异味" and row["criterion"] in MODULE_ISSUES:
            module_checks.add((row["criterion"], row["unit"]))
    dimensions = {name: Dimension() for name in DIMENSIONS if scope == "full" or name in used}
    if scope == "full":
        for check in BASIC.keys() - checks:
            dimensions[BASIC[check]].gaps.append(f"未选定基础检查「{check}」")
    groups, resolutions = defaultdict(list), defaultdict(list)
    for check, unit in selected:
        key = check, unit
        primary = CHECK_DIMENSION[check]
        by_dimension = by_unit[key]
        by_dimension.setdefault(primary, [])
        for name, observations in by_dimension.items():
            # 基础代码检查也能回传架构漂移，保留原派发键，按具体判据归属分项。
            label = check if name == primary else "、".join(dict.fromkeys(row["criterion"] for row in observations))
            assess_unit((label, unit), results.get(key, {}), observations, dimensions[name], groups, resolutions,
                        FULL_CRITERIA_BY_VERSION[version].get(label, set()))
    for row in rows:
        owner = row.get("owner")
        if owner in dimensions and owner != CHECK_DIMENSION[row["criterion"]]:
            if row["status"] == PENDING or not (row.get("root_id") and row.get("severity")):
                dimensions[owner].gaps.append(f"{row['unit']}：{row['detail']}（归属本维度的扣分待核实）")
    findings = {root_id: merge_finding(root_id, items) for root_id, items in groups.items()}
    for root_id, finding in findings.items():
        if finding.owner not in dimensions:
            raise ValueError(f"根因 {root_id} 的主责维度 {finding.owner} 超出评分范围")
        dim = dimensions[finding.owner]
        if not dim.applicable and not dim.gaps:
            raise ValueError(f"根因 {root_id} 的主责维度 {finding.owner} 已全部判为不适用")
        dim.deductions += PENALTIES[finding.severity]
    snapshot = Snapshot(version, scope, set(selected), set(excluded), module_checks, dimensions, findings, resolutions)
    return {"version": version, "scope": scope, "assessments": rows}, snapshot


def render_snapshot(score, heading):
    lines = [f"### {heading}", ""]
    applicable = [dim for dim in score.dimensions.values() if dim.applicable]
    if score.scope == "scoped":
        summary = "**专项评分**　" + ("仅限下表所列的检查项和入口。" if score.dimensions else "尚未选定检查范围。")
    elif score.total is not None:
        points = sum(dim.points for dim in applicable)
        summary = f"**本轮总分**　{score.total:g}/100（实得 {points}/{MAX_POINTS * len(applicable)}）"
    elif any(dim.gaps for dim in score.dimensions.values()):
        summary = "**本轮总分**　待补查"
    else:
        summary = "**本轮总分**　无适用维度"
    blocked = [item.impact for item in score.findings.values() if item.severity == "阻断"]
    if blocked:
        summary += "　**阻断操作**　" + "、".join(dict.fromkeys(blocked))
    lines.append(summary)
    if score.dimensions:
        lines.extend(["", "| 维度 | 得分 | 核对范围 | 依据或缺口 |", "| --- | --- | --- | --- |"])
    for name, dim in score.dimensions.items():
        if dim.gaps:
            points, reasons = "待补查", dim.gaps
        elif dim.applicable:
            points = f"{dim.points}/{MAX_POINTS}"
            reasons = [f"累计扣 {dim.deductions} 分，按 {MAX_POINTS} 分封顶"] if dim.deductions > MAX_POINTS else []
        else:
            points, reasons = NOT_APPLICABLE, dim.not_applicable
        lines.append(table_row((DIMENSION_LABELS[name], points, "、".join(dim.units) or "—", "、".join(dict.fromkeys(reasons)) or "—")))
    if score.findings:
        lines.extend(["", "| 根因 | 主责维度 | 影响档位 | 扣分 | 实际发现与维护影响 | 出处 |",
                      "| --- | --- | --- | ---: | --- | --- |"])
        for root_id, item in score.findings.items():
            lines.append(table_row((root_id, DIMENSION_LABELS[item.owner], item.severity, str(PENALTIES[item.severity]),
                                    f"{item.detail} {item.impact}", "、".join(item.evidence))))
    return lines


def compare_findings(before, after):
    changes = []
    for root_id, rows in after.resolutions.items():
        if root_id not in before.findings or root_id in after.findings:
            raise ValueError(f"resolves 的根因 {root_id} 需要对应基线且已经消除")
        original = before.findings[root_id]
        if any((row["check"], row["unit"], row["criterion"]) not in original.origins for row in rows):
            raise ValueError(f"resolves 的根因 {root_id} 需要在原检查范围和判据下复核")
        for row in rows:
            changes.append(f"{root_id} 已消除。{row['detail']}（{'、'.join(row['evidence'])}）")
    for root_id, original in before.findings.items():
        current = after.findings.get(root_id)
        if current:
            if (original.owner, original.severity) != (current.owner, current.severity):
                changes.append(f"{root_id} 从{DIMENSION_LABELS[original.owner]}「{original.severity}」"
                               f"变为{DIMENSION_LABELS[current.owner]}「{current.severity}」。")
        elif root_id not in after.resolutions and any((check, unit) in after.selected for check, unit, _ in original.origins):
            dim = after.dimensions.get(original.owner)
            if dim is not None:
                dim.gaps.append(f"根因 {root_id} 缺少复查结论和消除依据")
    for root_id, finding in after.findings.items():
        if root_id not in before.findings:
            changes.append(f"新增根因 {root_id}。{finding.impact}")
    return changes


def score_change(before, after):
    if (before.scope != after.scope or before.selected != after.selected or before.excluded != after.excluded
            or before.module_checks != after.module_checks):
        return "检查范围已变化，本次得分分别展示。"
    if any(dim.gaps for score in (before, after) for dim in score.dimensions.values()):
        return "有待补查的维度，分数变化待核实。"
    previous = {name for name, dim in before.dimensions.items() if dim.applicable}
    current = {name for name, dim in after.dimensions.items() if dim.applicable}
    if previous != current:
        return "适用维度已变化，本次得分分别展示。"
    if after.total is not None:
        return f"**总分变化**　{before.total:g} → {after.total:g}（{after.total - before.total:+.1f} 分）"
    if after.scope == "scoped" and current:
        changes = [f"{DIMENSION_LABELS[name]} {dim.points - before.dimensions[name].points:+d} 分"
                   for name, dim in after.dimensions.items() if dim.applicable]
        return "**专项分数变化**　" + "、".join(changes)
    return "本轮无可比较的适用维度。"


def score_section(before, reassessment=None, *, root=None, expected=False):
    lines = ["## 项目体检评分", "", *render_snapshot(before, "体检基线")]
    if reassessment is None:
        if expected:
            lines.extend(["", "**治理后复评**　待补查，尚未收到原范围的复查记录。"])
        return "\n".join(lines)
    if not isinstance(reassessment, dict) or type(reassessment.get("version")) is not int:
        raise ValueError("reassessment.version 需要评分规则版本")
    if reassessment["version"] != before.version:
        lines.extend(["", f"**治理后复评**　规则版本已变化（v{before.version} → v{reassessment['version']}），本次无法按 v{before.version} 计分。"])
        return "\n".join(lines)
    _, after = prepare_score(reassessment, reassessment.get("coverage"), root=root)
    changes = compare_findings(before, after)
    lines.extend(["", *render_snapshot(after, "治理后复评"), "", score_change(before, after)])
    if changes:
        lines.extend(["", *(f"- {change}" for change in changes)])
    return "\n".join(lines)
