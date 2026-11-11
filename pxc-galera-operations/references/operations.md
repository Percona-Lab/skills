# PXC / Galera operational reference

Exhaustive config, command, and tuning detail for Percona XtraDB Cluster operations. Read this when you need exact config snippets, the Clone-SST setup, the variable/status tables, load-balancer health-check config, garbd SSL detail, large-transaction fragmenting, or the rolling upgrade procedure. The editorial conceptual guidance lives in `../SKILL.md`.

> **Versions:** PXC **8.0** and **8.4 LTS**, both on Galera 4. Defaults differ in places (SST methods, XtraBackup-SST encryption) - noted per item. Verify with `SELECT VERSION();` and `SHOW STATUS LIKE 'wsrep_provider_version';`.

## Bootstrapping & joining

Config on every node (`mysqld.cnf`):
```ini
wsrep_provider=/usr/lib/galera4/libgalera_smm.so
wsrep_cluster_name=pxc-prod
wsrep_cluster_address=gcomm://10.0.0.1,10.0.0.2,10.0.0.3   # peer list; empty = bootstrap a NEW cluster
wsrep_node_address=10.0.0.1          # unique per node
wsrep_node_name=pxc1                 # unique per node
wsrep_sst_method=xtrabackup-v2
pxc_strict_mode=ENFORCING
innodb_autoinc_lock_mode=2
default_storage_engine=InnoDB
wsrep_applier_threads=8
```
```bash
# Node 1 - bootstrap a NEW cluster (stop with the same unit)
systemctl start mysql@bootstrap.service
#   verify: SHOW STATUS LIKE 'wsrep_cluster_size';  -> 1, wsrep_cluster_status=Primary

# Nodes 2 and 3 - normal start; SST/IST happens automatically.
# Wait for wsrep_local_state_comment=Synced before adding the next node.
systemctl start mysql
```

A bootstrap node has effectively `wsrep_cluster_address=gcomm://` (empty = create a new cluster). Other nodes list peers: `gcomm://10.0.0.1,10.0.0.2,10.0.0.3`.

### Bootstrapping after a full shutdown

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

## Clone SST (PXC 8.4)

PXC 8.4 (8.4.4-x) adds MySQL Clone-plugin-based SST. Set `wsrep_sst_method=clone` on the joiner; `clone` must be in `wsrep_sst_allowed_methods` on both donor and joiner (8.4 default is `xtrabackup-v2, clone`). Requires the `CLONE_ADMIN` privilege and the NetCat package; default port 4444. (On the 8.0 line, Clone SST exists from 8.0.41+ but is **tech preview** - test it before relying on it in production.) Clone SST encrypts with the MySQL `ssl-ca`/`ssl-cert`/`ssl-key` settings (or `clone_ssl_*` on the joiner); keep the certs outside the datadir. Both variables are read-only / config-file-only.

## Key variables

| Variable | Default | Purpose |
|---|---|---|
| `wsrep_cluster_address` | - | `gcomm://` peer list; empty = bootstrap |
| `wsrep_sst_method` | `xtrabackup-v2` | SST method (`clone` in 8.4.4+; 8.0.41+ as tech preview) |
| `pxc_strict_mode` | `ENFORCING` | PK/engine/locking validation (`DISABLED`/`PERMISSIVE`/`ENFORCING`/`MASTER`); 9.7.2-2+ ENFORCING/MASTER also forces `sql_require_primary_key=ON` and rejects setting it `OFF` (8.4.11-11 had this; later 8.4 releases revert to 8.4.10 behavior); lowering the mode later does not reset it |
| `wsrep_OSU_method` | `TOI` | DDL replication mode (`TOI`/`RSU`/`NBO`) |
| `wsrep_provider_options` | - | e.g. `gcache.size=1G;pc.weight=2` |
| `repl.force_sst_after_inconsistency` (provider option) | off (runtime-settable) | Added in 8.4.11-11 and 9.7.2-2. A node voted out of the cluster for a data inconsistency removes `grastate.dat` on shutdown, so its next start does a full SST instead of IST. The 8.4 notes also cover a joiner that fails to apply a write-set during IST |
| `innodb_autoinc_lock_mode` | must be `2` | Required by Galera |
| `wsrep_applier_threads` | `1` | Parallel apply (tune to `wsrep_cert_deps_distance`); replaces deprecated `wsrep_slave_threads` |
| `wsrep_sync_wait` | `0` | Causal-read consistency level |

