"""核对拟执行事项引用的本地位置，保留宿主已核实的其他证据。"""

import re
from pathlib import Path


LINE_REF = re.compile(r"(.+?):(-?\d+)(?:[-–](-?\d+))?")
LINE_ANCHOR = re.compile(r"(.+?)#L(\d+)(?:-L?(\d+))?")


def check_sources(sources, root):
    usable, issues = [], []
    for source in sources:
        issue = location_issue(source, root)
        if issue:
            issues.append(f"{source}（{issue}）")
        else:
            usable.append(source)
    return usable, issues


def location_issue(source, root, *, require_file=False):
    quoted = source.startswith("`") and source.endswith("`")
    if quoted:
        source = source[1:-1]
    if re.match(r"[a-zA-Z][\w+.-]*://", source) or source.startswith(("命令观察：", "外部资料：", "观察：")):
        return "需要仓库内的入口文件" if require_file else None
    lines = LINE_REF.fullmatch(source) or LINE_ANCHOR.fullmatch(source)
    path, separator, _ = source.partition("::")
    if not separator:
        path, separator, _ = source.partition("#")
    if lines:
        path = lines[1]
    path = path.strip("`")
    if not path:
        return "缺少入口文件路径" if require_file else None
    candidate = Path(path)
    try:
        if not require_file and not lines and not separator and not quoted and not (root / path).exists():
            # 旧记录也接受取证说明。只有独立的路径引用可机械核对。
            if any(char.isspace() for char in path) or not (
                "/" in path or candidate.suffix or path.startswith(".") or path in ("Makefile", "Dockerfile", "README")
            ):
                return None
        target = (root / candidate).resolve()
        if not target.is_relative_to(root):
            return "超出目标仓库"
        if target.is_dir() and not require_file and not lines and not separator:
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
    except (OSError, RuntimeError, ValueError):
        return "无法读取引用位置"
    return None
