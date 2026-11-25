"""从指定 Python 文件提取方法级异味的结构信号，以 JSON 输出。"""

import argparse
import ast
import io
import json
import sys
import tokenize
from bisect import bisect_left, bisect_right
from collections import defaultdict
from pathlib import Path


FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)
DEFINITIONS = FUNCTIONS + (ast.ClassDef,)
CONTROL = (ast.If, ast.For, ast.AsyncFor, ast.While)
NESTING = CONTROL + (ast.Match,) if hasattr(ast, "Match") else CONTROL
DECISIONS = CONTROL + (ast.ExceptHandler, ast.IfExp)
IGNORED_TOKENS = {
    tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER,
}


def functions(node, parents=()):
    for child in ast.iter_child_nodes(node):
        names = (*parents, child.name) if isinstance(child, DEFINITIONS) else parents
        if isinstance(child, FUNCTIONS):
            yield ".".join(names), child
        yield from functions(child, names)


def condition_terms(node):
    if isinstance(node, ast.BoolOp):
        return sum(condition_terms(value) for value in node.values)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return condition_terms(node.operand)
    return 1


def is_elif(parent, field, statements):
    """同缩进的 orelse 子 If 来自 elif 分支。"""
    return (
        isinstance(parent, ast.If) and field == "orelse" and len(statements) == 1
        and isinstance(statements[0], ast.If) and statements[0].col_offset == parent.col_offset
    )


def catches_every_value(pattern):
    kind = type(pattern).__name__
    if kind == "MatchAs":
        return pattern.pattern is None or catches_every_value(pattern.pattern)
    if kind == "MatchOr":
        return any(catches_every_value(option) for option in pattern.patterns)
    return False


class Flow:
    def __init__(self, source, min_terms):
        self.source = source
        self.min_terms = min_terms
        self.conditions = []
        self.decisions = []
        self.groups = []
        self.inner_definitions = []

    def record_condition(self, test):
        terms = condition_terms(test)
        if terms >= self.min_terms:
            expression = ast.get_source_segment(self.source, test)
            self.conditions.append({"line": test.lineno, "terms": terms, "expression": expression})

    def suite(self, statements, ancestors):
        longest = ancestors
        regions = []
        for statement in statements:
            path = self.node(statement, ancestors)
            longest = max(longest, path, key=len)
            if isinstance(statement, NESTING) and len(path) >= len(ancestors) + 2:
                regions.append({"start": statement.lineno, "end": statement.end_lineno})
        if len(regions) >= 2:
            self.groups.append(regions)
        return longest

    def node(self, node, ancestors):
        if isinstance(node, DEFINITIONS):
            self.inner_definitions.append(node)
            return ancestors
        if isinstance(node, ast.Lambda):
            return ancestors

        kind = type(node).__name__
        if isinstance(node, (ast.If, ast.While, ast.IfExp)):
            self.record_condition(node.test)
        if isinstance(node, DECISIONS):
            self.decisions.append({"kind": kind, "line": node.lineno})
        if kind == "match_case":
            pattern = node.pattern
            if node.guard is not None:
                self.record_condition(node.guard)
            if node.guard is not None or not catches_every_value(pattern):
                self.decisions.append({"kind": "case", "line": pattern.lineno})

        path = ancestors
        if isinstance(node, NESTING):
            path = (*ancestors, {"kind": kind, "line": node.lineno})
        longest = path
        for field, value in ast.iter_fields(node):
            if isinstance(value, ast.AST):
                longest = max(longest, self.node(value, path), key=len)
            elif isinstance(value, list) and value:
                if is_elif(node, field, value):
                    longest = max(longest, self.node(value[0], ancestors), key=len)
                elif isinstance(value[0], ast.stmt):
                    longest = max(longest, self.suite(value, path), key=len)
                else:
                    for item in value:
                        if isinstance(item, ast.AST):
                            longest = max(longest, self.node(item, path), key=len)
        return longest


def function_code_lines(node, lines, inner_definitions):
    first = node.body[0]
    start = min(item.lineno for item in [first, *getattr(first, "decorator_list", [])])
    code = set(lines[bisect_left(lines, start):bisect_right(lines, node.end_lineno)])
    if ast.get_docstring(node, clean=False) is not None:
        code.difference_update(range(first.lineno, first.end_lineno + 1))
        if len(node.body) > 1 and node.body[1].lineno == first.end_lineno:
            code.add(first.end_lineno)
    for inner in inner_definitions:
        start = min(item.lineno for item in [inner, *inner.decorator_list])
        code.difference_update(range(start, inner.end_lineno + 1))
    return len(code)


