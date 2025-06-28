#!/bin/bash
# ATLAS Edge Agent - Raspberry Pi Setup Script
# 
# This script installs and configures the ATLAS Edge Agent on a Raspberry Pi.
# Run this on a fresh Raspberry Pi OS Lite install after SSH-ing in.
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/the-Drunken-coder/EDGE-OS/main/provisioning/setup_pi.sh | bash
#   Or: wget -qO- https://raw.githubusercontent.com/the-Drunken-coder/EDGE-OS/main/provisioning/setup_pi.sh | bash
#   Or: Copy and paste the one-liner below

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/the-Drunken-coder/EDGE-OS.git}"
INSTALL_DIR="${INSTALL_DIR:-/opt/edge-agent}"
ASSET_ID="${ASSET_ID:-EDGE-$(hostname)}"

log() {
    echo "[setup] $*"
}

log "Starting ATLAS Edge Agent setup on $(hostname)"

# Update system and install dependencies
log "Installing system dependencies"
sudo apt update && sudo apt install -y git python3-venv

# Clone repository
log "Cloning repository to $INSTALL_DIR"
sudo rm -rf "$INSTALL_DIR"
sudo git clone "$REPO_URL" "$INSTALL_DIR"
sudo chown -R $USER:$USER "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Create virtual environment
log "Setting up Python virtual environment"
python3 -m venv venv
source venv/bin/activate

# Install package
log "Installing ATLAS Edge Agent package"
pip install -U pip wheel
pip install .

# Create configuration
log "Creating configuration file"
sudo tee /etc/atlas-edge.env << EOF
ATLAS_URL=http://atlas-host.local:8000/api/v1
ASSET_ID=$ASSET_ID
ASSET_NAME=Edge Agent Device ($ASSET_ID)
TELEMETRY_INTERVAL=5.0
COMMAND_POLL_INTERVAL=2.0
EOF

sudo chmod 600 /etc/atlas-edge.env

# Create systemd service
log "Creating systemd service"
sudo tee /etc/systemd/system/atlas-edge.service << EOF
[Unit]
Description=ATLAS Edge Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=exec
User=$USER
Group=$USER
ExecStart=$INSTALL_DIR/venv/bin/python -m atlas_edge.edge_stub
EnvironmentFile=/etc/atlas-edge.env
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
log "Enabling and starting service"
sudo systemctl daemon-reload
sudo systemctl enable atlas-edge.service
sudo systemctl start atlas-edge.service

# Show status
log "Setup complete! Service status:"
sudo systemctl status atlas-edge.service --no-pager

log "To monitor logs: sudo journalctl -u atlas-edge -f"
log "To restart: sudo systemctl restart atlas-edge"
log "Configuration: /etc/atlas-edge.env" 