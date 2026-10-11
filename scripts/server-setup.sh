#!/usr/bin/env bash
set -euo pipefail
[[ $EUID == 0 ]] || { echo "Run as root on the Vultr server." >&2; exit 1; }
source /etc/os-release
[[ $ID == ubuntu && $VERSION_ID == 24.04 ]] || { echo "Requires Ubuntu 24.04." >&2; exit 1; }
ROOT=$(cd "$(dirname "$0")/.." && pwd)
echo "Installing repository runtimes and server tools..."
apt-get update
apt-get install -y git curl ca-certificates nginx python3 python3-venv xz-utils ufw openssl apache2-utils sudo
# Tailwind's native build dependency requires modern Node; Ubuntu's Node 18 is too old.
node_tmp=$(mktemp -d)
curl --fail --silent --show-error https://nodejs.org/dist/latest-v22.x/SHASUMS256.txt -o "$node_tmp/SHASUMS256.txt"
node_archive=$(awk '$2 ~ /^node-v22\..*-linux-x64.tar.xz$/ {print $2}' "$node_tmp/SHASUMS256.txt")
[[ $node_archive =~ ^node-v22\.[0-9]+\.[0-9]+-linux-x64.tar.xz$ ]] || { echo "Unexpected Node archive" >&2; exit 1; }
curl --fail --silent --show-error "https://nodejs.org/dist/latest-v22.x/$node_archive" -o "$node_tmp/$node_archive"
(cd "$node_tmp" && grep "  $node_archive$" SHASUMS256.txt | sha256sum -c -)
install -d /opt/tiger-node22
tar -xJf "$node_tmp/$node_archive" --strip-components=1 -C /opt/tiger-node22
for tool in node npm npx; do ln -sfn "/opt/tiger-node22/bin/$tool" "/usr/local/bin/$tool"; done
rm -rf "$node_tmp"
id tiger >/dev/null 2>&1 || useradd --create-home --shell /bin/bash tiger
install -d -o tiger -g tiger -m 0750 /var/www/tiger /var/www/tiger/releases /var/www/tiger/incoming /var/www/tiger/backups
install -d -o tiger -g tiger -m 0700 /home/tiger/.ssh
install -d -o root -g tiger -m 0750 /etc/tiger
install -d -m 0755 /var/www/letsencrypt
# Client tools only, for cloud backups; never install/start a database server.
install -d /usr/share/postgresql-common/pgdg
curl --fail --silent --show-error https://www.postgresql.org/media/keys/ACCC4CF8.asc \
    -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc
cat > /etc/apt/sources.list.d/pgdg.sources <<'EOF'
Types: deb
URIs: https://apt.postgresql.org/pub/repos/apt
Suites: noble-pgdg
Components: main
Signed-By: /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc
EOF
apt-get update
apt-get install -y postgresql-client-18
systemctl enable --now nginx
if [[ ! -f /etc/tiger/tiger.env ]]; then
    install -o root -g tiger -m 0640 "$ROOT/deploy/vultr/tiger.env.example" /etc/tiger/tiger.env
fi
install -m 0644 "$ROOT/deploy/systemd/tiger.service" /etc/systemd/system/tiger.service
# Only these fixed service operations are granted, never arbitrary sudo commands.
echo 'tiger ALL=(root) NOPASSWD: /usr/bin/systemctl restart tiger.service, /usr/bin/systemctl stop tiger.service' > /etc/sudoers.d/tiger
chmod 0440 /etc/sudoers.d/tiger
visudo -cf /etc/sudoers.d/tiger
systemctl daemon-reload
systemctl enable tiger.service
if [[ ! -e /etc/nginx/sites-available/tiger ]]; then
    install -m 0644 "$ROOT/deploy/nginx/tiger.conf" /etc/nginx/sites-available/tiger
fi
ln -sfn /etc/nginx/sites-available/tiger /etc/nginx/sites-enabled/tiger
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx
# Preserve SSH on the session port as well as standard SSH; never change sshd auth.
ufw allow 22/tcp
if [[ -n ${SSH_CONNECTION:-} ]]; then
    read -r _ _ _ ssh_port <<< "$SSH_CONNECTION"
    [[ $ssh_port =~ ^[0-9]+$ ]] && ufw allow "$ssh_port/tcp"
fi
ufw allow 80/tcp
ufw allow 443/tcp
ufw default deny incoming
ufw default allow outgoing
ufw --force enable
echo "Prepared. Follow DEPLOYMENT.md to configure Tiger Cloud credentials, staging password and SSH key, then deploy."
echo "No database was seeded. Review ufw status for any pre-existing broad allow rules."
