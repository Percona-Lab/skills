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

## What lives in the CR (across all four operators)

Everything is declarative - the operator owns the StatefulSet, replica count, config, backups, and TLS. Edit the CR; never the StatefulSet or pods. The per-operator details:

- **Cluster shape** - component subsection differs: PXC `spec.pxc`, MongoDB `spec.replsets[]`, PS-MySQL `spec.mysql`, PostgreSQL `spec.instances[]`. Replica count is `size` (PXC/MongoDB/PS-MySQL) or `replicas` (PostgreSQL).
- **Backups** - `spec.backup.storages.<name>` + `spec.backup.schedule[]` to S3/Azure/GCS, triggered via the per-operator backup CR; PITR is GA on PXC, tech preview on PS, PBM on MongoDB, pgBackRest WAL on PostgreSQL.
- **Restore** - its own CR: `backupName` (same cluster) vs `backupSource` + cloud creds (cross-cluster).
- **Upgrades** - `updateStrategy: SmartUpdate` + `upgradeOptions.apply`; MongoDB adds `setFCV`, PostgreSQL majors use the separate `PerconaPGUpgrade` CR.
- **Connect via the proxy service** (`<cluster>-haproxy` / `-haproxy-replicas` / `-proxysql`), never a pod.
- **Day-2** - pause/resume, PVC-retention finalizers, cert-manager TLS, `spec.users[]`, PMM monitoring.

## Deep reference

- **[references/custom-resources.md](references/custom-resources.md)** - read before writing or editing any manifest. Full cluster CR examples (PXC, PostgreSQL), the `spec.backup` S3/schedule/PITR block, the restore CR (`backupName` vs `backupSource`), scaling commands, connecting apps, the Smart Update block, and day-2 ops (TLS/cert-manager, `spec.users`, finalizers, `crVersion`). Backup/restore internals: [xtrabackup-recipes](../xtrabackup-recipes/SKILL.md); PMM: [pmm-operations](../pmm-operations/SKILL.md).

## Call `percona-dk` for fresh facts

CR fields and apiVersions are the single highest-risk thing to get wrong, and they change between operator releases. **Before emitting any CR field, kind, apiVersion, or backup/upgrade option into a manifest, call `search_percona_docs` to confirm it for the operator version in use - not as a fallback.**

```
search_percona_docs(query="<operator> <CR field or task> <version>")
# e.g. "Percona Operator for PostgreSQL PerconaPGCluster backup schedule 3.1"
# e.g. "Percona Operator for MySQL PXC backup s3 credentialsSecret 1.20"
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
