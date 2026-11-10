# PCSM reference: options, API, metrics

Exact flag names, defaults, JSON fields, and metric names for Percona ClusterSync for MongoDB 1.0.0 and 1.1.0. Load this when you need a value beyond the recipes in `SKILL.md`. Defaults below are from the PCSM source. Where the published docs differ, that is noted. When in doubt, check `pcsm --help` and `pcsm start --help` on the installed binary.

## Server options (`pcsm`, no subcommand)

Set as flags or as env vars (in `/etc/default/pcsm` or `/etc/sysconfig/pcsm` for the packaged service).

| Flag | Env var | Default | Notes |
|---|---|---|---|
| `--source` | `PCSM_SOURCE_URI` | required | Plain `SOURCE_URI` is **not** read. |
| `--target` | `PCSM_TARGET_URI` | required | Also used by `pcsm reset`. |
| `--port` | `PCSM_PORT` | `2242` | Also on every subcommand, which calls `localhost:<port>`. |
| `--listen-host` | `PCSM_LISTEN_HOST` | `localhost` | 1.0.0+. Host only, no port. Use `0.0.0.0` / `::` in containers. Wide binding exposes the unauthenticated API. |
| `--mongodb-operation-timeout` | `PCSM_MONGODB_OPERATION_TIMEOUT` | `5m` | Server and `reset` only. `PLM_MONGODB_CLI_OPERATION_TIMEOUT` is accepted with a warning. |
| `--group-name` | `PCSM_GROUP_NAME` | `default` | 1.0.0+. Label for HA members, metrics, and logs. Does **not** isolate HA groups. |
| `--ha-lease-ttl` | `PCSM_HA_LEASE_TTL` | `10s` | **1.1.0.** Minimum `10s`, no maximum, `0` = default. Not accepted by `pcsm start` or `/start`. Set the same value on every instance. |
| `--log-level` | `PCSM_LOG_LEVEL` | `info` | `trace`, `debug`, `info`, `warn`, `error`, `fatal`. |
| `--log-json` | `PCSM_LOG_JSON` | `false` | |
| `--log-no-color` | `PCSM_LOG_NO_COLOR` | `false` | `--no-color` / `PCSM_NO_COLOR` are deprecated. |

## Run options (`pcsm start` flags, `/start` body, or env defaults)

The server reads the env vars as per-run defaults. A `pcsm start` flag or `/start` field overrides them for that run. None of these is a server flag.

| `pcsm start` flag | `/start` field | Env var | Default |
|---|---|---|---|
| `--include-namespaces` | `includeNamespaces` | - | all. Comma-separated, `db.*` for a whole database. |
| `--exclude-namespaces` | `excludeNamespaces` | - | none. Exclude wins over include. |
| `--target-write-concern` | `targetWriteConcern` | `PCSM_TARGET_WRITE_CONCERN` (read by `pcsm start` only) | `majority`. **1.1.0.** Positive integer or `majority`; `0` and named tags are rejected. Applies to data writes, not PCSM metadata. Lower values risk rollback on target failover. |
| `--clone-num-parallel-collections` | `cloneNumParallelCollections` | `PCSM_CLONE_NUM_PARALLEL_COLLECTIONS` | `2` |
| `--clone-num-read-workers` | `cloneNumReadWorkers` | `PCSM_CLONE_NUM_READ_WORKERS` | `max(NumCPU/4, 1)` |
| `--clone-num-insert-workers` | `cloneNumInsertWorkers` | `PCSM_CLONE_NUM_INSERT_WORKERS` | `NumCPU*2` in the binary (docs say `NumCPU*4`) |
| `--clone-segment-size` | `cloneSegmentSize` | `PCSM_CLONE_SEGMENT_SIZE` | auto. Human units (`500MB`, `1GiB`), max `64GiB`. 0.9.0+. |
| `--clone-skip-presplit` | `cloneSkipPresplit` | `PCSM_CLONE_SKIP_PRESPLIT` | `false`. **1.1.0.** Skips copying ranged-key chunk boundaries to the target. |
| `--repl-num-workers` | `replNumWorkers` | `PCSM_REPL_NUM_WORKERS` | `NumCPU` (0.8.0+) |
| `--repl-change-stream-batch-size` | `replChangeStreamBatchSize` | `PCSM_REPL_CHANGE_STREAM_BATCH_SIZE` | `10000` |
| `--repl-event-queue-size` | `replEventQueueSize` | `PCSM_REPL_EVENT_QUEUE_SIZE` | `5000` |
| `--repl-worker-queue-size` | `replWorkerQueueSize` | `PCSM_REPL_WORKER_QUEUE_SIZE` | `5000` |
| `--repl-bulk-ops-size` | `replBulkOpsSize` | `PCSM_REPL_BULK_OPS_SIZE` | `5000` |
| `--use-collection-bulk-write` | `useCollectionBulkWrite` | `PCSM_USE_COLLECTION_BULK_WRITE` | `false`. Client-level bulk write is used when the target is 8.0+. |

The docs' "Startup configuration" page lists the `--clone-*` options next to server flags. In the binary they are `pcsm start` flags.

`pcsm resume` takes only `--from-failure` (`/resume` body `{"fromFailure": true}`), so filters and tuning can't change mid-run.

## Connection strings

