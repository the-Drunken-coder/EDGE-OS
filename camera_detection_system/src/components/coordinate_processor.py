"""
CoordinateProcessor - Consumer component for spatial coordinate calculation
Processes detection results and adds spatial coordinates using CoordinateCalculator
"""

import threading
import queue
import time
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from .person_detector import DetectionResult
from .coordinate_calculator import CoordinateCalculator
from models.telemetry import Detection, SpatialCoordinates
from models.config import CameraConfig


@dataclass
class CoordinateResult:
    """Container for detection results with spatial coordinates"""
    detections: List[Detection]
    frame_data: Any  # FrameData from original detection
    processing_time: float
    coordinate_calculation_time: float
    successful_calculations: int
    failed_calculations: int


class CoordinateProcessor:
    """
    Consumer component that processes detection results to add spatial coordinates.
    Integrates with CoordinateCalculator to convert bounding boxes to spatial positions.
    """
    
    def __init__(self, 
                 detection_queue: queue.Queue, 
                 coordinate_queue: queue.Queue,
                 camera_config: CameraConfig,
                 shutdown_event: threading.Event):
        """
        Initialize CoordinateProcessor with input/output queues and camera configuration.
        
        Args:
            detection_queue: Input queue for detection results from PersonDetector
            coordinate_queue: Output queue for detection results with coordinates
            camera_config: Camera configuration for coordinate calculations
            shutdown_event: Event to signal shutdown
        """
        self.detection_queue = detection_queue
        self.coordinate_queue = coordinate_queue
        self.camera_config = camera_config
        
        # Initialize coordinate calculator
        self.coordinate_calculator = CoordinateCalculator(camera_config)
        
        # Processing state
        self.is_running = False
        self.processing_thread = None
        
        # Performance tracking
        self.processed_count = 0
        self.total_processing_time = 0.0
        self.total_coordinate_time = 0.0
        self.successful_calculations = 0
        self.failed_calculations = 0
        self.last_processing_time = 0
        
        # Thread synchronization
        self.stop_event = shutdown_event
        self.lock = threading.Lock()
        
        # Logging
        self.logger = logging.getLogger(__name__)
        
    def start_processing(self) -> bool:
        """
        Start coordinate processing in a separate thread.
        
        Returns:
            bool: True if processing started successfully, False otherwise
        """
        if self.is_running:
            self.logger.warning("Coordinate processing already running")
            return True
            
        # Reset synchronization objects
        self.stop_event.clear()
        self.is_running = True
        
        # Start processing thread
        self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.processing_thread.start()
        
        self.logger.info("Coordinate processing started")
        return True
    
    def stop_processing(self):
        """Stop coordinate processing and cleanup resources."""
        if not self.is_running:
            return
            
        # Signal thread to stop
        self.stop_event.set()
        self.is_running = False
        
        # Wait for thread to finish
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=5.0)
            
        self.logger.info("Coordinate processing stopped")
    
    def run(self):
        """Main processing loop for the coordinate processor thread."""
        self.is_running = True
        self.logger.info("Coordinate processing loop started")
        
        while not self.stop_event.is_set():
            try:
                # Get detection result from queue (with timeout)
                try:
                    detection_result = self.detection_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                
                # Process detection result to add coordinates
                coordinate_result = self._process_detections(detection_result)
                
                if coordinate_result:
                    # Add result to output queue
                    try:
                        self.coordinate_queue.put_nowait(coordinate_result)
                        self.processed_count += 1
                        self.last_processing_time = time.time()
                        
                    except queue.Full:
                        # Queue full, skip this result
                        self.logger.debug("Coordinate queue full, skipping result")
                
                # Mark detection as processed
                self.detection_queue.task_done()
                
            except Exception as e:
                self.logger.error(f"Error in coordinate processing loop: {e}")
                time.sleep(0.1)  # Brief pause before retrying
                
        self.is_running = False
        self.logger.info("Coordinate processing loop ended")
    
    def _process_detections(self, detection_result: DetectionResult) -> Optional[CoordinateResult]:
        """
        Process detection result to add spatial coordinates to each detection.
        
        Args:
            detection_result: Detection result from PersonDetector
            
        Returns:
            CoordinateResult: Detection result with spatial coordinates, or None if processing failed
        """
        start_time = time.time()
        coordinate_start_time = time.time()
        
        try:
            processed_detections = []
            successful_calcs = 0
            failed_calcs = 0
            
            for detection in detection_result.detections:
                try:
                    # Calculate spatial coordinates from bounding box
                    spatial_coords = self._calculate_spatial_coordinates(detection)
                    
                    if spatial_coords:
                        # Create new detection with spatial coordinates
                        updated_detection = Detection(
                            object_id=detection.object_id,
                            object_type=detection.object_type,
                            confidence=detection.confidence,
                            bounding_box=detection.bounding_box,
                            spatial_coordinates=spatial_coords
                        )
                        processed_detections.append(updated_detection)
                        successful_calcs += 1
                    else:
                        # Keep detection without spatial coordinates
                        processed_detections.append(detection)
                        failed_calcs += 1
                        
                except Exception as e:
                    self.logger.warning(f"Failed to calculate coordinates for detection {detection.object_id}: {e}")
                    processed_detections.append(detection)
                    failed_calcs += 1
            
            # Calculate processing times
            coordinate_time = time.time() - coordinate_start_time
            total_time = time.time() - start_time
            
            # Update statistics
            with self.lock:
                self.total_processing_time += total_time
                self.total_coordinate_time += coordinate_time
                self.successful_calculations += successful_calcs
                self.failed_calculations += failed_calcs
            
            return CoordinateResult(
                detections=processed_detections,
                frame_data=detection_result.frame_data,
                processing_time=total_time,
                coordinate_calculation_time=coordinate_time,
                successful_calculations=successful_calcs,
                failed_calculations=failed_calcs
            )
            
        except Exception as e:
            self.logger.error(f"Detection processing failed: {e}")
            return None
    
    def _calculate_spatial_coordinates(self, detection: Detection) -> Optional[SpatialCoordinates]:
        """
        Calculate spatial coordinates for a detection using the bounding box.
        
        Args:
            detection: Detection object with bounding box
            
        Returns:
            SpatialCoordinates: Calculated spatial coordinates, or None if calculation failed
        """
        try:
            # Use coordinate calculator with the bounding box
            spatial_coords = self.coordinate_calculator.calculate_coordinates(detection.bounding_box)
            return spatial_coords
                
        except Exception as e:
            self.logger.warning(f"Spatial coordinate calculation failed: {e}")
            return None
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """
        Get coordinate processing performance statistics.
        
        Returns:
            dict: Processing statistics including performance metrics
        """
        with self.lock:
            avg_processing_time = (self.total_processing_time / self.processed_count 
                                 if self.processed_count > 0 else 0.0)
            avg_coordinate_time = (self.total_coordinate_time / self.processed_count 
                                 if self.processed_count > 0 else 0.0)
            success_rate = (self.successful_calculations / 
                          (self.successful_calculations + self.failed_calculations)
                          if (self.successful_calculations + self.failed_calculations) > 0 else 0.0)
            
            return {
                'is_running': self.is_running,
                'processed_count': self.processed_count,
                'average_processing_time': avg_processing_time,
                'average_coordinate_time': avg_coordinate_time,
                'successful_calculations': self.successful_calculations,
                'failed_calculations': self.failed_calculations,
                'success_rate': success_rate,
                'last_processing_time': self.last_processing_time,
                'queue_sizes': {
                    'input_queue': self.detection_queue.qsize(),
                    'output_queue': self.coordinate_queue.qsize()
                }
            }
    
    def get_coordinate_calculator_info(self) -> Dict[str, Any]:
        """
        Get information about the coordinate calculator configuration.
        
        Returns:
            dict: Coordinate calculator information
        """
        return {
            'frame_width': self.coordinate_calculator.frame_width,
            'frame_height': self.coordinate_calculator.frame_height,
            'h_fov': self.coordinate_calculator.h_fov,
            'v_fov': self.coordinate_calculator.v_fov,
            'focal_length_x': getattr(self.coordinate_calculator, 'focal_length_x', 0),
            'focal_length_y': getattr(self.coordinate_calculator, 'focal_length_y', 0)
        }
    
    def update_camera_config(self, new_config: CameraConfig):
        """
        Update camera configuration and reinitialize coordinate calculator.
        
        Args:
            new_config: New camera configuration
        """
        try:
            with self.lock:
                self.camera_config = new_config
                self.coordinate_calculator = CoordinateCalculator(new_config)
                self.logger.info("Camera configuration updated and coordinate calculator reinitialized")
                
        except Exception as e:
            self.logger.error(f"Failed to update camera configuration: {e}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensure cleanup."""
        self.stop_processing() 