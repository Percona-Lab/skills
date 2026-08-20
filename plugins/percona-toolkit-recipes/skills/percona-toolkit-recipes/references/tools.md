# Percona Toolkit: per-tool reference

Deep per-tool flag catalogs, full command examples, and defaults. Load this when you need the exact flags, requirements, or worked recipes for a specific `pt-*` tool.

## Recipe: online schema change with pt-osc

> **Check native DDL first.** Prefer `ALGORITHM=INSTANT` (8.0.12+: add a nullable/defaulted column at the end of the row, set a column default, rename a column - metadata-only, finishes in milliseconds) or `ALGORITHM=INPLACE` (add/drop index) - they avoid the row copy entirely. Reach for pt-osc only when the change would otherwise force `ALGORITHM=COPY` on a large hot table, or when you need throttling and replica-lag awareness on a 24/7 write-heavy table.

```bash
pt-online-schema-change \
  --alter "ADD COLUMN status TINYINT NOT NULL DEFAULT 0, ADD INDEX (status)" \
  --max-lag=1 \
  --execute \
  D=mydb,t=orders \
  h=db.example.com,u=ops
```

How it works: pt-osc creates a `_orders_new` shadow table with the altered schema, installs `AFTER INSERT / UPDATE / DELETE` triggers on the original to keep both tables in sync, copies existing rows in chunks, then does an atomic `RENAME TABLE` swap. It sets `innodb_lock_wait_timeout=1` so it (not your app) is the lock victim, and throttles automatically based on replica lag.

Defaults worth knowing: `--chunk-time=0.5s`, `--chunk-size=1000`, `--max-lag=1`.

Common flags:

- `--dry-run` - print what it would do, change nothing. Use first, always.
- `--max-lag=5` - pause copying when any replica exceeds this lag in seconds.
- `--max-load=Threads_running=25` (default) - *pauses* the copy when exceeded; `--critical-load=...=50` (default) *aborts* and leaves the shadow table behind. Keep `--critical-load` above `--max-load`.
- `--chunk-size-limit=4.0` - abort a chunk whose EXPLAIN estimates >4× the target rows (a bad-index guard; default 4).
- `--no-drop-old-table` - keep the original table after swap so you can audit / rollback.
- `--alter-foreign-keys-method=rebuild_constraints` - required when other tables have FKs pointing at the target. No default; pt-osc refuses to run without it in that case. `drop_swap` is blocked on MySQL 8.0.0–8.0.14 (bug 89441).
- `--preserve-triggers` - if the source table already has triggers, copy them onto the new table (MySQL 5.7.2+; on < 5.7.2 pt-osc cannot run on a table that already has triggers).
- `--recursion-method=dsn=D=percona,t=dsns` (or `=none`) - for managed DBs (RDS/Aurora) where replicas aren't visible in `PROCESSLIST`.

Hard pt-osc requirements:

- Table must have a `PRIMARY KEY` or a `UNIQUE INDEX` (used as chunk key), unless the ALTER itself creates one.
- Source table cannot already have triggers unless `--preserve-triggers` is set (5.7.2+).
- Tables with foreign keys *pointing at* the target need `--alter-foreign-keys-method` set explicitly; there is no default.
- Storage for the shadow table = roughly the size of the original.

## Recipe: archive or purge old rows

`pt-archiver` nibbles rows in forward index scans. It has **no execute guard** - `--dry-run` first.

```bash
# Delete in chunks, throttling on replica lag:
pt-archiver \
  --source h=db,D=app,t=events \
  --where "created_at < NOW() - INTERVAL 90 DAY" \
  --purge \
  --limit 1000 --bulk-delete --sleep 1 \
  --max-lag 5 --check-replica-lag h=replica1

# Move to an archive table on another host instead of deleting:
pt-archiver \
  --source h=db,D=app,t=events \
  --dest   h=archive,D=archive,t=events_2025 \
  --where "created_at < '2025-01-01'" \
  --limit 1000 --bulk-insert --no-delete  # remove --no-delete to actually purge after copy
```

Defaults bite: `--txn-size=1` and `--limit=1` mean one row per transaction / SELECT - raise both. For big purges add `--bulk-delete` (one ranged DELETE per chunk instead of one per row); for big moves add `--bulk-insert` (LOAD DATA on the dest). In `--dest` mode, rows are copied before being deleted, and replication lag is checked between chunks.

## Recipe: analyze a slow query log

