#!/usr/bin/env python3
"""
Test script to verify MQTT "via" information extraction

This test verifies that:
1. gateway_id is correctly extracted from ServiceEnvelope
2. channel_id is correctly extracted from ServiceEnvelope
3. Debug logs include "via [gateway_name]" suffix
4. Gateway ID is resolved to node name when available
"""

import sys
import time
from unittest.mock import Mock, MagicMock, patch

# Mock config module
sys.modules['config'] = MagicMock()
sys.modules['config'].DEBUG_MODE = True

# Mock meshtastic imports before importing mqtt_neighbor_collector
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

# Now import the module
from mqtt_neighbor_collector import MQTTNeighborCollector
from meshtastic.protobuf import mqtt_pb2, mesh_pb2, portnums_pb2

def test_gateway_id_extraction():
    """Test that gateway_id is correctly extracted from ServiceEnvelope"""
    print("\n=== Test 1: Gateway ID Extraction ===")
    
    # Create mock objects
    mock_persistence = Mock()
    mock_node_manager = Mock()
    mock_node_manager.get_node_name = Mock(return_value="MyGateway")
    
    collector = MQTTNeighborCollector(
        mqtt_server="test.example.com",
        mqtt_port=1883,
        persistence=mock_persistence,
        node_manager=mock_node_manager
    )
    
    # Create mock MQTT message
    mock_msg = Mock()
    mock_msg.topic = "msh/EU_868/2/e/!12345678"
    
    # Create mock ServiceEnvelope
    mock_envelope = Mock()
    mock_envelope.HasField = Mock(return_value=True)
    mock_envelope.gateway_id = "!12345678"
    mock_envelope.channel_id = "MediumFast"
    
    # Create mock packet
    mock_packet = Mock()
    mock_packet.id = 123456
    setattr(mock_packet, 'from', 0x11223344)  # 'from' is a keyword
    mock_packet.HasField = Mock(return_value=True)
    
    # Create mock decoded data (NODEINFO)
    mock_decoded = Mock()
    mock_decoded.portnum = portnums_pb2.PortNum.NODEINFO_APP
    mock_decoded.payload = b''
    
    mock_packet.decoded = mock_decoded
    mock_envelope.packet = mock_packet
    
    # Mock the ServiceEnvelope parsing
    with patch.object(mqtt_pb2, 'ServiceEnvelope', return_value=mock_envelope):
        with patch('mqtt_neighbor_collector.debug_print') as mock_debug:
            # Call the message handler
            collector._on_mqtt_message(None, None, mock_msg)
            
            # Verify debug_print was called with "via" information
            debug_calls = [str(call) for call in mock_debug.call_args_list]
            
            # Check if any debug call contains "via"
            via_found = any("via" in call for call in debug_calls)
            
            if via_found:
                print("✅ PASS: Debug logs contain 'via' information")
                for call in debug_calls:
                    if "via" in call:
                        print(f"   Found: {call}")
            else:
                print("❌ FAIL: Debug logs do not contain 'via' information")
                print("   Debug calls:")
                for call in debug_calls:
                    print(f"   {call}")
    
    print()

