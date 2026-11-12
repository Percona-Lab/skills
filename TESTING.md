# Testing Percona Skills (internal dogfood)

This is the v0.1 dogfood guide. Anyone with repo access is welcome to try it: get the skills running in your own AI tool, use them in your real work for a week or so, and tell us what's wrong or missing. The feedback decides whether this becomes a public, supported deliverable or stays an experiment.

## 1. Install (with repo access)

The repo is public, so the installers work: `npx skills add Percona-Lab/skills` (interactive) or the raw-content `curl` per the README. For local iteration on the skills themselves, git clone + symlinks is handy:

```bash
# Clone once
git clone git@github.com:Percona-Lab/skills.git ~/code/percona-skills

# Symlink each skill into Claude Code's skill folder
mkdir -p ~/.claude/skills
for d in ~/code/percona-skills/*/SKILL.md; do
  skill=$(basename "$(dirname "$d")")
  ln -sfn ~/code/percona-skills/$skill ~/.claude/skills/$skill
done
```

For Cursor, Windsurf, or Codex, swap the target directory:
- **OpenAI Codex:** `~/.agents/skills/`
- **Cursor, Windsurf, Gemini CLI:** see each tool's skills / extensions docs

To pick up updates: `git -C ~/code/percona-skills pull`. All symlinks pick up the new content automatically.

Claude Code users can install the plugin instead (see the README): `/plugin marketplace add Percona-Lab/skills`, then `/plugin install percona-skills@percona-skills`. Use one route, not both: with the symlinks and the plugin installed you get every skill twice, once as `/<skill>` and once as `/percona-skills:<skill>`.

## 2. Enable Percona DK (recommended)

The skills lean on the percona-dk MCP for fresh, version-specific facts. Today it's self-hosted - one line clones it, builds the local index, and auto-configures Claude Code, Cursor, and Windsurf:

```bash
curl -fsSL https://raw.githubusercontent.com/Percona-Lab/percona-dk/main/install-percona-dk | bash
```

For other agents, see [`percona-dk-mcp/SKILL.md`](percona-dk-mcp/SKILL.md) for per-tool configuration. Without DK, the skills still work; the agent will note when an answer would benefit from fresher docs.

## 3. Try these prompts

Start a fresh AI session for each. Watch what happens: does the right skill load? Does the agent call DK? Is the answer correct?

### mysql-to-percona

- "What's the difference between Percona Server and Percona XtraDB Cluster?"
- "I want to migrate from MySQL Enterprise to Percona Server. What plugin equivalents should I use for the audit log, thread pool, and PAM authentication?"
- "Does Percona Server 8.4 still have XtraDB as a storage engine?"
- "How do I enable per-user statistics in Percona Server 8.4?"
- "What's the right way to back up a 100GB Percona Server database?"

### percona-server-features

- "What does Percona Server for MySQL give me that community MySQL doesn't?"
- "I'm reviewing a schema that runs on Percona Server 8.4. Is there anything Percona-specific I should use for observability?"
- "Should I enable the thread pool on Percona Server for a workload with 5,000 short-lived connections?"
- "How do I automatically kill transactions that sit idle for too long on Percona Server?"

### mysql-query-optimization

- "This query is slow on Percona Server 8.4. How do I find out why?"
- "Which indexes on my Percona Server database are never used?"
- "How do I get rows examined and InnoDB I/O per query into the slow log?"
- "Should I drop this index? How can I test that safely first?"

### mysql-replication-ha

- "Set up a GTID-based replica of a Percona Server 8.4 source."
- "Should I use semi-sync replication, Group Replication, or PXC for HA?"
- "My script runs SHOW SLAVE STATUS and broke after upgrading to 8.4. Why?"
- "How do I monitor replication lag accurately?"

### mysql-encryption

- "Encrypt all InnoDB tablespaces and binary logs on Percona Server 8.4 using HashiCorp Vault."
- "How do I rotate the master encryption key, and does it re-encrypt all my data?"
- "My server won't start after I enabled redo log encryption. What did I miss?"
- "Is binary log encryption an Enterprise-only feature?"

### mysql-audit-logging

- "Set up audit logging on Percona Server 8.4 that logs only connections and writes to the sales database."
- "I created an audit filter but nothing shows up in the log. Why?"
- "How do I migrate from the old audit_log plugin to the Audit Log Filter component?"

### mysql-data-masking

- "Mask credit card numbers and emails for a reporting user on Percona Server."
- "Generate realistic fake data for a test database."
- "If I use mask_pan() in a view, is the underlying column protected?"

### mysql-js-stored-procedures

- "Can I write a stored procedure in JavaScript on Percona Server?"
- "Write a JS stored function that parses a JSON column and returns a normalized string."
- "Can my JavaScript routine call an external HTTP API?"

### oracle-to-percona

- "Is there an Oracle compatibility mode in Percona Server like MariaDB has?"
- "Convert this Oracle query using CONNECT BY PRIOR and ROWNUM to Percona Server."
- "How should I map Oracle NUMBER, VARCHAR2, and DATE types?"
- "Port an Oracle PL/SQL package with a sequence to Percona Server 8.4."

### Routing and negative checks

These should load the named skill, a neighbouring skill, or none. Wrong routing is worth an issue.

