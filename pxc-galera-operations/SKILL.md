---
name: pxc-galera-operations
description: "Operating Percona XtraDB Cluster (PXC) - the Galera-based synchronous multi-master MySQL cluster. Use this skill when the user asks about SST vs IST, choosing or configuring `wsrep_sst_method`, bootstrapping a cluster after a full shutdown, recovering from a crash, flow control, split-brain / quorum, `pxc_strict_mode`, schema-change modes (TOI/RSU), or why a write or DDL behaves differently in a cluster. KEY POINTS - every table MUST have a primary key and only InnoDB is replicated; transactions can fail at COMMIT with error 1213 (certification conflict, not a local deadlock) so apps must retry; bootstrapping a node into an already-running cluster creates a second divergent cluster; after an unclean full outage run `mysqld --wsrep-recover` to pick the bootstrap node rather than trusting `safe_to_bootstrap`; and PXC 8.4 adds a Clone-plugin SST (`wsrep_sst_method=clone`) on top of the default `xtrabackup-v2`. Verify version-specific defaults before writing config."
---

# Percona XtraDB Cluster (PXC) / Galera Operations

*Last updated: 2026-06-02*

PXC is Percona Server for MySQL plus Galera: synchronous, virtually-multi-master replication where every node holds the full dataset and commits are certified cluster-wide. A transaction's write-set is broadcast to all nodes and certified before commit; if it conflicts with a concurrent transaction on any node, the committing node rolls back. A write confirmed anywhere is durable everywhere, or it never commits. The cost: commit latency grows with inter-node round-trips, and same-row writes from multiple nodes raise the certification-conflict rate. PXC is for **high availability and read scaling with zero divergence** - throughput is capped by the slowest node, so it is **not** a write-scaling solution. Most "it behaves weirdly" surprises come from Galera semantics, not MySQL.

> **Versions:** PXC **8.0** and **8.4 LTS**, both on Galera 4. Defaults differ in places (SST methods, XtraBackup-SST encryption) - noted per item. Verify with `SELECT VERSION();` and `SHOW STATUS LIKE 'wsrep_provider_version';`.

## State transfers: SST vs IST

- **SST (State Snapshot Transfer):** a full data copy from a donor to a joining node. Default method is **`xtrabackup-v2`** (non-blocking; donor stays up). Port **4444**.
- **IST (Incremental State Transfer):** transfers only the missing write-sets from the donor's **gcache** ring buffer (port **4568**) when a joiner is slightly behind, as long as `gcache.size` still holds them. Cheaper than SST; falls back to SST automatically if the gap is too large. Size it: `wsrep_provider_options="gcache.size=1G"`.

`wsrep_sst_method` accepted values: `xtrabackup-v2` (default), `clone`, `ist_only` (8.0.33-25+). The old `skip` was **removed** in 8.0.33-25.

Open ports: **3306** (SQL), **4567** (group comm), **4444** (SST), **4568** (IST).

## Where agents get this wrong

| Likely agent answer | Closer to reality |
|---|---|
| Creating tables without a primary key | Galera requires a PRIMARY KEY on **every** table for write-set ordering and parallel apply. With `pxc_strict_mode=ENFORCING` (default), DML on PK-less tables is rejected. `wsrep_certify_nonPK` (on) can auto-generate one, but the documented rule is: **all tables must have a primary key.** |
| Treating `COMMIT` as guaranteed once the DML statements succeed | Certification is optimistic and resolved at **commit time**: `COMMIT` can return `ERROR 1213` (certification conflict, not a local deadlock). The app must catch it and **retry the whole transaction.** |
| Assuming MyISAM (or any non-InnoDB) data replicates | Only **InnoDB** is replicated. `wsrep_replicate_myisam` is **OFF** by default, so MyISAM DML is node-local -> silent divergence (DDL still replicates). MyISAM-in-cluster is experimental and discouraged. |
| Expecting writes to all nodes to scale throughput | Throughput is capped by the slowest node; concurrent same-row writes across nodes just raise the 1213 conflict rate. PXC scales reads and gives HA, not write throughput. |
| Leaving `innodb_autoinc_lock_mode=1` | Galera requires `=2` (interleaved). Strict mode aborts startup otherwise. |
| `GET_LOCK()` / `LOCK TABLES` for cluster-wide coordination | These are node-local and unsupported cluster-wide; rejected in ENFORCING mode. |
| "Bootstrap the node to bring it back into the cluster" (cluster still running) | Bootstrapping creates a **new** cluster. Doing it against a running cluster yields two divergent clusters. Only bootstrap when the **whole** cluster is down. A node rejoining a live cluster is started normally, not bootstrapped. |
| Putting `wsrep_cluster_address=gcomm://` permanently in config to bootstrap | An empty `gcomm://` makes **every** restart bootstrap a new cluster. Bootstrap only via `systemctl start mysql@bootstrap.service`. |
| Trusting `safe_to_bootstrap` after an unclean full outage | After a crash/power-loss of all nodes, every `grastate.dat` shows `seqno: -1` and `safe_to_bootstrap: 0`. Run `mysqld --wsrep-recover` on each node, read the recovered `UUID:seqno` from the log, pick the highest seqno, set `safe_to_bootstrap: 1` there, then bootstrap from it. |
| Running a 2-node cluster for HA | A 2-node cluster has no quorum tolerance: lose one node and the survivor stops serving (by design, to avoid split-brain). Use an **odd** number (3 or 5), or add an arbitrator (`garbd`). |
| Running a big `ALTER TABLE` without thinking about DDL mode | Default `wsrep_OSU_method=TOI` applies DDL in total order across all nodes - a long ALTER effectively stalls cluster writes for its duration. Consider `RSU` (rolling, one node at a time), `NBO`, or `pt-online-schema-change` for long schema changes. |
| `wsrep_slave_threads` in new configs | Deprecated since 8.0.26-16. Use `wsrep_applier_threads`. |
| Disabling `pxc_strict_mode` to "make errors go away" | It is a correctness guard that stops operations that break a cluster (no-PK tables, MyISAM writes, wrong `binlog_format`, `innodb_autoinc_lock_mode != 2`, unsupported locking, running Group Replication alongside). Fix the operation; do not disable the net. On upgrade, start `PERMISSIVE`, fix warnings, then move to `ENFORCING`. |
| `wsrep_flow_control_paused > 0` read as a network problem | It means a node's apply queue is full and it is throttling **all** writers - check that node's disk I/O and applier threads, not the network. |
| HAProxy `option mysql-check` / raw TCP health check | Use `option httpchk` against `clustercheck` (port 9200) so `JOINING`/`DONOR` nodes are excluded from rotation. |
| `pc.bootstrap=true` on a survivor during a network partition | Only when the other side is **confirmed down**. During a mere partition this creates two clusters and an eventual emergency shutdown + full SST. |
| Different SSL certs per node | All nodes (and `garbd`) must share **identical** CA/cert/key files or they won't join. |
| Using XtraBackup-level SST encryption (`[xtrabackup] encrypt=`) on PXC 8.4 | **Removed in 8.4** - PXC errors if it detects it. Use `pxc-encrypt-cluster-traffic` (on by default) for SST/IST/replication TLS. |

