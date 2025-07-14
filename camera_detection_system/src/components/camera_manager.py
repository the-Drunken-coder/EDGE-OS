"""
CameraManager - Producer component for camera frame capture
Handles camera initialization, frame capture, and thread-safe frame distribution
"""

import cv2
import threading
import queue
import time
import logging
from typing import Optional, Tuple, Any
from dataclasses import dataclass
import numpy as np

from models.config import CameraConfig


@dataclass
class FrameData:
    """Container for frame data with metadata"""
    frame: Any  # numpy array
    timestamp: float
    frame_id: int
    camera_id: str


class CameraManager:
    """
    Producer component that manages camera capture and frame distribution.
    Implements thread-safe frame capture with configurable frame rate control.
    """
    
    def __init__(self, camera_config: CameraConfig, frame_queue: queue.Queue, shutdown_event: threading.Event, use_mock: bool = False, max_queue_size: int = 10):
        """
        Initialize CameraManager with configuration and output queue.
        
        Args:
            camera_config: Camera configuration object
            frame_queue: Thread-safe queue for frame distribution
            shutdown_event: Event to signal shutdown
            use_mock: Use mock camera mode for testing
            max_queue_size: Maximum frames to keep in queue (prevents memory overflow)
        """
        self.config = camera_config
        self.frame_queue = frame_queue
        self.max_queue_size = max_queue_size
        self.use_mock = use_mock
        
        # Camera state
        self.camera = None
        self.is_running = False
        
        # Frame tracking
        self.frame_counter = 0
        self.last_frame_time = 0
        self.target_frame_interval = 1.0 / camera_config.fps if camera_config.fps > 0 else 0.033  # Default 30 FPS
        
        # Thread synchronization
        self.stop_event = shutdown_event
        self.lock = threading.Lock()
        
        # Logging
        self.logger = logging.getLogger(__name__)
    
    def initialize_camera(self) -> bool:
        """
        Initialize camera based on configuration.
        
        Returns:
            bool: True if camera initialized successfully, False otherwise
        """
        try:
            if self.config.type.lower() == 'usb_camera':
                # USB Camera (webcam)
                device_id = 0  # Default device ID
                if self.config.device_path:
                    # Try to extract device ID from path like "/dev/video0"
                    try:
                        device_id = int(self.config.device_path.split('video')[-1])
                    except:
                        device_id = 0
                        
                self.camera = cv2.VideoCapture(device_id)
                
                if not self.camera.isOpened():
                    self.logger.error(f"Failed to open USB camera {device_id}")
                    return False
                    
                # Set camera properties
                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
                self.camera.set(cv2.CAP_PROP_FPS, self.config.fps)
                
            elif self.config.type.lower() == 'pi_camera':
                # Raspberry Pi Camera
                try:
                    import picamera
                    self.camera = picamera.PiCamera()
                    self.camera.resolution = (self.config.width, self.config.height)
                    self.camera.framerate = self.config.fps
                    time.sleep(2)  # Camera warm-up time
                except ImportError:
                    self.logger.error("PiCamera library not available. Install picamera for Pi Camera support.")
                    return False
                except Exception as e:
                    self.logger.error(f"Failed to initialize Pi Camera: {e}")
                    return False
                    
            else:
                self.logger.error(f"Unsupported camera type: {self.config.type}")
                return False
                
            self.logger.info(f"Camera initialized: {self.config.type} at {self.config.width}x{self.config.height} @ {self.config.fps} FPS")
            return True
            
        except Exception as e:
            self.logger.error(f"Camera initialization failed: {e}")
            return False
    
    def run(self):
        """Main capture loop for the camera manager thread."""
        if self.use_mock:
            self.logger.info("Using mock camera mode")
        else:
            if not self.initialize_camera():
                self.logger.error("Failed to initialize camera, exiting run loop")
                return
        
        self.is_running = True
        self.logger.info("Camera capture loop started")
        
        while not self.stop_event.is_set():
            try:
                current_time = time.time()
                
                # Frame rate control
                if current_time - self.last_frame_time < self.target_frame_interval:
                    time.sleep(0.001)  # Small sleep to prevent busy waiting
                    continue
                
                # Capture frame
                frame = self._capture_frame()
                if frame is None:
                    continue
                    
                # Create frame data
                frame_data = FrameData(
                    frame=frame,
                    timestamp=current_time,
                    frame_id=self.frame_counter,
                    camera_id=self.config.name
                )
                
                # Add to queue (non-blocking)
                try:
                    # Remove old frames if queue is full
                    while self.frame_queue.qsize() >= self.max_queue_size:
                        try:
                            self.frame_queue.get_nowait()
                        except queue.Empty:
                            break
                    
                    self.frame_queue.put_nowait(frame_data)
                    self.frame_counter += 1
                    self.last_frame_time = current_time
                    
                except queue.Full:
                    # Queue full, skip this frame
                    self.logger.debug("Frame queue full, skipping frame")
                    
            except Exception as e:
                self.logger.error(f"Error in capture loop: {e}")
                time.sleep(0.1)  # Brief pause before retrying
                
        self.is_running = False
        self._cleanup_camera()
        self.logger.info("Camera capture loop ended")
    
    def _capture_frame(self) -> Optional[Any]:
        """
        Capture a single frame from camera or generate mock frame.
        
        Returns:
            numpy array: Captured or mock frame, or None if capture failed
        """
        try:
            if self.use_mock:
                # Generate mock frame
                frame = np.zeros((self.config.height, self.config.width, 3), dtype=np.uint8)
                # Add some mock 'people' as rectangles
                num_people = np.random.randint(1, 4)  # 1-3 mock people
                for _ in range(num_people):
                    x = np.random.randint(0, self.config.width - 100)
                    y = np.random.randint(0, self.config.height - 200)
                    cv2.rectangle(frame, (x, y), (x+80, y+160), (0, 255, 0), 2)
                return frame
            
            if self.config.type.lower() == 'usb_camera':
                ret, frame = self.camera.read()
                if not ret or frame is None:
                    self.logger.debug("Failed to read frame from USB camera")
                    return None
                return frame
                
            elif self.config.type.lower() == 'pi_camera':
                import io
                import numpy as np
                from PIL import Image
                
                # Capture to stream
                stream = io.BytesIO()
                self.camera.capture(stream, format='jpeg')
                stream.seek(0)
                
                # Convert to numpy array
                image = Image.open(stream)
                frame = np.array(image)
                
                # Convert RGB to BGR (OpenCV format)
                if len(frame.shape) == 3:
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    
                return frame
                
        except Exception as e:
            self.logger.error(f"Frame capture failed: {e}")
            return None
    
    def _cleanup_camera(self):
        """Cleanup camera resources."""
        try:
            if self.camera:
                if self.config.type.lower() == 'usb_camera':
                    self.camera.release()
                elif self.config.type.lower() == 'pi_camera':
                    self.camera.close()
                self.camera = None
                
        except Exception as e:
            self.logger.error(f"Camera cleanup failed: {e}")
    
    def get_camera_info(self) -> dict:
        """
        Get current camera information and statistics.
        
        Returns:
            dict: Camera information including status, frame count, etc.
        """
        with self.lock:
            return {
                'name': self.config.name,
                'type': self.config.type,
                'width': self.config.width,
                'height': self.config.height,
                'fps': self.config.fps,
                'is_running': self.is_running,
                'frame_count': self.frame_counter,
                'queue_size': self.frame_queue.qsize(),
                'max_queue_size': self.max_queue_size
            }
    
    def __enter__(self):
        """Context manager entry."""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensure cleanup."""
        self.stop_capture() 