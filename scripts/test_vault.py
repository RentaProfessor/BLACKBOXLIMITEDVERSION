#!/usr/bin/env python3
"""
BLACK BOX - Vault test script
Tests create/open/lock, CRUD one credential
"""

import sys
import os
import tempfile
import logging
from pathlib import Path

# Add the blackbox package to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from blackbox.vault.db import VaultDatabase, VaultEntry
from blackbox.logging.rotating_logger import get_app_logger

logger = get_app_logger()

def test_passed(message):
    print(f"✓ {message}")
    logger.info(f"TEST PASSED: {message}")

def test_failed(message):
    print(f"✗ {message}")
    logger.error(f"TEST FAILED: {message}")

def test_warning(message):
    print(f"⚠ {message}")
    logger.warning(f"TEST WARNING: {message}")

def main():
    """Test vault functionality"""
    print("BLACK BOX - Vault System Test")
    print("=" * 40)
    
    # Use temporary database for testing
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_file:
        test_db_path = temp_file.name
    
    try:
        # Test 1: Vault initialization
        print("\n1. Testing Vault Initialization...")
        
        vault = VaultDatabase(test_db_path)
        test_passphrase = "test_passphrase_123"
        
        if vault.initialize_vault(test_passphrase):
            test_passed("Vault initialization successful")
        else:
            test_failed("Vault initialization failed")
            return 1
        
        # Test 2: Vault unlock
        print("\n2. Testing Vault Unlock...")
        
        vault.lock_vault()
        if vault.unlock_vault(test_passphrase):
            test_passed("Vault unlock successful")
        else:
            test_failed("Vault unlock failed")
            return 1
        
        # Test 3: Save password
        print("\n3. Testing Password Save...")
        
        test_site = "gmail"
        test_password = "test_password_123"
        test_username = "test@example.com"
        test_memo = "Test account"
        
        if vault.save_password(test_site, test_password, test_username, test_memo):
            test_passed("Password save successful")
        else:
            test_failed("Password save failed")
            return 1
        
        # Test 4: Retrieve password
        print("\n4. Testing Password Retrieve...")
        
        entry = vault.retrieve_password(test_site)
        if entry:
            if entry.site == test_site and entry.password == test_password:
                test_passed("Password retrieve successful")
                print(f"  Retrieved: {entry.site} - {entry.username}")
            else:
                test_failed("Password retrieve returned incorrect data")
                return 1
        else:
            test_failed("Password retrieve failed")
            return 1
        
        # Test 5: List entries
        print("\n5. Testing List Entries...")
        
        entries = vault.list_entries()
        if len(entries) == 1 and entries[0].site == test_site:
            test_passed("List entries successful")
        else:
            test_failed("List entries failed")
            return 1
        
        # Test 6: Search entries
        print("\n6. Testing Search Entries...")
        
        search_results = vault.search_entries("gmail")
        if len(search_results) == 1 and search_results[0].site == test_site:
            test_passed("Search entries successful")
        else:
            test_failed("Search entries failed")
            return 1
        
        # Test 7: Update entry
        print("\n7. Testing Entry Update...")
        
        new_password = "new_password_456"
        if vault.save_password(test_site, new_password, test_username, test_memo):
            entry = vault.retrieve_password(test_site)
            if entry and entry.password == new_password:
                test_passed("Entry update successful")
            else:
                test_failed("Entry update failed")
                return 1
        else:
            test_failed("Entry update save failed")
            return 1
        
        # Test 8: Vault statistics
        print("\n8. Testing Vault Statistics...")
        
        stats = vault.get_vault_stats()
        if stats.total_entries == 1 and stats.total_accesses > 0:
            test_passed("Vault statistics successful")
            print(f"  Total entries: {stats.total_entries}")
            print(f"  Total accesses: {stats.total_accesses}")
            print(f"  Vault size: {stats.vault_size_mb:.2f} MB")
        else:
            test_failed("Vault statistics failed")
            return 1
        
        # Test 9: Vault health
        print("\n9. Testing Vault Health...")
        
        health = vault.get_vault_health()
        if health["is_unlocked"] and health["database_exists"]:
            test_passed("Vault health check successful")
            print(f"  Unlocked: {health['is_unlocked']}")
            print(f"  Database exists: {health['database_exists']}")
            print(f"  Database size: {health['database_size']} bytes")
        else:
            test_failed("Vault health check failed")
            return 1
        
        # Test 10: Backup functionality
        print("\n10. Testing Backup Functionality...")
        
        with tempfile.NamedTemporaryFile(suffix='.backup', delete=False) as backup_file:
            backup_path = backup_file.name
        
        if vault.backup_vault(backup_path):
            if os.path.exists(backup_path) and os.path.getsize(backup_path) > 0:
                test_passed("Vault backup successful")
                print(f"  Backup size: {os.path.getsize(backup_path)} bytes")
            else:
                test_failed("Vault backup file not created")
                return 1
        else:
            test_failed("Vault backup failed")
            return 1
        
        # Test 11: Master passphrase change
        print("\n11. Testing Master Passphrase Change...")
        
        new_passphrase = "new_test_passphrase_456"
        if vault.change_master_passphrase(test_passphrase, new_passphrase):
            test_passed("Master passphrase change successful")
            
            # Test unlock with new passphrase
            vault.lock_vault()
            if vault.unlock_vault(new_passphrase):
                test_passed("Unlock with new passphrase successful")
            else:
                test_failed("Unlock with new passphrase failed")
                return 1
        else:
            test_failed("Master passphrase change failed")
            return 1
        
        # Test 12: Delete entry
        print("\n12. Testing Entry Deletion...")
        
        if vault.delete_entry(test_site):
            entries = vault.list_entries()
            if len(entries) == 0:
                test_passed("Entry deletion successful")
            else:
                test_failed("Entry deletion failed")
                return 1
        else:
            test_failed("Entry deletion failed")
            return 1
        
        # Test 13: Vault lock
        print("\n13. Testing Vault Lock...")
        
        vault.relock_vault()
        if not vault.is_unlocked:
            test_passed("Vault lock successful")
        else:
            test_failed("Vault lock failed")
            return 1
        
        # Test 14: Encrypted backup
        print("\n14. Testing Encrypted Backup...")
        
        # Unlock vault for backup test
        if vault.unlock_vault(new_passphrase):
            with tempfile.NamedTemporaryFile(suffix='.encrypted', delete=False) as encrypted_backup:
                encrypted_backup_path = encrypted_backup.name
            
            backup_passphrase = "backup_passphrase_789"
            if vault.export_encrypted_backup(encrypted_backup_path, backup_passphrase):
                if os.path.exists(encrypted_backup_path) and os.path.getsize(encrypted_backup_path) > 0:
                    test_passed("Encrypted backup export successful")
                    
                    # Test import
                    if vault.import_encrypted_backup(encrypted_backup_path, backup_passphrase):
                        test_passed("Encrypted backup import successful")
                    else:
                        test_failed("Encrypted backup import failed")
                        return 1
                else:
                    test_failed("Encrypted backup file not created")
                    return 1
            else:
                test_failed("Encrypted backup export failed")
                return 1
        else:
            test_failed("Vault unlock for backup test failed")
            return 1
        
        # Test Summary
        print("\n" + "=" * 40)
        print("Vault Test Summary")
        print("=" * 40)
        print("🎉 All vault tests passed successfully!")
        
        return 0
        
    except Exception as e:
        test_failed(f"Unexpected error: {e}")
        logger.error(f"Vault test error: {e}", exc_info=True)
        return 1
        
    finally:
        # Clean up
        try:
            if 'vault' in locals():
                vault.close()
        except:
            pass
        
        # Remove temporary files
        try:
            if os.path.exists(test_db_path):
                os.unlink(test_db_path)
            if 'backup_path' in locals() and os.path.exists(backup_path):
                os.unlink(backup_path)
            if 'encrypted_backup_path' in locals() and os.path.exists(encrypted_backup_path):
                os.unlink(encrypted_backup_path)
        except:
            pass

if __name__ == "__main__":
    sys.exit(main())
