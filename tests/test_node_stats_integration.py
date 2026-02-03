#!/usr/bin/env python3
"""
Integration test for node_stats retention with the full cleanup chain.
Tests the complete flow: TrafficMonitor -> TrafficPersistence -> cleanup
"""

import sqlite3
import json
import time
import os
import sys
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from traffic_monitor import TrafficMonitor
from node_manager import NodeManager


def test_integration():
    """Test the complete cleanup chain for node_stats"""
    
    print("\n" + "="*60)
    print("INTEGRATION TEST: Node Stats Retention via TrafficMonitor")
    print("="*60)
    
    # Create temporary test database
    test_db = "test_integration_node_stats.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    
    # Create a temporary node_names.json for NodeManager
    test_node_names = "test_node_names.json"
    with open(test_node_names, 'w') as f:
        json.dump({}, f)
    
    try:
        # Initialize NodeManager and TrafficMonitor (mimics main_bot.py)
        print("\n📊 Initializing TrafficMonitor with test database...")
        node_manager = NodeManager()
        
        # Initialize TrafficMonitor with test database
        traffic_monitor = TrafficMonitor(node_manager)
        traffic_monitor.persistence.db_path = test_db
        traffic_monitor.persistence._init_database()
        
        print(f"✅ TrafficMonitor initialized with DB: {test_db}")
        
        # Create test node_stats with different ages
        now = datetime.now().timestamp()
        cursor = traffic_monitor.persistence.conn.cursor()
        
        test_nodes = [
            ('305419896', now - (1 * 3600), 100, "fresh"),      # 1h old
            ('305419897', now - (3 * 24 * 3600), 200, "recent"),  # 3d old
            ('305419898', now - (8 * 24 * 3600), 300, "stale"),   # 8d old
        ]
        
        print("\n📊 Inserting test node_stats...")
        for node_id, timestamp, packets, label in test_nodes:
            cursor.execute('''
                INSERT INTO node_stats (
                    node_id, total_packets, total_bytes, packet_types,
                    hourly_activity, message_stats, telemetry_stats,
                    position_stats, routing_stats, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                node_id, packets, packets * 50,
                json.dumps({'TEXT_MESSAGE_APP': 50}),
                json.dumps({}), json.dumps({}), json.dumps({}),
                json.dumps({}), json.dumps({}), timestamp
            ))
            age_days = (now - timestamp) / (24 * 3600)
            print(f"  • {label}: {node_id} ({age_days:.1f} days old, {packets} packets)")
        
        traffic_monitor.persistence.conn.commit()
        
        # Verify initial state
        cursor.execute('SELECT COUNT(*) FROM node_stats')
        initial_count = cursor.fetchone()[0]
        print(f"\n✅ Initial count: {initial_count} node_stats entries")
        assert initial_count == 3, f"Expected 3 entries, got {initial_count}"
        
        # Test the cleanup chain (mimics main_bot.py periodic cleanup)
        print("\n🧹 Running cleanup via TrafficMonitor.cleanup_old_persisted_data()...")
        print("   (This simulates the periodic cleanup in main_bot.py)")
        
        # Call cleanup via TrafficMonitor (same as main_bot.py does)
        # Note: hours parameter is for packets/neighbors, node_stats uses config
        traffic_monitor.cleanup_old_persisted_data(hours=48)
        
        # Verify cleanup results
        cursor.execute('SELECT node_id, last_updated FROM node_stats ORDER BY last_updated DESC')
        remaining_nodes = cursor.fetchall()
        
        print(f"\n📊 After cleanup: {len(remaining_nodes)} node_stats entries remaining")
        
        # Check results
        remaining_ids = [row[0] for row in remaining_nodes]
        
        print("\n🔍 Remaining nodes:")
        for row in remaining_nodes:
            node_id = row[0]
            age_days = (now - row[1]) / (24 * 3600)
            status = "✅ KEPT" if age_days < 7 else "❌ UNEXPECTED"
            print(f"  • {node_id}: {age_days:.1f} days old - {status}")
        
        # Assertions
        assert len(remaining_nodes) == 2, f"Expected 2 remaining nodes, got {len(remaining_nodes)}"
        assert '305419896' in remaining_ids, "Fresh node (1h) should be kept"
        assert '305419897' in remaining_ids, "Recent node (3d) should be kept"
        assert '305419898' not in remaining_ids, "Stale node (8d) should be deleted"
        
        print("\n✅ All assertions passed!")
        print("\n" + "="*60)
        print("✅ INTEGRATION TEST PASSED")
        print("="*60)
        print("\n💡 The cleanup chain works correctly:")
        print("   TrafficMonitor.cleanup_old_persisted_data()")
        print("   └─> TrafficPersistence.cleanup_old_data()")
        print("       └─> DELETE FROM node_stats WHERE last_updated < cutoff")
        
        return True
        
    except Exception as e:
        print(f"\n❌ INTEGRATION TEST FAILED: {e}")
        import traceback
        print(traceback.format_exc())
        return False
        
    finally:
        # Cleanup
        try:
            traffic_monitor.persistence.close()
        except:
            pass
        
        if os.path.exists(test_db):
            os.remove(test_db)
            print(f"\n🧹 Test database cleaned up: {test_db}")
        
        if os.path.exists(test_node_names):
            os.remove(test_node_names)
            print(f"🧹 Test node_names cleaned up: {test_node_names}")


if __name__ == "__main__":
    success = test_integration()
    sys.exit(0 if success else 1)
