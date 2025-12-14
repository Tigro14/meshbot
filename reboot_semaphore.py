#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Semaphore-based reboot signaling mechanism
Uses /dev/shm (shared memory) to survive read-only filesystem issues
"""

import os
import fcntl
import time
import sys

# Import utils functions with fallback for standalone usage
try:
    from utils import info_print, error_print, debug_print
except ImportError:
    # Fallback implementations for standalone usage
    def info_print(msg):
        print(f"[INFO] {msg}", file=sys.stdout)
    
    def error_print(msg):
        print(f"[ERROR] {msg}", file=sys.stderr)
    
    def debug_print(msg):
        pass  # Debug disabled in standalone mode

# Use /dev/shm (tmpfs in RAM) - survives even if disk filesystems go read-only
REBOOT_SEMAPHORE_FILE = "/dev/shm/meshbot_reboot.lock"
REBOOT_INFO_FILE = "/dev/shm/meshbot_reboot.info"

class RebootSemaphore:
    """
    Semaphore-based reboot signaling using file locking on /dev/shm
    
    This approach uses a lock file in shared memory (/dev/shm) instead of
    a regular file in /tmp. Benefits:
    - /dev/shm is tmpfs (RAM-based), survives disk read-only issues
    - fcntl file locking is a true IPC mechanism
    - Works across processes (bot -> watcher daemon)
    - Automatic cleanup on reboot (tmpfs is cleared)
    """
    
    # Class variable to track file descriptor for proper cleanup
    _lock_fd = None
    
    @staticmethod
    def signal_reboot(requester_info):
        """
        Signal a reboot request using semaphore
        
        Args:
            requester_info (dict): Information about who requested the reboot
                Should contain: 'name', 'node_id', 'timestamp'
        
        Returns:
            bool: True if signal was set successfully, False otherwise
        
        Note:
            The lock file descriptor is kept open to maintain the lock.
            It will be automatically released when:
            - The process exits
            - clear_reboot_signal() is called explicitly
            - The system reboots (tmpfs is cleared)
        """
        try:
            # Create lock file if it doesn't exist
            # Note: /dev/shm should always be writable even if disk is read-only
            lock_fd = os.open(REBOOT_SEMAPHORE_FILE, os.O_CREAT | os.O_WRONLY, 0o644)
            
            try:
                # Try to acquire exclusive lock (non-blocking)
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                
                # Store fd for later cleanup (if needed)
                RebootSemaphore._lock_fd = lock_fd
                
                # Write reboot info for logging
                try:
                    with open(REBOOT_INFO_FILE, 'w') as f:
                        f.write(f"Demandé par: {requester_info.get('name', 'unknown')}\n")
                        f.write(f"Node ID: {requester_info.get('node_id', 'unknown')}\n")
                        f.write(f"Timestamp: {requester_info.get('timestamp', time.strftime('%Y-%m-%d %H:%M:%S'))}\n")
                    debug_print(f"✅ Info reboot écrites dans {REBOOT_INFO_FILE}")
                except Exception as e:
                    # Non-critical: we can proceed without info file
                    debug_print(f"⚠️ Impossible d'écrire info reboot: {e}")
                
                info_print(f"✅ Sémaphore reboot activé: {REBOOT_SEMAPHORE_FILE}")
                
                # Keep the lock - watcher will detect it
                # The lock is automatically released when this process exits or fd is closed
                # But we keep it locked while the bot is running to signal reboot
                
                return True
                
            except IOError as e:
                # Lock is already held - reboot already signaled
                os.close(lock_fd)  # Close since we won't use it
                debug_print(f"ℹ️ Sémaphore reboot déjà actif")
                return True  # Still consider it success
                
        except Exception as e:
            error_print(f"❌ Erreur lors de l'activation du sémaphore reboot: {e}")
            return False
    
    @staticmethod
    def check_reboot_signal():
        """
        Check if a reboot has been signaled
        
        Returns:
            bool: True if reboot is signaled (lock file exists and is locked)
        """
        try:
            # Check if lock file exists
            if not os.path.exists(REBOOT_SEMAPHORE_FILE):
                return False
            
            # Try to acquire lock (non-blocking)
            lock_fd = os.open(REBOOT_SEMAPHORE_FILE, os.O_RDONLY)
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # We got the lock - no reboot signaled
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                os.close(lock_fd)
                return False
            except IOError:
                # Lock is held - reboot is signaled
                os.close(lock_fd)
                return True
                
        except Exception as e:
            debug_print(f"Erreur vérification sémaphore: {e}")
            return False
    
    @staticmethod
    def clear_reboot_signal():
        """
        Clear the reboot signal (unlock and remove files)
        
        This should be called by the watcher after initiating the reboot
        """
        try:
            # Close file descriptor if we have one
            if RebootSemaphore._lock_fd is not None:
                try:
                    os.close(RebootSemaphore._lock_fd)
                    RebootSemaphore._lock_fd = None
                    debug_print(f"✅ Lock file descriptor fermé")
                except Exception as e:
                    debug_print(f"⚠️ Erreur fermeture fd: {e}")
            
            # Remove lock file
            if os.path.exists(REBOOT_SEMAPHORE_FILE):
                os.remove(REBOOT_SEMAPHORE_FILE)
                debug_print(f"✅ Sémaphore reboot effacé: {REBOOT_SEMAPHORE_FILE}")
            
            # Remove info file
            if os.path.exists(REBOOT_INFO_FILE):
                os.remove(REBOOT_INFO_FILE)
                debug_print(f"✅ Info reboot effacée: {REBOOT_INFO_FILE}")
            
            return True
        except Exception as e:
            error_print(f"❌ Erreur lors de l'effacement du sémaphore: {e}")
            return False
    
    @staticmethod
    def get_reboot_info():
        """
        Get information about who requested the reboot
        
        Returns:
            str: Reboot information or empty string if not available
        """
        try:
            if os.path.exists(REBOOT_INFO_FILE):
                with open(REBOOT_INFO_FILE, 'r') as f:
                    return f.read()
        except Exception as e:
            debug_print(f"Erreur lecture info reboot: {e}")
        return ""