## Monitoring cluster health

```sql
SHOW GLOBAL STATUS LIKE 'wsrep%';
```
| Variable | Healthy | Alarm |
|---|---|---|
| `wsrep_cluster_status` | `Primary` | anything else = not in the primary component |
| `wsrep_local_state_comment` | `Synced` | `Joining`/`Donor/Desynced` = not ready |
| `wsrep_ready` | `ON` | `OFF` -> error 1047 on all DML |
| `wsrep_flow_control_paused` | ~`0` | `>0.1` = a node is throttling the whole cluster |
| `wsrep_local_recv_queue_avg` | `0` | sustained `>0` = this node can't keep up |
| `wsrep_local_cert_failures` / `wsrep_local_bf_aborts` | flat | rising = hot-row certification conflicts |

## Load balancing

Health-check on cluster state, not raw TCP, so traffic never reaches a `JOINING`/`DONOR` node.
- **HAProxy** - use `option httpchk` against the `clustercheck` script (port 9200), not `option mysql-check`.
- **ProxySQL** - add nodes to a hostgroup with a monitor user; drain a node for maintenance with `SET GLOBAL pxc_maint_mode=MAINTENANCE;` (ProxySQL stops routing after ~10s), then `DISABLED` when done.

## garbd (Galera Arbitrator)

A voting-only daemon (no data) that gives an even node count a quorum tiebreaker - cheaper than a third full node.
```ini
# /etc/default/garb
GALERA_NODES="10.0.0.1:4567,10.0.0.2:4567"
GALERA_GROUP="pxc-prod"
# SSL is ON by default in PXC 8.x - garbd MUST set a cipher or it crashes (gnu::NotSet):
GALERA_OPTIONS="socket.ssl_cipher=AES128-SHA256;socket.ssl_key=...;socket.ssl_cert=...;socket.ssl_ca=..."
```

## Encryption & large transactions

- **Traffic encryption** is ON by default (`pxc-encrypt-cluster-traffic=ON`, covers SST/IST/replication). All nodes must use **identical** cert files; changing it needs a full cluster stop. PXC 8.4 **removed** XtraBackup-level SST encryption (`[xtrabackup] encrypt=`). The supported SST method is `[sst] encrypt=4` with `ssl-ca`/`ssl-cert`/`ssl-key`; it defaults to 4 when `pxc-encrypt-cluster-traffic=ON` and reverts to 0 if that is OFF. `transferfmt=nc` does not support `encrypt=4`.
- **Huge transactions** - by default the whole write-set is buffered in memory (`wsrep_max_ws_size` 2 GB). Fragment a big batch with streaming replication instead:
  ```sql
  SET SESSION wsrep_trx_fragment_unit='rows';
  SET SESSION wsrep_trx_fragment_size=10000;
  ```

## Upgrades

Rolling **8.0 -> 8.4**, one node at a time: remove 8.0 packages (keep datadir), install 8.4, start (auto-upgrade + SST/IST rejoin). Keep writes on 8.0 nodes during the mixed window and avoid 8.4-only DDL until done. PXC 8.4 switches the keyring plugin to a component and defaults to `caching_sha2_password` (needs ProxySQL >= 2.6.2).

**8.4 -> 9.7:** target **9.7.2 or newer** - 8.4.11 -> 9.7.1 is unsupported.
