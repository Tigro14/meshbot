#!/usr/bin/env python3
"""
MeshCore Diagnostic Tool - Pure MeshCore Decoder (NO Meshtastic!)

This tool listens to MeshCore Public channel messages and logs all details.
Uses ONLY meshcore and meshcoredecoder libraries - no meshtastic imports.

IMPORTANT: This tool now uses CHANNEL_MSG_RECV by default (like meshcore-cli).
The MeshCore library decrypts messages internally using the device's configured PSK.
No manual PSK decryption needed!

Usage:
    python3 listen_meshcore_debug.py [port]
    
    port: Serial port (default: /dev/ttyACM2)
    
Examples:
    python3 listen_meshcore_debug.py /dev/ttyACM1
    python3 listen_meshcore_debug.py --help

Note: Subscribes to CHANNEL_MSG_RECV (pre-decrypted by library) not RX_LOG_DATA (raw RF).
This matches how meshcore-cli works - no PSK needed!
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

# Import cryptography for MeshCore Public channel decryption
try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    import base64
    print("✅ cryptography library available (decryption enabled)")
    CRYPTO_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  WARNING: cryptography library not found")
    print(f"   Install with: pip install cryptography")
    print(f"   MeshCore Public channel decryption disabled")
    CRYPTO_AVAILABLE = False

# Import config for MESHCORE_PUBLIC_PSK
try:
    from config import MESHCORE_PUBLIC_PSK
    print(f"✅ MESHCORE_PUBLIC_PSK loaded from config")
except ImportError:
    print(f"⚠️  WARNING: Could not load MESHCORE_PUBLIC_PSK from config")
    print(f"   Using default MeshCore Public PSK")
    MESHCORE_PUBLIC_PSK = "izOH6cXN6mrJ5e26oRXNcg=="  # Default MeshCore Public channel PSK


def decrypt_meshcore_public(encrypted_bytes, packet_id, from_id):
    """
    Decrypt MeshCore Public channel encrypted message using AES-128-CTR.
    
    IMPORTANT: This function is for EDUCATIONAL purposes only!
    
    In practice, you should use CHANNEL_MSG_RECV events which provide
    pre-decrypted text from the MeshCore library. The library uses the
    device's configured PSK - not from our Python config!
    
    This is how meshcore-cli works - it doesn't decrypt manually,
    it just reads pre-decrypted text from library events.
    
    Args:
        encrypted_bytes: Encrypted payload data (bytes)
        packet_id: Packet ID from decoded packet
        from_id: Sender node ID from decoded packet
        
    Returns:
        Decrypted text string or None if decryption fails
    """
    if not CRYPTO_AVAILABLE:
        return None
        
    try:
        # Convert PSK from base64 to bytes
        if isinstance(MESHCORE_PUBLIC_PSK, str):
            psk = base64.b64decode(MESHCORE_PUBLIC_PSK)
        else:
            psk = MESHCORE_PUBLIC_PSK
            
        # Ensure PSK is 16 bytes for AES-128
        if len(psk) != 16:
            print(f"⚠️  PSK length is {len(psk)} bytes, expected 16 bytes")
            return None
        
        # Construct nonce for AES-CTR (16 bytes)
        # MeshCore uses: packet_id (8 bytes LE) + from_id (4 bytes LE) + padding (4 zeros)
        nonce = packet_id.to_bytes(8, 'little') + from_id.to_bytes(4, 'little') + b'\x00' * 4
        
        # Create AES-128-CTR cipher
        cipher = Cipher(
            algorithms.AES(psk),
            modes.CTR(nonce),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        
        # Decrypt
        decrypted_bytes = decryptor.update(encrypted_bytes) + decryptor.finalize()
        
        # Try to decode as UTF-8 text
        decrypted_text = decrypted_bytes.decode('utf-8', errors='ignore').rstrip('\x00')
        
        return decrypted_text
        
    except Exception as e:
        print(f"⚠️  Decryption failed: {e}")
        return None


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
                    
                    # Get human-readable names for types
                    route_name = get_route_type_name(decoded.route_type) if get_route_type_name else str(decoded.route_type)
                    payload_name = get_payload_type_name(decoded.payload_type) if get_payload_type_name else str(decoded.payload_type)
                    
                    # Show packet structure with enhanced information
                    if hasattr(decoded, 'sender_id'):
                        print(f"  From: 0x{decoded.sender_id:08x}")
                    if hasattr(decoded, 'receiver_id'):
                        recv_id = decoded.receiver_id
                        if recv_id == 0xFFFFFFFF:
                            print(f"  To: Broadcast (0xFFFFFFFF)")
                        else:
                            print(f"  To: 0x{recv_id:08x}")
                    
                    # Show payload type
                    if hasattr(decoded, 'payload_type'):
                        ptype = decoded.payload_type
                        if hasattr(ptype, 'value'):
                            print(f"  Payload Type: {ptype.value} ({ptype.name})")
                        else:
                            print(f"  Payload Type: {ptype}")
                    else:
                        print(f"  Payload Type: {payload_name}")
                    
                    # Show route type
                    print(f"  Route: {route_name}")
                    
                    # Show hop count and path information
                    if hasattr(decoded, 'path_length'):
                        print(f"  Hops: {decoded.path_length}")
                    elif hasattr(decoded, 'hop_count'):
                        print(f"  Hops: {decoded.hop_count}")
                    
                    # Show routing path if available
                    if hasattr(decoded, 'path') and decoded.path:
                        path_str = ' → '.join([f"0x{node:08x}" if isinstance(node, int) else str(node) for node in decoded.path])
                        print(f"  Path: {path_str}")
                    
                    # Show message hash
                    if hasattr(decoded, 'message_hash') and decoded.message_hash:
                        print(f"  Message Hash: {decoded.message_hash[:16]}...")
                    
                    # Show packet size
                    if hasattr(decoded, 'total_bytes') and decoded.total_bytes > 0:
                        print(f"  Packet Size: {decoded.total_bytes} bytes")
                    
                    # Show validity status
                    if hasattr(decoded, 'is_valid'):
                        status = "✅ Valid" if decoded.is_valid else "⚠️ Invalid"
                        print(f"  Status: {status}")
                    
                    # Show any errors
                    if hasattr(decoded, 'errors') and decoded.errors:
                        print(f"  ⚠️ Errors:")
                        for error in decoded.errors[:3]:  # Show first 3 errors
                            print(f"     - {error}")
                    
                    # Show payload details with comprehensive analysis
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
                        
                        # Determine if this is a public/broadcast message
                        is_public = route_name in ['Flood', 'TransportFlood']
                        
                        if isinstance(payload_data, dict):
                            print(f"  Type: dict")
                            print(f"  Keys: {list(payload_data.keys())}")
                            
                            # Check for decoded payload
                            decoded_payload = payload_data.get('decoded')
                            has_text = False
                            
                            if decoded_payload:
                                decoded_type = type(decoded_payload).__name__
                                print(f"  Decoded Type: {decoded_type}")
                                
                                # Handle TextMessage - show with public/DM context
                                if hasattr(decoded_payload, 'text'):
                                    msg_type = "📢 Public" if is_public else "📨 Direct"
                                    print(f"\n  ✅ DECRYPTED TEXT ({msg_type}):")
                                    print(f"     \"{decoded_payload.text}\"")
                                    print(f"     → Message successfully decrypted and decoded")
                                    has_text = True
                                
                                # Handle Advert with app_data
                                elif hasattr(decoded_payload, 'app_data'):
                                    app_data = decoded_payload.app_data
                                    print(f"\n  📣 ADVERT (Device Advertisement):")
                                    if isinstance(app_data, dict):
                                        name = app_data.get('name', 'Unknown')
                                        print(f"     Device: {name}")
                                        if 'role' in app_data:
                                            print(f"     Role: {app_data.get('role')}")
                                        if 'hw_model' in app_data:
                                            print(f"     Hardware: {app_data.get('hw_model')}")
                                    
                                    # Show public key if available
                                    if hasattr(decoded_payload, 'public_key') and decoded_payload.public_key:
                                        pubkey_prefix = decoded_payload.public_key[:12]
                                        node_id_hex = decoded_payload.public_key[:8]
                                        try:
                                            node_id = int(node_id_hex, 16)
                                            print(f"     Node ID: 0x{node_id:08x}")
                                        except:
                                            print(f"     Public Key: {pubkey_prefix}...")
                                
                                # Handle NodeInfo
                                elif hasattr(decoded_payload, 'long_name'):
                                    print(f"\n  📋 NODE INFO:")
                                    print(f"     Long Name: {decoded_payload.long_name}")
                                    if hasattr(decoded_payload, 'short_name'):
                                        print(f"     Short Name: {decoded_payload.short_name}")
                                    if hasattr(decoded_payload, 'hw_model'):
                                        print(f"     Hardware: {decoded_payload.hw_model}")
                                    if hasattr(decoded_payload, 'role'):
                                        print(f"     Role: {decoded_payload.role}")
                                
                                # Handle Position
                                elif hasattr(decoded_payload, 'latitude') or hasattr(decoded_payload, 'longitude'):
                                    print(f"\n  📍 POSITION:")
                                    if hasattr(decoded_payload, 'latitude'):
                                        print(f"     Latitude: {decoded_payload.latitude}")
                                    if hasattr(decoded_payload, 'longitude'):
                                        print(f"     Longitude: {decoded_payload.longitude}")
                                    if hasattr(decoded_payload, 'altitude'):
                                        print(f"     Altitude: {decoded_payload.altitude}m")
                                
                                # Handle Telemetry
                                elif hasattr(decoded_payload, 'battery_level') or hasattr(decoded_payload, 'temperature'):
                                    print(f"\n  📊 TELEMETRY:")
                                    if hasattr(decoded_payload, 'battery_level'):
                                        print(f"     Battery: {decoded_payload.battery_level}%")
                                    if hasattr(decoded_payload, 'voltage'):
                                        print(f"     Voltage: {decoded_payload.voltage}V")
                                    if hasattr(decoded_payload, 'temperature'):
                                        print(f"     Temperature: {decoded_payload.temperature}°C")
                                    if hasattr(decoded_payload, 'humidity'):
                                        print(f"     Humidity: {decoded_payload.humidity}%")
                                
                                # Handle ResponsePayload (usually encrypted)
                                elif decoded_type == 'ResponsePayload':
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
                            
                            # Analyze encryption status and try decryption
                            if not has_text and raw_data:
                                # Try to decrypt TextMessage on Public channel
                                decrypted_text = None
                                if (ptype_name == 'TextMessage' or ptype_value == 15) and CRYPTO_AVAILABLE:
                                    # Get packet_id and sender_id for decryption
                                    packet_id = None
                                    sender_id = None
                                    
                                    # Try to extract packet_id from decoded packet
                                    if hasattr(decoded, 'packet_id'):
                                        packet_id = decoded.packet_id
                                    elif hasattr(decoded, 'id'):
                                        packet_id = decoded.id
                                        
                                    # Try to extract sender_id
                                    if hasattr(decoded, 'sender_id'):
                                        sender_id = decoded.sender_id
                                    elif hasattr(decoded, 'from_id'):
                                        sender_id = decoded.from_id
                                    
                                    # Try decryption if we have necessary info
                                    if packet_id is not None and sender_id is not None:
                                        print(f"\n  🔓 ATTEMPTING DECRYPTION...")
                                        print(f"     Packet ID: {packet_id}")
                                        print(f"     From: 0x{sender_id:08x}")
                                        
                                        # Convert raw_data to bytes if needed
                                        if isinstance(raw_data, str):
                                            raw_bytes = bytes.fromhex(raw_data)
                                        else:
                                            raw_bytes = raw_data
                                        
                                        decrypted_text = decrypt_meshcore_public(raw_bytes, packet_id, sender_id)
                                        
                                        if decrypted_text:
                                            msg_type = "📢 Public" if is_public else "📨 Direct"
                                            print(f"\n  ✅ DECRYPTED TEXT ({msg_type}):")
                                            print(f"     \"{decrypted_text}\"")
                                            print(f"     → Message successfully decrypted with MeshCore Public PSK")
                                            has_text = True
                                        else:
                                            print(f"     ❌ Decryption failed (wrong PSK or not a text message)")
                                
                                # If still encrypted, show info
                                if not has_text:
                                    print(f"\n  🔒 ENCRYPTED PAYLOAD")
                                    
                                    # Provide context based on payload type
                                    if ptype_value == 1:  # Response
                                        print(f"     ℹ️  This is an encrypted response packet (type 1)")
                                        print(f"     → ResponsePayloads are typically encrypted responses to requests")
                                        print(f"     → To decrypt, you need the channel PSK")
                                    elif ptype_name == 'TextMessage' or ptype_value == 15:
                                        print(f"     ℹ️  This text message is encrypted on MeshCore Public channel")
                                        print(f"")
                                        print(f"     📋 MeshCore Public Channel Default PSK:")
                                        print(f"        Base64: {MESHCORE_PUBLIC_PSK}")
                                        print(f"        Hex: 8b3387e9c5cdea6ac9e5edbaa115cd72")
                                        print(f"")
                                        print(f"     → This is the REAL MeshCore Public channel PSK")
                                        print(f"     → NOT the Meshtastic default (AQ==)")
                                        if not CRYPTO_AVAILABLE:
                                            print(f"     ⚠️  Cryptography library not available - cannot decrypt")
                                            print(f"     → Install with: pip install cryptography")
                                        elif packet_id is None or sender_id is None:
                                            print(f"     ⚠️  Missing packet_id or sender_id - cannot decrypt")
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
        # 
        # IMPORTANT: Priority changed based on user insight!
        # User correctly pointed out: "when I use the CLI i do not need to provide any key"
        # This is because MeshCore library decrypts internally using device's configured PSK.
        # 
        # Priority: CHANNEL_MSG_RECV (pre-decrypted by library) > RX_LOG_DATA (raw RF)
        # 
        # CHANNEL_MSG_RECV: Pre-decrypted Public channel messages from library
        #   - Library uses device's configured PSK (not from our config!)
        #   - Provides decoded.text directly
        #   - No manual decryption needed
        #   - Works like meshcore-cli!
        # 
        # RX_LOG_DATA: Raw RF packets (all types - broadcasts, DMs, telemetry)
        #   - Gives encrypted payloads
        #   - Requires manual decryption with PSK
        #   - Wrong approach for Public channel messages
        #   - Only useful for RF monitoring/statistics
        print("🎧 Subscribing to MeshCore events...")
        
        subscribed = False
        
        if hasattr(meshcore, 'events'):
            # Newer MeshCore API
            # Try CHANNEL_MSG_RECV first (pre-decrypted by library, like meshcore-cli!)
            if hasattr(EventType, 'CHANNEL_MSG_RECV'):
                meshcore.events.subscribe(EventType.CHANNEL_MSG_RECV, on_message)
                print("   ✅ Subscribed to CHANNEL_MSG_RECV via events.subscribe()")
                print("   → Will receive pre-decrypted Public channel messages")
                print("   → Library handles decryption using device's configured PSK")
                print("   → Works like meshcore-cli - no manual PSK needed!")
                subscribed = True
            elif hasattr(EventType, 'RX_LOG_DATA'):
                meshcore.events.subscribe(EventType.RX_LOG_DATA, on_message)
                print("   ✅ Subscribed to RX_LOG_DATA via events.subscribe()")
                print("   → Will receive raw RF packets (requires manual decryption)")
                print("   ⚠️  WARNING: Manual decryption may not work (wrong PSK)")
                subscribed = True
        elif hasattr(meshcore, 'dispatcher'):
            # Older MeshCore API
            # Try CHANNEL_MSG_RECV first (pre-decrypted by library, like meshcore-cli!)
            if hasattr(EventType, 'CHANNEL_MSG_RECV'):
                meshcore.dispatcher.subscribe(EventType.CHANNEL_MSG_RECV, on_message)
                print("   ✅ Subscribed to CHANNEL_MSG_RECV via dispatcher.subscribe()")
                print("   → Will receive pre-decrypted Public channel messages")
                print("   → Library handles decryption using device's configured PSK")
                print("   → Works like meshcore-cli - no manual PSK needed!")
                subscribed = True
            elif hasattr(EventType, 'RX_LOG_DATA'):
                meshcore.dispatcher.subscribe(EventType.RX_LOG_DATA, on_message)
                print("   ✅ Subscribed to RX_LOG_DATA via dispatcher.subscribe()")
                print("   → Will receive raw RF packets (requires manual decryption)")
                print("   ⚠️  WARNING: Manual decryption may not work (wrong PSK)")
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
