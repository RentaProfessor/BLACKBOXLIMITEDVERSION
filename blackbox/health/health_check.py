"""
Health check system
Add a tiny /health endpoint (or internal check) used at startup before showing UI "Ready"
"""

import os
import time
import logging
from typing import Dict, Any, List
from pathlib import Path
import subprocess

logger = logging.getLogger(__name__)

class HealthChecker:
    """Health check system for BLACK BOX components"""
    
    def __init__(self):
        self.checks = {}
        self.last_check_time = 0
        self.check_interval = 30  # 30 seconds
        self.overall_status = "unknown"
    
    def register_check(self, name: str, check_func, critical: bool = True):
        """Register a health check function"""
        self.checks[name] = {
            "function": check_func,
            "critical": critical,
            "last_result": None,
            "last_check": 0
        }
    
    def run_checks(self, force: bool = False) -> Dict[str, Any]:
        """Run all health checks"""
        current_time = time.time()
        
        if not force and current_time - self.last_check_time < self.check_interval:
            return self._get_cached_results()
        
        results = {
            "timestamp": current_time,
            "overall_status": "healthy",
            "checks": {},
            "critical_failures": [],
            "warnings": []
        }
        
        for name, check_info in self.checks.items():
            try:
                start_time = time.time()
                result = check_info["function"]()
                check_time = time.time() - start_time
                
                check_result = {
                    "status": "healthy" if result.get("healthy", False) else "unhealthy",
                    "message": result.get("message", ""),
                    "details": result.get("details", {}),
                    "check_time": check_time,
                    "critical": check_info["critical"]
                }
                
                results["checks"][name] = check_result
                
                # Update cached result
                check_info["last_result"] = check_result
                check_info["last_check"] = current_time
                
                # Check for critical failures
                if not result.get("healthy", False) and check_info["critical"]:
                    results["critical_failures"].append(name)
                    results["overall_status"] = "unhealthy"
                elif not result.get("healthy", False):
                    results["warnings"].append(name)
                
            except Exception as e:
                logger.error(f"Health check '{name}' failed with exception: {e}")
                check_result = {
                    "status": "error",
                    "message": f"Check failed: {str(e)}",
                    "details": {},
                    "check_time": 0,
                    "critical": check_info["critical"]
                }
                
                results["checks"][name] = check_result
                
                if check_info["critical"]:
                    results["critical_failures"].append(name)
                    results["overall_status"] = "unhealthy"
        
        self.last_check_time = current_time
        self.overall_status = results["overall_status"]
        
        return results
    
    def _get_cached_results(self) -> Dict[str, Any]:
        """Get cached health check results"""
        results = {
            "timestamp": self.last_check_time,
            "overall_status": self.overall_status,
            "checks": {},
            "critical_failures": [],
            "warnings": []
        }
        
        for name, check_info in self.checks.items():
            if check_info["last_result"]:
                results["checks"][name] = check_info["last_result"]
                
                if check_info["last_result"]["status"] == "unhealthy":
                    if check_info["critical"]:
                        results["critical_failures"].append(name)
                    else:
                        results["warnings"].append(name)
        
        return results
    
    def is_healthy(self) -> bool:
        """Check if system is overall healthy"""
        results = self.run_checks()
        return results["overall_status"] == "healthy"
    
    def get_status_summary(self) -> str:
        """Get a simple status summary"""
        results = self.run_checks()
        
        if results["overall_status"] == "healthy":
            return "Ready"
        elif results["critical_failures"]:
            return f"Critical: {', '.join(results['critical_failures'])}"
        else:
            return f"Warnings: {', '.join(results['warnings'])}"

# Health check functions
def check_database() -> Dict[str, Any]:
    """Check database health"""
    try:
        from ..config.app import get_config
        config = get_config()
        
        if not config.vault_db.exists():
            return {
                "healthy": False,
                "message": "Database file not found",
                "details": {"path": str(config.vault_db)}
            }
        
        # Check if database is accessible
        import sqlite3
        try:
            conn = sqlite3.connect(str(config.vault_db))
            conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            conn.close()
            
            return {
                "healthy": True,
                "message": "Database accessible",
                "details": {"path": str(config.vault_db)}
            }
        except Exception as e:
            return {
                "healthy": False,
                "message": f"Database access error: {str(e)}",
                "details": {"path": str(config.vault_db)}
            }
            
    except Exception as e:
        return {
            "healthy": False,
            "message": f"Database check failed: {str(e)}",
            "details": {}
        }

