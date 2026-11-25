import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "skills/project-architect-skills/scripts/git_change_history.py"


@unittest.skipUnless(shutil.which("git"), "需要 Git")
class GitChangeHistoryTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.git("init", "-q")
        self.base_date = datetime.now(timezone.utc) - timedelta(days=10)

    def git(self, *args, env=None):
        return subprocess.check_output(["git", *args], cwd=self.root, text=True, env=env).strip()

    def commit(self, day, **files):
        for filename, content in files.items():
            (self.root / filename).write_text(str(content), encoding="utf-8")
        self.git("add", "-A")
        date = (self.base_date + timedelta(days=day)).isoformat()
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-qm", f"变更 {day}", "--allow-empty",
                 env={**os.environ, "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date})
        return self.git("rev-parse", "HEAD")

    def history(self, *args, cwd=None):
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), *args], cwd=cwd or self.root,
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_history_follows_rename_and_skips_bulk_empty_and_worktree_changes(self):
        old, new, test, auxiliary = "old.py", "新 模块.py", "test\nmodule.py", "utility.py"
        self.commit(0, **{old: 0, test: 0, auxiliary: 0})
        first_pair = self.commit(1, **{old: 1, test: 1})
        second_pair = self.commit(2, **{old: 2, test: 2})
        auxiliary_change = self.commit(3, **{auxiliary: 1})
        self.git("mv", old, new)
        self.commit(4)
        third_pair = self.commit(5, **{new: 3, test: 3})
        solo_change = self.commit(6, **{new: 4})
        self.commit(7, **{new: 5, test: 4, auxiliary: 2, "other.py": 1})
        head = self.commit(8)
        (self.root / new).write_text("dirty", encoding="utf-8")
        (self.root / "new.py").write_text("untracked", encoding="utf-8")
        before = self.git("status", "--porcelain=v1")

        result = self.history("--max-files", "3", new, test, auxiliary, "new.py")
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["head"], head)
        self.assertEqual(result["examined_commits"], 9)
        self.assertEqual(result["active_commits"], 5)
        self.assertEqual(result["active_days"], 5)
        self.assertEqual(result["skipped_bulk_commits"], 1)
        self.assertEqual(result["absent_paths"], ["new.py"])
        self.assertEqual(result["hotspots"], [
            {"path": new, "changes": 4, "commits": [solo_change, third_pair, second_pair]},
            {"path": test, "changes": 3, "commits": [third_pair, second_pair, first_pair]},
            {"path": auxiliary, "changes": 1, "commits": [auxiliary_change]},
        ])
        self.assertEqual(result["co_changes"], [{
            "paths": [test, new], "together": 3, "changes": [3, 4],
            "commits": [third_pair, second_pair, first_pair],
        }])
        self.assertEqual(self.git("status", "--porcelain=v1"), before)
        limited = self.history("--limit", "4", new, test)
        self.assertTrue(limited["truncated"])
        self.assertEqual(limited["status"], "insufficient")

    def test_new_file_with_reused_path_starts_its_own_history(self):
        self.commit(0, **{"module.py": 0, "other.py": 0})
        for day in range(1, 4):
            self.commit(day, **{"module.py": day, "other.py": day})
        (self.root / "module.py").unlink()
        self.commit(4)
        self.commit(5, **{"module.py": 5})
        changes = [self.commit(day, **{"module.py": day}) for day in (6, 7)]
        result = self.history("module.py", "other.py")
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["hotspots"][1], {"path": "module.py", "changes": 2, "commits": changes[::-1]})
        self.assertEqual(result["co_changes"], [])

    def test_rename_with_reordered_content_counts_even_at_full_similarity(self):
        original = [f"field_{index} = {index}\n" for index in range(80)]
        self.commit(0, **{"draft.py": "".join(original), "other.py": 0})
        for day in range(1, 5):
            self.commit(day, **{"other.py": day})
        self.git("mv", "draft.py", "final.py")
        renamed = self.commit(5, **{"final.py": "".join(reversed(original))})

        result = self.history("final.py", "other.py")
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["hotspots"][1], {"path": "final.py", "changes": 1, "commits": [renamed]})

    def test_insufficient_shallow_and_unavailable_history(self):
        self.commit(0, **{"a.py": 0})
        for index in range(1, 6):
            self.commit(1, **{"a.py": index})
        result = self.history("a.py")
        self.assertEqual(result["active_commits"], 5)
        self.assertEqual(result["status"], "insufficient")
        self.assertEqual(result["hotspots"], [])
        self.assertEqual(result["co_changes"], [])
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.history("a.py", cwd=directory)["status"], "unavailable")
            clone = Path(directory) / "clone"
            self.git("clone", "-q", "--depth", "1", self.root.resolve().as_uri(), str(clone))
            self.assertIn("浅克隆", self.history("a.py", cwd=clone)["reason"])
