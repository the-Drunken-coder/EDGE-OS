#!/usr/bin/env python3
"""
Test script for Phase 1: Foundation Setup

Tests the core data models, configuration system, and coordinate calculator
to verify the foundation is working correctly before proceeding to Phase 2.
"""

import sys
import os
import json
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from models.config import SystemConfig, CameraConfig
from models.telemetry import TelemetryMessage, Detection, BoundingBox, SpatialCoordinates, SystemStatus
from components.coordinate_calculator import CoordinateCalculator


def test_configuration_system():
    """Test configuration loading and creation."""
    print("🔧 Testing Configuration System...")
    
    # Test default configuration creation
    config = SystemConfig.create_default("TEST_CAM_001")
    print(f"✅ Default config created: {config.asset_id}")
    
    # Test JSON serialization
    config_dict = config.to_dict()
    print(f"✅ Config serialized to dict: {len(config_dict)} fields")
    
    # Test file operations
    config_file = "config/test_config.json"
    config.to_json_file(config_file)
    print(f"✅ Config saved to {config_file}")
    
    # Test loading from file
    loaded_config = SystemConfig.from_json_file(config_file)
    print(f"✅ Config loaded from file: {loaded_config.asset_id}")
    
    # Verify loaded config matches original
    assert loaded_config.asset_id == config.asset_id
    assert loaded_config.camera.width == config.camera.width
    print("✅ Configuration system test passed!")
    
    return loaded_config


def test_telemetry_models():
    """Test telemetry data models and JSON serialization."""
    print("\n📊 Testing Telemetry Models...")
    
    # Create test detection data
    bbox = BoundingBox(x=320, y=240, width=80, height=160)
    spatial = SpatialCoordinates(bearing=15.2, elevation=-2.1)
    detection = Detection(
        type="person",
        confidence=0.87,
        spatial=spatial,
        bounding_box=bbox,
        track_id="track_001"
    )
    
    # Create system status
    status = SystemStatus(
        camera_status="operational",
        processing_fps=12.5,
        cpu_usage=45.2,
        memory_usage=128.5
    )
    
    # Create complete telemetry message
    telemetry = TelemetryMessage(
        timestamp=datetime.utcnow(),
        asset_id="TEST_CAM_001",
        system_status=status,
        detections=[detection]
    )
    
    # Test JSON serialization
    json_dict = telemetry.to_json()
    print(f"✅ Telemetry serialized to JSON: {len(json_dict)} top-level fields")
    
    json_string = telemetry.to_json_string()
    print(f"✅ JSON string created: {len(json_string)} characters")
    
    # Test deserialization
    reconstructed = TelemetryMessage.from_dict(json_dict)
    print(f"✅ Telemetry reconstructed: {len(reconstructed.detections)} detections")
    
    # Verify data integrity
    assert reconstructed.asset_id == telemetry.asset_id
    assert len(reconstructed.detections) == 1
    assert reconstructed.detections[0].confidence == 0.87
    print("✅ Telemetry models test passed!")
    
    return telemetry


