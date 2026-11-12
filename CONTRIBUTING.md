# Contributing

Thanks for helping make AI agents better at Percona.

## What a skill is (and isn't)

A SKILL.md is editorial guidance for an LLM, not documentation for a human. It exists because agents repeatedly get something wrong, or repeatedly miss something useful. Every claim in a skill should answer one of:

- *What does the agent assume about Percona that isn't true?*
- *What does the agent fail to suggest that it should?*
- *Where in [docs.percona.com](https://docs.percona.com) should it look next?*

If a section reads like a tutorial or product brochure, it doesn't belong in a skill. Put it in a blog post.

## Conventions

- **One folder per skill** at the repo root: `<skill-name>/SKILL.md`. Add a new folder to the `skills` lists in `.claude-plugin/marketplace.json` and `.codex-plugin/plugin.json` (`scripts/check_skills.py` fails the PR otherwise).
- **No `SKILL.md` below a skill's top folder**, and no `bin/`, `hooks/`, `commands/`, `agents/`, `skills/` or `.mcp.json` at the repo root: the repo root is the plugin root, so the plugins would load them.
- **Frontmatter** with `name` and a specific `description` - the description is what makes the agent decide whether to load the skill. Bad descriptions ("Percona MySQL stuff") never trigger; good descriptions enumerate the tasks and symptoms that should activate the skill.
- **Voice**: terse, imperative, no marketing language. Match the existing skills.
- **Wrong/right pairs** in a two-column table for every claim where the agent is likely to be wrong.
- **Version annotations** on everything version-sensitive:
  - Percona Server for MySQL / PXC / XtraBackup / PG Distribution: 8.0 vs 8.4 (PS/PXC) or 16 vs 17 (PG).
  - Percona Server for MongoDB: 6.0, 7.0, 8.0.
  - PMM: 2.x vs 3.x.
- **Links** to [docs.percona.com](https://docs.percona.com), Jira ([perconadev.atlassian.net](https://perconadev.atlassian.net)), and the relevant GitHub repo under [github.com/percona](https://github.com/percona).
- **Length**: SKILL.md should fit on one screen unless it genuinely needs more. Detail-heavy material goes in `references/*.md` (loaded by the agent on demand).
- **Reference the percona-dk MCP** in every skill where deeper lookup makes sense - pattern:
  > If `percona-dk` is available, call `search_percona_docs` with `query="<product> …", version="…"` (there is no `product` argument - name the product in the query).

## Filing an issue first

For new skills, substantive rewrites, or restructuring the skill list, please open an issue before sending a PR. Small fixes (typos, broken links, version bumps, additional wrong/right rows) can go straight to a PR.

## Local testing

Skills are plain markdown. To test against Claude Code:

```bash
git clone https://github.com/Percona-Lab/skills.git ~/code/percona-skills
mkdir -p ~/.claude/skills
ln -s ~/code/percona-skills/<skill-name> ~/.claude/skills/<skill-name>
```

Then start a fresh Claude Code session and ask a question the skill should activate on. Confirm the agent picks it up (Claude Code shows the loaded skill in its session header).

To test the plugin packaging from a local clone:

```bash
python3 scripts/check_skills.py
claude plugin validate .
claude plugin marketplace add ./          # then: claude plugin install percona-skills@percona-skills
claude plugin details percona-skills@percona-skills   # should list every skill
codex plugin marketplace add ./           # then install Percona from /plugins in Codex
```

## License

By contributing, you agree your contribution is licensed under the [MIT License](LICENSE).
