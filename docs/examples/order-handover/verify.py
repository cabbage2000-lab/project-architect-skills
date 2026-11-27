"""观察员从三个公开命令的 CSV 输出验收交接结果。"""

import argparse
import csv
import io
import subprocess
import sys
from pathlib import Path


HEADERS = {
    "baseline": ["order_id", "customer", "amount"],
    "A": ["order_id", "customer", "net_amount"],
    "B": ["order_id", "customer_name", "amount"],
}
ROWS = [["A1", "Lin, Mei", "12.50"], ["A2", "Bo", "7.00"]]


def verify(project, case):
    expected = {
        "orders.py": [HEADERS[case], *ROWS],
        "reconcile.py": [HEADERS[case], ROWS[0]],
        "archive.py": [HEADERS["baseline"], *ROWS],
    }
    for command, rows in expected.items():
        output = subprocess.check_output([sys.executable, "-B", command], cwd=project, text=True)
        actual = list(csv.reader(io.StringIO(output)))
        if actual != rows:
            raise ValueError(f"{command} 预期 {rows!r}，实际 {actual!r}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("case", choices=HEADERS)
    args = parser.parse_args()
    try:
        verify(args.project, args.case)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")
    print(f"{args.case} 通过，订单、对账和历史归档的表头与数据均符合约定。")
