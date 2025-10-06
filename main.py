#!/usr/bin/env python3
"""
BLACK BOX - Main application entry point
AI-assisted password and voice-memo manager for elderly users
"""

import sys
import os
import logging
import signal
from pathlib import Path

# Add the blackbox package to Python path
sys.path.insert(0, str(Path(__file__).parent))

from blackbox.ui.main import main as ui_main

def setup_logging():
    """Setup logging configuration"""
    log_dir = Path("/mnt/nvme/blackbox/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / "blackbox.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set specific log levels for different modules
    logging.getLogger('blackbox.audio').setLevel(logging.INFO)
    logging.getLogger('blackbox.nlp').setLevel(logging.INFO)
    logging.getLogger('blackbox.vault').setLevel(logging.WARNING)  # Less verbose for security
    logging.getLogger('blackbox.ui').setLevel(logging.INFO)

def signal_handler(signum, frame):
    """Handle system signals for graceful shutdown"""
    logging.info(f"Received signal {signum}, shutting down gracefully...")
    sys.exit(0)

def main():
    """Main application entry point"""
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Setup logging
    setup_logging()
    
    logging.info("BLACK BOX starting up...")
    
    try:
        # Start the UI application
        ui_main()
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logging.info("BLACK BOX shutting down...")

if __name__ == "__main__":
    main()
