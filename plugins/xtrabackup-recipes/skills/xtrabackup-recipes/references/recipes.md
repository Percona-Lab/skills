# XtraBackup worked recipes

Full command-by-command walkthroughs for Percona XtraBackup: incremental chains, streaming to S3 via xbcloud, compression, encryption, partial backups, point-in-time recovery, and rebuilding a replica. Load this when you need the exact flags for a path beyond the basic full backup → prepare → restore in `SKILL.md`.

## Recipe: full backup

Backup user grants (the correct set - not `SUPER`):

```sql
CREATE USER 'backup'@'localhost' IDENTIFIED BY '…';
GRANT BACKUP_ADMIN, PROCESS, RELOAD, LOCK TABLES, REPLICATION CLIENT ON *.* TO 'backup'@'localhost';
GRANT SELECT ON performance_schema.log_status TO 'backup'@'localhost';
-- add SELECT on performance_schema.keyring_component_status / replication_group_members where those features apply
-- on 8.4, also GRANT INNODB_REDO_LOG_ARCHIVE if using redo log archiving
```

```bash
xtrabackup --backup \
  --target-dir=/var/backups/full-$(date +%F) \
  --user=backup --password=… \
  --parallel=4 \
  --compress --compress-threads=4   # ZSTD by default in PXB 8.0.34-29+ and PXB 8.4
```

Prepare (decompress first if `--compress` was used):

```bash
xtrabackup --decompress --target-dir=/var/backups/full-2026-05-29 --parallel=4
xtrabackup --prepare    --target-dir=/var/backups/full-2026-05-29
```

Restore (server must be **stopped** and target datadir **empty**):

```bash
xtrabackup --copy-back   --target-dir=/var/backups/full-2026-05-29
chown -R mysql:mysql /var/lib/mysql
```

Use `--move-back` instead of `--copy-back` to move files (faster, irreversible).

## Recipe: incremental chain

```bash
# Sunday: full
xtrabackup --backup --target-dir=/bk/sun

# Monday: incremental against the full
xtrabackup --backup --target-dir=/bk/mon --incremental-basedir=/bk/sun

# Tuesday: incremental against Monday
xtrabackup --backup --target-dir=/bk/tue --incremental-basedir=/bk/mon
```

Prepare. **All but the last** get `--apply-log-only`:

```bash
xtrabackup --prepare --apply-log-only --target-dir=/bk/sun
xtrabackup --prepare --apply-log-only --target-dir=/bk/sun --incremental-dir=/bk/mon
xtrabackup --prepare                  --target-dir=/bk/sun --incremental-dir=/bk/tue
xtrabackup --copy-back --target-dir=/bk/sun
```

Faster incrementals via **page tracking**: pass `--page-tracking` to `xtrabackup --backup`. PXB 8.0.27+ uses MySQL's native page tracking (the `mysqlbackup_page_track` component) to read only the pages modified since the last LSN instead of scanning every tablespace. Note: the older Percona-Server-only `innodb_track_changed_pages` mechanism was **deprecated in PS 8.0.27 and removed in PS 8.0.30** - do not enable it; use the `--page-tracking` flag instead.

## Recipe: stream + compress + upload to S3

```bash
xtrabackup --backup --stream=xbstream --compress --parallel=4 --target-dir=./ \
  | xbcloud put --storage=s3 \
      --s3-endpoint='https://s3.us-east-1.amazonaws.com' \
      --s3-access-key=… --s3-secret-key=… --s3-bucket=my-backups \
      --parallel=10 my-backup-2026-05-29
```

Download and extract:

```bash
xbcloud get --storage=s3 --s3-bucket=my-backups my-backup-2026-05-29 \
  | xbstream -x -C /restore
xtrabackup --decompress --target-dir=/restore --parallel=4
xtrabackup --prepare    --target-dir=/restore
```

`xbcloud` supports S3, Azure Blob, Google Cloud Storage, and OpenStack Swift via `--storage=swift`.

## Recipe: encrypted backup

```bash
# Generate a key once: openssl rand -base64 24 > /etc/mysql/backup.key
xtrabackup --backup \
  --encrypt=AES256 \
  --encrypt-key-file=/etc/mysql/backup.key \
  --encrypt-threads=4 \
  --target-dir=/bk/enc
```

Decrypt before prepare:

```bash
xtrabackup --decrypt=AES256 --encrypt-key-file=/etc/mysql/backup.key \
  --target-dir=/bk/enc --parallel=4
xtrabackup --prepare --target-dir=/bk/enc
```

