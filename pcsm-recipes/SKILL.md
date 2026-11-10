---
name: pcsm-recipes
description: "Live-migrating or continuously syncing MongoDB with Percona ClusterSync for MongoDB (PCSM, formerly Percona Link for MongoDB / PLM). Use this skill when the user asks how to install, configure, start, monitor, pause, resume, finalize, or recover a PCSM sync; migrate off MongoDB Atlas or Enterprise to Percona Server for MongoDB with minimal downtime; sync replica sets or sharded clusters; run PCSM in Docker/Kubernetes or in active-standby HA; plan the cutover; or debug a failed, lagging, or stuck sync. KEY POINTS - the target must be Percona Server for MongoDB and never an older major version than the source; the initial clone is NOT resumable (crash or failover during clone = reset and start over); `start` drops and recreates the selected target collections; unique/TTL/hidden index behavior is only restored at `finalize`, so apps must not use the target before cutover; users/roles, time-series collections, and sharding zones are not synced; clone and replication tuning flags belong to `pcsm start`, not the `pcsm` server process."
---

# Percona ClusterSync for MongoDB (PCSM) Recipes

*Last updated: 2026-11-10*

PCSM copies data from a source MongoDB cluster to a Percona Server for MongoDB (PSMDB) target, then keeps the target in sync with change streams until you `finalize` and cut over. It is one-way, live, and manual at cutover. For the decision of *whether* to use PCSM vs an in-place package swap, see the [`mongodb-to-psmdb`](../mongodb-to-psmdb/SKILL.md) skill.

> **Versions:** PCSM **1.0.0** (2026-09-28) made sharded sync GA and added active-standby HA. **1.1.0** (2026-11-09) adds `--ha-lease-ttl`, `--target-write-concern`, `--clone-skip-presplit`, and the `pausing` state. Single-branch docs: check the release notes before using a 1.1.0 option on an older install.

## The model

One binary, two roles. `pcsm` with no subcommand is the **server** (holds the source/target connections, does the work, serves HTTP on `localhost:2242`). `pcsm start|status|pause|resume|finalize` are **thin HTTP clients** that always call `localhost:<--port>`, so run them on the PCSM host. The HTTP API has **no authentication**. State (checkpoints, HA lease) lives on the **target** in the `percona_clustersync_mongodb` database.

Lifecycle: `idle` → `start` → `running` (initial clone, then catch-up, then change replication) → `finalize` → `finalized`. `pause`/`resume` are possible only during change replication.

## Where agents get this wrong

