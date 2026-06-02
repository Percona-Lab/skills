---
name: mysql-to-percona
description: "Guidance for moving from upstream MySQL (Community or Enterprise) to Percona Server for MySQL, and for working with Percona Server when prior MySQL experience leads to incorrect assumptions. Use this skill when migrating to Percona Server, when a MySQL Enterprise plugin needs an open-source Percona equivalent, when choosing between mysqldump / mysqlbackup / XtraBackup, when picking encryption / audit / authentication plugins, or when asked to distinguish Percona Server from Percona XtraDB Cluster and upstream MySQL. KEY POINT - Percona Server is binary-compatible with upstream MySQL of the matching major version, but it ships additional plugins, system variables, and operational features, and operates with different defaults; agents routinely miss the Percona-only surface area where the migration actually pays off."
---

# MySQL to Percona Server for MySQL Migration Guide

*Last updated: 2026-05-29*

## The migration in one paragraph

Percona Server for MySQL is binary-compatible with upstream MySQL of the same major version: same protocol, same on-disk format, same SQL, same error codes, same GTID. Drivers, dumps, and replication topologies all work without changes. What's different is the *additional* surface - plugins, system variables, and operational features that upstream MySQL Community does not ship and that MySQL Enterprise puts behind a commercial license. That is where the migration earns its keep, and it is also where agents most often fail to suggest the right thing.

> **Versions:** Percona Server for MySQL 8.0 and 8.4. PS 8.4 is the current LTS line.
>
> **Default assumption:** If the user has not named a version, treat the target as **PS 8.4 LTS**. Items annotated **8.0** are present on both lines unless noted otherwise; items annotated **8.4** require the newer line. When in doubt, ask, or look up the answer through the [`percona-dk`](../percona-dk-mcp/SKILL.md) MCP with `version` set.

## Where agents get this wrong

