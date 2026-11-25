"""从本地 Git 历史提取指定路径的变更热点和共变线索。"""

import argparse
import itertools
import json
import os
import subprocess
from collections import defaultdict
from pathlib import PurePosixPath


def git(*arguments):
    # Partial clones may try to fetch missing objects during rename detection.
    environment = {**os.environ, "GIT_ALLOW_PROTOCOL": ""}
    result = subprocess.run(["git", "--no-pager", *arguments], capture_output=True, env=environment)
    if result.returncode:
        raise ValueError(result.stderr.decode(errors="replace").strip() or "Git 命令失败")
    return result.stdout


def commit_changes(raw):
    fields = iter(raw.split(b"\0"))
    for header in fields:
        if not header:
            continue
        revision = header.decode("ascii")
        date = next(fields).decode("ascii")[:10]
        changes = []
        for field in fields:
            metadata = field.split()
            if not metadata:
                break
            old_mode, new_mode, old_blob, new_blob, status = metadata
            kind = status[:1].decode("ascii")
            old = os.fsdecode(next(fields))
            new = os.fsdecode(next(fields)) if kind in ("R", "C") else old
            # Git's similarity score can be 100 even if lines were reordered.
            pure_rename = kind == "R" and old_blob == new_blob and old_mode[1:] == new_mode
            changes.append((kind, old, new, pure_rename))
        yield revision, date, changes


def trace_paths(commits, paths, max_files):
    aliases = {path: path for path in paths}
    touches = defaultdict(list)
    pairs = defaultdict(list)
    active_days = set()
    active_commits = skipped_bulk = 0
    for revision, date, changes in commits:
        changed = set()
        renames = {}
        for kind, old, new, pure_rename in changes:
            current = aliases.get(new)
            if current is None:
                continue
            if kind == "R":
                renames[old] = aliases.pop(new)
            elif kind in ("A", "C"):
                # 这里创建了当前文件，同名旧文件属于另一段历史。
                aliases.pop(new)
            if kind in ("M", "T", "R") and not pure_rename:
                changed.add(current)
        aliases.update(renames)
        if sum(not pure_rename for _, _, _, pure_rename in changes) > max_files:
            skipped_bulk += 1
            continue
        if changed:
            active_commits += 1
            active_days.add(date)
        for path in changed:
            touches[path].append(revision)
        for pair in itertools.combinations(sorted(changed), 2):
            pairs[pair].append(revision)
    return touches, pairs, active_commits, len(active_days), skipped_bulk


def history(paths, days, limit, max_files):
    result = {
        "window_days": days, "commit_limit": limit, "max_files_per_commit": max_files,
        "hotspots": [], "co_changes": [],
    }
    try:
        if git("rev-parse", "--show-prefix").strip():
            raise ValueError("请在目标 Git 仓库根目录运行")
        head = git("rev-parse", "--verify", "HEAD").strip().decode("ascii")
        shallow = git("rev-parse", "--is-shallow-repository").strip() == b"true"
        tracked = {os.fsdecode(path) for path in git("ls-tree", "-rz", "--name-only", head).split(b"\0") if path}
        in_head = [path for path in paths if path in tracked]
        raw = git(
            "log", "--first-parent", "-m", f"--since={days} days ago", f"--max-count={limit + 1}",
            "--no-color", "--no-show-signature", "--no-ext-diff", "--no-textconv", "-M", "--raw", "--no-abbrev", "-z",
            "--format=%x00%H%x00%cI", head, "--",
        )
        commits = list(commit_changes(raw))
    except (OSError, ValueError) as error:
        return {**result, "status": "unavailable", "reason": str(error)}

    touches, pairs, active_commits, active_days, skipped_bulk = trace_paths(commits[:limit], in_head, max_files)
    result.update(
        head=head, paths=in_head, absent_paths=[path for path in paths if path not in tracked],
        examined_commits=min(len(commits), limit), truncated=len(commits) > limit,
        active_commits=active_commits, active_days=active_days, skipped_bulk_commits=skipped_bulk,
    )
    if shallow or active_commits < 5 or active_days < 3:
        reason = "浅克隆的历史不完整。" if shallow else "范围内的有效修改少于 5 次或分布不足 3 个提交日期。"
        return {**result, "status": "insufficient", "reason": reason}

    result["hotspots"] = [
        {"path": path, "changes": len(touches[path]), "commits": touches[path][:3]}
        for path in sorted(touches, key=lambda path: (-len(touches[path]), path))
    ]
    result["co_changes"] = [
        {"paths": pair, "together": len(revisions),
         "changes": [len(touches[path]) for path in pair], "commits": revisions[:3]}
        for pair, revisions in sorted(pairs.items(), key=lambda item: (-len(item[1]), item[0]))
        if len(revisions) >= 3
    ]
    return {**result, "status": "available"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=PurePosixPath, help="选定的源码和相关测试的仓库相对路径")
    parser.add_argument("--days", type=int, default=90, help="回看的天数，默认 90")
    parser.add_argument("--limit", type=int, default=200, help="最多检查的提交数，默认 200")
    parser.add_argument("--max-files", type=int, default=30, help="一个提交允许触及的实质变更文件数，默认 30")
    args = parser.parse_args()
    if min(args.days, args.limit, args.max_files) < 1:
        parser.error("天数、提交数和单次文件数需要为正整数")
    if any(path.is_absolute() or ".." in path.parts or not path.parts for path in args.paths):
        parser.error("请指定仓库相对文件路径")
    paths = list(dict.fromkeys(path.as_posix() for path in args.paths))
    print(json.dumps(history(paths, args.days, args.limit, args.max_files), indent=2))


if __name__ == "__main__":
    main()
