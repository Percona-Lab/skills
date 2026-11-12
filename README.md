# Percona Skills

> **Status: experiment.** This repo lives in [Percona-Lab](https://github.com/Percona-Lab), the org for things Percona is trying - not things Percona officially supports. The skills here are a starting point. Expect them to change, expect to find things that are wrong, [open an issue](https://github.com/Percona-Lab/skills/issues) or a PR if you do.
>
> **Currently in v0.1 internal dogfood.** Want to try it? See [TESTING.md](TESTING.md) for the install path, test prompts, and feedback flow.

*Brief your AI tools on Percona. Stop them from guessing.*

Short markdown briefings that AI coding agents (Claude Code, Cursor, Copilot, Codex, Gemini CLI, etc.) load automatically when a Percona topic comes up. Each skill tells the agent what to recommend, what to avoid, and where to look something up. No fine-tuning, no integration. Drop a skill folder in the agent's skills folder; it activates on every relevant question from then on.

## Skills

| Skill | What it covers |
|---|---|
| [`percona-dk-mcp`](percona-dk-mcp/SKILL.md) | When to query the Percona Developer Knowledge MCP, how to shape queries, how to scope by product and version. |
| [`mysql-to-percona`](mysql-to-percona/SKILL.md) | Drop-in migration from upstream MySQL to Percona Server for MySQL. The Percona-only plugins (audit, thread pool, PAM/LDAP, data masking) and the variables agents miss. |
| [`percona-server-features`](percona-server-features/SKILL.md) | What Percona Server adds over stock MySQL: User Statistics, the extended slow log, threadpool, backup locks, MyRocks, kill-idle-transaction, UUIDv7 - the things agents rarely suggest unprompted. The map to the feature-specific skills below. |
| [`mysql-query-optimization`](mysql-query-optimization/SKILL.md) | Diagnosing slow queries and designing indexes with Percona Server's extra instrumentation: `userstat`, the extended slow log, `pt-query-digest`, plus EXPLAIN ANALYZE, histograms, and invisible indexes. |
| [`mysql-replication-ha`](mysql-replication-ha/SKILL.md) | The non-Galera HA options: async/GTID, semi-synchronous, and Group Replication - how to choose, set up, and monitor them, plus the 8.4 SOURCE/REPLICA syntax. (Galera lives in `pxc-galera-operations`.) |
| [`mysql-encryption`](mysql-encryption/SKILL.md) | Data-at-rest encryption and keyring management: the master-key hierarchy, encrypting tablespaces/binlogs/redo-undo/temp files, the file/Vault/KMIP/AWS-KMS keyrings, and master-key rotation. |
| [`mysql-audit-logging`](mysql-audit-logging/SKILL.md) | The open-source Audit Log Filter: installing the component, the JSON filter rule DSL, assigning filters to users, and log formats/rotation/encryption. |
| [`mysql-data-masking`](mysql-data-masking/SKILL.md) | Masking PII and generating synthetic test data with the open-source masking component: the `mask_*`/`gen_*` functions, dictionaries, and why it is a presentation layer, not access control. |
| [`mysql-js-stored-procedures`](mysql-js-stored-procedures/SKILL.md) | Writing stored procedures and functions in JavaScript via the `js_lang` component (tech preview): syntax, privileges, the SQL↔JS type mapping, and the sandbox limits. |
| [`oracle-to-percona`](oracle-to-percona/SKILL.md) | Migrating from Oracle Database: why it is a true rewrite (no Oracle-compatibility mode, unlike MariaDB), data-type mapping, and rewriting PL/SQL, sequences, `ROWNUM`, and `CONNECT BY`. |
| [`xtrabackup-recipes`](xtrabackup-recipes/SKILL.md) | Hot physical backups with Percona XtraBackup - full, incremental, streamed, compressed, encrypted, restored. PS 8.0 vs 8.4 differences. |
| [`percona-toolkit-recipes`](percona-toolkit-recipes/SKILL.md) | When to reach for `pt-online-schema-change`, `pt-archiver`, `pt-query-digest`, `pt-table-checksum` instead of the obvious-but-wrong alternative. |
| [`pmm-operations`](pmm-operations/SKILL.md) | Percona Monitoring and Management: install, client agents, Query Analytics, custom queries, alerting. PMM 2 vs 3 (and why they don't interoperate). |
| [`psmdb-features`](psmdb-features/SKILL.md) | Percona Server for MongoDB: hot backup, encryption, audit, LDAP/Kerberos/OIDC, in-memory engine - the MongoDB Enterprise features it ships free, with version gates. |
| [`pbm-recipes`](pbm-recipes/SKILL.md) | Percona Backup for MongoDB: logical/physical/incremental backups, PITR, selective restore, sharded clusters, the physical-restore footguns. |
| [`pxc-galera-operations`](pxc-galera-operations/SKILL.md) | Percona XtraDB Cluster: SST/IST, bootstrap after outage, flow control, split-brain/quorum, `pxc_strict_mode`, Clone SST. |
| [`percona-operators-on-k8s`](percona-operators-on-k8s/SKILL.md) | Operators for PXC/MongoDB/PostgreSQL/MySQL: CR patterns, backups, scaling, upgrades - and the per-operator field differences agents hallucinate. |
| [`postgres-to-percona-pg`](postgres-to-percona-pg/SKILL.md) | Migration from community PostgreSQL to Percona Distribution for PostgreSQL: the package-swap path, pg_tde TDE, pg_stat_monitor, and the Patroni/etcd/HAProxy HA stack. |
| [`mongodb-to-psmdb`](mongodb-to-psmdb/SKILL.md) | Migration from MongoDB Community or Atlas to Percona Server for MongoDB: in-place swap, the PCSM live-migration tool, FCV, and config gotchas. |

## Who it's for

Anyone who points an AI coding agent at Percona software:

- **Operators and developers** writing install scripts, Ansible/Terraform, Kubernetes manifests, or runbooks - where a wrong flag, package name, or Custom Resource field ends up in real infrastructure.
- **Teams running agents without web access** (CI jobs, agentic pipelines) that can't fall back to a search engine.
- **Anyone migrating to or operating** Percona Server for MySQL, PXC, Percona Server for MongoDB, Percona Distribution for PostgreSQL, XtraBackup, PBM, PMM, the Kubernetes Operators, or Percona Toolkit.

The skills help most when the agent is about to *act* on a Percona-specific or version-specific detail: choosing the right tool (XtraBackup over `mysqldump`, `pt-online-schema-change` over a blocking `ALTER`), getting an operator CR field right, or avoiding a destructive default. For well-documented conceptual questions a capable model already handles, they add less - the value rises with how autonomous the agent is and how version-sensitive the task. Pairing with Percona DK (below) is what closes the version-specific gap.

## Better together: Skills + Percona DK

The skills pair with the [Percona Developer Knowledge MCP server](https://github.com/Percona-Lab/percona-dk) (`percona-dk`) - semantic search over Percona's docs, blog, and forums, re-ingested daily. The skills tell the agent **what to recommend and what to avoid**; DK is the **version-correct ground truth** it looks the specifics up in before writing them into code.

- **DK alone:** the agent has authoritative facts on tap, but decides for itself when to look something up - so it can still lead with a weak default it never thought to check.
- **Skills alone:** the agent knows the right tool and the common traps, but fills in version-specific detail (flags, CR fields, current release) from training data, which has a cutoff.
- **Both together:** the skill nudges the agent toward the right answer *and* to call DK for the exact, current, cited specifics before emitting them into a script, playbook, or manifest. If DK isn't configured, the skill surfaces the one-line install command in context.

> Skills cover "what to say first"; DK covers "what's actually true on this version." How much they change a given answer depends on the model - a frontier model already avoids many bad defaults, while smaller and no-web agents gain the most.

## Roadmap

The initial roadmap is complete. Candidate next skills:

- **`mysql-server-tuning`** - how to approach Percona server/knob tuning *safely and correctly*: which variables actually move the needle (buffer pool, redo log capacity, flushing, thread pool), version-specific defaults, the dangerous knobs, and measuring before/after with PMM and Query Analytics instead of pasting a `my.cnf` from an old blog post. Scoped to *guiding* the agent, not autonomous optimization - automatic knob-tuning remains an open research problem, and a skill should say so rather than pretend to solve it. (Distinct from `mysql-query-optimization`, which covers queries and indexes.)
- Deeper Operator recipes, replication topologies.

Open an issue to propose one, or a PR to add it.

> **Out of scope, by design.** These skills improve the *correctness of what an agent proposes* - the script, manifest, or config it writes for a human to review. They do not *enforce what an agent may execute* against a live database. Runtime safety (read-only or scoped credentials, sandboxes, query guardrails) lives in the database and the MCP/tooling layer, not in advisory skill files.

## Installing

### Claude Code plugin

```
/plugin marketplace add Percona-Lab/skills
/plugin install percona-skills@percona-skills
```

On Claude Code 2.1.275 or later this also works in one step: `/plugin install percona-skills --marketplace Percona-Lab/skills`. Skills show up as `/percona-skills:<skill>` and still load on their own when a prompt matches.

Every commit on `main` is a new version, but Claude Code doesn't auto-update third-party marketplaces by default, so fixes only arrive when you update. Run `/plugin marketplace update percona-skills`, or turn on auto-update for it under `/plugin` → Marketplaces.

### Codex plugin (experimental)

Not tested yet. Add the marketplace, then install **Percona** from the `/plugins` browser in Codex:

```
codex plugin marketplace add Percona-Lab/skills
```

If it doesn't load the skills, use `npx skills add` below or copy the folders into `~/.agents/skills/`.

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

Each skill is a folder: a `SKILL.md`, plus a `references/` directory for a few skills (`xtrabackup-recipes`, `percona-toolkit-recipes`, `pxc-galera-operations`, `percona-operators-on-k8s`). Copy the whole folder into your agent's skill folder:

```bash
# Claude Code / Claude Desktop - all skills
git clone --depth 1 https://github.com/Percona-Lab/skills.git /tmp/percona-skills
mkdir -p ~/.claude/skills
for d in /tmp/percona-skills/*/SKILL.md; do cp -r "$(dirname "$d")" ~/.claude/skills/; done

# Or a single-file skill only
mkdir -p ~/.claude/skills/mysql-to-percona
curl -L https://raw.githubusercontent.com/Percona-Lab/skills/main/mysql-to-percona/SKILL.md \
  -o ~/.claude/skills/mysql-to-percona/SKILL.md
```

A `curl` of `SKILL.md` alone is fine for skills without `references/`. For the four above, it silently drops the detail files the skill tells the agent to read.

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

## Authors and credits

This pack is maintained under [Percona-Lab](https://github.com/Percona-Lab). The Percona Server for MySQL ecosystem skills - `mysql-to-percona`, `percona-server-features`, `mysql-query-optimization`, `mysql-replication-ha`, `mysql-encryption`, `mysql-audit-logging`, `mysql-data-masking`, `mysql-js-stored-procedures`, and `oracle-to-percona` - originated in [**EvgeniyPatlan/percona-mysql-skills**](https://github.com/EvgeniyPatlan/percona-mysql-skills) by **Evgeniy Patlan**, and were merged here as part of consolidating the two packs into one home. Evgeniy co-maintains those skills (see [CODEOWNERS](.github/CODEOWNERS)); his sharper MySQL detail also strengthened the overlapping backup, toolkit, PXC, PMM, and operator skills.

## Contributing

Issues and pull requests welcome. For new skills, sweeping rewrites, or anything that changes the launch set, please open an issue first to align on scope. Everything else - broken links, version corrections, additional wrong/right rows, clarifications - can go straight to a PR. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE). The skills reference, but do not redistribute, Percona documentation. "Percona", "XtraDB", "XtraBackup", and "PMM" are trademarks of Percona LLC.
