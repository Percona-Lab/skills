#!/usr/bin/env python3
"""Static checks for the Percona skills pack. Stdlib only.

Errors (exit 1):
  - SKILL.md missing frontmatter, `name`, or `description`
  - `name` does not match the folder name
  - `description` longer than 1024 characters (Agent Skills limit)
  - a relative Markdown link that points at a file that does not exist
  - a skill missing from the README skills table
  - no skills found at all (layout changed?)
  - a skill folder missing from a plugin manifest's `skills` list, or a listed
    folder that is not a skill, or a manifest that is missing or not valid JSON
  - a SKILL.md below a skill's top folder (Codex would load it as a skill)
  - a root file or folder that Claude Code would load from the plugin root

Warnings (printed, exit 0 unless --strict):
  - a skill with no section in TESTING.md
  - a missing or stale `*Last updated: YYYY-MM-DD*` line (default > 120 days)
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DESC_MAX = 1024

# Plugin manifests that list skill folders. The repo root is the plugin root
# for both, so every skill folder must be listed in each.
MANIFESTS = {
    ".claude-plugin/marketplace.json": lambda d: [
        s for plugin in d.get("plugins", []) for s in plugin.get("skills", [])
    ],
    ".codex-plugin/plugin.json": lambda d: d.get("skills", []),
}

# Claude Code loads these from the plugin root on its own. A top-level bin/
# also stops claude.ai org sync from installing the plugin.
RESERVED_ROOT_NAMES = [
    "agents", "bin", "commands", "hooks", "monitors", "output-styles",
    "skills", "themes", "workflows", ".lsp.json", ".mcp.json", "settings.json",
]
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


def check_manifests(names, errors):
    """Each manifest lists every skill folder, and nothing else."""
    for rel, get_skills in MANIFESTS.items():
        path = ROOT / rel
        if not path.exists():
            errors.append(f"{rel}: missing")
            continue
        try:
            listed_raw = get_skills(json.loads(path.read_text()))
            if isinstance(listed_raw, str):
                listed_raw = [listed_raw]
            listed = {s.removeprefix("./").rstrip("/") for s in listed_raw}
        except (json.JSONDecodeError, AttributeError, TypeError) as e:
            errors.append(f"{rel}: cannot read skills list ({e})")
            continue
        for name in sorted(names - listed):
            errors.append(f"{rel}: skill {name} is not listed")
        for name in sorted(listed - names):
            errors.append(f"{rel}: lists {name}, which has no SKILL.md")


def check_layout(skills, errors):
    """Catch files that would load as extra skills or plugin components."""
    for d in skills:
        for nested in sorted(d.rglob("SKILL.md")):
            if nested.parent != d:
                errors.append(f"{nested.relative_to(ROOT)}: nested SKILL.md would load as its own skill")
    for name in RESERVED_ROOT_NAMES:
        if (ROOT / name).exists():
            errors.append(f"{name}: reserved plugin path at the repo root; Claude Code would load it for every install")


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

    if not skills:
        errors.append("no */SKILL.md found - did the layout change?")
    check_manifests({d.name for d in skills}, errors)
    check_layout(skills, errors)

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