- "My PXC cluster lost a node during a backup." should load `pxc-galera-operations`, maybe `xtrabackup-recipes`. It should not load `mysql-replication-ha`.
- "Write a PerconaServerMongoDB CR with PBM backups to S3." should load `percona-operators-on-k8s` before `pbm-recipes`.
- "How do I migrate from MySQL to MariaDB?" should not recommend Percona tooling as if it were MariaDB-compatible, and no migration skill should claim MariaDB is a drop-in.
- "Explain what a B-tree index is." should load no Percona skill.

### xtrabackup-recipes

- "How do I take an encrypted incremental backup with XtraBackup 8.4?"
- "I need to back up a PXC node so it can be used as an SST source. What flags do I need?"
- "Stream a XtraBackup backup to S3 using xbcloud."
- "What's the default compression algorithm in PXB 8.4? What changed from 8.0?"
- "My XtraBackup --prepare is failing on an incremental chain. Walk me through the correct prepare sequence."

### percona-toolkit-recipes

- "I need to ALTER a 50M-row table on a live production database without downtime. What's the safest way?"
- "How do I archive old rows from a busy table without overwhelming replication?"
- "My replicas might be out of sync with the source. How do I verify and fix?"
- "Why is my pt-online-schema-change failing on a table with foreign keys?"
- "Analyze a slow query log and show me the top time consumers."

### pmm-operations

- "Install a PMM server and add a MySQL instance to monitoring."
- "I added a MongoDB instance to PMM but Query Analytics is empty. Why?"
- "My PMM client won't register, I get a 404 at config time. What's wrong?"
- "How do I write a custom metric query for the PostgreSQL exporter in PMM?"

### psmdb-features

- "How do I enable data-at-rest encryption on Percona Server for MongoDB 8.0 with HashiCorp Vault?"
- "Set up audit logging on PSMDB and only log authentication events."
- "Does PSMDB support LDAP authentication? How is it different from MongoDB Enterprise?"
- "I'm upgrading PSMDB from 7.0 to 8.0 - anything about Transparent Huge Pages I should know?"

### pbm-recipes

- "Take a physical backup of my MongoDB replica set and enable point-in-time recovery."
- "Restore my sharded cluster to a specific timestamp with PBM."
- "I want to restore only one database from a PBM backup."
- "Walk me through a PBM physical restore - what are the gotchas?"

### pxc-galera-operations

- "My whole 3-node PXC cluster went down after a power outage. How do I bring it back?"
- "How do I add a new node to a running PXC cluster, and when does it do SST vs IST?"
- "What's the safest way to run a large ALTER TABLE on a PXC cluster?"
- "Why did my 2-node PXC cluster stop accepting writes when one node failed?"

### percona-operators-on-k8s

- "Write a Custom Resource for a 3-node Percona PostgreSQL cluster on Kubernetes."
- "How do I scale my PerconaXtraDBCluster from 3 to 5 nodes?"
- "Configure scheduled S3 backups for the Percona MongoDB operator."
- "How do I do a major version upgrade with the Percona PostgreSQL operator?"

### postgres-to-percona-pg

- "How do I migrate my existing PostgreSQL 17 server to Percona Distribution for PostgreSQL?"
- "Set up Transparent Data Encryption on Percona PostgreSQL with pg_tde and HashiCorp Vault."
- "What's the difference between pg_stat_monitor and pg_stat_statements?"
- "What's the recommended HA setup for Percona PostgreSQL?"

### mongodb-to-psmdb

- "How do I migrate a self-hosted MongoDB Community replica set to Percona Server for MongoDB?"
- "I'm on MongoDB Atlas and want to move to self-hosted PSMDB with no downtime. How?"
- "After upgrading PSMDB do I need to do anything about feature compatibility version?"
- "Can I just swap MongoDB Community binaries for PSMDB on the same data directory?"

### percona-dk-mcp (mostly exercised by the others, but try direct queries too)

- "What changed in Percona Server 8.4.7?"
- "Find Percona forum threads about WSREP gcs connect failures."
- "What's the latest version of Percona XtraBackup, and what compression algorithms does it support?"

## 4. File feedback

Open a feedback issue for each thing that's wrong, missing, or confusing:

**[Open a new feedback issue →](https://github.com/Percona-Lab/skills/issues/new?template=feedback.md)**

What we especially want to hear about:

- **Wrong facts** - any claim that doesn't match `docs.percona.com` or current product behavior
- **Missing things** - obvious gotchas, Percona-only features, or operational realities the skill skipped
- **Wrong scope** - the skill triggered when it shouldn't have, or didn't when it should have
- **Bad UX** - the agent answer was technically right but unusable for the real task

Quick fixes can also be a PR straight to the file. Small corrections (wrong facts, typos, broken links) do not need to wait for review.

DM Dennis on Slack for anything hard to put in an issue.

## 5. What we'll decide

After the dogfood window:

- **Promote beyond dogfood** (announce publicly, drop the "experiment" label) if the skills hold up to real-work testing.
- **Continue investing** in new skills (`mysql-server-tuning`, deeper Operator recipes, replication topologies) if it's valuable.
- **Pull into a Percona-supported deliverable** if external traction follows publication.

Your feedback drives all three calls.
