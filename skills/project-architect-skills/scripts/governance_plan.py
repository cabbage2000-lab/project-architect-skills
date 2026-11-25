"""校验按维护影响排序的治理候选，并生成本轮治理计划。"""

import argparse
import json
import sys
from pathlib import Path

from necessary_docs import PENDING, required_text, table_row, text_list


MAX_ITEMS = 3
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


def select_candidates(candidates, mode):
    targets = set()
    selected = {}
    deferred = []
    for index, candidate in enumerate(candidates):
        field = f"candidates[{index}]"
        if not isinstance(candidate, dict):
            raise ValueError(f"{field} 需要治理候选记录")
        target = required_text(candidate.get("target"), f"{field}.target")
        if target in targets:
            raise ValueError(f"{field}.target 重复，请合并同一治理目标的证据（{target}）")
        targets.add(target)

        title = required_text(candidate.get("title"), f"{field}.title")
        evidence = "、".join(text_list(candidate.get("evidence"), f"{field}.evidence"))
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
            details = {
                "优先理由": reason,
                "维护影响": impact,
                "核对依据": evidence,
            }
            for key, label in PLAN_FIELDS.items():
                details[label] = required_text(candidate.get(key), f"{field}.{key}")
            if len(selected) < MAX_ITEMS:
                selected[target] = (title, details)
                continue
            status, reason = DEFERRED, f"本轮已纳入 {MAX_ITEMS} 项，按维护影响顺延。"
        deferred.append((title, status, reason, impact, evidence))
    return selected, deferred


def build_plan(record, *, preview=False):
    if not isinstance(record, dict):
        raise ValueError("治理计划记录需要 JSON 对象")
    mode = record.get("mode")
    if mode not in ("execute", "inspect"):
        raise ValueError("mode 需要 execute 或 inspect")
    candidates = record.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("candidates 需要数组，无治理候选时传入 []")

    selected, deferred = select_candidates(candidates, mode)
    lines = ["## 治理计划", ""]
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
    return "\n".join(lines) + "\n", {target: title for target, (title, _) in selected.items()}


def render_report(record, *, preview=False):
    return build_plan(record, preview=preview)[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", nargs="?", type=Path, help="治理候选 JSON，默认读取标准输入")
    parser.add_argument("--preview", action="store_true", help="预览拟治理事项并在有入选项时提示授权")
    args = parser.parse_args()
    try:
        if args.record is None:
            record = json.load(sys.stdin)
        else:
            record = json.loads(args.record.read_text(encoding="utf-8"))
        report = render_report(record, preview=args.preview)
    except (OSError, ValueError) as error:
        parser.exit(2, f"治理计划无法汇总（{error}）\n")
    sys.stdout.write(report)


if __name__ == "__main__":
    main()
