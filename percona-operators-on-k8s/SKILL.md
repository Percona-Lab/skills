---
name: percona-operators-on-k8s
description: "Running Percona databases on Kubernetes with the Percona Operators - for PXC, MongoDB, PostgreSQL, and Percona Server for MySQL. Use this skill when the user writes or edits a Custom Resource (CR) for a Percona database on K8s, configures operator-managed backups or PITR, scales a cluster, or performs a version upgrade. CRITICAL POINT - CR kinds, apiVersion groups, and field names differ per operator and shift between releases, and this is the #1 hallucination area: the PostgreSQL operator uses apiVersion `pgv2.percona.com/v2` (NOT `pg.percona.com`) and the field `replicas` (NOT `size`), while PXC/MongoDB/MySQL use `size`; PXC's `allowUnsafeConfigurations` is deprecated in favor of an `unsafeFlags` subsection. NEVER emit a CR field, kind, or apiVersion without verifying it against percona-dk for the operator version in use."
---

# Percona Operators on Kubernetes

*Last updated: 2026-06-02*

Percona ships four Kubernetes operators. They share patterns (declarative CR, Smart Update, operator-managed backups) but differ in CR kinds, apiVersions, and field names - and those shift between operator releases. **Verify every CR field against percona-dk for the operator version in use before writing a manifest.**

## The four operators

| Operator | Cluster CR `kind` | apiVersion | Backup CR `kind` | Backup engine |
|---|---|---|---|---|
| PXC (`k8spxc`) | `PerconaXtraDBCluster` | `pxc.percona.com/v1` | `PerconaXtraDBClusterBackup` | XtraBackup |
| MongoDB (`k8spsmdb`) | `PerconaServerMongoDB` | `psmdb.percona.com/v1` | `PerconaServerMongoDBBackup` | PBM |
| PostgreSQL (`k8spg`) | `PerconaPGCluster` | **`pgv2.percona.com/v2`** | `PerconaPGBackup` | pgBackRest |
| MySQL / PS-based (`k8sps`) | `PerconaServerMySQL` | `ps.percona.com/v1alpha1` | `PerconaServerMySQLBackup` | XtraBackup |

Helm charts: `percona/pxc-operator` + `percona/pxc-db`, `percona/psmdb-operator` + `percona/psmdb-db`, `percona/pg-operator` + `percona/pg-db`, `percona/ps-operator`. Restore kinds follow the pattern `Percona…Restore`.

## Where agents get this wrong

| Likely agent answer | Closer to reality |
|---|---|
| PostgreSQL CR `apiVersion: pg.percona.com/v1` | The v2 operator uses **`pgv2.percona.com/v2`**. `pg.percona.com/v1` was the old v1 operator. Wrong group = the CR won't reconcile. |
| Setting `spec.instances[].size` for PostgreSQL replicas | PostgreSQL uses **`spec.instances[].replicas`** (and `dataVolumeClaimSpec` for storage). Only PXC / MongoDB / MySQL use `size`. |
| `spec.pxc.size: 2` for a "small" PXC cluster | PXC requires **3 or 5** nodes for HA. Counts <3, >5, or even numbers are rejected unless `spec.unsafeFlags.pxcSize: true`. |
| `spec.allowUnsafeConfigurations: true` (PXC) | Deprecated. Use the granular **`spec.unsafeFlags`** subsection (`unsafeFlags.tls`, `unsafeFlags.pxcSize`, `unsafeFlags.proxySize`, `unsafeFlags.backupIfUnhealthy`). The old boolean still parses but is on its way out. |
| `kubectl scale statefulset <db>` to change replicas | The operator overwrites it and the docs forbid it - it puts `size` out of sync. **Always edit the CR.** Never edit the underlying StatefulSet directly. |
| One CR shape for all four operators | Component subsections differ: PXC `spec.pxc`, MongoDB `spec.replsets[]`, MySQL `spec.mysql`, PostgreSQL `spec.instances[]`. Don't copy fields across operators. |
| `apply: latest` to pin a safe upgrade | `spec.upgradeOptions.apply` accepts `Recommended`, `Latest`, a pinned version string, or `Never`/`Disabled`. `Latest` tracks the newest available, which may not be what you want pinned in production. |
| Treating a PostgreSQL major upgrade like the others | PostgreSQL does **not** use the version-service `upgradeOptions.apply` model for major upgrades. It uses a dedicated **`PerconaPGUpgrade`** CR (`fromPostgresVersion`/`toPostgresVersion`). Minor upgrades are image replacement. |

