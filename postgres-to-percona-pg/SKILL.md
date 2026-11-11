---
name: postgres-to-percona-pg
description: "Migrating from community PostgreSQL to Percona Distribution for PostgreSQL, and using what the distribution adds. Use this skill when the user asks how to move a PostgreSQL install to the Percona distribution, what extensions and tools it bundles, how to set up Transparent Data Encryption with pg_tde, the difference between pg_stat_monitor and pg_stat_statements, or the Percona-recommended HA stack (Patroni + etcd + HAProxy). KEY POINTS - the core (Percona Server for PostgreSQL) is a binary-compatible drop-in, so same-server migration is a package swap on the existing data directory, not a dump/restore; and pg_tde's full `tde_heap` encryption (tables + indexes + WAL) requires Percona Server for PostgreSQL and is supported on PG 17.5+ and 18 (PG 16 build is tech preview only) - do not claim community PostgreSQL gets full TDE."
---

# Migrating to Percona Distribution for PostgreSQL

*Last updated: 2026-11-10*

Percona Distribution for PostgreSQL is community PostgreSQL plus a curated, co-tested set of extensions and tools. The core, **Percona Server for PostgreSQL**, is a binary-compatible, open-source drop-in replacement for upstream PostgreSQL (reported 100% on the PostgreSQL Compatibility Index for 17.6.1). Applications, drivers, SQL, and on-disk format are unchanged.

> **Versions:** latest releases are **18.6.1** and **17.11.1** (2026-09-29, both with `pg_tde` 2.2.2, `pg_stat_monitor` 2.4.0); PG 13 is EOL. Examples below use 17; for 18 swap the major number (`ppg-18`, `percona-postgresql-18`, `postgresql-18`). Extension versions below are as of 17.11.1 / 18.6.1.

## The migration in one paragraph

Because Percona Server for PostgreSQL is the same PostgreSQL underneath, a same-server migration is a **package swap on the existing data directory**, not a dump/restore: back up (recommended), stop the service, remove the community packages, install the Percona packages via `percona-release setup ppg-17` (apt) / `ppg17` (yum), restart. The installer reuses the existing cluster; the restore step is optional on the same server. A different-server migration does require restoring a backup on the target. The value you gain is the bundled stack: `pg_tde` (TDE), `pg_stat_monitor`, pgBackRest, Patroni/etcd/HAProxy for HA, pgAudit, and more.

## Where agents get this wrong

