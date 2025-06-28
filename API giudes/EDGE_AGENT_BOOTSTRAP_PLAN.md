# Edge-Agent – Pi Zero Bootstrap Plan

This document is **copy-ready**. Paste it into your new `edge-agent` project (e.g. as `README.md` or `PLAN.md`) and tick off items as you implement them.

---

## 0  Prerequisites (once per SD-card)

1. Flash **Raspberry Pi OS Lite 64-bit (Bookworm)**.  
2. Enable SSH & set hostname (e.g. `edge-0001`) in the imager or later via `raspi-config`.  
3. Verify the Pi can reach your LAN and resolve `atlas-host.local` (or use an IP address).

---

## Stage 1  – Auto-start `hello_edge.py` on every boot

**Goal:** prove that a script in `/opt/edge/` starts via `systemd` and logs to `journalctl`.

### 1. Create folder structure (on your laptop)
```
edge-agent/
├─ provisioning/
│   └─ first_boot.sh
└─ hello_edge.py
```

### 2. `hello_edge.py` – ultra-minimal heartbeat
```python
#!/usr/bin/env python3
from time import sleep, time
while True:
    print(f"[{time():.0f}] hello from edge-0001")
    sleep(10)
```

### 3. `provisioning/first_boot.sh` (Stage 1 version)
```bash
#!/bin/bash
set -e
apt-get update
apt-get install -y python3 python3-venv

mkdir -p /opt/edge
cp /boot/hello_edge.py /opt/edge/
chmod +x /opt/edge/hello_edge.py

cat >/etc/systemd/system/edge-hello.service <<'EOF'
[Unit]
Description=Edge Agent – hello demo
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/bin/python3 /opt/edge/hello_edge.py
Restart=on-failure
StandardOutput=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl enable edge-hello.service
```

### 4. Copy files onto the **/boot** partition before first boot
```bash
cp hello_edge.py provisioning/first_boot.sh /Volumes/boot/
```

### 5. Boot & verify
```bash
ssh pi@edge-0001.local
sudo journalctl -u edge-hello -f
```
You should see the "hello from edge-0001" line every 10 s.

✔ Stage 1 complete.

---

## Stage 2  – Pull real code from GitHub & push mock telemetry

### 1. `edge_stub.py` – simple telemetry generator
```python
# src/atlas_edge/edge_stub.py
import asyncio, httpx, os, random, json

BASE = os.getenv("ATLAS_URL", "http://atlas-host.local:8000/api/v1")
ASSET_ID = os.getenv("ASSET_ID", "EDGE-0001")

async def bootstrap(client):
    payload = {"id": ASSET_ID, "name": "Edge Test Unit", "asset_model_id": 1}
    await client.post(f"{BASE}/assets", json=payload)

async def send_telemetry(client):
    lat0, lon0 = 42.0, -71.0  # base point
    while True:
        lat = lat0 + random.uniform(-0.0005, 0.0005)
        lon = lon0 + random.uniform(-0.0005, 0.0005)
        body = {
            "latitude": lat,
            "longitude": lon,
            "altitude": 50,
            "status": "active",
        }
        await client.post(f"{BASE}/assets/{ASSET_ID}/telemetry", json=body)
        print("posted:", json.dumps(body))
        await asyncio.sleep(5)

async def main():
    async with httpx.AsyncClient(timeout=5) as c:
        await bootstrap(c)
        await send_telemetry(c)

if __name__ == "__main__":
    asyncio.run(main())
```

### 2. Minimal project layout for the **edge-agent** repo
```
edge-agent/
├─ src/
│   └─ atlas_edge/
│        └─ edge_stub.py
├─ pyproject.toml
└─ README.md
```

### 3. `pyproject.toml`
```toml
[build-system]
requires       = ["setuptools>=61", "wheel"]
build-backend  = "setuptools.build_meta"

[project]
name            = "atlas-edge"
version         = "0.0.1"
dependencies    = ["httpx>=0.25", "pydantic>=2.5"]

[tool.setuptools.package-dir]
"" = "src"

[project.scripts]
atlas-edge = "atlas_edge.edge_stub:main"
```

### 4. Update `provisioning/first_boot.sh` for Stage 2
```bash
#!/bin/bash
set -e
apt-get update
apt-get install -y git python3-venv

git clone --depth 1 git@github.com:your-org/edge-agent.git /opt/edge-agent
cd /opt/edge-agent
python3 -m venv venv
source venv/bin/activate
pip install -U pip wheel
pip install .

cat >/etc/systemd/system/atlas-edge.service <<'EOF'
[Unit]
Description=Atlas Edge Agent
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=/opt/edge-agent
ExecStart=/opt/edge-agent/venv/bin/python -m atlas_edge.edge_stub
Environment=ATLAS_URL=http://atlas-host.local:8000/api/v1
Environment=ASSET_ID=EDGE-0001
Restart=on-failure
StandardOutput=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl enable atlas-edge.service
```

### 5. Deploy & test
1. Copy the new `first_boot.sh` to **/boot** or run it manually via SSH.  
2. Verify asset creation & telemetry:
   ```bash
   curl http://atlas-host.local:8000/api/v1/assets
   curl http://atlas-host.local:8000/api/v1/assets/EDGE-0001/telemetry/latest
   ```

✔ Stage 2 complete – you now have a Pi Zero that registers with ATLAS and sends mock telemetry.

---

### Next milestones (for later)
1. Swap `edge_stub.py` for a MAVLink → schema converter.  
2. Implement robust retry/back-pressure per `EDGE_AGENT_INTEGRATION.md`.  
3. Introduce plug-in architecture and move vision processing to Pi 5.

---

*Happy hacking!* 