```bash
pt-query-digest /var/log/mysql/slow.log > digest.txt
```

Top of the output: queries ranked by total time, with fingerprint (parameterized form), counts, time percentiles, lock time, rows examined, and a worked example. Pairs directly with Percona Server's extended slow log (`log_slow_verbosity='full'`). From a tcpdump capture instead:

```bash
tcpdump -s 65535 -x -nn -q -tttt -i any port 3306 > /tmp/3306.tcp
pt-query-digest --type=tcpdump /tmp/3306.tcp
```

From the binary log (rare but useful when slow log isn't enabled), or live from the processlist:

```bash
mysqlbinlog mysql-bin.000123 | pt-query-digest --type=binlog
pt-query-digest --processlist h=db1            # live sampling
```

For continuous, always-on analysis, PMM Query Analytics is the live equivalent (see `pmm-operations`).

## Recipe: verify replica consistency

On the source:

```bash
pt-table-checksum \
  --replicate=percona.checksums \
  --databases=app \
  h=source,u=checksum
```

This computes per-chunk checksums on the source via `REPLACE...SELECT` that replicate down to every replica, writes results to `percona.checksums`, prints any mismatches, and exits non-zero on a diff (so it scripts well). To repair:

```bash
pt-table-sync --execute --replicate=percona.checksums --sync-to-source h=replica1
```

`--sync-to-source` is the safe direction: fixes flow through replication from the source, never written straight to a replica. Read `pt-table-sync --help` carefully - this tool can damage data if pointed the wrong way.

## Recipe: accurate replication lag

Install once on the source (needs synced clocks):

```bash
pt-heartbeat --update --create-table -D percona -t heartbeat \
  --daemonize h=source
```

Then on any replica:

```bash
pt-heartbeat --monitor -D percona -t heartbeat h=replica
# Outputs: 0.05s [ 0.04s, 0.04s, 0.04s ]
```

This is real lag (now − last applied heartbeat timestamp), unaffected by an idle SQL thread.

## Other tools worth knowing

- **`pt-kill`** - kill connections matching predicates (`--busy-time`, `--match-user`, `--match-info`, etc.). `--print` to preview before `--kill`. Default `--victims oldest`; use `--victims all` to kill every match, `--kill-query` to cancel the query but keep the connection.
- **`pt-stalk`** / **`pt-pmp`** - `pt-stalk` watches a trigger condition (e.g. `Threads_running > 50`) and dumps diagnostics on fire; pair with `pt-mext` to analyze the snapshots. `pt-pmp` aggregates stack traces (use eu-stack, not GDB, in production).
- **`pt-upgrade`** - replay queries against two servers and diff results / errors / row-counts before a version upgrade (`pt-upgrade h=old h=new slow.log`); non-zero exit on any difference, so it scripts well in CI.
- **`pt-mysql-summary` / `pt-summary`** - single-shot read-only text snapshot of the server / host config and current state. The first thing to attach to a support case.
- **`pt-show-grants`** - dump grants in a canonical, diffable form (cleaner than `mysql.user` queries; great for version control).
- **`pt-secure-collect`** - sanitized diagnostics bundle for sharing with Percona Support without leaking data.
- **`pt-config-diff`** - diff `SHOW VARIABLES` between two running servers, or a `my.cnf` vs a live server (`pt-config-diff /etc/my.cnf h=prod`).
- **`pt-variable-advisor`** - flag risky `SHOW VARIABLES` settings.
- **`pt-duplicate-key-checker`** - find redundant indexes / FKs (e.g. `(a)` covered by `(a,b)`) → `DROP INDEX` suggestions.
- **`pt-index-usage`** - replay a slow log to find indexes that are never used.
- **`pt-deadlock-logger`** / **`pt-fk-error-logger`** - parse `SHOW ENGINE INNODB STATUS` for deadlocks / FK errors; log to stdout or a table.
- **`pt-replica-restart`** (was `pt-slave-restart`) - auto-restart replication past *named* transient errors (`--error-numbers=1062`); always follow with `pt-table-checksum`, since skipping diverges data.
- **`pt-find`** - `find(1)` for tables (`pt-find --engine MyISAM --exec "ALTER TABLE %D.%N ENGINE=InnoDB"`).
- **`pt-fingerprint`** / **`pt-visual-explain`** - normalize a query to its fingerprint; turn `EXPLAIN` into a readable tree.

*Each tool also has full docs via `man pt-<tool>` and `pt-<tool> --help`.*
