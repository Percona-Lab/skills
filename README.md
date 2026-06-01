# Percona Skills

> **Status: experiment.** This repo lives in [Percona-Lab](https://github.com/Percona-Lab), the org for things Percona is trying - not things Percona officially supports. The skills here are a starting point. Expect them to change, expect to find things that are wrong, [open an issue](https://github.com/Percona-Lab/skills/issues) or a PR if you do.
>
> **Currently in v0.1 internal dogfood.** If you're one of the testers, see [TESTING.md](TESTING.md) for the install path, test prompts, and feedback flow.

Agent-side knowledge for working with Percona's open-source database software. Drop one of these into your coding agent and it stops guessing about Percona Server, Percona XtraDB Cluster, Percona Server for MongoDB, Percona XtraBackup, PBM, PMM, Percona Toolkit, and the Percona Kubernetes Operators - and starts answering from the things Percona actually ships.

These are **not** documentation. They are short, opinionated briefings aimed at the gaps where models get Percona wrong: confusing Percona Server with Percona XtraDB Cluster, suggesting `mysqldump` when XtraBackup is the right answer, citing MySQL Enterprise plugin names for Percona's free equivalents, missing `pt-online-schema-change` entirely. Each skill lists the wrong answer the agent is likely to give, the right answer, and a link to where the real documentation lives at [docs.percona.com](https://docs.percona.com).

## How this works

An *agent skill* is a small markdown file that agents like Claude Code, Cursor, Codex, Gemini CLI, and others load when a user's question matches the skill's description. You install the skill into your agent - nothing changes on your database. From then on, when the topic comes up, the agent reads the file and tailors its answer.

Skills in this repo follow the [Agent Skills](https://agentskills.io) convention, the same format used by other open-source skill packs.

## Better together: Skills + Percona DK

The skills are designed to be used alongside the [Percona Developer Knowledge MCP server](https://github.com/Percona-Lab/percona-dk) (`percona-dk`) at `https://pdk.percona.com/sse`. The MCP exposes semantic search over Percona's official documentation, blog, and community forum (~7K chunks, re-ingested daily).

The two solve different problems and stack:

- **DK alone:** the agent decides what to look up. Its bad defaults (recommend `mysqldump`, miss `pt-online-schema-change`, confuse Percona Server with PXC) win when it never looks up the right thing.
- **Skills alone:** the agent knows what to recommend, but answers from training data when version-specific detail is needed.
- **Both together:** Skills correct the defaults AND instruct the agent to call DK for fresh facts. The agent gives the right answer first, then verifies against current docs.

> Together they cover "what's true" (DK) and "what to say first" (Skills).

The product skills in this pack are written to call `search_percona_docs` **eagerly** for any version-specific question (release notes, "is X supported on Y?", error messages), not just as a fallback. If `percona-dk` is not configured when one of these questions comes up, the skill instructs the agent to tell you how to add it. The [`percona-dk-mcp`](percona-dk-mcp/SKILL.md) skill in this pack is the canonical reference for when and how the agent should use the MCP.

## v0.1 skills

| Skill | What it covers |
|---|---|
| [`percona-dk-mcp`](percona-dk-mcp/SKILL.md) | When to query the Percona Developer Knowledge MCP, how to shape queries, how to scope by product and version. |
| [`mysql-to-percona`](mysql-to-percona/SKILL.md) | Drop-in migration from upstream MySQL to Percona Server for MySQL. The Percona-only plugins (audit, thread pool, PAM/LDAP, data masking) and the variables agents miss. |
| [`xtrabackup-recipes`](xtrabackup-recipes/SKILL.md) | Hot physical backups with Percona XtraBackup - full, incremental, streamed, compressed, encrypted, restored. PS 8.0 vs 8.4 differences. |
| [`percona-toolkit-recipes`](percona-toolkit-recipes/SKILL.md) | When to reach for `pt-online-schema-change`, `pt-archiver`, `pt-query-digest`, `pt-table-checksum` instead of the obvious-but-wrong alternative. |

## Roadmap

These are next, in rough order of expected usefulness - open an issue or PR if you'd like to pull one forward:

- `pmm-operations` - Percona Monitoring and Management: install, client agents, custom queries, alerting.
- `psmdb-features` - Percona Server for MongoDB: hot backup, encryption, auditing, LDAP, things upstream MongoDB Community doesn't have.
- `pbm-recipes` - Percona Backup for MongoDB: PITR, selective restore, sharded clusters.
- `pxc-galera-operations` - Percona XtraDB Cluster operations: SST/IST, flow control, split-brain, bootstrap.
- `percona-operators-on-k8s` - Operators for MySQL, PXC, PostgreSQL, MongoDB: CR patterns, backups, scaling, upgrades.
- `postgres-to-percona-pg` - Migration to Percona Distribution for PostgreSQL.
- `mongodb-to-psmdb` - Migration to Percona Server for MongoDB.

## Installing

### With Node.js (`npx skills`)

The community [`skills` CLI](https://github.com/vercel-labs/skills) detects which agents you have installed and configures each one. Choose the skills you want from an interactive menu:

```
npx skills add Percona-Lab/skills
```

To pull a single skill:

```
npx skills add Percona-Lab/skills/mysql-to-percona
```

### Without Node.js

Each skill is a single `SKILL.md` file. Drop it into your agent's skill folder:

```bash
# Claude Code / Claude Desktop
mkdir -p ~/.claude/skills/mysql-to-percona
curl -L https://raw.githubusercontent.com/Percona-Lab/skills/main/mysql-to-percona/SKILL.md \
  -o ~/.claude/skills/mysql-to-percona/SKILL.md
```

- **Claude Code / Claude Desktop** - `~/.claude/skills/<skill-name>/SKILL.md`
- **OpenAI Codex** - `~/.agents/skills/<skill-name>/SKILL.md`
- **Cursor, Windsurf, Gemini CLI** - see each tool's skills / extensions documentation.

No further setup is needed for the skills themselves. The agent reads each skill's `description` frontmatter at startup and loads the file on demand whenever a user prompt matches what the skill is about.

### Pair with Percona DK (recommended)

For full value, also enable the Percona Developer Knowledge MCP. One line for Claude Code:

```
claude mcp add --transport sse percona-dk https://pdk.percona.com/sse
```

For other agents (Cursor, Windsurf, Codex, Gemini CLI), see [`percona-dk-mcp/SKILL.md`](percona-dk-mcp/SKILL.md) for per-tool configuration. Without DK, the skills still work; the agent will note when an answer would benefit from fresher docs and offer the install command in context.

## Prior art

This pack is shaped by - and grateful for - two earlier projects that established the conventions we follow:

- [**MariaDB/skills**](https://github.com/MariaDB/skills) (MIT, © Robert Silén / MariaDB) - the model for an open-source, vendor-curated skill pack covering a single database ecosystem. The "wrong answer / right answer" tabular framing and the `npx skills` install path come from there.
- [**villagesql/villagesql-skills**](https://github.com/villagesql/villagesql-skills) (Apache-2.0) - the model for repo layout, multi-agent install instructions, and the discipline of keeping `SKILL.md` thin with detail in `references/`.

Both are worth reading end-to-end if you want to write skills of your own.

The [Agent Skills](https://agentskills.io) convention is community-developed and tool-agnostic - Percona Skills are interoperable with any agent that supports it.

## Contributing

Issues and pull requests welcome. For new skills, sweeping rewrites, or anything that changes the launch set, please open an issue first to align on scope. Everything else - broken links, version corrections, additional wrong/right rows, clarifications - can go straight to a PR. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE). The skills reference, but do not redistribute, Percona documentation. "Percona", "XtraDB", "XtraBackup", and "PMM" are trademarks of Percona LLC.
