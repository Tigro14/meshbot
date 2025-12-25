#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PKI Key Synchronization Manager for Meshtastic 2.7.15+

This module synchronizes public keys from a remote TCP node's database
into the bot's local interface.nodes, enabling proper decryption of
PKI-encrypted DM messages.

PROBLEM:
    When the bot connects via TCP to a Meshtastic node (e.g., tigrog2),
    the in-memory interface.nodes object doesn't automatically contain
    all the public keys that are stored in the remote node's local database.
    This causes DMs to appear as ENCRYPTED even though the remote node
    can decrypt them.

SOLUTION:
    Periodically query the remote TCP node for its complete node list
    (including public keys) and merge any missing keys into the bot's
    interface.nodes. This allows the Meshtastic Python library to decrypt
    DMs without changing the TCP/serial architecture.

ARCHITECTURE:
    - Runs in a background thread
    - Queries remote node every 5 minutes (configurable)
    - Only adds missing keys (doesn't overwrite existing data)
    - Safe for both TCP and serial connections
    - Minimal overhead (uses temporary TCP connection)

USAGE:
    sync_manager = KeySyncManager(interface, remote_host, remote_port)
    sync_manager.start()
    # ...later...
    sync_manager.stop()
"""

import time
import threading
import traceback
from utils import debug_print, info_print, error_print


class KeySyncManager:
    """
    Manages periodic synchronization of public keys from remote TCP node
    """
    
    def __init__(self, interface, remote_host, remote_port, sync_interval=300):
        """
        Initialize key sync manager
        
        Args:
            interface: Local Meshtastic interface to update
            remote_host (str): IP address of remote TCP node
            remote_port (int): TCP port of remote node (usually 4403)
            sync_interval (int): Seconds between syncs (default: 300 = 5 min)
        """
        self.interface = interface
        self.remote_host = remote_host
        self.remote_port = remote_port
        self.sync_interval = sync_interval
        
        self._running = False
        self._thread = None
        self._last_sync = 0
        self._sync_count = 0
        self._keys_added = 0
        
        info_print(f"🔑 KeySyncManager initialized for {remote_host}:{remote_port}")
        info_print(f"   Sync interval: {sync_interval}s ({sync_interval // 60} minutes)")
    
    def start(self):
        """Start the key synchronization background thread"""
        if self._running:
            debug_print("⚠️ KeySyncManager already running")
            return
        
        self._running = True
        self._thread = threading.Thread(
            target=self._sync_loop,
            name="KeySyncManager",
            daemon=True
        )
        self._thread.start()
        info_print("✅ KeySyncManager started")
    
    def stop(self):
        """Stop the key synchronization background thread"""
        if not self._running:
            return
        
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        info_print("🛑 KeySyncManager stopped")
    
    def _sync_loop(self):
        """Background thread loop for periodic key synchronization"""
        # Initial delay to let the bot fully initialize
        time.sleep(30)
        
        while self._running:
            try:
                self._perform_sync()
                self._last_sync = time.time()
                self._sync_count += 1
            except Exception as e:
                error_print(f"❌ KeySyncManager error: {e}")
                error_print(traceback.format_exc())
            
            # Sleep in small increments to allow quick shutdown
            for _ in range(self.sync_interval):
                if not self._running:
                    break
                time.sleep(1)
    
    def _perform_sync(self):
        """
        Perform one key synchronization cycle
        
        1. Open temporary TCP connection to remote node
        2. Query its node list (with public keys)
        3. Merge missing keys into local interface.nodes
        4. Close temporary connection
        """
        debug_print(f"🔄 Starting key sync from {self.remote_host}:{self.remote_port}")
        
        try:
            # Import here to avoid circular dependency
            from safe_tcp_connection import SafeTCPConnection
            
            # Open temporary TCP connection to remote node
            with SafeTCPConnection(
                self.remote_host,
                self.remote_port,
                wait_time=3,
                timeout=10
            ) as remote_interface:
                
                # Get remote node list
                remote_nodes = getattr(remote_interface, 'nodes', {})
                if not remote_nodes:
                    debug_print("⚠️ Remote interface has no nodes yet")
                    return
                
                # Get local node list
                local_nodes = getattr(self.interface, 'nodes', {})
                if local_nodes is None:
                    debug_print("⚠️ Local interface.nodes is None - initializing")
                    if hasattr(self.interface, 'nodes'):
                        local_nodes = {}
                        self.interface.nodes = local_nodes
                    else:
                        error_print("❌ Cannot access interface.nodes")
                        return
                
                # Track stats for this sync
                nodes_checked = 0
                keys_added_this_sync = 0
                keys_updated_this_sync = 0
                
                # Merge keys from remote to local
                for node_id, remote_node_info in remote_nodes.items():
                    nodes_checked += 1
                    
                    # Skip if not a dict
                    if not isinstance(remote_node_info, dict):
                        continue
                    
                    # Extract user info with public key
                    remote_user = remote_node_info.get('user', {})
                    if not isinstance(remote_user, dict):
                        continue
                    
                    remote_public_key = remote_user.get('publicKey')
                    if not remote_public_key:
                        continue  # No key to sync
                    
                    # Check local node
                    local_node_info = local_nodes.get(node_id)
                    
                    if local_node_info is None:
                        # Node doesn't exist locally - add complete entry
                        local_nodes[node_id] = remote_node_info.copy()
                        keys_added_this_sync += 1
                        debug_print(f"✅ Added node 0x{node_id:08x} with public key")
                    
                    elif isinstance(local_node_info, dict):
                        # Node exists - check if it has the public key
                        local_user = local_node_info.get('user', {})
                        if not isinstance(local_user, dict):
                            local_node_info['user'] = {}
                            local_user = local_node_info['user']
                        
                        local_public_key = local_user.get('publicKey')
                        
                        if not local_public_key:
                            # Missing key - add it
                            local_user['publicKey'] = remote_public_key
                            keys_added_this_sync += 1
                            debug_print(f"✅ Added public key for node 0x{node_id:08x}")
                        
                        elif local_public_key != remote_public_key:
                            # Key exists but differs - update it
                            local_user['publicKey'] = remote_public_key
                            keys_updated_this_sync += 1
                            debug_print(f"🔄 Updated public key for node 0x{node_id:08x}")
                
                # Update total stats
                self._keys_added += keys_added_this_sync + keys_updated_this_sync
                
                # Log sync results
                if keys_added_this_sync > 0 or keys_updated_this_sync > 0:
                    info_print(
                        f"🔑 Key sync complete: {nodes_checked} nodes checked, "
                        f"{keys_added_this_sync} keys added, {keys_updated_this_sync} keys updated"
                    )
                else:
                    debug_print(
                        f"✅ Key sync complete: {nodes_checked} nodes checked, "
                        f"all keys up to date"
                    )
        
        except Exception as e:
            error_print(f"❌ Key sync failed: {e}")
            error_print(traceback.format_exc())
    
    def get_stats(self):
        """
        Get synchronization statistics
        
        Returns:
            dict: Stats including sync count, keys added, last sync time
        """
        return {
            'sync_count': self._sync_count,
            'keys_added': self._keys_added,
            'last_sync': self._last_sync,
            'running': self._running
        }
    
    def force_sync(self):
        """
        Force an immediate synchronization (for testing/debugging)
        
        Returns:
            bool: True if sync was performed, False if already running
        """
        if not self._running:
            error_print("❌ Cannot force sync - KeySyncManager not running")
            return False
        
        try:
            info_print("🔄 Forcing immediate key sync...")
            self._perform_sync()
            return True
        except Exception as e:
            error_print(f"❌ Forced sync failed: {e}")
            return False
