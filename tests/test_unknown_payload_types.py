#!/usr/bin/env python3
"""
Test for improved handling of unknown payload types in RX_LOG decoder

This test verifies that packets with undefined payload types (like 12 and 14)
are handled gracefully without noisy error messages.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys

def test_unknown_payload_type_handling():
    """Test that unknown payload types are displayed properly"""
    print("=" * 70)
    print("TEST: Unknown Payload Type Handling")
    print("=" * 70)
    
    from meshcoredecoder import MeshCoreDecoder
    from meshcoredecoder.utils.enum_names import get_route_type_name, get_payload_type_name
    import re
    
    # Test packets with unknown payload types (12 and 14 from production logs)
    test_cases = [
        {
            'name': 'Type 12 (from production)',
            'hex': '30d31502e1bf11f52547',
            'expected_type': '12'
        },
        {
            'name': 'Type 14 (from production)',
            'hex': '38f31503e1bf6e11f525',
            'expected_type': '14'
        },
    ]
    
    passed = 0
    failed = 0
    
    for test_case in test_cases:
        print(f"\n📦 Testing: {test_case['name']}")
        print(f"   Hex: {test_case['hex']}")
        
        try:
            # Decode packet
            packet = MeshCoreDecoder.decode(test_case['hex'])
            
            # Check for unknown payload type error
            unknown_type_error = None
            if packet.errors:
                for error in packet.errors:
                    if "is not a valid PayloadType" in error:
                        match = re.search(r'(\d+) is not a valid PayloadType', error)
                        if match:
                            unknown_type_error = match.group(1)
                        break
            
            # Verify we detected the unknown type
            if unknown_type_error:
                if unknown_type_error == test_case['expected_type']:
                    print(f"   ✅ Correctly identified as Unknown({unknown_type_error})")
                    
                    # Verify other errors are filtered
                    other_errors = [e for e in packet.errors if "is not a valid PayloadType" not in e]
                    if len(other_errors) == 0:
                        print(f"   ✅ No other errors logged")
                    else:
                        print(f"   ℹ️  Other errors present: {len(other_errors)}")
                    
                    # Show what would be displayed
                    route_name = get_route_type_name(packet.route_type)
                    payload_name = f"Unknown({unknown_type_error})"
                    validity = "ℹ️"  # Info icon for unknown types
                    
                    print(f"   📊 Display: Type: {payload_name} | Route: {route_name} | Status: {validity}")
                    passed += 1
                else:
                    print(f"   ❌ Expected type {test_case['expected_type']}, got {unknown_type_error}")
                    failed += 1
            else:
                print(f"   ❌ No unknown type error detected")
                print(f"   Payload type: {get_payload_type_name(packet.payload_type)}")
                failed += 1
                
        except Exception as e:
            print(f"   ❌ Exception: {e}")
            failed += 1
    
    # Summary
    print("\n" + "=" * 70)
    print(f"SUMMARY: {passed} passed, {failed} failed")
    print("=" * 70)
    
    if failed == 0:
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1

def test_known_payload_types_unchanged():
    """Verify known payload types still work normally"""
    print("\n" + "=" * 70)
    print("TEST: Known Payload Types Unchanged")
    print("=" * 70)
    
    from meshcoredecoder import MeshCoreDecoder
    from meshcoredecoder.utils.enum_names import get_payload_type_name
    
    # Test with a known good packet (Advert from earlier tests)
    hex_data = '11007E7662676F7F0850A8A355BAAFBFC1EB7B4174C340442D7D7161C9474A2C94006CE7CF682E58408DD8FCC51906ECA98EBF94A037886BDADE7ECD09FD92B839491DF3809C9454F5286D1D3370AC31A34593D569E9A042A3B41FD331DFFB7E18599CE1E60992A076D50238C5B8F85757375354522F50756765744D65736820436F75676172'
    
    try:
        packet = MeshCoreDecoder.decode(hex_data)
        payload_name = get_payload_type_name(packet.payload_type)
        
        print(f"📦 Known packet decoded")
        print(f"   Type: {payload_name}")
        print(f"   Valid: {'✅' if packet.is_valid else '⚠️'}")
        print(f"   Errors: {len(packet.errors)}")
        
        if packet.is_valid and payload_name == "Advert":
            print("   ✅ Known type handling unchanged")
            return 0
        else:
            print("   ❌ Known type handling broken")
            return 1
            
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return 1

def main():
    """Run all tests"""
    print("\n🧪 Testing improved unknown payload type handling\n")
    
    results = []
    results.append(test_unknown_payload_type_handling())
    results.append(test_known_payload_types_unchanged())
    
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    
    if all(r == 0 for r in results):
        print("✅ All test suites passed!")
        return 0
    else:
        print("❌ Some test suites failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
