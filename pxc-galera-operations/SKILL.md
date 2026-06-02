---
name: pxc-galera-operations
description: "Operating Percona XtraDB Cluster (PXC) - the Galera-based synchronous multi-master MySQL cluster. Use this skill when the user asks about SST vs IST, choosing or configuring `wsrep_sst_method`, bootstrapping a cluster after a full shutdown, recovering from a crash, flow control, split-brain / quorum, `pxc_strict_mode`, or why a write or DDL behaves differently in a cluster. KEY POINTS - bootstrapping a node into an already-running cluster creates a second divergent cluster; after an unclean full outage you must run `mysqld --wsrep-recover` to pick the bootstrap node rather than trusting `safe_to_bootstrap`; every table needs a primary key; and PXC 8.4 adds a Clone-plugin SST (`wsrep_sst_method=clone`) on top of the default `xtrabackup-v2`. Verify version-specific defaults before writing config."
---

# Percona XtraDB Cluster (PXC) / Galera Operations

*Last updated: 2026-06-02*

PXC is Percona Server for MySQL plus Galera: synchronous, virtually-multi-master replication where every node holds the full dataset and commits are certified cluster-wide. Most "it behaves weirdly" surprises come from Galera semantics, not MySQL.

> **Versions:** PXC **8.0** and **8.4**. Defaults differ in places (SST methods, XtraBackup-SST encryption) - noted per item.

## State transfers: SST vs IST

- **SST (State Snapshot Transfer):** a full data copy from a donor to a joining node. Default method is **`xtrabackup-v2`** (non-blocking; donor stays up).
- **IST (Incremental State Transfer):** transfers only the missing write-sets when a joiner is slightly behind, as long as the donor's gcache (`gcache.size`) still holds them. Cheaper than SST; falls back to SST automatically if the gap is too large.

`wsrep_sst_method` accepted values: `xtrabackup-v2` (default), `clone`, `ist_only` (8.0.33-25+). The old `skip` was **removed** in 8.0.33-25.

## Where agents get this wrong

| Likely agent answer | Closer to reality |
|---|---|
| "Bootstrap the node to bring it back into the cluster" (cluster still running) | Bootstrapping creates a **new** cluster. Doing it against a running cluster yields two divergent clusters. Only bootstrap when the **whole** cluster is down. A node rejoining a live cluster is started normally, not bootstrapped. |
| Trusting `safe_to_bootstrap` after an unclean full outage | After a crash/power-loss of all nodes, every `grastate.dat` shows `seqno: -1` and `safe_to_bootstrap: 0`. Run `mysqld --wsrep-recover` on each node, read the recovered `UUID:seqno` from the log, pick the highest seqno, set `safe_to_bootstrap: 1` there, then bootstrap from it. |
| `service mysql start` to bootstrap the first node | Bootstrap is `systemctl start mysql@bootstrap.service` (or `/etc/init.d/mysql bootstrap-pxc`). A normal start with a non-empty `gcomm://` tries to join existing members. |
| Running a 2-node cluster for HA | A 2-node cluster has no quorum tolerance: lose one node and the survivor stops serving (by design, to avoid split-brain). Use an **odd** number (3 or 5), or add an arbitrator (`garbd`). |
| Creating tables without a primary key | Galera requires primary keys for parallel apply. `wsrep_certify_nonPK` (on by default) auto-generates one, but the documented rule is: **all tables must have a primary key.** |
| Writing to MyISAM tables and expecting replication | `wsrep_replicate_myisam` is **OFF** by default; MyISAM DML is not replicated (DDL is). MyISAM-in-cluster is experimental and discouraged. |
| Running a big `ALTER TABLE` without thinking about DDL mode | Default `wsrep_OSU_method=TOI` applies DDL in total order across all nodes - a long ALTER effectively stalls cluster writes for its duration. Consider `RSU` (rolling, one node at a time) or `NBO` for long schema changes. |
| Disabling `pxc_strict_mode` to "make errors go away" | It exists to stop operations that break a cluster (no-PK tables, MyISAM writes, wrong `binlog_format`, `innodb_autoinc_lock_mode != 2`). On upgrade, start `PERMISSIVE`, fix warnings, then move to `ENFORCING`. |
| Using XtraBackup-level SST encryption (`[xtrabackup] encrypt=`) on PXC 8.4 | **Removed in 8.4** - PXC errors if it detects it. Use `pxc-encrypt-cluster-traffic` (on by default) for SST/IST/replication TLS. |

## Bootstrapping after a full shutdown

