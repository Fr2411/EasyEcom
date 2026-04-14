#!/usr/bin/env bash
set -euo pipefail

DEFAULT_EC2_HOST="44.197.250.127"
DEFAULT_EC2_USER="ec2-user"
DEFAULT_SSH_KEY="$HOME/Downloads/EasyEcomKey.pem"

EC2_HOST="${EC2_HOST:-$DEFAULT_EC2_HOST}"
EC2_USER="${EC2_USER:-$DEFAULT_EC2_USER}"
SSH_KEY_PATH="${SSH_KEY_PATH:-${SSH_KEY:-$DEFAULT_SSH_KEY}}"
DEPLOY_REF="${DEPLOY_REF:-${1:-HEAD}}"
DEPLOY_SHA="$(git rev-parse --verify "${DEPLOY_REF}^{commit}")"
ARTIFACT_PATH="$("$(dirname "$0")/build_backend_release.sh" "${DEPLOY_SHA}")"
REMOTE_ARTIFACT="/tmp/easyecom-backend-${DEPLOY_SHA}.tar.gz"

if [[ -z "${EC2_HOST}" ]]; then
  echo "[deploy] EC2_HOST is required"
  exit 1
fi

if [[ -z "${EC2_USER}" ]]; then
  echo "[deploy] EC2_USER is required"
  exit 1
fi

if [[ -z "${SSH_KEY_PATH}" ]]; then
  echo "[deploy] SSH_KEY_PATH is required"
  exit 1
fi

if [[ ! -f "${SSH_KEY_PATH}" ]]; then
  echo "[deploy] SSH key not found at ${SSH_KEY_PATH}"
  exit 1
fi

echo "[deploy] Backend production deploy script"
echo "[deploy] This deploys a backend-only release bundle to EC2."
echo "[deploy] Frontend changes deploy separately via Amplify."
echo "[deploy] Release SHA: ${DEPLOY_SHA}"
echo "[deploy] Building backend-only artifact: ${ARTIFACT_PATH}"

cleanup() {
  rm -f "${ARTIFACT_PATH}"
}
trap cleanup EXIT

echo "[deploy] Uploading backend artifact to EC2..."
scp \
  -o IPQoS=throughput \
  -o IdentitiesOnly=yes \
  -i "$SSH_KEY_PATH" \
  "${ARTIFACT_PATH}" \
  "${EC2_USER}@${EC2_HOST}:${REMOTE_ARTIFACT}"

echo "[deploy] Connecting to EC2 and applying release..."

ssh -T \
  -o IPQoS=throughput \
  -o IdentitiesOnly=yes \
  -i "$SSH_KEY_PATH" \
  "${EC2_USER}@${EC2_HOST}" \
  "DEPLOY_SHA='${DEPLOY_SHA}' REMOTE_ARTIFACT='${REMOTE_ARTIFACT}' bash -s" <<'REMOTE'
set -euo pipefail

PROJECT_DIR="/home/ec2-user/EasyEcom"
VENV_DIR="$PROJECT_DIR/.venv"
SERVICE_NAME="easy-ecom.service"
RELEASE_DIR="$(mktemp -d /tmp/easyecom-release-XXXXXX)"

cleanup() {
  rm -rf "$RELEASE_DIR"
  rm -f "$REMOTE_ARTIFACT"
}
trap cleanup EXIT

echo "[remote] Entering project directory"
cd "$PROJECT_DIR"

echo "[remote] Release SHA: $DEPLOY_SHA"
echo "[remote] Extracting backend artifact"
tar -xzf "$REMOTE_ARTIFACT" -C "$RELEASE_DIR"

echo "[remote] Syncing backend runtime files into project directory"
rsync -a --delete \
  --exclude '.env' \
  --exclude '.venv/' \
  --exclude '__pycache__/' \
  "$RELEASE_DIR"/ "$PROJECT_DIR"/

echo "[remote] Removing AppleDouble metadata artifacts from backend tree"
find "$PROJECT_DIR/easy_ecom" -name '._*' -type f -delete

echo "[remote] Recording deployed backend release"
printf '%s\n' "$DEPLOY_SHA" > "$PROJECT_DIR/CURRENT_BACKEND_RELEASE"

echo "[remote] Activating virtual environment"
if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

echo "[remote] Installing dependencies"
pip install --upgrade pip
pip install -e .

echo "[remote] Applying versioned database migrations"
python3 -m easy_ecom.scripts.migrate

echo "[remote] Seeding baseline data if needed"
python3 -m easy_ecom.scripts.init_data

echo "[remote] Restarting backend service"
sudo systemctl restart "$SERVICE_NAME"

echo "[remote] Service status"
sudo systemctl status "$SERVICE_NAME" --no-pager

echo "[remote] Deployment completed successfully"
echo "[remote] Next checks:"
echo "[remote]   1. Run scripts/auth_deploy_smoke.sh against the backend."
echo "[remote]   2. If a WhatsApp channel is configured, run channel diagnostics with SESSION_COOKIE and CHANNEL_ID."
echo "[remote]   3. Confirm frontend changes separately in Amplify before treating the UI as updated."
REMOTE
