#!/usr/bin/env python3
"""
MeshCore Serial Monitor - Standalone diagnostic tool
Tests meshcore-cli library API and displays received messages

Usage:
    python meshcore-serial-monitor.py [port] [--debug]
    
Arguments:
    port       Serial port (default: /dev/ttyACM0)
    --debug    Enable debug mode for verbose meshcore library output
    
Example:
    python meshcore-serial-monitor.py /dev/ttyACM0 --debug
"""

import asyncio
import sys
import signal
import argparse
from datetime import datetime
import base64

# Force unbuffered output for real-time logging
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# Try to import PyNaCl for DM decryption
try:
    import nacl.public
    import nacl.encoding
    NACL_AVAILABLE = True
except ImportError:
    NACL_AVAILABLE = False
    print("⚠️  PyNaCl not installed - DM decryption disabled", file=sys.stderr)
    print("   Install with: pip install PyNaCl", file=sys.stderr)


class MeshCoreMonitor:
    """Simple monitor for MeshCore messages"""
    
    def __init__(self, port="/dev/ttyACM0", baudrate=115200, debug=False, meshcore_module=None, event_type=None, private_key=None):
        self.port = port
        self.baudrate = baudrate
        self.debug = debug
        self.meshcore = None
        self.running = True
        self.message_count = 0
        self.rx_log_count = 0  # Track RX_LOG_DATA events separately
        self.decryption_count = 0  # Track successful decryptions
        self.last_heartbeat = None
        # Store module references (will be set by main())
        self.MeshCore = meshcore_module
        self.EventType = event_type
        # Private key for decryption (base64 or hex string)
        self.private_key = self._parse_private_key(private_key) if private_key else None
    
    def _parse_private_key(self, key_string):
        """
        Parse private key from string (base64 or hex format)
        
        Supports:
        - 32 bytes (private key only)
        - 64 bytes (private key + public key concatenated, MeshCore format)
        
        Args:
            key_string: Private key as base64 or hex string
            
        Returns:
            nacl.public.PrivateKey object or None if parsing fails
        """
        if not NACL_AVAILABLE or not key_string:
            return None
        
        try:
            # Try base64 decoding first
            try:
                key_bytes = base64.b64decode(key_string)
                if len(key_bytes) == 32:  # Curve25519 private key is 32 bytes
                    return nacl.public.PrivateKey(key_bytes)
                elif len(key_bytes) == 64:  # MeshCore format: private key (32) + public key (32)
                    print(f"ℹ️  Detected 64-byte key (private+public), using first 32 bytes", file=sys.stderr)
                    return nacl.public.PrivateKey(key_bytes[:32])
            except Exception:
                pass
            
            # Try hex decoding
            try:
                key_bytes = bytes.fromhex(key_string.replace(':', '').replace(' ', ''))
                if len(key_bytes) == 32:
                    return nacl.public.PrivateKey(key_bytes)
                elif len(key_bytes) == 64:  # MeshCore format: private key (32) + public key (32)
                    print(f"ℹ️  Detected 64-byte key (private+public), using first 32 bytes", file=sys.stderr)
                    return nacl.public.PrivateKey(key_bytes[:32])
            except Exception:
                pass
            
            # Try raw bytes if exactly 32 or 64 bytes
            if isinstance(key_string, bytes):
                if len(key_string) == 32:
                    return nacl.public.PrivateKey(key_string)
                elif len(key_string) == 64:
                    print(f"ℹ️  Detected 64-byte key (private+public), using first 32 bytes", file=sys.stderr)
                    return nacl.public.PrivateKey(key_string[:32])
            
            print(f"⚠️  Failed to parse private key (expected 32 or 64 bytes, got {len(key_string)} chars)", file=sys.stderr)
            return None
            
        except Exception as e:
            print(f"⚠️  Error parsing private key: {e}", file=sys.stderr)
            return None
    
    def _decrypt_dm(self, encrypted_data, sender_public_key_bytes):
        """
        Decrypt DM using PyNaCl crypto_box
        
        Args:
            encrypted_data: Encrypted message bytes or string
            sender_public_key_bytes: Sender's Curve25519 public key (32 bytes)
            
        Returns:
            Decrypted plaintext string or None if decryption fails
        """
        if not NACL_AVAILABLE:
            return None
        
        if not self.private_key:
            return None
        
        try:
            # Convert encrypted data to bytes if string
            if isinstance(encrypted_data, str):
                # Try base64 first
                try:
                    encrypted_bytes = base64.b64decode(encrypted_data)
                except Exception:
                    # Try as raw bytes (UTF-8 encoded)
                    encrypted_bytes = encrypted_data.encode('latin-1')
            else:
                encrypted_bytes = encrypted_data
            
            # Create sender's public key object
            sender_public_key = nacl.public.PublicKey(sender_public_key_bytes)
            
            # Create a Box for decryption (combines our private key with sender's public key)
            box = nacl.public.Box(self.private_key, sender_public_key)
            
            # Decrypt the message
            # The encrypted message includes a nonce (first 24 bytes) + ciphertext
            decrypted_bytes = box.decrypt(encrypted_bytes)
            
            # Convert to string
            decrypted_text = decrypted_bytes.decode('utf-8')
            
            self.decryption_count += 1
            return decrypted_text
            
        except Exception as e:
            if self.debug:
                print(f"  ⚠️  Decryption failed: {e}", file=sys.stderr)
            return None
    
    def _get_sender_public_key(self, contact_id):
        """
        Get sender's public key from MeshCore contacts
        
        Args:
            contact_id: Sender's contact ID (integer)
            
        Returns:
            Public key bytes (32 bytes) or None if not found
        """
        try:
            # Try to get contacts from meshcore
            contacts = None
            if hasattr(self.meshcore, 'contacts'):
                contacts = self.meshcore.contacts
            elif hasattr(self.meshcore, 'get_contacts'):
                # This might need to be awaited, but we're in a sync function
                # Called from async context, so this is a limitation
                pass
            
            if not contacts:
                return None
            
            # Find contact by ID
            for contact in contacts:
                # Try different ways to access contact ID
                cid = None
                if isinstance(contact, dict):
                    cid = contact.get('id') or contact.get('contact_id') or contact.get('node_id')
                elif hasattr(contact, 'id'):
                    cid = contact.id
                elif hasattr(contact, 'contact_id'):
                    cid = contact.contact_id
                
                if cid == contact_id or (isinstance(cid, int) and cid == contact_id):
                    # Found the contact, get public key
                    public_key = None
                    if isinstance(contact, dict):
                        public_key = contact.get('public_key') or contact.get('publicKey')
                    elif hasattr(contact, 'public_key'):
                        public_key = contact.public_key
                    elif hasattr(contact, 'publicKey'):
                        public_key = contact.publicKey
                    
                    if public_key:
                        # Convert to bytes if needed
                        if isinstance(public_key, str):
                            try:
                                return base64.b64decode(public_key)
                            except Exception:
                                try:
                                    return bytes.fromhex(public_key.replace(':', '').replace(' ', ''))
                                except Exception:
                                    pass
                        elif isinstance(public_key, bytes):
                            return public_key
            
            return None
            
        except Exception as e:
            if self.debug:
                print(f"  ⚠️  Error getting sender public key: {e}", file=sys.stderr)
            return None
        
    async def on_message(self, event):
        """Callback when message received"""
        self.message_count += 1
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        print(f"\n{'='*60}")
        print(f"[{timestamp}] 📬 Message #{self.message_count} received!")
        print(f"{'='*60}")
        
        # Display event details
        print(f"Event type: {type(event).__name__}")
        print(f"Event repr: {repr(event)}")
        print(f"Event str: {str(event)}")
        
        # Show ALL attributes (including private ones for debugging)
        print(f"\nALL event attributes (dir):")
        all_attrs = dir(event)
        for attr in all_attrs:
            if not attr.startswith('__'):  # Skip double-underscore methods
                try:
                    value = getattr(event, attr)
                    if not callable(value):  # Skip methods
                        print(f"  {attr}: {value} (type: {type(value).__name__})")
                except Exception as e:
                    print(f"  {attr}: <error accessing: {e}>")
        
        # Try to extract payload using multiple methods
        print(f"\n🔍 Trying to extract message data:")
        
        # Method 1: Check for payload attribute
        if hasattr(event, 'payload'):
            print(f"  ✓ event.payload found: {event.payload}")
        
        # Method 2: Check for data attribute
        if hasattr(event, 'data'):
            print(f"  ✓ event.data found: {event.data}")
        
        # Method 3: Check for message attribute
        if hasattr(event, 'message'):
            print(f"  ✓ event.message found: {event.message}")
        
        # Method 4: Check for contact_id and text directly on event
        if hasattr(event, 'contact_id'):
            print(f"  ✓ event.contact_id found: {event.contact_id} (0x{event.contact_id:08x})")
        
        if hasattr(event, 'text'):
            print(f"  ✓ event.text found: {event.text}")
        
        # Method 5: Check if event itself is dict-like
        if isinstance(event, dict):
            print(f"  ✓ event is dict: {event}")
        
        # Try to extract and display the actual message
        print(f"\n📨 Extracted message data:")
        contact_id = None
        text = None
        
        # Try direct attributes first
        if hasattr(event, 'contact_id'):
            contact_id = event.contact_id
        if hasattr(event, 'text'):
            text = event.text
        
        # Try payload
        if not (contact_id and text):
            for payload_attr in ['payload', 'data', 'message']:
                if hasattr(event, payload_attr):
                    payload = getattr(event, payload_attr)
                    if isinstance(payload, dict):
                        contact_id = contact_id or payload.get('contact_id')
                        text = text or payload.get('text')
        
        if contact_id:
            print(f"  From: 0x{contact_id:08x}")
        else:
            print(f"  From: <not found>")
        
        if text:
            print(f"  Text: {text}")
        else:
            print(f"  Text: <not found>")
        
        # Try to decrypt if text appears encrypted/garbled and we have private key
        if text and contact_id and self.private_key:
            # Check if text appears to be encrypted (contains non-printable chars or looks like base64)
            is_encrypted = False
            try:
                # Check for non-printable characters (except common ones like newline)
                non_printable = sum(1 for c in text if ord(c) < 32 and c not in '\n\r\t')
                if non_printable > len(text) * 0.1:  # More than 10% non-printable
                    is_encrypted = True
            except Exception:
                pass
            
            if is_encrypted or (len(text) > 20 and text.isalnum() and '=' in text[-2:]):
                # Looks encrypted, try to decrypt
                print(f"\n🔐 Text appears encrypted, attempting decryption...")
                
                # Get sender's public key
                sender_public_key = self._get_sender_public_key(contact_id)
                
                if sender_public_key:
                    print(f"  ✅ Found sender's public key ({len(sender_public_key)} bytes)")
                    
                    # Try to decrypt
                    decrypted_text = self._decrypt_dm(text, sender_public_key)
                    
                    if decrypted_text:
                        print(f"  ✅ Decryption successful!")
                        print(f"  📨 Decrypted text: {decrypted_text}")
                    else:
                        print(f"  ❌ Decryption failed")
                else:
                    print(f"  ❌ Sender's public key not found in contacts")
                    print(f"     Contact ID: 0x{contact_id:08x}")
        
        print(f"{'='*60}\n")
    
    async def on_rx_log_data(self, event):
        """Callback for RX_LOG_DATA events (raw RF data)"""
        self.rx_log_count += 1
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Only show summary unless in debug mode
        if not self.debug:
            # Just count, don't spam output
            return
        
        print(f"\n[{timestamp}] 📡 RX_LOG_DATA #{self.rx_log_count}")
        print(f"  Event: {type(event).__name__}")
        
        # Try to extract useful info
        if hasattr(event, 'data'):
            data = event.data
            if isinstance(data, dict):
                print(f"  SNR: {data.get('snr', 'N/A')}")
                print(f"  RSSI: {data.get('rssi', 'N/A')}")
                payload_len = data.get('payload_length', 0)
                print(f"  Payload length: {payload_len}")
                
                # Show payload hex if available (for debugging encrypted DMs)
                payload = data.get('payload', '')
                if payload:
                    # Truncate long payloads
                    payload_hex = payload if isinstance(payload, str) else payload.hex()
                    if len(payload_hex) > 60:
                        print(f"  Payload: {payload_hex[:60]}...")
                    else:
                        print(f"  Payload: {payload_hex}")
                    
                    # Note about encrypted DMs
                    if self.private_key:
                        print(f"  ℹ️  RF packet received but not decoded as DM by MeshCore library")
                        print(f"     This may be an encrypted DM that needs manual decryption")
                        print(f"     Waiting for CONTACT_MSG_RECV event...")
        
        print()
        
    async def _check_configuration(self):
        """Check MeshCore configuration and report potential issues"""
        print("\n" + "="*60, flush=True)
        print("🔍 Configuration Diagnostics", flush=True)
        print("="*60, flush=True)
        
        issues_found = []
        
        # Check 1: Private key access
        print("\n1️⃣  Checking private key access...", flush=True)
        has_private_key = False
        try:
            # Check for various private key related attributes
            key_attrs = ['private_key', 'key', 'node_key', 'device_key', 'crypto']
            found_key_attrs = [attr for attr in key_attrs if hasattr(self.meshcore, attr)]
            
            if found_key_attrs:
                print(f"   ✅ Found key-related attributes: {', '.join(found_key_attrs)}", flush=True)
                has_private_key = True
                
                # Try to check if key is actually set
                for attr in found_key_attrs:
                    try:
                        value = getattr(self.meshcore, attr)
                        if value is None:
                            print(f"   ⚠️  {attr} is None", flush=True)
                            issues_found.append(f"{attr} is None - decryption may fail")
                        else:
                            print(f"   ✅ {attr} is set", flush=True)
                    except Exception as e:
                        print(f"   ⚠️  Cannot access {attr}: {e}", flush=True)
            else:
                print("   ⚠️  No private key attributes found in memory", flush=True)
            
            # Check for private key files
            import os
            import glob
            key_file_patterns = ['*.priv', 'private_key*', 'node_key*', '*_priv.key']
            found_key_files = []
            for pattern in key_file_patterns:
                files = glob.glob(pattern)
                found_key_files.extend(files)
            
            if found_key_files:
                print(f"   ✅ Found private key file(s): {', '.join(found_key_files)}", flush=True)
                has_private_key = True
                
                # Try to check if files are readable and non-empty
                for key_file in found_key_files:
                    try:
                        if os.path.exists(key_file) and os.path.isfile(key_file):
                            file_size = os.path.getsize(key_file)
                            if file_size > 0:
                                print(f"   ✅ {key_file} is readable ({file_size} bytes)", flush=True)
                            else:
                                print(f"   ⚠️  {key_file} is empty", flush=True)
                                issues_found.append(f"{key_file} is empty - cannot load private key")
                    except Exception as e:
                        print(f"   ⚠️  Cannot access {key_file}: {e}", flush=True)
            else:
                print("   ℹ️  No private key files found in current directory", flush=True)
            
            if not has_private_key:
                issues_found.append("No private key found (neither in memory nor as file) - encrypted messages cannot be decrypted")
        except Exception as e:
            print(f"   ⚠️  Error checking private key: {e}", flush=True)
            issues_found.append(f"Error checking private key: {e}")
        
        # Check 2: Contact sync capability
        print("\n2️⃣  Checking contact sync capability...", flush=True)
        if hasattr(self.meshcore, 'sync_contacts'):
            print("   ✅ sync_contacts() method available", flush=True)
            
            # Try to check contact list
            if hasattr(self.meshcore, 'contacts') or hasattr(self.meshcore, 'get_contacts'):
                try:
                    contacts = None
                    if hasattr(self.meshcore, 'contacts'):
                        contacts = self.meshcore.contacts
                    elif hasattr(self.meshcore, 'get_contacts'):
                        contacts = await self.meshcore.get_contacts()
                    
                    if contacts:
                        print(f"   ✅ Found {len(contacts)} contacts", flush=True)
                    else:
                        print("   ⚠️  Contact list is empty", flush=True)
                        issues_found.append("No contacts found - DM decryption may fail")
                except Exception as e:
                    print(f"   ⚠️  Cannot retrieve contacts: {e}", flush=True)
            else:
                print("   ⚠️  No contact list accessor found", flush=True)
        else:
            print("   ❌ sync_contacts() method NOT available", flush=True)
            issues_found.append("sync_contacts() not available - contact sync cannot be performed")
        
        # Check 3: Auto message fetching
        print("\n3️⃣  Checking auto message fetching...", flush=True)
        if hasattr(self.meshcore, 'start_auto_message_fetching'):
            print("   ✅ start_auto_message_fetching() available", flush=True)
        else:
            print("   ❌ start_auto_message_fetching() NOT available", flush=True)
            issues_found.append("start_auto_message_fetching() not available - messages must be fetched manually")
        
        # Check 4: Event dispatcher
        print("\n4️⃣  Checking event dispatcher...", flush=True)
        if hasattr(self.meshcore, 'events'):
            print("   ✅ Event dispatcher (events) available", flush=True)
        elif hasattr(self.meshcore, 'dispatcher'):
            print("   ✅ Event dispatcher (dispatcher) available", flush=True)
        else:
            print("   ❌ No event dispatcher found", flush=True)
            issues_found.append("No event dispatcher - events cannot be received")
        
        # Check 5: Debug mode
        print("\n5️⃣  Checking debug mode...", flush=True)
        if hasattr(self.meshcore, 'debug'):
            debug_enabled = getattr(self.meshcore, 'debug', False)
            if debug_enabled:
                print("   ✅ Debug mode is enabled", flush=True)
            else:
                print("   ℹ️  Debug mode is disabled (enable for more verbose logging)", flush=True)
        else:
            print("   ℹ️  Debug mode attribute not found", flush=True)
        
        # Summary
        print("\n" + "="*60, flush=True)
        if issues_found:
            print("⚠️  Configuration Issues Found:", flush=True)
            for i, issue in enumerate(issues_found, 1):
                print(f"   {i}. {issue}", flush=True)
            print("\n💡 Troubleshooting Tips:", flush=True)
            print("   • Ensure the MeshCore device has a private key configured", flush=True)
            print("   • Check that contacts are properly synced", flush=True)
            print("   • Verify auto message fetching is started", flush=True)
            print("   • Try enabling debug mode for more detailed logs", flush=True)
        else:
            print("✅ No configuration issues detected", flush=True)
        print("="*60 + "\n", flush=True)
        
        return len(issues_found) == 0
    
    async def start(self):
        """Start monitoring"""
        print("🔧 MeshCore Serial Monitor - Diagnostic Tool", flush=True)
        print(f"   Port: {self.port}", flush=True)
        print(f"   Baudrate: {self.baudrate}", flush=True)
        print(f"   Debug mode: {'ENABLED' if self.debug else 'DISABLED'}", flush=True)
        if NACL_AVAILABLE:
            if self.private_key:
                print(f"   DM Decryption: ENABLED (private key provided)", flush=True)
            else:
                print(f"   DM Decryption: DISABLED (no private key)", flush=True)
        else:
            print(f"   DM Decryption: UNAVAILABLE (PyNaCl not installed)", flush=True)
        print(flush=True)
        
        try:
            # Connect to device
            print("🔌 Connecting to MeshCore device...", flush=True)
            self.meshcore = await self.MeshCore.create_serial(
                self.port,
                baudrate=self.baudrate,
                debug=self.debug  # Pass debug flag to meshcore library
            )
            print("✅ Connected successfully!", flush=True)
            print(flush=True)
            
            # Display MeshCore object info
            print("📊 MeshCore object info:", flush=True)
            try:
                print(f"   Type: {type(self.meshcore)}", flush=True)
            except Exception as e:
                print(f"   Type: <error: {e}>", flush=True)
            
            try:
                attrs = [a for a in dir(self.meshcore) if not a.startswith('_')]
                print(f"   Attributes ({len(attrs)} total):", flush=True)
                # Print in smaller chunks
                for i in range(0, len(attrs), 10):
                    chunk = attrs[i:i+10]
                    print(f"      {', '.join(chunk)}", flush=True)
            except Exception as e:
                print(f"   Attributes: <error: {e}>", flush=True)
            print(flush=True)
            
            # Run configuration diagnostics
            config_ok = await self._check_configuration()
            
            # Subscribe to messages
            print("📡 Setting up event subscription...", flush=True)
            
            # Try different subscription methods
            subscription_ok = False
            if hasattr(self.meshcore, 'events'):
                print("   Using: meshcore.events.subscribe()", flush=True)
                # Subscribe to CONTACT_MSG_RECV for actual DM messages
                self.meshcore.events.subscribe(self.EventType.CONTACT_MSG_RECV, self.on_message)
                print("   ✅ Subscribed to CONTACT_MSG_RECV events", flush=True)
                
                # Also subscribe to RX_LOG_DATA to track raw RF activity
                if hasattr(self.EventType, 'RX_LOG_DATA'):
                    self.meshcore.events.subscribe(self.EventType.RX_LOG_DATA, self.on_rx_log_data)
                    print("   ✅ Subscribed to RX_LOG_DATA events (RF activity)", flush=True)
                
                subscription_ok = True
            elif hasattr(self.meshcore, 'dispatcher'):
                print("   Using: meshcore.dispatcher.subscribe()", flush=True)
                # Subscribe to CONTACT_MSG_RECV for actual DM messages
                self.meshcore.dispatcher.subscribe(self.EventType.CONTACT_MSG_RECV, self.on_message)
                print("   ✅ Subscribed to CONTACT_MSG_RECV events", flush=True)
                
                # Also subscribe to RX_LOG_DATA to track raw RF activity
                if hasattr(self.EventType, 'RX_LOG_DATA'):
                    self.meshcore.dispatcher.subscribe(self.EventType.RX_LOG_DATA, self.on_rx_log_data)
                    print("   ✅ Subscribed to RX_LOG_DATA events (RF activity)", flush=True)
                
                subscription_ok = True
            else:
                print("   ❌ No known subscription method found!", flush=True)
                print(f"   Available attributes: {dir(self.meshcore)}", flush=True)
                return
            
            if not subscription_ok:
                print("   ❌ Event subscription failed!", flush=True)
                return
            
            print(flush=True)
            
            # Sync contacts first
            print("🔄 Syncing contacts...", flush=True)
            if hasattr(self.meshcore, 'sync_contacts'):
                try:
                    await self.meshcore.sync_contacts()
                    print("✅ Contacts synced successfully", flush=True)
                except Exception as e:
                    print(f"   ⚠️  Error syncing contacts: {e}", flush=True)
                    print(f"   This may prevent decryption of incoming messages", flush=True)
            else:
                print("   ⚠️  sync_contacts() not available", flush=True)
                print("   Decryption of incoming messages may fail", flush=True)
            print(flush=True)
            
            # Start auto message fetching
            print("🚀 Starting auto message fetching...", flush=True)
            if hasattr(self.meshcore, 'start_auto_message_fetching'):
                try:
                    await self.meshcore.start_auto_message_fetching()
                    print("✅ Auto message fetching started", flush=True)
                except Exception as e:
                    print(f"   ⚠️  Error starting auto message fetching: {e}", flush=True)
                    print(f"   Messages may not be received automatically", flush=True)
            else:
                print("   ⚠️  start_auto_message_fetching() not available", flush=True)
                print("   Messages may not be received automatically", flush=True)
            print(flush=True)
            
            print("="*60, flush=True)
            print("✅ Monitor ready! Waiting for messages...", flush=True)
            print("   Send a DM to this device to test", flush=True)
            print("   Press Ctrl+C to exit", flush=True)
            if not config_ok:
                print("\n   ⚠️  Configuration issues detected (see above)", flush=True)
                print("   If messages are not received/decrypted, check:", flush=True)
                print("   • Private key is configured on the device", flush=True)
                print("   • Contacts are properly synced", flush=True)
                print("   • Auto message fetching is running", flush=True)
            print("="*60, flush=True)
            print(flush=True)
            
            # Start heartbeat task to show monitor is alive
            heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            
            # Keep running
            try:
                while self.running:
                    await asyncio.sleep(0.1)
            finally:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
                
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            await self.cleanup()
    
    async def _heartbeat_loop(self):
        """Periodic heartbeat to show monitor is still active"""
        while self.running:
            await asyncio.sleep(30)  # Heartbeat every 30 seconds
            if self.running:
                timestamp = datetime.now().strftime("%H:%M:%S")
                heartbeat_msg = f"[{timestamp}] 💓 Monitor active | DM messages: {self.message_count} | RF packets: {self.rx_log_count}"
                
                # Add warning if RF packets received but no DMs
                if self.rx_log_count > 0 and self.message_count == 0:
                    heartbeat_msg += " ⚠️  (RF received but no DM decoded)"
                
                print(heartbeat_msg, flush=True)
    
    async def cleanup(self):
        """Cleanup resources"""
        print("\n\n🛑 Shutting down...")
        
        if self.meshcore:
            try:
                if hasattr(self.meshcore, 'disconnect'):
                    await self.meshcore.disconnect()
                print("✅ Disconnected from device")
            except Exception as e:
                print(f"⚠️  Disconnect error: {e}")
        
        print(f"\n📊 Statistics:")
        print(f"   DM messages received: {self.message_count}")
        print(f"   RF packets received: {self.rx_log_count}")
        if self.private_key:
            print(f"   Messages decrypted: {self.decryption_count}")
        print("\n✅ Monitor stopped")
    
    def stop(self):
        """Stop monitoring"""
        self.running = False


