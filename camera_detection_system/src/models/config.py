"""
Configuration data models for the camera detection system.

These models define the structure of configuration files and
system parameters used throughout the application.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import json


@dataclass
class CameraConfig:
    """Camera configuration parameters."""
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

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "type": self.type,
            "width": self.width,
            "height": self.height,
            "horizontal_fov": self.horizontal_fov,
            "vertical_fov": self.vertical_fov,
            "fps": self.fps,
            "device_path": self.device_path,
            "calibration_matrix": self.calibration_matrix,
            "distortion_coefficients": self.distortion_coefficients
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CameraConfig':
        """Create CameraConfig from dictionary."""
        return cls(**data)


@dataclass
class SystemConfig:
    """Complete system configuration."""
    asset_id: str
    atlas_api_url: str
    telemetry_interval: float   # seconds
    detection_confidence_threshold: float
    camera: CameraConfig
    logging_level: str = "INFO"
    max_detections_per_frame: int = 10
    frame_queue_size: int = 5
    detection_queue_size: int = 10
    telemetry_queue_size: int = 50

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "asset_id": self.asset_id,
            "atlas_api_url": self.atlas_api_url,
            "telemetry_interval": self.telemetry_interval,
            "detection_confidence_threshold": self.detection_confidence_threshold,
            "logging_level": self.logging_level,
            "max_detections_per_frame": self.max_detections_per_frame,
            "frame_queue_size": self.frame_queue_size,
            "detection_queue_size": self.detection_queue_size,
            "telemetry_queue_size": self.telemetry_queue_size,
            "camera": self.camera.to_dict()
        }

    def to_json_file(self, filepath: str) -> None:
        """Save configuration to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SystemConfig':
        """Create SystemConfig from dictionary."""
        camera_data = data.pop('camera')
        camera_config = CameraConfig.from_dict(camera_data)
        return cls(camera=camera_config, **data)

    @classmethod
    def from_json_file(cls, filepath: str) -> 'SystemConfig':
        """Load configuration from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def create_default(cls, asset_id: str = "SEC_CAM_EDGE_001") -> 'SystemConfig':
        """Create a default configuration for testing/initial setup."""
        default_camera = CameraConfig(
            name="Primary Security Camera",
            type="usb_camera",  # Default to USB camera for development
            width=640,
            height=480,
            horizontal_fov=60.0,
            vertical_fov=45.0,
            fps=30,
            device_path=None
        )
        
        return cls(
            asset_id=asset_id,
            atlas_api_url="http://localhost:8000/api/v1",  # Default for testing
            telemetry_interval=1.0,
            detection_confidence_threshold=0.5,
            camera=default_camera,
            logging_level="INFO"
        ) 