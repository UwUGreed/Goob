# Tiger staging on Vultr

## Temporary hackathon deployment

The temporary HTTPS address is https://45.76.253.215.sslip.io, with the staging
password gate retained. For this short-lived demo, `/etc/tiger/tiger.env` uses
`GOOB_ENV=hackathon`, `GOOB_HACKATHON_UNVERIFIED_TLS=1`, and both database URLs
use `sslmode=require` without `sslrootcert`. This keeps database traffic encrypted
but skips certificate identity verification. Production deployments still require
`verify-full` and a trusted CA. Restore those settings when ending the demo.
The website service uses `HOME=/var/www/tiger` so libpq does not probe client
certificate files under the home directory blocked by systemd's `ProtectHome`.

This deploys the existing website, without redesigning it. Target: Ubuntu 24.04,
45.76.253.215, hostname tiger-db, 2 vCPU / 4 GB. These instructions target a
fresh dedicated server. Adding these files alone does not provision a server.

## Repository audit and deployment choices

- Frontend: React 19, TypeScript, Vite 6, Tailwind 4, Three.js; npm with
  `goob-dispatch/package-lock.json`. Install with `npm ci --prefix goob-dispatch`;
  build with `npm run build --prefix goob-dispatch`. Node/npm are build tools only.
- Website: Python standard-library HTTP server, psycopg2, dotenv. Start with
  `.venv/bin/python -m operations.server`; loopback 8081 serves both built assets
  and the existing `/api` contract. Vite development uses 5173.
- Separate backend: FastAPI/Uvicorn, SQLAlchemy, psycopg 3, Alembic, OIDC; port
  8090. The website does NOT call its `/api/v1` endpoints. Existing backend-only
  Docker/Compose/Caddy deployment remains unchanged and is not started here.
- This is a multi-component repository, without a workspace package manager.
  Python dependencies use `requirements.txt` and the existing backend constraint
  lock. Ubuntu supplies Python 3.12; setup installs Node 22 with npm from official
  checksummed Node.js binaries because current Tailwind requires it. Build failures stop
  deployment rather than silently altering versions or locks.
- Three data owners remain separate: `goob` website schema, `goob_foundation`
  plus `goob_db_meta` standalone foundation, and `public.*_v1` authenticated API.
  Existing migration entrypoints are preserved and all three are migrated.
- Vultr runs the application and Nginx; the EXISTING Tiger Cloud database remains
  the database server. No local PostgreSQL server or new database is created.
  All three schema migrations target the explicitly configured cloud service.
  TLS verifies its hostname using a trusted CA certificate.
- The website has simulated roles, not real user authentication. Nginx adds a
  shared staging password, and denies remote HTTP access until HTTPS is ready.
  This is a private demo deployment, not a multi-user production security model.

## 1. First-time Vultr setup

Use Vultr's console or your existing administrator SSH login. Keep the console
and current SSH session open while testing a second login after firewall setup.
If using Vultr Firewall, allow inbound 22, 80 and 443 only (plus your actual SSH
port if different). Do not add 5432, 8081, 8090 or 5173.

First commit the deployment files locally and push them when ready. Before that,
you may transfer the working tree using your normal secure file-transfer tool.
For a private repository, the server does not need permanent GitHub credentials:
create an archive locally and upload it with your existing administrator login:

```bash
# On your local machine, after committing these files:
cd /home/spike3y/Desktop/HACKATHON/Goob
git archive --format=tar.gz --output=/tmp/tiger-setup.tar.gz HEAD
scp /tmp/tiger-setup.tar.gz root@45.76.253.215:/root/
ssh root@45.76.253.215
# Now on Vultr:
mkdir -p /root/tiger-setup
tar -xzf /root/tiger-setup.tar.gz -C /root/tiger-setup
cd /root/tiger-setup
bash scripts/server-setup.sh
```

Use your actual administrator account with sudo if root login is unavailable.
The script installs Git/curl/Nginx/Python/Node/npm/UFW and PostgreSQL 18 CLIENT
tools from the official PostgreSQL apt repository, creates user `tiger`, enables
the application services, and
allows SSH before enabling UFW. It does not change SSH authentication, create
passwords, seed data, or overwrite an existing Nginx site/env file. Re-running
refreshes the service template; review changes before rerunning on a used server.
It does not install, start, remove or reconfigure a PostgreSQL server, and does
not reset existing UFW rules. The client tools are only for cloud backups/checks.

```bash
sudo ufw status numbered
sudo ss -ltnp
sudo nginx -t
```