```bash
# Graceful full shutdown: highest seqno in grastate.dat is the most-advanced node.
grep seqno /var/lib/mysql/grastate.dat        # on each node

# Unclean outage (seqno: -1 everywhere): recover the position first.
mysqld --wsrep-recover                        # read "Recovered position UUID:seqno" from log
# Pick the node with the greatest seqno, then:
#   set safe_to_bootstrap: 1 in its grastate.dat
systemctl start mysql@bootstrap.service       # bootstrap ONLY that node
# Then start the remaining nodes normally - they join via IST or SST.
```

A bootstrap node has effectively `wsrep_cluster_address=gcomm://` (empty = create a new cluster). Other nodes list peers: `gcomm://10.0.0.1,10.0.0.2,10.0.0.3`.

## Flow control, quorum, split-brain

- **Flow control:** when a node's apply queue exceeds `gcs.fc_limit` (default 100, dynamically recalculated by node count), it pauses cluster-wide replication until it catches up. One slow node throttles everyone. `wsrep_desync=ON` removes a node from flow control (it falls behind without pausing the cluster; rejoining needs IST/SST).
- **Quorum:** only a partition holding a majority (>50%) stays Primary. Even splits (3+3) leave neither side with quorum and both stop serving - avoid even node counts.
- **Force a primary** only when the other side is truly dead: `SET GLOBAL wsrep_provider_options='pc.bootstrap=true';`. Setting it on both halves of a partition creates two clusters and an eventual emergency shutdown + full SST.
- Weight nodes with `pc.weight` (default 1) to bias which partition survives.

## pxc_strict_mode

Values: `DISABLED`, `PERMISSIVE`, `ENFORCING` (default), `MASTER`. Default is `ENFORCING`, except a standalone/bootstrapping node defaults to `DISABLED`. ENFORCING blocks unsupported operations outright; PERMISSIVE logs and continues. Note: validation happens on the **originating** node - an op let through on a DISABLED node is not re-checked on ENFORCING peers.

## Clone SST (PXC 8.4)

PXC 8.4 (8.4.4-x) adds MySQL Clone-plugin-based SST. Set `wsrep_sst_method=clone` on the joiner; `clone` must be in `wsrep_sst_allowed_methods` on both donor and joiner (8.4 default is `xtrabackup-v2, clone`). Requires the `CLONE_ADMIN` privilege and the NetCat package; default port 4444. (Clone is also available on the 8.0 line from 8.0.41+.) Both variables are read-only / config-file-only.

## Call `percona-dk` for fresh facts

PXC defaults and `wsrep_*` variable behavior shift between point releases (e.g. the exact release that changed SST defaults, removed `skip`, or added Clone). For any exact variable default, provider option, or version boundary, **call `search_percona_docs` with `version` set before writing it into config, not as a fallback.**

```
search_percona_docs(query="<your question verbatim>",
                    product="percona-xtradb-cluster",
                    version="8.4")   # or "8.0"
```

**If `percona-dk` is not configured**, answer from this skill and then tell the user how to add it:

> *For fresher, version-correct PXC answers, add the Percona Developer Knowledge MCP. Self-host it with one line - a hosted public endpoint is coming soon:*
> ```
> curl -fsSL https://raw.githubusercontent.com/Percona-Lab/percona-dk/main/install-percona-dk | bash
> ```
> *For other agents, see the [`percona-dk-mcp` skill](../percona-dk-mcp/SKILL.md).*

## Key gotchas

- **Never bootstrap into a running cluster.** It forks the cluster.
- **`mysqld --wsrep-recover`** is how you pick the bootstrap node after an unclean full outage - not `safe_to_bootstrap`.
- **Odd node counts** (3/5) or an arbitrator. Two-node clusters can't tolerate a failure.
- **Primary keys on every table.** MyISAM writes don't replicate by default.
- **TOI DDL stalls the cluster** - use RSU/NBO for long ALTERs.
- **8.4 dropped XtraBackup-SST encryption** - rely on `pxc-encrypt-cluster-traffic`.

## Sources

- [State Snapshot Transfer](https://docs.percona.com/percona-xtradb-cluster/8.0/state-snapshot-transfer/) · [Clone SST (8.4)](https://docs.percona.com/percona-xtradb-cluster/8.4/clone-sst/)
- [Crash recovery & bootstrap scenarios](https://docs.percona.com/percona-xtradb-cluster/8.0/crash-recovery/)
- [Strict mode](https://docs.percona.com/percona-xtradb-cluster/8.0/strict-mode/)
- [wsrep system variables](https://docs.percona.com/percona-xtradb-cluster/8.0/wsrep-system-index/) · [wsrep provider options](https://docs.percona.com/percona-xtradb-cluster/8.0/wsrep-provider-index/)
