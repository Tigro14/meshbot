#!/usr/bin/env python3
"""
Test script to verify that gateway_id is properly resolved to longname
in MQTT debug logs.

This test verifies the fix for the issue where:
  BEFORE: "👥 [MQTT] Paquet POSITION de a2ea17b8 (🚀 Normandy SR-2) via !a2ea17b8"
  AFTER:  "👥 [MQTT] Paquet POSITION de a2ea17b8 (🚀 Normandy SR-2) via 🚀 Normandy SR-2"
"""

import sys
from unittest.mock import Mock, MagicMock

# Mock config module
sys.modules['config'] = MagicMock()
sys.modules['config'].DEBUG_MODE = True

# Mock meshtastic imports
sys.modules['meshtastic'] = MagicMock()
sys.modules['meshtastic.protobuf'] = MagicMock()
sys.modules['meshtastic.protobuf.mesh_pb2'] = MagicMock()
sys.modules['meshtastic.protobuf.portnums_pb2'] = MagicMock()
sys.modules['meshtastic.protobuf.mqtt_pb2'] = MagicMock()

# Mock paho.mqtt
sys.modules['paho'] = MagicMock()
sys.modules['paho.mqtt'] = MagicMock()
sys.modules['paho.mqtt.client'] = MagicMock()

# Mock cryptography
sys.modules['cryptography'] = MagicMock()
sys.modules['cryptography.hazmat'] = MagicMock()
sys.modules['cryptography.hazmat.primitives'] = MagicMock()
sys.modules['cryptography.hazmat.primitives.ciphers'] = MagicMock()
sys.modules['cryptography.hazmat.backends'] = MagicMock()

# Import the module
from mqtt_neighbor_collector import MQTTNeighborCollector


def test_resolve_gateway_name_with_hex_prefix():
    """Test gateway name resolution with '!' prefix"""
    print("\n=== Test 1: Gateway ID with '!' prefix ===")
    
    # Create mock node_manager
    mock_node_manager = Mock()
    mock_node_manager.get_node_name = Mock(return_value="🚀 Normandy SR-2")
    
    # Create mock persistence
    mock_persistence = Mock()
    
    # Create collector
    collector = MQTTNeighborCollector(
        mqtt_server="test.example.com",
        mqtt_port=1883,
        persistence=mock_persistence,
        node_manager=mock_node_manager
    )
    
    # Test resolution with "!a2ea17b8" format
    gateway_id = "!a2ea17b8"
    result = collector._resolve_gateway_name(gateway_id)
    
    # Verify get_node_name was called with integer
    expected_int = int("a2ea17b8", 16)  # 2732177336
    mock_node_manager.get_node_name.assert_called_once_with(expected_int)
    
    # Verify result
    if result == "🚀 Normandy SR-2":
        print(f"✅ PASS: Gateway ID '{gateway_id}' resolved to '{result}'")
        print(f"   Called get_node_name({expected_int}) = {hex(expected_int)}")
    else:
        print(f"❌ FAIL: Expected '🚀 Normandy SR-2', got '{result}'")
    
    print()


def test_resolve_gateway_name_without_prefix():
    """Test gateway name resolution without '!' prefix"""
    print("=== Test 2: Gateway ID without '!' prefix ===")
    
    # Create mock node_manager
    mock_node_manager = Mock()
    mock_node_manager.get_node_name = Mock(return_value="TestGateway")
    
    # Create mock persistence
    mock_persistence = Mock()
    
    # Create collector
    collector = MQTTNeighborCollector(
        mqtt_server="test.example.com",
        mqtt_port=1883,
        persistence=mock_persistence,
        node_manager=mock_node_manager
    )
    
    # Test resolution with "12345678" format (no prefix)
    gateway_id = "12345678"
    result = collector._resolve_gateway_name(gateway_id)
    
    # Verify get_node_name was called with integer
    expected_int = int("12345678", 16)  # 305419896
    mock_node_manager.get_node_name.assert_called_once_with(expected_int)
    
    # Verify result
    if result == "TestGateway":
        print(f"✅ PASS: Gateway ID '{gateway_id}' resolved to '{result}'")
        print(f"   Called get_node_name({expected_int}) = {hex(expected_int)}")
    else:
        print(f"❌ FAIL: Expected 'TestGateway', got '{result}'")
    
    print()


