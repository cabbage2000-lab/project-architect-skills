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


def build_plan(record):
    if not isinstance(record, dict):
        raise ValueError("治理计划记录需要 JSON 对象")
    mode = record.get("mode")
    if mode not in ("execute", "inspect"):
        raise ValueError("mode 需要 execute 或 inspect")
    candidates = record.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("candidates 需要数组，无治理候选时传入 []")

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
            details = [
                f"- **{label}**　{required_text(candidate.get(key), f'{field}.{key}')}"
                for key, label in PLAN_FIELDS.items()
            ]
            if len(selected) < MAX_ITEMS:
                selected[target] = (title, [
                    f"### {len(selected) + 1}. {title}", "",
                    f"- **优先理由**　{reason}",
                    f"- **维护影响**　{impact}",
                    f"- **核对依据**　{evidence}",
                    *details,
                ])
                continue
            status, reason = DEFERRED, f"本轮已纳入 {MAX_ITEMS} 项，按维护影响顺延。"
        deferred.append(table_row((title, status, reason, impact, evidence)))

    lines = ["## 治理计划", ""]
    if selected:
        lines.append(f"本轮按以下顺序执行 {len(selected)} 项。")
        for _, item in selected.values():
            lines.extend(["", *item])
    elif mode == "inspect" and deferred:
        lines.append("本轮仅交付治理建议。")
    else:
        lines.append("本轮无可执行的治理事项。")
    if deferred:
        lines.extend([
            "", "### 未纳入本轮执行", "",
            "| 发现 | 状态 | 原因 | 维护影响 | 核对依据 |",
            "| --- | --- | --- | --- | --- |", *deferred,
        ])
    return "\n".join(lines) + "\n", {target: title for target, (title, _) in selected.items()}


def render_report(record):
    return build_plan(record)[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", nargs="?", type=Path, help="治理候选 JSON，默认读取标准输入")
    args = parser.parse_args()
    try:
        if args.record is None:
            record = json.load(sys.stdin)
        else:
            record = json.loads(args.record.read_text(encoding="utf-8"))
        report = render_report(record)
    except (OSError, ValueError) as error:
        parser.exit(2, f"治理计划无法汇总（{error}）\n")
    sys.stdout.write(report)


if __name__ == "__main__":
    main()
