# ATLAS Project Technical Architecture Overview

## Core Philosophy & Design Principles

**ATLAS (Asset Tracking, Location And Surveillance)** is fundamentally built around an **asset-centric, self-registration paradigm**. The system operates on the principle that assets (drones, cameras, sensors) are autonomous entities that manage their own lifecycle and status reporting, rather than being managed by a central authority.

### Key Architectural Philosophies:

1. **Asset Self-Registration**: Assets bootstrap themselves into the system by calling registration endpoints with their specifications
2. **Read-Only Web Interface**: The web UI is strictly for monitoring and visualization - no CRUD operations on assets
3. **Asset-Driven Status**: Assets determine and report their own operational status (on mission, standby, lost connection)
4. **API-First Design**: Single unified REST API serves as the only entry point for all functionality
5. **Real-Time Data Pipeline**: Continuous telemetry processing with WebSocket-based live updates

## System Architecture Overview

### Backend (Atlas Command)
- **Framework**: FastAPI with Python 3.11+ for ultra-low latency (sub-millisecond responses)
- **Database**: PostgreSQL 15+ with TimescaleDB extension for hybrid relational/time-series data
- **Caching**: Redis 7+ for session management and high-performance data access
- **Real-Time**: WebSocket connections for live data streaming to web interface
- **Deployment**: Docker containerized with single-machine deployment strategy

### Frontend (Atlas Web Interface)
- **Framework**: TypeScript + Vite with component-based architecture
- **UI Pattern**: Windows-like desktop environment with multi-window management
- **Real-Time**: WebSocket subscriptions for live asset updates
- **Caching**: Sophisticated client-side cache system with performance monitoring

### Data Flow Architecture
```
Asset → REST API → PostgreSQL/TimescaleDB → Redis Cache → WebSocket → Web Interface
  ↓
Asset Self-Registration → Asset Models (JSON) → Database → Cache → UI
```

## Asset Management System

### Asset Self-Registration Process

Assets follow a standardized bootstrap sequence:

1. **Asset Model Loading**: System loads asset model definitions from JSON files in `startup_data/asset_models/`
2. **Self-Registration**: Asset calls `POST /api/v1/assets/` with:
   ```json
   {
     "id": "SEC_CAM_EDGE_001",  // Optional - system generates if omitted
     "name": "Security Camera Edge Unit",
     "asset_model_id": 1  // References pre-loaded asset model
   }
   ```
3. **ID Management**: Asset IDs are strings supporting both numeric ("1") and alphanumeric ("DRONE-001") formats
4. **Validation**: System validates asset model exists and creates database record

### Asset Model System

Asset models are pre-defined templates loaded from JSON files:

```json
{
  "id": 1,
  "name": "Security Camera Fixed",
  "type": "security_camera",
  "description": "Stationary security camera for perimeter monitoring",
  "sensor_id": 1
}
```

This allows assets to register with minimal data while inheriting rich specifications from the model.

### Asset Status Philosophy

Assets implement self-assessment logic and report their operational status:

- **"on mission"**: Actively executing tasks (recording, tracking, patrolling)
- **"standby"**: Ready and waiting for orders
- **"lost connection"**: Communication failure or critical conditions

The system never assumes asset status - assets must actively report their state.

## Data Management Architecture

### Telemetry System

High-frequency telemetry data flows through optimized pipelines:

- **Ingestion**: Assets POST telemetry to `/api/v1/assets/{asset_id}/telemetry`
- **Storage**: TimescaleDB hypertables for automatic time-series partitioning
- **Retention**: 24-hour automatic cleanup for operational efficiency
- **Performance**: Optimized for 1 record/second during active operations

### Command System

Assets can receive commands through a queue-based system:

- **Command Queue**: Per-asset command queues with 0-based indexing
- **Polling**: Assets poll their command queue or subscribe to updates
- **Acknowledgment**: Assets acknowledge command receipt and completion

### Real-Time Updates

WebSocket-based change stream provides live updates:

- **Change Detection**: Database triggers capture data changes
- **WebSocket Push**: Changes streamed to connected clients
- **Cache Invalidation**: Client-side cache automatically updated

## Current System State & Evolution

### MQTT Integration (In Progress)

The system is currently implementing MQTT-based communication for enhanced scalability:

- **Topic Structure**: `atlas/assets/{asset_id}/{message_type}`
- **Broker**: Eclipse Mosquitto with graduated enhancement path
- **Protocol**: Hybrid JSON-binary translation for optimal performance
- **Security**: TLS encryption with topic-based access control

### Meshtastic Integration (Planned)

Future mesh networking capabilities through Meshtastic LoRa integration:

- **Bridge Architecture**: LoRa mesh → Bridge System → ATLAS API
- **One-Way Communication**: Assets only send telemetry (no commands to mesh)
- **Cost Reduction**: 90% hardware cost reduction through mesh networking

## Performance Characteristics

### Response Times
- **API Responses**: Sub-millisecond for cached requests
- **Database Queries**: Optimized for time-series data with chunk pruning
- **WebSocket Updates**: Real-time propagation of changes
- **Concurrent Users**: Multi-user support with session management

### Scalability
- **Single Machine**: Optimized for local deployment
- **Asset Capacity**: Designed for 100+ concurrent assets
- **Data Retention**: 24-hour automatic cleanup for operational efficiency
- **Resource Usage**: Minimal footprint for single-machine constraints

## Security & Error Handling

### Error Management
- **Unique Error Codes**: All 4xx/5xx responses include unique `error_code` fields
- **Comprehensive Logging**: Structured logging with file-based output
- **Graceful Degradation**: System continues operating with partial failures

### Security Model
- **TLS Encryption**: All communications encrypted
- **Topic-Based Access Control**: MQTT topic-level security
- **Asset Authentication**: Secure asset registration and communication

## Development & Testing Philosophy

### Code Quality Standards
- **Modular Design**: Files kept under 200-300 lines
- **Type Safety**: TypeScript frontend, Pydantic schemas
- **No Mock Data**: Production code never includes fake/stub data
- **Comprehensive Testing**: Unit, integration, and end-to-end testing

### Deployment Strategy
- **Docker Containerization**: All services containerized
- **Single Command Deployment**: `docker-compose up` starts entire system
- **Hot Reload**: Development-friendly with zero downtime restarts
- **Self-Managing**: Automatic cleanup and maintenance tasks

## Integration Points for Security Camera Asset

### Required Endpoints
1. **Registration**: `POST /api/v1/assets/` (one-time on startup)
2. **Telemetry**: `POST /api/v1/assets/{asset_id}/telemetry` (continuous)
3. **Command Polling**: `GET /api/v1/assets/{asset_id}/commands` (periodic)
4. **Status Updates**: Include status in telemetry payload

### Expected Data Formats
- **JSON**: Primary data exchange format
- **ISO-8601**: UTC timestamps for all time data
- **String IDs**: Asset identifiers as strings
- **Error Codes**: Unique error identifiers in responses

### Future Transport Options
- **Current**: REST API over HTTPS
- **Near-term**: MQTT over TLS
- **Future**: Meshtastic LoRa mesh integration

This architecture provides a robust, scalable foundation for building edge assets that seamlessly integrate with the ATLAS ecosystem while maintaining operational independence and reliability. 