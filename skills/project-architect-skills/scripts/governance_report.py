"""汇总质检、治理计划、执行复核和维护导读。"""

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path

from behavior_verification import SPECIALTY_LABELS
from directory_structure import GENERATED, GENERATED_LABEL
from governance_plan import DEFERRED, UNVERIFIED, build_plan
from inspection_coverage import coverage_units
from necessary_docs import PENDING, required_text, table_row, text_list
from plan_evidence import check_sources, location_issue
from report_fields import labeled_fields, records
from report_publication import matches, refresh_managed


PASSED = "通过"
REGRESSION = "发现差异"
RESOLVED = "已解决"
CHECK_KINDS = {"structure": "结构", "behavior": "行为", "handover": "交接"}
REPORT_PATH = Path("docs/project-architect-report.md")
SUMMARY_LABELS = {**SPECIALTY_LABELS, GENERATED: GENERATED_LABEL}
SUMMARY_STATUSES = {
    "通过": "✅ 通过", "未通过": "❌ 未通过", "待确认": "待确认", "未查": "未查", "不适用": "不适用",
}


def combined_verdict(units, supplied):
    verdicts = {row.get("verdict", "未查" if row["status"] == "未查" else None) for row in units.values()}
    if "未通过" in verdicts:
        return "未通过"
    if verdicts == {"未查"}:
        return "未查"
    if None in verdicts:
        # 全为旧版回传时沿用显式摘要。新旧混合不能用已查替代缺失的判定。
        if any("verdict" in row for row in units.values()):
            return "未通过" if supplied == "未通过" else PENDING
        return supplied
    if verdicts & {PENDING, "未查"}:
        return PENDING
    return PASSED if PASSED in verdicts else "不适用"


def summary_status(entry, field, units):
    supplied = required_text(entry["status"], f"{field}.status") if "status" in entry else None
    derived = combined_verdict(units, supplied)
    if supplied is not None and supplied != derived:
        raise ValueError(f"{field}.status 与专家回传不符，应为{derived}")
    if derived not in SUMMARY_STATUSES:
        raise ValueError(f"{field}.status 需要通过、未通过、待确认、未查或不适用")
    if derived in (PASSED, "不适用") and any(row["status"] != "已查" for row in units.values()):
        raise ValueError(f"{field}.status 不能将部分已查或未查的范围标为{derived}")
    return derived


def render_summary(record):
    if not isinstance(record, dict):
        raise ValueError("质检摘要记录需要 JSON 对象")
    build_plan(record.get("plan"), replay=True)
    entries = records(record.get("summary"), "summary")
    if not entries:
        raise ValueError("summary 需要非空质检结论数组，不能用已查范围推断通过")
    selected, results, _ = coverage_units(record.get("plan", {}).get("coverage"))
    expected = {check for check, unit in selected}
    seen, counts, rows = set(), {}, []
    for index, entry in enumerate(entries):
        field = f"summary[{index}]"
        check = required_text(entry.get("check"), f"{field}.check")
        detail = required_text(entry.get("detail"), f"{field}.detail")
        if check in seen or check not in expected:
            raise ValueError(f"{field}.check 需要对应选定检查项，且同类结果合并一行")
        units = {unit: results.get((check, unit), {"status": "未查"}) for name, unit in selected if name == check}
        status = summary_status(entry, field, units)
        limits = [f"{unit}（{row['status']}）" for unit, row in units.items() if row["status"] != "已查"]
        if limits:
            detail += " 核对范围：" + "、".join(limits)
        seen.add(check)
        counts[status] = counts.get(status, 0) + 1
        rows.append(table_row((SUMMARY_LABELS.get(check, check), SUMMARY_STATUSES[status], detail)))
    if seen != expected:
        raise ValueError("summary 缺少选定检查项的结论，未查项也需单独标明")
    conclusion = summary_conclusion(counts, record)
    return "\n".join(["| 质检项 | 是否通过 | 说明 |", "| --- | --- | --- |", *rows, "", conclusion + "。"])


def summary_conclusion(counts, record):
    pending = counts.get(PENDING, 0) + counts.get("未查", 0)
    failed = counts.get("未通过", 0)
    if failed:
        conclusion = f"本次质检有 {failed} 项未通过，需修复表中问题"
        if pending:
            conclusion += f"，另有 {pending} 项待确认或未查"
    elif pending:
        conclusion = f"本次质检有 {pending} 项待确认或未查，暂不能判定全部通过"
    elif counts.get(PASSED):
        conclusion = "本次适用的质检项均通过，暂无需要修复的问题"
    else:
        conclusion = "本次质检项均不适用，无需修复"
    if "guide_replay" in record:
        status, detail, _ = guide_replay(record, Path.cwd())
        if status != PASSED and not (failed or pending):
            conclusion = "表内质检已完成"
        conclusion += f"，维护导读独立复验{status}（{detail}）"
    return conclusion


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


