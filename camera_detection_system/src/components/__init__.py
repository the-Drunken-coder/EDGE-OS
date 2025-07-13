"""
Components package for camera detection system
"""

from .coordinate_calculator import CoordinateCalculator
from .camera_manager import CameraManager, FrameData
from .person_detector import PersonDetector, DetectionResult

__all__ = [
    'CoordinateCalculator',
    'CameraManager',
    'FrameData', 
    'PersonDetector',
    'DetectionResult'
] 