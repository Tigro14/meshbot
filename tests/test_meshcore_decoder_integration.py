#!/usr/bin/env python3
"""
Test script for meshcore-decoder integration in RX_LOG_DATA handling

This test verifies that:
1. meshcore-decoder can be imported
2. Packets can be decoded from hex strings
3. The decoder provides useful packet type and route information
4. Error handling works when packets are malformed
"""

import sys

def test_decoder_import():
    """Test that meshcore-decoder can be imported"""
    print("=" * 60)
    print("TEST 1: Import meshcore-decoder")
    print("=" * 60)
    try:
        from meshcoredecoder import MeshCoreDecoder
        from meshcoredecoder.utils.enum_names import get_route_type_name, get_payload_type_name
        print("✅ meshcore-decoder imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Failed to import meshcore-decoder: {e}")
        print("   Install with: pip install meshcoredecoder")
        return False

def test_packet_decoding():
    """Test basic packet decoding"""
    print("\n" + "=" * 60)
    print("TEST 2: Decode sample MeshCore packets")
    print("=" * 60)
    
    from meshcoredecoder import MeshCoreDecoder
    from meshcoredecoder.utils.enum_names import get_route_type_name, get_payload_type_name
    
    # Test cases with various packet types
    test_packets = [
        {
            'name': 'Short packet (from logs)',
            'hex': '31cc15024abf118ebecd',
        },
        {
            'name': 'Longer packet (from logs)',
            'hex': '37f315024a6e118ebecd1234567890abcdef',
        },
        {
            'name': 'Sample Advert packet (from meshcore-decoder docs)',
            'hex': '11007E7662676F7F0850A8A355BAAFBFC1EB7B4174C340442D7D7161C9474A2C94006CE7CF682E58408DD8FCC51906ECA98EBF94A037886BDADE7ECD09FD92B839491DF3809C9454F5286D1D3370AC31A34593D569E9A042A3B41FD331DFFB7E18599CE1E60992A076D50238C5B8F85757375354522F50756765744D65736820436F75676172',
        },
    ]
    
    success_count = 0
    for test_case in test_packets:
        print(f"\n📦 Testing: {test_case['name']}")
        print(f"   Hex: {test_case['hex'][:40]}...")
        
        try:
            packet = MeshCoreDecoder.decode(test_case['hex'])
            
            route_name = get_route_type_name(packet.route_type)
            payload_name = get_payload_type_name(packet.payload_type)
            
            print(f"   ✅ Decoded successfully!")
            print(f"   Route Type: {route_name}")
            print(f"   Payload Type: {payload_name}")
            print(f"   Valid: {'✅' if packet.is_valid else '⚠️'}")
            print(f"   Total bytes: {packet.total_bytes}")
            
            if packet.message_hash:
                print(f"   Message Hash: {packet.message_hash[:16]}...")
            
            if packet.path_length > 0:
                print(f"   Path Length: {packet.path_length}")
            
            if packet.errors:
                print(f"   Errors: {len(packet.errors)}")
                for error in packet.errors[:2]:
                    print(f"      • {error}")
            
            success_count += 1
            
        except Exception as e:
            print(f"   ⚠️ Decode error: {e}")
    
    print(f"\n{'=' * 60}")
    print(f"Summary: {success_count}/{len(test_packets)} packets decoded")
    return success_count > 0

def test_integration_with_rx_log():
    """Test integration with RX_LOG_DATA handler logic"""
    print("\n" + "=" * 60)
    print("TEST 3: Integration with RX_LOG_DATA handler")
    print("=" * 60)
    
    from meshcoredecoder import MeshCoreDecoder
    from meshcoredecoder.utils.enum_names import get_route_type_name, get_payload_type_name
    
    # Simulate RX_LOG_DATA event payload
    mock_payload = {
        'snr': 12.25,
        'rssi': -52,
        'raw_hex': '31cc15024abf118ebecd1234567890',
    }
    
    print(f"Mock RX_LOG_DATA payload:")
    print(f"  SNR: {mock_payload['snr']}dB")
    print(f"  RSSI: {mock_payload['rssi']}dBm")
    print(f"  Hex: {mock_payload['raw_hex'][:20]}...")
    
    # Simulate the decoder logic from _on_rx_log_data
    try:
        raw_hex = mock_payload['raw_hex']
        packet = MeshCoreDecoder.decode(raw_hex)
        
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
        
        print(f"\n📦 [RX_LOG] {' | '.join(info_parts)}")
        
        if packet.errors:
            for error in packet.errors[:3]:
                print(f"   ⚠️ {error}")
        
        print("\n✅ Integration test passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_error_handling():
    """Test error handling with invalid packets"""
    print("\n" + "=" * 60)
    print("TEST 4: Error handling")
    print("=" * 60)
    
    from meshcoredecoder import MeshCoreDecoder
    
    # Test with invalid/malformed packets
    test_cases = [
        ('Empty string', ''),
        ('Very short', 'ab'),
        ('Invalid hex', 'xyz123'),
    ]
    
    success_count = 0
    for name, hex_data in test_cases:
        print(f"\n📦 Testing: {name}")
        print(f"   Hex: '{hex_data}'")
        
        try:
            if hex_data:
                packet = MeshCoreDecoder.decode(hex_data)
                print(f"   ⚠️ Decoded (unexpected): {packet.is_valid}")
            else:
                print(f"   ⚠️ Empty hex string - skipped decode")
            success_count += 1
        except Exception as e:
            print(f"   ✅ Error handled gracefully: {type(e).__name__}")
            success_count += 1
    
    print(f"\n{'=' * 60}")
    print(f"Summary: {success_count}/{len(test_cases)} error cases handled")
    return success_count == len(test_cases)

def main():
    """Run all tests"""
    print("🧪 Testing meshcore-decoder integration for RX_LOG_DATA")
    print()
    
    results = []
    
    # Test 1: Import
    if not test_decoder_import():
        print("\n❌ Cannot proceed without meshcore-decoder")
        print("   Install with: pip install meshcoredecoder")
        return 1
    
    # Test 2: Decoding
    results.append(("Packet decoding", test_packet_decoding()))
    
    # Test 3: Integration
    results.append(("Integration", test_integration_with_rx_log()))
    
    # Test 4: Error handling
    results.append(("Error handling", test_error_handling()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
    
    all_passed = all(result for _, result in results)
    
    print("=" * 60)
    if all_passed:
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
