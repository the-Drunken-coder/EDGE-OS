#!/bin/bash
# ATLAS Edge Agent Setup Script for Raspberry Pi
# Run with: curl -sSL https://raw.githubusercontent.com/the-Drunken-coder/EDGE-OS/main/provisioning/setup_pi.sh | bash

set -e

echo "=== ATLAS Edge Agent Setup ==="
echo "Setting up edge agent on $(hostname)"

# Configuration
REPO_URL="https://github.com/the-Drunken-coder/EDGE-OS"
INSTALL_DIR="/opt/edge-agent"
ATLAS_URL="${ATLAS_URL:-http://192.168.1.132:8000/api/v1/}"
ASSET_ID="${ASSET_ID:-EDGE-PI-$(hostname | tr '[:lower:]' '[:upper:]')}"
ASSET_NAME="${ASSET_NAME:-Raspberry Pi Edge Agent}"

echo "Configuration:"
echo "  Repository: $REPO_URL"
echo "  Install Directory: $INSTALL_DIR"
echo "  ATLAS URL: $ATLAS_URL"
echo "  Asset ID: $ASSET_ID"
echo "  Asset Name: $ASSET_NAME"

# Update system
echo "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install dependencies
echo "Installing dependencies..."
sudo apt install -y python3 python3-pip python3-venv git curl

# Create installation directory
echo "Creating installation directory..."
sudo mkdir -p $INSTALL_DIR
sudo chown $(whoami):$(id -gn) $INSTALL_DIR

# Clone repository
echo "Cloning repository..."
cd $INSTALL_DIR
git clone $REPO_URL.git .

# Create and activate virtual environment
echo "Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -e .

# Create systemd service
echo "Creating systemd service..."
sudo tee /etc/systemd/system/edge-agent.service > /dev/null << EOF
[Unit]
Description=ATLAS Edge Agent
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=$(whoami)
Group=$(id -gn)
WorkingDirectory=$INSTALL_DIR
Environment="ATLAS_URL=$ATLAS_URL"
Environment="ASSET_ID=$ASSET_ID"
Environment="ASSET_NAME=$ASSET_NAME"
Environment="ASSET_MODEL_ID=1"
Environment="TELEMETRY_INTERVAL=5.0"
Environment="COMMAND_POLL_INTERVAL=2.0"
ExecStart=$INSTALL_DIR/venv/bin/python3 -m atlas_edge.edge_stub
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
echo "Enabling and starting edge agent service..."
sudo systemctl daemon-reload
sudo systemctl enable edge-agent
sudo systemctl start edge-agent

# Show status
echo "=== Setup Complete ==="
echo "Service status:"
sudo systemctl status edge-agent --no-pager

echo ""
echo "To view logs: sudo journalctl -u edge-agent -f"
echo "To restart: sudo systemctl restart edge-agent"
echo "To stop: sudo systemctl stop edge-agent"

echo ""
echo "Edge agent is now running with:"
echo "  Asset ID: $ASSET_ID"
echo "  ATLAS URL: $ATLAS_URL"
echo "  Install Directory: $INSTALL_DIR" 