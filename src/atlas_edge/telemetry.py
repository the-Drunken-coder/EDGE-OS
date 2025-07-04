"""Telemetry data models and generation for ATLAS Edge Agent.

Provides data models for telemetry payloads and functions to generate
realistic mock telemetry data following the contract specified in
EDGE_AGENT_INTEGRATION.md and ATLAS_API_GUIDE.md.
"""
from __future__ import annotations

import random
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from .config import EdgeConfig


class TelemetryReading(BaseModel):
    """Individual telemetry reading."""
    
    metric_key: str = Field(description="Metric identifier")
    value: Union[float, int, str, bool] = Field(description="Metric value")
    unit: Optional[str] = Field(default=None, description="Unit of measurement")
    timestamp: Optional[datetime] = Field(default=None, description="Reading timestamp")
    
    def model_dump(self, **kwargs) -> dict[str, Any]:
        """Custom serialization to handle datetime formatting."""
        return {
            "metric_key": self.metric_key,
            "value": self.value,
            "unit": self.unit,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }


class TelemetryPayload(BaseModel):
    """Complete telemetry payload for POST to /api/v1/assets/{asset_id}/telemetry."""
    
    readings: List[TelemetryReading] = Field(description="List of telemetry readings")
    batch_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when batch was created"
    )
    
    def model_dump(self, **kwargs) -> dict[str, Any]:
        """Custom serialization to handle datetime formatting."""
        return {
            "readings": [reading.model_dump(**kwargs) for reading in self.readings],
            "batch_timestamp": self.batch_timestamp.isoformat()
        }


class BatchTelemetryPayload(BaseModel):
    """Batch telemetry payload for POST to /api/v1/assets/{asset_id}/telemetry/batch."""
    
    batches: List[TelemetryPayload] = Field(description="List of telemetry batches")
    
    def model_dump(self, **kwargs) -> dict[str, Any]:
        """Custom serialization to handle datetime formatting."""
        return {
            "batches": [batch.model_dump(**kwargs) for batch in self.batches]
        }