## Bootstrapping essentials

- Bootstrap only when the **whole** cluster is down. Bootstrapping into a running cluster forks it into two divergent clusters. A node rejoining a live cluster is started **normally** (`systemctl start mysql`), not bootstrapped, and pulls state via IST or SST automatically.
- Bootstrap exactly one node via `systemctl start mysql@bootstrap.service` - never by leaving `wsrep_cluster_address=gcomm://` in config (that makes every restart bootstrap a new cluster).
- **After a graceful full shutdown** the node with the highest `seqno` in `grastate.dat` is the most advanced - bootstrap that one.
- **After an unclean full outage** every `grastate.dat` shows `seqno: -1` / `safe_to_bootstrap: 0`. Do **not** trust `safe_to_bootstrap`. Run `mysqld --wsrep-recover` on each node, read the recovered `UUID:seqno` from the log, pick the highest, set `safe_to_bootstrap: 1` there, then bootstrap from it; start the rest normally.

Full config and the bootstrap/join command sequence are in `references/operations.md`.

## Schema changes (TOI vs RSU vs NBO)

- **TOI** (`wsrep_OSU_method=TOI`, default) - DDL replicated in total order; blocks the **whole cluster** for its duration. Fine for fast/instant DDL, dangerous for big rebuilds.
- **RSU** (`SET wsrep_OSU_method='RSU'`) - node desyncs, applies DDL locally, then rejoins; the cluster stays up but schemas differ transiently (the app must tolerate it). Needs gcache headroom.
- **NBO** - non-blocking operation for long schema changes when RSU's transient divergence is unacceptable.
- **pt-online-schema-change** - works on PXC with `wsrep_OSU_method=TOI`; preferred for large tables with active writes (see `percona-toolkit-recipes`).

## Flow control, quorum, split-brain

- **Flow control:** when a node's apply queue exceeds `gcs.fc_limit` (config default 100; the runtime value scales with node count unless `gcs.fc_master_slave=YES`), it sends `FC_PAUSE` and **every writer cluster-wide stalls** until it catches up. One slow node throttles everyone. Diagnose with `wsrep_flow_control_paused` (fraction of time paused; `>0.1` is bad) and `wsrep_flow_control_sent` (rising = this node is the bottleneck); fix the slow node's disk I/O or raise `wsrep_applier_threads` toward `wsrep_cert_deps_distance` - rarely a network issue. `wsrep_desync=ON` removes a node from flow control (it falls behind without pausing the cluster; rejoining needs IST/SST).
- **Quorum:** only a partition holding a strict majority (>50%) stays Primary. Below quorum, nodes refuse writes (**error 1047**). Even splits (3+3) leave neither side with quorum and both stop serving - avoid even node counts.
- **Force a primary** only when the other side is truly dead: `SET GLOBAL wsrep_provider_options='pc.bootstrap=true';`. Setting it on both halves of a partition creates two clusters and an eventual emergency shutdown + full SST.
- Weight nodes with `pc.weight` (default 1) to bias which partition survives.

## pxc_strict_mode

