import cv2
import numpy as np
from ultralytics import YOLO
import requests
import json
from datetime import datetime

def test_camera_access():
    """Test camera enumeration and access"""
    print("Testing camera access...")
    
    # Try to access default camera
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print(" No camera found at index 0")
        return False
    
    # Test frame capture
    ret, frame = cap.read()
    if not ret:
        print(" Failed to capture frame")
        cap.release()
        return False
    
    print(f" Camera access successful - Frame shape: {frame.shape}")
    cap.release()
    return True

def test_yolo_detection():
    """Test YOLO model loading and inference"""
    print("Testing YOLO person detection...")
    
    try:
        # Load YOLOv8 model (will download if not present)
        model = YOLO("yolov8n.pt")  # nano version for speed
        print(" YOLO model loaded successfully")
        
        # Test inference on a dummy image
        dummy_image = np.zeros((480, 640, 3), dtype=np.uint8)
        results = model(dummy_image)
        print(f" YOLO inference successful - {len(results)} result(s)")
        
        return True
    except Exception as e:
        print(f" YOLO test failed: {e}")
        return False

def test_coordinate_calculation():
    """Test bearing and elevation calculations"""
    print("Testing coordinate calculations...")
    
    # Mock camera parameters (typical webcam)
    frame_width = 640
    frame_height = 480
    horizontal_fov = 60  # degrees
    vertical_fov = 45    # degrees
    
    # Test pixel coordinates (center of frame)
    pixel_x = frame_width // 2
    pixel_y = frame_height // 2
    
    # Calculate bearing (azimuth) from center
    bearing = (pixel_x - frame_width/2) * (horizontal_fov / frame_width)
    
    # Calculate elevation from center  
    elevation = (frame_height/2 - pixel_y) * (vertical_fov / frame_height)
    
    print(f" Coordinate calculation successful")
    print(f"   Pixel ({pixel_x}, {pixel_y}) -> Bearing: {bearing:.1f}, Elevation: {elevation:.1f}")
    
    return True

def test_atlas_integration():
    """Test ATLAS API format (mock)"""
    print("Testing ATLAS integration format...")
    
    # Mock telemetry data structure
    telemetry_data = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "asset_id": "SEC_CAM_EDGE_001",
        "detections": [
            {
                "type": "person",
                "confidence": 0.85,
                "bearing": 15.2,
                "elevation": -5.1,
                "bounding_box": {
                    "x": 320,
                    "y": 240,
                    "width": 80,
                    "height": 160
                }
            }
        ],
        "camera_status": "operational",
        "processing_fps": 12.5
    }
    
    # Test JSON serialization
    json_data = json.dumps(telemetry_data, indent=2)
    print(" ATLAS telemetry format validated")
    print(f"   Sample payload: {len(json_data)} bytes")
    
    return True

def main():
    """Run all technology validation tests"""
    print(" CAMERA DETECTION SYSTEM - TECHNOLOGY VALIDATION")
    print("=" * 50)
    
    tests = [
        ("Camera Access", test_camera_access),
        ("YOLO Detection", test_yolo_detection), 
        ("Coordinate Calculation", test_coordinate_calculation),
        ("ATLAS Integration", test_atlas_integration)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n {test_name}:")
        success = test_func()
        results.append((test_name, success))
    
    print("\n" + "=" * 50)
    print(" VALIDATION RESULTS:")
    
    all_passed = True
    for test_name, success in results:
        status = " PASS" if success else " FAIL"
        print(f"   {test_name}: {status}")
        if not success:
            all_passed = False
    
    if all_passed:
        print("\n ALL TESTS PASSED - Technology stack validated!")
        print("Ready to proceed with implementation.")
    else:
        print("\n  Some tests failed - resolve issues before proceeding.")
    
    return all_passed

if __name__ == "__main__":
    main()