`--encrypt-key=<hex>` is also accepted but the file form is safer (key isn't in process arguments / shell history).

## Recipe: partial backup

```bash
# Only some tables / databases:
xtrabackup --backup --tables='^reporting\\..*' --target-dir=/bk/reporting
xtrabackup --backup --databases='salesdb other_db' --target-dir=/bk/two
xtrabackup --backup --tables-exclude='audit\\.events' --target-dir=/bk/no-audit
```

Partial backups restore via **transportable tablespaces** (`--export` during prepare, then `IMPORT TABLESPACE` on the target). Plan for that - it is not a `--copy-back`. A partial backup cannot be used as an incremental base.

## Recipe: point-in-time recovery

Restore a full backup, start the server, then replay binary logs from the position the backup recorded in **`xtrabackup_binlog_info`** (not `xtrabackup_slave_info` - see below).

```bash
xtrabackup --copy-back --target-dir=/bk/base && chown -R mysql:mysql /var/lib/mysql
systemctl start mysql
cat /bk/base/xtrabackup_binlog_info          # e.g. mysql-bin.000003   57
mysqlbinlog /var/lib/mysql/mysql-bin.000003 /var/lib/mysql/mysql-bin.000004 \
  --start-position=57 --stop-datetime="2026-05-27 14:00:00" | mysql -u root -p
```

## Recipe: rebuild a replica from a backup

Back up the source (or an existing replica with `--slave-info --safe-slave-backup`), prepare, copy to the new node, then point replication at the recorded coordinates.

```bash
# GTID-based (preferred): line 3 of xtrabackup_binlog_info holds the GTID set
mysql -e "RESET BINARY LOGS AND GTIDS;
          SET GLOBAL gtid_purged='<gtid-set-from-xtrabackup_binlog_info>';
          CHANGE REPLICATION SOURCE TO SOURCE_HOST='src', SOURCE_USER='repl',
            SOURCE_PASSWORD='***', SOURCE_AUTO_POSITION=1;
          START REPLICA;"
```

Two coordinate files, two purposes:

- **`xtrabackup_binlog_info`** - the *backed-up server's own* binlog position/GTID. Use this for PITR and when seeding from the source.
- **`xtrabackup_slave_info`** - the *source's* coordinates as seen by a replica (written when you pass `--slave-info`). Use this when seeding a new replica from an existing replica. `--slave-info` writes a ready-made `CHANGE REPLICATION SOURCE TO …` statement into it.

**8.4 note:** MySQL/PS 8.4 removed `CHANGE MASTER TO` and `START SLAVE`. Use `CHANGE REPLICATION SOURCE TO` / `START REPLICA` - which is exactly the statement form `--slave-info` already writes.

## PS 8.0 vs PS 8.4 differences

| Topic | 8.0 | 8.4 |
|---|---|---|
| Redo log sizing | Both legacy variables (`innodb_log_files_in_group`, `innodb_log_file_size`) and the modern `innodb_redo_log_capacity` (8.0.30+) are recognized | Legacy variables **removed**; `innodb_redo_log_capacity` is the only knob. XtraBackup honors the active variable automatically. |
| Required grants | `BACKUP_ADMIN` added to the base set (`PROCESS, RELOAD, LOCK TABLES, REPLICATION CLIENT` + `SELECT` on `performance_schema.log_status`) | Same base set; also `INNODB_REDO_LOG_ARCHIVE` for the redo log archiving feature |
| `mysql_native_password` plugin | Default-loaded | Not loaded by default - use `caching_sha2_password` for the backup user, or explicitly load the plugin |
| Compression default | ZSTD (since 8.0.34-29); LZ4 and ZSTD selectable. QuickLZ removed for backup. | ZSTD; same options as 8.0.34-29+. |
| Component-based keyring (`component_keyring_file`, `component_keyring_kmip`) | Supported | Supported; plugin-based keyring is deprecated - migrate before going to 8.4 |

## Key gotchas

- **Stop the server, empty the datadir** before `--copy-back`. The flag refuses to overwrite a non-empty target.
- **`--prepare` is single-threaded by default** for crash-recovery correctness. Use `--use-memory=4G` (or higher) to speed it up.
- **PXC backups** must include `--galera-info` if the backup will be used as an SST source or to bootstrap a new node. The file `xtrabackup_galera_info` is what `wsrep_sst_xtrabackup-v2` reads.
- **TokuDB backup is not supported** by PXB 8.0+ (TokuDB itself was removed from PS in 8.0.28).
- **MyRocks backup** is supported by PXB 8.0+ but copies the entire RocksDB data - no incremental support for the MyRocks portion.
- **Verify the version pair every time.** A mismatched PXB silently produces unusable backups. Make this a script check, not a habit.
