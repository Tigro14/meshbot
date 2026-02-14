#!/usr/bin/env python3
"""
MeshCore Public Channel Listener
Diagnostic tool to listen to MeshCore public channel messages and log details

Usage:
    python listen_meshcore_channel.py [PORT]
    
    PORT: Serial port (default: /dev/ttyACM2)
    
Examples:
    python listen_meshcore_channel.py
    python listen_meshcore_channel.py /dev/ttyACM1
    python listen_meshcore_channel.py /dev/ttyACM0
"""

import time
import sys
from datetime import datetime

# Try to import meshcore-cli
try:
    from meshcore import MeshCore, EventType
    print("✅ meshcore-cli library available")
except ImportError:
    print("❌ ERROR: meshcore-cli not installed")
    print("   Install: pip install meshcore")
    sys.exit(1)

# Try to import meshcore-decoder
try:
    from meshcoredecoder import MeshCoreDecoder
    from meshcoredecoder.utils.enum_names import get_route_type_name, get_payload_type_name
    DECODER_AVAILABLE = True
    print("✅ meshcore-decoder available")
except ImportError:
    DECODER_AVAILABLE = False
    print("⚠️  meshcore-decoder not available (optional)")
    print("   Install: pip install meshcoredecoder")

def format_timestamp():
    """Get formatted timestamp"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

def format_hex(data):
    """Format bytes as hex string"""
    if isinstance(data, bytes):
        return ' '.join(f'{b:02x}' for b in data)
    return str(data)

def on_message(event_type, data):
    """
    Callback for MeshCore messages
    
    Args:
        event_type: EventType enum value
        data: Message data dict
    """
    print("\n" + "="*80)
    print(f"[{format_timestamp()}] 📡 MESHCORE EVENT RECEIVED")
    print("="*80)
    
    # Event type
    print(f"Event Type: {event_type}")
    if hasattr(EventType, 'CHANNEL_MSG_RECV') and event_type == EventType.CHANNEL_MSG_RECV:
        print("✅ This is a CHANNEL_MSG_RECV (Public channel message)")
    
    # Raw data
    print(f"\n📋 RAW DATA:")
    print(f"  Type: {type(data)}")
    if isinstance(data, dict):
        print(f"  Keys: {list(data.keys())}")
        for key, value in data.items():
            if isinstance(value, bytes):
                print(f"  {key}: {len(value)} bytes")
                print(f"    Hex: {format_hex(value)[:100]}...")
                print(f"    Raw: {repr(value[:50])}...")
            else:
                print(f"  {key}: {value}")
    else:
        print(f"  Data: {data}")
    
    # Try to decode with meshcore-decoder if available
    if DECODER_AVAILABLE and isinstance(data, dict):
        raw_packet = data.get('raw_packet') or data.get('packet') or data.get('data')
        if raw_packet and isinstance(raw_packet, bytes):
            print(f"\n🔍 DECODED PACKET (meshcore-decoder):")
            try:
                decoder = MeshCoreDecoder()
                decoded = decoder.decode(raw_packet)
                
                print(f"  From: 0x{decoded.get('from', 0):08x}")
                print(f"  To: 0x{decoded.get('to', 0):08x}")
                print(f"  Type: {decoded.get('type', 'unknown')}")
                
                if 'payload' in decoded:
                    payload = decoded['payload']
                    print(f"  Payload: {len(payload)} bytes")
                    print(f"    Hex: {format_hex(payload)[:100]}")
                    print(f"    Raw: {repr(payload[:50])}")
                
                if 'text' in decoded:
                    print(f"  Text: {decoded['text']}")
                
                # Show all decoded fields
                print(f"\n  All fields:")
                for key, value in decoded.items():
                    if key not in ['payload', 'from', 'to', 'type', 'text']:
                        if isinstance(value, bytes):
                            print(f"    {key}: {format_hex(value)[:50]}")
                        else:
                            print(f"    {key}: {value}")
                            
            except Exception as e:
                print(f"  ❌ Decode error: {e}")
    
    print("="*80)
    print()

def main():
    """Main function"""
    # Parse command-line arguments
    port = "/dev/ttyACM2"  # Default port
    baudrate = 115200
    
    if len(sys.argv) > 1:
        if sys.argv[1] in ['-h', '--help', 'help']:
            print("Usage: python listen_meshcore_channel.py [PORT]")
            print()
            print("Arguments:")
            print("  PORT    Serial port (default: /dev/ttyACM2)")
            print()
            print("Examples:")
            print("  python listen_meshcore_channel.py")
            print("  python listen_meshcore_channel.py /dev/ttyACM1")
            print("  python listen_meshcore_channel.py /dev/ttyACM0")
            return 0
        else:
            port = sys.argv[1]
    
    print("="*80)
    print("🎯 MeshCore Public Channel Listener")
    print("="*80)
    print(f"Device: {port} @ {baudrate} baud")
    print(f"Started: {format_timestamp()}")
    print("Purpose: Listen to MeshCore public channel messages")
    print()
    print("Press Ctrl+C to stop")
    print("="*80)
    print()
    
    try:
        # Connect to MeshCore
        print(f"[{format_timestamp()}] 🔌 Connecting to MeshCore on {port}...")
        meshcore = MeshCore(port, baudrate)
        print(f"[{format_timestamp()}] ✅ Connected to MeshCore")
        
        # Subscribe to CHANNEL_MSG_RECV events
        if hasattr(EventType, 'CHANNEL_MSG_RECV'):
            print(f"[{format_timestamp()}] 📡 Subscribing to CHANNEL_MSG_RECV...")
            meshcore.subscribe(EventType.CHANNEL_MSG_RECV, on_message)
            print(f"[{format_timestamp()}] ✅ Subscribed successfully")
        else:
            print(f"[{format_timestamp()}] ⚠️  CHANNEL_MSG_RECV not available in this version")
            print(f"[{format_timestamp()}] 📡 Subscribing to all events...")
            # Subscribe to all available events
            for attr in dir(EventType):
                if not attr.startswith('_') and hasattr(getattr(EventType, attr), 'value'):
                    event = getattr(EventType, attr)
                    meshcore.subscribe(event, on_message)
            print(f"[{format_timestamp()}] ✅ Subscribed to all events")
        
        print()
        print("🎧 Listening for messages...")
        print("   Send /echo test on MeshCore Public channel to see output!")
        print()
        
        # Keep running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print()
        print(f"[{format_timestamp()}] ⏹️  Stopped by user")
    except Exception as e:
        print()
        print("="*80)
        print(f"[{format_timestamp()}] ❌ ERROR: {e}")
        print("="*80)
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
