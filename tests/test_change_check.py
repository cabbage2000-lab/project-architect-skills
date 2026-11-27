import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "skills/project-architect-skills/scripts/change_check.py"


@unittest.skipUnless(shutil.which("git"), "需要 Git")
class ChangeCheckTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "commit.gpgsign", "false")

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, text=True).strip()

    def write(self, path, content):
        file = self.root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding="utf-8")

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-qm", message)
        return self.git("rev-parse", "HEAD")

    def run_check(self, *args, cwd=None):
        return subprocess.run([sys.executable, "-B", str(SCRIPT), *args], cwd=cwd or self.root,
                              capture_output=True, text=True)

    def scope(self, *args):
        run = self.run_check(*args)
        self.assertEqual(run.returncode, 0, run.stderr)
        return json.loads(run.stdout)

    def test_worktree_preserves_both_layers_and_ignored_boundary(self):
        self.write(".gitignore", "private/\n")
        self.write("original", "contents to rename")
        self.write("both", "base")
        self.write("removed", "deleted file")
        head = self.commit("baseline")
        renamed = " 新\t名\n.txt"
        self.git("mv", "original", renamed)
        self.write("both", "staged")
        self.git("add", "both")
        self.write("both", "base")
        (self.root / "removed").unlink()
        self.write("new/file", "untracked")
        self.write("private/file", "ignored")

        index = self.root / ".git/index"
        before = (index.read_bytes(), index.stat().st_mtime_ns)
        scope = self.scope()
        self.assertEqual(scope["head"], head)
        self.assertCountEqual(scope["changes"], [
            {"status": "R.", "old_path": "original", "path": renamed},
            {"status": "MM", "path": "both"}, {"status": ".D", "path": "removed"},
            {"status": "??", "path": "new/file"},
        ])
        self.assertEqual((index.read_bytes(), index.stat().st_mtime_ns), before)
        self.assertEqual(self.git("show", ":both"), "staged")
        self.assertEqual((self.root / "both").read_text(), "base")

    def test_clean_and_unborn_worktree(self):
        self.assertEqual(self.scope(), {"mode": "worktree", "head": None, "changes": []})
        self.write("entry", "new")
        self.git("add", "entry")
        self.assertEqual(self.scope()["changes"], [{"status": "A.", "path": "entry"}])
        head = self.commit("first")
        self.assertEqual(self.scope(), {"mode": "worktree", "head": head, "changes": []})
        self.assertEqual(self.scope("--range", "HEAD..HEAD")["changes"], [])

    def test_ranges_pin_the_selected_trees_and_resolve_merge_base(self):
        self.write("old", "contents to rename")
        initial = self.commit("base")
        self.git("branch", "feature")
        self.write("only-on-main", "main")
        main = self.commit("advance main")
        self.git("checkout", "-q", "feature")
        new = "new\nname"
        self.git("mv", "old", new)
        feature = self.commit("rename on branch")
        self.write("only-in-index", "staged")
        self.git("add", "only-in-index")
        self.write("only-in-worktree", "untracked")
        self.write(new, "subsequent edit")

        rename = {"status": "R100", "old_path": "old", "path": new}
        branch = self.scope("--range", "main...feature")
        self.assertEqual(branch, {"mode": "range", "range": "main...feature", "base": initial,
                                  "target": feature, "changes": [rename]})
        endpoints = self.scope("--range", "main..feature")
        self.assertEqual((endpoints["base"], endpoints["target"]), (main, feature))
        self.assertCountEqual(endpoints["changes"], [rename, {"status": "D", "path": "only-on-main"}])

    def test_unmerged_path_stays_visible(self):
        self.write("rule", "base\n")
        self.commit("base")
        self.git("checkout", "-qb", "feature")
        self.write("rule", "feature\n")
        self.commit("feature")
        self.git("checkout", "-q", "main")
        self.write("rule", "main\n")
        self.commit("main")
        merge = subprocess.run(["git", "merge", "feature"], cwd=self.root, capture_output=True)
        self.assertEqual(merge.returncode, 1)
        self.assertEqual(self.scope()["changes"], [{"status": "UU", "path": "rule", "conflict": True}])

    def test_invalid_range_or_unavailable_repo_has_no_partial_result(self):
        self.write("file", "initial")
        self.commit("initial")
        for spec in ("HEAD", "HEAD..", "missing..HEAD", "^HEAD..HEAD", "HEAD..HEAD..HEAD"):
            with self.subTest(spec=spec):
                run = self.run_check("--range", spec)
                self.assertNotEqual(run.returncode, 0)
                self.assertEqual(run.stdout, "")
                self.assertIn("无法取得改动范围", run.stderr)
        with tempfile.TemporaryDirectory() as other:
            run = self.run_check(cwd=other)
            self.assertNotEqual(run.returncode, 0)
            self.assertEqual(run.stdout, "")
            self.assertTrue(run.stderr)

    def test_unrelated_histories_cannot_be_reviewed_as_a_branch_delta(self):
        self.write("entry", "first history")
        self.commit("first root")
        self.git("checkout", "-q", "--orphan", "unrelated")
        self.write("entry", "other history")
        self.commit("second root")
        run = self.run_check("--range", "main...unrelated")
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(run.stdout, "")
        self.assertIn("共同祖先", run.stderr)
