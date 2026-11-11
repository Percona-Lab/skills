#!/usr/bin/env python3
"""Static checks for the Percona skills pack. Stdlib only.

Errors (exit 1):
  - SKILL.md missing frontmatter, `name`, or `description`
  - `name` does not match the folder name
  - `description` longer than 1024 characters (Agent Skills limit)
  - a relative Markdown link that points at a file that does not exist
  - a skill missing from the README skills table

Warnings (printed, exit 0 unless --strict):
  - a skill with no section in TESTING.md
  - a missing or stale `*Last updated: YYYY-MM-DD*` line (default > 120 days)
"""
import argparse
import datetime as dt
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DESC_MAX = 1024
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
FM_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def frontmatter(text):
    m = FM_RE.match(text)
    if not m:
        return None
    out = {}
    for line in m.group(1).splitlines():
        k, sep, v = line.partition(":")
        if sep and not line.startswith((" ", "\t")):
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            out[k.strip()] = v
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    ap.add_argument("--max-age-days", type=int, default=120)
    args = ap.parse_args()

    errors, warnings = [], []
    skills = sorted(p.parent for p in ROOT.glob("*/SKILL.md"))
    readme = (ROOT / "README.md").read_text()
    testing = (ROOT / "TESTING.md").read_text() if (ROOT / "TESTING.md").exists() else ""
    today = dt.date.today()

    for d in skills:
        name = d.name
        text = (d / "SKILL.md").read_text()
        fm = frontmatter(text)
        if fm is None:
            errors.append(f"{name}/SKILL.md: no YAML frontmatter")
            continue
        if fm.get("name") != name:
            errors.append(f"{name}/SKILL.md: name {fm.get('name')!r} != folder {name!r}")
        desc = fm.get("description", "")
        if not desc:
            errors.append(f"{name}/SKILL.md: empty description")
        elif len(desc) > DESC_MAX:
            errors.append(f"{name}/SKILL.md: description is {len(desc)} chars (max {DESC_MAX})")

        if f"({name}/SKILL.md)" not in readme:
            errors.append(f"README.md: skill {name} missing from the skills table")
        if not re.search(rf"^###\s+`?{re.escape(name)}`?\b", testing, re.M):
            warnings.append(f"TESTING.md: no '### {name}' prompt section")

        m = re.search(r"Last updated:\s*(\d{4}-\d{2}-\d{2})", text)
        if not m:
            warnings.append(f"{name}/SKILL.md: no 'Last updated' date")
        else:
            age = (today - dt.date.fromisoformat(m.group(1))).days
            if age > args.max_age_days:
                warnings.append(f"{name}/SKILL.md: last updated {age} days ago ({m.group(1)})")

    for md in sorted(ROOT.rglob("*.md")):
        if any(part.startswith(".") and part != ".github" for part in md.relative_to(ROOT).parts):
            continue
        in_code = False
        for i, line in enumerate(md.read_text().splitlines(), 1):
            if line.lstrip().startswith("```"):
                in_code = not in_code
            if in_code:
                continue
            for target in LINK_RE.findall(line):
                if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
                    continue
                path = target.split("#", 1)[0]
                if path and not (md.parent / path).exists():
                    errors.append(f"{md.relative_to(ROOT)}:{i}: broken relative link {target}")

    for w in warnings:
        print(f"warning: {w}")
    for e in errors:
        print(f"error: {e}")
    print(f"{len(skills)} skills checked, {len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors or (args.strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
