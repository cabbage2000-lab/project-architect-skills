import unittest
from pathlib import Path


class SkillEntryTests(unittest.TestCase):
    def test_project_skill_entries_resolve_to_the_shared_source(self):
        root = Path(__file__).resolve().parents[1]
        source = root / "skills" / "project-architect-skills"
        for host in (".agents", ".claude", ".workbuddy", ".codebuddy"):
            with self.subTest(host=host):
                entry = root / host / "skills" / source.name
                self.assertFalse(entry.readlink().is_absolute())
                self.assertEqual(entry.resolve(strict=True), source)


if __name__ == "__main__":
    unittest.main()