def rollback_summary(rollback, field):
    if not isinstance(rollback, dict) or rollback.get("status") not in ("已回退", "部分回退", "保留现场"):
        raise ValueError(f"{field}.rollback 需要已回退、部分回退或保留现场的记录")
    evidence = required_text(rollback.get("evidence"), f"{field}.rollback.evidence")
    return f"{rollback['status']}。{evidence}"


def review_details(review, status, results, field):
    outcomes = set().union(*results.values())
    if REGRESSION in outcomes and status != REGRESSION:
        raise ValueError(f"{field}.status 在验收发现差异时需要为发现差异")
    if status == REGRESSION and REGRESSION not in outcomes:
        raise ValueError(f"{field}.checks 需要记录实际差异及失败样例")

    details = {"结果": status}
    changes = review.get("changes")
    if status in (PASSED, REGRESSION) or changes is not None:
        details["实际改动"] = required_text(changes, f"{field}.changes")
    if status == PASSED:
        kind = review.get("kind")
        if kind not in ("code", "handover"):
            raise ValueError(f"{field}.kind 需要 code 或 handover")
        required = {"structure", "behavior"} if kind == "code" else {"handover"}
        if outcomes != {PASSED} or not required.issubset(results):
            raise ValueError(f"{field}.checks 缺少全部通过的{kind}验收证据")
        return details

    if status != REGRESSION:
        details["原因"] = required_text(review.get("reason"), f"{field}.reason")
    if changes is not None:
        details["回退复核"] = rollback_summary(review.get("rollback"), field)
    return details


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
        details = review_details(review, status, results, field)
        if status == PASSED:
            passed.add(target)
        lines.extend(["", f"### {index + 1}. {title}"])
        for label, value in details.items():
            lines.extend(["", f"**{label}**　{value}"])
        if "preexisting" in review:
            original = required_text(review["preexisting"], f"{field}.preexisting")
            lines.extend(["", f"**改前已有差异**　{original}"])
        if "structure_delta" in review:
            observations = text_list(review["structure_delta"], f"{field}.structure_delta")
            lines.extend(["", "**结构信号增量对照**", "", *(f"- {item}" for item in observations)])
        if checks:
            lines.extend([
                "", "| 验收 | 实际操作 | 预期 | 观察结果 | 结论 |",
                "| --- | --- | --- | --- | --- |", *checks,
            ])
    return "\n".join(lines), passed


def guide_sources(item, field, root, location=None):
    if location is not None:
        issue = location_issue(location, root, require_file=True)
        if issue:
            raise ValueError(f"{field}.entry 无法定位：{location}（{issue}）")
    evidence = text_list(item.get("evidence"), f"{field}.evidence")
    _, issues = check_sources(evidence, root)
    if issues:
        raise ValueError(f"{field}.evidence 无法定位：{'、'.join(issues)}")
    return evidence


def guide_replay(record, root):
    replay = record["guide_replay"]
    if not isinstance(replay, dict):
        raise ValueError("guide_replay 需要独立复验记录")
    status = required_text(replay.get("status"), "guide_replay.status")
    if status not in (PASSED, "未通过", PENDING):
        raise ValueError("guide_replay.status 需要通过、未通过或待确认")
    attempted = status != PENDING
    if attempted and replay.get("independent") is not True:
        raise ValueError("guide_replay.independent 需要由未参与拟稿的复验者确认")
    if attempted or "guide_task" in replay:
        topic = required_text(replay.get("guide_task"), "guide_replay.guide_task")
        if not any(guide.get("task") == topic for guide in records(record.get("guide"), "guide")):
            raise ValueError("guide_replay.guide_task 需要对应本次交付的一条导读")
    lines = ["### 维护导读独立复验", "", f"**{status}**", ""]
    lines.extend(labeled_fields(replay, "guide_replay", (
        ("guide_task", "对应导读", attempted), ("task", "相邻维护任务", True),
        ("reviewer", "独立复验者", attempted), ("entry", "找到的修改入口", status == PASSED),
        ("callers", "核实的调用方及影响", status == PASSED), ("operation", "实际操作", attempted),
        ("expected", "可区分对错的预期", status == PASSED), ("observed", "观察结果", attempted),
        ("reason", "卡住的步骤或限制", status != PASSED),
    )))
    if attempted or "evidence" in replay:
        location = replay["entry"] if status == PASSED else None
        evidence = guide_sources(replay, "guide_replay", root, location)
        lines.append(f"- 核对依据　{'、'.join(evidence)}")
    detail = replay["observed"] if status == PASSED else replay["reason"]
    return status, required_text(detail, "guide_replay"), lines