Remove any pre-existing unwanted public allow rules deliberately. No database port needs to listen on Vultr. Allow outbound connectivity to your
Tiger Cloud host/port; never open an inbound PostgreSQL firewall port.

## 2. Configure the existing Tiger Cloud database

Use the existing Tiger Cloud service connection details. Do NOT create a local
role/database, export/import existing data, or reseed the shared cloud service.
If Tiger Cloud has an IP allowlist, permit this Vultr server's outbound IP
(45.76.253.215). Keep credentials server-side, never in VITE_ variables or GitHub.

Copy the trusted CA certificate for that service to `/etc/tiger/tiger-ca.pem`
through your administrator connection. Use the provider's trusted CA; do not
fetch and blindly trust a certificate from an unverified connection. For a
publicly trusted service chain you may instead use the Ubuntu CA bundle path
`/etc/ssl/certs/ca-certificates.crt` in BOTH URLs.

Edit `/etc/tiger/tiger.env` using sudoedit. Substitute the existing host, port,
database and credentials; URL-encode password punctuation. The example database
name `tsdb` is a placeholder; use the actual service database name:

```dotenv
DATABASE_URL=postgresql://USER:URL_ENCODED_PASSWORD@TIGER_CLOUD_HOST:PORT/tsdb?sslmode=verify-full&sslrootcert=/etc/tiger/tiger-ca.pem
GOOB_DATABASE_URL=postgresql://USER:URL_ENCODED_PASSWORD@TIGER_CLOUD_HOST:PORT/tsdb?sslmode=verify-full&sslrootcert=/etc/tiger/tiger-ca.pem
TIGER_DB_HOST=TIGER_CLOUD_HOST
TIGER_DB_PORT=PORT
TIGER_DB_NAME=tsdb
GOOB_DEMO_PORT=8081
GOOB_ENV=production
```

The three TIGER_DB_* values explicitly identify the authorized migration target.
Both URLs must match that host, explicit port and database. Credentials need
permission to back up the database and apply the existing schema migrations.
Separate credentials in the two URLs are allowed for the same database, but
website and v1 migrations currently use DATABASE_URL. No role grants are changed
automatically. Review migrations before pushing because this is the existing
shared cloud database; other clients see those schema changes too.

```bash
sudo chown root:tiger /etc/tiger/tiger.env
sudo chmod 640 /etc/tiger/tiger.env
# If using the provider CA file:
sudo chown root:tiger /etc/tiger/tiger-ca.pem
sudo chmod 640 /etc/tiger/tiger-ca.pem
sudo htpasswd -c /etc/nginx/tiger.htpasswd demo
sudo chown root:www-data /etc/nginx/tiger.htpasswd
sudo chmod 640 /etc/nginx/tiger.htpasswd
```

Use htpasswd WITHOUT -c for later password changes. The staging password is
separate from database credentials. Never commit populated env files or keys.
The env file is parsed as dotenv data, not executed as shell. Use simple values
without shell expansions; systemd also reads this file. No database credential
is printed or automatically copied from your local development environment.

## 3. Dedicated GitHub Actions SSH key

On your local machine, create a NEW uniquely named key. Never overwrite personal keys:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/tiger_actions -C tiger-actions
```

Leave its passphrase empty for unattended CI; protect the private key and limit
its authorized server account. Add the contents of `~/.ssh/tiger_actions.pub` on
Vultr as one line to `/home/tiger/.ssh/authorized_keys`, prefixed with `restrict `:

```text
restrict ssh-ed25519 YOUR_NEW_PUBLIC_KEY tiger-actions
```

Then on Vultr:

```bash
sudo chown tiger:tiger /home/tiger/.ssh/authorized_keys
sudo chmod 600 /home/tiger/.ssh/authorized_keys
```

`restrict` disables forwarding and PTY for this CI key. Use your administrator
key, not this key, for browser tunnels. The tiger account can deploy code and
read staging secrets; treat write access to main and the staging environment
as trusted deployment access. Its sudo privileges only restart/stop tiger.service.

Obtain the host's Ed25519 public key through the trusted Vultr console:

```bash
cat /etc/ssh/ssh_host_ed25519_key.pub
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

Build a known-hosts line: `45.76.253.215 ssh-ed25519 <that public key>`.
Do not trust unverified `ssh-keyscan` output or disable host-key checking.

## 4. GitHub setup

In repository Settings → Environments create `staging`; restrict deployments to
main. Under that environment's secrets create:

| Secret | Value |
|---|---|
| VULTR_HOST | `45.76.253.215` |
| VULTR_USER | `tiger` |
| VULTR_SSH_KEY | Entire contents of the NEW `~/.ssh/tiger_actions` private key |
| VULTR_KNOWN_HOSTS | Verified known-hosts line from the previous section |

No database password belongs in GitHub; it stays on Vultr. Never commit the
private SSH key. The workflow uses GitHub's temporary read-only checkout token,
archives the exact pushed commit, and uploads it over verified SSH. No server
GitHub token or second repository deploy key is needed. Standard SSH port 22 is
assumed by CI. Protect main and review workflow/deployment-script changes.

## 5. Initial deployment using existing cloud records

Once server configuration and secrets are complete, push main, or open Actions →
Deploy Vultr staging → Run workflow on main. A push before bootstrap finishes
will fail safely; rerun it afterward. Normal deployments:

1. Install pinned dependencies and build in a new release directory.
2. Back up the database with pg_dump (failure stops deployment).
3. Run website schema initialization, foundation migrations with explicit target
   verification, and Alembic upgrade head. Never run seed/reset.
4. Atomically switch `current`, restart systemd and check database-backed health
   plus frontend HTML. On failure restore previous code and restart it.

Existing Tiger Cloud website records are used immediately. Do not seed them again.
For a deliberately empty, authorized demo service ONLY, an operator may use:

```bash
sudo -u tiger bash -c 'cd /var/www/tiger/current && .venv/bin/python scripts/vultr-database.py seed --confirm-fictional-demo'
```

This existing seed preserves an existing demo tenant and approvals; normal CI
never invokes it. The foundation's isolated-development seed/reset guards remain
unchanged; do not bypass them for the shared cloud database. V1 provisioning is
separate and unnecessary for the current website. No fixture files were removed.

## 6. Test and inspect logs

Before a domain/HTTPS, open a tunnel from your local machine using your ADMIN login:

```bash
ssh -L 8088:127.0.0.1:80 root@45.76.253.215
```

Open http://127.0.0.1:8088 and enter the staging `demo` login. Select Oak Lane →
Assign visit → Start. Check Work review against the existing cloud records. Public HTTP
returns 403 intentionally; the SSH tunnel encrypts your connection to Vultr.

On Vultr:

```bash
curl -fsS http://127.0.0.1:8081/api/health
curl -fsS http://127.0.0.1:8081/ >/dev/null
# Verify Nginx routing and password gate; curl prompts for the password:
curl -f -u demo http://127.0.0.1/api/health
sudo systemctl status tiger nginx
sudo journalctl -u tiger -n 100 --no-pager
sudo tail -n 100 /var/log/nginx/tiger.error.log
sudo tail -n 100 /var/log/nginx/tiger.access.log
# Read-only check against the configured Tiger Cloud database:
sudo -u tiger bash -c 'cd /var/www/tiger/current && .venv/bin/python scripts/vultr-database.py check'
sudo systemctl restart tiger.service
cat /var/www/tiger/current/RELEASE
```

Health returns only `{"status":"ok"}` or a generic 503, not connection details.

## 7. Manual redeployment and recovery

From a committed local checkout, using the dedicated deployment key and your
verified host entry in ~/.ssh/known_hosts:

```bash
sha=$(git rev-parse HEAD)
git archive --format=tar.gz --output="/tmp/$sha.tar.gz" "$sha"
scp -i ~/.ssh/tiger_actions "/tmp/$sha.tar.gz" "tiger@45.76.253.215:/var/www/tiger/incoming/$sha.tar.gz"
ssh -i ~/.ssh/tiger_actions tiger@45.76.253.215 "bash -s -- '$sha'" < scripts/deploy.sh
```

Deployment locking prevents simultaneous updates. Previous releases and backups
remain under `/var/www/tiger`; monitor disk usage and prune old releases manually
only after confirming they are not `current` or needed for rollback. Failed
builds leave the previous service untouched. Migration failure stops promotion.
Migrations across three tools are not one transaction: partial successful schema
changes remain. Code rollback NEVER downgrades/restores the database. Review
future migrations for backward compatibility with the previous release.

For manual code rollback, identify a known-good release directory, then as tiger:

```bash
cd /var/www/tiger
# Replace KNOWN_GOOD_RELEASE with an actual retained directory name.
ln -sfn /var/www/tiger/releases/KNOWN_GOOD_RELEASE current.next
mv -Tf current.next current
sudo /usr/bin/systemctl restart tiger.service
curl -fsS http://127.0.0.1:8081/api/health
```

Database backups contain private data; mode-restricted backups stay on the server.
Copy backups off-server through an approved secure channel. Test pg_restore into
a separate empty database first. Restoring over staging data is deliberately not
automated. Do not run --clean against the live database to fix a code error.

