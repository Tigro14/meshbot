#!/usr/bin/env python3
"""
Demo: Enhanced Packet Content Display
Shows packet type/family/content for public, advertising, and routing packets
"""

import sys

def demo_enhanced_content():
    """Demonstrate enhanced packet content display"""
    print("\n" + "="*70)
    print("Enhanced Packet Content Display Demo")
    print("="*70 + "\n")
    
    # Check if meshcoredecoder is available
    try:
        from meshcoredecoder import MeshCoreDecoder
        from meshcoredecoder.types import RouteType
        from meshcoredecoder.utils.enum_names import get_route_type_name, get_payload_type_name
        print("✅ meshcoredecoder is available\n")
    except ImportError:
        print("❌ meshcoredecoder not installed")
        print("Install with: pip install meshcoredecoder")
        return 1
    
    # Test packets showcasing different content types
    test_packets = [
        {
            'name': 'Advertisement with Device Info',
            'hex': '11007E7662676F7F0850A8A355BAAFBFC1EB7B4174C340442D7D7161C9474A2C94006CE7CF682E58408DD8FCC51906ECA98EBF94A037886BDADE7ECD09FD92B839491DF3809C9454F5286D1D3370AC31A34593D569E9A042A3B41FD331DFFB7E18599CE1E60992A076D50238C5B8F85757375354522F50756765744D65736820436F75676172',
            'snr': 11.5,
            'rssi': -58,
            'description': 'Advertisement packet with device role and GPS location'
        },
        {
            'name': 'Unknown Type (Public)',
            'hex': '34c81101bf143bcd7f1b',
            'snr': 13.0,
            'rssi': -56,
            'description': 'Unknown packet type on public/flood route'
        },
        {
            'name': 'Raw Custom Packet',
            'hex': 'd28c1102bf34143bcd7f',
            'snr': -11.5,
            'rssi': -116,
            'description': 'RawCustom packet with structural error'
        }
    ]
    
    for i, test in enumerate(test_packets, 1):
        print("\n" + "-"*70)
        print(f"Test {i}: {test['name']}")
        print(f"Description: {test['description']}")
        print("-"*70)
        
        hex_data = test['hex']
        snr = test['snr']
        rssi = test['rssi']
        hex_len = len(hex_data) // 2
        
        # Display packet info
        print(f"\n[DEBUG] 📡 [RX_LOG] Paquet RF reçu ({hex_len}B) - SNR:{snr}dB RSSI:{rssi}dBm Hex:{hex_data[:40]}...")
        
        try:
            packet = MeshCoreDecoder.decode(hex_data)
            
            # Get type names
            route_name = get_route_type_name(packet.route_type)
            payload_name = get_payload_type_name(packet.payload_type)
            
            # Build info string
            info_parts = []
            info_parts.append(f"Type: {payload_name}")
            info_parts.append(f"Route: {route_name}")
            
            if packet.total_bytes > 0:
                info_parts.append(f"Size: {packet.total_bytes}B")
            
            if packet.message_hash:
                info_parts.append(f"Hash: {packet.message_hash[:8]}")
            
            if packet.path_length > 0:
                info_parts.append(f"Hops: {packet.path_length}")
            
            validity = "✅" if packet.is_valid else "⚠️"
            info_parts.append(f"Status: {validity}")
            
            print(f"[DEBUG] 📦 [RX_LOG] {' | '.join(info_parts)}")
            
            # Show errors if any
            if packet.errors:
                for error in packet.errors[:2]:
                    if "is not a valid PayloadType" not in error:
                        print(f"[DEBUG]    ⚠️ {error}")
            
            # Enhanced content display
            is_public = packet.route_type in [RouteType.Flood, RouteType.TransportFlood]
            
            if packet.payload and isinstance(packet.payload, dict):
                decoded = packet.payload.get('decoded')
                if decoded:
                    # Text messages with public/direct indicator
                    if hasattr(decoded, 'text'):
                        text_preview = decoded.text[:50] if len(decoded.text) > 50 else decoded.text
                        msg_type = "📢 Public" if is_public else "📨 Direct"
                        print(f"[DEBUG] 📝 [RX_LOG] {msg_type} Message: \"{text_preview}\"")
                    
                    # Adverts with device info
                    elif hasattr(decoded, 'app_data'):
                        app_data = decoded.app_data
                        if isinstance(app_data, dict):
                            name = app_data.get('name', 'Unknown')
                            
                            advert_parts = [f"from: {name}"]
                            
                            if 'device_role' in app_data:
                                role = app_data['device_role']
                                role_name = str(role).split('.')[-1]
                                advert_parts.append(f"Role: {role_name}")
                            
                            if app_data.get('has_location'):
                                location = app_data.get('location', {})
                                if location:
                                    lat = location.get('latitude', 0)
                                    lon = location.get('longitude', 0)
                                    advert_parts.append(f"GPS: ({lat:.4f}, {lon:.4f})")
                            
                            print(f"[DEBUG] 📢 [RX_LOG] Advert {' | '.join(advert_parts)}")
                    
                    # Group messages
                    elif packet.payload_type.name in ['GroupText', 'GroupData']:
                        content_type = "Group Text" if packet.payload_type.name == 'GroupText' else "Group Data"
                        print(f"[DEBUG] 👥 [RX_LOG] {content_type} (public broadcast)")
                    
                    # Routing packets
                    elif packet.payload_type.name == 'Trace':
                        print(f"[DEBUG] 🔍 [RX_LOG] Trace packet (routing diagnostic)")
                    elif packet.payload_type.name == 'Path':
                        print(f"[DEBUG] 🛣️  [RX_LOG] Path packet (routing info)")
            
            # Show what's new
            print("\n✨ Enhanced Display Features:")
            if is_public:
                print("   • Route is PUBLIC/BROADCAST (Flood)")
            else:
                print("   • Route is DIRECT/UNICAST")
            
            if packet.payload_type.name == 'Advert':
                print("   • Device role shown (ChatNode/Repeater/RoomServer/Sensor)")
                print("   • GPS location included when available")
            
        except Exception as e:
            print(f"[DEBUG] 📊 [RX_LOG] Décodage non disponible: {str(e)[:60]}")
    
    # Summary
    print("\n\n" + "="*70)
    print("Summary of Enhanced Content Display")
    print("="*70)
    print("""
The enhanced display now shows:

1. **Message Type Context**
   - 📢 Public/Broadcast for Flood routes
   - 📨 Direct/Unicast for Direct routes

2. **Advertisement Details**
   - Device name
   - Device role (ChatNode, Repeater, RoomServer, Sensor)
   - GPS location coordinates when available

3. **Group Messages**
   - 👥 Group Text/Data indicator
   - Public broadcast context

4. **Routing Packets**
   - 🔍 Trace packets (routing diagnostics)
   - 🛣️  Path packets (routing information)

This provides better context about packet type, family, and content,
making it easier to understand network traffic patterns and behavior.
""")
    
    return 0


if __name__ == '__main__':
    try:
        sys.exit(demo_enhanced_content())
    except KeyboardInterrupt:
        print("\n\nDemo interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
