#!/usr/bin/env bash
set -euo pipefail
if [[ "$(id -u)" -ne 0 ]]; then echo "Run as root." >&2; exit 1; fi
git -C /opt/abrehamrahi pull --ff-only origin main
/opt/abrehamrahi/.venv/bin/pip install -r /opt/abrehamrahi/requirements.txt
systemctl restart abrehamrahi-api
nginx -t
systemctl reload nginx
curl --fail --silent http://127.0.0.1:8765/health