async def main():
    """Main entry point"""
    # Parse command line arguments first (before importing meshcore)
    parser = argparse.ArgumentParser(
        description='MeshCore Serial Monitor - Diagnostic tool for meshcore-cli',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Use default port /dev/ttyACM0, no debug
  %(prog)s /dev/ttyUSB0                       # Use custom port, no debug
  %(prog)s --debug                            # Default port with debug enabled
  %(prog)s /dev/ttyUSB0 --debug               # Custom port with debug enabled
  %(prog)s --private-key <base64_key>         # With DM decryption (base64 key)
  %(prog)s --private-key-file key.txt         # With DM decryption (from file)
  %(prog)s --private-key <key> --debug        # DM decryption + debug mode

DM Decryption:
  When --private-key or --private-key-file is provided, the monitor will attempt
  to decrypt encrypted Direct Messages using PyNaCl (Curve25519+XSalsa20-Poly1305).
  
  The private key should be:
  - 32 bytes in base64 format (e.g., "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXowMTIzNDU=")
  - OR 32 bytes in hex format (e.g., "6162636465666768696a6b6c6d6e6f707172737475767778797a30313233343")
  
  The monitor will automatically detect encrypted messages and attempt decryption.
        """
    )
    parser.add_argument(
        'port',
        nargs='?',
        default='/dev/ttyACM0',
        help='Serial port (default: /dev/ttyACM0)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode for verbose meshcore library output'
    )
    parser.add_argument(
        '--private-key',
        type=str,
        help='Private key for DM decryption (base64 or hex format, 32 bytes)'
    )
    parser.add_argument(
        '--private-key-file',
        type=str,
        help='Path to file containing private key (base64 or hex format)'
    )
    
    args = parser.parse_args()
    
    # Read private key from file if specified
    private_key = args.private_key
    if args.private_key_file:
        try:
            with open(args.private_key_file, 'r') as f:
                private_key = f.read().strip()
                print(f"✅ Loaded private key from {args.private_key_file}")
        except Exception as e:
            print(f"❌ Failed to read private key file: {e}")
            sys.exit(1)
    
    # Now try to import meshcore (after parsing args so --help works)
    try:
        from meshcore import MeshCore, EventType
    except ImportError:
        print("❌ meshcore-cli library not installed")
        print("   Install with: pip install meshcore")
        sys.exit(1)
    
    # Create monitor with debug flag
    monitor = MeshCoreMonitor(
        port=args.port, 
        debug=args.debug,
        meshcore_module=MeshCore,
        event_type=EventType,
        private_key=private_key
    )
    
    # Handle Ctrl+C
    def signal_handler(sig, frame):
        print("\n\n⚠️  Interrupt signal received")
        monitor.stop()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start monitoring
    await monitor.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n✅ Exited cleanly")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
