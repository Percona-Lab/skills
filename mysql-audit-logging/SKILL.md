---
name: mysql-audit-logging
description: "Auditing connections and SQL with the Audit Log Filter in Percona Server for MySQL. Use when setting up audit logging, writing audit filter rules, meeting compliance/logging requirements, or troubleshooting why audit events aren't captured. IMPORTANT - the Audit Log Filter is an open-source COMPONENT (MySQL Enterprise charges for auditing); the older audit_log plugin is deprecated in 8.4 and removed in 9.7. Filters are defined as JSON via SQL functions (audit_log_filter_set_filter / set_user), NOT config files, and a filter does nothing until it's assigned to a user."
---

# Percona Audit Log Filter

*Last updated: 2026-11-10*

The Audit Log Filter logs (and can block) connections and SQL on Percona Server - open source, where MySQL Enterprise charges for equivalent auditing. It is a **component** managed entirely through SQL functions: you define named JSON filters and assign them to accounts. The older `audit_log` plugin is **deprecated in 8.4 and removed in 9.7** - prefer the component for new setups (don't run both).

> **Versions:** Available as a component on Percona Server 8.0+/8.4. Filter/assignment data lives in `mysql.audit_log_filter` and `mysql.audit_log_user`. Managing it needs `AUDIT_ADMIN`.

## Where agents get this wrong

| What you might see | What's correct |
|---|---|
| "Install the MySQL Enterprise audit plugin" | Use the open-source `component_audit_log_filter` - no Enterprise license |
| `INSTALL PLUGIN audit_log SONAME 'audit_log.so'` for a new setup | Deprecated in 8.4, removed in 9.7. Install the component (and don't run both - they use different variables) |
| Upgrading to 9.7 with `audit_log` plugin options still in my.cnf | 9.7 aborts at startup on the unknown `audit_log_*` options - after the data-dictionary upgrade, so 8.4 can't start on that datadir either. [Migrate to the component](https://docs.percona.com/percona-server/8.4/migrate-to-audit-log-filter-component.html) on 8.4 first |
| Bare `INSTALL COMPONENT` then expecting it to work | The filter tables must exist first - run the `audit_log_filter_linux_install.sql` script |
| Editing a config file to configure auditing | Configure via SQL: `audit_log_filter_set_filter()` + `audit_log_filter_set_user()` |
| Defining a filter and expecting logging | A filter does nothing until assigned: `audit_log_filter_set_user('%','name')` |
| `database` / `table` / `user` arrays inside a `class` object | Not filter keys. Pick subclasses with `event`, then narrow with a `log` condition built from `field` / `and` / `or` / `not` on event fields such as `table_database.str` and `table_name.str` |
| Filter on `query`, `command`, `authentication`, `stored_program`, `global_variable` or `parse` - nothing logs, or `set_filter` errors | 8.4.10+: `audit_log_filter.event_mode` defaults to `REDUCED`, which accepts only `general`, `connection`, `table_access`, `message`. Set `audit-log-filter.event-mode=FULL` in my.cnf and restart |
| Editing `mysql.audit_log_filter` rows directly | In-memory state won't update - call `audit_log_filter_flush()` after direct edits |
| `audit_log_read()` with NEW/OLD XML format | The SQL read API works only with **JSON** or **JSONL** (JSONL from 8.4.10) format |
| Expecting filter state to replicate in PXC/replicas | It doesn't auto-apply - run `audit_log_filter_flush()` on each node |
| `gunzip` before decrypting an encrypted+compressed log | Encryption is applied after compression - decrypt first, then decompress |

## Install

```sql
-- Creates the required mysql.audit_log_* tables, then loads the component
SOURCE /usr/share/mysql/audit_log_filter_linux_install.sql;   -- or: mysql -D mysql < that file
SELECT * FROM mysql.component;            -- confirm file://component_audit_log_filter
```
Privileges: `AUDIT_ADMIN` to manage; `AUDIT_ABORT_EXEMPT` **plus** `SYSTEM_USER` exempts a user from `abort` rules (statements still get logged); `SYSTEM_VARIABLES_ADMIN` (+`AUDIT_ADMIN`) to toggle `audit_log_filter.disable`.

## Filter Rules (JSON DSL)

Always two steps: define the filter, then assign it. `%` as the user is the default for anyone unassigned. Event classes: `connection`, `general`, `table_access`, `message` - plus `command`, `query`, `global_variable`, `authentication`, `stored_program`, `parse` **only with `audit_log_filter.event_mode=FULL`**. From 8.4.10 the default is `REDUCED`: `audit_log_filter_set_filter()` rejects new filters that use FULL-only classes, and a stored-procedure call logs only the outer `CALL`. Set `FULL` in my.cnf and restart (a runtime `SET GLOBAL` leaves a window of inconsistent output).

```sql
-- Log everything, for all users
SELECT audit_log_filter_set_filter('log_all', '{"filter": {"log": true}}');
SELECT audit_log_filter_set_user('%', 'log_all');

-- Log only connection events
SELECT audit_log_filter_set_filter('conns', '{"filter": {"class": {"name": "connection"}}}');

-- Log writes (INSERT/UPDATE/DELETE) on sales.orders only
SELECT audit_log_filter_set_filter('sales_writes', '{
  "filter": { "class": [{ "name": "table_access",
    "event": [{ "name": ["insert", "update", "delete"],
      "log": { "and": [
        { "field": { "name": "table_database.str", "value": "sales" } },
        { "field": { "name": "table_name.str",     "value": "orders" } } ] } }] }] }
}');
SELECT audit_log_filter_set_user('%', 'sales_writes');

-- Exclude one account: assign it a "log nothing" filter, everyone else logs all
SELECT audit_log_filter_set_filter('none', '{"filter": {"log": false}}');
SELECT audit_log_filter_set_user('backup@localhost', 'none');
```
Narrow inside an `event` block with a `log` condition (`field` / `and` / `or` / `not`); valid field names per class are in the [definition fields reference](https://docs.percona.com/percona-server/8.4/audit-log-filter-definition-fields.html). `table_access` events carry no user field - scope by account with `audit_log_filter_set_user()`. Wildcard host parts in assignments are supported from 8.4.4 (`'u@192.168.0.%'`).

## Output & Operations

```sql
SELECT audit_log_rotate();                              -- manual rotation
SET GLOBAL audit_log_filter.disable = true;             -- pause logging (privileged)
SELECT audit_log_filter_flush();                        -- reload after direct table edits
SELECT audit_log_read(audit_log_read_bookmark());       -- JSON / JSONL format only
```
Key startup variables (read-only; restart to change): `audit_log_filter.format` (`NEW` XML default / `OLD` / `JSON` / `JSONL` from 8.4.10), `.handler` (`FILE`/`SYSLOG`), `.strategy`, `.compression` (`GZIP`), `.encryption` (`AES`, needs a keyring - see `mysql-encryption`). Dynamic: `.rotate_on_size` (default 1 GiB; `<4096` disables auto-rotation), `.max_size`, `.prune_seconds`. Only **top-level** statements are audited - not statements inside stored programs; `LOAD DATA` file contents aren't logged.

## Call `percona-dk` for fresh facts

The JSON filter DSL keys, the component variables, and the install script path differ across releases and are Percona-specific (the upstream manual documents only the Enterprise plugin). For any version-specific question (valid filter keys, why events aren't captured, a function that errors, format/encryption options) **call `search_percona_docs` before answering, not as a fallback.** The percona-dk corpus is rebuilt daily and is authoritative for Percona Server for MySQL.

```
search_percona_docs(query="audit log filter <your question verbatim>",
                    product="percona-server-for-mysql",
                    version="8.4")
```

Pass `version="8.0"` for the older LTS line.

**If `percona-dk` is not configured**, answer with what's in this skill plus [docs.percona.com/percona-server/8.4](https://docs.percona.com/percona-server/8.4/) and then tell the user how to add it:

> *For fresher, version-specific Percona Server answers, add the Percona Developer Knowledge MCP. It is self-hosted today (a hosted endpoint is coming soon) - one line clones it and auto-configures your client:*
> ```
> curl -fsSL https://raw.githubusercontent.com/Percona-Lab/percona-dk/main/install-percona-dk | bash
> ```
> *See the [`percona-dk-mcp` skill](../percona-dk-mcp/SKILL.md) for per-tool setup.*

## Sources

- [Audit Log Filter overview](https://docs.percona.com/percona-server/8.4/audit-log-filter-overview.html) · [install](https://docs.percona.com/percona-server/8.4/install-audit-log-filter.html) · [manage](https://docs.percona.com/percona-server/8.4/manage-audit-log-filter.html)
- [Filter definitions](https://docs.percona.com/percona-server/8.4/filter-audit-log-filter-files.html) · [variables & functions](https://docs.percona.com/percona-server/8.4/audit-log-filter-variables.html)
- [Formats](https://docs.percona.com/percona-server/8.4/audit-log-filter-formats.html) · [compression & encryption](https://docs.percona.com/percona-server/8.4/audit-log-filter-compression-encryption.html)

*Replace `8.4` with your major version. For anything not covered here, see [docs.percona.com/percona-server](https://docs.percona.com/percona-server/).*