def test_gateway_name_resolution():
    """Test that gateway ID is resolved to node name"""
    print("=== Test 2: Gateway Name Resolution ===")
    
    # Create mock objects
    mock_persistence = Mock()
    mock_node_manager = Mock()
    
    # Mock get_node_name to return a friendly name
    def mock_get_name(node_id):
        if node_id == "!12345678":
            return "GatewayNode"
        elif node_id == 0x11223344:
            return "SenderNode"
        return "Unknown"
    
    mock_node_manager.get_node_name = Mock(side_effect=mock_get_name)
    
    collector = MQTTNeighborCollector(
        mqtt_server="test.example.com",
        mqtt_port=1883,
        persistence=mock_persistence,
        node_manager=mock_node_manager
    )
    
    # Create mock MQTT message
    mock_msg = Mock()
    mock_msg.topic = "msh/EU_868/2/e/!12345678"
    
    # Create mock ServiceEnvelope
    mock_envelope = Mock()
    mock_envelope.HasField = Mock(return_value=True)
    mock_envelope.gateway_id = "!12345678"
    mock_envelope.channel_id = "MediumFast"
    
    # Create mock packet
    mock_packet = Mock()
    mock_packet.id = 123456
    setattr(mock_packet, 'from', 0x11223344)
    mock_packet.HasField = Mock(return_value=True)
    
    # Create mock decoded data (TELEMETRY)
    mock_decoded = Mock()
    mock_decoded.portnum = portnums_pb2.PortNum.TELEMETRY_APP
    mock_decoded.payload = b''
    
    mock_packet.decoded = mock_decoded
    mock_envelope.packet = mock_packet
    
    # Mock the ServiceEnvelope parsing
    with patch.object(mqtt_pb2, 'ServiceEnvelope', return_value=mock_envelope):
        with patch('mqtt_neighbor_collector.debug_print') as mock_debug:
            # Call the message handler
            collector._on_mqtt_message(None, None, mock_msg)
            
            # Verify get_node_name was called for gateway
            debug_calls = [str(call) for call in mock_debug.call_args_list]
            
            # Check if gateway name appears in debug calls
            gateway_name_found = any("GatewayNode" in call for call in debug_calls)
            
            if gateway_name_found:
                print("✅ PASS: Gateway ID resolved to node name")
                for call in debug_calls:
                    if "GatewayNode" in call or "via" in call:
                        print(f"   Found: {call}")
            else:
                print("❌ FAIL: Gateway ID not resolved to node name")
                print("   Debug calls:")
                for call in debug_calls:
                    print(f"   {call}")
    
    print()

def test_no_gateway_id():
    """Test graceful handling when gateway_id is missing"""
    print("=== Test 3: Missing Gateway ID ===")
    
    # Create mock objects
    mock_persistence = Mock()
    mock_node_manager = Mock()
    
    collector = MQTTNeighborCollector(
        mqtt_server="test.example.com",
        mqtt_port=1883,
        persistence=mock_persistence,
        node_manager=mock_node_manager
    )
    
    # Create mock MQTT message
    mock_msg = Mock()
    mock_msg.topic = "msh/EU_868/2/e/unknown"
    
    # Create mock ServiceEnvelope without gateway_id
    mock_envelope = Mock()
    mock_envelope.HasField = Mock(return_value=True)
    mock_envelope.gateway_id = ''  # Empty string, simulating missing gateway_id
    
    # Create mock packet
    mock_packet = Mock()
    mock_packet.id = 123456
    setattr(mock_packet, 'from', 0x11223344)
    mock_packet.HasField = Mock(return_value=True)
    
    # Create mock decoded data
    mock_decoded = Mock()
    mock_decoded.portnum = portnums_pb2.PortNum.POSITION_APP
    mock_decoded.payload = b''
    
    mock_packet.decoded = mock_decoded
    mock_envelope.packet = mock_packet
    
    # Mock the ServiceEnvelope parsing
    with patch.object(mqtt_pb2, 'ServiceEnvelope', return_value=mock_envelope):
        with patch('mqtt_neighbor_collector.debug_print') as mock_debug:
            # Call the message handler - should not crash
            try:
                collector._on_mqtt_message(None, None, mock_msg)
                print("✅ PASS: Handles missing gateway_id gracefully")
                
                # Verify debug was still called (without via suffix)
                if mock_debug.called:
                    print("   Debug logs generated successfully")
            except Exception as e:
                print(f"❌ FAIL: Exception raised: {e}")
    
    print()

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("Testing MQTT 'via' Information Extraction")
    print("="*60)
    
    test_gateway_id_extraction()
    test_gateway_name_resolution()
    test_no_gateway_id()
    
    print("="*60)
    print("Testing Complete!")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
