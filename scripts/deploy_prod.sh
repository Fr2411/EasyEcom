#!/usr/bin/env bash
set -euo pipefail

EC2_HOST="44.197.250.127"
EC2_USER="ec2-user"
SSH_KEY="$HOME/Downloads/EasyEcomKey.pem"

echo "[deploy] Backend production deploy script"
echo "[deploy] This deploys the rebuilt backend foundation currently running on EC2."
echo "[deploy] Frontend changes deploy separately via Amplify."
echo "[deploy] Connecting to EC2 and running deploy steps..."

ssh -T \
  -o IPQoS=throughput \
  -o IdentitiesOnly=yes \
  -i "$SSH_KEY" \
  "${EC2_USER}@${EC2_HOST}" <<'REMOTE'
set -euo pipefail

PROJECT_DIR="/home/ec2-user/EasyEcom"
VENV_DIR="$PROJECT_DIR/.venv"
SERVICE_NAME="easy-ecom.service"

echo "[remote] Entering project directory"
cd "$PROJECT_DIR"

echo "[remote] Pulling latest code from main"
git pull origin main

echo "[remote] Activating virtual environment"
source "$VENV_DIR/bin/activate"

echo "[remote] Installing dependencies"
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
REMOTE
