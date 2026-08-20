# Percona Toolkit: DSNs, credentials & install

DSN syntax, credential handling, and package installation steps. Load this when you need to construct a DSN, avoid leaking passwords, or install the toolkit.

## DSNs & credentials

Tools take a DSN: `h=host,P=3306,u=user,p=pass,D=db,t=table,S=/sock,F=/path/my.cnf`. **Never put `p=secret` on the command line** (visible in `ps`, saved to shell history) - use `F=/root/.my.cnf` (reads the `[client]` stanza) or `--ask-pass`. Escape commas in passwords as `\,`.

```ini
# /root/.my.cnf  →  then DSNs shrink to just D=shop,t=orders
[client]
user=ptuser
password=secret
host=db1
```

## Install

```bash
percona-release enable pt release    # enable the Percona Toolkit repo first
apt install percona-toolkit          # Debian / Ubuntu
dnf install percona-toolkit          # RHEL / Rocky / Alma
```

Repo setup: see [docs.percona.com/percona-toolkit](https://docs.percona.com/percona-toolkit/installation.html). The tools are Perl scripts - they install everywhere Perl runs, including on a separate jump host away from the database, and are mostly server-version independent.
