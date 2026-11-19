#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/ostaddehdari/abrehamrahi.git"
APP_DIR="/opt/abrehamrahi"
DATA_DIR="/var/lib/abrehamrahi"
ENV_FILE="/etc/abrehamrahi.env"
SERVICE_USER="abrehamrahi"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root." >&2
  exit 1
fi

NEED_PACKAGES=0
for required_command in python3 git nginx openssl curl; do
  if ! command -v "$required_command" >/dev/null 2>&1; then
    NEED_PACKAGES=1
  fi
done

if [[ "$NEED_PACKAGES" -eq 0 ]]; then
  VENV_CHECK_DIR="$(mktemp -d /tmp/abrehamrahi-venv-check.XXXXXX)"
  if ! python3 -m venv "$VENV_CHECK_DIR" >/dev/null 2>&1; then
    NEED_PACKAGES=1
  fi
  rm -rf -- "$VENV_CHECK_DIR"
fi

if [[ "$NEED_PACKAGES" -eq 1 ]]; then
  if ! apt-get update; then
    echo "WARNING: apt-get update reported an error, usually from an unrelated third-party repository." >&2
    echo "Continuing with the successfully refreshed Ubuntu package indexes." >&2
  fi
  DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=900 install -y \
    python3 python3-venv python3-pip git nginx openssl curl ca-certificates
else
  echo "Required system packages and Python venv are already available; skipping apt."
fi

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  useradd --system --home-dir "$DATA_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
fi
install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 750 "$DATA_DIR"

if [[ -d "$APP_DIR/.git" ]]; then
  git -C "$APP_DIR" pull --ff-only origin main
else
  git clone --branch main "$REPO_URL" "$APP_DIR"
fi

python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

if [[ ! -f "$ENV_FILE" ]]; then
  ENCRYPTION_KEY="$($APP_DIR/.venv/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
  ADMIN_PASSWORD="$(openssl rand -base64 30 | tr -d '\n')"
  install -m 600 /dev/null "$ENV_FILE"
  {
    echo "ABR_API_ORIGIN=https://abrehamrahi.ir"
    echo "APP_ROOT_PATH=/abrehamrahi"
    echo "PUBLIC_BASE_URL=https://srun.ir/abrehamrahi"
    echo "APP_PORT=28765"
    echo "DATABASE_PATH=$DATA_DIR/abrehamrahi.sqlite3"
    echo "ENCRYPTION_KEY=$ENCRYPTION_KEY"
    echo "ADMIN_USERNAME=admin"
    echo "ADMIN_PASSWORD=$ADMIN_PASSWORD"
    echo "SESSION_TTL_SECONDS=2592000"
    echo "OTP_TTL_SECONDS=600"
    echo "MAX_UPLOAD_BYTES=5368709120"
    echo "UPSTREAM_TIMEOUT_SECONDS=60"
    echo "SIGNED_URL_TIMEOUT_SECONDS=300"
    echo "COOKIE_SECURE=true"
    echo "LOG_LEVEL=INFO"
  } > "$ENV_FILE"
  chmod 600 "$ENV_FILE"
fi

systemctl stop abrehamrahi-api 2>/dev/null || true

APP_PORT="$(sed -n 's/^APP_PORT=//p' "$ENV_FILE" | tail -n 1)"
if [[ ! "$APP_PORT" =~ ^[0-9]+$ ]] || (( APP_PORT < 1 || APP_PORT > 65535 )); then
  APP_PORT=28765
fi

port_is_available() {
  python3 - "$1" <<'PY'
import socket
import sys

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    try:
        sock.bind(("127.0.0.1", int(sys.argv[1])))
    except OSError:
        raise SystemExit(1)
PY
}

if ! port_is_available "$APP_PORT"; then
  PREVIOUS_PORT="$APP_PORT"
  APP_PORT=""
  for candidate in {28765..28775} 38765 48765; do
    if port_is_available "$candidate"; then
      APP_PORT="$candidate"
      break
    fi
  done
  if [[ -z "$APP_PORT" ]]; then
    APP_PORT="$(python3 - <<'PY'
import socket

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
)"
  fi
  sed -i -E "s/^APP_PORT=.*/APP_PORT=$APP_PORT/" "$ENV_FILE"
  echo "Port $PREVIOUS_PORT is used by another service; selected free port $APP_PORT."
fi

install -m 644 "$APP_DIR/deploy/abrehamrahi-api.service" /etc/systemd/system/abrehamrahi-api.service
install -d -m 755 /etc/nginx/snippets
sed "s/__APP_PORT__/$APP_PORT/g" "$APP_DIR/deploy/nginx-location.conf" \
  > /etc/nginx/snippets/abrehamrahi.conf
chmod 644 /etc/nginx/snippets/abrehamrahi.conf

NGINX_SITE_CONFIG="${NGINX_SITE_CONFIG:-}"
if [[ -z "$NGINX_SITE_CONFIG" ]]; then
  while IFS= read -r candidate; do
    if grep -Eq 'server_name[^;]*\bsrun\.ir\b' "$candidate"; then
      NGINX_SITE_CONFIG="$candidate"
      break
    fi
  done < <(find /etc/nginx/sites-enabled /etc/nginx/conf.d -maxdepth 1 -type f 2>/dev/null | sort)
fi
if [[ -z "$NGINX_SITE_CONFIG" ]]; then
  echo "Nginx server block for srun.ir was not found. Set NGINX_SITE_CONFIG and run this script again." >&2
  exit 1
fi
python3 "$APP_DIR/deploy/inject_nginx.py" "$NGINX_SITE_CONFIG"

systemctl daemon-reload
systemctl enable --now abrehamrahi-api
nginx -t
systemctl reload nginx
sleep 2
curl --fail --silent "http://127.0.0.1:$APP_PORT/health" >/dev/null

echo "Deployment completed."
echo "API docs: https://srun.ir/abrehamrahi/docs"
echo "Token page: https://srun.ir/abrehamrahi/admin/tokens"
echo "Read the generated admin password as root from: $ENV_FILE"

