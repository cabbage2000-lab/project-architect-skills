import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


EXAMPLE = Path(__file__).resolve().parents[1] / "docs/examples/order-handover"


class OrderHandoverTests(unittest.TestCase):
    def verify(self, project, case):
        return subprocess.run([sys.executable, "-B", str(EXAMPLE / "verify.py"), str(project), case],
                              capture_output=True, text=True)

    def test_baseline_and_each_adjacent_change_through_all_consumers(self):
        self.assertEqual(self.verify(EXAMPLE / "project", "baseline").returncode, 0)
        for case, old, new in (("A", "amount", "net_amount"), ("B", "customer", "customer_name")):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / "orders"
                shutil.copytree(EXAMPLE / "project", project)
                self.assertNotEqual(self.verify(project, case).returncode, 0)
                header = '["order_id", "customer", "amount"]'
                for name in ("order_csv.py", "archive.py"):
                    file = project / name
                    file.write_text(file.read_text().replace(header, header.replace(old, new)))
                    result = self.verify(project, case)
                    if name == "order_csv.py":
                        self.assertEqual(result.returncode, 0, result.stderr)
                    else:
                        self.assertEqual(result.returncode, 1)
                        self.assertIn("archive.py", result.stderr)