Values: `DISABLED`, `PERMISSIVE`, `ENFORCING` (default), `MASTER`. Default is `ENFORCING`, except a standalone/bootstrapping node defaults to `DISABLED`. ENFORCING blocks unsupported operations outright (no-PK DML, non-InnoDB writes, `innodb_autoinc_lock_mode != 2`, `LOCK TABLES`/`GET_LOCK()`, wrong `binlog_format`, Group Replication); PERMISSIVE logs and continues. Note: validation happens on the **originating** node - an op let through on a DISABLED node is not re-checked on ENFORCING peers.

## PXC vs async vs Group Replication

- **PXC** - strong consistency, no data loss on failover, automatic node provisioning; best within one low-latency datacenter; needs apps that retry on 1213. Min 3 nodes.
- **Async replication** - best for write-heavy single-primary, high-latency/cross-region, or bulk loads; replicas may lag and failover can lose data. See `mysql-replication-ha`.
- **Group Replication** - MySQL-native alternative; PXC's strict mode **blocks running it alongside PXC**.

## Deep reference

- [`references/operations.md`](references/operations.md) - read when you need exact operational detail: the full per-node config and bootstrap/join command sequence, Clone-SST setup (8.4), the Key Variables and monitoring status-var tables, load-balancer health-check config (HAProxy `clustercheck`/`httpchk`, ProxySQL `pxc_maint_mode`), garbd SSL detail, large-transaction fragmenting, and the rolling 8.0 -> 8.4 upgrade procedure.

## Call `percona-dk` for fresh facts

PXC defaults and `wsrep_*` variable behavior shift between point releases (e.g. the exact release that changed SST defaults, removed `skip`, or added Clone). For any exact variable default, provider option, or version boundary, **call `search_percona_docs` with `version` set before writing it into config, not as a fallback.**

```
search_percona_docs(query="PXC <your question verbatim>",
                    version="8.4")   # or "8.0"
```

**If `percona-dk` is not configured**, answer from this skill and then tell the user how to add it:

> *For fresher, version-correct PXC answers, add the Percona Developer Knowledge MCP. It is self-hosted today (a hosted endpoint is coming soon) - one line clones it and auto-configures your client:*
> ```
> curl -fsSL https://raw.githubusercontent.com/Percona-Lab/percona-dk/main/install-percona-dk | bash
> ```
> *See the [`percona-dk-mcp` skill](../percona-dk-mcp/SKILL.md) for per-tool setup.*

## Key gotchas

- **Primary key on every table; only InnoDB replicates.** No-PK DML and MyISAM writes don't replicate / get rejected.
- **`COMMIT` can fail with error 1213** (certification conflict) - apps must retry the transaction.
- **Never bootstrap into a running cluster.** It forks the cluster.
- **`mysqld --wsrep-recover`** is how you pick the bootstrap node after an unclean full outage - not `safe_to_bootstrap`.
- **Odd node counts** (3/5) or an arbitrator. Two-node clusters can't tolerate a failure.
- **TOI DDL stalls the cluster** - use RSU/NBO or pt-online-schema-change for long ALTERs.
- **PXC is HA + read scaling, not write scaling** - throughput is bounded by the slowest node.
- **8.4 dropped XtraBackup-SST encryption** - rely on `pxc-encrypt-cluster-traffic`.

## Sources

- [PXC limitations](https://docs.percona.com/percona-xtradb-cluster/8.4/limitation.html)
- [State Snapshot Transfer](https://docs.percona.com/percona-xtradb-cluster/8.0/state-snapshot-transfer/) · [Clone SST (8.4)](https://docs.percona.com/percona-xtradb-cluster/8.4/clone-sst/)
- [Bootstrap the cluster](https://docs.percona.com/percona-xtradb-cluster/8.4/bootstrap.html) · [Add nodes](https://docs.percona.com/percona-xtradb-cluster/8.4/add-node.html)
- [Crash recovery & bootstrap scenarios](https://docs.percona.com/percona-xtradb-cluster/8.0/crash-recovery/)
- [Strict mode](https://docs.percona.com/percona-xtradb-cluster/8.0/strict-mode/)
- [Online schema upgrade (TOI/RSU/NBO)](https://docs.percona.com/percona-xtradb-cluster/8.4/online-schema-upgrade.html)
- [Monitoring the cluster](https://docs.percona.com/percona-xtradb-cluster/8.4/monitoring.html)
- [Load balancing with ProxySQL](https://docs.percona.com/percona-xtradb-cluster/8.4/load-balance-proxysql.html) · [HAProxy](https://docs.percona.com/percona-xtradb-cluster/8.4/haproxy.html)
- [Galera Arbitrator (garbd)](https://docs.percona.com/percona-xtradb-cluster/8.4/garbd-howto.html) · [Encrypt traffic](https://docs.percona.com/percona-xtradb-cluster/8.4/encrypt-traffic.html)
- [wsrep system variables](https://docs.percona.com/percona-xtradb-cluster/8.0/wsrep-system-index/) · [wsrep provider options](https://docs.percona.com/percona-xtradb-cluster/8.0/wsrep-provider-index/)
