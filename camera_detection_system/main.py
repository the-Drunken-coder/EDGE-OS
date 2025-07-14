#!/usr/bin/env python3
"""
Main entry point for the Camera Detection and Person Tracking System.
This script initializes and runs the EdgeAgent orchestrator.
"""

import sys
import os
import argparse
import logging

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from models.config import SystemConfig
from components.edge_agent import EdgeAgent


def setup_logging(log_level: str = "INFO"):
    """Setup logging configuration"""
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/main.log'),
            logging.StreamHandler()
        ]
    )


def main():
    """Main application entry point"""
    parser = argparse.ArgumentParser(
        description="Camera Detection and Person Tracking System"
    )
    parser.add_argument(
        "--config", 
        default="config/system_config.json",
        help="Path to system configuration file"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )
    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="Run in test mode (shorter duration)"
    )
    parser.add_argument(
        "--mock-camera",
        action="store_true",
        help="Use mock camera for development testing (no hardware required)"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, "config", "system_config.json")
        logger.info(f"Loading configuration from: {config_path}")
        config = SystemConfig.from_json_file(config_path)
        
        # Create and run EdgeAgent
        logger.info("Creating EdgeAgent...")
        edge_agent = EdgeAgent(config, use_mock_camera=args.mock_camera)
        
        if args.test_mode:
            logger.info("Running in test mode for 30 seconds...")
            if edge_agent.start():
                import time
                time.sleep(30)
                edge_agent.stop()
        else:
            logger.info("Starting EdgeAgent system...")
            edge_agent.run_forever()
            
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
    
    logger.info("Application terminated")


if __name__ == "__main__":
    main() 