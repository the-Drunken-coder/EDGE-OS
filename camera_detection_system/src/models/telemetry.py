"""
Telemetry data models for ATLAS integration.

These models define the structure of data sent to the ATLAS system,
including person detections, spatial coordinates, and system status.
Based on the creative phase decision: Nested Object Structure with JSON serialization.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime
import json


@dataclass
class BoundingBox:
    """Bounding box coordinates for detected objects."""
    x: int
    y: int
    width: int
    height: int

    def to_dict(self) -> Dict[str, int]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height
        }


@dataclass
class SpatialCoordinates:
    """Spatial coordinates relative to camera field of view."""
    bearing: float      # degrees, positive = right
    elevation: float    # degrees, positive = up
    distance: Optional[float] = None  # meters, if available

    def to_dict(self) -> Dict[str, Optional[float]]:
        return {
            "bearing": self.bearing,
            "elevation": self.elevation,
            "distance": self.distance
        }


@dataclass
class Detection:
    """Individual person detection with spatial and visual information."""
    object_id: str               # Unique identifier for this detection
    object_type: str             # "person", "vehicle", etc.
    confidence: float            # 0.0 to 1.0
    bounding_box: BoundingBox
    spatial_coordinates: Optional[SpatialCoordinates] = None
    track_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "object_id": self.object_id,
            "object_type": self.object_type,
            "confidence": self.confidence,
            "bounding_box": self.bounding_box.to_dict(),
            "spatial_coordinates": self.spatial_coordinates.to_dict() if self.spatial_coordinates else None,
            "track_id": self.track_id
        }


@dataclass
class SystemStatus:
    """System operational status and performance metrics."""
    camera_status: str          # "operational", "degraded", "offline"
    processing_fps: float
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    temperature: Optional[float] = None

    def to_dict(self) -> Dict[str, Optional[float]]:
        return {
            "camera_status": self.camera_status,
            "processing_fps": self.processing_fps,
            "cpu_usage": self.cpu_usage,
            "memory_usage": self.memory_usage,
            "temperature": self.temperature
        }


@dataclass
class TelemetryMessage:
    """Complete telemetry message for ATLAS API."""
    timestamp: datetime
    asset_id: str
    system_status: SystemStatus
    detections: List[Detection]
    
    def to_json(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary for ATLAS API."""
        return {
            "timestamp": self.timestamp.isoformat() + "Z",
            "asset_id": self.asset_id,
            "system_status": self.system_status.to_dict(),
            "detections": [detection.to_dict() for detection in self.detections]
        }
    
    def to_json_string(self) -> str:
        """Convert to JSON string for transmission."""
        return json.dumps(self.to_json(), indent=None, separators=(',', ':'))
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TelemetryMessage':
        """Create TelemetryMessage from dictionary (for testing/deserialization)."""
        return cls(
            timestamp=datetime.fromisoformat(data['timestamp'].rstrip('Z')),
            asset_id=data['asset_id'],
            system_status=SystemStatus(**data['system_status']),
            detections=[
                Detection(
                    object_id=det['object_id'],
                    object_type=det['object_type'],
                    confidence=det['confidence'],
                    bounding_box=BoundingBox(**det['bounding_box']),
                    spatial_coordinates=SpatialCoordinates(**det['spatial_coordinates']) if det['spatial_coordinates'] else None,
                    track_id=det.get('track_id')
                )
                for det in data['detections']
            ]
        ) 