import threading
import time
import queue
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from components.camera_manager import CameraManager
from components.person_detector import PersonDetector
from components.coordinate_processor import CoordinateProcessor
from components.telemetry_client import TelemetryClient
from models.config import SystemConfig
from models.telemetry import SystemStatus


@dataclass
class EdgeAgentStats:
    """Statistics for the EdgeAgent system"""
    frames_processed: int = 0
    detections_made: int = 0
    coordinates_calculated: int = 0
    messages_sent: int = 0
    errors_encountered: int = 0
    uptime_seconds: float = 0.0
    fps: float = 0.0


class EdgeAgent:
    """
    Main orchestrator for the camera detection and person tracking system.
    Manages all components in a multi-threaded architecture.
    """
    
    def __init__(self, config: SystemConfig, use_mock_camera: bool = False):
        self.config = config
        self.use_mock_camera = use_mock_camera
        self.running = False
        self.start_time = None
        self.stats = EdgeAgentStats()
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/edge_agent.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Inter-component queues
        self.frame_queue = queue.Queue(maxsize=config.frame_queue_size)
        self.detection_queue = queue.Queue(maxsize=config.detection_queue_size)
        self.coordinate_queue = queue.Queue(maxsize=config.telemetry_queue_size)
        
        # Components
        self.camera_manager = None
        self.person_detector = None
        self.coordinate_processor = None
        self.telemetry_client = None
        
        # Threads
        self.threads = []
        self.shutdown_event = threading.Event()
        
        # Statistics tracking
        self.stats_lock = threading.Lock()
        self.last_stats_time = time.time()
    
    def initialize_components(self) -> bool:
        """Initialize all system components"""
        try:
            self.logger.info("Initializing EdgeAgent components...")
            
            # Initialize camera manager
            self.camera_manager = CameraManager(
                camera_config=self.config.camera,
                frame_queue=self.frame_queue,
                shutdown_event=self.shutdown_event,
                use_mock=self.use_mock_camera
            )
            
            # Initialize person detector
            self.person_detector = PersonDetector(
                config=self.config,
                frame_queue=self.frame_queue,
                detection_queue=self.detection_queue,
                shutdown_event=self.shutdown_event
            )
            
            # Initialize coordinate processor
            self.coordinate_processor = CoordinateProcessor(
                camera_config=self.config.camera,
                detection_queue=self.detection_queue,
                coordinate_queue=self.coordinate_queue,
                shutdown_event=self.shutdown_event
            )
            
            # Initialize telemetry client
            self.telemetry_client = TelemetryClient(
                system_config=self.config,
                coordinate_queue=self.coordinate_queue,
                shutdown_event=self.shutdown_event
            )
            
            self.logger.info("All components initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}")
            return False
    
    def start_components(self) -> bool:
        """Start all component threads"""
        try:
            self.logger.info("Starting component threads...")
            
            # Start camera manager thread
            camera_thread = threading.Thread(
                target=self.camera_manager.run,
                name="CameraManager",
                daemon=True
            )
            camera_thread.start()
            self.threads.append(camera_thread)
            
            # Start person detector thread
            detector_thread = threading.Thread(
                target=self.person_detector.run,
                name="PersonDetector",
                daemon=True
            )
            detector_thread.start()
            self.threads.append(detector_thread)
            
            # Start coordinate processor thread
            coordinate_thread = threading.Thread(
                target=self.coordinate_processor.run,
                name="CoordinateProcessor",
                daemon=True
            )
            coordinate_thread.start()
            self.threads.append(coordinate_thread)
            
            # Start telemetry client thread
            telemetry_thread = threading.Thread(
                target=self.telemetry_client.run,
                name="TelemetryClient",
                daemon=True
            )
            telemetry_thread.start()
            self.threads.append(telemetry_thread)
            
            self.logger.info(f"Started {len(self.threads)} component threads")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start component threads: {e}")
            return False
    
    def start(self) -> bool:
        """Start the EdgeAgent system"""
        if self.running:
            self.logger.warning("EdgeAgent is already running")
            return False
            
        self.logger.info("Starting EdgeAgent system...")
        self.start_time = time.time()
        
        # Initialize components
        if not self.initialize_components():
            return False
            
        # Start component threads
        if not self.start_components():
            return False
            
        self.running = True
        self.logger.info("EdgeAgent system started successfully")
        return True
    
    def stop(self):
        """Stop the EdgeAgent system gracefully"""
        if not self.running:
            self.logger.warning("EdgeAgent is not running")
            return
            
        self.logger.info("Stopping EdgeAgent system...")
        self.running = False
        
        # Signal all threads to shutdown
        self.shutdown_event.set()
        
        # Wait for all threads to complete
        for thread in self.threads:
            thread.join(timeout=5.0)
            if thread.is_alive():
                self.logger.warning(f"Thread {thread.name} did not shutdown gracefully")
        
        # Clear queues
        self._clear_queues()
        
        # Log final statistics
        self._log_final_stats()
        
        self.logger.info("EdgeAgent system stopped")
    
    def _clear_queues(self):
        """Clear all inter-component queues"""
        queues = [self.frame_queue, self.detection_queue, self.coordinate_queue]
        for q in queues:
            while not q.empty():
                try:
                    q.get_nowait()
                except queue.Empty:
                    break
    
    def update_stats(self, stat_type: str, increment: int = 1):
        """Thread-safe statistics update"""
        with self.stats_lock:
            if stat_type == "frames_processed":
                self.stats.frames_processed += increment
            elif stat_type == "detections_made":
                self.stats.detections_made += increment
            elif stat_type == "coordinates_calculated":
                self.stats.coordinates_calculated += increment
            elif stat_type == "messages_sent":
                self.stats.messages_sent += increment
            elif stat_type == "errors_encountered":
                self.stats.errors_encountered += increment
    
    def get_stats(self) -> EdgeAgentStats:
        """Get current system statistics"""
        with self.stats_lock:
            if self.start_time:
                self.stats.uptime_seconds = time.time() - self.start_time
                if self.stats.uptime_seconds > 0:
                    self.stats.fps = self.stats.frames_processed / self.stats.uptime_seconds
            return self.stats
    
    def get_system_status(self) -> SystemStatus:
        """Get current system status for telemetry"""
        stats = self.get_stats()
        return SystemStatus(
            camera_status="operational" if self.running else "offline",
            processing_fps=stats.fps,
            cpu_usage=None,  # Could be implemented later
            memory_usage=None,  # Could be implemented later
            temperature=None  # Could be implemented later
        )
    
    def _log_final_stats(self):
        """Log final system statistics"""
        stats = self.get_stats()
        self.logger.info(f"Final Statistics:")
        self.logger.info(f"  Uptime: {stats.uptime_seconds:.1f} seconds")
        self.logger.info(f"  Frames processed: {stats.frames_processed}")
        self.logger.info(f"  Detections made: {stats.detections_made}")
        self.logger.info(f"  Coordinates calculated: {stats.coordinates_calculated}")
        self.logger.info(f"  Messages sent: {stats.messages_sent}")
        self.logger.info(f"  Errors encountered: {stats.errors_encountered}")
        self.logger.info(f"  Average FPS: {stats.fps:.2f}")
    
    def run_forever(self):
        """Run the EdgeAgent system indefinitely"""
        if not self.start():
            return False
            
        try:
            self.logger.info("EdgeAgent running. Press Ctrl+C to stop.")
            
            # Main monitoring loop
            while self.running:
                time.sleep(1.0)
                
                # Log statistics every 30 seconds
                current_time = time.time()
                if current_time - self.last_stats_time >= 30.0:
                    stats = self.get_stats()
                    self.logger.info(f"Stats - FPS: {stats.fps:.2f}, "
                                   f"Frames: {stats.frames_processed}, "
                                   f"Detections: {stats.detections_made}, "
                                   f"Messages: {stats.messages_sent}")
                    self.last_stats_time = current_time
                
                # Check for queue overflow
                if self.frame_queue.qsize() > self.config.frame_queue_size * 0.8:
                    self.logger.warning(f"Frame queue near capacity: {self.frame_queue.qsize()}")
                
        except KeyboardInterrupt:
            self.logger.info("Received interrupt signal")
        finally:
            self.stop()
            
        return True 