# ATLAS Command – Master API Guide

> Version tracked: `api/v1` (FastAPI backend).  
> All endpoints are JSON-only and support standard HTTP verbs.  
> Base path in development: **`http://localhost:8000/api/v1`**

---

## Conventions & Notes

• **Content-Type**: `application/json` for request/response bodies.  
• **Asset IDs are strings** – can be numeric (`"1"`) or custom (`"DRONE-001"`).  
• Error responses include a unique `error_code` field (e.g. `ASSET_NOT_FOUND`).  
• Pagination params: `skip` (offset) & `limit` (max 1000 unless stated).  
• All times are UTC ISO-8601.

---

## 1. System & Health

| Method | Path | Description |
|--------|---------------------------|-------------|
| GET | `/` | System banner & version |
| GET | `/health` | Lightweight liveness probe |
| GET | `/health/database` | PostgreSQL connectivity |
| GET | `/health/redis` | Redis connectivity |
| GET | `/health/docker` | Docker containers health summary |
| GET | `/health/all` | Combined health report |
| GET | `/system/errors` | Recent error logs (development only) |


## 2. Assets

| Method | Path | Description |
|--------|-----------------------------|-------------|
| GET | `/assets` | List assets (`skip`, `limit`) |
| POST | `/assets` | Create asset |
| GET | `/assets/{asset_id}` | Retrieve asset |
| PUT | `/assets/{asset_id}` | Update asset |
| DELETE | `/assets/{asset_id}` | Delete asset |
| GET | `/assets/catalog` | Reference data – asset models & sensors |

### 2.1  Sample – create asset | curl
```bash
curl -X POST $BASE/assets \
     -H "Content-Type: application/json" \
     -d '{
           "id": "DRONE-001",            # optional; generated if omitted
           "name": "Quadcopter Alpha",
           "asset_model_id": 1             # see /assets/catalog
         }'
```


## 3. Telemetry (per-asset)
Base prefix: `/assets/{asset_id}/telemetry`

| Method | Path | Body | Description |
|--------|------|------|-------------|
| GET | `/` | – | List telemetry records (optional `start_time`,`end_time`,`limit`) |
| GET | `/latest` | – | Most recent record |
| POST | `/` | TelemetryCreate | Insert (or upsert if unchanged) |
| POST | `/batch` | TelemetryBatchCreate | Bulk insert array |
| GET | `/track` | – | Ordered track (path) between dates |
| GET | `/stats` | – | Min/Max/Avg summary |
| GET | `/summary` | – | Count & time-span summary |

TelemetryCreate example:
```json
{
  "latitude": 40.7128,
  "longitude": -74.0060,
  "altitude": 120,
  "heading": 45,
  "speed": 12.3,
  "status": "active"
}
```

## 3.1 Global Telemetry (system-wide)
Base prefix: `/telemetry`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/latest-all` | Latest telemetry from all assets (optional `limit`) |


## 4. Command Queue (per-asset)
Base prefix: `/assets/{asset_id}/commands`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Return `{ asset_id, commands: [] }` |
| POST | `/` | Append command object |
| PUT | `/` | Replace queue with array |
| DELETE | `/` | Clear entire queue |
| DELETE | `/{index}` | Delete command at position |

Command object (example – **GOTO**):
```json
{
  "type": "GOTO",
  "parameters": { "lat": 40.7130, "lon": -74.0050, "alt": 100 }
}
```

## 4.1 Global Commands (system-wide)
Base prefix: `/commands`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/all-queues` | Command queues from all assets (optional `limit`) |


## 5. Tasks (system-wide)
Base prefix: `/tasks`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | List tasks |
| POST | `/` | Create task |
| GET | `/{task_id}` | Retrieve task |
| PUT | `/{task_id}` | Update task |
| DELETE | `/{task_id}` | Delete task |
| POST | `/{task_id}/assign/{asset_id}` | Assign task to asset |
| DELETE | `/{task_id}/assign/{asset_id}` | Remove assignment |
| GET | `/{task_id}/assignments` | List assigned assets |
| GET | `/tasks/assets/{asset_id}/task` | Get current task for asset |


## 6. Contacts

| Method | Path | Description |
|--------|------|-------------|
| GET | `/contacts` | List contacts (filter `asset_id`) |
| POST | `/contacts` | Create new contact |
| GET | `/contacts/{contact_id}` | Retrieve contact |
| PUT | `/contacts/{contact_id}` | Update contact |
| DELETE | `/contacts/{contact_id}` | Delete contact |

Contact creation example (camera detection):
```json
{
  "id": "CAM001_TARGET_1700000000",
  "spotter_asset_id": "CAM001",
  "contact_description": "camera_detection – person",
  "detection_metrics": {
    "bearing_deg": -45.2,
    "elevation_deg": 2.1,
    "range_m": 150.5
  }
}
```


---

## 7. Error Handling
Responses that are not `2xx` follow this structure:
```json
{
  "error_code": "ASSET_NOT_FOUND",
  "detail": "Asset with ID DRONE-999 does not exist"
}
```
Unique `error_code` strings allow quick troubleshooting (see logs in `logs/api_logs/`).

---

## 8. WebSockets (road-map)
A Socket.IO namespace `/ws` will push real-time telemetry & command-queue updates.  Until finalised, poll the `latest`/`commands` endpoints.

---

### CLI Snippets (Python 3.11 + httpx)
```python
import asyncio, httpx, json

BASE = "http://localhost:8000/api/v1"

async def main():
    async with httpx.AsyncClient(base_url=BASE) as c:
        # Create asset
        r = await c.post("/assets", json={"name": "SIM_DRONE", "asset_model_id": 1})
        asset = r.json(); print("Created", asset["id"])

        # Send telemetry
        await c.post(f"/assets/{asset['id']}/telemetry", json={
            "latitude": 40.0, "longitude": -70.0, "altitude": 100
        })

        # Add GOTO command
        await c.post(f"/assets/{asset['id']}/commands", json={
            "type": "GOTO", "parameters": {"lat": 40.1, "lon": -70.1, "alt": 120}
        })

asyncio.run(main())
```

---

*Last regenerated: 2024-07-12* 