#!/usr/bin/env bash
set -euo pipefail

echo "[deploy] Backend production deploy script"
echo "[deploy] Reminder: use this for backend and/or database schema changes only."
echo "[deploy] Frontend changes deploy separately via Amplify after merge to main."

echo "[deploy] Connecting to EC2 and running deploy steps..."
ssh -o IPQoS=throughput -o IdentitiesOnly=yes -i ~/Downloads/EasyEcomKey.pem ec2-user@44.197.250.127 <<'EOF_REMOTE'
set -euo pipefail

echo "[remote] Entering project directory"
cd /home/ec2-user/EasyEcom

echo "[remote] Pulling latest main"
git pull origin main

echo "[remote] Activating virtual environment"
source /home/ec2-user/EasyEcom/.venv/bin/activate

echo "[remote] Installing package"
pip install -e .

echo "[remote] Running migrations"
alembic upgrade head

echo "[remote] Restarting service"
sudo systemctl restart easy-ecom.service

echo "[remote] Service status"
sudo systemctl status easy-ecom.service --no-pager
EOF_REMOTE

echo "[deploy] Production backend deploy completed successfully."
