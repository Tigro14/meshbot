#!/usr/bin/env python3
"""
MeshCore Public Channel Listener
=================================

Diagnostic tool to listen to MeshCore Public channel messages and log them to stdout.

Purpose:
- Understand MeshCore Public channel message format
- Identify encryption method and PSK
- Debug the /echo command encryption issue

Usage:
    python listen_meshcore_public.py [PORT]
    
    PORT: Serial port (default: /dev/ttyACM2)
    
Examples:
    python listen_meshcore_public.py
    python listen_meshcore_public.py /dev/ttyACM1
    python listen_meshcore_public.py /dev/ttyACM0

Device: Configurable @ 115200 baud
"""

import sys
import time
from datetime import datetime
import meshtastic
import meshtastic.serial_interface


def print_separator():
    """Print a visual separator"""
    print("=" * 80)


def format_hex(data):
    """Format bytes as hex string"""
    if isinstance(data, bytes):
        return ' '.join(f'{b:02x}' for b in data)
    return str(data)


def format_timestamp():
    """Get formatted timestamp"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def on_receive(packet, interface):
    """Callback for received packets"""
    try:
        print_separator()
        print(f"[{format_timestamp()}] 📡 PACKET RECEIVED")
        print_separator()
        
        # Basic packet info
        print(f"From: 0x{packet.get('fromId', packet.get('from', 0)):08x}")
        print(f"To: 0x{packet.get('toId', packet.get('to', 0)):08x}")
        print(f"Channel: {packet.get('channel', 'N/A')}")
        
        # Decoded data
        decoded = packet.get('decoded', {})
        if decoded:
            print(f"\n📋 DECODED DATA:")
            print(f"  Portnum: {decoded.get('portnum', 'N/A')}")
            
            # Text message
            if 'text' in decoded:
                print(f"  Text: '{decoded['text']}'")
            
            # Raw payload
            if 'payload' in decoded:
                payload = decoded['payload']
                if isinstance(payload, bytes):
                    print(f"  Payload (bytes): {len(payload)} bytes")
                    print(f"  Payload (hex): {format_hex(payload)}")
                    print(f"  Payload (raw): {payload}")
                else:
                    print(f"  Payload: {payload}")
            
            # Other decoded fields
            for key, value in decoded.items():
                if key not in ['portnum', 'text', 'payload']:
                    print(f"  {key}: {value}")
        
        # Raw packet data
        print(f"\n🔍 RAW PACKET DATA:")
        for key, value in packet.items():
            if key == 'decoded':
                continue  # Already printed above
            if isinstance(value, bytes):
                print(f"  {key}: {format_hex(value)} ({len(value)} bytes)")
            else:
                print(f"  {key}: {value}")
        
        # Check if this is a TEXT_MESSAGE_APP on Public channel
        if decoded.get('portnum') == 'TEXT_MESSAGE_APP':
            print(f"\n✅ This is a TEXT_MESSAGE_APP")
            
            # Check if encrypted
            has_text = 'text' in decoded and decoded['text']
            has_payload = 'payload' in decoded and decoded['payload']
            
            if not has_text and has_payload:
                print(f"⚠️  ENCRYPTED: Has payload but no text")
                print(f"   Payload may be encrypted data")
            elif has_text:
                print(f"✅ DECRYPTED: Text content available")
                print(f"   Message: '{decoded['text']}'")
        
        print()
        
    except Exception as e:
        print(f"❌ ERROR processing packet: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main function"""
    # Parse command-line arguments
    port = "/dev/ttyACM2"  # Default port
    
    if len(sys.argv) > 1:
        if sys.argv[1] in ['-h', '--help', 'help']:
            print("Usage: python listen_meshcore_public.py [PORT]")
            print()
            print("Arguments:")
            print("  PORT    Serial port (default: /dev/ttyACM2)")
            print()
            print("Examples:")
            print("  python listen_meshcore_public.py")
            print("  python listen_meshcore_public.py /dev/ttyACM1")
            print("  python listen_meshcore_public.py /dev/ttyACM0")
            return 0
        else:
            port = sys.argv[1]
    
    print_separator()
    print("🎯 MeshCore Public Channel Listener")
    print_separator()
    print(f"Device: {port} @ 115200 baud")
    print(f"Started: {format_timestamp()}")
    print(f"Purpose: Listen to Public channel messages and log details")
    print()
    print("Press Ctrl+C to stop")
    print_separator()
    print()
    
    try:
        # Connect to Meshtastic device
        print(f"[{format_timestamp()}] 🔌 Connecting to {port}...")
        interface = meshtastic.serial_interface.SerialInterface(port)
        print(f"[{format_timestamp()}] ✅ Connected successfully")
        
        # Get node info
        try:
            node_info = interface.getMyNodeInfo()
            if node_info:
                print(f"[{format_timestamp()}] 📱 Node info:")
                print(f"   User: {node_info.get('user', {}).get('longName', 'N/A')}")
                print(f"   ID: {node_info.get('user', {}).get('id', 'N/A')}")
        except Exception as e:
            print(f"[{format_timestamp()}] ⚠️  Could not get node info: {e}")
        
        print()
        print(f"[{format_timestamp()}] 👂 Listening for messages...")
        print(f"[{format_timestamp()}] 💡 Send a message on the Public channel to see it logged here")
        print()
        
        # Subscribe to message events
        interface.onReceive = lambda packet, interface=interface: on_receive(packet, interface)
        
        # Keep running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print()
        print_separator()
        print(f"[{format_timestamp()}] 🛑 Stopped by user")
        print_separator()
        sys.exit(0)
        
    except Exception as e:
        print()
        print_separator()
        print(f"[{format_timestamp()}] ❌ ERROR: {e}")
        print_separator()
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
