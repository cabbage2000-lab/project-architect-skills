"""列出本次改动体检的取证范围。默认检查未提交改动，可指定两个提交比较。"""

import argparse
import json
import os
import re

from git_evidence import git


# Number of fields before the path in Git porcelain v2 records.
STATUS_PREFIX = {"1": 8, "2": 9, "u": 10}


def worktree_scope():
    raw = git("-c", "core.fsmonitor=false", "status", "--porcelain=v2", "-z", "--branch",
              "--no-ahead-behind", "--untracked-files=all", "--find-renames", "--ignore-submodules=none")
    fields = iter(os.fsdecode(raw).split("\0"))
    changes = []
    head = None
    for field in fields:
        if field.startswith("# branch.oid "):
            oid = field.split()[-1]
            head = None if oid == "(initial)" else oid
        if not field or field.startswith("# "):
            continue
        kind = field[0]
        if kind == "?":
            changes.append({"status": "??", "path": field[2:]})
            continue
        # Porcelain v2 ordinary, rename/copy and unmerged records have
        # different fixed prefixes. The remaining path may itself contain spaces.
        if kind not in STATUS_PREFIX:
            raise ValueError(f"未知的 Git 状态记录 {kind!r}")
        parts = field.split(" ", STATUS_PREFIX[kind])
        change = {"status": parts[1], "path": parts[-1]}
        if kind == "2":
            change["old_path"] = next(fields)
        if kind == "u":
            change["conflict"] = True
        if parts[2].startswith("S"):
            change["submodule"] = parts[2]
        changes.append(change)
    return {"mode": "worktree", "head": head, "changes": changes}


def revision(name):
    try:
        oid = git("rev-parse", "--verify", "--end-of-options", name + "^{commit}").strip().decode("ascii")
    except ValueError as error:
        raise ValueError(f"无法解析本地提交 {name!r}：{error}") from error
    if not re.fullmatch("[0-9a-f]+", oid):
        raise ValueError(f"需要单个提交作为端点：{name!r}")
    return oid


def range_scope(spec):
    separator = "..." if "..." in spec else ".."
    left, found, right = spec.partition(separator)
    if not found or not left or not right or ".." in right:
        raise ValueError("请用 A..B 指定两个端点，或用 A...B 从共同祖先检查到 B")
    base, target = revision(left), revision(right)
    if separator == "...":
        try:
            bases = git("merge-base", "--all", base, target).decode("ascii").splitlines()
        except ValueError as error:
            raise ValueError(f"无法取得 {left!r} 和 {right!r} 的共同祖先：{error}") from error
        if len(bases) != 1:
            raise ValueError("无法确定唯一共同祖先，请用 A..B 明确指定比较端点")
        base = bases[0]
    raw = git("diff", "--name-status", "-z", "--find-renames", "--no-ext-diff", "--no-textconv",
              "--ignore-submodules=none", base, target, "--")
    fields = iter(os.fsdecode(raw).split("\0"))
    changes = []
    for status in fields:
        if not status:
            continue
        path = next(fields)
        change = {"status": status, "path": path}
        if status.startswith(("R", "C")):
            change.update(old_path=path, path=next(fields))
        changes.append(change)
    return {"mode": "range", "range": spec, "base": base, "target": target, "changes": changes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--range", metavar="A..B", help="比较两个本地提交，A...B 表示从共同祖先到 B")
    args = parser.parse_args()
    try:
        if git("rev-parse", "--show-prefix").strip():
            raise ValueError("请在目标 Git 仓库根目录运行")
        scope = worktree_scope() if args.range is None else range_scope(args.range)
    except (OSError, ValueError) as error:
        parser.exit(1, f"无法取得改动范围：{error}\n")
    print(json.dumps(scope, indent=2))


if __name__ == "__main__":
    main()
