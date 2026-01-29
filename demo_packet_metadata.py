#!/usr/bin/env python3
"""
Demo script showing packet metadata extraction and DEBUG logging.
Demonstrates the comprehensive packet metadata display feature.
"""

import sys
from unittest.mock import Mock, MagicMock
import time

# Mock config with DEBUG_MODE enabled
config_mock = MagicMock()
config_mock.DEBUG_MODE = True
sys.modules['config'] = config_mock

from traffic_monitor import TrafficMonitor
from node_manager import NodeManager

def create_demo_interface():
    """Create a mock interface with demo nodes"""
    interface = Mock()
    interface.nodes = {
        0x16fad3dc: {
            'user': {
                'id': '!16fad3dc',
                'longName': 'tigrobot',
                'shortName': 'tbot',
                'publicKey': 'VGhpc0lzQVRlc3RQdWJsaWNLZXlGb3JEZW1vUHVycG9zZXM='
            }
        },
        0x0de3331e: {
            'user': {
                'id': '!0de3331e',
                'longName': 'tigro g2',
                'shortName': 'tg2',
                'publicKey': 'QW5vdGhlclRlc3RQdWJsaWNLZXlGb3JEZW1vUHVycG9zZXM='
            }
        }
    }
    return interface

def demo_broadcast_message():
    """Demo: Broadcast message with full metadata"""
    print("\n" + "="*70)
    print("DEMO 1: FLOOD (Broadcast) Message")
    print("="*70)
    print("\nScenario: Node 'tigrobot' broadcasts a message on channel 0")
    print("          Relayed 2 hops from original sender")
    
    node_manager = Mock(spec=NodeManager)
    node_manager.get_node_name = Mock(return_value="tigrobot")
    interface = create_demo_interface()
    node_manager.interface = interface
    
    monitor = TrafficMonitor(node_manager)
    
    packet = {
        'id': 987654321,
        'from': 0x16fad3dc,
        'to': 0xFFFFFFFF,  # Broadcast
        'rxTime': int(time.time()),
        'hopLimit': 3,
        'hopStart': 5,
        'rssi': -92,
        'snr': 9.2,
        'channel': 0,
        'viaMqtt': False,
        'wantAck': False,
        'wantResponse': False,
        'priority': 0,  # DEFAULT
        'decoded': {
            'portnum': 'TEXT_MESSAGE_APP',
            'text': 'Hello everyone on the mesh!'
        }
    }
    
    print("\n📡 Processing packet...")
    monitor.add_packet(packet, source='local', my_node_id=0x99999999, interface=interface)
    print("\n✅ Packet processed and logged in DEBUG mode")

def demo_direct_message():
    """Demo: Direct message with ACK request"""
    print("\n" + "="*70)
    print("DEMO 2: DIRECT (Unicast) Message with ACK")
    print("="*70)
    print("\nScenario: Node 'tigro g2' sends private message to 'tigrobot'")
    print("          Wants acknowledgment, high priority")
    
    node_manager = Mock(spec=NodeManager)
    node_manager.get_node_name = Mock(return_value="tigro g2")
    interface = create_demo_interface()
    node_manager.interface = interface
    
    monitor = TrafficMonitor(node_manager)
    
    packet = {
        'id': 987654322,
        'from': 0x0de3331e,
        'to': 0x16fad3dc,  # Direct to tigrobot
        'rxTime': int(time.time()),
        'hopLimit': 5,
        'hopStart': 5,
        'rssi': -78,
        'snr': 14.5,
        'channel': 0,
        'viaMqtt': False,
        'wantAck': True,  # Wants acknowledgment
        'wantResponse': True,  # Expects response
        'priority': 64,  # RELIABLE
        'decoded': {
            'portnum': 'TEXT_MESSAGE_APP',
            'text': 'Private message - please confirm receipt'
        }
    }
    
    print("\n📡 Processing packet...")
    monitor.add_packet(packet, source='local', my_node_id=0x99999999, interface=interface)
    print("\n✅ Packet processed and logged in DEBUG mode")

def demo_position_packet():
    """Demo: Position packet (GPS location)"""
    print("\n" + "="*70)
    print("DEMO 3: POSITION_APP Packet")
    print("="*70)
    print("\nScenario: Node 'tigrobot' broadcasts GPS position")
    print("          Standard priority, no ACK needed")
    
    node_manager = Mock(spec=NodeManager)
    node_manager.get_node_name = Mock(return_value="tigrobot")
    interface = create_demo_interface()
    node_manager.interface = interface
    
    monitor = TrafficMonitor(node_manager)
    
    packet = {
        'id': 987654323,
        'from': 0x16fad3dc,
        'to': 0xFFFFFFFF,
        'rxTime': int(time.time()),
        'hopLimit': 4,
        'hopStart': 5,
        'rssi': -88,
        'snr': 10.8,
        'channel': 0,
        'viaMqtt': False,
        'wantAck': False,
        'wantResponse': False,
        'priority': 0,
        'decoded': {
            'portnum': 'POSITION_APP',
            'position': {
                'latitude': 47.234567 * 1e7,  # Stored as int in protobuf
                'longitude': 6.123456 * 1e7,
                'altitude': 450
            }
        }
    }
    
    print("\n📡 Processing packet...")
    monitor.add_packet(packet, source='local', my_node_id=0x99999999, interface=interface)
    print("\n✅ Packet processed and logged in DEBUG mode")