- Only these URI options survive; everything else is stripped with a warning: `appName`, `replicaSet`, `maxPoolSize`, `authSource`, `authMechanism`, `authMechanismProperties`, `gssapiServiceName`, `tls`, `ssl`, `tlsCertificateKeyFile`, `tlsCertificateKeyFilePassword`, `tlsCAFile`, `tlsAllowInvalidCertificates`, `tlsAllowInvalidHostnames`, `tlsInsecure`.
- Reads go to the primary with `majority` read concern. Writes use `majority` unless `--target-write-concern` (1.1.0) says otherwise.
- `maxPoolSize` (1.0.0+): size the source pool at least to the read workers and the target pool at least to the insert workers. The driver default is 100.
- Percent-encode special characters in passwords.
- Kerberos, LDAP, and AWS IAM authentication are not supported, even though the URI allowlist accepts the mechanism option.

## HTTP API (`localhost:2242`, no auth)

| Endpoint | Purpose |
|---|---|
| `GET /status` | State and progress. Standbys return `409 {"error":"not_active"}`. |
| `POST /start` | Body: the `/start` fields above. |
| `POST /pause` | Change replication only. 1.1.0 acknowledges immediately with state `pausing`, then `paused`. |
| `POST /resume` | `{"fromFailure": true}` after a replication failure. |
| `POST /finalize` | Pauses, then completes indexes asynchronously. 1.1.0 errors if the pause takes more than 5s; retry once `state: paused`. |
| `GET /metrics` | Prometheus. Served on every HA role, so use it for probes. |

**States:** `idle`, `running`, `pausing` (1.1.0), `paused`, `finalizing`, `finalized`, `failed`.

**`/status` fields:** `ok`, `error`, `state`, `info`, `lagTimeSeconds`, `eventsRead`, `eventsApplied`, `lastReplicatedOpTime {ts, isoDate}`, `initialSync {completed, cloneCompleted, lagTimeSeconds, estimatedCloneSizeBytes, clonedSizeBytes}`, `finalization {completed, startedAt, completedAt, unsuccessfulIndexes[]}`. The docs' API page calls one field `initialSync.lagTime`; the binary returns `initialSync.lagTimeSeconds`. With HA and more than one live member, responses also carry an optional `me` / `role` / `group` envelope.

**`start` from each state:** rejected while `running`, `pausing`, `finalizing`, or `paused`. From `failed`, allowed only if the clone never finished; otherwise use `resume --from-failure`. From `finalized`, starts a new full run.

## Metrics

Prefix `percona_clustersync_mongodb_`: `events_read_total`, `events_applied_total`, `lag_time_seconds`, `initial_sync_lag_time_seconds`, `estimated_total_size_bytes`, `copy_read_size_bytes_total`, `copy_insert_size_bytes_total`, `copy_read_document_total`, `copy_insert_document_total`, `copy_read_batch_duration_seconds`, `copy_insert_batch_duration_seconds`, `repl_event_queue_size`, `repl_worker_event_queue_size`, `repl_worker_events_applied_total`, `repl_worker_flush_batch_size`, `repl_worker_flush_duration_seconds`, `repl_worker_bulk_queue_size`, `ha_active`, `ha_term`, `ha_role_transitions_total`, `ha_info`.

The PMM setup page references `events_processed_total`, which no longer exists. Use `events_read_total` / `events_applied_total`.

PMM has no native PCSM exporter. Add it as an external service, then import the dashboard from the docs:

```bash
pmm-admin add external --service-name=pcsm --listen-port=2242 --metrics-path=metrics --scheme=http
```

## Sharded clusters (GA in 1.0.0)

- Connect to `mongos` on sharded sides. Shard and node counts can differ between source and target.
- Supported: sharded → sharded, sharded → replica set (1.0.0+). Replica set → sharded copies data but leaves collections unsharded, and isn't in the supported-deployments list.
- Ranged shard keys get a one-time pre-split from the source chunk boundaries before clone (skip with `--clone-skip-presplit` in 1.1.0). Hashed keys use MongoDB's own layout. Later chunk moves, primary shards, and zones are not replicated.
- Sharded → replica set: `_id` must be unique across source shards. PCSM doesn't check this, and duplicates can be silently overwritten or skipped.
- Don't `reshardCollection`, `unshardCollection`, or `refineCollectionShardKey` a synced collection during sync.

## HA timings

The lease TTL is 10s (configurable in 1.1.0). The active instance renews the lease every 3s, heartbeats run every 3s, and a member is stale after 3 missed heartbeats. A crash failover takes up to the TTL plus a few seconds. A restarted sole instance can wait up to the TTL to become active again. A failed checkpoint write ends the active role regardless of the TTL. With no reachable target primary, that happens after about 30–45s, because the driver's 30s server-selection timeout is fixed.

## Sources

- [Startup configuration](https://docs.percona.com/percona-clustersync-for-mongodb/install/parameters.html) · [PCSM commands](https://docs.percona.com/percona-clustersync-for-mongodb/pcsm-commands.html) · [HTTP API](https://docs.percona.com/percona-clustersync-for-mongodb/api.html)
- [Sharding](https://docs.percona.com/percona-clustersync-for-mongodb/sharding.html) · [Sharded source to replica set target](https://docs.percona.com/percona-clustersync-for-mongodb/sharded-source-to-replica-set-target.html)
- [Multiple targets](https://docs.percona.com/percona-clustersync-for-mongodb/multiple-targets.html) · [Upgrade](https://docs.percona.com/percona-clustersync-for-mongodb/upgrade.html) · [Troubleshooting](https://docs.percona.com/percona-clustersync-for-mongodb/troubleshooting.html)
- [Monitor with PMM](https://docs.percona.com/percona-clustersync-for-mongodb/pmm-setup.html)
- Defaults verified against [percona/percona-clustersync-mongodb](https://github.com/percona/percona-clustersync-mongodb) `main` (v1.1.0) and tag `v1.0.0`.
