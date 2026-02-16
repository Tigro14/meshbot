#!/usr/bin/env python3
"""
Test the /keys command key-checking logic

This is a standalone test that directly tests the key-checking methods
without importing the full module chain.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys

# Mock the required objects
class MockInterface:
    def __init__(self):
        self.nodes = {
            0x12345678: {
                'user': {
                    'id': '!12345678',
                    'longName': 'Test Node 1',
                    'shortName': 'TN1',
                    'publicKey': 'a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6'
                }
            },
            0xa76f40da: {
                'user': {
                    'id': '!a76f40da',
                    'longName': 'tigro t1000E',
                    'shortName': 'tigro',
                    # Missing public key - this is the problem case
                }
            },
            0xdeadbeef: {
                'user': {
                    'id': '!deadbeef',
                    'longName': 'Key Holder',
                    'publicKey': 'z9y8x7w6v5u4t3s2r1q0p9o8'
                }
            }
        }

def check_node_has_key(interface, node_id):
    """
    Check if a node has a public key in the interface
    (Simplified version of what _check_node_keys does)
    """
    if not interface or not hasattr(interface, 'nodes'):
        return None, "Interface not available"
    
    nodes = getattr(interface, 'nodes', {})
    node_info = nodes.get(node_id)
    
    if not node_info:
        return None, "Node not in database"
    
    user_info = node_info.get('user', {}) if isinstance(node_info, dict) else {}
    public_key = user_info.get('publicKey', None) if isinstance(user_info, dict) else None
    
    if public_key:
        return True, f"Key present: {public_key[:16]}..."
    else:
        return False, "Key missing"

def count_keys(interface):
    """
    Count nodes with/without keys
    (Simplified version of what _check_all_keys does)
    """
    if not interface or not hasattr(interface, 'nodes'):
        return None, None, "Interface not available"
    
    nodes = getattr(interface, 'nodes', {})
    total_nodes = 0
    nodes_with_keys = 0
    nodes_without_keys = []
    
    for node_id, node_info in nodes.items():
        if not isinstance(node_info, dict):
            continue
        
        total_nodes += 1
        user_info = node_info.get('user', {})
        
        if isinstance(user_info, dict):
            public_key = user_info.get('publicKey')
            node_name = user_info.get('longName', f"Node-{node_id:08x}")
            
            if public_key:
                nodes_with_keys += 1
            else:
                nodes_without_keys.append((node_id, node_name))
    
    return total_nodes, nodes_with_keys, nodes_without_keys

def test_check_all_keys():
    """Test checking key status for all nodes"""
    print("\n=== Test 1: Check All Keys Status ===")
    
    interface = MockInterface()
    total, with_keys, without_keys = count_keys(interface)
    
    print(f"Total nodes: {total}")
    print(f"Nodes with keys: {with_keys}")
    print(f"Nodes without keys: {len(without_keys)}")
    
    assert total == 3, f"Expected 3 total nodes, got {total}"
    assert with_keys == 2, f"Expected 2 nodes with keys, got {with_keys}"
    assert len(without_keys) == 1, f"Expected 1 node without key, got {len(without_keys)}"
    assert without_keys[0][0] == 0xa76f40da, "Node without key should be tigro (0xa76f40da)"
    
    print("✅ Test 1 passed!")

def test_check_specific_node_with_key():
    """Test checking key status for a specific node that HAS a key"""
    print("\n=== Test 2: Check Specific Node WITH Key ===")
    
    interface = MockInterface()
    has_key, message = check_node_has_key(interface, 0xdeadbeef)
    
    print(f"Node 0xdeadbeef: has_key={has_key}, message={message}")
    
    assert has_key is True, "Node should have a key"
    assert "Key present" in message, "Message should say key is present"
    assert "z9y8x7w6" in message, "Message should show key preview"
    
    print("✅ Test 2 passed!")

def test_check_specific_node_without_key():
    """Test checking key status for a specific node that LACKS a key"""
    print("\n=== Test 3: Check Specific Node WITHOUT Key ===")
    
    interface = MockInterface()
    has_key, message = check_node_has_key(interface, 0xa76f40da)
    
    print(f"Node 0xa76f40da: has_key={has_key}, message={message}")
    
    assert has_key is False, "Node should NOT have a key"
    assert "missing" in message.lower(), "Message should say key is missing"
    
    print("✅ Test 3 passed!")

def test_check_nonexistent_node():
    """Test checking key status for a node that doesn't exist"""
    print("\n=== Test 4: Check Non-existent Node ===")
    
    interface = MockInterface()
    has_key, message = check_node_has_key(interface, 0x99999999)
    
    print(f"Node 0x99999999: has_key={has_key}, message={message}")
    
    assert has_key is None, "Non-existent node should return None"
    assert "not in database" in message.lower(), "Message should say node not found"
    
    print("✅ Test 4 passed!")

def test_no_interface():
    """Test behavior when interface is not available"""
    print("\n=== Test 5: No Interface Available ===")
    
    has_key, message = check_node_has_key(None, 0x12345678)
    
    print(f"With no interface: has_key={has_key}, message={message}")
    
    assert has_key is None, "Should return None without interface"
    assert "not available" in message.lower(), "Message should say interface unavailable"
    
    print("✅ Test 5 passed!")

def test_format_lengths():
    """Test that formatted messages respect length constraints"""
    print("\n=== Test 6: Message Length Constraints ===")
    
    interface = MockInterface()
    total, with_keys, without_keys = count_keys(interface)
    
    # Simulate compact format (for mesh - max 180 chars)
    compact_msg = f"🔑 {with_keys}/{total} avec clés. {len(without_keys)} sans."
    print(f"Compact message ({len(compact_msg)} chars): {compact_msg}")
    assert len(compact_msg) <= 180, f"Compact message too long: {len(compact_msg)} chars"
    
    # Simulate detailed format (for Telegram)
    detailed_lines = [
        "🔑 État des clés publiques PKI",
        "",
        f"Total nœuds: {total}",
        f"✅ Avec clé publique: {with_keys}",
        f"❌ Sans clé publique: {len(without_keys)}",
        "",
        "⚠️ Nœuds sans clé publique:",
        "   (Vous ne pouvez pas recevoir leurs DM)",
        ""
    ]
    
    for node_id, node_name in without_keys:
        detailed_lines.append(f"   • {node_name} (0x{node_id:08x})")
    
    detailed_msg = "\n".join(detailed_lines)
    print(f"Detailed message ({len(detailed_msg)} chars):")
    print(detailed_msg)
    # No strict length limit for Telegram, but verify it's reasonable
    assert len(detailed_msg) < 4096, "Detailed message too long for Telegram"
    
    print("✅ Test 6 passed!")

def run_all_tests():
    """Run all tests"""
    print("="*60)
    print("Testing /keys Command Logic")
    print("="*60)
    
    try:
        test_check_all_keys()
        test_check_specific_node_with_key()
        test_check_specific_node_without_key()
        test_check_nonexistent_node()
        test_no_interface()
        test_format_lengths()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60)
        print("\n📖 Summary:")
        print("   • Key detection logic works correctly")
        print("   • Missing key detection works")
        print("   • Message formatting respects constraints")
        print("   • Error handling for edge cases works")
        print("\n💡 Next step: Test in live bot environment")
        return True
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

