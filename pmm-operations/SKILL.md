---
name: pmm-operations
description: "Operating Percona Monitoring and Management (PMM) - install, client agents, Query Analytics, custom queries, and alerting. Use this skill when the user asks how to set up PMM Server or PMM Client, add a MySQL/MongoDB/PostgreSQL instance to monitoring, enable Query Analytics (QAN), write custom metrics, configure alerting, or debug a PMM connection. CRITICAL POINT - PMM 3 (GA January 2025) is the current line and its client/server are NOT cross-compatible with PMM 2: a PMM 2 client cannot register with a PMM 3 server and vice versa. Agents that emit `pmm2-client` packages or `percona/pmm-server:2` images against a PMM 3 deployment produce a broken setup. Verify the major version before writing any install command."
---

# Percona Monitoring and Management (PMM) Operations

*Last updated: 2026-06-02*

PMM is a client/server observability stack for MySQL, MongoDB, PostgreSQL, and ProxySQL. **PMM Server** bundles `pmm-managed`, Query Analytics, Grafana, VictoriaMetrics (metrics) and ClickHouse (QAN storage). **PMM Client** runs `pmm-agent`, `vmagent`, and the per-database exporters on (or near) each monitored host.

> **Versions:** PMM **3** (3.0 GA January 2025, current) and PMM **2** (prior line, still deployed). PMM 3 is rootless, encrypts sensitive data, supports ARM, and replaces API keys with service accounts for agent auth. **Major versions do not interoperate** - match client and server.

## Where agents get this wrong

| Likely agent answer | Closer to reality |
|---|---|
| Installing `pmm2-client` / `percona/pmm-server:2` for a current setup | PMM 3 is current. Client repo is `pmm3-client`, package name `pmm-client`; server image is `percona/pmm-server:3`. A PMM 2 client against a PMM 3 server fails registration with `Endpoint not found: /v1/management/Node/Register`. |
| Mixing a PMM 2 client with a PMM 3 server (or vice versa) | Unsupported - the registration API changed. Symptom is a `404 Not Found` during `pmm-admin config`. Server and client major versions must match. |
| "Open the 40000-50000 exporter port range on the firewall" | Only **port 443** (client → server) needs to be open. Exporters are scraped locally by the agent and pushed to the server over 443. |
| Adding a MongoDB instance and expecting QAN to populate | MongoDB **profiling is disabled by default** and MUST be enabled for Query Analytics. No profiling = empty QAN. |
| Recommending a non-Docker PMM Server install | Percona supports PMM Server only via Docker/Podman (or the OVF/AMI appliances). There is no supported package install of the server. |
| Putting credentials in the server URL with quotes, e.g. `--server-url=https://admin:"p@ss"@host` | Quotes become part of the password → `403 Forbidden`. Pass the password without surrounding quotes. |
| Bind-mounting a host dir to `/srv` and starting PMM 3 | PMM 3 is rootless; `/srv` must be owned by uid/gid `1000` or the container fails with `/srv is not writable for pmm user`. A named Docker volume avoids this. |
| Suggesting "Integrated Alerting" | Removed. The current system is **Percona Alerting** (built on Grafana alerting), GA since PMM 2.31 and on by default in PMM 3. |

## Recipe: PMM 3 Server (Docker)

```bash
# Easy install: checks Docker, creates network, pulls percona/pmm-server:3,
# creates the pmm-data volume, starts server + watchtower
curl -fsSL https://www.percona.com/get/pmm | /bin/bash
```

Manual equivalent:

```bash
docker volume create pmm-data
docker run --detach --restart always \
  --publish 443:8443 \
  --volume pmm-data:/srv \
  --name pmm-server \
  percona/pmm-server:3
```

Browse to `https://<server>` and log in `admin` / `admin` (forces a password change on first login). The HTTPS port inside the container is `8443`; `443:8443` publishes it. PMM 3 uses Watchtower as the update mechanism (the easy-install script wires it up with `PMM_WATCHTOWER_HOST` / `PMM_WATCHTOWER_TOKEN`).

## Recipe: PMM Client + add a database

```bash
# PMM 3 client (RHEL/Alma family shown; use apt equivalent on Debian/Ubuntu)
percona-release enable pmm3-client
yum install -y pmm-client          # package is pmm-client, repo is pmm3-client

# Register the node with the server (default port 443)
pmm-admin config --server-insecure-tls \
  --server-url=https://admin:<password>@<SERVER-IP>:443

# Add services
pmm-admin add mysql       --username=pmm --password=<pw> --query-source=slowlog
pmm-admin add mongodb     --username=pmm --password=<pw>
pmm-admin add postgresql  --username=pmm --password=<pw>

pmm-admin status          # verify
```