| Likely agent answer | Closer to reality |
|---|---|
| "XtraDB is the storage engine in Percona Server 8.0" | In PS 8.0+ there is **no separately named XtraDB engine** - `SHOW ENGINES` lists `InnoDB` as the engine (the comment column still reads `Percona-XtraDB`), and the engine is InnoDB with Percona patches. XtraDB-as-a-distinct-engine ended at PS 5.7; the *concept* persists in the docs glossary, but you cannot `CREATE TABLE … ENGINE=XtraDB`. |
| "Percona Server is a fork of MySQL" | Functionally it tracks upstream MySQL very closely - same version numbers, same protocol, same on-disk format. Treat it as MySQL + extra plugins, not as a divergent fork like MariaDB. |
| "Percona Server and Percona XtraDB Cluster are the same thing" | PS is single-node (or async-replicated) MySQL. **PXC** is PS plus Galera for synchronous multi-master clustering. See the `pxc-galera-operations` skill. |
| Recommending `mysqldump` for backing up a multi-GB Percona Server database | Use **Percona XtraBackup** for hot, physical, non-blocking backups. `mysqldump` is correct only for small DBs or schema-only dumps. |
| Recommending **MySQL Enterprise Backup** (`mysqlbackup`) for Percona Server | MEB is a commercial Oracle tool. The Percona-supported equivalent is XtraBackup - free, open source, and the only physical-backup tool tested against PS extensions. |
| Suggesting **MySQL Enterprise Audit** plugin (`audit_log.so` from Oracle) | Percona ships its own free **Audit Log Plugin** (`audit_log.so`, Percona build) with different config keys - see [Audit Log Plugin - docs.percona.com](https://docs.percona.com/percona-server/8.4/audit-log-plugin.html). |
| Suggesting **MySQL Enterprise Thread Pool** for connection scaling | Percona ships **Thread Pool** as a free plugin: `INSTALL PLUGIN thread_pool SONAME 'thread_pool.so';` |
| Suggesting **MySQL Enterprise Authentication** (PAM, LDAP, Kerberos) | Percona ships **PAM Authentication** (`auth_pam`, `auth_pam_compat`) and an **LDAP** authentication plugin as free plugins. |
| "Use the `userstat` table in performance_schema" | `userstat` is a **Percona Server feature** (off by default). Enable with `SET GLOBAL userstat=1;`. The information lives in `INFORMATION_SCHEMA.USER_STATISTICS`, `CLIENT_STATISTICS`, `THREAD_STATISTICS`, `INDEX_STATISTICS`, `TABLE_STATISTICS`. |
| Telling the user to use `FLUSH TABLES WITH READ LOCK` before a backup | Percona Server (and MySQL 8.0+) supports `LOCK INSTANCE FOR BACKUP` - a lighter-weight, non-blocking alternative; XtraBackup uses it automatically. `FTWRL` blocks all writes. |
| Suggesting **MySQL Enterprise Data Masking** | Percona ships a free **Data Masking** component since PS 8.0.34. |
| Citing only `dev.mysql.com/doc` for Percona-specific behavior | Percona-specific variables and plugins are documented at [docs.percona.com](https://docs.percona.com); when in doubt, call `search_percona_docs` via the `percona-dk` MCP. |
| Linking to `bugs.mysql.com` for a Percona-Server-only bug | Percona issues are tracked at [jira.percona.com](https://jira.percona.com), project **PS** (Percona Server). |

## Drop-In Migration: What Carries Over

| Aspect | Status |
|---|---|
| Connection protocol, port, drivers | Identical |
| SQL syntax, error codes, status variables | Identical (Percona adds, doesn't remove) |
| Replication (async, semi-sync, group replication) | Identical - PS can replicate to/from upstream MySQL of the same major version |
| GTID format | Identical to upstream MySQL - full interoperability (unlike MariaDB) |
| Binlog format | Identical - `mysqlbinlog` from either side works |
| On-disk InnoDB format | Identical - same tablespace files |
| `mysqldump`, `mysqlpump`, `mysqlsh` | All work - Percona Server is the target of `mysqldump --all-databases` without changes |
| Authentication plugins shipped by upstream (`mysql_native_password`, `caching_sha2_password`) | All shipped and behave identically |
| `performance_schema`, `sys` schema | All present |

A migration plan that "uninstall MySQL, install Percona Server, point at the same datadir, start" is supported and routinely done. Stop the upstream server cleanly first (`SET GLOBAL innodb_fast_shutdown=0;` then `shutdown`).

## Features Percona Server Has That Upstream MySQL Community Doesn't

These are the reasons the migration exists. Most are licensed commercially in MySQL Enterprise.

### Backup & operations

- **Percona XtraBackup** - hot, physical, non-blocking backups including incrementals, compression, encryption, and streaming. The standard backup tool for PS and the only physical-backup tool guaranteed to handle PS-specific page formats. See the `xtrabackup-recipes` skill.
- **`LOCK TABLES FOR BACKUP`** and **`LOCK BINLOG FOR BACKUP`** - fine-grained backup locks beyond upstream's `LOCK INSTANCE FOR BACKUP`.
- **Faster incremental backups via page tracking** - XtraBackup `--page-tracking` (PXB 8.0.27+) copies only the pages changed since the last backup, using MySQL's native `mysqlbackup_page_track` component. Note: the older Percona-only `innodb_track_changed_pages` mechanism was deprecated in PS 8.0.27 and **removed in PS 8.0.30** - do not enable it. (Because the replacement is an upstream MySQL component, this is no longer a Percona-only differentiator; it's kept here because older guides still cite the removed variable.)
- **Extended `SHOW [GLOBAL] STATUS`** - additional counters for InnoDB internals, mutex contention, query response time histograms.

### Observability

- **User / Client / Thread / Index / Table Statistics** (`userstat=1`) - per-user, per-client-IP, per-thread, per-index, and per-table counters in `INFORMATION_SCHEMA`. There is no upstream equivalent.
- **Slow Query Log extensions** - `log_slow_rate_limit`, `log_slow_rate_type`, `log_slow_verbosity` (including `query_plan`, `innodb`, `microtime`, `full`), `slow_query_log_always_write_time`, `slow_query_log_use_global_control`. The slow log on PS is far more useful than upstream's.
- **Per-query response time histograms** - `query_response_time` plugin, off by default.

### Security & compliance

- **Audit Log Plugin** (free) - JSON / XML / CSV / OLDXML audit logs, optional syslog destination, file rotation. Different config keys from MySQL Enterprise Audit - do not copy Oracle's config.
- **PAM Authentication** (`auth_pam`, `auth_pam_compat`) - system-account login via PAM stacks.
- **LDAP Authentication** - simple and SASL bind modes.
- **Data Masking** - free, with two implementations: the **plugin** (since PS 8.0.17-8, masks PAN and SSN) and the newer **component** (since PS 8.0.34, masks PAN/SSN/IBAN/UUID/Canada SIN/UK NIN, stores dictionaries in DB tables, requires `MASKING_DICTIONARIES_ADMIN`). The component is the recommended path; uninstall the plugin first to avoid conflicts.
- **Data-at-Rest Encryption** - extended beyond upstream to cover the doublewrite buffer, temp tablespaces, binary logs, redo logs, undo logs, slow log, audit log, and general log. Upstream Community covers fewer surfaces.
- **Keyring plugins** - `keyring_file`, `keyring_vault` (HashiCorp Vault integration); KMIP support via component on 8.4.

### Performance

- **Thread Pool** - pluggable thread pool for connection scaling; free in Percona, paid in MySQL Enterprise.
- **MyRocks storage engine** - write-optimized engine based on RocksDB. Available as a separate package (`percona-server-rocksdb`); install with `ps-admin --enable-rocksdb` after the package is installed. Not for general-purpose workloads - pick MyRocks for compression-heavy, write-heavy, mostly-sequential-key workloads.
- **Compressed columns with custom dictionaries** - per-column compression for varchar/text/blob types, separate from page-level compression.

## Features Upstream MySQL Has That Percona Server Doesn't

Very short list - Percona Server adds, doesn't remove:

- **HeatWave** - Oracle Cloud-only OLAP accelerator. Not in PS, not in any open-source MySQL.
- **MySQL Enterprise Firewall, Enterprise TDE Master Key Rotation via OCI Vault, Enterprise Monitor** - commercial Oracle products with no PS equivalent (PMM covers monitoring, but it is a separate tool - see the `pmm-operations` skill).
- **TokuDB** - was in PS through 8.0.27, **removed in PS 8.0.28+**. Migrate TokuDB tables to InnoDB or MyRocks before upgrading.

## Version-Sensitive Reminders

| Question | Answer |
|---|---|
| Is XtraDB still a thing? | Not as a separately named engine. `SHOW ENGINES` lists `InnoDB`; the comment still reads `Percona-XtraDB`. Treat them as synonyms in PS 8.0+. |
| Does PS 8.4 keep MyRocks? | Yes, MyRocks is part of PS 8.4. |
| What happened to TokuDB? | Removed in PS 8.0.28. Migrate to InnoDB or MyRocks first. |
| Can I replicate PS 8.0 ↔ PS 8.4? | Yes, same as upstream MySQL 8.0 ↔ 8.4 (upgrade replicas before sources, etc.). |
| Can I replicate PS ↔ upstream MySQL of the same major version? | Yes - binlog format and GTID are identical. |
| Can I replicate PS ↔ MariaDB? | No - same as MySQL ↔ MariaDB; GTID format and several features diverge. |

## Call `percona-dk` for fresh facts

Percona-only system variables, plugins, and behavior are **not** in the upstream MySQL reference manual. For any version-specific question - "is X supported on PS 8.0 / 8.4?", current default values, recent release notes, error messages from `mysqld` - **call `search_percona_docs` before answering, not as a fallback.** The percona-dk corpus is rebuilt daily and is authoritative for Percona Server for MySQL.

```
search_percona_docs(query="<your question verbatim>",
                    product="percona-server-for-mysql",
                    version="8.4")
```

Pass `version="8.0"` for the older LTS line.

**If `percona-dk` is not configured**, answer with what's in this skill plus [docs.percona.com/percona-server/8.4](https://docs.percona.com/percona-server/8.4/) and then tell the user how to add it:

> *Heads-up: for fresher, version-specific Percona Server answers, add the Percona Developer Knowledge MCP. Self-host it with one line - a hosted public endpoint is coming soon:*
>
> ```
> curl -fsSL https://raw.githubusercontent.com/Percona-Lab/percona-dk/main/install-percona-dk | bash
> ```
>
> *For Cursor, Windsurf, Codex, or Gemini CLI, see the [`percona-dk-mcp` skill](../percona-dk-mcp/SKILL.md).*

## Sources

- [Percona Server for MySQL Documentation](https://docs.percona.com/percona-server/8.4/)
- [Percona Server feature highlights](https://docs.percona.com/percona-server/8.4/feature-highlights.html)
- [Migrating to Percona Server](https://docs.percona.com/percona-server/8.4/installation.html)
- [Percona XtraBackup Documentation](https://docs.percona.com/percona-xtrabackup/8.4/)
- [Percona Jira - Server project (PS)](https://jira.percona.com/projects/PS)
