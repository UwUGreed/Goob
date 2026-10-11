#!/usr/bin/env bash
set -euo pipefail
umask 027
[[ $(id -un) == tiger ]] || { echo "Run as tiger, not root." >&2; exit 1; }
sha=${1:?Usage: deploy.sh FULL_COMMIT_SHA}
[[ $sha =~ ^[0-9a-f]{40}$ ]] || { echo "Invalid commit SHA" >&2; exit 1; }
base=/var/www/tiger
cd "$base"
exec 9>"$base/deploy.lock"
flock -n 9 || { echo "Another deployment is active." >&2; exit 1; }
archive="$base/incoming/$sha.tar.gz"
[[ -f $archive ]] || { echo "Missing release archive." >&2; exit 1; }
release=$(mktemp -d "$base/releases/$sha.XXXXXXXX")
previous=$(readlink -f "$base/current" || true)
switched=false
rollback() {
    code=$?
    trap - EXIT
    if (( code != 0 )) && $switched; then
        echo "Deployment failed; restoring previous code (database is NOT rolled back)." >&2
        if [[ -n $previous && -d $previous ]]; then
            ln -sfn "$previous" "$base/current.next"
            mv -Tf "$base/current.next" "$base/current"
            if sudo /usr/bin/systemctl restart tiger.service; then
                restored=false
                for retry in {1..10}; do
                    if curl --fail --silent --max-time 3 http://127.0.0.1:8081/api/health >/dev/null; then
                        restored=true
                        break
                    fi
                    sleep 2
                done
                $restored || echo "ROLLBACK HEALTH CHECK FAILED; inspect journalctl -u tiger" >&2
            else
                echo "ROLLBACK RESTART FAILED" >&2
            fi
        else
            sudo /usr/bin/systemctl stop tiger.service || true
            rm -f "$base/current"
        fi
    fi
    exit "$code"
}
trap rollback EXIT
tar -xzf "$archive" --no-same-owner -C "$release"
cd "$release"
echo "Installing and building $sha in isolated release directory..."
python3 -m venv .venv
.venv/bin/pip install --disable-pip-version-check -r requirements.txt
npm ci --prefix goob-dispatch
npm run build --prefix goob-dispatch
# Parse dotenv as data; never source shell commands from an environment file.
.venv/bin/python scripts/vultr-database.py migrate "$base/backups/$sha-$(date -u +%Y%m%dT%H%M%SZ).dump"
printf '%s\n' "$sha" > RELEASE
ln -sfn "$release" "$base/current.next"
mv -Tf "$base/current.next" "$base/current"
switched=true
sudo /usr/bin/systemctl restart tiger.service
for attempt in {1..20}; do
    if curl --fail --silent --max-time 3 http://127.0.0.1:8081/api/health >/dev/null && \
       curl --fail --silent --max-time 3 http://127.0.0.1:8081/ | grep -q '<div id="root">'; then
        echo "Release $sha is healthy. Previous release retained: $previous"
        exit 0
    fi
    sleep 2
done
echo "Health check failed." >&2
exit 1
