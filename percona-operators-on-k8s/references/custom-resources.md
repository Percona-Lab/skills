# Percona Operator Custom Resources - field reference

Full CR examples, backup/restore blocks, scaling, connecting apps, upgrades, and day-2 ops, grouped by operator. Load on demand when writing or editing a manifest. **Verify every field against `percona-dk` for the operator version in use** - the field names, kinds, and apiVersions shift between releases (see SKILL.md).

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

Component subsections differ per operator: PXC `spec.pxc`, MongoDB `spec.replsets[]`, PS-MySQL `spec.mysql`, PostgreSQL `spec.instances[]`. Do not copy fields across operators.

## Scaling

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

Backup/restore internals: [xtrabackup-recipes](../../xtrabackup-recipes/SKILL.md).

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

Operator version must be ≥ the cluster's `crVersion`; upgrade order is operator (CRDs/Deployment) → bump `crVersion` → images roll (replicas first, primary last). MongoDB major upgrades also use `upgradeOptions.setFCV` to manage FeatureCompatibilityVersion. PostgreSQL majors use the separate `PerconaPGUpgrade` CR (`fromPostgresVersion`/`toPostgresVersion`); minor upgrades are image replacement.

## Day-2 ops (MySQL)

- **Pause/resume:** `spec.pause: true|false`. **Delete keeps PVCs** by default - add the `percona.com/delete-pxc-pvc` finalizer to drop data too.
- **TLS:** auto-provisioned when **cert-manager** is installed (90-day certs); `spec.sslSecretName` (external) and `spec.sslInternalSecretName` (internal) name the Secrets.
- **Monitoring:** `spec.pmm.enabled: true` with `image: percona/pmm-client:3` and a `serverHost`. Auth differs by PMM major: PMM 3 uses a service-account **token** (`pmmservertoken`), PMM 2 uses an API **key** (`pmmserverkey`). See [pmm-operations](../../pmm-operations/SKILL.md).
- **Debug a stuck reconcile:** `kubectl describe pxc cluster1` (events) → `kubectl logs <pod> -c pxc`.
- **HA hygiene:** spread pods with `spec.pxc.affinity.antiAffinityTopologyKey`, protect quorum with `spec.pxc.podDisruptionBudget`.