def test_resolve_gateway_name_unknown_node():
    """Test gateway name resolution when node is unknown"""
    print("=== Test 3: Unknown node (not in database) ===")
    
    # Create mock node_manager that returns "Unknown"
    mock_node_manager = Mock()
    mock_node_manager.get_node_name = Mock(return_value="Unknown")
    
    # Create mock persistence
    mock_persistence = Mock()
    
    # Create collector
    collector = MQTTNeighborCollector(
        mqtt_server="test.example.com",
        mqtt_port=1883,
        persistence=mock_persistence,
        node_manager=mock_node_manager
    )
    
    # Test resolution
    gateway_id = "!99999999"
    result = collector._resolve_gateway_name(gateway_id)
    
    # When node is unknown, should return the original ID string
    if result == "!99999999":
        print(f"✅ PASS: Unknown node returns original ID '{result}'")
    else:
        print(f"❌ FAIL: Expected '!99999999', got '{result}'")
    
    print()


def test_resolve_gateway_name_node_format():
    """Test gateway name resolution when node_manager returns 'Node-xxxxxxxx' format"""
    print("=== Test 4: Node-xxxxxxxx format (not found, default name) ===")
    
    # Create mock node_manager that returns default "Node-xxxxxxxx" format
    mock_node_manager = Mock()
    mock_node_manager.get_node_name = Mock(return_value="Node-a2ea17b8")
    
    # Create mock persistence
    mock_persistence = Mock()
    
    # Create collector
    collector = MQTTNeighborCollector(
        mqtt_server="test.example.com",
        mqtt_port=1883,
        persistence=mock_persistence,
        node_manager=mock_node_manager
    )
    
    # Test resolution
    gateway_id = "!a2ea17b8"
    result = collector._resolve_gateway_name(gateway_id)
    
    # When node_manager returns "Node-xxxxxxxx", should return the original ID string
    if result == "!a2ea17b8":
        print(f"✅ PASS: Node-xxxxxxxx format returns original ID '{result}'")
    else:
        print(f"❌ FAIL: Expected '!a2ea17b8', got '{result}'")
    
    print()


def test_resolve_gateway_name_empty():
    """Test gateway name resolution with empty gateway_id"""
    print("=== Test 5: Empty gateway_id ===")
    
    # Create mock node_manager
    mock_node_manager = Mock()
    
    # Create mock persistence
    mock_persistence = Mock()
    
    # Create collector
    collector = MQTTNeighborCollector(
        mqtt_server="test.example.com",
        mqtt_port=1883,
        persistence=mock_persistence,
        node_manager=mock_node_manager
    )
    
    # Test with empty string
    result = collector._resolve_gateway_name("")
    
    if result is None:
        print("✅ PASS: Empty gateway_id returns None")
    else:
        print(f"❌ FAIL: Expected None, got '{result}'")
    
    print()


def test_resolve_gateway_name_invalid_hex():
    """Test gateway name resolution with invalid hex string"""
    print("=== Test 6: Invalid hex string ===")
    
    # Create mock node_manager
    mock_node_manager = Mock()
    
    # Create mock persistence
    mock_persistence = Mock()
    
    # Create collector
    collector = MQTTNeighborCollector(
        mqtt_server="test.example.com",
        mqtt_port=1883,
        persistence=mock_persistence,
        node_manager=mock_node_manager
    )
    
    # Test with invalid hex
    gateway_id = "!ZZZZZZZZ"
    result = collector._resolve_gateway_name(gateway_id)
    
    # Should return the original ID when conversion fails
    if result == "!ZZZZZZZZ":
        print(f"✅ PASS: Invalid hex returns original ID '{result}'")
    else:
        print(f"❌ FAIL: Expected '!ZZZZZZZZ', got '{result}'")
    
    print()


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("Testing Gateway Longname Resolution Fix")
    print("="*60)
    
    test_resolve_gateway_name_with_hex_prefix()
    test_resolve_gateway_name_without_prefix()
    test_resolve_gateway_name_unknown_node()
    test_resolve_gateway_name_node_format()
    test_resolve_gateway_name_empty()
    test_resolve_gateway_name_invalid_hex()
    
    print("="*60)
    print("Testing Complete!")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