class MockTelemetryGenerator:
    """Generator for realistic mock telemetry data.
    
    Simulates various sensor readings with realistic drift, noise, and patterns.
    Supports both mobile assets (with GPS simulation) and stationary assets 
    (with fixed coordinates).
    """
    
    def __init__(self, asset_id: str, config: Optional[EdgeConfig] = None):
        """Initialize telemetry generator.
        
        Args:
            asset_id: Asset identifier for telemetry context
            config: Edge configuration for asset type and location settings
        """
        self.asset_id = asset_id
        self.config = config
        self._last_values = {
            "battery_voltage": 12.8,
            "solar_voltage": 18.2,
            "internal_temp": 25.0,
            "cpu_temp": 45.0,
            "memory_usage": 0.35,
            "cpu_usage": 0.15,
            "disk_usage": 0.42,
            "signal_strength": -65,
            "gps_latitude": 40.7589,
            "gps_longitude": -73.9851,
            "accelerometer_x": 0.0,
            "accelerometer_y": 0.0,
            "accelerometer_z": 9.81,
        }
        
        # Initialize GPS coordinates from config if available for stationary assets
        if (config and config.asset_type == "stationary" and 
            config.has_static_location()):
            self._last_values["gps_latitude"] = config.static_latitude
            self._last_values["gps_longitude"] = config.static_longitude
        
        self._random_seed = hash(asset_id) % 10000
        random.seed(self._random_seed)
    
    def _random_walk(self, current: float, min_val: float, max_val: float, step: float = 0.1) -> float:
        """Generate next value using random walk with bounds.
        
        Args:
            current: Current value
            min_val: Minimum allowed value
            max_val: Maximum allowed value
            step: Maximum step size
            
        Returns:
            Next value in the walk
        """
        delta = random.uniform(-step, step)
        new_value = current + delta
        return max(min_val, min(max_val, new_value))
    
    def _sine_wave(self, amplitude: float, frequency: float, offset: float = 0.0) -> float:
        """Generate sine wave value based on current time.
        
        Args:
            amplitude: Wave amplitude
            frequency: Wave frequency (cycles per hour)
            offset: Phase offset
            
        Returns:
            Sine wave value
        """
        import math
        t = time.time()
        return amplitude * math.sin(2 * math.pi * frequency * t / 3600 + offset)
    
    def generate_reading(self, metric_key: str, timestamp: Optional[datetime] = None) -> TelemetryReading:
        """Generate a single telemetry reading.
        
        Args:
            metric_key: Metric to generate
            timestamp: Reading timestamp (defaults to now)
            
        Returns:
            Generated telemetry reading
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        # Update stored values with realistic patterns
        if metric_key == "battery_voltage":
            # Battery voltage: slow decline with some noise
            self._last_values[metric_key] = self._random_walk(
                self._last_values[metric_key], 11.5, 13.2, 0.05
            )
            return TelemetryReading(
                metric_key=metric_key,
                value=round(self._last_values[metric_key], 2),
                unit="V",
                timestamp=timestamp
            )
        
        elif metric_key == "solar_voltage":
            # Solar voltage: follows daily pattern with weather noise
            base_voltage = 18.0 + self._sine_wave(4.0, 1.0)  # Daily cycle
            voltage = max(0, base_voltage + random.uniform(-2.0, 2.0))
            return TelemetryReading(
                metric_key=metric_key,
                value=round(voltage, 2),
                unit="V",
                timestamp=timestamp
            )
        
        elif metric_key == "internal_temp":
            # Internal temperature: daily cycle + slow drift
            base_temp = 22.0 + self._sine_wave(8.0, 1.0)  # Daily cycle
            self._last_values[metric_key] = self._random_walk(base_temp, 15.0, 35.0, 0.5)
            return TelemetryReading(
                metric_key=metric_key,
                value=round(self._last_values[metric_key], 1),
                unit="°C",
                timestamp=timestamp
            )
        
        elif metric_key == "cpu_temp":
            # CPU temperature: correlated with load and ambient
            base_temp = self._last_values["internal_temp"] + 15 + random.uniform(0, 10)
            self._last_values[metric_key] = self._random_walk(base_temp, 35.0, 75.0, 2.0)
            return TelemetryReading(
                metric_key=metric_key,
                value=round(self._last_values[metric_key], 1),
                unit="°C",
                timestamp=timestamp
            )
        
        elif metric_key == "memory_usage":
            # Memory usage: random walk with occasional spikes
            if random.random() < 0.05:  # 5% chance of spike
                target = random.uniform(0.7, 0.9)
            else:
                target = self._last_values[metric_key]
            self._last_values[metric_key] = self._random_walk(target, 0.1, 0.95, 0.05)
            return TelemetryReading(
                metric_key=metric_key,
                value=round(self._last_values[metric_key], 3),
                unit="%",
                timestamp=timestamp
            )
        
        elif metric_key == "cpu_usage":
            # CPU usage: bursty with occasional higher usage
            if random.random() < 0.1:  # 10% chance of burst
                target = random.uniform(0.6, 0.9)
            else:
                target = random.uniform(0.05, 0.25)
            self._last_values[metric_key] = self._random_walk(target, 0.01, 1.0, 0.1)
            return TelemetryReading(
                metric_key=metric_key,
                value=round(self._last_values[metric_key], 3),
                unit="%",
                timestamp=timestamp
            )
        
        elif metric_key == "signal_strength":
            # Signal strength: random walk in dBm range
            self._last_values[metric_key] = self._random_walk(
                self._last_values[metric_key], -90, -40, 3.0
            )
            return TelemetryReading(
                metric_key=metric_key,
                value=int(self._last_values[metric_key]),
                unit="dBm",
                timestamp=timestamp
            )
        
        elif metric_key in ["gps_latitude", "gps_longitude"]:
            # GPS coordinates: behavior depends on asset type
            if self.config and self.config.asset_type == "stationary":
                # Stationary assets: return fixed coordinates with minimal drift
                # to simulate GPS precision variations
                self._last_values[metric_key] = self._random_walk(
                    self._last_values[metric_key], 
                    self._last_values[metric_key] - 0.00001,  # ~1m precision
                    self._last_values[metric_key] + 0.00001,
                    0.000005
                )
            else:
                # Mobile assets: larger random walk for movement simulation
                self._last_values[metric_key] = self._random_walk(
                    self._last_values[metric_key], 
                    self._last_values[metric_key] - 0.001,
                    self._last_values[metric_key] + 0.001,
                    0.0001
                )
            
            return TelemetryReading(
                metric_key=metric_key,
                value=round(self._last_values[metric_key], 6),
                unit="deg",
                timestamp=timestamp
            )
        
        elif metric_key.startswith("accelerometer_"):
            # Accelerometer: mostly stable with small vibrations
            axis = metric_key.split("_")[1]
            if axis == "z":
                # Z-axis should be ~9.81 (gravity)
                base_value = 9.81
            else:
                # X and Y should be near 0
                base_value = 0.0
            
            self._last_values[metric_key] = self._random_walk(
                base_value, base_value - 0.5, base_value + 0.5, 0.1
            )
            return TelemetryReading(
                metric_key=metric_key,
                value=round(self._last_values[metric_key], 3),
                unit="m/s²",
                timestamp=timestamp
            )
        
        else:
            # Unknown metric: return a simple random value
            return TelemetryReading(
                metric_key=metric_key,
                value=round(random.uniform(0, 100), 2),
                unit="unit",
                timestamp=timestamp
            )
    
    def get_default_metrics(self) -> List[str]:
        """Get default metrics list based on asset type.
        
        Returns:
            List of default metrics for this asset type
        """
        base_metrics = [
            "battery_voltage",
            "solar_voltage", 
            "internal_temp",
            "cpu_temp",
            "memory_usage",
            "cpu_usage",
            "signal_strength",
        ]
        
        # Add GPS metrics based on asset type
        if (self.config and self.config.asset_type == "stationary" and 
            self.config.has_static_location()):
            # Stationary assets with configured location: include GPS
            base_metrics.extend(["gps_latitude", "gps_longitude"])
        elif not self.config or self.config.asset_type == "mobile":
            # Mobile assets: always include GPS
            base_metrics.extend(["gps_latitude", "gps_longitude"])
        
        return base_metrics
    
    def generate_telemetry_batch(
        self,
        metrics: Optional[List[str]] = None,
        timestamp: Optional[datetime] = None
    ) -> TelemetryPayload:
        """Generate a complete telemetry batch.
        
        Args:
            metrics: List of metrics to include (uses default set if None)
            timestamp: Batch timestamp (defaults to now)
            
        Returns:
            Complete telemetry payload
        """
        if metrics is None:
            metrics = self.get_default_metrics()
        
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        readings = [self.generate_reading(metric, timestamp) for metric in metrics]
        
        return TelemetryPayload(
            readings=readings,
            batch_timestamp=timestamp
        ) 