def test_coordinate_calculator(config: SystemConfig):
    """Test coordinate calculation algorithms."""
    print("\n📐 Testing Coordinate Calculator...")
    
    # Initialize calculator with camera config
    calculator = CoordinateCalculator(config.camera)
    print(f"✅ Calculator initialized: {calculator.frame_width}x{calculator.frame_height}")
    
    # Test performance info
    perf_info = calculator.get_performance_info()
    print(f"✅ Performance info: {perf_info['expected_accuracy']}")
    
    # Test FOV calculation
    fov_info = calculator.get_field_of_view()
    print(f"✅ FOV calculated: H={fov_info['horizontal_fov']:.1f}°, V={fov_info['vertical_fov']:.1f}°")
    
    # Test coordinate calculations with various positions
    test_cases = [
        # (description, x, y, width, height)
        ("Center of frame", 320, 240, 80, 160),
        ("Top-left quadrant", 160, 120, 60, 120),
        ("Top-right quadrant", 480, 120, 60, 120),
        ("Bottom-left quadrant", 160, 360, 60, 120),
        ("Bottom-right quadrant", 480, 360, 60, 120),
    ]
    
    print("\n📍 Testing coordinate calculations:")
    for description, x, y, w, h in test_cases:
        bbox = BoundingBox(x=x, y=y, width=w, height=h)
        
        try:
            coords = calculator.calculate_coordinates(bbox)
            print(f"  {description}: ({x}, {y}) -> "
                  f"bearing={coords.bearing:.2f}°, elevation={coords.elevation:.2f}°")
        except Exception as e:
            print(f"  ❌ {description}: Failed - {e}")
            return False
    
    # Test edge cases
    print("\n🔍 Testing edge cases:")
    
    # Test invalid bounding box (should raise ValueError)
    try:
        invalid_bbox = BoundingBox(x=-10, y=-10, width=50, height=50)
        calculator.calculate_coordinates(invalid_bbox)
        print("  ❌ Invalid bbox test failed - should have raised ValueError")
        return False
    except ValueError:
        print("  ✅ Invalid bbox correctly rejected")
    
    # Test extreme coordinates
    try:
        extreme_bbox = BoundingBox(x=0, y=0, width=10, height=10)
        coords = calculator.calculate_coordinates(extreme_bbox)
        print(f"  ✅ Extreme coordinates: bearing={coords.bearing:.2f}°, elevation={coords.elevation:.2f}°")
    except Exception as e:
        print(f"  ❌ Extreme coordinates failed: {e}")
        return False
    
    print("✅ Coordinate calculator test passed!")
    return True


def test_integration():
    """Test integration between components."""
    print("\n🔗 Testing Component Integration...")
    
    # Load configuration
    config = SystemConfig.from_json_file("config/system_config.json")
    
    # Initialize calculator
    calculator = CoordinateCalculator(config.camera)
    
    # Create detection
    bbox = BoundingBox(x=300, y=200, width=100, height=200)
    coords = calculator.calculate_coordinates(bbox)
    
    # Create complete detection object
    detection = Detection(
        type="person",
        confidence=0.92,
        spatial=coords,
        bounding_box=bbox
    )
    
    # Create telemetry message
    status = SystemStatus(
        camera_status="operational",
        processing_fps=15.3
    )
    
    telemetry = TelemetryMessage(
        timestamp=datetime.utcnow(),
        asset_id=config.asset_id,
        system_status=status,
        detections=[detection]
    )
    
    # Test complete pipeline
    json_output = telemetry.to_json_string()
    print(f"✅ Complete pipeline: {len(json_output)} byte payload")
    
    # Verify ATLAS-compatible format
    parsed = json.loads(json_output)
    assert "timestamp" in parsed
    assert "asset_id" in parsed
    assert "system_status" in parsed
    assert "detections" in parsed
    assert len(parsed["detections"]) == 1
    assert "spatial" in parsed["detections"][0]
    assert "bearing" in parsed["detections"][0]["spatial"]
    
    print("✅ Integration test passed!")
    return True


def main():
    """Run all Phase 1 tests."""
    print("🚀 PHASE 1 FOUNDATION SETUP TESTS")
    print("=" * 50)
    
    try:
        # Test individual components
        config = test_configuration_system()
        telemetry = test_telemetry_models()
        calculator_ok = test_coordinate_calculator(config)
        integration_ok = test_integration()
        
        # Summary
        print("\n" + "=" * 50)
        if calculator_ok and integration_ok:
            print("🎉 ALL PHASE 1 TESTS PASSED!")
            print("✅ Foundation setup complete")
            print("✅ Data models working correctly")
            print("✅ Configuration system functional")
            print("✅ Coordinate calculator operational")
            print("✅ Component integration successful")
            print("\n➡️  Ready to proceed to Phase 2: Person Detection Core")
            return True
        else:
            print("❌ Some tests failed - resolve issues before proceeding")
            return False
            
    except Exception as e:
        print(f"\n❌ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 