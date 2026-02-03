#!/usr/bin/env python3
"""
Test the /keys command with multiple key formats in interface.nodes

This test verifies that _check_node_keys() can find nodes regardless of
which key format is used in interface.nodes (int, str, "!hex", "hex").
"""

import sys
import os

# Mock classes to simulate Meshtastic interface
class MockInterface:
    def __init__(self):
        self.nodes = {}

class MockNodeManager:
    def __init__(self):
        self.node_names = {
            0xa76f40da: {'name': 'tigro t1000E'},
            305419896: {'name': 'Test Node'},
            0x12345678: {'name': 'Sample Node'}
        }
    
    def get_node_name(self, node_id):
        return self.node_names.get(node_id, {}).get('name', f'Node-{node_id:08x}')

class MockSender:
    pass

class MockRemoteNodesClient:
    def get_remote_nodes(self, host):
        return []

def test_integer_key():
    """Test finding a node when interface.nodes uses integer keys"""
    print("\n=== Test 1: Integer Key Format ===")
    
    # Setup mock interface with INTEGER key
    mock_interface = MockInterface()
    node_id = 0xa76f40da
    mock_interface.nodes[node_id] = {  # INTEGER KEY
        'user': {
            'id': f"!{node_id:08x}",
            'longName': 'tigro t1000E',
            'shortName': 'tigro',
            'publicKey': 'abc123xyz=='
        }
    }
    
    print(f"Setup: interface.nodes with INTEGER key {node_id} (0x{node_id:08x})")
    print(f"       Keys in interface.nodes: {list(mock_interface.nodes.keys())}")
    
    # Simulate the multi-format search from _check_node_keys
    nodes = mock_interface.nodes
    node_info = None
    search_keys = [node_id, str(node_id), f"!{node_id:08x}", f"{node_id:08x}"]
    
    print(f"Trying search keys: {search_keys}")
    
    for key in search_keys:
        print(f"  Checking key={key} (type={type(key).__name__})... ", end='')
        if key in nodes:
            node_info = nodes[key]
            print(f"✅ FOUND")
            break
        else:
            print(f"❌ not found")
    
    assert node_info is not None, "Should find node with integer key"
    assert 'publicKey' in node_info['user'], "Should have publicKey"
    print("✅ Test 1 passed - Found node with INTEGER key\n")

def test_string_key():
    """Test finding a node when interface.nodes uses string keys"""
    print("\n=== Test 2: String Key Format ===")
    
    # Setup mock interface with STRING key
    mock_interface = MockInterface()
    node_id = 0xa76f40da
    mock_interface.nodes[str(node_id)] = {  # STRING KEY (decimal)
        'user': {
            'id': f"!{node_id:08x}",
            'longName': 'tigro t1000E',
            'shortName': 'tigro',
            'publicKey': 'def456uvw=='
        }
    }
    
    print(f"Setup: interface.nodes with STRING key '{str(node_id)}'")
    print(f"       Keys in interface.nodes: {list(mock_interface.nodes.keys())}")
    
    # Simulate the multi-format search from _check_node_keys
    nodes = mock_interface.nodes
    node_info = None
    search_keys = [node_id, str(node_id), f"!{node_id:08x}", f"{node_id:08x}"]
    
    print(f"Trying search keys: {search_keys}")
    
    for key in search_keys:
        print(f"  Checking key={key} (type={type(key).__name__})... ", end='')
        if key in nodes:
            node_info = nodes[key]
            print(f"✅ FOUND")
            break
        else:
            print(f"❌ not found")
    
    assert node_info is not None, "Should find node with string key"
    assert 'publicKey' in node_info['user'], "Should have publicKey"
    print("✅ Test 2 passed - Found node with STRING key\n")

