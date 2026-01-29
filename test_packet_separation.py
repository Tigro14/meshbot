#!/usr/bin/env python3
"""
Test for MeshCore and Meshtastic packet separation.
Verifies that packets are saved to separate tables based on source.
"""

import sys
import time
import os
import sqlite3
from unittest.mock import Mock, MagicMock

# Mock config before imports
sys.modules['config'] = MagicMock()

from traffic_monitor import TrafficMonitor
from traffic_persistence import TrafficPersistence
from node_manager import NodeManager

def create_mock_node_manager():
    """Create a mock node manager"""
    node_manager = Mock(spec=NodeManager)
    node_manager.get_node_name = Mock(return_value="TestNode")
    
    # Mock interface
    mock_interface = Mock()
    mock_interface.nodes = {}
    node_manager.interface = mock_interface
    
    return node_manager

def test_separate_tables():
    """Test that MeshCore and Meshtastic packets go to separate tables"""
    print("\n" + "="*70)
    print("TEST: MeshCore and Meshtastic Packet Separation")
    print("="*70)
    
    # Use temp database
    db_path = '/tmp/test_packet_separation.db'
    if os.path.exists(db_path):
        os.remove(db_path)
    
    print(f"\n📁 Creating test database: {db_path}")
    
    try:
        # Create persistence layer
        persistence = TrafficPersistence(db_path)
        node_manager = create_mock_node_manager()
        monitor = TrafficMonitor(node_manager)
        monitor.persistence = persistence
        
        # Create Meshtastic packet (source='local')
        print("\n1️⃣ Testing Meshtastic packet (source='local')...")
        meshtastic_packet = {
            'id': 111111,
            'from': 0x12345678,
            'to': 0xFFFFFFFF,
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
                'text': 'Meshtastic message'
            }
        }
        
        monitor.add_packet(meshtastic_packet, source='local', my_node_id=0x99999999, interface=node_manager.interface)
        print("   ✅ Meshtastic packet processed")
        
        # Create MeshCore packet (source='meshcore')
        print("\n2️⃣ Testing MeshCore packet (source='meshcore')...")
        meshcore_packet = {
            'id': 222222,
            'from': 0x87654321,
            'to': 0xFFFFFFFF,
            'rxTime': int(time.time()),
            'hopLimit': 4,
            'hopStart': 5,
            'rssi': -88,
            'snr': 10.2,
            'channel': 0,
            'viaMqtt': False,
            'wantAck': False,
            'wantResponse': False,
            'priority': 0,
            'decoded': {
                'portnum': 'TEXT_MESSAGE_APP',
                'text': 'MeshCore message'
            }
        }
        
        monitor.add_packet(meshcore_packet, source='meshcore', my_node_id=0x99999999, interface=node_manager.interface)
        print("   ✅ MeshCore packet processed")
        
        # Verify tables exist
        print("\n3️⃣ Verifying table structure...")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check both tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        
        assert 'packets' in tables, "packets table should exist"
        print("   ✅ packets table exists")
        
        assert 'meshcore_packets' in tables, "meshcore_packets table should exist"
        print("   ✅ meshcore_packets table exists")
        
        # Verify Meshtastic packet is in packets table
        print("\n4️⃣ Verifying packet storage...")
        cursor.execute("SELECT COUNT(*), source FROM packets GROUP BY source")
        packets_results = cursor.fetchall()
        print(f"   packets table: {packets_results}")
        
        # Should have 1 packet with source='local'
        cursor.execute("SELECT COUNT(*) FROM packets WHERE source='local'")
        meshtastic_count = cursor.fetchone()[0]
        assert meshtastic_count == 1, f"Should have 1 Meshtastic packet, got {meshtastic_count}"
        print("   ✅ Meshtastic packet in 'packets' table")
        
        # Should have 0 meshcore packets in packets table
        cursor.execute("SELECT COUNT(*) FROM packets WHERE source='meshcore'")
        meshcore_in_packets = cursor.fetchone()[0]
        assert meshcore_in_packets == 0, f"Should have 0 MeshCore packets in 'packets', got {meshcore_in_packets}"
        print("   ✅ No MeshCore packets in 'packets' table")
        
        # Verify MeshCore packet is in meshcore_packets table
        cursor.execute("SELECT COUNT(*), source FROM meshcore_packets GROUP BY source")
        meshcore_results = cursor.fetchall()
        print(f"   meshcore_packets table: {meshcore_results}")
        
        cursor.execute("SELECT COUNT(*) FROM meshcore_packets WHERE source='meshcore'")
        meshcore_count = cursor.fetchone()[0]
        assert meshcore_count == 1, f"Should have 1 MeshCore packet, got {meshcore_count}"
        print("   ✅ MeshCore packet in 'meshcore_packets' table")
        
        # Verify message content
        print("\n5️⃣ Verifying packet content...")
        cursor.execute("SELECT message, source FROM packets WHERE from_id='305419896'")  # 0x12345678
        meshtastic_msg = cursor.fetchone()
        assert meshtastic_msg[0] == 'Meshtastic message', "Meshtastic message content incorrect"
        assert meshtastic_msg[1] == 'local', "Meshtastic source should be 'local'"
        print(f"   ✅ Meshtastic packet: '{meshtastic_msg[0]}' (source: {meshtastic_msg[1]})")
        
        cursor.execute("SELECT message, source FROM meshcore_packets WHERE from_id='2271560481'")  # 0x87654321
        meshcore_msg = cursor.fetchone()
        assert meshcore_msg[0] == 'MeshCore message', "MeshCore message content incorrect"
        assert meshcore_msg[1] == 'meshcore', "MeshCore source should be 'meshcore'"
        print(f"   ✅ MeshCore packet: '{meshcore_msg[0]}' (source: {meshcore_msg[1]})")
        
        conn.close()
        
        print("\n✅ SEPARATION TEST PASSED!")
        print("   • Meshtastic packets stored in 'packets' table")
        print("   • MeshCore packets stored in 'meshcore_packets' table")
        print("   • No mixing between tables")
        
        # Cleanup
        os.remove(db_path)
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_migration():
    """Test migration of existing meshcore packets from packets to meshcore_packets"""
    print("\n" + "="*70)
    print("TEST: Migration of Existing MeshCore Packets")
    print("="*70)
    
    # Use temp database
    db_path = '/tmp/test_migration.db'
    if os.path.exists(db_path):
        os.remove(db_path)
    
    print(f"\n📁 Creating test database with mixed packets: {db_path}")
    
    try:
        # Create database and manually insert mixed packets (simulating old database)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create old-style packets table
        cursor.execute('''
            CREATE TABLE packets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                from_id TEXT NOT NULL,
                to_id TEXT,
                source TEXT,
                sender_name TEXT,
                packet_type TEXT NOT NULL,
                message TEXT,
                rssi INTEGER,
                snr REAL,
                hops INTEGER,
                size INTEGER,
                is_broadcast INTEGER,
                is_encrypted INTEGER DEFAULT 0,
                telemetry TEXT,
                position TEXT,
                hop_limit INTEGER,
                hop_start INTEGER,
                channel INTEGER DEFAULT 0,
                via_mqtt INTEGER DEFAULT 0,
                want_ack INTEGER DEFAULT 0,
                want_response INTEGER DEFAULT 0,
                priority INTEGER DEFAULT 0,
                family TEXT,
                public_key TEXT
            )
        ''')
        
        # Insert mixed packets (old database state)
        print("\n1️⃣ Inserting mixed packets (simulating old database)...")
        cursor.execute('''
            INSERT INTO packets (timestamp, from_id, to_id, source, sender_name, packet_type, message, rssi, snr, hops, size, is_broadcast, is_encrypted)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (time.time(), '305419896', '4294967295', 'local', 'Node1', 'TEXT_MESSAGE_APP', 'Meshtastic 1', -90, 8.0, 1, 100, 1, 0))
        
        cursor.execute('''
            INSERT INTO packets (timestamp, from_id, to_id, source, sender_name, packet_type, message, rssi, snr, hops, size, is_broadcast, is_encrypted)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (time.time(), '2271560481', '4294967295', 'meshcore', 'Node2', 'TEXT_MESSAGE_APP', 'MeshCore 1', -85, 10.0, 0, 100, 1, 0))
        
        cursor.execute('''
            INSERT INTO packets (timestamp, from_id, to_id, source, sender_name, packet_type, message, rssi, snr, hops, size, is_broadcast, is_encrypted)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (time.time(), '305419897', '4294967295', 'tcp', 'Node3', 'TEXT_MESSAGE_APP', 'Meshtastic 2', -92, 7.5, 2, 100, 1, 0))
        
        cursor.execute('''
            INSERT INTO packets (timestamp, from_id, to_id, source, sender_name, packet_type, message, rssi, snr, hops, size, is_broadcast, is_encrypted)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (time.time(), '2271560482', '4294967295', 'meshcore', 'Node4', 'TEXT_MESSAGE_APP', 'MeshCore 2', -88, 9.0, 1, 100, 1, 0))
        
        conn.commit()
        
        # Verify mixed state
        cursor.execute("SELECT COUNT(*), source FROM packets GROUP BY source ORDER BY source")
        before_migration = cursor.fetchall()
        print(f"   Before migration: {before_migration}")
        
        conn.close()
        
        # Now initialize TrafficPersistence which should trigger migration
        print("\n2️⃣ Initializing TrafficPersistence (triggers migration)...")
        persistence = TrafficPersistence(db_path)
        
        # Verify migration
        print("\n3️⃣ Verifying migration results...")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check packets table (should only have Meshtastic)
        cursor.execute("SELECT COUNT(*), source FROM packets GROUP BY source ORDER BY source")
        packets_after = cursor.fetchall()
        print(f"   packets table after: {packets_after}")
        
        # Should have 2 Meshtastic packets ('local' and 'tcp')
        cursor.execute("SELECT COUNT(*) FROM packets")
        meshtastic_total = cursor.fetchone()[0]
        assert meshtastic_total == 2, f"Should have 2 Meshtastic packets, got {meshtastic_total}"
        print("   ✅ 2 Meshtastic packets remain in 'packets'")
        
        # Should have 0 meshcore packets
        cursor.execute("SELECT COUNT(*) FROM packets WHERE source='meshcore'")
        meshcore_remain = cursor.fetchone()[0]
        assert meshcore_remain == 0, f"Should have 0 MeshCore packets in 'packets', got {meshcore_remain}"
        print("   ✅ 0 MeshCore packets in 'packets'")
        
        # Check meshcore_packets table (should have 2 meshcore)
        cursor.execute("SELECT COUNT(*), source FROM meshcore_packets GROUP BY source ORDER BY source")
        meshcore_after = cursor.fetchall()
        print(f"   meshcore_packets table: {meshcore_after}")
        
        cursor.execute("SELECT COUNT(*) FROM meshcore_packets")
        meshcore_total = cursor.fetchone()[0]
        assert meshcore_total == 2, f"Should have 2 MeshCore packets, got {meshcore_total}"
        print("   ✅ 2 MeshCore packets migrated to 'meshcore_packets'")
        
        # Verify message content
        cursor.execute("SELECT message FROM packets ORDER BY message")
        meshtastic_messages = [row[0] for row in cursor.fetchall()]
        assert 'Meshtastic 1' in meshtastic_messages, "Meshtastic 1 should be in packets"
        assert 'Meshtastic 2' in meshtastic_messages, "Meshtastic 2 should be in packets"
        print(f"   ✅ Meshtastic messages: {meshtastic_messages}")
        
        cursor.execute("SELECT message FROM meshcore_packets ORDER BY message")
        meshcore_messages = [row[0] for row in cursor.fetchall()]
        assert 'MeshCore 1' in meshcore_messages, "MeshCore 1 should be in meshcore_packets"
        assert 'MeshCore 2' in meshcore_messages, "MeshCore 2 should be in meshcore_packets"
        print(f"   ✅ MeshCore messages: {meshcore_messages}")
        
        conn.close()
        
        print("\n✅ MIGRATION TEST PASSED!")
        print("   • Old MeshCore packets migrated successfully")
        print("   • Meshtastic packets remained in place")
        print("   • Tables properly separated")
        
        # Cleanup
        os.remove(db_path)
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("="*70)
    print("MESHCORE/MESHTASTIC SEPARATION TEST SUITE")
    print("="*70)
    
    all_passed = True
    
    # Run tests
    all_passed &= test_separate_tables()
    all_passed &= test_migration()
    
    # Summary
    print("\n" + "="*70)
    if all_passed:
        print("✅ ALL TESTS PASSED!")
        print("="*70)
        print("\n✨ Verification complete:")
        print("  • MeshCore and Meshtastic packets separated")
        print("  • New packets go to correct tables")
        print("  • Migration of existing data works")
        print("  • No mixing between tables")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        print("="*70)
        sys.exit(1)
