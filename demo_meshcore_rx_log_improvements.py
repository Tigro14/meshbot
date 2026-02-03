#!/usr/bin/env python3
"""
Standalone demo for MeshCore RX_LOG improvements
Demonstrates enhanced packet decoding display without needing full bot setup
"""

import sys

def demo_improved_display():
    """Demonstrate the improved RX_LOG display"""
    print("\n" + "="*70)
    print("MeshCore RX_LOG Improvements Demo")
    print("="*70 + "\n")
    
    # Check if meshcoredecoder is available
    try:
        from meshcoredecoder import MeshCoreDecoder
        from meshcoredecoder.utils.enum_names import get_route_type_name, get_payload_type_name
        print("✅ meshcoredecoder is available\n")
    except ImportError:
        print("❌ meshcoredecoder not installed")
        print("Install with: pip install meshcoredecoder")
        return 1
    
    # Test packets from the problem statement
    test_packets = [
        {
            'name': 'Packet 1: Unknown Type 13',
            'hex': '34c81101bf143bcd7f1b',
            'snr': 13.0,
            'rssi': -56
        },
        {
            'name': 'Packet 2: Too Short Error',
            'hex': 'd28c1102bf34143bcd7f',
            'snr': -11.5,
            'rssi': -116
        },
        {
            'name': 'Packet 3: Longer Packet',
            'hex': '11007E7662676F7F0850A8A355BAAFBFC1EB7B4174C340442D7D7161C9474A2C94006CE7CF682E58408DD8FCC51906ECA98EBF94A037886BDADE7ECD09FD92B839491DF3809C9454F5286D1D3370AC31A34593D569E9A042A3B41FD331DFFB7E18599CE1E60992A076D50238C5B8F85757375354522F50756765744D65736820436F75676172',
            'snr': 11.5,
            'rssi': -58
        }
    ]
    
    for test in test_packets:
        print("\n" + "-"*70)
        print(f"Test: {test['name']}")
        print("-"*70)
        
        hex_data = test['hex']
        snr = test['snr']
        rssi = test['rssi']
        
        # Calculate packet size
        hex_len = len(hex_data) // 2
        
        # BEFORE (Old display - only 20 chars of hex)
        print("\n📋 BEFORE (Old Display):")
        print(f"[DEBUG] 📡 [RX_LOG] Paquet RF reçu - SNR:{snr}dB RSSI:{rssi}dBm Hex:{hex_data[:20]}...")
        
        # AFTER (New display with improvements)
        print("\n📋 AFTER (Improved Display):")
        
        # First line: Now includes packet size and shows 40 chars of hex
        print(f"[DEBUG] 📡 [RX_LOG] Paquet RF reçu ({hex_len}B) - SNR:{snr}dB RSSI:{rssi}dBm Hex:{hex_data[:40]}...")
        
        # Decode the packet
        try:
            packet = MeshCoreDecoder.decode(hex_data)
            
            # Get human-readable names
            route_name = get_route_type_name(packet.route_type)
            payload_name = get_payload_type_name(packet.payload_type)
            
            # Check for unknown payload type errors
            unknown_type_error = None
            if packet.errors:
                for error in packet.errors:
                    if "is not a valid PayloadType" in error:
                        import re
                        match = re.search(r'(\d+) is not a valid PayloadType', error)
                        if match:
                            unknown_type_error = match.group(1)
                        break
            
            # Build detailed info string
            info_parts = []
            
            # Show unknown types with their numeric ID
            if unknown_type_error:
                info_parts.append(f"Type: Unknown({unknown_type_error})")
            else:
                info_parts.append(f"Type: {payload_name}")
            
            info_parts.append(f"Route: {route_name}")
            
            # NEW: Add packet size
            if packet.total_bytes > 0:
                info_parts.append(f"Size: {packet.total_bytes}B")
            
            # NEW: Add payload version if not default
            if hasattr(packet, 'payload_version') and packet.payload_version:
                version_str = str(packet.payload_version).replace('PayloadVersion.', '')
                if version_str != 'Version1':
                    info_parts.append(f"Ver: {version_str}")
            
            # Add message hash if available
            if packet.message_hash:
                info_parts.append(f"Hash: {packet.message_hash[:8]}")
            
            # Add path info if available
            if packet.path_length > 0:
                info_parts.append(f"Hops: {packet.path_length}")
            
            # NEW: Add transport codes if available
            if hasattr(packet, 'transport_codes') and packet.transport_codes:
                info_parts.append(f"Transport: {packet.transport_codes}")
            
            # Check if packet is valid
            if unknown_type_error:
                validity = "ℹ️"  # Info icon for unknown types
            else:
                validity = "✅" if packet.is_valid else "⚠️"
            info_parts.append(f"Status: {validity}")
            
            # Display decoded packet information
            print(f"[DEBUG] 📦 [RX_LOG] {' | '.join(info_parts)}")
            
            # NEW: Categorize and display errors
            if packet.errors:
                structural_errors = []
                content_errors = []
                unknown_type_errors = []
                
                for error in packet.errors:
                    if "is not a valid PayloadType" in error:
                        unknown_type_errors.append(error)
                    elif "too short" in error.lower() or "truncated" in error.lower():
                        structural_errors.append(error)
                    else:
                        content_errors.append(error)
                
                # Display structural errors first (most critical)
                for error in structural_errors[:2]:
                    print(f"[DEBUG]    ⚠️ {error}")
                
                # Display content errors
                for error in content_errors[:2]:
                    print(f"[DEBUG]    ⚠️ {error}")
            
            # Show payload if decoded
            if packet.payload and isinstance(packet.payload, dict):
                decoded_payload = packet.payload.get('decoded')
                if decoded_payload:
                    if hasattr(decoded_payload, 'text'):
                        text_preview = decoded_payload.text[:50] if len(decoded_payload.text) > 50 else decoded_payload.text
                        print(f"[DEBUG] 📝 [RX_LOG] Message: \"{text_preview}\"")
                    elif hasattr(decoded_payload, 'app_data'):
                        app_data = decoded_payload.app_data
                        if isinstance(app_data, dict):
                            name = app_data.get('name', 'Unknown')
                            print(f"[DEBUG] 📢 [RX_LOG] Advert from: {name}")
        
        except Exception as e:
            print(f"[DEBUG] 📊 [RX_LOG] Décodage non disponible: {str(e)[:60]}")
        
        print("\n✅ Improvements:")
        print("   • Packet size shown in first line (10B, 78B, etc.)")
        print("   • More hex data visible (40 chars vs 20)")
        print("   • Size field in decoded info")
        print("   • Better error categorization (structural vs content)")
        print("   • Transport codes when available")
        print("   • Payload version info")
    
    print("\n" + "="*70)
    print("Summary of Improvements")
    print("="*70)
    print("""
The enhanced RX_LOG display now provides:

1. **Packet Size**: Shows byte count immediately in first line
   Example: "Paquet RF reçu (10B)" instead of just "Paquet RF reçu"

2. **More Hex Data**: Shows 40 characters instead of 20
   Better visibility for debugging packet structure

3. **Size Field**: Added "Size: XB" in decoded info line
   Quick reference without calculating from hex

4. **Error Categorization**: Separates structural from content errors
   - Structural errors (truncated, too short): ⚠️
   - Content errors: ⚠️
   - Unknown types: ℹ️ (info, not warning)

5. **Transport Codes**: Shows transport layer info when available
   Useful for debugging routing issues

6. **Payload Version**: Shows protocol version if not default
   Helps identify firmware version mismatches

These improvements make debugging MeshCore traffic much easier!
""")
    
    return 0


if __name__ == '__main__':
    try:
        sys.exit(demo_improved_display())
    except KeyboardInterrupt:
        print("\n\nDemo interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
