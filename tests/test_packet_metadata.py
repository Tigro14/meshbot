#!/usr/bin/env python3
"""
Test for comprehensive packet metadata extraction and DEBUG logging.
Tests that all new metadata fields are extracted and logged correctly.
"""

import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time
from unittest.mock import Mock, MagicMock

# Mock config before imports
sys.modules['config'] = MagicMock()

from traffic_monitor import TrafficMonitor
from traffic_persistence import TrafficPersistence
from node_manager import NodeManager

def create_mock_node_manager():
    """Create a mock node manager with a test node"""
    node_manager = Mock(spec=NodeManager)
    node_manager.get_node_name = Mock(return_value="TestNode")
    
    # Mock interface with nodes
    mock_interface = Mock()
    mock_interface.nodes = {
        0x12345678: {
            'user': {
                'id': '!12345678',
                'longName': 'TestNode',
                'shortName': 'TN1',
                'publicKey': 'dGVzdHB1YmxpY2tleXRlc3RwdWJsaWNrZXl0ZXN0cHVia2V5'  # base64: "testpublickeytestpublickeytestpubkey"
            }
        }
    }
    node_manager.interface = mock_interface
    
    return node_manager

def test_packet_metadata_extraction():
    """Test that packet metadata is correctly extracted"""
    print("\n" + "="*70)
    print("TEST 1: Packet Metadata Extraction")
    print("="*70)
    
    # Create mock node manager
    node_manager = create_mock_node_manager()
    
    # Create traffic monitor
    monitor = TrafficMonitor(node_manager)
    
    # Create a test packet with all metadata fields
    test_packet = {
        'id': 123456789,
        'from': 0x12345678,
        'to': 0xFFFFFFFF,  # Broadcast
        'rxTime': int(time.time()),
        'hopLimit': 3,
        'hopStart': 5,
        'rssi': -95,
        'snr': 8.5,
        'channel': 0,
        'viaMqtt': False,
        'wantAck': False,
        'wantResponse': False,
        'priority': 0,
        'decoded': {
            'portnum': 'TEXT_MESSAGE_APP',
            'text': 'Test message'
        }
    }
    
    # Extract metadata using add_packet
    print("\n📋 Testing add_packet() with full metadata...")
    try:
        monitor.add_packet(test_packet, source='local', my_node_id=0x87654321, interface=node_manager.interface)
        print("✅ Packet processed successfully")
        
        # Check that packet was added to queue
        assert len(monitor.all_packets) > 0, "Packet should be added to queue"
        print(f"✅ Packet added to queue (total: {len(monitor.all_packets)})")
        
        # Get the added packet
        added_packet = monitor.all_packets[-1]
        
        # Verify all metadata fields
        print("\n📊 Verifying extracted metadata:")
        
        # Basic fields
        assert added_packet['from_id'] == 0x12345678, "from_id should match"
        print(f"  ✅ from_id: {added_packet['from_id']:08x}")
        
        assert added_packet['to_id'] == 0xFFFFFFFF, "to_id should match"
        print(f"  ✅ to_id: {added_packet['to_id']:08x}")
        
        assert added_packet['packet_type'] == 'TEXT_MESSAGE_APP', "packet_type should match"
        print(f"  ✅ packet_type: {added_packet['packet_type']}")
        
        # Hop fields
        assert added_packet['hop_limit'] == 3, "hop_limit should match"
        assert added_packet['hop_start'] == 5, "hop_start should match"
        assert added_packet['hops'] == 2, "hops should be calculated as hop_start - hop_limit"
        print(f"  ✅ hops: {added_packet['hops']} (limit: {added_packet['hop_limit']}, start: {added_packet['hop_start']})")
        
        # New metadata fields
        assert added_packet['channel'] == 0, "channel should match"
        print(f"  ✅ channel: {added_packet['channel']}")
        
        assert added_packet['via_mqtt'] == False, "via_mqtt should match"
        print(f"  ✅ via_mqtt: {added_packet['via_mqtt']}")
        
        assert added_packet['want_ack'] == False, "want_ack should match"
        print(f"  ✅ want_ack: {added_packet['want_ack']}")
        
        assert added_packet['want_response'] == False, "want_response should match"
        print(f"  ✅ want_response: {added_packet['want_response']}")
        
        assert added_packet['priority'] == 0, "priority should match"
        print(f"  ✅ priority: {added_packet['priority']}")
        
        assert added_packet['family'] == 'FLOOD', "family should be FLOOD for broadcast"
        print(f"  ✅ family: {added_packet['family']}")
        
        # Public key should be extracted from mock node
        assert added_packet['public_key'] is not None, "public_key should be extracted"
        print(f"  ✅ public_key: {added_packet['public_key'][:20]}... ({len(added_packet['public_key'])} chars)")
        
        print("\n✅ All metadata fields extracted correctly!")
        
    except Exception as e:
        print(f"❌ Error processing packet: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def test_direct_message_family():
    """Test that direct messages get DIRECT family"""
    print("\n" + "="*70)
    print("TEST 2: DIRECT Message Family")
    print("="*70)
    
    node_manager = create_mock_node_manager()
    monitor = TrafficMonitor(node_manager)
    
    # Create a direct message packet (not broadcast)
    dm_packet = {
        'id': 123456790,
        'from': 0x12345678,
        'to': 0x87654321,  # Direct to specific node
        'rxTime': int(time.time()),
        'hopLimit': 5,
        'hopStart': 5,
        'rssi': -85,
        'snr': 12.0,
        'channel': 0,
        'viaMqtt': False,
        'wantAck': True,  # Direct messages often want ACK
        'wantResponse': False,
        'priority': 32,  # ACK_REQ priority
        'decoded': {
            'portnum': 'TEXT_MESSAGE_APP',
            'text': 'Private message'
        }
    }
    
    print("\n📋 Testing direct message...")
    try:
        monitor.add_packet(dm_packet, source='local', my_node_id=0x99999999, interface=node_manager.interface)
        
        added_packet = monitor.all_packets[-1]
        
        # Verify family is DIRECT
        assert added_packet['family'] == 'DIRECT', "family should be DIRECT for unicast"
        print(f"  ✅ family: {added_packet['family']}")
        
        assert added_packet['is_broadcast'] == False, "is_broadcast should be False"
        print(f"  ✅ is_broadcast: {added_packet['is_broadcast']}")
        
        assert added_packet['want_ack'] == True, "want_ack should be True"
        print(f"  ✅ want_ack: {added_packet['want_ack']}")
        
        assert added_packet['priority'] == 32, "priority should be 32 (ACK_REQ)"
        print(f"  ✅ priority: {added_packet['priority']}")
        
        print("\n✅ Direct message metadata correct!")
        
    except Exception as e:
        print(f"❌ Error processing direct message: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def test_database_persistence():
    """Test that metadata is saved to SQLite correctly"""
    print("\n" + "="*70)
    print("TEST 3: Database Persistence")
    print("="*70)
    
    import os
    import sqlite3
    
    # Use temp database
    db_path = '/tmp/test_packet_metadata.db'
    if os.path.exists(db_path):
        os.remove(db_path)
    
    print(f"\n📁 Creating test database: {db_path}")
    
    try:
        # Create persistence layer
        persistence = TrafficPersistence(db_path)
        
        # Create a test packet entry
        packet_entry = {
            'timestamp': time.time(),
            'from_id': 0x12345678,
            'to_id': 0xFFFFFFFF,
            'source': 'local',
            'sender_name': 'TestNode',
            'packet_type': 'TEXT_MESSAGE_APP',
            'message': 'Test message',
            'rssi': -95,
            'snr': 8.5,
            'hops': 2,
            'hop_limit': 3,
            'hop_start': 5,
            'size': 100,
            'is_broadcast': True,
            'is_encrypted': False,
            # New metadata fields
            'channel': 0,
            'via_mqtt': False,
            'want_ack': False,
            'want_response': False,
            'priority': 0,
            'family': 'FLOOD',
            'public_key': 'dGVzdHB1YmxpY2tleXRlc3RwdWJsaWNrZXl0ZXN0cHVia2V5'
        }
        
        # Save packet
        print("\n💾 Saving packet to database...")
        persistence.save_packet(packet_entry)
        print("✅ Packet saved")
        
        # Verify columns exist and data is correct
        print("\n🔍 Verifying database schema and data...")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='packets'")
        assert cursor.fetchone() is not None, "packets table should exist"
        print("  ✅ packets table exists")
        
        # Check new columns exist
        cursor.execute("PRAGMA table_info(packets)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        required_columns = ['channel', 'via_mqtt', 'want_ack', 'want_response', 'priority', 'family', 'public_key']
        for col in required_columns:
            assert col in columns, f"{col} column should exist"
            print(f"  ✅ {col} column exists ({columns[col]})")
        
        # Verify data
        cursor.execute("SELECT * FROM packets ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        assert row is not None, "Packet should be in database"
        
        # Get column names
        cursor.execute("PRAGMA table_info(packets)")
        col_names = [row[1] for row in cursor.fetchall()]
        
        # Create dict from row
        saved_packet = dict(zip(col_names, row))
        
        print("\n📊 Verifying saved data:")
        print(f"  ✅ channel: {saved_packet['channel']}")
        print(f"  ✅ via_mqtt: {saved_packet['via_mqtt']}")
        print(f"  ✅ want_ack: {saved_packet['want_ack']}")
        print(f"  ✅ want_response: {saved_packet['want_response']}")
        print(f"  ✅ priority: {saved_packet['priority']}")
        print(f"  ✅ family: {saved_packet['family']}")
        print(f"  ✅ public_key: {saved_packet['public_key'][:20] if saved_packet['public_key'] else 'None'}...")
        
        # Verify values
        assert saved_packet['channel'] == 0
        assert saved_packet['via_mqtt'] == 0  # Boolean stored as INTEGER
        assert saved_packet['want_ack'] == 0
        assert saved_packet['want_response'] == 0
        assert saved_packet['priority'] == 0
        assert saved_packet['family'] == 'FLOOD'
        assert saved_packet['public_key'] == 'dGVzdHB1YmxpY2tleXRlc3RwdWJsaWNrZXl0ZXN0cHVia2V5'
        
        conn.close()
        
        print("\n✅ All database fields saved and verified correctly!")
        
        # Cleanup
        os.remove(db_path)
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def test_public_key_extraction():
    """Test public key extraction from different node formats"""
    print("\n" + "="*70)
    print("TEST 4: Public Key Extraction")
    print("="*70)
    
    node_manager = create_mock_node_manager()
    monitor = TrafficMonitor(node_manager)
    
    # Test 1: Node with publicKey (dict format)
    print("\n📋 Testing publicKey extraction (dict format)...")
    public_key = monitor._get_sender_public_key(0x12345678, node_manager.interface)
    assert public_key is not None, "Public key should be found"
    print(f"  ✅ Public key found: {public_key[:20]}... ({len(public_key)} chars)")
    
    # Test 2: Node without public key
    print("\n📋 Testing missing public key...")
    public_key = monitor._get_sender_public_key(0x99999999, node_manager.interface)
    assert public_key is None, "Public key should be None for unknown node"
    print("  ✅ Correctly returns None for unknown node")
    
    print("\n✅ Public key extraction working correctly!")
    
    return True

if __name__ == '__main__':
    print("="*70)
    print("COMPREHENSIVE PACKET METADATA TEST SUITE")
    print("="*70)
    
    all_passed = True
    
    # Run all tests
    all_passed &= test_packet_metadata_extraction()
    all_passed &= test_direct_message_family()
    all_passed &= test_database_persistence()
    all_passed &= test_public_key_extraction()
    
    # Summary
    print("\n" + "="*70)
    if all_passed:
        print("✅ ALL TESTS PASSED!")
        print("="*70)
        print("\n✨ Implementation verified:")
        print("  • Packet metadata extraction working")
        print("  • Family (FLOOD/DIRECT) correctly determined")
        print("  • Channel, priority, flags extracted")
        print("  • Public key extraction working")
        print("  • SQLite persistence working")
        print("  • Database schema updated")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        print("="*70)
        sys.exit(1)