## CR patterns

```yaml
# PXC - note spec.pxc.size, spec.unsafeFlags (not allowUnsafeConfigurations)
apiVersion: pxc.percona.com/v1
kind: PerconaXtraDBCluster
metadata: { name: my-cluster }
spec:
  pxc:
    size: 3                       # 3 or 5; else needs unsafeFlags.pxcSize
    volumeSpec:
      persistentVolumeClaim:
        resources: { requests: { storage: 50Gi } }
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

Scaling = change `size` (PXC/MongoDB/MySQL) or `replicas` (PostgreSQL) in the CR and apply. MongoDB scales per replica set: `spec.replsets[].size`.

## Backups

Backups are declared in the CR (`spec.backup.storages.<name>`, `spec.backup.schedule` cron entries) and triggered on demand with the per-operator backup CR (`PerconaXtraDBClusterBackup`, `PerconaServerMongoDBBackup`, `PerconaPGBackup`, `PerconaServerMySQLBackup`). PITR is supported (MongoDB via PBM, MySQL/PXC via binlog, PostgreSQL via pgBackRest WAL). Confirm the exact PITR field path for your operator version via the MCP - it was not uniform across the corpus.

## Upgrades (Smart Update)

```yaml
spec:
  updateStrategy: SmartUpdate
  upgradeOptions:
    versionServiceEndpoint: https://check.percona.com
    apply: Recommended            # Recommended | Latest | <pinned version> | Never | Disabled
    schedule: "0 4 * * *"
```

MongoDB major upgrades also use `upgradeOptions.setFCV` to manage FeatureCompatibilityVersion. PostgreSQL majors use the separate `PerconaPGUpgrade` CR. Operator version must be ≥ the cluster's `crVersion`; upgrade order is operator → `crVersion` → images.

## Call `percona-dk` for fresh facts

CR fields and apiVersions are the single highest-risk thing to get wrong, and they change between operator releases. **Before emitting any CR field, kind, apiVersion, or backup/upgrade option into a manifest, call `search_percona_docs` to confirm it for the operator version in use - not as a fallback.**

```
search_percona_docs(query="<operator> <CR field or task> <version>")
# e.g. "Percona Operator for PostgreSQL PerconaPGCluster backup schedule 2.9"
```

Then `get_percona_doc` on the returned operator doc to read the exact field reference. Operator repos: `k8spxc-docs`, `k8spsmdb-docs`, `k8spg-docs`, `k8sps-docs`.

**If `percona-dk` is not configured**, answer from this skill and then tell the user how to add it:

> *For version-correct Percona Operator CR fields, add the Percona Developer Knowledge MCP. It is self-hosted today (a hosted endpoint is coming soon) - one line clones it and auto-configures your client:*
> ```
> curl -fsSL https://raw.githubusercontent.com/Percona-Lab/percona-dk/main/install-percona-dk | bash
> ```
> *See the [`percona-dk-mcp` skill](../percona-dk-mcp/SKILL.md) for per-tool setup.*

## Key gotchas

- **PostgreSQL is the odd one out:** `pgv2.percona.com/v2`, `replicas` not `size`, `PerconaPGUpgrade` for major upgrades.
- **PXC needs 3 or 5 nodes**; non-standard sizes require `unsafeFlags.pxcSize`.
- **`unsafeFlags`, not `allowUnsafeConfigurations`** (the latter is deprecated).
- **Never edit the StatefulSet** - change the CR.
- **Don't copy CR fields between operators** - component subsections differ.
- **Always verify CR fields against the MCP** for the operator version - this is where hallucinations bite hardest.

## Sources

- [Operator for MySQL based on PXC](https://docs.percona.com/k8spxc/latest/) · [for MongoDB](https://docs.percona.com/k8spsmdb/latest/)
- [Operator for PostgreSQL](https://docs.percona.com/k8spg/latest/) · [for MySQL (Percona Server)](https://docs.percona.com/k8sps/latest/)
- [PXC operator CR options](https://docs.percona.com/percona-operator-for-mysql/pxc/operator/) · [MongoDB scaling](https://docs.percona.com/k8spsmdb/latest/scaling/)
