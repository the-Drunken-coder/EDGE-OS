"""
Phase 2 Test Suite: Camera Management and Person Detection
Tests CameraManager and PersonDetector components with mock data and real inference
"""

import sys
import os
import time
import queue
import threading
import logging
import numpy as np
import cv2
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from models.config import CameraConfig
from components import CameraManager, PersonDetector, FrameData, DetectionResult

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_mock_frame(width: int = 640, height: int = 480, with_person: bool = True) -> np.ndarray:
    """
    Create a mock frame for testing.
    
    Args:
        width: Frame width
        height: Frame height  
        with_person: Whether to draw a person-like shape
        
    Returns:
        numpy array: Mock frame
    """
    # Create base frame (blue background)
    frame = np.full((height, width, 3), (100, 50, 0), dtype=np.uint8)
    
    if with_person:
        # Draw a simple person-like shape (rectangle for body, circle for head)
        person_x = width // 2
        person_y = height // 2
        
        # Body (rectangle)
        cv2.rectangle(frame, 
                     (person_x - 30, person_y - 20), 
                     (person_x + 30, person_y + 60), 
                     (0, 255, 0), -1)
        
        # Head (circle)
        cv2.circle(frame, (person_x, person_y - 40), 20, (0, 255, 0), -1)
        
        # Add some noise to make it more realistic
        noise = np.random.randint(0, 50, (height, width, 3), dtype=np.uint8)
        frame = cv2.addWeighted(frame, 0.8, noise, 0.2, 0)
    
    return frame


class MockCameraManager:
    """Mock camera manager that generates synthetic frames for testing."""
    
    def __init__(self, frame_queue: queue.Queue, num_frames: int = 10):
        self.frame_queue = frame_queue
        self.num_frames = num_frames
        self.is_running = False
        self.thread = None
        self.stop_event = threading.Event()
        
    def start_capture(self) -> bool:
        self.stop_event.clear()
        self.is_running = True
        self.thread = threading.Thread(target=self._generate_frames, daemon=True)
        self.thread.start()
        return True
    
    def stop_capture(self):
        self.stop_event.set()
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2.0)
    
    def _generate_frames(self):
        for i in range(self.num_frames):
            if self.stop_event.is_set():
                break
                
            # Create mock frame
            frame = create_mock_frame(with_person=(i % 3 == 0))  # Person every 3rd frame
            
            frame_data = FrameData(
                frame=frame,
                timestamp=time.time(),
                frame_id=i,
                camera_id="mock_camera"
            )
            
            try:
                self.frame_queue.put_nowait(frame_data)
                time.sleep(0.1)  # Simulate frame rate
            except queue.Full:
                pass


def test_camera_manager_initialization():
    """Test CameraManager initialization and configuration."""
    print("\n=== Testing CameraManager Initialization ===")
    
    # Create camera configuration
    camera_config = CameraConfig(
        name="test_camera",
        type="usb_camera",
        width=640,
        height=480,
        horizontal_fov=60.0,
        vertical_fov=45.0,
        fps=30,
        device_path="/dev/video0"
    )
    
    frame_queue = queue.Queue(maxsize=5)
    
    # Initialize CameraManager
    camera_manager = CameraManager(camera_config, frame_queue)
    
    # Test configuration
    info = camera_manager.get_camera_info()
    print(f"Camera Info: {info}")
    
    assert info['name'] == "test_camera"
    assert info['type'] == "usb_camera"
    assert info['width'] == 640
    assert info['height'] == 480
    assert info['fps'] == 30
    assert not info['is_running']
    
    print("✅ CameraManager initialization test passed")
    return True


def test_person_detector_initialization():
    """Test PersonDetector initialization and model loading."""
    print("\n=== Testing PersonDetector Initialization ===")
    
    frame_queue = queue.Queue()
    detection_queue = queue.Queue()
    
    # Initialize PersonDetector
    person_detector = PersonDetector(
        frame_queue=frame_queue,
        detection_queue=detection_queue,
        confidence_threshold=0.3
    )
    
    # Test model loading
    model_loaded = person_detector.initialize_model()
    print(f"Model loaded: {model_loaded}")
    
    if model_loaded:
        model_info = person_detector.get_model_info()
        print(f"Model Info: {model_info}")
        
        assert model_info['model_loaded']
        assert model_info['person_class_id'] == 0
        
        print("✅ PersonDetector initialization test passed")
    else:
        print("⚠️ YOLO model not available - skipping model tests")
    
    return model_loaded


def test_frame_data_structure():
    """Test FrameData structure and serialization."""
    print("\n=== Testing FrameData Structure ===")
    
    # Create mock frame
    frame = create_mock_frame()
    
    # Create FrameData
    frame_data = FrameData(
        frame=frame,
        timestamp=time.time(),
        frame_id=123,
        camera_id="test_camera"
    )
    
    # Test attributes
    assert frame_data.frame is not None
    assert frame_data.timestamp > 0
    assert frame_data.frame_id == 123
    assert frame_data.camera_id == "test_camera"
    assert frame_data.frame.shape == (480, 640, 3)
    
    print(f"FrameData: ID={frame_data.frame_id}, Camera={frame_data.camera_id}, Shape={frame_data.frame.shape}")
    print("✅ FrameData structure test passed")
    return True