def guide_steps(entry, field):
    checks = text_list(entry.get("checks"), f"{field}.checks", preserve_lines=True)
    for number, step in enumerate(checks, 1):
        if "\n" not in step:
            yield f"{number}. {step.strip()}"
            continue
        # 代码围栏顶格，复制 Markdown 源文中的 heredoc 也能保留原缩进。
        longest_run = max((len(run) for run in re.findall(r"~+", step)), default=0)
        fence = "~" * max(3, longest_run + 1)
        body = step if step.endswith("\n") else step + "\n"
        yield f"\n**步骤 {number}**\n\n{fence}\n{body}{fence}\n"


def render_guide(record, passed, *, root=None):
    if not isinstance(record, dict):
        raise ValueError("维护导读记录需要 JSON 对象")
    if root is None:
        root = Path.cwd()
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
        evidence = guide_sources(entry, field, root, location)
        lines.extend([
            "", f"### {task}", "", f"- **当前入口**　{location}",
            f"- **受影响的调用方**　{callers}", f"- **核对依据**　{'、'.join(evidence)}",
            "", "自查步骤", "", *guide_steps(entry, field),
        ])
    if not guide or "guide_limit" in record:
        limit = required_text(record.get("guide_limit"), "guide_limit")
        lines.extend(["", f"**可见范围与待核实事项**　{limit}"])
    if "guide_replay" in record:
        _, _, replay_lines = guide_replay(record, root)
        lines.extend(["", *replay_lines])
    return "\n".join(lines)


def render_report(record):
    if not isinstance(record, dict):
        raise ValueError("治理报告记录需要 JSON 对象")
    audit = record.get("audit")
    if not isinstance(audit, list) or any(not isinstance(item, str) or not item.strip() for item in audit):
        raise ValueError("audit 需要质检章节数组")
    plan, selected = build_plan(record.get("plan"), replay=True)
    if not audit:
        coverage = record["plan"].get("coverage", {})
        if not coverage.get("selected") or any(result["status"] != "未查" for result in coverage["results"]):
            raise ValueError("audit 缺少已查范围的质检章节")
    review, passed = render_reviews(record.get("reviews"), selected)
    guide = render_guide(record, passed)
    summary = render_summary(record) if "summary" in record else ""
    sections = ["# 项目治理报告", summary, *(item.strip() for item in audit), plan.rstrip(), review, guide]
    return "\n\n".join(section for section in sections if section) + "\n"


def managed_report(body, skill_name="project-architect-skills"):
    digest = hashlib.sha256(body).hexdigest()
    return f"<!-- {skill_name} sha256={digest} -->\n\n".encode("ascii") + body


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
        if before not in (managed_report(body), managed_report(body, "code-architect-skills")):
            return False
    content = managed_report(report.encode("utf-8"))
    if before == content:
        return True

    path.parent.mkdir(exist_ok=True)
    directory = Path(tempfile.mkdtemp(dir=path.parent, prefix=".project-architect-"))
    staged = directory / path.name
    try:
        staged.write_bytes(content)
        if before is None:
            os.link(staged, path)
            return True
        if not matches(path, before):
            return False
        staged.chmod(stat.S_IMODE(path.stat().st_mode))
        return refresh_managed(staged, path, before, content)
    finally:
        # An unexpected displaced file may be the only copy of a concurrent save.
        if matches(staged, content):
            staged.unlink()
        if any(directory.iterdir()):
            print(f"发布期间保留的文件位于 {directory}", file=sys.stderr)
        else:
            directory.rmdir()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", nargs="?", type=Path, help="治理报告 JSON，默认读取标准输入")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--write", action="store_true", help="将报告写入当前仓库，无法安全写入时输出全文")
    output.add_argument("--guide-only", action="store_true", help="仅在标准输出交付当前工作区的维护导读")
    output.add_argument("--summary", action="store_true", help="仅输出质检表格和一句话总结，需提供 summary 结论")
    args = parser.parse_args()
    try:
        if args.record is None:
            record = json.load(sys.stdin)
        else:
            record = json.loads(args.record.read_text(encoding="utf-8"))
        if args.guide_only:
            report = render_guide(record, set()) + "\n"
        elif args.summary:
            report = render_summary(record) + "\n"
        else:
            report = render_report(record)
    except (OSError, ValueError) as error:
        parser.exit(2, f"治理报告无法汇总（{error}）\n")
    if args.write:
        try:
            if publish_report(report):
                print(REPORT_PATH)
                return
            print(f"保留已有的 {REPORT_PATH}，会话默认交付质检摘要。", file=sys.stderr)
        except OSError as error:
            print(f"无法写入 {REPORT_PATH}（{error}），会话默认交付质检摘要。", file=sys.stderr)
    sys.stdout.write(report)


if __name__ == "__main__":
    main()
