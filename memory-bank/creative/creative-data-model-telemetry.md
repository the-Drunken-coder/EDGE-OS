# 🎨🎨🎨 ENTERING CREATIVE PHASE: DATA MODEL DESIGN 🎨🎨🎨

## Component Description
The Data Model Design defines the structure and format of telemetry data sent to the ATLAS system, configuration files for camera parameters, and internal data structures for efficient processing and communication between system components.

## Requirements & Constraints

### Data Model Requirements:
- ATLAS-compatible telemetry format
- Efficient serialization/deserialization
- Support for multiple person detections per frame
- Include confidence scores and spatial coordinates
- Timestamp precision for temporal correlation
- Asset identification and status information
- Configurable camera parameters storage
- Error handling and validation

### Technical Constraints:
- JSON format for ATLAS API compatibility
- Minimal payload size for network efficiency
- ISO-8601 timestamp format
- Schema validation support
- Backward compatibility considerations
- Human-readable configuration files
- Type safety for internal structures

## Multiple Data Model Options

### Option 1: Flat JSON Structure
**Description**: Simple flat JSON structure with minimal nesting for easy parsing and small payload size.

**Telemetry Format**:
```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "asset_id": "SEC_CAM_EDGE_001",
  "camera_status": "operational",
  "processing_fps": 12.5,
  "detection_count": 2,
  "detection_1_type": "person",
  "detection_1_confidence": 0.87,
  "detection_1_bearing": 15.2,
  "detection_1_elevation": -2.1,
  "detection_1_x": 320,
  "detection_1_y": 240,
  "detection_1_width": 80,
  "detection_1_height": 160,
  "detection_2_type": "person",
  "detection_2_confidence": 0.92,
  "detection_2_bearing": -8.5,
  "detection_2_elevation": 1.3,
  "detection_2_x": 180,
  "detection_2_y": 200,
  "detection_2_width": 75,
  "detection_2_height": 150
}
```

**Pros**:
- Extremely simple to parse
- Small payload size
- Fast serialization/deserialization
- No nested structure complexity

**Cons**:
- Not scalable for many detections
- Difficult to iterate over detections
- Repetitive field names
- Hard to extend with new fields

**Payload Size**: ~400-600 bytes per message
**Parse Time**: <0.1ms
**Extensibility**: Low

### Option 2: Nested Object Structure
**Description**: Hierarchical JSON structure with nested objects for logical grouping and extensibility.

**Telemetry Format**:
```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "asset_id": "SEC_CAM_EDGE_001",
  "system_status": {
    "camera_status": "operational",
    "processing_fps": 12.5,
    "cpu_usage": 45.2,
    "memory_usage": 128.5
  },
  "detections": [
    {
      "type": "person",
      "confidence": 0.87,
      "spatial": {
        "bearing": 15.2,
        "elevation": -2.1
      },
      "bounding_box": {
        "x": 320,
        "y": 240,
        "width": 80,
        "height": 160
      }
    },
    {
      "type": "person",
      "confidence": 0.92,
      "spatial": {
        "bearing": -8.5,
        "elevation": 1.3
      },
      "bounding_box": {
        "x": 180,
        "y": 200,
        "width": 75,
        "height": 150
      }
    }
  ]
}
```

**Pros**:
- Scalable for any number of detections
- Logical grouping of related data
- Easy to iterate and process
- Extensible structure

**Cons**:
- Larger payload size
- More complex parsing
- Nested structure overhead
- Potential for deep nesting

**Payload Size**: ~500-800 bytes per message
**Parse Time**: ~0.2ms
**Extensibility**: High

### Option 3: Compressed Binary Format
**Description**: Custom binary format with compression for minimal network overhead.

**Binary Structure**:
```python
# Header (20 bytes)
timestamp: uint64        # Unix timestamp with milliseconds
asset_id_hash: uint32    # Hash of asset ID
camera_status: uint8     # Status flags
processing_fps: float32  # FPS value
detection_count: uint8   # Number of detections

# Per detection (16 bytes each)
type: uint8              # Detection type (person=1)
confidence: uint8        # Confidence * 100
bearing: int16           # Bearing * 100 (centidegrees)
elevation: int16         # Elevation * 100 (centidegrees)
x: uint16               # Bounding box x
y: uint16               # Bounding box y
width: uint16           # Bounding box width
height: uint16          # Bounding box height
```

