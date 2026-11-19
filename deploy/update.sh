#!/usr/bin/env bash
set -euo pipefail
if [[ "$(id -u)" -ne 0 ]]; then echo "Run as root." >&2; exit 1; fi
git -C /opt/abrehamrahi pull --ff-only origin main
/opt/abrehamrahi/.venv/bin/pip install -r /opt/abrehamrahi/requirements.txt
systemctl restart abrehamrahi-api
nginx -t
systemctl reload nginx
APP_PORT="$(sed -n 's/^APP_PORT=//p' /etc/abrehamrahi.env | tail -n 1)"
curl --fail --silent "http://127.0.0.1:$APP_PORT/health"

