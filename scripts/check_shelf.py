#!/usr/bin/env python3
"""Structural and hygiene checks for this skills shelf.

Usage:
    python3 scripts/check_shelf.py                      # structure + hygiene
    python3 scripts/check_shelf.py --compare DIR [...]  # also check text overlap with DIR
    python3 scripts/check_shelf.py --release            # also gate a public release

Checks (exit code 1 if any check fails):
  skills     every skills/<slug>/SKILL.md has YAML frontmatter with `name` and
             `description`; name equals the directory name, is lowercase
             letters/digits/hyphens, <= 64 chars; description is 1..1024 chars
             and contains no angle brackets.
  plugin     .claude-plugin/marketplace.json (required) and the optional
             .claude-plugin/plugin.json / .cursor-plugin/plugin.json parse, carry
             the required fields, and every plugin source / skills path resolves
             to an existing directory inside the repo.
  hygiene    no absolute home paths, e-mail addresses, or zero-width characters
             in text files.
  overlap    (only with --compare) no normalized line of 25+ characters and no
             8-word run (change with --shingle N) in skills/ also appears in
             the compared directories.
             Words are ASCII letters/digits, so text in other scripts (e.g.
             Japanese) is only covered by the line comparison.
  release    (only with --release) no {{PLACEHOLDER}} left in the repo and no
             internal planning files (see INTERNAL_PATHS) in the tree.

Passing all checks is necessary, not sufficient: review every file before
making the repository public.

Standard library only (Python 3.9+).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TEXT_SUFFIXES = {".md", ".json", ".py", ".txt", ".yml", ".yaml", ".html", ".sh", ".mdc", ".template", ".toml"}
SKIP_DIRS = {".git", ".claude", "__pycache__", "node_modules", ".venv", "venv", ".mypy_cache", ".pytest_cache"}
HOME_PATH_RE = re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+/")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
ZERO_WIDTH_RE = re.compile("[" + "".join(map(chr, (0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF))) + "]")
PLACEHOLDER_RE = re.compile(r"\{\{[A-Z0-9_]+\}\}")
# Addresses that are allowed to appear (e.g. git attribution examples).
EMAIL_ALLOW = {"noreply@anthropic.com"}
# Private planning material that must not ship in the public repository.
INTERNAL_PATHS = ("claude-skills-shelf-spec.html", "TODO.md", "reports")
MIN_LINE = 25
SHINGLE = 8
FENCE_RE = re.compile(r"^---[ \t]*$", re.MULTILINE)


def parse_frontmatter(text: str) -> dict[str, str] | None:
    """Parse the flat frontmatter used by SKILL.md files.

    Supports `key: value`, quoted values, and `>` / `|` block scalars whose
    indented continuation lines are joined. Nested mappings are skipped.
    Returns None when the frontmatter is missing or malformed.
    """
    text = text.replace("\r\n", "\n")
    if not FENCE_RE.match(text):
        return None
    start = text.index("\n") + 1
    close = FENCE_RE.search(text, start)
    if close is None:
        return None
    lines = text[start:close.start()].splitlines()
    fields: dict[str, str] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line.strip() or line.lstrip().startswith("#") or line[0] in " \t":
            continue
        key, sep, value = line.partition(":")
        if not sep:
            return None
        value = value.strip()
        if value[:1] in (">", "|"):
            block = []
            while i < len(lines) and (not lines[i].strip() or lines[i][0] in " \t"):
                block.append(lines[i].strip())
                i += 1
            joiner = " " if value[0] == ">" else "\n"
            value = joiner.join(b for b in block if b)
        fields[key.strip()] = value.strip("\"'")
    return fields


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def check_skills(root: Path) -> list[str]:
    errors: list[str] = []
    skill_files = sorted((root / "skills").glob("*/SKILL.md"))
    if not skill_files:
        return ["skills: no skills/<slug>/SKILL.md found"]
    for path in skill_files:
        rel = path.relative_to(root)
        fm = parse_frontmatter(_read(path))
        if fm is None:
            errors.append(f"{rel}: missing or malformed frontmatter")
            continue
        name = fm.get("name", "")
        desc = fm.get("description", "")
        if name != path.parent.name:
            errors.append(f"{rel}: name '{name}' != directory '{path.parent.name}'")
        if not NAME_RE.match(name) or len(name) > 64:
            errors.append(f"{rel}: name must be lowercase-hyphen, <= 64 chars")
        if not 1 <= len(desc) <= 1024:
            errors.append(f"{rel}: description length {len(desc)} not in 1..1024")
        if "<" in desc or ">" in desc:
            errors.append(f"{rel}: description must not contain angle brackets")
    return errors


def _load_json(path: Path, errors: list[str]) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{path.name}: not found")
        return None
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        errors.append(f"{path.name}: invalid JSON ({exc})")
        return None
    if not isinstance(data, dict):
        errors.append(f"{path.name}: top level must be an object")
        return None
    return data


def _inside(root: Path, rel: object) -> Path | None:
    if not isinstance(rel, str):
        return None
    target = (root / rel).resolve()
    return target if target.is_dir() and root in [target, *target.parents] else None


def check_plugin(root: Path) -> list[str]:
    errors: list[str] = []
    market = _load_json(root / ".claude-plugin" / "marketplace.json", errors)
    if market is not None:
        name = market.get("name")
        if not isinstance(name, str) or not name:
            errors.append("marketplace.json: missing name")
        elif not NAME_RE.match(name):
            errors.append("marketplace.json: name must be kebab-case")
        owner = market.get("owner")
        if not isinstance(owner, dict) or not owner.get("name"):
            errors.append("marketplace.json: missing owner.name")
        plugins = market.get("plugins")
        if not isinstance(plugins, list) or not plugins:
            errors.append("marketplace.json: plugins must be a non-empty list")
            plugins = []
        for entry in plugins:
            if not isinstance(entry, dict):
                errors.append("marketplace.json: plugin entry must be an object")
                continue
            label = entry.get("name") or "?"
            if not entry.get("name"):
                errors.append("marketplace.json: plugin entry without name")
            source = entry.get("source")
            if isinstance(source, str):
                if not source.startswith("./"):
                    errors.append(f"marketplace.json: {label}: relative source must start with ./")
                elif _inside(root, source) is None:
                    errors.append(f"marketplace.json: {label}: source {source} is not a directory in the repo")
            elif not isinstance(source, dict):
                errors.append(f"marketplace.json: {label}: missing source")
            if "skills" in entry:
                skills = entry["skills"]
                for rel in skills if isinstance(skills, list) else [skills]:
                    if _inside(root, rel) is None:
                        errors.append(f"marketplace.json: {label}: skills path {rel!r} is not a directory in the repo")
    # Plugin manifests are optional; validate whichever ones exist.
    for manifest in (root / ".claude-plugin" / "plugin.json", root / ".cursor-plugin" / "plugin.json"):
        if not manifest.exists():
            continue
        label = manifest.relative_to(root)
        plugin = _load_json(manifest, errors)
        if plugin is None:
            continue
        name = plugin.get("name")
        if not isinstance(name, str) or not NAME_RE.match(name):
            errors.append(f"{label}: name missing or not kebab-case")
        skills = plugin.get("skills", [])
        for rel in skills if isinstance(skills, list) else [skills]:
            if _inside(root, rel) is None:
                errors.append(f"{label}: skills path {rel!r} is not a directory in the repo")
    return errors


def iter_text_files(root: Path):
    for path in sorted(root.rglob("*")):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.is_file() and (path.suffix in TEXT_SUFFIXES or path.name == "LICENSE"):
            yield path


def check_hygiene(root: Path) -> list[str]:
    errors: list[str] = []
    for path in iter_text_files(root):
        rel = path.relative_to(root)
        for no, line in enumerate(_read(path).splitlines(), 1):
            if HOME_PATH_RE.search(line):
                errors.append(f"{rel}:{no}: absolute home path")
            for mail in EMAIL_RE.findall(line):
                if mail not in EMAIL_ALLOW:
                    errors.append(f"{rel}:{no}: e-mail address")
            if ZERO_WIDTH_RE.search(line):
                errors.append(f"{rel}:{no}: zero-width character")
    return errors


def check_release(root: Path) -> list[str]:
    errors = [f"{rel}: internal planning file must not ship" for rel in INTERNAL_PATHS if (root / rel).exists()]
    internal = tuple(root / rel for rel in INTERNAL_PATHS)
    for path in iter_text_files(root):
        if path == Path(__file__).resolve() or any(p == path or p in path.parents for p in internal):
            continue
        for no, line in enumerate(_read(path).splitlines(), 1):
            for token in PLACEHOLDER_RE.findall(line):
                errors.append(f"{path.relative_to(root)}:{no}: unresolved placeholder {token}")
    return errors


def _norm(line: str) -> str:
    line = re.sub(r"[`*_>#|\-]+", " ", line.lower())
    return re.sub(r"\s+", " ", line).strip()


def _lines(text: str) -> set[str]:
    return {n for n in (_norm(x) for x in text.splitlines()) if len(n) >= MIN_LINE}


def _shingles(text: str, n: int = SHINGLE) -> set[tuple[str, ...]]:
    words = re.findall(r"[a-z0-9']+", text.lower())
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def check_overlap(root: Path, compare_dirs: list[Path], n: int = SHINGLE) -> tuple[list[str], list[str]]:
    """Return (errors, summary lines) for text shared with compare_dirs."""
    ref_lines: set[str] = set()
    ref_shingles: set[tuple[str, ...]] = set()
    count = 0
    for base in compare_dirs:
        for path in sorted(base.rglob("*")):
            if path.is_file() and path.suffix in TEXT_SUFFIXES:
                text = _read(path)
                ref_lines |= _lines(text)
                ref_shingles |= _shingles(text, n)
                count += 1
    errors: list[str] = []
    summary = [f"compared against {count} files in {len(compare_dirs)} dir(s)"]
    for path in sorted((root / "skills").rglob("*")):
        if not path.is_file():
            continue
        text = _read(path)
        rel = path.relative_to(root)
        shared_lines = sorted(_lines(text) & ref_lines)
        shared_shingles = _shingles(text, n) & ref_shingles
        summary.append(f"{rel}: shared lines={len(shared_lines)} shared {n}-word shingles={len(shared_shingles)}")
        for line in shared_lines:
            errors.append(f"{rel}: line also in compared dir: {line[:80]}")
        for shingle in sorted(shared_shingles):
            errors.append(f"{rel}: {n}-word run also in compared dir: '{' '.join(shingle)}'")
    return errors, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--compare", type=Path, nargs="+", default=[],
                        help="directories whose text must not appear in skills/")
    parser.add_argument("--shingle", type=int, default=SHINGLE,
                        help=f"word-run length for --compare (default {SHINGLE}; lower = stricter)")
    parser.add_argument("--release", action="store_true",
                        help="also fail on placeholders and internal planning files")
    args = parser.parse_args(argv)
    root = args.root.resolve()

    results = {
        "skills": check_skills(root),
        "plugin": check_plugin(root),
        "hygiene": check_hygiene(root),
    }
    summary: list[str] = []
    if args.compare:
        missing = [d for d in args.compare if not d.is_dir()]
        if missing:
            parser.error(f"not a directory: {missing[0]}")
        if args.shingle < 2:
            parser.error("--shingle must be at least 2")
        results["overlap"], summary = check_overlap(root, [d.resolve() for d in args.compare], args.shingle)
    if args.release:
        results["release"] = check_release(root)

    for line in summary:
        print(f"  {line}")
    failed = 0
    for name, errors in results.items():
        print(f"[{'FAIL' if errors else 'PASS'}] {name}")
        for err in errors:
            print(f"    {err}")
        failed += bool(errors)
    print(f"{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
