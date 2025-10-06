"""
Graceful shutdown handler for BLACK BOX
Handles SIGTERM and SIGINT signals to properly shut down components
"""

import signal
import sys
import logging
import time
from typing import Optional, List, Callable

logger = logging.getLogger(__name__)

class GracefulShutdown:
    """Graceful shutdown handler"""
    
    def __init__(self):
        self.shutdown_handlers: List[Callable] = []
        self.is_shutting_down = False
        self.shutdown_timeout = 10  # 10 seconds timeout
        
        # Register signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGHUP, self._reload_handler)
    
    def register_handler(self, handler: Callable):
        """Register a shutdown handler"""
        self.shutdown_handlers.append(handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        signal_name = signal.Signals(signum).name
        logger.info(f"Received {signal_name} signal, initiating graceful shutdown...")
        
        if self.is_shutting_down:
            logger.warning("Shutdown already in progress, forcing exit")
            sys.exit(1)
        
        self.is_shutting_down = True
        self._shutdown()
    
    def _reload_handler(self, signum, frame):
        """Handle reload signal"""
        logger.info("Received SIGHUP signal, reloading configuration...")
        self._reload()
    
    def _shutdown(self):
        """Execute shutdown handlers"""
        logger.info("Starting graceful shutdown...")
        
        start_time = time.time()
        
        for i, handler in enumerate(self.shutdown_handlers):
            try:
                logger.info(f"Executing shutdown handler {i+1}/{len(self.shutdown_handlers)}")
                handler()
            except Exception as e:
                logger.error(f"Error in shutdown handler {i+1}: {e}")
        
        elapsed_time = time.time() - start_time
        logger.info(f"Graceful shutdown completed in {elapsed_time:.2f} seconds")
        
        # Force exit if timeout exceeded
        if elapsed_time > self.shutdown_timeout:
            logger.warning("Shutdown timeout exceeded, forcing exit")
            sys.exit(1)
        else:
            sys.exit(0)
    
    def _reload(self):
        """Execute reload handlers"""
        logger.info("Reloading configuration...")
        
        # For now, just log the reload request
        # In a full implementation, you would reload configuration files
        logger.info("Configuration reload completed")
    
    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested"""
        return self.is_shutting_down

# Global shutdown handler
shutdown_handler = GracefulShutdown()

def register_shutdown_handler(handler: Callable):
    """Register a shutdown handler"""
    shutdown_handler.register_handler(handler)

def is_shutdown_requested() -> bool:
    """Check if shutdown has been requested"""
    return shutdown_handler.is_shutdown_requested()

def main():
    """Test graceful shutdown"""
    import threading
    import time
    
    def test_handler():
        print("Test shutdown handler executed")
        time.sleep(1)
    
    def test_handler2():
        print("Test shutdown handler 2 executed")
        time.sleep(1)
    
    # Register test handlers
    register_shutdown_handler(test_handler)
    register_shutdown_handler(test_handler2)
    
    print("Graceful shutdown test running...")
    print("Press Ctrl+C to test shutdown")
    
    try:
        while True:
            time.sleep(1)
            if is_shutdown_requested():
                break
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