| Likely agent answer | Closer to reality |
|---|---|
| "Migrate with `pg_dumpall` then restore into Percona" (same server) | Same-server migration is a **package swap on the same data directory** - the underlying PostgreSQL binaries are the same major version, so the data dir carries over. Backup/restore is a safety net, not a required conversion. Dump/restore is only mandatory when moving to a different server. |
| "Use `pg_tde` to encrypt - it works on community PostgreSQL" | Full `tde_heap` encryption (tables, **indexes**, and WAL) requires **Percona Server for PostgreSQL** (it relies on Percona's SMGR/WAL API additions). The old community-compatible `tde_heap_basic` is **deprecated**. Community PostgreSQL has no path to full TDE. |
| "`tde_heap` encrypts tables but not indexes" | Backwards. `tde_heap` (full) encrypts tables, **indexes, and WAL**. `tde_heap_basic` (deprecated) was the one that left indexes unencrypted. It does **not** yet encrypt temporary files or statistics. |
| Enabling `pg_stat_monitor` alongside `pg_stat_statements` | Running both makes memory-block and WAL stats display inconsistently. Use `pg_stat_monitor` (it inherits all `pg_stat_statements` columns and adds time-bucketed stats, query plans, client IP, histograms) instead of both. |
| "etcd is required for Patroni" | Patroni supports etcd, ZooKeeper, Consul, and Kubernetes. etcd is Percona's **reference** choice (and what the distribution bundles), not a hard requirement. |
| Assuming standard WAL tooling works once WAL encryption is on | With `pg_tde` WAL encryption enabled, `pg_receivewal`, `pg_createsubscriber`, Barman, and default `pg_verifybackup` are unsupported. **pgBackRest works** only with `archive_command`/`restore_command` wrapped in `pg_tde_archive_decrypt` / `pg_tde_restore_encrypt` and with `archive-async`, `archive-header-check`, and `checksum-page` **disabled**. Percona ships TDE-aware variants: `pg_tde_basebackup`, `pg_tde_waldump`, `pg_tde_resetwal`, `pg_tde_rewind`. |
| Running Citus or TimescaleDB on Percona Server for PostgreSQL | **Not compatible** - Percona's core changes for `pg_tde` break them even when `pg_tde` is not enabled. |
| Citing `postgresql.org/docs` for Percona-distribution specifics | Core PostgreSQL behavior, yes - but the bundled extensions, `pg_tde`, and the HA solution are documented at [docs.percona.com](https://docs.percona.com). |

## What's bundled

Percona-authored: **pg_stat_monitor** (2.x), **pg_tde** (2.x). Third-party, co-tested: **pgBackRest**, **Patroni**, **etcd**, **HAProxy**, **PgBouncer**, **pgpool2**, **pgAudit** + **set_user**, **pg_repack**, **pg_cron**, **pgvector**, **PostGIS**, **wal2json**, **pgBadger**, and more. (Confirm exact versions for your release via the MCP.)

## Recipe: same-server migration

```bash
# 1. Back up (recommended): pg_dumpall + copy postgresql.conf, pg_hba.conf, postgresql.auto.conf
# 2. Stop PostgreSQL
systemctl stop postgresql                # RHEL: systemctl stop postgresql-17
# 3. Remove community packages
apt-get --purge remove postgresql        # RHEL: yum remove postgresql
# 4. Install Percona Distribution
percona-release setup ppg-17             # RHEL: percona-release setup ppg17
apt-get install percona-postgresql-17    # RHEL: yum install percona-postgresql17-server
# 5. Start; the existing data directory is reused
systemctl start postgresql               # RHEL: systemctl start postgresql-17
```

## Recipe: Transparent Data Encryption (pg_tde)

```sql
-- 1. Preload first (shared_preload_libraries is empty by default since 17.11.1 / 18.6.1):
ALTER SYSTEM SET shared_preload_libraries = 'pg_tde';
-- 2. Restart PostgreSQL (systemctl restart postgresql / postgresql-17)
-- 3. Then, in EACH database that needs it (or template1 for new DBs):
CREATE EXTENSION pg_tde;
-- configure a key provider (Vault / OpenBao / KMIP / local keyfile-dev only)
-- then set the principal key, and create encrypted tables with the tde_heap access method:
CREATE TABLE secret (id int) USING tde_heap;
```

`tde_heap` (full: tables + indexes + WAL) is supported on **Percona Server for PostgreSQL 17.5+** (and 18). The PG 16 build is **Tech Preview** - not officially supported, not for production. Key providers: HashiCorp Vault, OpenBao, KMIP servers, and a local keyfile (development only). WAL encryption reached GA in `pg_tde` 2.0 (shipped in Percona Distribution for PostgreSQL 17.5.3), but it is **opt-in**: it's off by default (`pg_tde.wal_encrypt`), and enabling it needs a configured global principal key and a server restart.

## Recipe: HA stack

Percona's documented HA architecture is **Patroni + etcd + HAProxy**, with pgBackRest for backup/DR and PMM for monitoring. Typical layout: 3 nodes each running PostgreSQL + Patroni + etcd, fronted by HAProxy with a virtual IP. On Kubernetes, use the Percona Operator for PostgreSQL (see `percona-operators-on-k8s`).

## Call `percona-dk` for fresh facts

Extension versions, `pg_tde` per-version availability, the exact package names, and bundled-component lists change between releases. For any of these, **call `search_percona_docs` with `version` set before writing it into a script, not as a fallback.**

```
search_percona_docs(query="Percona Distribution for PostgreSQL <your question verbatim>",
                    version="17")   # or "16"; PG 18 is not indexed yet - omit version, put "18" in the query
```

**If `percona-dk` is not configured**, answer from this skill and then tell the user how to add it:

> *For version-correct Percona PostgreSQL answers, add the Percona Developer Knowledge MCP. It is self-hosted today (a hosted endpoint is coming soon) - one line clones it, builds the local index, and auto-configures your client:*
> ```
> curl -fsSL https://raw.githubusercontent.com/Percona-Lab/percona-dk/main/install-percona-dk | bash
> ```
> *See the [`percona-dk-mcp` skill](../percona-dk-mcp/SKILL.md) for per-tool setup.*

## Key gotchas

- **Same-server migration is a package swap**, not a mandated dump/restore.
- **Full TDE (`tde_heap`) needs Percona Server for PostgreSQL** - community PostgreSQL can't get it; `tde_heap_basic` is deprecated.
- **`tde_heap` encrypts indexes and WAL too** - don't claim otherwise; it does not encrypt temp files or statistics.
- **Don't run `pg_stat_monitor` and `pg_stat_statements` together.**
- **Encrypted WAL breaks standard WAL tools** - use the `pg_tde_*` variants.
- **`pg_tde` on PG 16 is Tech Preview** - not for production; supported on 17.5+ and 18.
- **`pg_tde` goes in `shared_preload_libraries` + restart before `CREATE EXTENSION`.**
- **MD5 password auth is deprecated** (17.11.1 / 18.6.1) - use `scram-sha-256`.

## Sources

- [Migrating to Percona Distribution for PostgreSQL](https://docs.percona.com/postgresql/17/migration/)
- [Percona Server for PostgreSQL](https://docs.percona.com/postgresql/17/postgresql-server/)
- [pg_tde documentation](https://docs.percona.com/pg-tde/index.html) · [pg_tde limitations](https://docs.percona.com/pg-tde/index/tde-limitations.html)
- [pg_stat_monitor vs pg_stat_statements](https://docs.percona.com/pg-stat-monitor/comparison/)
- [HA with Patroni](https://docs.percona.com/postgresql/17/solutions/patroni-info/)