def demo_mqtt_gateway_packet():
    """Demo: Message received via MQTT gateway"""
    print("\n" + "="*70)
    print("DEMO 4: Message via MQTT Gateway")
    print("="*70)
    print("\nScenario: Message from remote node via MQTT gateway")
    print("          Channel 1, came through internet gateway")
    
    node_manager = Mock(spec=NodeManager)
    node_manager.get_node_name = Mock(return_value="remote-node")
    interface = create_demo_interface()
    node_manager.interface = interface
    
    monitor = TrafficMonitor(node_manager)
    
    packet = {
        'id': 987654324,
        'from': 0x11223344,
        'to': 0xFFFFFFFF,
        'rxTime': int(time.time()),
        'hopLimit': 5,
        'hopStart': 5,
        'rssi': 0,  # No radio metrics for MQTT
        'snr': 0,
        'channel': 1,  # Secondary channel
        'viaMqtt': True,  # Via MQTT gateway
        'wantAck': False,
        'wantResponse': False,
        'priority': 0,
        'decoded': {
            'portnum': 'TEXT_MESSAGE_APP',
            'text': 'Message from internet gateway'
        }
    }
    
    print("\n📡 Processing packet...")
    monitor.add_packet(packet, source='local', my_node_id=0x99999999, interface=interface)
    print("\n✅ Packet processed and logged in DEBUG mode")

def demo_critical_priority():
    """Demo: Critical priority message"""
    print("\n" + "="*70)
    print("DEMO 5: Critical Priority Message")
    print("="*70)
    print("\nScenario: Emergency alert with critical priority")
    print("          Highest priority (100), wants ACK and response")
    
    node_manager = Mock(spec=NodeManager)
    node_manager.get_node_name = Mock(return_value="emergency-node")
    interface = create_demo_interface()
    node_manager.interface = interface
    
    monitor = TrafficMonitor(node_manager)
    
    packet = {
        'id': 987654325,
        'from': 0x55667788,
        'to': 0xFFFFFFFF,
        'rxTime': int(time.time()),
        'hopLimit': 3,
        'hopStart': 3,
        'rssi': -105,
        'snr': 2.5,
        'channel': 0,
        'viaMqtt': False,
        'wantAck': True,
        'wantResponse': True,
        'priority': 100,  # CRITICAL
        'decoded': {
            'portnum': 'TEXT_MESSAGE_APP',
            'text': '🚨 EMERGENCY: Need assistance immediately'
        }
    }
    
    print("\n📡 Processing packet...")
    monitor.add_packet(packet, source='local', my_node_id=0x99999999, interface=interface)
    print("\n✅ Packet processed and logged in DEBUG mode")

if __name__ == '__main__':
    print("="*70)
    print("PACKET METADATA EXTRACTION - INTERACTIVE DEMO")
    print("="*70)
    print("\nThis demo shows the comprehensive packet metadata logging")
    print("feature in DEBUG mode. Each packet displays:")
    print("  • Family (FLOOD/DIRECT)")
    print("  • Channel (0-7)")
    print("  • Priority (CRITICAL/RELIABLE/ACK_REQ/DEFAULT)")
    print("  • Flags (Via MQTT, Want ACK, Want Response)")
    print("  • Public Key (if available)")
    print("  • Path (hops taken)")
    print("  • Type (MESSAGE/POSITION/TELEMETRY/etc.)")
    print("  • Name (sender node name)")
    print("  • Position (GPS coordinates if available)")
    
    # Run all demos
    demo_broadcast_message()
    demo_direct_message()
    demo_position_packet()
    demo_mqtt_gateway_packet()
    demo_critical_priority()
    
    print("\n" + "="*70)
    print("✅ DEMO COMPLETE")
    print("="*70)
    print("\nAll packet metadata has been extracted and logged in DEBUG mode.")
    print("The logs show comprehensive information without exposing raw data.")
    print("\nKey features demonstrated:")
    print("  ✓ Family detection (FLOOD vs DIRECT)")
    print("  ✓ Channel identification")
    print("  ✓ Priority levels (0-100)")
    print("  ✓ Routing flags (MQTT, ACK, Response)")
    print("  ✓ Public key extraction and display")
    print("  ✓ Complete hop path information")
    print("  ✓ Signal quality metrics (RSSI/SNR)")
