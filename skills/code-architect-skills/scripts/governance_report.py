"""汇总体检、治理计划、执行复核和维护导读。"""

import argparse
import hashlib
import json
import os
import stat
import sys
import tempfile
from pathlib import Path

from governance_plan import DEFERRED, UNVERIFIED, build_plan
from necessary_docs import PENDING, required_text, table_row, text_list


PASSED = "通过"
REGRESSION = "发现差异"
RESOLVED = "已解决"
CHECK_KINDS = {"structure": "结构", "behavior": "行为", "handover": "交接"}
REPORT_PATH = Path("docs/code-architect-report.md")


def records(value, field):
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{field} 需要记录数组")
    return value


def review_checks(review, field):
    rows = []
    results = {}
    for index, check in enumerate(records(review.get("checks", []), f"{field}.checks")):
        prefix = f"{field}.checks[{index}]"
        kind = required_text(check.get("kind"), f"{prefix}.kind")
        if kind not in CHECK_KINDS:
            raise ValueError(f"{prefix}.kind 需要 structure、behavior 或 handover")
        result = check.get("result")
        if result not in (PASSED, REGRESSION, UNVERIFIED):
            raise ValueError(f"{prefix}.result 需要通过、发现差异或待验证")
        operation, expected, observed = (
            required_text(check.get(key), f"{prefix}.{key}")
            for key in ("operation", "expected", "observed")
        )
        rows.append(table_row((CHECK_KINDS[kind], operation, expected, observed, result)))
        results.setdefault(kind, set()).add(result)
    return rows, results


def render_reviews(reviews, selected):
    reviews = records(reviews, "reviews")
    if len(reviews) != len(selected):
        raise ValueError("reviews 需要按计划顺序逐项记录所有已纳入事项的结果")
    lines = ["## 执行复核"] if reviews else []
    passed = set()
    for index, ((target, title), review) in enumerate(zip(selected.items(), reviews)):
        field = f"reviews[{index}]"
        if review.get("target") != target:
            raise ValueError(f"{field}.target 需要按计划顺序对应 {target}")
        status = review.get("status")
        if status not in (PASSED, REGRESSION, UNVERIFIED, PENDING, DEFERRED, RESOLVED):
            raise ValueError(f"{field}.status 需要通过、发现差异、待验证、待确认、暂缓或已解决")
        checks, results = review_checks(review, field)
        outcomes = set().union(*results.values())
        changes = review.get("changes")
        lines.extend(["", f"### {index + 1}. {title}", "", f"**结果**　{status}"])
        if status in (PASSED, REGRESSION) or changes is not None:
            lines.extend(["", f"**实际改动**　{required_text(changes, f'{field}.changes')}"])
        if status == PASSED:
            kind = review.get("kind")
            if kind not in ("code", "handover"):
                raise ValueError(f"{field}.kind 需要 code 或 handover")
            required = {"structure", "behavior"} if kind == "code" else {"handover"}
            if outcomes != {PASSED} or not required.issubset(results):
                raise ValueError(f"{field}.checks 缺少全部通过的{kind}验收证据")
            passed.add(target)
        else:
            if status == REGRESSION and REGRESSION not in outcomes:
                raise ValueError(f"{field}.checks 需要记录实际差异及失败样例")
            if status != REGRESSION:
                lines.extend(["", f"**原因**　{required_text(review.get('reason'), f'{field}.reason')}"])
            if changes is not None:
                rollback = review.get("rollback")
                if not isinstance(rollback, dict) or rollback.get("status") not in ("已回退", "部分回退", "保留现场"):
                    raise ValueError(f"{field}.rollback 需要已回退、部分回退或保留现场的记录")
                evidence = required_text(rollback.get("evidence"), f"{field}.rollback.evidence")
                lines.extend(["", f"**回退复核**　{rollback['status']}。{evidence}"])
        if "preexisting" in review:
            original = required_text(review["preexisting"], f"{field}.preexisting")
            lines.extend(["", f"**改前已有差异**　{original}"])
        if checks:
            lines.extend([
                "", "| 验收 | 实际操作 | 预期 | 观察结果 | 结论 |",
                "| --- | --- | --- | --- | --- |", *checks,
            ])
    return "\n".join(lines), passed