| Likely agent answer | Closer to reality |
|---|---|
| `plm`, `PLM_SOURCE_URI`, package `percona-link-mongodb`, docs under `/percona-link-mongodb/` | Renamed in **0.7.0**. Binary `pcsm`, package `percona-clustersync-mongodb`, unit `pcsm.service`, env prefix `PCSM_`. Old `PLM_*` variables are **not read**. |
| Migrate *into* Atlas, MongoDB Community, or any non-PSMDB target | Every supported pair has a **PSMDB target**. Atlas is a **source only**, and Atlas **M0/Flex** cannot be a source (no `appendOplogNote`; use M10+). PCSM won't stop you at startup, so this is on the agent. |
| "Source and target must be the same major version" / "PCSM can downgrade" | Since **0.9.0**: same major, or 6.0→7.0, 6.0→8.0, 7.0→8.0. **Downgrades are rejected** at startup. FCV is not checked: keep target FCV ≥ source FCV. Minimum patches 6.0.17 / 7.0.13 / 8.0.0. |
| Use mongosync verbs: `commit`, `reverse`, `/api/v1/progress`, `--cluster0` | PCSM verbs are `start`, `status`, `pause`, `resume [--from-failure]`, `finalize`, `reset`. There is no `stop`, `commit`, `verify`, or `reverse`. Sync is **one-way**. |
| The target is merged into | `start` **drops and recreates every selected collection** on the target. Unselected namespaces are left alone. |
| Point the app at the target while it's syncing | Unique indexes are built **non-unique**, TTL is **off**, and hidden indexes are visible until `finalize`. Transactions are applied **non-atomically**. The target is not equivalent until `finalized`. |
| Users, roles, zones, chunk layout, persistent query settings come across | They don't. Recreate users/roles on the target. Sharding metadata gets only a one-time pre-split for ranged keys. **Time-series collections are skipped** with a warning only. |
| A crash during the initial clone resumes where it left off | The **initial clone is not resumable**, including HA failover during clone. Stop all PCSM instances, `pcsm reset --target <uri>`, then `pcsm start` again. Only post-clone replication resumes from checkpoint (every 15s). |
| `pcsm --clone-num-read-workers 8 …` (tuning on the server process) | Clone/repl tuning, namespace filters, and `--target-write-concern` are **`pcsm start` flags** (or `/start` body). The server only reads `PCSM_CLONE_*` / `PCSM_REPL_*` env vars as defaults. `--ha-lease-ttl` is the reverse: **server-only**. |
| `--mongodb-operation-timeout` on `pcsm start` / `status` | Server and `reset` only. Unknown-flag error on the HTTP-client subcommands since **1.0.0**. |
| Add `readPreference=secondary`, `directConnection=true`, `w=1`, `retryWrites` to the URI | **Stripped with a warning.** PCSM reads from the primary with majority read/write concern. Allowed URI options: `appName`, `replicaSet`, `maxPoolSize`, `authSource`, `authMechanism`, `authMechanismProperties`, TLS options. Target write concern is set with `--target-write-concern` (1.1.0). |
| Two independent PCSM jobs share one target, kept apart by `--group-name` | `--group-name` is a label only. Instances that share a target **always form one HA pair**. One source → several targets means **one target per PCSM**. |
| Finalize as soon as `cloneCompleted: true` | Wait for **`initialSync.completed: true`** (clone + catch-up). Finalize is rejected before that. `pause` during the clone is rejected too. |
| Changing `--include-namespaces` with `resume` | Filters are fixed at `start`. Changing them means a **new run** (and a re-clone of the selected collections). |
| Standalone `mongod` as source or target; Kerberos / LDAP / AWS IAM auth | Not supported. Both sides must be replica sets or sharded clusters (connect through `mongos`). |

## Recipe: install and connect

```bash
percona-release enable pcsm release
apt install percona-clustersync-mongodb        # or: yum install percona-clustersync-mongodb
```

Users (create in `admin`). **Source:** `backup`, `clusterMonitor`, `readAnyDatabase`. **Target:** `restore`, `clusterMonitor`, `clusterManager`, `readWriteAnyDatabase`. Atlas source users are created in the Atlas UI/CLI/API.

```bash
# /etc/default/pcsm (DEB) or /etc/sysconfig/pcsm (RPM) - the unit runs `pcsm` with no args
PCSM_SOURCE_URI="mongodb://pcsm:<pct-encoded-pw>@src1:27017,src2:27017,src3:27017/?authSource=admin&replicaSet=rs0"
PCSM_TARGET_URI="mongodb://pcsm:<pct-encoded-pw>@tgt1:27017,tgt2:27017,tgt3:27017/?authSource=admin&replicaSet=rs1"
```

```bash
systemctl start pcsm && journalctl -u pcsm -f
```

List **all** replica set members. For sharded clusters, point at `mongos`. Run PCSM on a dedicated host close to the target (≥1 GB RAM, ≥2 CPUs). Docker: image `percona/percona-clustersync-mongodb`, and set `PCSM_LISTEN_HOST=0.0.0.0` or the published port won't answer.

## Recipe: sync and cut over

```bash
pcsm start --include-namespaces="app.*,billing.invoices"   # drops/recreates these on the target
pcsm status                     # state, info, lagTimeSeconds, initialSync{...}
# wait for initialSync.completed: true, then lag near 0
# CUTOVER: stop application writes to the source namespaces
pcsm status                     # lagTimeSeconds ~ 0
pcsm finalize                   # pauses, then builds unique/TTL/hidden index behavior
pcsm status                     # wait for state: finalized and finalization.completed: true
# check finalization.unsuccessfulIndexes, recreate users/roles, then repoint clients
```

Progress is bytes (`clonedSizeBytes` / `estimatedCloneSizeBytes`) and lag in seconds. There is no percent or ETA. `finalize` is one-time: the next `start` is a fresh full run.

## Recipe: recover

