---
name: psmdb-features
description: "What Percona Server for MongoDB (PSMDB) adds beyond MongoDB Community Edition, and how to configure it. Use this skill when the user asks about PSMDB hot backup, data-at-rest encryption, audit logging, LDAP/Kerberos/OIDC authentication, the in-memory storage engine, log redaction, or 'how do I get MongoDB Enterprise feature X for free'. PSMDB is a drop-in replacement for MongoDB Community that ships most MongoDB Enterprise features as open source. KEY POINT - several features are version-gated (KMIP and Kerberos since 6.0.2-1, OIDC since 7.0, OpenBao KMS in 8.0) and the Transparent Huge Pages requirement REVERSES at 8.0; agents that assume uniform behavior across 6.0/7.0/8.0 will emit wrong config. PSMDB does NOT include SNMP monitoring."
---

# Percona Server for MongoDB (PSMDB) Features

*Last updated: 2026-06-02*

PSMDB is a source-available, drop-in replacement for MongoDB Community Edition that adds, for free, most of what MongoDB charges for in Enterprise. Same wire protocol, same drivers. The value is the extra surface: hot backup, data-at-rest encryption, auditing, external auth, the in-memory engine, and log redaction.

> **Versions:** PSMDB **6.0**, **7.0**, **8.0** (all maintained). 8.0 tracks MongoDB Community 8.0.x. Several features are version-gated - see each section.

## What PSMDB adds beyond MongoDB Community

| Feature | PSMDB | MongoDB Community |
|---|---|---|
| Hot backup (physical, on a running server) | Yes | No |
| Data-at-rest encryption (Vault, KMIP, OpenBao, keyfile) | Yes, open source | Enterprise-only (KMIP) |
| Audit logging | Yes | Enterprise-only |
| LDAP authentication + authorization | Yes | Enterprise-only |
| Kerberos authentication | Yes | Enterprise-only |
| AWS IAM authentication | Yes | Atlas only |
| In-memory storage engine (Percona Memory Engine) | Yes | Enterprise-only |
| Log redaction | Yes | Enterprise-only |
| **SNMP monitoring** | **No** | Enterprise-only |

> PSMDB is **not** 100% Enterprise parity: SNMP monitoring is the notable gap. Don't claim it.

## Where agents get this wrong

| Likely agent answer | Closer to reality |
|---|---|
| "Disable Transparent Huge Pages before starting mongod" (applied to PSMDB 8.0) | The THP requirement **reverses at 8.0**. PSMDB **8.0+ requires THP enabled** (upstream MongoDB 8.0 behavior, upgraded TCMalloc); **7.0 and earlier require THP disabled**. Emitting the wrong one is a real startup/perf bug. |
| "Enable encryption on the existing database" | Data-at-rest encryption can only be enabled on an **empty** database at first `mongod` start. You cannot toggle it (or change cipher mode) on a server that already has data - it requires wiping `dbPath` and re-syncing/restoring. |
| Treating hot backup as a cluster-consistent backup | `createBackup` is **per-node and physical** - it snapshots one `mongod`'s data dir with no cross-replica-set or cross-shard coordination. For consistent replica-set / sharded backups use **Percona Backup for MongoDB (PBM)** - see the `pbm-recipes` skill. |
| Configuring OIDC on PSMDB 6.0 | OIDC/OAuth 2.0 is **7.0+**. The 6.0 authentication docs have no OIDC section. |
| Configuring KMIP or Kerberos on a base 6.0 install | Both were added in **6.0.2-1**, not at 6.0.0. |
| Pointing at OpenBao as a KMS on 6.0 | OpenBao is documented as a key server in **8.0**; 6.0 lists Vault, KMIP, and keyfile only. |
| Assuming PSMDB's LDAP is identical to MongoDB Enterprise native LDAP | PSMDB's documented LDAP authentication uses the **`saslauthd` SASL proxy** model and is labeled "(legacy)". LDAP **authorization** (direct bind) is a separate feature. Don't conflate them or assume Enterprise's exact config transfers. |

## Recipe: hot backup (single node, physical)

