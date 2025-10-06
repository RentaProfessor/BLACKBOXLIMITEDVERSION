"""
Rotating logger with file rotation
File logging with rotation: logs/app.log (weekly, keep 4), plus logs/asr.log and logs/vault.log (no secrets)
"""

import os
import logging
import logging.handlers
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

class RotatingLogger:
    """Rotating logger with file rotation"""
    
    def __init__(self, 
                 log_dir: str = "/mnt/nvme/blackbox/logs",
                 max_bytes: int = 100 * 1024 * 1024,  # 100MB
                 backup_count: int = 4,
                 when: str = "W0",  # Weekly on Monday
                 interval: int = 1):
        self.log_dir = Path(log_dir)
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.when = when
        self.interval = interval
        
        # Create log directory
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure loggers
        self._setup_loggers()
    
    def _setup_loggers(self):
        """Setup all loggers with rotation"""
        
        # Main application logger
        self._setup_logger(
            "app",
            self.log_dir / "app.log",
            level=logging.INFO
        )
        
        # ASR logger
        self._setup_logger(
            "asr",
            self.log_dir / "asr.log",
            level=logging.INFO
        )
        
        # Vault logger (no secrets)
        self._setup_logger(
            "vault",
            self.log_dir / "vault.log",
            level=logging.WARNING
        )
        
        # TTS logger
        self._setup_logger(
            "tts",
            self.log_dir / "tts.log",
            level=logging.INFO
        )
        
        # UI logger
        self._setup_logger(
            "ui",
            self.log_dir / "ui.log",
            level=logging.INFO
        )
        
        # System logger
        self._setup_logger(
            "system",
            self.log_dir / "system.log",
            level=logging.INFO
        )
    
    def _setup_logger(self, name: str, log_file: Path, level: int = logging.INFO):
        """Setup a single logger with rotation"""
        
        # Create logger
        logger = logging.getLogger(name)
        logger.setLevel(level)
        
        # Clear existing handlers
        logger.handlers.clear()
        
        # Create rotating file handler
        file_handler = logging.handlers.TimedRotatingFileHandler(
            filename=log_file,
            when=self.when,
            interval=self.interval,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # Add console handler for critical messages
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.ERROR)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # Prevent propagation to root logger
        logger.propagate = False
    
    def get_logger(self, name: str) -> logging.Logger:
        """Get a logger by name"""
        return logging.getLogger(name)
    
    def get_app_logger(self) -> logging.Logger:
        """Get main application logger"""
        return logging.getLogger("app")
    
    def get_asr_logger(self) -> logging.Logger:
        """Get ASR logger"""
        return logging.getLogger("asr")
    
    def get_vault_logger(self) -> logging.Logger:
        """Get vault logger (no secrets)"""
        return logging.getLogger("vault")
    
    def get_tts_logger(self) -> logging.Logger:
        """Get TTS logger"""
        return logging.getLogger("tts")
    
    def get_ui_logger(self) -> logging.Logger:
        """Get UI logger"""
        return logging.getLogger("ui")
    
    def get_system_logger(self) -> logging.Logger:
        """Get system logger"""
        return logging.getLogger("system")
    
    def log_system_info(self):
        """Log system information"""
        system_logger = self.get_system_logger()
        
        # Log system info
        import platform
        import psutil
        
        system_logger.info("=== System Information ===")
        system_logger.info(f"Platform: {platform.platform()}")
        system_logger.info(f"Python: {platform.python_version()}")
        system_logger.info(f"CPU: {platform.processor()}")
        system_logger.info(f"Memory: {psutil.virtual_memory().total / (1024**3):.2f} GB")
        system_logger.info(f"Disk: {psutil.disk_usage('/').total / (1024**3):.2f} GB")
        
        # Log GPU info if available
        try:
            import subprocess
            result = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                system_logger.info(f"GPU: {result.stdout.strip()}")
        except:
            system_logger.info("GPU: Not available")
        
        system_logger.info("=== End System Information ===")
    
    def log_startup(self):
        """Log application startup"""
        app_logger = self.get_app_logger()
        app_logger.info("=" * 50)
        app_logger.info("BLACK BOX Application Starting")
        app_logger.info(f"Startup Time: {datetime.now().isoformat()}")
        app_logger.info("=" * 50)
    
    def log_shutdown(self):
        """Log application shutdown"""
        app_logger = self.get_app_logger()
        app_logger.info("=" * 50)
        app_logger.info("BLACK BOX Application Shutting Down")
        app_logger.info(f"Shutdown Time: {datetime.now().isoformat()}")
        app_logger.info("=" * 50)
    
    def get_log_stats(self) -> Dict[str, Any]:
        """Get log file statistics"""
        stats = {}
        
        log_files = [
            "app.log",
            "asr.log",
            "vault.log",
            "tts.log",
            "ui.log",
            "system.log"
        ]
        
        for log_file in log_files:
            log_path = self.log_dir / log_file
            if log_path.exists():
                try:
                    file_size = log_path.stat().st_size
                    modified_time = datetime.fromtimestamp(log_path.stat().st_mtime)
                    
                    stats[log_file] = {
                        "size_bytes": file_size,
                        "size_mb": file_size / (1024 * 1024),
                        "modified": modified_time.isoformat(),
                        "exists": True
                    }
                except Exception as e:
                    stats[log_file] = {
                        "error": str(e),
                        "exists": True
                    }
            else:
                stats[log_file] = {
                    "exists": False
                }
        
        return stats
    
    def cleanup_old_logs(self):
        """Clean up old log files"""
        app_logger = self.get_app_logger()
        
        try:
            # Find all log files
            log_files = list(self.log_dir.glob("*.log*"))
            
            # Sort by modification time
            log_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # Keep only the most recent files
            for log_file in log_files[self.backup_count:]:
                try:
                    log_file.unlink()
                    app_logger.info(f"Cleaned up old log file: {log_file.name}")
                except Exception as e:
                    app_logger.error(f"Failed to clean up log file {log_file.name}: {e}")
                    
        except Exception as e:
            app_logger.error(f"Error during log cleanup: {e}")
    
    def rotate_logs(self):
        """Manually rotate all logs"""
        app_logger = self.get_app_logger()
        app_logger.info("Manual log rotation requested")
        
        # Force rotation of all handlers
        for logger_name in ["app", "asr", "vault", "tts", "ui", "system"]:
            logger = logging.getLogger(logger_name)
            for handler in logger.handlers:
                if isinstance(handler, logging.handlers.TimedRotatingFileHandler):
                    handler.doRollover()
        
        app_logger.info("Log rotation completed")