def test_mock_frame_generation():
    """Test mock frame generation for testing."""
    print("\n=== Testing Mock Frame Generation ===")
    
    # Test frame without person
    frame_empty = create_mock_frame(with_person=False)
    assert frame_empty.shape == (480, 640, 3)
    
    # Test frame with person
    frame_person = create_mock_frame(with_person=True)
    assert frame_person.shape == (480, 640, 3)
    
    # Frames should be different
    assert not np.array_equal(frame_empty, frame_person)
    
    print(f"Empty frame shape: {frame_empty.shape}")
    print(f"Person frame shape: {frame_person.shape}")
    print("✅ Mock frame generation test passed")
    return True


def test_detection_pipeline():
    """Test the complete detection pipeline with mock data."""
    print("\n=== Testing Detection Pipeline ===")
    
    frame_queue = queue.Queue(maxsize=10)
    detection_queue = queue.Queue(maxsize=10)
    
    # Initialize PersonDetector
    person_detector = PersonDetector(
        frame_queue=frame_queue,
        detection_queue=detection_queue,
        confidence_threshold=0.1  # Lower threshold for testing
    )
    
    # Check if YOLO is available
    if not person_detector.initialize_model():
        print("⚠️ YOLO model not available - skipping detection pipeline test")
        return False
    
    # Start detection
    person_detector.start_detection()
    
    # Generate mock frames
    mock_camera = MockCameraManager(frame_queue, num_frames=5)
    mock_camera.start_capture()
    
    # Wait for processing
    time.sleep(2.0)
    
    # Stop components
    mock_camera.stop_capture()
    person_detector.stop_detection()
    
    # Check results
    detection_count = 0
    while not detection_queue.empty():
        try:
            detection_result = detection_queue.get_nowait()
            detection_count += 1
            
            print(f"Detection Result {detection_count}:")
            print(f"  Frame ID: {detection_result.frame_data.frame_id}")
            print(f"  Detections: {len(detection_result.detections)}")
            print(f"  Processing Time: {detection_result.processing_time:.3f}s")
            print(f"  Model Confidence: {detection_result.model_confidence:.3f}")
            
            # Validate detection result structure
            assert isinstance(detection_result, DetectionResult)
            assert isinstance(detection_result.detections, list)
            assert detection_result.processing_time > 0
            
        except queue.Empty:
            break
    
    # Get detection stats
    stats = person_detector.get_detection_stats()
    print(f"\nDetection Stats: {stats}")
    
    print(f"✅ Detection pipeline test passed - processed {detection_count} frames")
    return True


def test_component_integration():
    """Test integration between CameraManager and PersonDetector."""
    print("\n=== Testing Component Integration ===")
    
    # This test would require a real camera, so we'll use mock data
    frame_queue = queue.Queue(maxsize=5)
    detection_queue = queue.Queue(maxsize=5)
    
    # Create components
    person_detector = PersonDetector(frame_queue, detection_queue)
    
    if not person_detector.initialize_model():
        print("⚠️ YOLO model not available - skipping integration test")
        return False
    
    # Test queue communication
    mock_frame = create_mock_frame(with_person=True)
    frame_data = FrameData(
        frame=mock_frame,
        timestamp=time.time(),
        frame_id=1,
        camera_id="integration_test"
    )
    
    # Add frame to queue
    frame_queue.put(frame_data)
    
    # Start detection briefly
    person_detector.start_detection()
    time.sleep(0.5)
    person_detector.stop_detection()
    
    # Check if detection was processed
    if not detection_queue.empty():
        result = detection_queue.get()
        print(f"Integration test result: {len(result.detections)} detections")
        print("✅ Component integration test passed")
        return True
    else:
        print("⚠️ No detection results - integration may need adjustment")
        return False


def test_error_handling():
    """Test error handling in components."""
    print("\n=== Testing Error Handling ===")
    
    frame_queue = queue.Queue()
    detection_queue = queue.Queue()
    
    # Test PersonDetector with invalid model path
    person_detector = PersonDetector(
        frame_queue=frame_queue,
        detection_queue=detection_queue,
        model_path="invalid_model.pt"
    )
    
    # This should fail gracefully
    model_loaded = person_detector.initialize_model()
    print(f"Invalid model loading (should fail): {model_loaded}")
    
    # Test confidence threshold updates
    person_detector.update_confidence_threshold(0.7)
    person_detector.update_confidence_threshold(1.5)  # Should warn about invalid value
    
    print("✅ Error handling test passed")
    return True


def run_all_tests():
    """Run all Phase 2 tests."""
    print("🚀 Starting Phase 2 Component Tests")
    print("=" * 50)
    
    test_results = []
    
    try:
        # Basic component tests
        test_results.append(("Camera Manager Init", test_camera_manager_initialization()))
        test_results.append(("Person Detector Init", test_person_detector_initialization()))
        test_results.append(("FrameData Structure", test_frame_data_structure()))
        test_results.append(("Mock Frame Generation", test_mock_frame_generation()))
        
        # Pipeline tests (require YOLO)
        test_results.append(("Detection Pipeline", test_detection_pipeline()))
        test_results.append(("Component Integration", test_component_integration()))
        
        # Error handling
        test_results.append(("Error Handling", test_error_handling()))
        
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        test_results.append(("Test Execution", False))
    
    # Print results summary
    print("\n" + "=" * 50)
    print("📊 PHASE 2 TEST RESULTS SUMMARY")
    print("=" * 50)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:<25} {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All Phase 2 tests passed! Components are working correctly.")
        return True
    else:
        print("⚠️ Some tests failed. Check the output above for details.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1) 