def check_audio_system() -> Dict[str, Any]:
    """Check audio system health"""
    try:
        # Check if audio devices are available
        result = subprocess.run(["aplay", "-l"], capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return {
                "healthy": False,
                "message": "No audio output devices found",
                "details": {"error": result.stderr}
            }
        
        result = subprocess.run(["arecord", "-l"], capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return {
                "healthy": False,
                "message": "No audio input devices found",
                "details": {"error": result.stderr}
            }
        
        return {
            "healthy": True,
            "message": "Audio devices available",
            "details": {"output_devices": True, "input_devices": True}
        }
        
    except Exception as e:
        return {
            "healthy": False,
            "message": f"Audio system check failed: {str(e)}",
            "details": {}
        }

def check_models() -> Dict[str, Any]:
    """Check AI models health"""
    try:
        from ..config.app import get_config
        config = get_config()
        
        model_paths = config.get_model_paths()
        missing_models = []
        
        for name, path in model_paths.items():
            if not Path(path).exists():
                missing_models.append(name)
        
        if missing_models:
            return {
                "healthy": False,
                "message": f"Missing models: {', '.join(missing_models)}",
                "details": {"missing_models": missing_models}
            }
        
        return {
            "healthy": True,
            "message": "All models available",
            "details": {"model_count": len(model_paths)}
        }
        
    except Exception as e:
        return {
            "healthy": False,
            "message": f"Models check failed: {str(e)}",
            "details": {}
        }

def check_storage() -> Dict[str, Any]:
    """Check storage health"""
    try:
        from ..config.app import get_config
        config = get_config()
        
        # Check disk space
        import shutil
        total, used, free = shutil.disk_usage(config.base_dir)
        free_gb = free / (1024**3)
        
        if free_gb < 1.0:  # Less than 1GB free
            return {
                "healthy": False,
                "message": f"Low disk space: {free_gb:.2f} GB free",
                "details": {"free_gb": free_gb, "total_gb": total / (1024**3)}
            }
        
        return {
            "healthy": True,
            "message": f"Storage healthy: {free_gb:.2f} GB free",
            "details": {"free_gb": free_gb, "total_gb": total / (1024**3)}
        }
        
    except Exception as e:
        return {
            "healthy": False,
            "message": f"Storage check failed: {str(e)}",
            "details": {}
        }

def check_gpu() -> Dict[str, Any]:
    """Check GPU health (optional)"""
    try:
        result = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return {
                "healthy": True,
                "message": "GPU available",
                "details": {"gpu_available": True}
            }
        else:
            return {
                "healthy": False,
                "message": "GPU not available",
                "details": {"gpu_available": False}
            }
    except Exception as e:
        return {
            "healthy": False,
            "message": f"GPU check failed: {str(e)}",
            "details": {}
        }

def check_network() -> Dict[str, Any]:
    """Check network health (should be disabled for offline operation)"""
    try:
        # Check if network interfaces are down (good for offline operation)
        result = subprocess.run(["ip", "link", "show"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            # Count active interfaces (excluding loopback)
            active_interfaces = [line for line in result.stdout.split('\n') 
                               if 'state UP' in line and 'lo:' not in line]
            
            if len(active_interfaces) == 0:
                return {
                    "healthy": True,
                    "message": "Network disabled (offline mode)",
                    "details": {"offline_mode": True}
                }
            else:
                return {
                    "healthy": False,
                    "message": f"Network active: {len(active_interfaces)} interfaces",
                    "details": {"offline_mode": False, "active_interfaces": len(active_interfaces)}
                }
        else:
            return {
                "healthy": True,
                "message": "Network status unknown",
                "details": {}
            }
    except Exception as e:
        return {
            "healthy": False,
            "message": f"Network check failed: {str(e)}",
            "details": {}
        }

# Global health checker instance
health_checker = HealthChecker()

def initialize_health_checks():
    """Initialize all health checks"""
    # Register critical checks
    health_checker.register_check("database", check_database, critical=True)
    health_checker.register_check("audio_system", check_audio_system, critical=True)
    health_checker.register_check("models", check_models, critical=True)
    health_checker.register_check("storage", check_storage, critical=True)
    
    # Register optional checks
    health_checker.register_check("gpu", check_gpu, critical=False)
    health_checker.register_check("network", check_network, critical=False)

def get_health_status() -> Dict[str, Any]:
    """Get current health status"""
    return health_checker.run_checks()

def is_system_healthy() -> bool:
    """Check if system is healthy"""
    return health_checker.is_healthy()

def get_status_summary() -> str:
    """Get status summary for UI"""
    return health_checker.get_status_summary()

def main():
    """Test health checks"""
    print("BLACK BOX Health Check")
    print("=" * 30)
    
    # Initialize health checks
    initialize_health_checks()
    
    # Run checks
    results = get_health_status()
    
    print(f"Overall Status: {results['overall_status']}")
    print(f"Timestamp: {results['timestamp']}")
    
    if results['critical_failures']:
        print(f"Critical Failures: {', '.join(results['critical_failures'])}")
    
    if results['warnings']:
        print(f"Warnings: {', '.join(results['warnings'])}")
    
    print("\nDetailed Results:")
    for name, check_result in results['checks'].items():
        status = check_result['status']
        message = check_result['message']
        critical = "CRITICAL" if check_result['critical'] else "OPTIONAL"
        print(f"{status.upper():10} {critical:8} {name}: {message}")

if __name__ == "__main__":
    main()
