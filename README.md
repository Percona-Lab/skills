# Percona Skills

> **Status: experiment.** This repo lives in [Percona-Lab](https://github.com/Percona-Lab), the org for things Percona is trying - not things Percona officially supports. The skills here are a starting point. Expect them to change, expect to find things that are wrong, [open an issue](https://github.com/Percona-Lab/skills/issues) or a PR if you do.
>
> **Currently in v0.1 internal dogfood.** Want to try it? See [TESTING.md](TESTING.md) for the install path, test prompts, and feedback flow.

*Brief your AI tools on Percona. Stop them from guessing.*

Short markdown briefings that AI coding agents (Claude Code, Cursor, Copilot, Codex, Gemini CLI, etc.) load automatically when a Percona topic comes up. Each skill is one file: it tells the agent what to recommend, what to avoid, and where to look something up. No fine-tuning, no integration. Drop a file in the agent's skills folder; it activates on every relevant question from then on.

## Skills

| Skill | What it covers |
|---|---|
| [`percona-dk-mcp`](percona-dk-mcp/SKILL.md) | When to query the Percona Developer Knowledge MCP, how to shape queries, how to scope by product and version. |
| [`mysql-to-percona`](mysql-to-percona/SKILL.md) | Drop-in migration from upstream MySQL to Percona Server for MySQL. The Percona-only plugins (audit, thread pool, PAM/LDAP, data masking) and the variables agents miss. |
| [`xtrabackup-recipes`](xtrabackup-recipes/SKILL.md) | Hot physical backups with Percona XtraBackup - full, incremental, streamed, compressed, encrypted, restored. PS 8.0 vs 8.4 differences. |
| [`percona-toolkit-recipes`](percona-toolkit-recipes/SKILL.md) | When to reach for `pt-online-schema-change`, `pt-archiver`, `pt-query-digest`, `pt-table-checksum` instead of the obvious-but-wrong alternative. |
| [`pmm-operations`](pmm-operations/SKILL.md) | Percona Monitoring and Management: install, client agents, Query Analytics, custom queries, alerting. PMM 2 vs 3 (and why they don't interoperate). |
| [`psmdb-features`](psmdb-features/SKILL.md) | Percona Server for MongoDB: hot backup, encryption, audit, LDAP/Kerberos/OIDC, in-memory engine - the MongoDB Enterprise features it ships free, with version gates. |
| [`pbm-recipes`](pbm-recipes/SKILL.md) | Percona Backup for MongoDB: logical/physical/incremental backups, PITR, selective restore, sharded clusters, the physical-restore footguns. |
| [`pxc-galera-operations`](pxc-galera-operations/SKILL.md) | Percona XtraDB Cluster: SST/IST, bootstrap after outage, flow control, split-brain/quorum, `pxc_strict_mode`, Clone SST. |
| [`percona-operators-on-k8s`](percona-operators-on-k8s/SKILL.md) | Operators for PXC/MongoDB/PostgreSQL/MySQL: CR patterns, backups, scaling, upgrades - and the per-operator field differences agents hallucinate. |

## Better together: Skills + Percona DK

The skills pair with the [Percona Developer Knowledge MCP server](https://github.com/Percona-Lab/percona-dk) (`percona-dk`) - semantic search over Percona's docs, blog, and forums, re-ingested daily. The skills tell the agent **what to recommend and what to avoid**; DK is the **version-correct ground truth** it looks the specifics up in before writing them into code.

- **DK alone:** the agent has authoritative facts on tap, but decides for itself when to look something up - so it can still lead with a weak default it never thought to check.
- **Skills alone:** the agent knows the right tool and the common traps, but fills in version-specific detail (flags, CR fields, current release) from training data, which has a cutoff.
- **Both together:** the skill nudges the agent toward the right answer *and* to call DK for the exact, current, cited specifics before emitting them into a script, playbook, or manifest. If DK isn't configured, the skill surfaces the one-line install command in context.

> Skills cover "what to say first"; DK covers "what's actually true on this version." How much they change a given answer depends on the model - a frontier model already avoids many bad defaults, while smaller and no-web agents gain the most.

## Roadmap

These are next - open an issue or PR if you'd like to pull one forward:

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

The agent reads each skill's `description` frontmatter at startup and loads the file on demand whenever a user prompt matches.

### Pair with Percona DK (recommended)

For full value, also run the Percona Developer Knowledge MCP. Today it's self-hosted - one line clones it, builds the local index, and auto-configures Claude Code, Claude Desktop, Cursor, and Windsurf:

```
curl -fsSL https://raw.githubusercontent.com/Percona-Lab/percona-dk/main/install-percona-dk | bash
```

See [`percona-dk-mcp/SKILL.md`](percona-dk-mcp/SKILL.md) and the [percona-dk README](https://github.com/Percona-Lab/percona-dk) for per-tool setup. A hosted public endpoint is coming soon. Without DK, the skills still work; the agent will note when an answer would benefit from fresher docs.

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