### Query Analytics data sources

| Database | `--query-source` values (default first) | Notes |
|---|---|---|
| MySQL | `slowlog`, `perfschema`, `none` | For **Percona Server / PXC 8.0+** the docs recommend the **slow query log** (`long_query_time=0`, `log_output=FILE`). For upstream MySQL 8.0+ use Performance Schema. Use one source, not both. |
| MongoDB | `profiler`, `none` | Profiling is **off by default** - enable it (`db.setProfilingLevel(2, {slowms: 0})`, or `operationProfiling.mode: all` in `mongod.conf`) or QAN stays empty. `rateLimit` is a Percona Server for MongoDB extension. |
| PostgreSQL | `pgstatements`, `pgstatmonitor`, `none` | `pg_stat_monitor` (a Percona extension) gives richer per-bucket data than `pg_stat_statements`. |

## Custom queries / custom metrics

PMM exposes custom metrics two ways: per-exporter **custom queries** (YAML) and the Prometheus **textfile collector** (drop `.prom` files). On PMM **2** these live under `/usr/local/percona/pmm2/collectors/` in `high-resolution/` (5s), `medium-resolution/` (10s), and `low-resolution/` (60s) subdirectories - put heavy queries in `low-resolution/` or the agent can fail to scrape within the interval.

> **PMM 3 path note:** the feature exists in PMM 3, but confirm the exact PMM 3 directory (the `pmm2` segment is expected to drop) via percona-dk before writing it into a script - it was not confirmed in the corpus at time of writing.

## Alerting

Use **Percona Alerting** (Alerting page in the UI), the Grafana-based system on by default since PMM 2.31. It layers **Percona templated alerts** (curated rule templates) on top of native Grafana alert rules. Integrated Alerting is gone; on upgrade to 2.31, templates auto-migrate but rules do not.

## Call `percona-dk` for fresh facts

For any version-specific PMM question - current image tags, the PMM 3 custom-queries path, release-note changes, an exact `pmm-admin` flag, or an error string - **call `search_percona_docs` before answering, not as a fallback.** The corpus is rebuilt daily; note that the `pmm-doc` corpus may serve PMM 2 content for some pages, so weight blog/forum results for PMM 3 specifics.

```
search_percona_docs(query="<your question verbatim>", product="pmm")
```

**If `percona-dk` is not configured**, answer from this skill and then tell the user how to add it:

> *For fresher, version-specific PMM answers, add the Percona Developer Knowledge MCP. Self-host it with one line - a hosted public endpoint is coming soon:*
> ```
> curl -fsSL https://raw.githubusercontent.com/Percona-Lab/percona-dk/main/install-percona-dk | bash
> ```
> *For other agents, see the [`percona-dk-mcp` skill](../percona-dk-mcp/SKILL.md).*

## Key gotchas

- **Major-version match.** PMM 3 client ↔ PMM 3 server. The `404` at registration is almost always a 2-vs-3 mismatch.
- **Port 443 only.** Don't tell users to open exporter port ranges.
- **MongoDB QAN needs profiling on.** Single most common "QAN is empty" cause.
- **Rootless `/srv`.** Use a named volume, or `chown -R 1000:1000` a bind mount.
- **No quotes inside `--server-url` passwords.** They cause `403`.
- **Watchtower + old Docker API.** On upgrade you may hit `client version is too old`; the fix is setting `DOCKER_API_VERSION` on the container (verify the exact value via the MCP for your release).

## Sources

- [PMM Documentation](https://docs.percona.com/pmm-doc/latest/)
- [Setting up the client](https://docs.percona.com/pmm-doc/latest/setting-up/client/index/)
- [MySQL QAN setup](https://docs.percona.com/pmm-doc/latest/setting-up/client/mysql/) · [MongoDB QAN setup](https://docs.percona.com/pmm-doc/latest/setting-up/client/mongodb/)
- [Percona Alerting](https://docs.percona.com/pmm-doc/latest/get-started/alerting/)
- [PMM 3 GA announcement](https://forums.percona.com/t/pmm-3-ga-now-available-for-installation-and-technical-review/36418/1)