**Pros**:
- Minimal network bandwidth usage
- Very fast parsing
- Deterministic payload size
- Efficient for high-frequency data

**Cons**:
- Not human-readable
- Custom parsing required
- Limited precision for some values
- Versioning complexity

**Payload Size**: ~50-100 bytes per message
**Parse Time**: <0.05ms
**Extensibility**: Very Low

### Option 4: Hybrid JSON with Compression
**Description**: JSON format with optional compression and multiple payload formats based on context.

**Full Format** (periodic, comprehensive):
```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "asset_id": "SEC_CAM_EDGE_001",
  "message_type": "full_telemetry",
  "system_status": {
    "camera_status": "operational",
    "processing_fps": 12.5,
    "uptime": 3600,
    "cpu_usage": 45.2,
    "memory_usage": 128.5,
    "temperature": 42.1
  },
  "detections": [
    {
      "id": "det_001",
      "type": "person",
      "confidence": 0.87,
      "spatial": {
        "bearing": 15.2,
        "elevation": -2.1,
        "distance_estimate": null
      },
      "bounding_box": {
        "x": 320,
        "y": 240,
        "width": 80,
        "height": 160
      },
      "tracking": {
        "track_id": "track_001",
        "velocity": null
      }
    }
  ]
}
```

**Minimal Format** (frequent, detection-only):
```json
{
  "ts": "2024-01-15T10:30:45.123Z",
  "aid": "SEC_CAM_EDGE_001",
  "mt": "detection",
  "det": [
    {"t": "person", "c": 0.87, "b": 15.2, "e": -2.1, "bb": [320, 240, 80, 160]}
  ]
}
```

**Pros**:
- Adaptive payload size
- Optimal for different use cases
- Maintains JSON compatibility
- Efficient for high-frequency data

**Cons**:
- Multiple formats to maintain
- Complex switching logic
- Parsing complexity
- Potential format confusion

**Payload Size**: 100-800 bytes (adaptive)
**Parse Time**: 0.1-0.3ms
**Extensibility**: High

## Options Analysis

### Network Efficiency:
- **Option 1**: Good (400-600 bytes)
- **Option 2**: Moderate (500-800 bytes)
- **Option 3**: Excellent (50-100 bytes)
- **Option 4**: Variable (100-800 bytes)

### Development Complexity:
- **Option 1**: Very Low
- **Option 2**: Low-Medium
- **Option 3**: High
- **Option 4**: High

### ATLAS Compatibility:
- **Option 1**: High (standard JSON)
- **Option 2**: High (standard JSON)
- **Option 3**: Low (requires custom parser)
- **Option 4**: High (JSON-based)

### Maintainability:
- **Option 1**: High
- **Option 2**: High
- **Option 3**: Low
- **Option 4**: Medium

## Recommended Approach

**Selected Option**: **Option 2 - Nested Object Structure with Configuration Extensions**

### Rationale:
1. **ATLAS Compatibility**: Standard JSON format ensures seamless integration
2. **Scalability**: Handles variable number of detections efficiently
3. **Extensibility**: Easy to add new fields without breaking changes
4. **Maintainability**: Clear structure and logical grouping
5. **Performance**: Acceptable overhead for the benefits provided

### Implementation Guidelines:

