#!/bin/bash
# ATLAS Edge Agent Setup Script for Raspberry Pi
# 
# Interactive usage (default):
#   curl -sSL https://raw.githubusercontent.com/the-Drunken-coder/EDGE-OS/main/provisioning/setup_pi.sh | bash
#   wget https://raw.githubusercontent.com/the-Drunken-coder/EDGE-OS/main/provisioning/setup_pi.sh && chmod +x setup_pi.sh && ./setup_pi.sh
#
# Non-interactive usage with environment variables:
#   export NON_INTERACTIVE=true
#   export ATLAS_URL="http://your-server:8000/api/v1/"
#   export ASSET_ID="DRONE-001"
#   export ASSET_NAME="Field Drone Alpha"
#   export ASSET_MODEL_ID="2"
#   curl -sSL https://raw.githubusercontent.com/the-Drunken-coder/EDGE-OS/main/provisioning/setup_pi.sh | bash

set -e

echo "=============================================="
echo "    ATLAS Edge Agent Setup"
echo "=============================================="
echo ""

# Configuration defaults
REPO_URL="https://github.com/the-Drunken-coder/EDGE-OS"
INSTALL_DIR="/opt/edge-agent"
DEFAULT_ATLAS_URL="http://192.168.1.132:8000/api/v1/"
DEFAULT_ASSET_ID="EDGE-PI-$(hostname | tr '[:lower:]' '[:upper:]')"
DEFAULT_ASSET_NAME="Edge Agent on $(hostname)"

# Check for non-interactive mode via environment variable, otherwise default to interactive
if [ "${NON_INTERACTIVE:-false}" = "true" ]; then
    INTERACTIVE=false
    echo "Running in non-interactive mode. Using environment variables or defaults."
    echo ""
else
    INTERACTIVE=true
    echo "🤖 Welcome to ATLAS Edge Agent setup!"
    echo ""
    echo "This script will configure and install the edge agent on your Raspberry Pi."
    echo "You'll be prompted for configuration details."
    echo ""
    echo "💡 Tip: For automated installs, set NON_INTERACTIVE=true"
    echo ""
fi

# Function to prompt for input with fallback to environment variables
prompt_or_env() {
    local prompt_text="$1"
    local env_var="$2"
    local default_value="$3"
    local result=""
    
    if [ "$INTERACTIVE" = true ]; then
        echo "$prompt_text"
        if [ -n "$default_value" ]; then
            echo "Default: $default_value"
        fi
        # Handle case where stdin is not a TTY (like curl | bash)
        if [ ! -t 0 ]; then
            read -p "> " result </dev/tty
        else
            read -p "> " result
        fi
        if [ -z "$result" ]; then
            result="$default_value"
        fi
    else
        # Use environment variable or default
        result="${!env_var:-$default_value}"
    fi
    
    echo "$result"
}

# Set static ATLAS URL
ATLAS_URL="$DEFAULT_ATLAS_URL"
if [ "$INTERACTIVE" = true ]; then
    echo "📡 ATLAS Command API Configuration"
    echo "Using: $ATLAS_URL"
    echo ""
fi

# Validate URL format
if [[ ! $ATLAS_URL =~ ^https?:// ]]; then
    echo "❌ Invalid URL format. URL must start with http:// or https://"
    exit 1
fi

# Get Asset ID
if [ "$INTERACTIVE" = true ]; then
    echo ""
    echo "🏷️  Asset Identification"
fi
ASSET_ID=$(prompt_or_env "Enter a unique identifier for this edge device:" "ASSET_ID" "$DEFAULT_ASSET_ID")

# Get Asset Name
ASSET_NAME=$(prompt_or_env "Enter a human-readable name for this device:" "ASSET_NAME" "$DEFAULT_ASSET_NAME")

# Get Asset Model
if [ "$INTERACTIVE" = true ]; then
    echo ""
    echo "📋 Asset Model Configuration"
    echo "Select the asset model type:"
    echo "1) Security Camera (ID: 1)"
    echo "2) Drone (ID: 2)"  
    echo "3) Sensor Station (ID: 3)"
    echo "4) Custom (enter ID manually)"
    if [ ! -t 0 ]; then
        read -p "Select option [1-4]: " MODEL_CHOICE </dev/tty
    else
        read -p "Select option [1-4]: " MODEL_CHOICE
    fi
    
    case $MODEL_CHOICE in
        1)
            ASSET_MODEL_ID=1
            MODEL_NAME="Security Camera"
            ;;
        2)
            ASSET_MODEL_ID=2
            MODEL_NAME="Drone"
            ;;
        3)
            ASSET_MODEL_ID=3
            MODEL_NAME="Sensor Station"
            ;;
        4)
            echo "Enter custom asset model ID:"
            if [ ! -t 0 ]; then
                read -p "> " ASSET_MODEL_ID </dev/tty
            else
                read -p "> " ASSET_MODEL_ID
            fi
            MODEL_NAME="Custom Model"
            ;;
        *)
            echo "Invalid selection. Using default (Security Camera)."
            ASSET_MODEL_ID=1
            MODEL_NAME="Security Camera"
            ;;
    esac
