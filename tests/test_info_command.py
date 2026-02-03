#!/usr/bin/env python3
"""
Test script for /info command implementation
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

# Mock config module
class MockConfig:
    DEBUG_MODE = False
    REMOTE_NODE_HOST = "192.168.1.38"
    REMOTE_NODE_NAME = "tigrog2"
    NODE_NAMES_FILE = "node_names_test.json"
    NEIGHBOR_RETENTION_HOURS = 720
    BOT_POSITION = (47.123, 6.789)

sys.modules['config'] = MockConfig()

from handlers.command_handlers.network_commands import NetworkCommands
from handlers.message_sender import MessageSender
from node_manager import NodeManager
from traffic_monitor import TrafficMonitor


class MockRemoteNodesClient:
    """Mock client for testing"""
    def get_remote_nodes(self, host):
        """Return mock node data"""
        return [
            {
                'id': 0x12345678,
                'name': 'TestNode',
                'rssi': -95,
                'snr': 5.5,
                'last_heard': 1234567890,
            },
            {
                'id': 0xF547FABC,
                'name': 'tigrog2',
                'rssi': -87,
                'snr': 8.2,
                'last_heard': 1234567800,
            }
        ]


class MockInterface:
    """Mock Meshtastic interface"""
    def __init__(self):
        self.localNode = None


class MockSender:
    """Mock message sender"""
    def __init__(self):
        self.sent_messages = []
    
    def send_single(self, message, sender_id, sender_info):
        print(f"\n📤 SENT (single):")
        print(f"   To: {sender_info} (ID: {sender_id:08x})")
        print(f"   Message ({len(message)} chars):")
        print(f"   {message}")
        self.sent_messages.append(('single', message))
    
    def send_chunks(self, message, sender_id, sender_info):
        print(f"\n📤 SENT (chunks):")
        print(f"   To: {sender_info} (ID: {sender_id:08x})")
        print(f"   Message ({len(message)} chars):")
        print(f"   {message}")
        self.sent_messages.append(('chunks', message))
    
    def log_conversation(self, sender_id, sender_info, command, response):
        print(f"\n📝 LOGGED: {command}")


def test_info_compact():
    """Test compact format (mesh)"""
    print("\n" + "="*60)
    print("TEST 1: /info compact format (mesh)")
    print("="*60)
    
    # Setup
    node_manager = NodeManager()
    node_manager.node_names = {
        0x12345678: {
            'name': 'TestNode',
            'shortName': 'TEST',
            'hwModel': 'TLORA_V2_1_1P6',
            'lat': 47.123456,
            'lon': 6.789012,
            'alt': 450,
            'last_update': 1234567890
        }
    }
    
    mock_client = MockRemoteNodesClient()
    mock_sender = MockSender()
    mock_interface = MockInterface()
    
    handler = NetworkCommands(
        remote_nodes_client=mock_client,
        sender=mock_sender,
        node_manager=node_manager,
        interface=mock_interface
    )
    
    # Test: /info TestNode (compact)
    message = "/info TestNode"
    sender_id = 0x11111111
    sender_info = "Mesh User"
    
    print(f"\n📥 COMMAND: {message}")
    print(f"   From: {sender_info} (ID: {sender_id:08x})")
    print(f"   Format: compact (mesh)")
    
    handler.handle_info(message, sender_id, sender_info, is_broadcast=False)
    
    # Wait a bit for thread to complete
    import time
    time.sleep(1)
    
    # Check result
    if mock_sender.sent_messages:
        msg_type, msg_content = mock_sender.sent_messages[-1]
        print(f"\n✅ Message sent successfully")
        print(f"   Length: {len(msg_content)} chars (limit: 180)")
        if len(msg_content) > 180:
            print(f"   ⚠️ WARNING: Message exceeds 180 char limit!")
        else:
            print(f"   ✓ Within 180 char limit")
    else:
        print(f"\n❌ No message sent")


def test_info_detailed():
    """Test detailed format (Telegram/CLI)"""
    print("\n" + "="*60)
    print("TEST 2: /info detailed format (Telegram/CLI)")
    print("="*60)
    
    # Setup with traffic monitor
    node_manager = NodeManager()
    node_manager.node_names = {
        0xF547FABC: {
            'name': 'tigrog2',
            'shortName': 'TGR2',
            'hwModel': 'TLORA_V2_1_1P6',
            'lat': 47.234567,
            'lon': 6.890123,
            'alt': 520,
            'last_update': 1234567800
        }
    }
    
    traffic_monitor = TrafficMonitor(node_manager)
    # Add some stats
    traffic_monitor.node_packet_stats[0xF547FABC] = {
        'total_packets': 1234,
        'by_type': {
            'TEXT_MESSAGE_APP': 456,
            'POSITION_APP': 123,
            'NODEINFO_APP': 45,
            'TELEMETRY_APP': 67
        },
        'first_seen': 1234500000,
        'last_seen': 1234567890,
        'telemetry_stats': {
            'count': 67,
            'last_battery': 85,
            'last_voltage': 4.15
        }
    }
    
    mock_client = MockRemoteNodesClient()
    mock_sender = MockSender()
    mock_interface = MockInterface()
    
    handler = NetworkCommands(
        remote_nodes_client=mock_client,
        sender=mock_sender,
        node_manager=node_manager,
        traffic_monitor=traffic_monitor,
        interface=mock_interface
    )
    
    # Test: /info tigrog2 (detailed - simulate Telegram)
    message = "/info tigrog2"
    sender_id = 0x22222222
    sender_info = "telegram_user_123"  # Contains 'telegram' -> detailed format
    
    print(f"\n📥 COMMAND: {message}")
    print(f"   From: {sender_info} (ID: {sender_id:08x})")
    print(f"   Format: detailed (Telegram)")
    
    handler.handle_info(message, sender_id, sender_info, is_broadcast=False)
    
    # Wait for thread
    import time
    time.sleep(1)
    
    # Check result
    if mock_sender.sent_messages:
        msg_type, msg_content = mock_sender.sent_messages[-1]
        print(f"\n✅ Message sent successfully")
        print(f"   Type: {msg_type}")
        print(f"   Length: {len(msg_content)} chars")
    else:
        print(f"\n❌ No message sent")


def test_info_node_not_found():
    """Test error handling for non-existent node"""
    print("\n" + "="*60)
    print("TEST 3: /info with non-existent node")
    print("="*60)
    
    # Setup
    node_manager = NodeManager()
    node_manager.node_names = {}  # Empty
    
    mock_client = MockRemoteNodesClient()
    mock_sender = MockSender()
    mock_interface = MockInterface()
    
    handler = NetworkCommands(
        remote_nodes_client=mock_client,
        sender=mock_sender,
        node_manager=node_manager,
        interface=mock_interface
    )
    
    # Test: /info NonExistent
    message = "/info NonExistent"
    sender_id = 0x33333333
    sender_info = "Mesh User"
    
    print(f"\n📥 COMMAND: {message}")
    print(f"   From: {sender_info} (ID: {sender_id:08x})")
    
    handler.handle_info(message, sender_id, sender_info, is_broadcast=False)
    
    # Wait for thread
    import time
    time.sleep(1)
    
    # Check result
    if mock_sender.sent_messages:
        msg_type, msg_content = mock_sender.sent_messages[-1]
        print(f"\n✅ Error message sent")
        print(f"   Message: {msg_content}")
        if "introuvable" in msg_content.lower() or "not found" in msg_content.lower():
            print(f"   ✓ Proper error message")
        else:
            print(f"   ⚠️ Unexpected error message")
    else:
        print(f"\n❌ No error message sent")


def test_info_missing_argument():
    """Test error handling for missing argument"""
    print("\n" + "="*60)
    print("TEST 4: /info without argument")
    print("="*60)
    
    # Setup
    node_manager = NodeManager()
    mock_client = MockRemoteNodesClient()
    mock_sender = MockSender()
    mock_interface = MockInterface()
    
    handler = NetworkCommands(
        remote_nodes_client=mock_client,
        sender=mock_sender,
        node_manager=node_manager,
        interface=mock_interface
    )
    
    # Test: /info (no argument)
    message = "/info"
    sender_id = 0x44444444
    sender_info = "Mesh User"
    
    print(f"\n📥 COMMAND: {message}")
    print(f"   From: {sender_info} (ID: {sender_id:08x})")
    
    handler.handle_info(message, sender_id, sender_info, is_broadcast=False)
    
    # Check result (should be immediate, no thread)
    if mock_sender.sent_messages:
        msg_type, msg_content = mock_sender.sent_messages[-1]
        print(f"\n✅ Usage message sent")
        print(f"   Message: {msg_content}")
        if "usage" in msg_content.lower():
            print(f"   ✓ Proper usage message")
        else:
            print(f"   ⚠️ Unexpected message")
    else:
        print(f"\n❌ No usage message sent")


def test_info_by_id():
    """Test /info with node ID (hex)"""
    print("\n" + "="*60)
    print("TEST 5: /info by node ID")
    print("="*60)
    
    # Setup
    node_manager = NodeManager()
    node_manager.node_names = {
        0xF547FABC: {
            'name': 'tigrog2',
            'shortName': 'TGR2',
            'hwModel': 'TLORA_V2_1_1P6',
            'lat': 47.234567,
            'lon': 6.890123,
            'alt': 520,
            'last_update': 1234567800
        }
    }
    
    mock_client = MockRemoteNodesClient()
    mock_sender = MockSender()
    mock_interface = MockInterface()
    
    handler = NetworkCommands(
        remote_nodes_client=mock_client,
        sender=mock_sender,
        node_manager=node_manager,
        interface=mock_interface
    )
    
    # Test different ID formats
    test_cases = [
        "/info F547F",        # Partial ID without padding
        "/info F547FABC",     # Full ID without padding
        "/info !F547FABC",    # With Meshtastic prefix
    ]
    
    for test_message in test_cases:
        print(f"\n📥 COMMAND: {test_message}")
        print(f"   Testing ID recognition...")
        
        mock_sender.sent_messages = []  # Reset
        handler.handle_info(test_message, 0x55555555, "Mesh User", is_broadcast=False)
        
        import time
        time.sleep(1)
        
        if mock_sender.sent_messages:
            msg_type, msg_content = mock_sender.sent_messages[-1]
            if "tigrog2" in msg_content:
                print(f"   ✓ Node found by ID")
            else:
                print(f"   ⚠️ Node not found or unexpected result")
        else:
            print(f"   ❌ No response")


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("TESTING /info COMMAND IMPLEMENTATION")
    print("="*60)
    
    try:
        test_info_compact()
        test_info_detailed()
        test_info_node_not_found()
        test_info_missing_argument()
        test_info_by_id()
        
        print("\n" + "="*60)
        print("ALL TESTS COMPLETED")
        print("="*60)
        print("\nCheck output above for any warnings or failures.")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED WITH EXCEPTION:")
        print(f"   {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
