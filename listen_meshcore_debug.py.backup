#!/usr/bin/env python3
"""
MeshCore Diagnostic Tool - Pure MeshCore Decoder (NO Meshtastic!)

This tool listens to MeshCore Public channel messages and logs all details.
Uses ONLY meshcore and meshcoredecoder libraries - no meshtastic imports.

Usage:
    python3 listen_meshcore_debug.py [port]
    
    port: Serial port (default: /dev/ttyACM2)
    
Examples:
    python3 listen_meshcore_debug.py /dev/ttyACM1
    python3 listen_meshcore_debug.py --help
"""

import sys
import time
import asyncio
from datetime import datetime

# Import ONLY MeshCore libraries (NO meshtastic!)
try:
    from meshcore import MeshCore, EventType
    print("✅ meshcore library available")
except ImportError as e:
    print(f"❌ ERROR: meshcore library not found")
    print(f"   Install with: pip install meshcore")
    print(f"   Error: {e}")
    sys.exit(1)

try:
    from meshcoredecoder import MeshCoreDecoder
    from meshcoredecoder.utils.enum_names import get_route_type_name, get_payload_type_name
    print("✅ meshcoredecoder library available")
    DECODER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  WARNING: meshcoredecoder library not found")
    print(f"   Install with: pip install meshcoredecoder")
    print(f"   Will show raw data only")
    print(f"   Error: {e}")
    DECODER_AVAILABLE = False
    MeshCoreDecoder = None
    get_route_type_name = None
    get_payload_type_name = None


def format_hex(data):
    """Format bytes as hex string"""
    if isinstance(data, str):
        return data
    elif isinstance(data, (bytes, bytearray)):
        return ' '.join(f'{b:02x}' for b in data)
    else:
        return str(data)


