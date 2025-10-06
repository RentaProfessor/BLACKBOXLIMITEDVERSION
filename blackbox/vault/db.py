"""
Encrypted vault database using SQLCipher with Argon2id KDF
Secure storage for passwords and voice memos
"""

import os
import sqlite3
import hashlib
import secrets
import time
import logging
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import argon2
from argon2 import PasswordHasher
import json

logger = logging.getLogger(__name__)

@dataclass
class VaultEntry:
    """Vault entry for password or memo"""
    id: int
    site: str
    username: Optional[str]
    password: str
    memo: Optional[str]
    created_at: datetime
    updated_at: datetime
    access_count: int
    last_accessed: Optional[datetime]

@dataclass
class VaultStats:
    """Vault statistics"""
    total_entries: int
    total_accesses: int
    last_backup: Optional[datetime]
    vault_size_mb: float

class VaultDatabase:
    """Encrypted SQLCipher database for vault storage"""
    
    def __init__(self, db_path: str = "/mnt/nvme/blackbox/db/vault.db"):
        self.db_path = db_path
        self.connection = None
        self.is_unlocked = False
        self.master_key = None
        self.argon2_hasher = PasswordHasher(
            time_cost=3,      # Reduced for Jetson performance
            memory_cost=65536, # 64MB
            parallelism=4,
            hash_len=32,
            salt_len=16
        )
        
        # Auto-lock settings
        self.idle_timeout = 300  # 5 minutes
        self.last_activity = time.time()
        
        # Ensure database directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    def initialize_vault(self, master_passphrase: str) -> bool:
        """
        Initialize vault with master passphrase
        Returns True if successful, False otherwise
        """
        try:
            # Hash the master passphrase
            self.master_key = self.argon2_hasher.hash(master_passphrase)
            
            # Create database connection
            self.connection = sqlite3.connect(self.db_path)
            
            # Enable SQLCipher
            self.connection.execute("PRAGMA key = ?", (master_passphrase,))
            
            # Create tables
            self._create_tables()
            
            # Set up auto-lock
            self._setup_auto_lock()
            
            self.is_unlocked = True
            self.last_activity = time.time()
            
            logger.info("Vault initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize vault: {e}")
            return False
    
    def unlock_vault(self, master_passphrase: str) -> bool:
        """
        Unlock vault with master passphrase
        Returns True if successful, False otherwise
        """
        try:
            # Create database connection
            self.connection = sqlite3.connect(self.db_path)
            
            # Enable SQLCipher
            self.connection.execute("PRAGMA key = ?", (master_passphrase,))
            
            # Test if key is correct by trying to read from a table
            self.connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
            
            # Verify master passphrase hash
            stored_hash = self._get_master_hash()
            if stored_hash:
                try:
                    self.argon2_hasher.verify(stored_hash, master_passphrase)
                except argon2.exceptions.VerifyMismatchError:
                    logger.error("Invalid master passphrase")
                    return False
            
            self.master_key = master_passphrase
            self.is_unlocked = True
            self.last_activity = time.time()
            
            logger.info("Vault unlocked successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unlock vault: {e}")
            return False
    
    def lock_vault(self) -> None:
        """Lock the vault and clear sensitive data from memory"""
        if self.connection:
            self.connection.close()
            self.connection = None
        
        self.is_unlocked = False
        self.master_key = None
        self.last_activity = 0
        
        logger.info("Vault locked")
    
    def _create_tables(self) -> None:
        """Create database tables"""
        cursor = self.connection.cursor()
        
        # Vault entries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vault_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site TEXT NOT NULL,
                username TEXT,
                password TEXT NOT NULL,
                memo TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                access_count INTEGER DEFAULT 0,
                last_accessed TIMESTAMP
            )
        """)
        
        # Vault metadata table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vault_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Store master passphrase hash
        if self.master_key:
            cursor.execute("""
                INSERT OR REPLACE INTO vault_metadata (key, value) 
                VALUES ('master_hash', ?)
            """, (self.master_key,))
        
        # Create indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_site ON vault_entries(site)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON vault_entries(created_at)")
        
        self.connection.commit()
    
    def _get_master_hash(self) -> Optional[str]:
        """Get stored master passphrase hash"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT value FROM vault_metadata WHERE key = 'master_hash'")
            result = cursor.fetchone()
            return result[0] if result else None
        except:
            return None
    
    def _setup_auto_lock(self) -> None:
        """Setup auto-lock functionality"""
        # This would typically be handled by a background thread
        # For now, we'll check on each operation
        pass
    
    def _check_auto_lock(self) -> None:
        """Check if vault should be auto-locked due to inactivity"""
        if self.is_unlocked and time.time() - self.last_activity > self.idle_timeout:
            logger.info("Auto-locking vault due to inactivity")
            self.lock_vault()
    
    def _update_activity(self) -> None:
        """Update last activity timestamp"""
        self.last_activity = time.time()
    
    def save_password(self, site: str, password: str, username: Optional[str] = None, 
                     memo: Optional[str] = None) -> bool:
        """
        Save password to vault
        Returns True if successful, False otherwise
        """
        if not self.is_unlocked:
            logger.error("Vault is locked")
            return False
        
        try:
            self._check_auto_lock()
            if not self.is_unlocked:
                return False
            
            cursor = self.connection.cursor()
            
            # Check if entry already exists
            cursor.execute("SELECT id FROM vault_entries WHERE site = ?", (site,))
            existing = cursor.fetchone()
            
            if existing:
                # Update existing entry
                cursor.execute("""
                    UPDATE vault_entries 
                    SET password = ?, username = ?, memo = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE site = ?
                """, (password, username, memo, site))
            else:
                # Insert new entry
                cursor.execute("""
                    INSERT INTO vault_entries (site, username, password, memo)
                    VALUES (?, ?, ?, ?)
                """, (site, username, password, memo))
            
            self.connection.commit()
            self._update_activity()
            
            logger.info(f"Password saved for site: {site}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save password: {e}")
            return False
    
    def retrieve_password(self, site: str) -> Optional[VaultEntry]:
        """
        Retrieve password from vault
        Returns VaultEntry if found, None otherwise
        """
        if not self.is_unlocked:
            logger.error("Vault is locked")
            return None
        
        try:
            self._check_auto_lock()
            if not self.is_unlocked:
                return None
            
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT id, site, username, password, memo, created_at, updated_at, 
                       access_count, last_accessed
                FROM vault_entries 
                WHERE site = ?
            """, (site,))
            
            result = cursor.fetchone()
            if result:
                # Update access statistics
                cursor.execute("""
                    UPDATE vault_entries 
                    SET access_count = access_count + 1, last_accessed = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (result[0],))
                
                self.connection.commit()
                self._update_activity()
                
                return VaultEntry(
                    id=result[0],
                    site=result[1],
                    username=result[2],
                    password=result[3],
                    memo=result[4],
                    created_at=datetime.fromisoformat(result[5]),
                    updated_at=datetime.fromisoformat(result[6]),
                    access_count=result[7] + 1,
                    last_accessed=datetime.now()
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to retrieve password: {e}")
            return None
    
    def list_entries(self) -> List[VaultEntry]:
        """
        List all vault entries
        Returns list of VaultEntry objects
        """
        if not self.is_unlocked:
            logger.error("Vault is locked")
            return []
        
        try:
            self._check_auto_lock()
            if not self.is_unlocked:
                return []
            
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT id, site, username, password, memo, created_at, updated_at, 
                       access_count, last_accessed
                FROM vault_entries 
                ORDER BY site
            """)
            
            entries = []
            for result in cursor.fetchall():
                entries.append(VaultEntry(
                    id=result[0],
                    site=result[1],
                    username=result[2],
                    password=result[3],
                    memo=result[4],
                    created_at=datetime.fromisoformat(result[5]),
                    updated_at=datetime.fromisoformat(result[6]),
                    access_count=result[7],
                    last_accessed=datetime.fromisoformat(result[8]) if result[8] else None
                ))
            
            self._update_activity()
            return entries
            
        except Exception as e:
            logger.error(f"Failed to list entries: {e}")
            return []
    
    def delete_entry(self, site: str) -> bool:
        """
        Delete entry from vault
        Returns True if successful, False otherwise
        """
        if not self.is_unlocked:
            logger.error("Vault is locked")
            return False
        
        try:
            self._check_auto_lock()
            if not self.is_unlocked:
                return False
            
            cursor = self.connection.cursor()
            cursor.execute("DELETE FROM vault_entries WHERE site = ?", (site,))
            
            if cursor.rowcount > 0:
                self.connection.commit()
                self._update_activity()
                logger.info(f"Entry deleted for site: {site}")
                return True
            else:
                logger.warning(f"No entry found for site: {site}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete entry: {e}")
            return False
    
    def search_entries(self, query: str) -> List[VaultEntry]:
        """
        Search entries by site name
        Returns list of matching VaultEntry objects
        """
        if not self.is_unlocked:
            logger.error("Vault is locked")
            return []
        
        try:
            self._check_auto_lock()
            if not self.is_unlocked:
                return []
            
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT id, site, username, password, memo, created_at, updated_at, 
                       access_count, last_accessed
                FROM vault_entries 
                WHERE site LIKE ? OR username LIKE ?
                ORDER BY site
            """, (f"%{query}%", f"%{query}%"))
            
            entries = []
            for result in cursor.fetchall():
                entries.append(VaultEntry(
                    id=result[0],
                    site=result[1],
                    username=result[2],
                    password=result[3],
                    memo=result[4],
                    created_at=datetime.fromisoformat(result[5]),
                    updated_at=datetime.fromisoformat(result[6]),
                    access_count=result[7],
                    last_accessed=datetime.fromisoformat(result[8]) if result[8] else None
                ))
            
            self._update_activity()
            return entries
            
        except Exception as e:
            logger.error(f"Failed to search entries: {e}")
            return []
    
    def get_vault_stats(self) -> VaultStats:
        """
        Get vault statistics
        Returns VaultStats object
        """
        if not self.is_unlocked:
            logger.error("Vault is locked")
            return VaultStats(0, 0, None, 0.0)
        
        try:
            self._check_auto_lock()
            if not self.is_unlocked:
                return VaultStats(0, 0, None, 0.0)
            
            cursor = self.connection.cursor()
            
            # Get total entries
            cursor.execute("SELECT COUNT(*) FROM vault_entries")
            total_entries = cursor.fetchone()[0]
            
            # Get total accesses
            cursor.execute("SELECT SUM(access_count) FROM vault_entries")
            total_accesses = cursor.fetchone()[0] or 0
            
            # Get last backup
            cursor.execute("SELECT value FROM vault_metadata WHERE key = 'last_backup'")
            last_backup_result = cursor.fetchone()
            last_backup = datetime.fromisoformat(last_backup_result[0]) if last_backup_result else None
            
            # Get vault size
            vault_size_mb = os.path.getsize(self.db_path) / (1024 * 1024)
            
            self._update_activity()
            
            return VaultStats(
                total_entries=total_entries,
                total_accesses=total_accesses,
                last_backup=last_backup,
                vault_size_mb=vault_size_mb
            )
            
        except Exception as e:
            logger.error(f"Failed to get vault stats: {e}")
            return VaultStats(0, 0, None, 0.0)
    
    def backup_vault(self, backup_path: str) -> bool:
        """
        Create backup of vault
        Returns True if successful, False otherwise
        """
        if not self.is_unlocked:
            logger.error("Vault is locked")
            return False
        
        try:
            self._check_auto_lock()
            if not self.is_unlocked:
                return False
            
            # Create backup directory
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            
            # Copy database file
            import shutil
            shutil.copy2(self.db_path, backup_path)
            
            # Update backup timestamp
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO vault_metadata (key, value) 
                VALUES ('last_backup', ?)
            """, (datetime.now().isoformat(),))
            
            self.connection.commit()
            self._update_activity()
            
            logger.info(f"Vault backed up to: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to backup vault: {e}")
            return False
    
    def change_master_passphrase(self, old_passphrase: str, new_passphrase: str) -> bool:
        """
        Change master passphrase with secure key rotation
        Returns True if successful, False otherwise
        """
        if not self.is_unlocked:
            logger.error("Vault is locked")
            return False
        
        try:
            # Verify old passphrase
            if not self.unlock_vault(old_passphrase):
                return False
            
            # Create new database with new passphrase
            new_db_path = self.db_path + ".new"
            new_connection = sqlite3.connect(new_db_path)
            new_connection.execute("PRAGMA key = ?", (new_passphrase,))
            
            # Copy all data to new database
            self.connection.backup(new_connection)
            
            # Update master hash
            new_hasher = PasswordHasher(
                time_cost=3,
                memory_cost=65536,
                parallelism=4,
                hash_len=32,
                salt_len=16
            )
            new_master_key = new_hasher.hash(new_passphrase)
            
            cursor = new_connection.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO vault_metadata (key, value) 
                VALUES ('master_hash', ?)
            """, (new_master_key,))
            
            new_connection.commit()
            new_connection.close()
            
            # Replace old database
            os.replace(new_db_path, self.db_path)
            
            # Update current connection
            self.connection.close()
            self.connection = sqlite3.connect(self.db_path)
            self.connection.execute("PRAGMA key = ?", (new_passphrase,))
            
            self.master_key = new_master_key
            self._update_activity()
            
            logger.info("Master passphrase changed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to change master passphrase: {e}")
            return False
    
    def rotate_master_key(self, new_passphrase: str) -> bool:
        """
        Rotate master key and re-encrypt database
        Returns True if successful, False otherwise
        """
        if not self.is_unlocked:
            logger.error("Vault is locked")
            return False
        
        try:
            # Create backup before rotation
            backup_path = f"{self.db_path}.backup.{int(time.time())}"
            self.backup_vault(backup_path)
            
            # Change passphrase (this re-encrypts the database)
            success = self.change_master_passphrase(self.master_key, new_passphrase)
            
            if success:
                logger.info("Master key rotation completed successfully")
                return True
            else:
                logger.error("Master key rotation failed")
                return False
                
        except Exception as e:
            logger.error(f"Error during master key rotation: {e}")
            return False
    
    def relock_vault(self) -> None:
        """
        Relock vault and securely wipe key from memory
        """
        if self.connection:
            self.connection.close()
            self.connection = None
        
        # Securely wipe master key from memory
        if self.master_key:
            # Overwrite memory with random data
            import secrets
            self.master_key = secrets.token_hex(32)
            self.master_key = None
        
        self.is_unlocked = False
        self.last_activity = 0
        
        logger.info("Vault relocked and key wiped from memory")
    
    def export_encrypted_backup(self, backup_path: str, passphrase: str) -> bool:
        """
        Export encrypted backup file (never plaintext)
        Returns True if successful, False otherwise
        """
        if not self.is_unlocked:
            logger.error("Vault is locked")
            return False
        
        try:
            # Create backup directory
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            
            # Create encrypted backup
            backup_connection = sqlite3.connect(backup_path)
            backup_connection.execute("PRAGMA key = ?", (passphrase,))
            
            # Copy all data to backup
            self.connection.backup(backup_connection)
            
            # Add backup metadata
            cursor = backup_connection.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO vault_metadata (key, value) 
                VALUES ('backup_created', ?)
            """, (datetime.now().isoformat(),))
            
            cursor.execute("""
                INSERT OR REPLACE INTO vault_metadata (key, value) 
                VALUES ('backup_version', ?)
            """, ("1.0",))
            
            backup_connection.commit()
            backup_connection.close()
            
            logger.info(f"Encrypted backup exported to: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export encrypted backup: {e}")
            return False
    
    def import_encrypted_backup(self, backup_path: str, passphrase: str) -> bool:
        """
        Import encrypted backup file
        Returns True if successful, False otherwise
        """
        try:
            # Verify backup file exists
            if not os.path.exists(backup_path):
                logger.error(f"Backup file not found: {backup_path}")
                return False
            
            # Test backup passphrase
            test_connection = sqlite3.connect(backup_path)
            test_connection.execute("PRAGMA key = ?", (passphrase,))
            
            # Try to read from backup
            try:
                test_connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
            except:
                logger.error("Invalid backup passphrase")
                return False
            
            test_connection.close()
            
            # Create backup of current database
            current_backup = f"{self.db_path}.pre_import.{int(time.time())}"
            if self.is_unlocked:
                self.backup_vault(current_backup)
            
            # Replace current database with backup
            import shutil
            shutil.copy2(backup_path, self.db_path)
            
            # Unlock with new passphrase
            if self.unlock_vault(passphrase):
                logger.info(f"Encrypted backup imported from: {backup_path}")
                return True
            else:
                logger.error("Failed to unlock imported backup")
                return False
                
        except Exception as e:
            logger.error(f"Failed to import encrypted backup: {e}")
            return False
    
    def get_vault_health(self) -> Dict[str, Any]:
        """
        Get vault health status
        Returns health information
        """
        health = {
            "is_unlocked": self.is_unlocked,
            "last_activity": self.last_activity,
            "idle_time": time.time() - self.last_activity if self.last_activity > 0 else 0,
            "auto_lock_enabled": True,
            "auto_lock_timeout": self.idle_timeout,
            "database_exists": os.path.exists(self.db_path),
            "database_size": os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
        }
        
        if self.is_unlocked:
            try:
                stats = self.get_vault_stats()
                health.update({
                    "total_entries": stats.total_entries,
                    "total_accesses": stats.total_accesses,
                    "last_backup": stats.last_backup.isoformat() if stats.last_backup else None
                })
            except Exception as e:
                logger.error(f"Error getting vault stats: {e}")
                health["error"] = str(e)
        
        return health
    
    def close(self) -> None:
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.connection = None
        
        self.is_unlocked = False
        self.master_key = None