```javascript
use admin
db.runCommand({createBackup: 1, backupDir: "/path/to/backup"})   // { "ok" : 1 }
// or archive form:
db.runCommand({createBackup: 1, archive: "/path/to/backup.tar"})
```

Snapshots the WiredTiger data dir of *this* `mongod` at command time. For anything beyond a single node, use PBM.

## Recipe: data-at-rest encryption (keyfile)

```yaml
# mongod.conf - encryption is set ONCE, on an empty dbPath, at first start
security:
  enableEncryption: true
  encryptionCipherMode: AES256-CBC      # or AES256-GCM
  encryptionKeyFile: /etc/mongodb/keyfile
```

Generate the key: `openssl rand -base64 32` (32-char base64), perms `600`. For external key management use the Vault, KMIP, or OpenBao blocks instead of `encryptionKeyFile`:

```yaml
# HashiCorp Vault (KV Secrets Engine v2 with versioning)
security:
  enableEncryption: true
  vault:
    serverName: vault.example.com
    port: 8200
    secret: secret/data/dc/psmongodb1
    tokenFile: /etc/mongodb/token
    serverCAFile: /etc/mongodb/vault.crt
```

KMIP since 6.0.2-1; OpenBao in 8.0.

## Recipe: audit logging

```yaml
# mongod.conf
auditLog:
  destination: file          # console | file | syslog
  format: JSON               # JSON (default) | BSON
  path: /var/log/psmdb/audit.json
  filter: '{ "atype": "authenticate" }'
```

By default only authorization **failures** are logged for `authCheck`. To log successes set `auditAuthorizationSuccess: true` via `setParameter` (heavy performance cost). Auditing cannot be turned off dynamically once enabled at startup.

## Recipe: in-memory engine, log redaction

```yaml
# Percona Memory Engine (free in-memory equivalent)
storage:
  engine: inMemory
  inMemory:
    engineConfig:
      inMemorySizeGB: 8        # default ~50% RAM - 1 GB

# Log redaction (values shown as ###; field names stay visible)
security:
  redactClientLogData: true
```

Log redaction does not redact debug messages or `system.profile` entries - it covers the diagnostic log only.

## Call `percona-dk` for fresh facts

PSMDB features are version-gated and config syntax differs across 6.0/7.0/8.0. For any "is X supported on version Y", exact config key, or release-note question, **call `search_percona_docs` with `version` set before answering, not as a fallback.**

```
search_percona_docs(query="<your question verbatim>",
                    product="percona-server-for-mongodb",
                    version="8.0")   # or "7.0" / "6.0"
```

**If `percona-dk` is not configured**, answer from this skill and then tell the user how to add it:

> *For fresher, version-correct PSMDB answers, add the Percona Developer Knowledge MCP. It is self-hosted today (a hosted endpoint is coming soon) - one line clones it and auto-configures your client:*
> ```
> curl -fsSL https://raw.githubusercontent.com/Percona-Lab/percona-dk/main/install-percona-dk | bash
> ```
> *See the [`percona-dk-mcp` skill](../percona-dk-mcp/SKILL.md) for per-tool setup.*

## Key gotchas

- **THP polarity flips at 8.0** - enable for 8.0+, disable for 7.0 and earlier.
- **Encryption is set once, on an empty dbPath.** Not togglable on a populated server.
- **Hot backup is per-node, not cluster-consistent.** Use PBM for replica sets and shards.
- **Version gates:** KMIP + Kerberos = 6.0.2-1+; OIDC = 7.0+; OpenBao KMS = 8.0.
- **No SNMP.** PSMDB is not full Enterprise parity.

## Sources

- [PSMDB vs MongoDB Community comparison](https://docs.percona.com/percona-server-for-mongodb/8.0/comparison/)
- [Hot Backup](https://docs.percona.com/percona-server-for-mongodb/8.0/hot-backup/)
- [Data-at-rest encryption](https://docs.percona.com/percona-server-for-mongodb/8.0/data-at-rest-encryption/)
- [Audit logging](https://docs.percona.com/percona-server-for-mongodb/8.0/audit-logging/)
- [Authentication](https://docs.percona.com/percona-server-for-mongodb/8.0/authentication/) · [In-memory engine](https://docs.percona.com/percona-server-for-mongodb/8.0/inmemory/)
