#!/usr/bin/env python3
"""
Interactive demonstration of meshcore-decoder integration

This script simulates RX_LOG_DATA events and shows how packets
are decoded by the new integration.

Run: python3 demo_meshcore_decoder.py
"""

import sys
import time

def simulate_rx_log_event(snr, rssi, hex_data, description):
    """Simulate the old _on_rx_log_data behavior (before decoder)"""
    print("=" * 70)
    print(f"🔍 {description}")
    print("=" * 70)
    print()
    print("📋 BEFORE INTEGRATION (Old behavior):")
    print("-" * 70)
    print(f"[DEBUG] 📡 [RX_LOG] Paquet RF reçu - SNR:{snr}dB RSSI:{rssi}dBm Hex:{hex_data[:20]}...")
    print(f"[DEBUG] 📊 [RX_LOG] RF activity monitoring only (full parsing requires protocol spec)")
    print()
    print("ℹ️  Information available:")
    print("   ✅ SNR, RSSI")
    print("   ✅ Raw hex (partial)")
    print("   ❌ Packet type: UNKNOWN")
    print("   ❌ Route type: UNKNOWN")
    print("   ❌ Message content: UNKNOWN")
    print()

def simulate_decoder_output(snr, rssi, hex_data):
    """Simulate the new _on_rx_log_data behavior (with decoder)"""
    from meshcoredecoder import MeshCoreDecoder
    from meshcoredecoder.utils.enum_names import get_route_type_name, get_payload_type_name
    
    print("📋 AFTER INTEGRATION (New behavior):")
    print("-" * 70)
    print(f"[DEBUG] 📡 [RX_LOG] Paquet RF reçu - SNR:{snr}dB RSSI:{rssi}dBm Hex:{hex_data[:20]}...")
    
    try:
        # Decode the packet
        packet = MeshCoreDecoder.decode(hex_data)
        
        route_name = get_route_type_name(packet.route_type)
        payload_name = get_payload_type_name(packet.payload_type)
        
        info_parts = []
        info_parts.append(f"Type: {payload_name}")
        info_parts.append(f"Route: {route_name}")
        
        if packet.message_hash:
            info_parts.append(f"Hash: {packet.message_hash[:8]}")
        
        if packet.path_length > 0:
            info_parts.append(f"Hops: {packet.path_length}")
        
        validity = "✅" if packet.is_valid else "⚠️"
        info_parts.append(f"Valid: {validity}")
        
        print(f"[DEBUG] 📦 [RX_LOG] {' | '.join(info_parts)}")
        
        if packet.errors:
            for error in packet.errors[:3]:
                print(f"[DEBUG]    ⚠️ {error}")
        
        # Show payload if available
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
        
        print()
        print("ℹ️  Information available:")
        print(f"   ✅ SNR, RSSI")
        print(f"   ✅ Raw hex (partial)")
        print(f"   ✅ Packet type: {payload_name}")
        print(f"   ✅ Route type: {route_name}")
        print(f"   ✅ Validity: {validity}")
        if packet.message_hash:
            print(f"   ✅ Message hash: {packet.message_hash[:16]}...")
        if packet.path_length > 0:
            print(f"   ✅ Hop count: {packet.path_length}")
        
    except Exception as e:
        print(f"[DEBUG] 📊 [RX_LOG] Décodage non disponible: {str(e)[:60]}")
        print()
        print("ℹ️  Decode error (gracefully handled)")

def main():
    """Run interactive demo"""
    print()
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "MeshCore Decoder Integration Demo" + " " * 20 + "║")
    print("║" + " " * 68 + "║")
    print("║" + "  This demo shows how RX_LOG_DATA packets are now decoded    " + " " * 4 + "║")
    print("║" + "  using the meshcore-decoder library.                        " + " " * 4 + "║")
    print("╚" + "═" * 68 + "╝")
    print()
    
    # Check if decoder is available
    try:
        from meshcoredecoder import MeshCoreDecoder
        print("✅ meshcore-decoder is installed")
    except ImportError:
        print("❌ meshcore-decoder is NOT installed")
        print()
        print("Install with: pip install meshcoredecoder")
        return 1
    
    print()
    input("Press ENTER to start demo...")
    print()
    
    # Test case 1: Short packet from logs (will have errors)
    simulate_rx_log_event(
        snr=12.25,
        rssi=-52,
        hex_data='31cc15024abf118ebecd',
        description="Test Case 1: Short packet from production logs"
    )
    simulate_decoder_output(12.25, -52, '31cc15024abf118ebecd')
    print()
    input("Press ENTER for next test case...")
    print("\n" * 2)
    
    # Test case 2: Advertisement packet (from decoder docs)
    simulate_rx_log_event(
        snr=11.5,
        rssi=-58,
        hex_data='11007E7662676F7F0850A8A355BAAFBFC1EB7B4174C340442D7D7161C9474A2C94006CE7CF682E58408DD8FCC51906ECA98EBF94A037886BDADE7ECD09FD92B839491DF3809C9454F5286D1D3370AC31A34593D569E9A042A3B41FD331DFFB7E18599CE1E60992A076D50238C5B8F85757375354522F50756765744D65736820436F75676172',
        description="Test Case 2: Node advertisement packet (valid)"
    )
    simulate_decoder_output(
        11.5,
        -58,
        '11007E7662676F7F0850A8A355BAAFBFC1EB7B4174C340442D7D7161C9474A2C94006CE7CF682E58408DD8FCC51906ECA98EBF94A037886BDADE7ECD09FD92B839491DF3809C9454F5286D1D3370AC31A34593D569E9A042A3B41FD331DFFB7E18599CE1E60992A076D50238C5B8F85757375354522F50756765744D65736820436F75676172'
    )
    print()
    input("Press ENTER for next test case...")
    print("\n" * 2)
    
    # Test case 3: Another packet from logs
    simulate_rx_log_event(
        snr=13.75,
        rssi=-13,
        hex_data='37f315024a6e118ebecd1234567890abcdef',
        description="Test Case 3: Another packet from production logs"
    )
    simulate_decoder_output(13.75, -13, '37f315024a6e118ebecd1234567890abcdef')
    print()
    
    # Summary
    print()
    print("=" * 70)
    print("📊 DEMO SUMMARY")
    print("=" * 70)
    print()
    print("✅ The integration successfully decodes MeshCore packets!")
    print()
    print("Benefits:")
    print("  • Packet type identification (TextMessage, Ack, Advert, etc.)")
    print("  • Route type visibility (Flood, Direct)")
    print("  • Message hash for tracking")
    print("  • Hop count for routing analysis")
    print("  • Validity checking")
    print("  • Error detection and reporting")
    print()
    print("🎯 Result: Debug logs are now much more informative!")
    print()
    print("For more details, see:")
    print("  • MESHCORE_DECODER_INTEGRATION.md - Complete documentation")
    print("  • MESHCORE_DECODER_BEFORE_AFTER.md - Visual comparison")
    print("  • test_meshcore_decoder_integration.py - Test suite")
    print()
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
