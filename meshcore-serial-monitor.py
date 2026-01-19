#!/usr/bin/env python3
"""
MeshCore Serial Monitor - Standalone diagnostic tool
Tests meshcore-cli library API and displays received messages
"""

import asyncio
import sys
import signal
from datetime import datetime

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
        print(f"Event: {event}")
        
        # Try to extract payload
        if hasattr(event, '__dict__'):
            print(f"\nEvent attributes:")
            for key, value in event.__dict__.items():
                print(f"  {key}: {value}")
        
        # Try common payload patterns
        payload = None
        if hasattr(event, 'payload'):
            payload = event.payload
        elif hasattr(event, 'data'):
            payload = event.data
        elif hasattr(event, 'message'):
            payload = event.message
            
        if payload:
            print(f"\nPayload: {payload}")
            
            # Extract contact_id and text if present
            if isinstance(payload, dict):
                contact_id = payload.get('contact_id')
                text = payload.get('text')
                
                if contact_id:
                    print(f"  From: 0x{contact_id:08x}")
                if text:
                    print(f"  Text: {text}")
        
        print(f"{'='*60}\n")
        
    async def start(self):
        """Start monitoring"""
        print("🔧 MeshCore Serial Monitor")
        print(f"   Port: {self.port}")
        print(f"   Baudrate: {self.baudrate}")
        print()
        
        try:
            # Connect to device
            print("🔌 Connecting to MeshCore device...")
            self.meshcore = await MeshCore.create_serial(
                self.port,
                baudrate=self.baudrate,
                debug=False
            )
            print("✅ Connected successfully!")
            print()
            
            # Display MeshCore object info
            print("📊 MeshCore object info:")
            print(f"   Type: {type(self.meshcore)}")
            print(f"   Attributes: {[a for a in dir(self.meshcore) if not a.startswith('_')]}")
            print()
            
            # Subscribe to messages
            print("📡 Setting up event subscription...")
            
            # Try different subscription methods
            if hasattr(self.meshcore, 'events'):
                print("   Using: meshcore.events.subscribe()")
                self.meshcore.events.subscribe(EventType.CONTACT_MSG_RECV, self.on_message)
            elif hasattr(self.meshcore, 'dispatcher'):
                print("   Using: meshcore.dispatcher.subscribe()")
                self.meshcore.dispatcher.subscribe(EventType.CONTACT_MSG_RECV, self.on_message)
            else:
                print("   ❌ No known subscription method found!")
                print(f"   Available attributes: {dir(self.meshcore)}")
                return
            
            print("✅ Subscribed to CONTACT_MSG_RECV events")
            print()
            
            # Start auto message fetching
            print("🚀 Starting auto message fetching...")
            if hasattr(self.meshcore, 'start_auto_message_fetching'):
                await self.meshcore.start_auto_message_fetching()
                print("✅ Auto message fetching started")
            else:
                print("   ⚠️  start_auto_message_fetching() not available")
                print("   Messages may not be received automatically")
            print()
            
            print("="*60)
            print("✅ Monitor ready! Waiting for messages...")
            print("   Send a message to this device to test")
            print("   Press Ctrl+C to exit")
            print("="*60)
            print()
            
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
