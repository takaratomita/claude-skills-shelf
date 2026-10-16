"""Tests for check_shelf.py. Run: python3 -m unittest discover -s scripts"""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import check_shelf

SKILL = """---
name: {name}
description: {desc}
---

# Body

Some instructions for the agent to follow carefully.
"""


def make_repo(tmp: Path, name="demo-skill", desc="Use when testing the checker.") -> Path:
    skill_dir = tmp / "skills" / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(SKILL.format(name=name, desc=desc), encoding="utf-8")
    (tmp / ".claude-plugin").mkdir()
    write_market(tmp, {
        "name": "demo-market",
        "owner": {"name": "someone"},
        "plugins": [{"name": "demo-plugin", "source": "./"}],
    })
    return tmp


def write_market(root: Path, data) -> None:
    text = data if isinstance(data, str) else json.dumps(data)
    (root / ".claude-plugin" / "marketplace.json").write_text(text, encoding="utf-8")


class ParseFrontmatterTest(unittest.TestCase):
    def test_folded_block_scalar_is_joined(self):
        fm = check_shelf.parse_frontmatter("---\nname: a\ndescription: >\n  long\n  text\n---\nx")
        self.assertEqual(fm["description"], "long text")

    def test_crlf_is_accepted(self):
        fm = check_shelf.parse_frontmatter("---\r\nname: a\r\ndescription: d\r\n---\r\nx")
        self.assertEqual(fm, {"name": "a", "description": "d"})

    def test_empty_frontmatter_has_no_fields(self):
        self.assertEqual(check_shelf.parse_frontmatter("---\n---\nbody"), {})

    def test_missing_closing_fence_is_malformed(self):
        self.assertIsNone(check_shelf.parse_frontmatter("---\nname: a\n----\nbody"))


class CheckShelfTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()

    def tearDown(self):
        self._tmp.cleanup()

    def test_valid_repo_passes_all_checks(self):
        root = make_repo(self.tmp)
        self.assertEqual(check_shelf.check_skills(root), [])
        self.assertEqual(check_shelf.check_plugin(root), [])
        self.assertEqual(check_shelf.check_hygiene(root), [])
        self.assertEqual(check_shelf.check_release(root), [])

    def test_name_must_match_directory(self):
        root = make_repo(self.tmp, name="other-name")
        self.assertTrue(any("!= directory" in e for e in check_shelf.check_skills(root)))

    def test_description_over_1024_chars_fails(self):
        root = make_repo(self.tmp, desc="x" * 1025)
        self.assertTrue(any("description length" in e for e in check_shelf.check_skills(root)))

    def test_description_with_angle_brackets_fails(self):
        root = make_repo(self.tmp, desc="Use when <tag> appears.")
        self.assertTrue(any("angle brackets" in e for e in check_shelf.check_skills(root)))

    def test_marketplace_source_outside_repo_fails(self):
        root = make_repo(self.tmp)
        write_market(root, {"name": "m", "owner": {"name": "o"}, "plugins": [{"name": "p", "source": "./missing"}]})
        self.assertTrue(any("not a directory" in e for e in check_shelf.check_plugin(root)))

    def test_marketplace_invalid_json_and_bad_entries_fail_without_crashing(self):
        root = make_repo(self.tmp)
        write_market(root, "{not json")
        self.assertTrue(any("invalid JSON" in e for e in check_shelf.check_plugin(root)))
        write_market(root, {"name": "m", "owner": {"name": "o"}, "plugins": ["oops"]})
        self.assertTrue(any("must be an object" in e for e in check_shelf.check_plugin(root)))

    def test_marketplace_entry_skills_must_resolve(self):
        root = make_repo(self.tmp)
        write_market(root, {"name": "m", "owner": {"name": "o"},
                            "plugins": [{"name": "p", "source": "./", "skills": [None, "./skills/demo-skill"]}]})
        errors = check_shelf.check_plugin(root)
        self.assertEqual(len([e for e in errors if "skills path" in e]), 1)

    def test_cursor_manifest_with_null_skills_fails_without_crashing(self):
        root = make_repo(self.tmp)
        (root / ".cursor-plugin").mkdir()
        (root / ".cursor-plugin" / "plugin.json").write_text('{"name": "p", "skills": null}', encoding="utf-8")
        self.assertTrue(any("skills path" in e for e in check_shelf.check_plugin(root)))

    def test_hygiene_flags_home_path_and_zero_width(self):
        root = make_repo(self.tmp)
        home = "/" + "Users/alice/"  # split so this file passes the hygiene check itself
        (root / "notes.md").write_text(f"see {home}secret\nhidden" + chr(0x200B), encoding="utf-8")
        errors = check_shelf.check_hygiene(root)
        self.assertTrue(any("absolute home path" in e for e in errors))
        self.assertTrue(any("zero-width" in e for e in errors))

    def test_hygiene_flags_email_except_allowlist(self):
        root = make_repo(self.tmp)
        user = "alice" + "@" + "example.com"
        (root / "notes.md").write_text(f"{user}\nnoreply" + "@anthropic.com\n", encoding="utf-8")
        errors = check_shelf.check_hygiene(root)
        self.assertEqual([e for e in errors if "e-mail" in e], ["notes.md:1: e-mail address"])

    def test_release_flags_placeholders_and_internal_files(self):
        root = make_repo(self.tmp)
        (root / "README.md").write_text("Buy: {{" + "KIT_URL}}\n", encoding="utf-8")
        (root / "TODO.md").write_text("internal\n", encoding="utf-8")
        errors = check_shelf.check_release(root)
        self.assertTrue(any("unresolved placeholder" in e for e in errors))
        self.assertTrue(any("TODO.md: internal planning file" in e for e in errors))

    def test_overlap_detects_copied_text_and_ignores_unrelated(self):
        root = make_repo(self.tmp)
        private = self.tmp / "private"
        private.mkdir()
        (private / "a.md").write_text("Totally unrelated words that never appear in the skill file.\n", encoding="utf-8")
        errors, _ = check_shelf.check_overlap(root, [private])
        self.assertEqual(errors, [])
        (private / "b.sh").write_text("Some instructions for the agent to follow carefully.\n", encoding="utf-8")
        errors, _ = check_shelf.check_overlap(root, [private])
        self.assertTrue(any("line also in compared dir" in e for e in errors))

    def test_main_exit_code_reflects_failures(self):
        root = make_repo(self.tmp)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(check_shelf.main(["--root", str(root)]), 0)
            (root / "TODO.md").write_text("internal\n", encoding="utf-8")
            self.assertEqual(check_shelf.main(["--root", str(root), "--release"]), 1)

    def test_compare_without_directory_is_rejected(self):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            check_shelf.main(["--compare"])


if __name__ == "__main__":
    unittest.main()
