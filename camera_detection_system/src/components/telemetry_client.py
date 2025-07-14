"""
TelemetryClient - Consumer component for ATLAS API communication
Processes coordinate results and sends formatted telemetry messages to ATLAS
"""

import threading
import queue
import time
import logging
import requests
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime

from .coordinate_processor import CoordinateResult
from models.telemetry import TelemetryMessage, SystemStatus
from models.config import SystemConfig


@dataclass
class TelemetryResult:
    """Container for telemetry transmission results"""
    success: bool
    status_code: Optional[int]
    response_data: Optional[Dict[str, Any]]
    error_message: Optional[str]
    transmission_time: float
    payload_size: int


class TelemetryClient:
    """
    Consumer component that processes coordinate results and sends telemetry to ATLAS API.
    Handles message formatting, transmission, retry logic, and error handling.
    """
    
    def __init__(self, 
                 coordinate_queue: queue.Queue,
                 system_config: SystemConfig,
                 shutdown_event: threading.Event,
                 transmission_interval: float = 1.0,
                 max_retry_attempts: int = 3,
                 timeout: float = 10.0):
        """
        Initialize TelemetryClient with configuration and transmission settings.
        
        Args:
            coordinate_queue: Input queue for coordinate results
            system_config: System configuration with ATLAS API details
            shutdown_event: Event to signal shutdown
            transmission_interval: Minimum seconds between transmissions
            max_retry_attempts: Maximum retry attempts for failed transmissions
            timeout: Request timeout in seconds
        """
        self.coordinate_queue = coordinate_queue
        self.system_config = system_config
        self.transmission_interval = transmission_interval
        self.max_retry_attempts = max_retry_attempts
        self.timeout = timeout
        
        # Transmission state
        self.is_running = False
        self.transmission_thread = None
        
        # Performance tracking
        self.transmitted_count = 0
        self.successful_transmissions = 0
        self.failed_transmissions = 0
        self.total_transmission_time = 0.0
        self.total_payload_size = 0
        self.last_transmission_time = 0
        self.last_successful_transmission = 0
        
        # Retry tracking
        self.retry_queue = queue.Queue()
        self.consecutive_failures = 0
        
        # Thread synchronization
        self.stop_event = shutdown_event
        self.lock = threading.Lock()
        
        # Logging
        self.logger = logging.getLogger(__name__)
        
        # HTTP session for connection reuse
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': f'ATLAS-Edge-Agent/{system_config.asset_id}'
        })
        
    def run(self):
        """Main transmission loop for the telemetry client thread."""
        self.is_running = True
        self.logger.info("Telemetry transmission loop started")
        
        last_transmission = 0
        
        while not self.stop_event.is_set():
            try:
                current_time = time.time()
                
                # Check if it's time for next transmission
                if current_time - last_transmission < self.transmission_interval:
                    time.sleep(0.1)  # Small sleep to prevent busy waiting
                    continue
                
                # Process retry queue first
                self._process_retry_queue()
                
                # Collect coordinate results for transmission
                coordinate_results = self._collect_coordinate_results()
                
                if coordinate_results:
                    # Create and send telemetry message
                    telemetry_result = self._send_telemetry(coordinate_results)
                    
                    if telemetry_result.success:
                        self.consecutive_failures = 0
                        last_transmission = current_time
                        
                        with self.lock:
                            self.successful_transmissions += 1
                            self.last_successful_transmission = current_time
                    else:
                        self.consecutive_failures += 1
                        
                        # Add to retry queue if not too many failures
                        if self.consecutive_failures <= self.max_retry_attempts:
                            self.retry_queue.put((coordinate_results, 1))
                        
                        with self.lock:
                            self.failed_transmissions += 1
                    
                    with self.lock:
                        self.transmitted_count += 1
                        self.total_transmission_time += telemetry_result.transmission_time
                        self.total_payload_size += telemetry_result.payload_size
                        self.last_transmission_time = current_time
                
            except Exception as e:
                self.logger.error(f"Error in transmission loop: {e}")
                time.sleep(1.0)  # Longer pause on error
                
        self.session.close()
        self.is_running = False
        self.logger.info("Telemetry transmission loop ended")
    
    def _collect_coordinate_results(self) -> List[CoordinateResult]:
        """
        Collect available coordinate results from queue.
        
        Returns:
            List[CoordinateResult]: List of coordinate results to transmit
        """
        results = []
        
        # Collect all available results (non-blocking)
        while not self.coordinate_queue.empty():
            try:
                coordinate_result = self.coordinate_queue.get_nowait()
                results.append(coordinate_result)
                self.coordinate_queue.task_done()
            except queue.Empty:
                break
        
        return results
    
    def _send_telemetry(self, coordinate_results: List[CoordinateResult]) -> TelemetryResult:
        """
        Create and send telemetry message to ATLAS API.
        
        Args:
            coordinate_results: List of coordinate results to include
            
        Returns:
            TelemetryResult: Result of transmission attempt
        """
        start_time = time.time()
        
        try:
            # Create telemetry message
            telemetry_message = self._create_telemetry_message(coordinate_results)
            
            # Convert to JSON
            payload = telemetry_message.to_json_string()
            payload_size = len(payload.encode('utf-8'))
            
            # Send to ATLAS API
            response = self.session.post(
                self.system_config.atlas_api_url,
                data=payload,
                timeout=self.timeout
            )
            
            transmission_time = time.time() - start_time
            
            # Check response
            if response.status_code == 200:
                self.logger.info(f"Telemetry sent successfully: {len(coordinate_results)} frames, "
                               f"{sum(len(cr.detections) for cr in coordinate_results)} detections")
                
                try:
                    response_data = response.json()
                except:
                    response_data = {"status": "success"}
                
                return TelemetryResult(
                    success=True,
                    status_code=response.status_code,
                    response_data=response_data,
                    error_message=None,
                    transmission_time=transmission_time,
                    payload_size=payload_size
                )
            else:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                self.logger.warning(f"Telemetry transmission failed: {error_msg}")
                
                return TelemetryResult(
                    success=False,
                    status_code=response.status_code,
                    response_data=None,
                    error_message=error_msg,
                    transmission_time=transmission_time,
                    payload_size=payload_size
                )
                
        except requests.exceptions.Timeout:
            error_msg = f"Request timeout after {self.timeout}s"
            self.logger.warning(f"Telemetry transmission timeout: {error_msg}")
            
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection error: {str(e)[:200]}"
            self.logger.warning(f"Telemetry transmission connection error: {error_msg}")
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)[:200]}"
            self.logger.error(f"Telemetry transmission error: {error_msg}")
        
        transmission_time = time.time() - start_time
        
        return TelemetryResult(
            success=False,
            status_code=None,
            response_data=None,
            error_message=error_msg,
            transmission_time=transmission_time,
            payload_size=0
        )
    
    def _create_telemetry_message(self, coordinate_results: List[CoordinateResult]) -> TelemetryMessage:
        """
        Create ATLAS-compatible telemetry message from coordinate results.
        
        Args:
            coordinate_results: List of coordinate results
            
        Returns:
            TelemetryMessage: Formatted telemetry message
        """
        # Aggregate all detections from all frames
        all_detections = []
        total_processing_time = 0.0
        
        for result in coordinate_results:
            all_detections.extend(result.detections)
            total_processing_time += result.processing_time
        
        # Calculate system performance metrics
        avg_processing_time = total_processing_time / len(coordinate_results) if coordinate_results else 0.0
        processing_fps = 1.0 / avg_processing_time if avg_processing_time > 0 else 0.0
        
        # Create system status
        system_status = SystemStatus(
            camera_status="operational" if self.consecutive_failures < 3 else "degraded",
            processing_fps=processing_fps,
            cpu_usage=None,  # Could be added with psutil
            memory_usage=None,  # Could be added with psutil
            temperature=None  # Could be added with hardware monitoring
        )
        
        # Create telemetry message
        telemetry_message = TelemetryMessage(
            timestamp=datetime.utcnow(),
            asset_id=self.system_config.asset_id,
            system_status=system_status,
            detections=all_detections
        )
        
        return telemetry_message
    
    def _process_retry_queue(self):
        """Process failed transmissions in retry queue."""
        retry_items = []
        
        # Collect retry items
        while not self.retry_queue.empty():
            try:
                retry_items.append(self.retry_queue.get_nowait())
            except queue.Empty:
                break
        
        # Process retry items
        for coordinate_results, attempt_count in retry_items:
            if attempt_count <= self.max_retry_attempts:
                self.logger.info(f"Retrying telemetry transmission (attempt {attempt_count})")
                
                telemetry_result = self._send_telemetry(coordinate_results)
                
                if telemetry_result.success:
                    self.logger.info(f"Retry successful on attempt {attempt_count}")
                    with self.lock:
                        self.successful_transmissions += 1
                else:
                    # Re-queue for another retry
                    if attempt_count < self.max_retry_attempts:
                        self.retry_queue.put((coordinate_results, attempt_count + 1))
                    else:
                        self.logger.error(f"Max retry attempts reached, dropping telemetry data")
    
    def get_transmission_stats(self) -> Dict[str, Any]:
        """
        Get telemetry transmission statistics.
        
        Returns:
            dict: Transmission statistics and performance metrics
        """
        with self.lock:
            avg_transmission_time = (self.total_transmission_time / self.transmitted_count 
                                   if self.transmitted_count > 0 else 0.0)
            avg_payload_size = (self.total_payload_size / self.transmitted_count 
                              if self.transmitted_count > 0 else 0.0)
            success_rate = (self.successful_transmissions / self.transmitted_count 
                          if self.transmitted_count > 0 else 0.0)
            
            return {
                'is_running': self.is_running,
                'transmitted_count': self.transmitted_count,
                'successful_transmissions': self.successful_transmissions,
                'failed_transmissions': self.failed_transmissions,
                'success_rate': success_rate,
                'consecutive_failures': self.consecutive_failures,
                'average_transmission_time': avg_transmission_time,
                'average_payload_size': avg_payload_size,
                'last_transmission_time': self.last_transmission_time,
                'last_successful_transmission': self.last_successful_transmission,
                'retry_queue_size': self.retry_queue.qsize(),
                'coordinate_queue_size': self.coordinate_queue.qsize(),
                'atlas_api_url': self.system_config.atlas_api_url
            }
    
    def get_connection_info(self) -> Dict[str, Any]:
        """
        Get connection and configuration information.
        
        Returns:
            dict: Connection information
        """
        return {
            'atlas_api_url': self.system_config.atlas_api_url,
            'asset_id': self.system_config.asset_id,
            'transmission_interval': self.transmission_interval,
            'max_retry_attempts': self.max_retry_attempts,
            'timeout': self.timeout,
            'session_active': hasattr(self.session, '_adapter_cache')
        }
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Test connection to ATLAS API.
        
        Returns:
            dict: Connection test results
        """
        try:
            # Send a simple GET request to test connectivity
            test_url = self.system_config.atlas_api_url.rstrip('/') + '/health'
            
            start_time = time.time()
            response = self.session.get(test_url, timeout=self.timeout)
            response_time = time.time() - start_time
            
            return {
                'success': True,
                'status_code': response.status_code,
                'response_time': response_time,
                'url': test_url,
                'error': None
            }
            
        except Exception as e:
            return {
                'success': False,
                'status_code': None,
                'response_time': None,
                'url': test_url if 'test_url' in locals() else self.system_config.atlas_api_url,
                'error': str(e)
            }
    
    def __enter__(self):
        """Context manager entry."""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensure cleanup."""
        self.stop_transmission() 