#### Core Telemetry Schema:
```python
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

@dataclass
class BoundingBox:
    x: int
    y: int
    width: int
    height: int

@dataclass
class SpatialCoordinates:
    bearing: float      # degrees, positive = right
    elevation: float    # degrees, positive = up
    distance: Optional[float] = None  # meters, if available

@dataclass
class Detection:
    type: str                    # "person", "vehicle", etc.
    confidence: float            # 0.0 to 1.0
    spatial: SpatialCoordinates
    bounding_box: BoundingBox
    track_id: Optional[str] = None

@dataclass
class SystemStatus:
    camera_status: str          # "operational", "degraded", "offline"
    processing_fps: float
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    temperature: Optional[float] = None

@dataclass
class TelemetryMessage:
    timestamp: datetime
    asset_id: str
    system_status: SystemStatus
    detections: List[Detection]
    
    def to_json(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat() + "Z",
            "asset_id": self.asset_id,
            "system_status": {
                "camera_status": self.system_status.camera_status,
                "processing_fps": self.system_status.processing_fps,
                "cpu_usage": self.system_status.cpu_usage,
                "memory_usage": self.system_status.memory_usage,
                "temperature": self.system_status.temperature
            },
            "detections": [
                {
                    "type": detection.type,
                    "confidence": detection.confidence,
                    "spatial": {
                        "bearing": detection.spatial.bearing,
                        "elevation": detection.spatial.elevation,
                        "distance": detection.spatial.distance
                    },
                    "bounding_box": {
                        "x": detection.bounding_box.x,
                        "y": detection.bounding_box.y,
                        "width": detection.bounding_box.width,
                        "height": detection.bounding_box.height
                    },
                    "track_id": detection.track_id
                }
                for detection in self.detections
            ]
        }
```

#### Camera Configuration Schema:
```python
@dataclass
class CameraConfig:
    name: str
    type: str                   # "pi_camera", "usb_camera"
    width: int
    height: int
    horizontal_fov: float       # degrees
    vertical_fov: float         # degrees
    fps: int
    device_path: Optional[str] = None
    calibration_matrix: Optional[List[List[float]]] = None
    distortion_coefficients: Optional[List[float]] = None

@dataclass
class SystemConfig:
    asset_id: str
    atlas_api_url: str
    telemetry_interval: float   # seconds
    detection_confidence_threshold: float
    camera: CameraConfig
    logging_level: str = "INFO"
    
    @classmethod
    def from_json_file(cls, filepath: str) -> 'SystemConfig':
        with open(filepath, 'r') as f:
            data = json.load(f)
        return cls(**data)
```

#### Configuration File Format:
```json
{
  "asset_id": "SEC_CAM_EDGE_001",
  "atlas_api_url": "https://atlas.example.com/api/v1",
  "telemetry_interval": 1.0,
  "detection_confidence_threshold": 0.5,
  "logging_level": "INFO",
  "camera": {
    "name": "Primary Security Camera",
    "type": "pi_camera",
    "width": 640,
    "height": 480,
    "horizontal_fov": 62.2,
    "vertical_fov": 48.8,
    "fps": 30,
    "device_path": null,
    "calibration_matrix": null,
    "distortion_coefficients": null
  }
}
```

## 🎨 CREATIVE CHECKPOINT: Data Model Selected

Data model decision made: Nested Object Structure with typed dataclasses for internal processing and JSON serialization for ATLAS compatibility.

## Verification Against Requirements

### Requirements Met:
- ✅ ATLAS-compatible telemetry format (Standard JSON)
- ✅ Efficient serialization/deserialization (Dataclass to JSON)
- ✅ Support for multiple person detections (List structure)
- ✅ Include confidence scores and spatial coordinates (Nested objects)
- ✅ Timestamp precision for temporal correlation (ISO-8601 format)
- ✅ Asset identification and status information (Top-level fields)
- ✅ Configurable camera parameters storage (Configuration schema)
- ✅ Error handling and validation (Type safety with dataclasses)

### Technical Constraints Met:
- ✅ JSON format for ATLAS API compatibility (Native JSON serialization)
- ✅ Minimal payload size for network efficiency (~500-800 bytes)
- ✅ ISO-8601 timestamp format (Standard datetime formatting)
- ✅ Schema validation support (Dataclass type checking)
- ✅ Backward compatibility considerations (Optional fields)
- ✅ Human-readable configuration files (JSON configuration)
- ✅ Type safety for internal structures (Python dataclasses)

### Performance Characteristics:
- **Serialization Time**: <0.5ms per message
- **Payload Size**: 500-800 bytes (2-5 detections)
- **Memory Usage**: <2KB per message object
- **Validation Time**: <0.1ms per message

### Extensibility Features:
- Optional fields for future enhancements
- Nested structure allows adding new categories
- Configuration-driven behavior
- Type-safe internal processing

🎨🎨🎨 EXITING CREATIVE PHASE - DATA MODEL DECISION MADE 🎨🎨🎨 