"""校验按维护影响排序的治理候选，并生成本轮治理计划。"""

import argparse
import json
import sys
from pathlib import Path

from health_score import prepare_score, score_section
from inspection_coverage import coverage_lines
from necessary_docs import PENDING, required_text, table_row, text_list
from plan_evidence import check_sources


READY = "可执行"
UNVERIFIED = "待验证"
DEFERRED = "暂缓"
NOT_RUN = "未执行"
PLAN_FIELDS = {
    "scope": "目标与范围",
    "baseline": "改前基线",
    "steps": "执行步骤",
    "acceptance": "验收方法",
    "rollback": "回退办法",
}


def select_candidates(candidates, mode, root=None):
    targets = set()
    selected = {}
    deferred = []
    checked = []
    for index, candidate in enumerate(candidates):
        field = f"candidates[{index}]"
        if not isinstance(candidate, dict):
            raise ValueError(f"{field} 需要治理候选记录")
        target = required_text(candidate.get("target"), f"{field}.target")
        if target in targets:
            raise ValueError(f"{field}.target 重复，请合并同一治理目标的证据（{target}）")
        targets.add(target)

        title = required_text(candidate.get("title"), f"{field}.title")
        sources = text_list(candidate.get("evidence"), f"{field}.evidence")
        impact = required_text(candidate.get("impact"), f"{field}.impact")
        reason = required_text(candidate.get("reason"), f"{field}.reason")
        status = candidate.get("status")
        if status not in (READY, PENDING, UNVERIFIED, DEFERRED, NOT_RUN):
            raise ValueError(f"{field}.status 需要可执行、待确认、待验证、暂缓或未执行")

        if mode == "inspect":
            if status in (PENDING, UNVERIFIED, DEFERRED):
                reason = f"{status}。{reason}"
            status = NOT_RUN
        elif status == NOT_RUN:
            raise ValueError(f"{field}.status 在 execute 模式下需要写明暂缓类型")
        elif status == READY:
            requirements = {
                label: required_text(candidate.get(key), f"{field}.{key}") for key, label in PLAN_FIELDS.items()
            }
            if root is not None:
                usable, issues = check_sources(sources, root)
                if issues:
                    reason += " 待核实出处：" + "、".join(issues) + "。"
                    if usable:
                        sources = usable
                    else:
                        status = PENDING
        checked.append({**candidate, "status": status, "evidence": sources, "reason": reason})
        evidence = "、".join(sources)
        if status == READY:
            details = {
                "优先理由": reason,
                "维护影响": impact,
                "核对依据": evidence,
                **requirements,
            }
            selected[target] = (title, details)
            continue
        deferred.append((title, status, reason, impact, evidence))
    return selected, deferred, checked


def prepare_plan(record, *, preview=False, root=None, include_score=True):
    if not isinstance(record, dict):
        raise ValueError("治理计划记录需要 JSON 对象")
    mode = record.get("mode")
    if mode not in ("execute", "inspect"):
        raise ValueError("mode 需要 execute 或 inspect")
    candidates = record.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("candidates 需要数组，无治理候选时传入 []")

    selected, deferred, checked = select_candidates(candidates, mode, root)
    lines = ["## 治理计划", ""]
    if "coverage" in record:
        lines.extend(coverage_lines(record["coverage"]))
    if selected:
        if preview:
            lines.append(f"本轮拟治理 {len(selected)} 项，待授权。")
        else:
            lines.append(f"本轮按以下顺序执行 {len(selected)} 项。")
        for number, (title, details) in enumerate(selected.values(), 1):
            lines.extend(["", f"### {number}. {title}", ""])
            lines.extend(f"- **{label}**　{value}" for label, value in details.items())
    elif mode == "inspect" and deferred:
        lines.append("本轮仅交付治理建议。")
    else:
        lines.append("本轮无可执行的治理事项。")
    if deferred:
        lines.extend([
            "", "### 未纳入本轮执行", "",
            "| 发现 | 状态 | 原因 | 维护影响 | 核对依据 |",
            "| --- | --- | --- | --- | --- |", *(table_row(row) for row in deferred),
        ])
    if preview and selected:
        lines.extend(["", "请在当前会话回复 **同意治理**，我会按以上计划逐项修复和验收。"])
    titles = {target: title for target, (title, _) in selected.items()}
    checked_plan = {**record, "candidates": checked}
    if include_score and "scoring" in record:
        checked_plan["scoring"], baseline = prepare_score(record["scoring"], record.get("coverage"), root=root)
        if root is not None:
            checked_plan["scoring"]["evidence_checked"] = True
        lines = [score_section(baseline), "", *lines]
    return "\n".join(lines) + "\n", titles, checked_plan


def build_plan(record, *, preview=False, replay=False, include_score=True):
    root = None if replay else Path.cwd()
    report, titles, _ = prepare_plan(record, preview=preview, root=root, include_score=include_score)
    return report, titles


def render_report(record, *, preview=False):
    return build_plan(record, preview=preview)[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", nargs="?", type=Path, help="治理候选 JSON，默认读取标准输入")
    parser.add_argument("--preview", action="store_true", help="预览拟治理事项并在有入选项时提示授权")
    parser.add_argument("--json", action="store_true", help="同时返回 Markdown 和本次检查后的 plan 记录")
    args = parser.parse_args()
    try:
        if args.record is None:
            record = json.load(sys.stdin)
        else:
            record = json.loads(args.record.read_text(encoding="utf-8"))
        report, _, checked = prepare_plan(record, preview=args.preview, root=Path.cwd())
        if args.json:
            report = json.dumps({"markdown": report, "plan": checked}, ensure_ascii=False) + "\n"
    except (OSError, ValueError) as error:
        parser.exit(2, f"治理计划无法汇总（{error}）\n")
    sys.stdout.write(report)


if __name__ == "__main__":
    main()
