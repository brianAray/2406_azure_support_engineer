#!/usr/bin/env bash
set -e

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y docker.io docker-compose-v2 docker-buildx git
systemctl enable --now docker

rm -rf /home/azureuser/2406_azure_support_engineer
git clone https://github.com/brianAray/2406_azure_support_engineer.git /home/azureuser/2406_azure_support_engineer

cd /home/azureuser/2406_azure_support_engineer/examples/week_1/friday/fast_api_demo

docker compose up -d --build

docker compose ps
sleep 5
curl -I http://localhost:8081/health || curl -I http://localhost:8081/

#Fix folder permissions
chown -R azureuser:azureuser /home/azureuser/2406_azure_support_engineer