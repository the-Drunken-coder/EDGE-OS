# ATLAS Edge Agent

A lightweight Python agent for Raspberry Pi Zero 2 W field devices that interfaces with ATLAS Command backend systems.

## Overview

The ATLAS Edge Agent provides:
- **Asset Registration**: Automatic registration with ATLAS Command backend
- **Telemetry Streaming**: Real-time sensor data collection and transmission
- **Command Processing**: Remote command execution via polling queues
- **Robust Network Handling**: Exponential backoff retry logic and rate limiting

## Hardware Requirements

- Raspberry Pi Zero 2 W (primary target)
- Raspberry Pi OS Lite (64-bit Bookworm) 
- Python 3.11+
- Network connectivity (Ethernet or Wi-Fi)

## Quick Start

### 1. On Your Development Machine

Clone and install for development:
```bash
git clone https://github.com/the-Drunken-coder/EDGE-OS.git edge-agent
cd edge-agent
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

### 2. On Raspberry Pi

**Option A: One-liner setup** (after SSH-ing into a fresh Pi OS install):
```bash
sudo apt update && sudo apt install -y git python3-venv && git clone https://github.com/the-Drunken-coder/EDGE-OS.git /opt/edge-agent && cd /opt/edge-agent && python3 -m venv venv && source venv/bin/activate && pip install -U pip wheel && pip install .
```

**Option B: Manual setup**:
```bash
# Install dependencies
sudo apt update && sudo apt install -y git python3-venv

# Clone repository
sudo git clone https://github.com/the-Drunken-coder/EDGE-OS.git /opt/edge-agent
cd /opt/edge-agent

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install package
pip install -U pip wheel
pip install .
```

### 3. Configuration

Create environment file `/etc/atlas-edge.env`:
```bash
sudo tee /etc/atlas-edge.env << EOF
ATLAS_URL=http://atlas-host.local:8000/api/v1
ASSET_ID=EDGE-0001
ASSET_NAME=Edge Agent Device
TELEMETRY_INTERVAL=5.0
COMMAND_POLL_INTERVAL=2.0
EOF

sudo chmod 600 /etc/atlas-edge.env
```

### 4. Run as Service

Create systemd service:
```bash
sudo tee /etc/systemd/system/atlas-edge.service << EOF
[Unit]
Description=ATLAS Edge Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=exec
User=pi
Group=pi
ExecStart=/opt/edge-agent/venv/bin/python -m atlas_edge.edge_stub
EnvironmentFile=/etc/atlas-edge.env
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable atlas-edge.service
sudo systemctl start atlas-edge.service
```

### 5. Monitor

Check service status and logs:
```bash
sudo systemctl status atlas-edge
sudo journalctl -u atlas-edge -f
```

## Configuration

The agent uses environment variables for configuration:

| Variable | Default | Description |
|----------|---------|-------------|
| `ATLAS_URL` | `http://atlas-host.local:8000/api/v1` | ATLAS Command API base URL |
| `ASSET_ID` | `EDGE-0001` | Unique asset identifier |
| `ASSET_NAME` | `Edge Agent Device` | Human-readable asset name |
| `ASSET_MODEL_ID` | `1` | Asset model ID from ATLAS catalog |
| `TELEMETRY_INTERVAL` | `5.0` | Seconds between telemetry posts |
| `COMMAND_POLL_INTERVAL` | `2.0` | Seconds between command polls |
| `REQUEST_TIMEOUT` | `5.0` | HTTP request timeout in seconds |
| `MAX_RETRIES` | `3` | Maximum retry attempts for failed requests |
| `BACKOFF_BASE` | `2.0` | Base multiplier for exponential backoff |
| `BEARER_TOKEN` | (none) | Bearer token for API authentication |

## Development

### Setup Development Environment

```bash
git clone https://github.com/the-Drunken-coder/EDGE-OS.git edge-agent
cd edge-agent
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

### Code Quality

```bash
# Format code
black src/ tests/
isort src/ tests/

# Type checking
mypy src/

# Run tests
pytest
```

### Project Structure

```
edge-agent/
├── src/
│   └── atlas_edge/
│       ├── __init__.py          # Package metadata
│       ├── config.py            # Configuration management
│       ├── client.py            # HTTP client with retry logic
│       ├── telemetry.py         # Telemetry data models
│       ├── registry.py          # Asset registration & commands
│       └── edge_stub.py         # Main agent implementation
├── provisioning/
│   ├── first_boot_stage1.sh     # Stage-1 provisioning script
│   ├── hello_edge.py            # Stage-1 heartbeat script
│   └── patch_firstrun_stage1.ps1 # SD card patching helper
├── pyproject.toml               # Python packaging config
├── README.md                    # This file
└── docs/                        # Documentation (MkDocs)
```

## API Integration

The agent integrates with ATLAS Command using these endpoints:

- **Asset Registration**: `POST /api/v1/assets`
- **Telemetry**: `POST /api/v1/assets/{asset_id}/telemetry`
- **Commands**: `GET /api/v1/assets/{asset_id}/commands`
- **Command ACK**: `DELETE /api/v1/assets/{asset_id}/commands/{index}`

See `ATLAS_API_GUIDE.md` and `EDGE_AGENT_INTEGRATION.md` for detailed API contracts.

## Troubleshooting

### Agent Won't Start
- Check network connectivity: `ping atlas-host.local`
- Verify Python version: `python3 --version` (should be ≥3.11)
- Check systemd logs: `sudo journalctl -u atlas-edge -f`

### Network Errors
- The agent includes robust retry logic with exponential backoff
- Check ATLAS Command backend availability
- Verify firewall settings allow outbound HTTP/HTTPS

### High CPU/Memory Usage
- Monitor telemetry interval (default 5s should be fine)
- Check for stuck command processing loops
- Consider reducing log verbosity in production

## Stage Development

### Stage 1: Boot Persistence ✅
- [x] Systemd service creation
- [x] Heartbeat logging every 10s
- [x] Boot survival verification

### Stage 2: Live Integration ✅
- [x] Asset registration with ATLAS Command
- [x] Mock telemetry generation and streaming
- [x] Command queue polling and acknowledgment
- [x] Graceful error handling and retry logic

### Stage 3: Real Sensors (Future)
- [ ] GPIO sensor integration
- [ ] I2C/SPI device drivers
- [ ] Camera module support
- [ ] Real GPS data collection

## License

MIT License - see LICENSE file for details. 