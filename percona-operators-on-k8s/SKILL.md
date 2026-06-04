---
name: percona-operators-on-k8s
description: "Running Percona databases on Kubernetes with the Percona Operators - for PXC, MongoDB, PostgreSQL, and Percona Server for MySQL. Use this skill when the user writes or edits a Custom Resource (CR) for a Percona database on K8s, chooses between the two MySQL operators, configures operator-managed backups (S3/GCS/Azure) or PITR, scales a cluster, or performs a version upgrade. CRITICAL POINT - CR kinds, apiVersion groups, and field names differ per operator and shift between releases, and this is the #1 hallucination area: there are TWO MySQL operators (PXC-based vs Percona-Server-based) with separate CRDs (`pxc.percona.com` vs `ps.percona.com`); the PostgreSQL operator uses apiVersion `pgv2.percona.com/v2` (NOT `pg.percona.com`) and the field `replicas` (NOT `size`), while PXC/MongoDB/MySQL use `size`; PXC's `allowUnsafeConfigurations` is deprecated in favor of an `unsafeFlags` subsection. NEVER emit a CR field, kind, or apiVersion without verifying it against percona-dk for the operator version in use."
---

# Percona Operators on Kubernetes

*Last updated: 2026-06-02*

Percona ships Kubernetes operators for PXC, MongoDB, PostgreSQL, and Percona Server for MySQL. They share patterns (declarative CR, Smart Update, operator-managed backups) but differ in CR kinds, apiVersions, and field names - and those shift between operator releases. **Verify every CR field against percona-dk for the operator version in use before writing a manifest.**

## The operators

| Operator | Cluster CR `kind` | apiVersion | Backup CR `kind` | Backup engine |
|---|---|---|---|---|
| MySQL / PXC-based (`k8spxc`) | `PerconaXtraDBCluster` | `pxc.percona.com/v1` | `PerconaXtraDBClusterBackup` | XtraBackup |
| MongoDB (`k8spsmdb`) | `PerconaServerMongoDB` | `psmdb.percona.com/v1` | `PerconaServerMongoDBBackup` | PBM |
| PostgreSQL (`k8spg`) | `PerconaPGCluster` | **`pgv2.percona.com/v2`** | `PerconaPGBackup` | pgBackRest |
| MySQL / PS-based (`k8sps`) | `PerconaServerMySQL` | `ps.percona.com/v1alpha1` | `PerconaServerMySQLBackup` | XtraBackup |

Helm charts: `percona/pxc-operator` + `percona/pxc-db`, `percona/psmdb-operator` + `percona/psmdb-db`, `percona/pg-operator` + `percona/pg-db`, `percona/ps-operator` + `percona/ps-db`. Restore kinds follow the pattern `Percona…Restore`.

