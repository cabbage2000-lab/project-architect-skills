"""核对拟执行事项引用的本地位置，保留宿主已核实的其他证据。"""

import re
from pathlib import Path


LINE_REF = re.compile(r"(.+?):(-?\d+)(?:[-–](-?\d+))?")
LINE_ANCHOR = re.compile(r"(.+?)#L(\d+)(?:-L?(\d+))?")
SOURCE_NOTES = ("命令观察：", "外部资料：", "观察：")
SOURCE_URL = re.compile(r"[a-zA-Z][\w+.-]*://")


def check_sources(sources, root, *, require_local_on_error=False, require_reference=False):
    usable, issues = [], []
    has_valid_local = False
    has_reference = False
    for source in sources:
        is_local, issue = _check_location(source, root)
        if issue:
            issues.append(f"{source}（{issue}）")
        else:
            usable.append(source)
            has_valid_local = has_valid_local or is_local
            if require_reference:
                location = source.strip("`")
                has_reference |= is_local or bool(SOURCE_URL.match(location)) or any(
                    location.startswith(prefix) and location[len(prefix):].strip() for prefix in SOURCE_NOTES
                )
    if require_reference and not (has_reference or issues):
        issues.append("缺少可定位的文件、已读外部资料或具体命令观察")
    if require_local_on_error and issues and not has_valid_local:
        # 全部本地出处失效时，补充观察仍保存在原始记录中。
        return [], issues
    return usable, issues


def location_issue(source, root, *, require_file=False):
    _, issue = _check_location(source, root, require_file=require_file)
    return issue


def _check_location(source, root, *, require_file=False):
    """返回该出处是否为本地引用，以及需要报告的定位问题。"""
    quoted = source.startswith("`") and source.endswith("`")
    if quoted:
        source = source[1:-1]
    if SOURCE_URL.match(source) or source.startswith(SOURCE_NOTES):
        return False, "需要仓库内的入口文件" if require_file else None
    lines = LINE_REF.fullmatch(source) or LINE_ANCHOR.fullmatch(source)
    path, separator, _ = source.partition("::")
    if not separator:
        path, separator, _ = source.partition("#")
    if lines:
        path = lines[1]
    path = path.strip("`")
    if not path:
        return False, "缺少入口文件路径" if require_file else None
    candidate = Path(path)
    try:
        explicit = require_file or quoted or bool(lines) or bool(separator)
        if not explicit and not (root / path).exists():
            # 旧记录也接受取证说明。只有独立的路径引用可机械核对。
            if any(char.isspace() for char in path) or not (
                "/" in path or candidate.suffix or path.startswith(".") or path in ("Makefile", "Dockerfile", "README")
            ):
                return False, None
        target = (root / candidate).resolve()
        allow_directory = not require_file and not lines and not separator
        issue = _path_issue(target, root, lines, allow_directory)
    except (OSError, RuntimeError, ValueError):
        issue = "无法读取引用位置"
    return True, issue


def _path_issue(target, root, lines, allow_directory):
    if not target.is_relative_to(root):
        return "超出目标仓库"
    if allow_directory and target.is_dir():
        return None
    if not target.is_file():
        return "找不到可读文件"
    with target.open("rb") as stream:
        if lines:
            start, end = int(lines[2]), int(lines[3] or lines[2])
            if not 1 <= start <= end:
                return "行号范围无效"
            if not any(number == end for number, _ in enumerate(stream, 1)):
                return "行号超出文件范围"
        else:
            stream.read(1)
    return None
