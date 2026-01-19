#!/usr/bin/env python3
"""
MeshCore Serial Monitor - Standalone diagnostic tool
Tests meshcore-cli library API and displays received messages
"""

import asyncio
import sys
import signal
from datetime import datetime

# Force unbuffered output for real-time logging
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

try:
    from meshcore import MeshCore, EventType
    MESHCORE_AVAILABLE = True
except ImportError:
    print("❌ meshcore-cli library not installed")
    print("   Install with: pip install meshcore")
    sys.exit(1)


class MeshCoreMonitor:
    """Simple monitor for MeshCore messages"""
    
    def __init__(self, port="/dev/ttyACM0", baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.meshcore = None
        self.running = True
        self.message_count = 0
        
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
        
        print(f"{'='*60}\n")
        
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
        print(flush=True)
        
        try:
            # Connect to device
            print("🔌 Connecting to MeshCore device...", flush=True)
            self.meshcore = await MeshCore.create_serial(
                self.port,
                baudrate=self.baudrate,
                debug=False
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
            if hasattr(self.meshcore, 'events'):
                print("   Using: meshcore.events.subscribe()", flush=True)
                self.meshcore.events.subscribe(EventType.CONTACT_MSG_RECV, self.on_message)
            elif hasattr(self.meshcore, 'dispatcher'):
                print("   Using: meshcore.dispatcher.subscribe()", flush=True)
                self.meshcore.dispatcher.subscribe(EventType.CONTACT_MSG_RECV, self.on_message)
            else:
                print("   ❌ No known subscription method found!", flush=True)
                print(f"   Available attributes: {dir(self.meshcore)}", flush=True)
                return
            
            print("✅ Subscribed to CONTACT_MSG_RECV events", flush=True)
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
            
            # Keep running
            while self.running:
                await asyncio.sleep(0.1)
                
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            await self.cleanup()
    
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
        print(f"   Messages received: {self.message_count}")
        print("\n✅ Monitor stopped")
    
    def stop(self):
        """Stop monitoring"""
        self.running = False


async def main():
    """Main entry point"""
    # Get port from command line or use default
    port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyACM0"
    
    # Create monitor
    monitor = MeshCoreMonitor(port=port)
    
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