**Two MySQL operators, not one.** "Percona Operator for MySQL" is an umbrella over two distinct, non-interchangeable operators with separate CRDs (see [Choosing the MySQL operator](#choosing-the-mysql-operator)). Check which is installed (`kubectl get pxc` vs `kubectl get ps`) before applying any manifest.

## Where agents get this wrong

| Likely agent answer | Closer to reality |
|---|---|
| "The Percona MySQL Operator" as one product; PXC CRDs applied to a PS install | TWO operators, separate CRDs (`pxc.percona.com` vs `ps.percona.com`). They are NOT interchangeable - check which is installed first. |
| PostgreSQL CR `apiVersion: pg.percona.com/v1` | The v2 operator uses **`pgv2.percona.com/v2`**. `pg.percona.com/v1` was the old v1 operator. Wrong group = the CR won't reconcile. |
| Setting `spec.instances[].size` for PostgreSQL replicas | PostgreSQL uses **`spec.instances[].replicas`** (and `dataVolumeClaimSpec` for storage). Only PXC / MongoDB / MySQL use `size`. |
| `spec.pxc.size: 2` (or `4`) for a PXC cluster | PXC requires **odd 3 or 5** nodes for HA; even counts risk split-brain. Counts <3, >5, or even are rejected unless `spec.unsafeFlags.pxcSize: true`. |
| `spec.allowUnsafeConfigurations: true` (PXC) | Deprecated. Use the granular **`spec.unsafeFlags`** subsection (`unsafeFlags.tls`, `unsafeFlags.pxcSize`, `unsafeFlags.proxySize`, `unsafeFlags.backupIfUnhealthy`). The old boolean still parses but is on its way out. |
| `kubectl scale statefulset <db>` / `kubectl exec` to edit `my.cnf` | The operator overwrites both - config and replica count live in the CR. **Always edit the CR.** Never edit the StatefulSet or pod directly. |
| One CR shape for all operators | Component subsections differ: PXC `spec.pxc`, MongoDB `spec.replsets[]`, PS-MySQL `spec.mysql`, PostgreSQL `spec.instances[]`. Don't copy fields across operators. |
| Treating PS-operator async replication as production-ready | It is **tech preview** (PS operator v1.1.0). Group Replication is the GA topology. |
| Choosing the PS operator for cross-site / multi-cluster DR | Multi-cluster / cross-site replication is supported by the **PXC** operator, not PS. |
| Connecting the app to `<cluster>-pxc-0` directly | Connect to the `<cluster>-haproxy` service (writes) or `-haproxy-replicas` (reads), or `<cluster>-proxysql`. Pod connections bypass HA/failover. |
| `backupName` when restoring into a *different* cluster | Cross-cluster restore needs `backupSource` + cloud creds; PVC backups are namespace-scoped and can't cross namespaces. |
| Stale/missing `crVersion` after an operator upgrade | `crVersion` must match the installed operator version or reconciliation misbehaves. |
| `apply: latest` to pin a safe upgrade | `spec.upgradeOptions.apply` accepts `Recommended`, `Latest`, a pinned version string, or `Never`/`Disabled`. `Latest` tracks the newest available, which may not be what you want pinned in production. |
| Treating a PostgreSQL major upgrade like the others | PostgreSQL does **not** use the version-service `upgradeOptions.apply` model for major upgrades. It uses a dedicated **`PerconaPGUpgrade`** CR (`fromPostgresVersion`/`toPostgresVersion`). Minor upgrades are image replacement. |

## Choosing the MySQL operator

Both back up via XtraBackup and declare everything in the cluster CR, but they are separate products:

| | PXC-based (`pxc.percona.com`) | PS-based (`ps.percona.com`) |
|---|---|---|
| Cluster kind | `PerconaXtraDBCluster` | `PerconaServerMySQL` |
| Replication | Galera **synchronous** multi-primary | **Group Replication (GA)** / async (**tech preview**) |
| Proxy | HAProxy, ProxySQL | HAProxy, MySQL Router (Orchestrator for failover) |
| Maturity | GA since 2019, long track record | Newer; GR GA, async tech preview |
| Cross-site / multi-cluster DR | Supported | Not supported |
| Choose when | Proven synchronous HA, cross-site DR, production PITR | Stock Percona Server + Group Replication + MySQL Router |
| Helm | `percona/pxc-operator` + `percona/pxc-db` | `percona/ps-operator` + `percona/ps-db` |

> **Versions (latest in scope):** PXC operator **v1.19.1** (manages PXC 8.4 / 8.0 / 5.7); PS operator **v1.1.0** (manages Percona Server 8.4 / 8.0). PS-operator **async replication is tech preview** as of v1.1.0 - not for production; Group Replication is GA. Set `crVersion` to match the installed operator.

For MySQL replication/HA concepts behind these topologies, see the [mysql-replication-ha](../mysql-replication-ha/SKILL.md) skill; for Galera/PXC internals, [pxc-galera-operations](../pxc-galera-operations/SKILL.md).

## CR patterns

```yaml
# PXC (Operator for MySQL based on PXC) - note spec.pxc.size, spec.unsafeFlags
apiVersion: pxc.percona.com/v1
kind: PerconaXtraDBCluster
metadata:
  name: cluster1                  # ≤22 chars
  finalizers: [percona.com/delete-pods-in-order]
spec:
  crVersion: "1.19.1"             # match the installed operator
  secretsName: cluster1-secrets
  updateStrategy: SmartUpdate
  pxc:
    size: 3                       # odd: 3 or 5; else needs unsafeFlags.pxcSize
    image: percona/percona-xtradb-cluster:8.4.7-7.1
    volumeSpec:
      persistentVolumeClaim:
        resources: { requests: { storage: 50Gi } }
  haproxy:                        # enable HAProxy OR proxysql, not both
    enabled: true
    size: 3
  # unsafeFlags: { pxcSize: true }   # only to allow non-standard sizes
```

```yaml
# PostgreSQL - note the apiVersion group and 'replicas' (not 'size')
apiVersion: pgv2.percona.com/v2
kind: PerconaPGCluster
metadata: { name: my-pg }
spec:
  instances:
    - name: instance1
      replicas: 3
      dataVolumeClaimSpec:
        resources: { requests: { storage: 50Gi } }
```

Scaling = change `size` (PXC/MongoDB/PS-MySQL) or `replicas` (PostgreSQL) in the CR and apply; e.g. `kubectl patch pxc cluster1 --type merge -p '{"spec":{"pxc":{"size":5}}}'` (PXC odd numbers only). MongoDB scales per replica set: `spec.replsets[].size`. PS-MySQL scales via `spec.mysql.size`. Vertical scaling = edit the component's `resources` (triggers a SmartUpdate rolling restart).

## Backups

Backups are declared in the CR (`spec.backup.storages.<name>`, `spec.backup.schedule[]` cron entries with a retention policy) and triggered on demand with the per-operator backup CR (`PerconaXtraDBClusterBackup`, `PerconaServerMongoDBBackup`, `PerconaPGBackup`, `PerconaServerMySQLBackup`).

**Cloud storage:** both MySQL operators back up via XtraBackup to **S3, Azure Blob, or GCS** (GCS on the PS operator / on-prem PVC). Cloud storage requires a Kubernetes **Secret with credentials**, referenced from the storage entry (`credentialsSecret`). Example PXC storage + schedule:

```yaml
spec:
  backup:
    enabled: true
    storages:
      s3-backup:
        type: s3                  # s3 | azure | gcs
        s3:
          bucket: my-backup-bucket
          region: us-west-2
          credentialsSecret: cluster1-backup-s3
    schedule:
      - name: daily
        schedule: "0 2 * * *"
        storageName: s3-backup
        retention: { count: 7, type: count, deleteFromStorage: true }
    pitr:
      enabled: false              # PXC: GA. Incompatible with retention - use bucket lifecycle
      storageName: s3-backup
      timeBetweenUploads: 60
```

**PITR:** GA on the PXC operator (a pod streams binlogs to cloud storage; incompatible with any retention policy - use bucket lifecycle instead), **tech preview** on the PS operator. MongoDB PITR is via PBM; PostgreSQL via pgBackRest WAL. Confirm the exact PITR field path for your operator version via the MCP - it was not uniform across the corpus.

**Restore** is its own CR. Use `backupName` for same-cluster restore; cross-cluster needs `backupSource` + cloud creds (PVC backups are namespace-scoped). Disable PITR on the live cluster before restoring.

```yaml
apiVersion: pxc.percona.com/v1
kind: PerconaXtraDBClusterRestore
metadata: { name: restore1 }
spec:
  pxcCluster: cluster1
  backupName: backup1             # same cluster
  # cross-cluster: use backupSource (with S3/Azure creds) instead of backupName
  # pitr: { type: date, date: "2026-05-27 14:30:00", backupSource: { storageName: s3-backup } }
```

Backup/restore internals: [xtrabackup-recipes](../xtrabackup-recipes/SKILL.md).

## Connecting applications (MySQL)

Apps connect to the **proxy service**, never directly to a pod:

| Service | Use |
|---|---|
| `<cluster>-haproxy` | writes (routed to the primary) |
| `<cluster>-haproxy-replicas` | reads only |
| `<cluster>-proxysql` | writes + reads (if ProxySQL enabled) |

Root password: `kubectl get secret cluster1-secrets -o jsonpath='{.data.root}' | base64 -d`. System users live in `cluster1-secrets` (`root`, `xtrabackup`, `monitor`, `operator`, …); rotate by patching the Secret. Declarative app users via `spec.users[]` (PXC operator v1.16.0+).

## Upgrades (Smart Update)

```yaml
spec:
  updateStrategy: SmartUpdate
  upgradeOptions:
    versionServiceEndpoint: https://check.percona.com
    apply: Recommended            # Recommended | Latest | <pinned version> | Never | Disabled
    schedule: "0 4 * * *"
```

Operator version must be ≥ the cluster's `crVersion`; upgrade order is operator (CRDs/Deployment) → bump `crVersion` → images roll (replicas first, primary last). MongoDB major upgrades also use `upgradeOptions.setFCV` to manage FeatureCompatibilityVersion. PostgreSQL majors use the separate `PerconaPGUpgrade` CR.

## Day-2 ops (MySQL)

- **Pause/resume:** `spec.pause: true|false`. **Delete keeps PVCs** by default - add the `percona.com/delete-pxc-pvc` finalizer to drop data too.
- **TLS:** auto-provisioned when **cert-manager** is installed (90-day certs); `spec.sslSecretName` (external) and `spec.sslInternalSecretName` (internal) name the Secrets.
- **Monitoring:** `spec.pmm.enabled: true` with `image: percona/pmm-client:3` and a `serverHost`. Auth differs by PMM major: PMM 3 uses a service-account **token** (`pmmservertoken`), PMM 2 uses an API **key** (`pmmserverkey`). See [pmm-operations](../pmm-operations/SKILL.md).
- **Debug a stuck reconcile:** `kubectl describe pxc cluster1` (events) → `kubectl logs <pod> -c pxc`.
- **HA hygiene:** spread pods with `spec.pxc.affinity.antiAffinityTopologyKey`, protect quorum with `spec.pxc.podDisruptionBudget`.

## Call `percona-dk` for fresh facts

CR fields and apiVersions are the single highest-risk thing to get wrong, and they change between operator releases. **Before emitting any CR field, kind, apiVersion, or backup/upgrade option into a manifest, call `search_percona_docs` to confirm it for the operator version in use - not as a fallback.**

```
search_percona_docs(query="<operator> <CR field or task> <version>")
# e.g. "Percona Operator for PostgreSQL PerconaPGCluster backup schedule 2.9"
# e.g. "Percona Operator for MySQL PXC backup s3 credentialsSecret 1.19"
```

Then `get_percona_doc` on the returned operator doc to read the exact field reference. Operator repos: `k8spxc-docs`, `k8spsmdb-docs`, `k8spg-docs`, `k8sps-docs`.

**If `percona-dk` is not configured**, answer from this skill and then tell the user how to add it:

> *For version-correct Percona Operator CR fields, add the Percona Developer Knowledge MCP. It is self-hosted today (a hosted endpoint is coming soon) - one line clones it and auto-configures your client:*
> ```
> curl -fsSL https://raw.githubusercontent.com/Percona-Lab/percona-dk/main/install-percona-dk | bash
> ```
> *See the [`percona-dk-mcp` skill](../percona-dk-mcp/SKILL.md) for per-tool setup.*

## Key gotchas

- **Two MySQL operators:** PXC-based (`pxc.percona.com`, Galera synchronous, cross-site DR, PITR GA) vs PS-based (`ps.percona.com`, Group Replication GA / async tech preview). Separate CRDs, not interchangeable - check which is installed.
- **PostgreSQL is the odd one out:** `pgv2.percona.com/v2`, `replicas` not `size`, `PerconaPGUpgrade` for major upgrades.
- **PXC needs odd 3 or 5 nodes**; non-standard sizes require `unsafeFlags.pxcSize`.
- **`unsafeFlags`, not `allowUnsafeConfigurations`** (the latter is deprecated).
- **Never edit the StatefulSet or pod** - change the CR; the operator reconciles and overwrites manual changes.
- **Don't copy CR fields between operators** - component subsections differ (`spec.pxc` / `spec.mysql` / `spec.replsets[]` / `spec.instances[]`).
- **Cloud backups need a credentials Secret**; cross-cluster restore needs `backupSource`, not `backupName`.
- **Keep `crVersion` in sync** with the installed operator after an upgrade.
- **Always verify CR fields against the MCP** for the operator version - this is where hallucinations bite hardest.

## Sources

- [Compare the MySQL operators](https://docs.percona.com/percona-operator-for-mysql/pxc/compare.html)
- [Operator for MySQL based on PXC](https://docs.percona.com/percona-operator-for-mysql/pxc/) · [for MongoDB](https://docs.percona.com/percona-operator-for-mongodb/)
- [Operator for PostgreSQL](https://docs.percona.com/percona-operator-for-postgresql/latest/) · [for MySQL (Percona Server)](https://docs.percona.com/percona-operator-for-mysql/ps/)
- PXC operator: [CR options](https://docs.percona.com/percona-operator-for-mysql/pxc/operator/) · [helm](https://docs.percona.com/percona-operator-for-mysql/pxc/helm.html) · [backups](https://docs.percona.com/percona-operator-for-mysql/pxc/backups.html) · [restore](https://docs.percona.com/percona-operator-for-mysql/pxc/backups-restore.html) · [scaling](https://docs.percona.com/percona-operator-for-mysql/pxc/scaling.html) · [TLS](https://docs.percona.com/percona-operator-for-mysql/pxc/TLS.html) · [users](https://docs.percona.com/percona-operator-for-mysql/pxc/users.html)
- PS operator: [how it works](https://docs.percona.com/percona-operator-for-mysql/ps/how-it-works.html) · [backups](https://docs.percona.com/percona-operator-for-mysql/ps/backups.html)
- [MongoDB scaling](https://docs.percona.com/percona-operator-for-mongodb/scaling/)