## 8. Add a real domain and HTTPS

Create an A record for your real domain pointing to 45.76.253.215. Do not add an
AAAA record unless IPv6 is configured. Set `server_name` in
`/etc/nginx/sites-available/tiger` to that domain, then:

```bash
sudo nginx -t && sudo systemctl reload nginx
sudo apt-get install -y certbot python3-certbot-nginx
# Replace YOUR_REAL_DOMAIN only after DNS resolves to this server:
sudo certbot --nginx -d YOUR_REAL_DOMAIN --redirect
```

The ACME challenge path is reachable without a staging password. After Certbot
success, remove ONLY the `allow 127.0.0.1;` and `deny all;` lines in the HTTPS
server block, retaining `auth_basic`. Ensure HTTP redirects to HTTPS. Add
`GOOB_PUBLIC_ORIGIN=https://YOUR_REAL_DOMAIN` (no trailing slash) to
`/etc/tiger/tiger.env`, then:

```bash
sudo nginx -t && sudo systemctl reload nginx
sudo systemctl restart tiger.service
sudo certbot renew --dry-run
curl -f -u demo https://YOUR_REAL_DOMAIN/api/health
```

The explicit public origin allows same-origin HTTPS POST requests through Nginx
without trusting arbitrary forwarded headers. No WebSockets are used by the
production website, so no upgrade configuration is needed.

## Troubleshooting and limits

- SSH failure: verify the host fingerprint, key line, owner/modes, port and Vultr
  firewall. Never fix it with StrictHostKeyChecking=no. Keep console access.
- Dependency/build failure: read Actions logs; check free disk/RAM and locked
  packages' Python/Node support. Locks are preserved, not silently regenerated.
- DB/TLS failure: check the Tiger Cloud service status, outbound connectivity,
  IP allowlist, password encoding, hostname and trusted CA. Never disable TLS.
- Backup version failure: client 18 supports server versions through 18. If your
  Tiger Cloud service is newer, explicitly update the client package/path before
  deploying. Backup failure prevents migrations and release promotion.
- Migration failure: inspect logs and backup; do not seed/reset. The scripts
  require both URLs to match TIGER_DB_HOST/PORT/NAME and reject v1 URL overrides.
- 502: check `journalctl -u tiger`, current symlink and port 8081.
- 403 over public HTTP: intentional until HTTPS setup above.
- 401: staging password required. Use the htpasswd command without -c to update.
- HTTPS POST 403: GOOB_PUBLIC_ORIGIN must match the browser's exact origin.
- Work review missing: confirm this is the intended existing Tiger Cloud service
  and website schema. Foundation/v1 rows do not populate this UI. Do not reset data.
- New service/Nginx template changes require an administrator to review/install
  them; routine CI cannot sudo-install configuration or change the firewall.
- Separate authenticated v1 is not launched by this website profile. Its existing
  deploy/backend documentation describes OIDC and container setup. Do not run
  its Caddy on the same 80/443 ports as Nginx. Connecting the UI to v1 is outside
  this infrastructure task.

References: [Nginx proxy headers](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)
, [PostgreSQL client packages](https://www.postgresql.org/download/linux/ubuntu/)
and [PostgreSQL TLS](https://www.postgresql.org/docs/current/ssl-tcp.html).

## Remote development with VS Code and Codex

The configured local SSH alias is `tiger-vultr`, using the non-root `tiger-dev`
account. Its checkout is `/home/tiger-dev/projects/Goob`, separate from the live
`/var/www/tiger/current` release. Open it from your local terminal:

```bash
code --new-window --remote ssh-remote+tiger-vultr /home/tiger-dev/projects/Goob
```

Remote SSH installs VS Code Server over SSH. Install `openai.chatgpt` in the
remote extension host, open the Codex sidebar, and sign in when requested.
Codex account sessions are not copied from your local machine. GitHub may also
ask you to sign in for Git operations from the remote editor.

Commit and push changes to main to trigger the workflow; saving a remote file
alone does not deploy it. The CI `tiger` account and its dedicated SSH key are
separate from your editor account. Repository-level Actions secrets also work
with the workflow's staging environment; GitHub passes them to the job. This
setup uses repository secrets. The server retains only the CI public key.

The first rollout still requires a trusted Tiger Cloud CA certificate at the
configured sslrootcert path. A self-signed certificate retrieved over an
unverified database connection must not be accepted without an independently
verified CA/fingerprint. No database TLS verification is bypassed.