# Global logger instance
rotating_logger = RotatingLogger()

def get_logger(name: str) -> logging.Logger:
    """Get a logger by name"""
    return rotating_logger.get_logger(name)

def get_app_logger() -> logging.Logger:
    """Get main application logger"""
    return rotating_logger.get_app_logger()

def get_asr_logger() -> logging.Logger:
    """Get ASR logger"""
    return rotating_logger.get_asr_logger()

def get_vault_logger() -> logging.Logger:
    """Get vault logger (no secrets)"""
    return rotating_logger.get_vault_logger()

def get_tts_logger() -> logging.Logger:
    """Get TTS logger"""
    return rotating_logger.get_tts_logger()

def get_ui_logger() -> logging.Logger:
    """Get UI logger"""
    return rotating_logger.get_ui_logger()

def get_system_logger() -> logging.Logger:
    """Get system logger"""
    return rotating_logger.get_system_logger()

def main():
    """Test rotating logger"""
    print("Testing Rotating Logger")
    print("=" * 30)
    
    # Test loggers
    app_logger = get_app_logger()
    asr_logger = get_asr_logger()
    vault_logger = get_vault_logger()
    
    app_logger.info("This is an app log message")
    asr_logger.info("This is an ASR log message")
    vault_logger.warning("This is a vault log message")
    
    # Log system info
    rotating_logger.log_system_info()
    
    # Get log stats
    stats = rotating_logger.get_log_stats()
    print("\nLog Statistics:")
    for log_file, stat in stats.items():
        if stat.get("exists"):
            if "error" in stat:
                print(f"{log_file}: Error - {stat['error']}")
            else:
                print(f"{log_file}: {stat['size_mb']:.2f} MB, Modified: {stat['modified']}")
        else:
            print(f"{log_file}: Not found")

if __name__ == "__main__":
    main()