else
    # Non-interactive: use environment variable or default
    ASSET_MODEL_ID="${ASSET_MODEL_ID:-1}"
    case $ASSET_MODEL_ID in
        1) MODEL_NAME="Security Camera" ;;
        2) MODEL_NAME="Drone" ;;
        3) MODEL_NAME="Sensor Station" ;;
        *) MODEL_NAME="Custom Model" ;;
    esac
fi

# Get timing configuration
if [ "$INTERACTIVE" = true ]; then
    echo ""
    echo "⏱️  Timing Configuration"
fi
TELEMETRY_INTERVAL=$(prompt_or_env "Enter telemetry interval in seconds (how often to send sensor data):" "TELEMETRY_INTERVAL" "5.0")
COMMAND_POLL_INTERVAL=$(prompt_or_env "Enter command poll interval in seconds (how often to check for commands):" "COMMAND_POLL_INTERVAL" "2.0")

echo ""
echo "📝 Configuration Summary"
echo "=============================================="
echo "ATLAS URL:           $ATLAS_URL"
echo "Asset ID:            $ASSET_ID"
echo "Asset Name:          $ASSET_NAME"
echo "Asset Model:         $MODEL_NAME (ID: $ASSET_MODEL_ID)"
echo "Telemetry Interval:  ${TELEMETRY_INTERVAL}s"
echo "Command Interval:    ${COMMAND_POLL_INTERVAL}s"
echo "Install Directory:   $INSTALL_DIR"
echo "=============================================="
echo ""

# Confirmation prompt (only in interactive mode)
if [ "$INTERACTIVE" = true ]; then
    if [ ! -t 0 ]; then
        read -p "Continue with this configuration? [Y/n]: " CONFIRM </dev/tty
    else
        read -p "Continue with this configuration? [Y/n]: " CONFIRM
    fi
    case $CONFIRM in
        [nN][oO]|[nN])
            echo "Setup cancelled."
            exit 0
            ;;
        *)
            echo "Proceeding with installation..."
            ;;
    esac
else
    echo "Proceeding with installation..."
fi

echo ""
echo "🔧 Starting installation..."

# Update system
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install dependencies
echo "📦 Installing dependencies..."
sudo apt install -y python3 python3-pip python3-venv git curl

# Create installation directory
echo "📁 Creating installation directory..."
sudo mkdir -p $INSTALL_DIR
sudo chown $(whoami):$(id -gn) $INSTALL_DIR

# Clone repository
echo "📥 Cloning repository..."
cd $INSTALL_DIR
git clone $REPO_URL.git .

# Create and activate virtual environment
echo "🐍 Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -e .

# Create systemd service
echo "⚙️  Creating systemd service..."
sudo tee /etc/systemd/system/edge-agent.service > /dev/null << EOF
[Unit]
Description=ATLAS Edge Agent ($ASSET_ID)
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
Environment="ASSET_MODEL_ID=$ASSET_MODEL_ID"
Environment="TELEMETRY_INTERVAL=$TELEMETRY_INTERVAL"
Environment="COMMAND_POLL_INTERVAL=$COMMAND_POLL_INTERVAL"
ExecStart=$INSTALL_DIR/venv/bin/python3 -m atlas_edge.edge_stub
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Create configuration backup file
echo "💾 Creating configuration backup..."
sudo tee /etc/atlas-edge.conf > /dev/null << EOF
# ATLAS Edge Agent Configuration
# Generated on $(date)

ATLAS_URL=$ATLAS_URL
ASSET_ID=$ASSET_ID
ASSET_NAME=$ASSET_NAME
ASSET_MODEL_ID=$ASSET_MODEL_ID
TELEMETRY_INTERVAL=$TELEMETRY_INTERVAL
COMMAND_POLL_INTERVAL=$COMMAND_POLL_INTERVAL
INSTALL_DIR=$INSTALL_DIR
EOF

# Enable and start service
echo "🚀 Enabling and starting edge agent service..."
sudo systemctl daemon-reload
sudo systemctl enable edge-agent
sudo systemctl start edge-agent

# Wait a moment for service to start
sleep 2

echo ""
echo "✅ Setup Complete!"
echo "=============================================="
echo ""

# Show service status
echo "📊 Service Status:"
sudo systemctl status edge-agent --no-pager -l

echo ""
echo "📋 Useful Commands:"
echo "  View live logs:    sudo journalctl -u edge-agent -f"
echo "  Check status:      sudo systemctl status edge-agent"
echo "  Restart service:   sudo systemctl restart edge-agent"
echo "  Stop service:      sudo systemctl stop edge-agent"
echo "  View config:       cat /etc/atlas-edge.conf"
echo ""

echo "🎉 Your ATLAS Edge Agent is now running!"
echo "   Asset ID: $ASSET_ID"
echo "   Connecting to: $ATLAS_URL"
echo ""
echo "The agent will automatically start on boot and reconnect if the network goes down." 