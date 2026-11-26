"""检查章节与覆盖记录共用的文本字段。"""


def required_text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} 需要非空文本")
    return " ".join(value.strip().splitlines())


def text_list(value, field):
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} 需要非空文本数组")
    return [required_text(item, field) for item in value]


def table_row(cells):
    return "| " + " | ".join(cell.replace("|", r"\|") for cell in cells) + " |"
