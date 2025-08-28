#!/bin/bash
set -euo pipefail

# Pick the non-root user when running with sudo, otherwise fall back to $USER
TARGET_USER="${SUDO_USER:-$USER}"

echo "[1/8] Updating packages..."
sudo dnf update -y

echo "[2/8] Installing Docker engine..."
sudo dnf install -y docker

echo "[3/8] Enabling and starting Docker..."
sudo systemctl enable docker
sudo systemctl start docker

echo "[4/8] Adding ${TARGET_USER} to docker group (will take effect next login)..."
sudo usermod -aG docker "${TARGET_USER}"

echo "[5/8] Installing Docker Compose plugin..."
# Standard plugin location on Amazon Linux 2023
sudo mkdir -p /usr/libexec/docker/cli-plugins
sudo curl -sSL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m)" \
  -o /usr/libexec/docker/cli-plugins/docker-compose
sudo chmod +x /usr/libexec/docker/cli-plugins/docker-compose

echo "[6/8] Installing Nitro Enclaves CLI and jq..."
sudo dnf install -y aws-nitro-enclaves-cli aws-nitro-enclaves-cli-devel jq

echo "[7/8] Adding ${TARGET_USER} to 'ne' group (will take effect next login)..."
sudo usermod -aG ne "${TARGET_USER}"

echo "[8/8] Verifying installations..."
# These run as root; they don't require your session to have the new groups yet.
sudo docker --version
sudo docker compose version || true  # print if available; don't fail the script if not
sudo nitro-cli --version

echo
echo "✅ Setup complete."
echo "Please log out and back in (or open a new SSH session) so your user picks up group changes:"
echo "    - docker"
echo "    - ne"
echo
echo "After re-login, you can test without sudo:"
echo "  docker ps"
echo "  docker compose version"
echo "  nitro-cli --version"