def render_guide(record, passed):
    guide = records(record.get("guide"), "guide")
    lines = ["## 维护导读"]
    for index, entry in enumerate(guide):
        field = f"guide[{index}]"
        if "target" in entry:
            target = required_text(entry["target"], f"{field}.target")
            if target not in passed:
                raise ValueError(f"{field}.target 的改动通过复核后才能作为当前维护入口")
        task, location, callers = (
            required_text(entry.get(key), f"{field}.{key}") for key in ("task", "entry", "callers")
        )
        evidence = "、".join(text_list(entry.get("evidence"), f"{field}.evidence"))
        checks = text_list(entry.get("checks"), f"{field}.checks")
        lines.extend([
            "", f"### {task}", "", f"- **当前入口**　{location}",
            f"- **受影响的调用方**　{callers}", f"- **核对依据**　{evidence}",
            "", "自查步骤", "", *(f"{number}. {check}" for number, check in enumerate(checks, 1)),
        ])
    if not guide or "guide_limit" in record:
        limit = required_text(record.get("guide_limit"), "guide_limit")
        lines.extend(["", f"**可见范围与待核实事项**　{limit}"])
    return "\n".join(lines)


def render_report(record):
    if not isinstance(record, dict):
        raise ValueError("治理报告记录需要 JSON 对象")
    audit = record.get("audit")
    if not isinstance(audit, list) or not audit or any(not isinstance(item, str) or not item.strip() for item in audit):
        raise ValueError("audit 需要非空体检章节数组")
    plan, selected = build_plan(record.get("plan"))
    review, passed = render_reviews(record.get("reviews"), selected)
    guide = render_guide(record, passed)
    sections = ["# 代码架构治理报告", *(item.strip() for item in audit), plan.rstrip(), review, guide]
    return "\n\n".join(section for section in sections if section) + "\n"


def managed_report(body):
    digest = hashlib.sha256(body).hexdigest()
    return f"<!-- code-architect-skills sha256={digest} -->\n\n".encode("ascii") + body


def publish_report(report):
    path = REPORT_PATH
    if path.parent.is_symlink() or path.is_symlink():
        return False
    before = None
    if path.exists():
        if not path.is_file():
            return False
        before = path.read_bytes()
        _, _, body = before.partition(b"\n\n")
        if before != managed_report(body):
            return False
    content = managed_report(report.encode("utf-8"))
    if before == content:
        return True

    path.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=path.parent, prefix=".code-architect-") as directory:
        staged = Path(directory) / path.name
        staged.write_bytes(content)
        if before is None:
            os.link(staged, path)
        else:
            if path.is_symlink() or not path.is_file() or path.read_bytes() != before:
                return False
            staged.chmod(stat.S_IMODE(path.stat().st_mode))
            staged.replace(path)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", nargs="?", type=Path, help="治理报告 JSON，默认读取标准输入")
    parser.add_argument("--write", action="store_true", help="将报告写入当前仓库，无法安全写入时输出全文")
    args = parser.parse_args()
    try:
        if args.record is None:
            record = json.load(sys.stdin)
        else:
            record = json.loads(args.record.read_text(encoding="utf-8"))
        report = render_report(record)
    except (OSError, ValueError) as error:
        parser.exit(2, f"治理报告无法汇总（{error}）\n")
    if args.write:
        try:
            if publish_report(report):
                print(REPORT_PATH)
                return
            print(f"保留已有的 {REPORT_PATH}，请在会话交付报告全文。", file=sys.stderr)
        except OSError as error:
            print(f"无法写入 {REPORT_PATH}（{error}），请在会话交付报告全文。", file=sys.stderr)
    sys.stdout.write(report)


if __name__ == "__main__":
    main()