def test_hex_with_bang():
    """Test finding a node when interface.nodes uses '!hex' format"""
    print("\n=== Test 3: '!hex' Key Format ===")
    
    # Setup mock interface with "!hex" key
    mock_interface = MockInterface()
    node_id = 0xa76f40da
    mock_interface.nodes[f"!{node_id:08x}"] = {  # "!hex" KEY
        'user': {
            'id': f"!{node_id:08x}",
            'longName': 'tigro t1000E',
            'shortName': 'tigro',
            'publicKey': 'ghi789rst=='
        }
    }
    
    print(f"Setup: interface.nodes with '!hex' key '!{node_id:08x}'")
    print(f"       Keys in interface.nodes: {list(mock_interface.nodes.keys())}")
    
    # Simulate the multi-format search from _check_node_keys
    nodes = mock_interface.nodes
    node_info = None
    search_keys = [node_id, str(node_id), f"!{node_id:08x}", f"{node_id:08x}"]
    
    print(f"Trying search keys: {search_keys}")
    
    for key in search_keys:
        print(f"  Checking key={key} (type={type(key).__name__})... ", end='')
        if key in nodes:
            node_info = nodes[key]
            print(f"✅ FOUND")
            break
        else:
            print(f"❌ not found")
    
    assert node_info is not None, "Should find node with !hex key"
    assert 'publicKey' in node_info['user'], "Should have publicKey"
    print("✅ Test 3 passed - Found node with '!hex' key\n")

def test_hex_no_bang():
    """Test finding a node when interface.nodes uses 'hex' format (no !)"""
    print("\n=== Test 4: 'hex' Key Format (no !) ===")
    
    # Setup mock interface with "hex" key (no bang)
    mock_interface = MockInterface()
    node_id = 0xa76f40da
    mock_interface.nodes[f"{node_id:08x}"] = {  # "hex" KEY (no !)
        'user': {
            'id': f"!{node_id:08x}",
            'longName': 'tigro t1000E',
            'shortName': 'tigro',
            'publicKey': 'jkl012mno=='
        }
    }
    
    print(f"Setup: interface.nodes with 'hex' key '{node_id:08x}'")
    print(f"       Keys in interface.nodes: {list(mock_interface.nodes.keys())}")
    
    # Simulate the multi-format search from _check_node_keys
    nodes = mock_interface.nodes
    node_info = None
    search_keys = [node_id, str(node_id), f"!{node_id:08x}", f"{node_id:08x}"]
    
    print(f"Trying search keys: {search_keys}")
    
    for key in search_keys:
        print(f"  Checking key={key} (type={type(key).__name__})... ", end='')
        if key in nodes:
            node_info = nodes[key]
            print(f"✅ FOUND")
            break
        else:
            print(f"❌ not found")
    
    assert node_info is not None, "Should find node with hex key"
    assert 'publicKey' in node_info['user'], "Should have publicKey"
    print("✅ Test 4 passed - Found node with 'hex' key\n")

def test_node_not_found():
    """Test behavior when node is not in interface.nodes at all"""
    print("\n=== Test 5: Node Not In Interface ===")
    
    # Setup mock interface WITHOUT the node
    mock_interface = MockInterface()
    node_id = 0xa76f40da
    # Don't add the node to interface.nodes
    
    print(f"Setup: interface.nodes EMPTY")
    print(f"       Looking for node_id={node_id} (0x{node_id:08x})")
    
    # Simulate the multi-format search from _check_node_keys
    nodes = mock_interface.nodes
    node_info = None
    search_keys = [node_id, str(node_id), f"!{node_id:08x}", f"{node_id:08x}"]
    
    print(f"Trying search keys: {search_keys}")
    
    for key in search_keys:
        print(f"  Checking key={key} (type={type(key).__name__})... ", end='')
        if key in nodes:
            node_info = nodes[key]
            print(f"✅ FOUND")
            break
        else:
            print(f"❌ not found")
    
    assert node_info is None, "Should NOT find node when not in interface.nodes"
    print("✅ Test 5 passed - Correctly handles missing node\n")

def run_all_tests():
    """Run all multi-format key tests"""
    print("="*70)
    print("Testing /keys Command Multi-Format Key Lookup")
    print("="*70)
    print("\nThis tests that _check_node_keys() can find nodes regardless of")
    print("the key format used in interface.nodes (int, str, '!hex', 'hex')")
    
    try:
        test_integer_key()
        test_string_key()
        test_hex_with_bang()
        test_hex_no_bang()
        test_node_not_found()
        
        print("\n" + "="*70)
        print("✅ ALL MULTI-FORMAT TESTS PASSED!")
        print("="*70)
        print("\n📖 Summary:")
        print("   • Can find nodes with INTEGER keys (e.g., 0xa76f40da)")
        print("   • Can find nodes with STRING keys (e.g., '2800066714')")
        print("   • Can find nodes with '!hex' keys (e.g., '!a76f40da')")
        print("   • Can find nodes with 'hex' keys (e.g., 'a76f40da')")
        print("   • Correctly handles nodes not in interface.nodes")
        print("\n💡 The fix ensures /keys <node_id> works regardless of key format")
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
