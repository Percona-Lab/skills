# Testing Percona Skills (internal dogfood)

This is the v0.1 dogfood guide. Anyone with repo access is welcome to try it: get the four skills running in your own AI tool, use them in your real work for a week or so, and tell us what's wrong or missing. The feedback decides whether this becomes a public, supported deliverable or stays an experiment.

## 1. Install (with repo access)

While the repo is private, the public installers (`npx skills add ...`, the raw-content `curl ...`) won't work. Use git clone + symlinks instead:

```bash
# Clone once
git clone git@github.com:Percona-Lab/skills.git ~/code/percona-skills

# Symlink each skill into Claude Code's skill folder
mkdir -p ~/.claude/skills
for skill in percona-dk-mcp mysql-to-percona xtrabackup-recipes percona-toolkit-recipes; do
  ln -s ~/code/percona-skills/$skill ~/.claude/skills/$skill
done
```

For Cursor, Windsurf, or Codex, swap the target directory:
- **OpenAI Codex:** `~/.agents/skills/`
- **Cursor, Windsurf, Gemini CLI:** see each tool's skills / extensions docs

To pick up updates: `git -C ~/code/percona-skills pull`. All symlinks pick up the new content automatically.

## 2. Enable Percona DK (recommended)

The skills lean on the percona-dk MCP for fresh, version-specific facts. Enable it in Claude Code:

```bash
claude mcp add --transport sse percona-dk https://pdk.percona.com/sse
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

- **Flip the repo public** on Percona-Lab if the skills hold up to real-work testing.
- **Continue investing** in the roadmap (PMM, PSMDB, PBM, PXC, Operators, PG migration, Mongo migration) if it's valuable.
- **Pull into a Percona-supported deliverable** if external traction follows publication.

Your feedback drives all three calls.
