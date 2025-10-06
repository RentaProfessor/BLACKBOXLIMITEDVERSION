"""
Application configuration and paths
All paths under /mnt/nvme/blackbox/{db,logs,models,media} from app/config.py
"""

import os
from pathlib import Path
from typing import Dict, Any

class AppConfig:
    """Application configuration and paths"""
    
    def __init__(self):
        # Base directory
        self.base_dir = Path("/mnt/nvme/blackbox")
        
        # Subdirectories
        self.db_dir = self.base_dir / "db"
        self.logs_dir = self.base_dir / "logs"
        self.models_dir = self.base_dir / "models"
        self.media_dir = self.base_dir / "media"
        self.config_dir = self.base_dir / "config"
        self.assets_dir = self.base_dir / "assets"
        self.catalog_dir = self.base_dir / "catalog"
        self.backups_dir = self.base_dir / "backups"
        
        # Database paths
        self.vault_db = self.db_dir / "vault.db"
        self.backup_dir = self.db_dir / "backups"
        
        # Log paths
        self.app_log = self.logs_dir / "app.log"
        self.asr_log = self.logs_dir / "asr.log"
        self.vault_log = self.logs_dir / "vault.log"
        self.tts_log = self.logs_dir / "tts.log"
        self.ui_log = self.logs_dir / "ui.log"
        
        # Model paths
        self.whisper_dir = self.models_dir / "whisper"
        self.piper_dir = self.models_dir / "piper"
        self.llm_dir = self.models_dir / "llm"
        
        # Audio paths
        self.audio_config = self.config_dir / "audio.json"
        self.voice_config = self.config_dir / "voice.json"
        self.app_config = self.config_dir / "app.yaml"
        
        # Asset paths
        self.beeps_dir = self.assets_dir / "beeps"
        
        # Catalog paths
        self.sites_catalog = self.catalog_dir / "sites.json"
        
        # Ensure directories exist
        self._create_directories()
    
    def _create_directories(self):
        """Create all necessary directories"""
        directories = [
            self.db_dir,
            self.logs_dir,
            self.models_dir,
            self.media_dir,
            self.config_dir,
            self.assets_dir,
            self.catalog_dir,
            self.backups_dir,
            self.backup_dir,
            self.whisper_dir,
            self.piper_dir,
            self.llm_dir,
            self.beeps_dir
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def get_paths(self) -> Dict[str, str]:
        """Get all paths as dictionary"""
        return {
            "base_dir": str(self.base_dir),
            "db_dir": str(self.db_dir),
            "logs_dir": str(self.logs_dir),
            "models_dir": str(self.models_dir),
            "media_dir": str(self.media_dir),
            "config_dir": str(self.config_dir),
            "assets_dir": str(self.assets_dir),
            "catalog_dir": str(self.catalog_dir),
            "backups_dir": str(self.backups_dir),
            "vault_db": str(self.vault_db),
            "backup_dir": str(self.backup_dir),
            "app_log": str(self.app_log),
            "asr_log": str(self.asr_log),
            "vault_log": str(self.vault_log),
            "tts_log": str(self.tts_log),
            "ui_log": str(self.ui_log),
            "whisper_dir": str(self.whisper_dir),
            "piper_dir": str(self.piper_dir),
            "llm_dir": str(self.llm_dir),
            "audio_config": str(self.audio_config),
            "voice_config": str(self.voice_config),
            "app_config": str(self.app_config),
            "beeps_dir": str(self.beeps_dir),
            "sites_catalog": str(self.sites_catalog)
        }
    
    def get_model_paths(self) -> Dict[str, str]:
        """Get model-specific paths"""
        return {
            "whisper_binary": str(self.whisper_dir / "whisper"),
            "whisper_tiny": str(self.whisper_dir / "whisper-tiny.en.bin"),
            "whisper_base": str(self.whisper_dir / "whisper-base.en.bin"),
            "piper_binary": str(self.piper_dir / "piper"),
            "piper_model": str(self.piper_dir / "en_US-lessac-medium.onnx"),
            "piper_config": str(self.piper_dir / "en_US-lessac-medium.onnx.json")
        }
    
    def get_log_paths(self) -> Dict[str, str]:
        """Get log file paths"""
        return {
            "app_log": str(self.app_log),
            "asr_log": str(self.asr_log),
            "vault_log": str(self.vault_log),
            "tts_log": str(self.tts_log),
            "ui_log": str(self.ui_log)
        }
    
    def get_beep_paths(self) -> Dict[str, str]:
        """Get beep file paths"""
        return {
            "recording_start": str(self.beeps_dir / "recording_start.wav"),
            "recording_stop": str(self.beeps_dir / "recording_stop.wav"),
            "success": str(self.beeps_dir / "success.wav"),
            "error": str(self.beeps_dir / "error.wav"),
            "confirm": str(self.beeps_dir / "confirm.wav")
        }
    
    def validate_paths(self) -> Dict[str, bool]:
        """Validate that all paths exist and are accessible"""
        validation = {}
        
        # Check directories
        directories = [
            ("base_dir", self.base_dir),
            ("db_dir", self.db_dir),
            ("logs_dir", self.logs_dir),
            ("models_dir", self.models_dir),
            ("config_dir", self.config_dir),
            ("assets_dir", self.assets_dir),
            ("catalog_dir", self.catalog_dir)
        ]
        
        for name, path in directories:
            validation[name] = path.exists() and path.is_dir()
        
        # Check critical files
        critical_files = [
            ("audio_config", self.audio_config),
            ("app_config", self.app_config),
            ("sites_catalog", self.sites_catalog)
        ]
        
        for name, path in critical_files:
            validation[name] = path.exists() and path.is_file()
        
        return validation
    
    def get_disk_usage(self) -> Dict[str, Any]:
        """Get disk usage information"""
        import shutil
        
        usage = {}
        
        try:
            # Get total disk usage
            total, used, free = shutil.disk_usage(self.base_dir)
            usage["total"] = total
            usage["used"] = used
            usage["free"] = free
            usage["percent_used"] = (used / total) * 100
            
            # Get directory sizes
            usage["directories"] = {}
            for name, path in [
                ("db", self.db_dir),
                ("logs", self.logs_dir),
                ("models", self.models_dir),
                ("media", self.media_dir),
                ("config", self.config_dir),
                ("assets", self.assets_dir),
                ("catalog", self.catalog_dir),
                ("backups", self.backups_dir)
            ]:
                if path.exists():
                    try:
                        dir_size = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
                        usage["directories"][name] = dir_size
                    except Exception:
                        usage["directories"][name] = 0
                else:
                    usage["directories"][name] = 0
            
        except Exception as e:
            usage["error"] = str(e)
        
        return usage

# Global configuration instance
config = AppConfig()

def get_config() -> AppConfig:
    """Get global configuration instance"""
    return config

def get_paths() -> Dict[str, str]:
    """Get all paths as dictionary"""
    return config.get_paths()

def get_model_paths() -> Dict[str, str]:
    """Get model-specific paths"""
    return config.get_model_paths()

def get_log_paths() -> Dict[str, str]:
    """Get log file paths"""
    return config.get_log_paths()

def get_beep_paths() -> Dict[str, str]:
    """Get beep file paths"""
    return config.get_beep_paths()

def main():
    """Test configuration"""
    print("BLACK BOX Configuration")
    print("=" * 30)
    
    # Show all paths
    paths = config.get_paths()
    for name, path in paths.items():
        print(f"{name}: {path}")
    
    print("\nModel Paths:")
    model_paths = config.get_model_paths()
    for name, path in model_paths.items():
        print(f"{name}: {path}")
    
    print("\nLog Paths:")
    log_paths = config.get_log_paths()
    for name, path in log_paths.items():
        print(f"{name}: {path}")
    
    print("\nBeep Paths:")
    beep_paths = config.get_beep_paths()
    for name, path in beep_paths.items():
        print(f"{name}: {path}")
    
    print("\nPath Validation:")
    validation = config.validate_paths()
    for name, valid in validation.items():
        status = "✓" if valid else "✗"
        print(f"{status} {name}")
    
    print("\nDisk Usage:")
    usage = config.get_disk_usage()
    if "error" not in usage:
        print(f"Total: {usage['total'] / (1024**3):.2f} GB")
        print(f"Used: {usage['used'] / (1024**3):.2f} GB")
        print(f"Free: {usage['free'] / (1024**3):.2f} GB")
        print(f"Percent Used: {usage['percent_used']:.1f}%")
        
        print("\nDirectory Sizes:")
        for name, size in usage["directories"].items():
            print(f"{name}: {size / (1024**2):.2f} MB")
    else:
        print(f"Error: {usage['error']}")

if __name__ == "__main__":
    main()