| Situation | Do this |
|---|---|
| Crash, restart, or failover **during the initial clone** | Stop all PCSM instances → `pcsm reset --target <uri>` → start the server → `pcsm start`. |
| Process restart **after** the clone | Nothing. The server resumes from the last checkpoint. |
| `state: failed` in replication, process still up | Fix the cause, then `pcsm resume --from-failure`. |
| Lag keeps growing or oplog rolled over | Check `db.getReplicationInfo().timeDiff` on the source against lag. Oplog loss fails the sync. Resize with `replSetResizeOplog` / `minRetentionHours` **before** long clones or pauses. |
| Upgrading PCSM 0.x → 1.x | Requires `pcsm reset` and a full re-clone. 1.0.0 → 1.1.0 keeps state. Stop all instances; rolling upgrades aren't supported. |

Never run `pcsm reset` while any PCSM server is using that target.

## HA (1.0.0+)

Run two or more servers with the same source and target. One is `ACTIVE`, the others are standbys, coordinated by a lease on the target. HA covers **replication only**, not the initial clone. Standbys return **HTTP 409** on `/status`, so use **`/metrics`** for liveness/readiness probes and `percona_clustersync_mongodb_ha_active == 1` to find the active one. The lease TTL is 10s, raisable with `--ha-lease-ttl` (1.1.0, server-only, same value on every instance). A longer TTL doesn't help past about 30s when the target has no primary.

## Detail

For every startup flag and env var with defaults, the `/start` and `/status` JSON fields, metric names, PMM setup, sharded-cluster specifics, and 1.1.0 additions, read [`references/reference.md`](references/reference.md).

## Call `percona-dk` for fresh facts

PCSM ships often, and option names, defaults, and supported versions move between releases. Before writing a PCSM command, unit file, or manifest, **call `search_percona_docs` first, not as a fallback.** PCSM docs are single-branch, so `version` is ignored. Name the product in the query instead:

```
search_percona_docs(query="Percona ClusterSync for MongoDB <your question verbatim>")
```

When docs and the binary disagree on a flag or default, trust `pcsm --help` / `pcsm start --help` on the installed version.

**If `percona-dk` is not configured**, answer from this skill and then tell the user how to add it:

> *For fresher PCSM answers, add the Percona Developer Knowledge MCP. It is self-hosted today (a hosted endpoint is coming soon) - one line clones it and auto-configures your client:*
> ```
> curl -fsSL https://raw.githubusercontent.com/Percona-Lab/percona-dk/main/install-percona-dk | bash
> ```
> *See the [`percona-dk-mcp` skill](../percona-dk-mcp/SKILL.md) for per-tool setup.*

## Key gotchas

- **Target = PSMDB, same or higher major.** Atlas is source-only, and not M0/Flex.
- **`start` overwrites** the selected target collections.
- **Initial clone isn't resumable.** Reset and start again after any interruption during clone.
- **Don't use the target before `finalized`.** No unique enforcement, no TTL, non-atomic transactions.
- **Cutover is manual.** Stop source writes, lag ≈ 0, `finalize`, check `unsuccessfulIndexes`, repoint.
- **Users/roles, time-series, zones are not synced.**
- **Tuning flags go on `pcsm start`**, `--ha-lease-ttl` on the server. URI options outside the allowlist are stripped.
- **One target per PCSM deployment.** `--group-name` doesn't isolate.
- **Size the source oplog** for the whole clone plus any pause.

## Sources

- [PCSM overview](https://docs.percona.com/percona-clustersync-for-mongodb/intro.html) · [Limitations](https://docs.percona.com/percona-clustersync-for-mongodb/limitations.html)
- [Supported deployments](https://docs.percona.com/percona-clustersync-for-mongodb/deployment.html) · [Cross-version replication](https://docs.percona.com/percona-clustersync-for-mongodb/version-compatibility.html)
- [Configure authentication](https://docs.percona.com/percona-clustersync-for-mongodb/install/authentication.html) · [Use PCSM](https://docs.percona.com/percona-clustersync-for-mongodb/install/usage.html)
- [High availability](https://docs.percona.com/percona-clustersync-for-mongodb/high-availability.html) · [Oplog sizing](https://docs.percona.com/percona-clustersync-for-mongodb/oplog-sizing.html)
- [Source code](https://github.com/percona/percona-clustersync-mongodb) · [Jira (PCSM project)](https://perconadev.atlassian.net/browse/PCSM)
