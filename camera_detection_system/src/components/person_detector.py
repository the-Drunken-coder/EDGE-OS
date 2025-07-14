"""
PersonDetector - Consumer component for person detection
Processes frames from CameraManager using YOLO and outputs detection results
"""

import cv2
import threading
import queue
import time
import logging
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass
import numpy as np

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

from .camera_manager import FrameData
from models.telemetry import Detection, BoundingBox
from models.config import SystemConfig


@dataclass
class DetectionResult:
    """Container for detection results with metadata"""
    detections: List[Detection]
    frame_data: FrameData
    processing_time: float
    model_confidence: float


class PersonDetector:
    """
    Consumer component that processes frames for person detection using YOLO.
    Implements thread-safe detection with configurable confidence thresholds.
    """
    
    def __init__(self, 
                 config: SystemConfig,
                 frame_queue: queue.Queue, 
                 detection_queue: queue.Queue,
                 shutdown_event: threading.Event,
                 model_path: str = "yolov8n.pt"):
        """
        Initialize PersonDetector with input/output queues and configuration.
        
        Args:
            config: System configuration object
            frame_queue: Input queue for frames from CameraManager
            detection_queue: Output queue for detection results
            shutdown_event: Event to signal shutdown
            model_path: Path to YOLO model file
        """
        self.config = config
        self.frame_queue = frame_queue
        self.detection_queue = detection_queue
        self.model_path = model_path
        self.confidence_threshold = config.detection_confidence_threshold
        self.max_detections = config.max_detections_per_frame
        
        # Detection state
        self.model = None
        self.is_running = False
        self.detection_thread = None
        
        # Performance tracking
        self.detection_count = 0
        self.total_processing_time = 0.0
        self.last_detection_time = 0
        
        # Thread synchronization
        self.stop_event = shutdown_event
        self.lock = threading.Lock()
        
        # Logging
        self.logger = logging.getLogger(__name__)
        
        # YOLO class ID for person (COCO dataset)
        self.PERSON_CLASS_ID = 0
        
        # Initialize model in __init__
        self.initialize_model()
        
    def initialize_model(self) -> bool:
        """
        Initialize YOLO model for person detection.
        
        Returns:
            bool: True if model loaded successfully, False otherwise
        """
        if YOLO is None:
            self.logger.error("YOLO not available. Install ultralytics: pip install ultralytics")
            return False
            
        try:
            self.logger.info(f"Loading YOLO model: {self.model_path}")
            self.model = YOLO(self.model_path)
            
            # Warm up model with dummy inference
            dummy_frame = np.zeros((640, 640, 3), dtype=np.uint8)
            _ = self.model(dummy_frame, verbose=False)
            
            self.logger.info("YOLO model loaded and warmed up successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load YOLO model: {e}")
            return False
    
    def run(self):
        """Main detection loop for the person detector thread."""
        if self.model is None:
            self.logger.error("Model not initialized, exiting run loop")
            return
        
        self.is_running = True
        self.logger.info("Person detection loop started")
        
        while not self.stop_event.is_set():
            try:
                # Get frame from queue (with timeout)
                try:
                    frame_data = self.frame_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                
                # Process frame for person detection
                detection_result = self._process_frame(frame_data)
                
                if detection_result:
                    # Add result to output queue
                    try:
                        self.detection_queue.put_nowait(detection_result)
                        self.detection_count += 1
                        self.last_detection_time = time.time()
                        
                    except queue.Full:
                        # Queue full, skip this result
                        self.logger.debug("Detection queue full, skipping result")
                
                # Mark frame as processed
                self.frame_queue.task_done()
                
            except Exception as e:
                self.logger.error(f"Error in detection loop: {e}")
                time.sleep(0.1)  # Brief pause before retrying
                
        self.is_running = False
        self.logger.info("Person detection loop ended")
    
    def _process_frame(self, frame_data: FrameData) -> Optional[DetectionResult]:
        """
        Process a single frame for person detection.
        
        Args:
            frame_data: Frame data from CameraManager
            
        Returns:
            DetectionResult: Detection results, or None if processing failed
        """
        start_time = time.time()
        
        try:
            # Run YOLO inference
            results = self.model(frame_data.frame, verbose=False)
            
            # Extract person detections
            detections = self._extract_person_detections(results[0], frame_data)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            self.total_processing_time += processing_time
            
            # Get model confidence (average of all detections)
            avg_confidence = np.mean([det.confidence for det in detections]) if detections else 0.0
            
            return DetectionResult(
                detections=detections,
                frame_data=frame_data,
                processing_time=processing_time,
                model_confidence=float(avg_confidence)
            )
            
        except Exception as e:
            self.logger.error(f"Frame processing failed: {e}")
            return None
    
    def _extract_person_detections(self, result: Any, frame_data: FrameData) -> List[Detection]:
        """
        Extract person detections from YOLO results.
        
        Args:
            result: YOLO detection result
            frame_data: Original frame data
            
        Returns:
            List[Detection]: List of person detections
        """
        detections = []
        
        try:
            # Get detection data
            boxes = result.boxes
            if boxes is None or len(boxes) == 0:
                return detections
            
            # Filter for person class and confidence threshold
            for i, box in enumerate(boxes):
                # Check if detection is a person
                class_id = int(box.cls[0])
                if class_id != self.PERSON_CLASS_ID:
                    continue
                
                # Check confidence threshold
                confidence = float(box.conf[0])
                if confidence < self.confidence_threshold:
                    continue
                
                # Extract bounding box coordinates (x1, y1, x2, y2)
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                
                # Create bounding box
                bbox = BoundingBox(
                    x=int(x1),
                    y=int(y1),
                    width=int(x2 - x1),
                    height=int(y2 - y1)
                )
                
                # Create detection
                detection = Detection(
                    object_id=f"person_{frame_data.frame_id}_{i}",
                    object_type="person",
                    confidence=confidence,
                    bounding_box=bbox,
                    spatial_coordinates=None  # Will be calculated later by CoordinateCalculator
                )
                
                detections.append(detection)
                
                # Limit number of detections
                if len(detections) >= self.max_detections:
                    break
            
            self.logger.debug(f"Found {len(detections)} person detections in frame {frame_data.frame_id}")
            
        except Exception as e:
            self.logger.error(f"Detection extraction failed: {e}")
            
        return detections
    
    def get_detection_stats(self) -> Dict[str, Any]:
        """
        Get detection performance statistics.
        
        Returns:
            dict: Detection statistics including FPS, processing time, etc.
        """
        with self.lock:
            avg_processing_time = (self.total_processing_time / self.detection_count 
                                 if self.detection_count > 0 else 0.0)
            
            return {
                'is_running': self.is_running,
                'detection_count': self.detection_count,
                'average_processing_time': avg_processing_time,
                'confidence_threshold': self.confidence_threshold,
                'max_detections': self.max_detections,
                'model_path': self.model_path,
                'last_detection_time': self.last_detection_time,
                'queue_sizes': {
                    'input_queue': self.frame_queue.qsize(),
                    'output_queue': self.detection_queue.qsize()
                }
            }
    
    def update_confidence_threshold(self, new_threshold: float):
        """
        Update confidence threshold for detections.
        
        Args:
            new_threshold: New confidence threshold (0.0-1.0)
        """
        if 0.0 <= new_threshold <= 1.0:
            with self.lock:
                self.confidence_threshold = new_threshold
                self.logger.info(f"Confidence threshold updated to {new_threshold}")
        else:
            self.logger.warning(f"Invalid confidence threshold: {new_threshold}. Must be between 0.0 and 1.0")
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the loaded YOLO model.
        
        Returns:
            dict: Model information
        """
        if not self.model:
            return {'model_loaded': False}
            
        try:
            return {
                'model_loaded': True,
                'model_path': self.model_path,
                'model_type': str(type(self.model)),
                'input_size': getattr(self.model, 'imgsz', 'Unknown'),
                'classes': getattr(self.model, 'names', {}),
                'person_class_id': self.PERSON_CLASS_ID
            }
        except Exception as e:
            self.logger.error(f"Failed to get model info: {e}")
            return {'model_loaded': True, 'error': str(e)}
    
    def __enter__(self):
        """Context manager entry."""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensure cleanup."""
        self.stop_detection() 