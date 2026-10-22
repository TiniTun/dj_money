#!/bin/sh
# One-time VM setup (run as root on a fresh Debian 12 VM): swap, Docker, app checkout, backup cron.
set -eu

APP_DIR=/opt/dj_money

# e2-small has 2 GB RAM; swap absorbs Celery/gunicorn spikes
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# Docker Engine + Compose plugin from Docker's apt repository
apt-get update
apt-get install -y ca-certificates curl git
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

[ -d "$APP_DIR" ] || git clone https://github.com/TiniTun/dj_money.git "$APP_DIR"

echo "30 3 * * * root $APP_DIR/deploy/gcp/backup.sh >> /var/log/dj-money-backup.log 2>&1" > /etc/cron.d/dj-money-backup
timedatectl set-timezone Australia/Brisbane