def measure_file(source, path, thresholds, *, include_clean=False):
    tree = ast.parse(source, filename=path)
    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    lines = sorted({token.start[0] for token in tokens if token.type not in IGNORED_TOKENS})
    hits = []
    count = 0
    for symbol, node in functions(tree):
        count += 1
        flow = Flow(source, thresholds.min_terms)
        deepest = flow.suite(node.body, ())
        code_lines = function_code_lines(node, lines, flow.inner_definitions)
        signals = {}
        if code_lines >= thresholds.min_lines:
            signals["long_method"] = {"code_lines": code_lines}
        if len(deepest) >= thresholds.min_depth:
            signals["deep_nested_logic"] = {"depth": len(deepest), "path": deepest}
        if flow.groups:
            signals["bumpy_road"] = {"groups": flow.groups}
        if flow.conditions:
            signals["complex_conditional"] = flow.conditions
        if len(flow.decisions) >= thresholds.min_decisions:
            signals["complex_method"] = {"decision_count": len(flow.decisions), "decisions": flow.decisions}
        if signals or include_clean:
            hits.append({"path": path, "symbol": symbol, "start": node.lineno, "end": node.end_lineno, "signals": signals})
    return count, hits


def measure_path(path, thresholds, *, include_clean=False):
    with tokenize.open(path) as stream:
        return measure_file(stream.read(), path.as_posix(), thresholds, include_clean=include_clean)


READ_ERRORS = (OSError, SyntaxError, UnicodeError, RecursionError, tokenize.TokenError)


def signal_values(method):
    values = dict(method["signals"]) if method else {}
    for kind, fields in (("deep_nested_logic", ("depth",)), ("complex_method", ("decision_count",))):
        if kind in values:
            values[kind] = {field: values[kind][field] for field in fields}
    if "bumpy_road" in values:
        groups = values["bumpy_road"]["groups"]
        values["bumpy_road"] = {"groups": len(groups), "regions": sum(map(len, groups))}
    if "complex_conditional" in values:
        conditions = values["complex_conditional"]
        values["complex_conditional"] = {"conditions": len(conditions), "max_terms": max(item["terms"] for item in conditions)}
    return values


def signal_status(before, after):
    if before is None:
        return "added"
    if after is None:
        return "removed"
    if all(value >= before[key] for key, value in after.items()):
        return "increased"
    if all(value <= before[key] for key, value in after.items()):
        return "decreased"
    return "changed"


def compare_files(before_path, after_path, thresholds):
    result = {"before": before_path, "after": after_path, "changes": [], "ambiguous": [], "unread": []}
    versions = []
    for side, path in (("before", before_path), ("after", after_path)):
        methods = defaultdict(list)
        if path != "-":
            try:
                _, measured = measure_path(Path(path), thresholds, include_clean=True)
                for method in measured:
                    methods[method["symbol"]].append(method)
            except READ_ERRORS as error:
                result["unread"].append({"side": side, "source": path, "reason": str(error)})
        versions.append(methods)
    if result["unread"]:
        return result

    old_methods, new_methods = versions
    for symbol in sorted(old_methods.keys() | new_methods.keys()):
        old, new = old_methods[symbol], new_methods[symbol]
        if len(old) > 1 or len(new) > 1:
            result["ambiguous"].append(symbol)
            continue
        before, after = (methods[0] if methods else None for methods in (old, new))
        before_values, after_values = signal_values(before), signal_values(after)
        signals = []
        for kind in sorted(before_values.keys() | after_values.keys()):
            prior, current = before_values.get(kind), after_values.get(kind)
            if prior != current:
                signals.append({"kind": kind, "status": signal_status(prior, current), "before": prior, "after": current})
        if signals:
            result["changes"].append({
                "symbol": symbol, "before_lines": [before["start"], before["end"]] if before else None,
                "after_lines": [after["start"], after["end"]] if after else None, "signals": signals,
            })
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, help="本轮范围内需要测量的 Python 文件")
    parser.add_argument("--compare", nargs=2, action="append", metavar=("BEFORE", "AFTER"),
                        help="成对比较改前快照和改后文件，可重复使用。明确不存在的一侧用 -")
    parser.add_argument("--min-lines", type=int, default=40)
    parser.add_argument("--min-depth", type=int, default=4)
    parser.add_argument("--min-terms", type=int, default=4)
    parser.add_argument("--min-decisions", type=int, default=8)
    args = parser.parse_args()
    thresholds = {
        "min_lines": args.min_lines, "min_depth": args.min_depth,
        "min_terms": args.min_terms, "min_decisions": args.min_decisions,
    }
    if min(args.min_lines, args.min_decisions) < 1 or min(args.min_depth, args.min_terms) < 2:
        parser.error("行数和决策点阈值至少为 1，深度和条件项阈值至少为 2")
    if args.compare:
        if args.paths or any(pair == ["-", "-"] for pair in args.compare):
            parser.error("请单独使用 --compare，每对至少指定一个文件")
        comparisons = [compare_files(before, after, args) for before, after in args.compare]
        json.dump({"thresholds": thresholds, "comparisons": comparisons}, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return
    if not args.paths:
        parser.error("请指定需要测量或比较的 Python 文件")

    files, methods, unread = [], [], []
    for path in dict.fromkeys(args.paths):
        name = path.as_posix()
        try:
            count, hits = measure_path(path, args)
        except READ_ERRORS as error:
            unread.append({"source": name, "reason": str(error)})
            continue
        files.append({"path": name, "methods": count})
        methods.extend(hits)
    json.dump({"thresholds": thresholds, "files": files, "methods": methods, "unread": unread},
              sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