def on_message(event):
    """Callback for MeshCore events
    
    Args:
        event: Event object from MeshCore (single parameter)
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    
    # Extract event type and payload from event object
    event_type = event.type if hasattr(event, 'type') else 'Unknown'
    payload = event.payload if hasattr(event, 'payload') else event
    
    print("\n" + "="*80)
    print(f"[{timestamp}] 📡 MESHCORE EVENT RECEIVED")
    print("="*80)
    print(f"Event Type: {event_type}")
    
    if hasattr(EventType, 'CHANNEL_MSG_RECV') and event_type == EventType.CHANNEL_MSG_RECV:
        print("✅ This is a CHANNEL_MSG_RECV (Public channel message)")
    elif hasattr(EventType, 'RX_LOG_DATA') and event_type == EventType.RX_LOG_DATA:
        print("✅ This is RX_LOG_DATA (ALL RF packets)")
    else:
        print(f"ℹ️  This is a different event type: {event_type}")
    
    print("\n📋 RAW DATA:")
    print(f"  Keys: {list(payload.keys()) if isinstance(payload, dict) else 'Not a dict'}")
    
    # Extract raw packet data
    raw_hex = None
    if isinstance(payload, dict):
        # Try different possible keys for raw data
        raw_hex = payload.get('raw_packet') or payload.get('data') or payload.get('payload')
        
        if raw_hex:
            if isinstance(raw_hex, str):
                print(f"  raw_packet: {len(raw_hex)//2} bytes")
                print(f"    Hex: {raw_hex[:80]}{'...' if len(raw_hex) > 80 else ''}")
            elif isinstance(raw_hex, (bytes, bytearray)):
                print(f"  raw_packet: {len(raw_hex)} bytes")
                hex_str = format_hex(raw_hex)
                print(f"    Hex: {hex_str[:80]}{'...' if len(hex_str) > 80 else ''}")
            
            # Try to decode with MeshCoreDecoder
            if DECODER_AVAILABLE and raw_hex:
                print("\n🔍 DECODED PACKET:")
                try:
                    decoded = MeshCoreDecoder.decode(raw_hex)
                    
                    # Show packet structure
                    if hasattr(decoded, 'sender_id'):
                        print(f"  From: 0x{decoded.sender_id:08x}")
                    if hasattr(decoded, 'receiver_id'):
                        print(f"  To: 0x{decoded.receiver_id:08x}")
                    if hasattr(decoded, 'payload_type'):
                        ptype = decoded.payload_type
                        if hasattr(ptype, 'value'):
                            print(f"  Payload Type: {ptype.value} ({ptype.name})")
                        else:
                            print(f"  Payload Type: {ptype}")
                    if hasattr(decoded, 'route_type'):
                        rtype = decoded.route_type
                        if hasattr(rtype, 'name'):
                            print(f"  Route: {rtype.name}")
                        else:
                            print(f"  Route: {rtype}")
                    if hasattr(decoded, 'hop_count'):
                        print(f"  Hops: {decoded.hop_count}")
                    
                    # Show payload details
                    if hasattr(decoded, 'payload'):
                        print("\n📦 PAYLOAD:")
                        payload_data = decoded.payload
                        
                        # Get payload type for context
                        ptype_name = "Unknown"
                        ptype_value = None
                        if hasattr(decoded, 'payload_type'):
                            ptype = decoded.payload_type
                            if hasattr(ptype, 'value'):
                                ptype_value = ptype.value
                                ptype_name = ptype.name
                            else:
                                ptype_value = ptype
                        
                        if isinstance(payload_data, dict):
                            print(f"  Type: dict")
                            print(f"  Keys: {list(payload_data.keys())}")
                            
                            # Check for decoded text
                            decoded_payload = payload_data.get('decoded')
                            has_text = False
                            if decoded_payload:
                                if hasattr(decoded_payload, 'text'):
                                    print(f"\n  ✅ DECRYPTED TEXT: \"{decoded_payload.text}\"")
                                    print(f"     → Message successfully decrypted and decoded")
                                    has_text = True
                                else:
                                    decoded_type = type(decoded_payload).__name__
                                    print(f"  Decoded payload type: {decoded_type}")
                                    
                                    # Special handling for ResponsePayload
                                    if decoded_type == 'ResponsePayload':
                                        print(f"\n  🔒 ENCRYPTED ResponsePayload (type {ptype_value})")
                            
                            # Check for raw data
                            raw_data = payload_data.get('raw')
                            if raw_data:
                                if isinstance(raw_data, str):
                                    print(f"  Raw data: {len(raw_data)//2} bytes (hex string)")
                                    print(f"    Hex: {raw_data[:80]}{'...' if len(raw_data) > 80 else ''}")
                                elif isinstance(raw_data, (bytes, bytearray)):
                                    print(f"  Raw data: {len(raw_data)} bytes")
                                    hex_str = format_hex(raw_data)
                                    print(f"    Hex: {hex_str[:80]}{'...' if len(hex_str) > 80 else ''}")
                            
                            # Analyze encryption status
                            if not has_text and raw_data:
                                print(f"\n  🔒 ENCRYPTED PAYLOAD")
                                
                                # Provide context based on payload type
                                if ptype_value == 1:  # Response
                                    print(f"     ℹ️  This is an encrypted response packet (type 1)")
                                    print(f"     → ResponsePayloads are typically encrypted responses to requests")
                                    print(f"     → To decrypt, you need the channel PSK")
                                elif ptype_name == 'TextMessage' or ptype_value == 15:
                                    print(f"     ℹ️  This text message is encrypted")
                                    print(f"     → If broadcast: needs default PSK")
                                    print(f"     → If channel: needs channel PSK")
                                    print(f"     → If DM: needs default PSK (Meshtastic 2.7.15+)")
                                else:
                                    print(f"     ℹ️  Payload type {ptype_value} ({ptype_name}) is encrypted")
                                    print(f"     → Check channel configuration for correct PSK")
                        else:
                            print(f"  Type: {type(payload_data).__name__}")
                            if isinstance(payload_data, (bytes, bytearray)):
                                print(f"  Size: {len(payload_data)} bytes")
                                hex_str = format_hex(payload_data)
                                print(f"  Hex: {hex_str[:80]}{'...' if len(hex_str) > 80 else ''}")
                    
                except Exception as e:
                    print(f"  ❌ Decoding failed: {e}")
                    import traceback
                    print(f"  Traceback: {traceback.format_exc()}")
            else:
                if not DECODER_AVAILABLE:
                    print("\n⚠️  MeshCoreDecoder not available - install meshcoredecoder for packet decoding")
        else:
            print("  ⚠️  No raw_packet data found in payload")
            print(f"  Available keys: {list(payload.keys())}")
    else:
        print(f"  ⚠️  Payload is not a dict: {type(payload).__name__}")
        print(f"  Payload: {str(payload)[:200]}")


def main():
    # Parse command-line arguments
    port = "/dev/ttyACM2"  # Default
    
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg in ['-h', '--help', 'help']:
            print(__doc__)
            print("\nDefault port: /dev/ttyACM2")
            print("\nNote: This tool uses ONLY meshcore libraries (no meshtastic!)")
            return
        else:
            port = arg
    
    print("="*80)
    print("🎯 MeshCore Debug Listener (Pure MeshCore - No Meshtastic!)")
    print("="*80)
    print(f"Device: {port} @ 115200 baud")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
    print("Purpose: Listen to MeshCore messages and decode packets")
    print("\nLibraries used:")
    print("  ✅ meshcore - MeshCore serial interface")
    print(f"  {'✅' if DECODER_AVAILABLE else '❌'} meshcoredecoder - Packet decoder")
    print("\nPress Ctrl+C to stop")
    print("="*80)
    
    try:
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] 🔌 Connecting to MeshCore...")
        
        # Create MeshCore instance using async factory method
        # Must use MeshCore.create_serial() - NOT direct instantiation!
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        meshcore = loop.run_until_complete(
            MeshCore.create_serial(port, baudrate=115200)
        )
        
        print(f"✅ Connected to MeshCore on {port}")
        
        # Subscribe to events
        # MeshCore API has two variants - check which one exists
        # Priority: RX_LOG_DATA (all RF packets) > CHANNEL_MSG_RECV (channel only)
        print("🎧 Subscribing to MeshCore events...")
        
        subscribed = False
        
        if hasattr(meshcore, 'events'):
            # Newer MeshCore API
            # Try RX_LOG_DATA first (receives ALL RF packets - broadcasts, DMs, telemetry)
            if hasattr(EventType, 'RX_LOG_DATA'):
                meshcore.events.subscribe(EventType.RX_LOG_DATA, on_message)
                print("   ✅ Subscribed to RX_LOG_DATA via events.subscribe()")
                print("   → Will receive ALL RF packets (broadcasts, channel, DMs, telemetry)")
                subscribed = True
            elif hasattr(EventType, 'CHANNEL_MSG_RECV'):
                meshcore.events.subscribe(EventType.CHANNEL_MSG_RECV, on_message)
                print("   ✅ Subscribed to CHANNEL_MSG_RECV via events.subscribe()")
                print("   → Will receive channel messages only")
                subscribed = True
        elif hasattr(meshcore, 'dispatcher'):
            # Older MeshCore API
            # Try RX_LOG_DATA first (receives ALL RF packets)
            if hasattr(EventType, 'RX_LOG_DATA'):
                meshcore.dispatcher.subscribe(EventType.RX_LOG_DATA, on_message)
                print("   ✅ Subscribed to RX_LOG_DATA via dispatcher.subscribe()")
                print("   → Will receive ALL RF packets (broadcasts, channel, DMs, telemetry)")
                subscribed = True
            elif hasattr(EventType, 'CHANNEL_MSG_RECV'):
                meshcore.dispatcher.subscribe(EventType.CHANNEL_MSG_RECV, on_message)
                print("   ✅ Subscribed to CHANNEL_MSG_RECV via dispatcher.subscribe()")
                print("   → Will receive channel messages only")
                subscribed = True
        
        if not subscribed:
            print("❌ ERROR: No subscription method available")
            print("   MeshCore object has neither 'events' nor 'dispatcher' attribute")
            print("   Or EventType has neither 'RX_LOG_DATA' nor 'CHANNEL_MSG_RECV'")
            print("   Check MeshCore library version")
            sys.exit(1)
        
        print("✅ Subscription successful")
        
        # CRITICAL: Start auto message fetching to receive events
        # Without this, MeshCore won't read from serial port!
        async def start_fetching():
            try:
                if hasattr(meshcore, 'start_auto_message_fetching'):
                    await meshcore.start_auto_message_fetching()
                    print("✅ Auto message fetching started")
                else:
                    print("⚠️  WARNING: start_auto_message_fetching() not available")
                    print("   Messages may not be received automatically")
            except Exception as e:
                print(f"❌ ERROR starting auto message fetching: {e}")
        
        loop.run_until_complete(start_fetching())
        
        print("\n🎧 Listening for messages...")
        print("   Send '/echo test' on MeshCore Public channel to see output!\n")
        
        # Keep event loop running to process callbacks
        # CRITICAL: Must use loop.run_forever() to process async events
        # Without this, callbacks are never invoked!
        loop.run_forever()
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Stopped by user (Ctrl+C)")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        print(f"\nTraceback:\n{traceback.format_exc()}")
    finally:
        print("\n👋 Exiting...")


if __name__ == "__main__":
    main()
