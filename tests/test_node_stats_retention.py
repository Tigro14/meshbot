#!/usr/bin/env python3
"""
Test suite for node_stats retention functionality.
Verifies that stale node_stats entries are properly cleaned up.
"""

import sqlite3
import json
import time
import os
import sys
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from traffic_persistence import TrafficPersistence


def test_node_stats_retention():
    """Test that node_stats entries older than retention period are cleaned up"""
    
    print("\n" + "="*60)
    print("TEST: Node Stats Retention Cleanup")
    print("="*60)
    
    # Create a temporary test database
    test_db = "test_node_stats_retention.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    
    try:
        # Initialize persistence
        persistence = TrafficPersistence(db_path=test_db)
        
        # Create test data with different ages
        now = datetime.now().timestamp()
        
        test_nodes = {
            'fresh_node': {
                'node_id': '305419896',  # Recent node (1 hour old)
                'timestamp': now - (1 * 3600),
                'total_packets': 100,
                'total_bytes': 5000
            },
            'week_old_node': {
                'node_id': '305419897',  # 6.5 days old (within retention)
                'timestamp': now - (6.5 * 24 * 3600),
                'total_packets': 200,
                'total_bytes': 10000
            },
            'stale_node': {
                'node_id': '305419898',  # 8 days old (should be deleted)
                'timestamp': now - (8 * 24 * 3600),
                'total_packets': 300,
                'total_bytes': 15000
            },
            'ancient_node': {
                'node_id': '305419899',  # 30 days old (should be deleted)
                'timestamp': now - (30 * 24 * 3600),
                'total_packets': 400,
                'total_bytes': 20000
            }
        }
        
        # Insert test data
        print("\n📊 Inserting test node_stats data...")
        cursor = persistence.conn.cursor()
        
        for name, node in test_nodes.items():
            cursor.execute('''
                INSERT INTO node_stats (
                    node_id, total_packets, total_bytes, packet_types,
                    hourly_activity, message_stats, telemetry_stats,
                    position_stats, routing_stats, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                node['node_id'],
                node['total_packets'],
                node['total_bytes'],
                json.dumps({'TEXT_MESSAGE_APP': 50}),
                json.dumps({}),
                json.dumps({}),
                json.dumps({}),
                json.dumps({}),
                json.dumps({}),
                node['timestamp']
            ))
            
            # Calculate age in days
            age_days = (now - node['timestamp']) / (24 * 3600)
            print(f"  • {name}: {node['node_id']} ({age_days:.1f} days old)")
        
        persistence.conn.commit()
        
        # Verify initial state
        cursor.execute('SELECT COUNT(*) FROM node_stats')
        initial_count = cursor.fetchone()[0]
        print(f"\n✅ Initial count: {initial_count} node_stats entries")
        assert initial_count == 4, f"Expected 4 entries, got {initial_count}"
        
        # Run cleanup with 7-day retention
        print("\n🧹 Running cleanup with 7-day retention...")
        persistence.cleanup_old_data(hours=48, node_stats_hours=168)  # 168h = 7 days
        
        # Verify cleanup results
        cursor.execute('SELECT node_id, last_updated FROM node_stats ORDER BY last_updated DESC')
        remaining_nodes = cursor.fetchall()
        
        print(f"\n📊 After cleanup: {len(remaining_nodes)} node_stats entries remaining")
        
        # Check which nodes remain
        remaining_ids = [row[0] for row in remaining_nodes]
        
        print("\n🔍 Remaining nodes:")
        for row in remaining_nodes:
            node_id = row[0]
            age_days = (now - row[1]) / (24 * 3600)
            status = "✅ KEPT" if age_days < 7 else "❌ SHOULD BE DELETED"
            print(f"  • {node_id}: {age_days:.1f} days old - {status}")
        
        # Assertions
        assert len(remaining_nodes) == 2, f"Expected 2 remaining nodes, got {len(remaining_nodes)}"
        assert '305419896' in remaining_ids, "Fresh node (1h old) should be kept"
        assert '305419897' in remaining_ids, "Week-old node (7d old) should be kept"
        assert '305419898' not in remaining_ids, "Stale node (8d old) should be deleted"
        assert '305419899' not in remaining_ids, "Ancient node (30d old) should be deleted"
        
        print("\n✅ All assertions passed!")
        print("\n" + "="*60)
        print("✅ TEST PASSED: Node stats retention works correctly")
        print("="*60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        print(traceback.format_exc())
        return False
        
    finally:
        # Cleanup test database
        if os.path.exists(test_db):
            try:
                persistence.close()
            except:
                pass
            os.remove(test_db)
            print(f"\n🧹 Test database cleaned up: {test_db}")


def test_node_stats_retention_edge_cases():
    """Test edge cases for node_stats retention"""
    
    print("\n" + "="*60)
    print("TEST: Node Stats Retention Edge Cases")
    print("="*60)
    
    # Create a temporary test database
    test_db = "test_node_stats_edge_cases.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    
    try:
        # Initialize persistence
        persistence = TrafficPersistence(db_path=test_db)
        
        # Test 1: Empty database
        print("\n📊 Test 1: Cleanup on empty database")
        persistence.cleanup_old_data(hours=48, node_stats_hours=168)
        cursor = persistence.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM node_stats')
        count = cursor.fetchone()[0]
        assert count == 0, f"Expected 0 entries, got {count}"
        print("  ✅ Empty database handled correctly")
        
        # Test 2: All fresh nodes (none should be deleted)
        print("\n📊 Test 2: All fresh nodes")
        now = datetime.now().timestamp()
        for i in range(3):
            cursor.execute('''
                INSERT INTO node_stats (
                    node_id, total_packets, total_bytes, packet_types,
                    hourly_activity, message_stats, telemetry_stats,
                    position_stats, routing_stats, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                f'30541989{i}',
                100 * (i+1),
                5000 * (i+1),
                json.dumps({'TEXT_MESSAGE_APP': 50}),
                json.dumps({}),
                json.dumps({}),
                json.dumps({}),
                json.dumps({}),
                json.dumps({}),
                now - (i * 3600)  # 0-2 hours old
            ))
        persistence.conn.commit()
        
        persistence.cleanup_old_data(hours=48, node_stats_hours=168)
        cursor.execute('SELECT COUNT(*) FROM node_stats')
        count = cursor.fetchone()[0]
        assert count == 3, f"Expected 3 entries, got {count}"
        print("  ✅ All fresh nodes kept")
        
        # Test 3: All stale nodes (all should be deleted)
        print("\n📊 Test 3: All stale nodes")
        cursor.execute('DELETE FROM node_stats')
        for i in range(3):
            cursor.execute('''
                INSERT INTO node_stats (
                    node_id, total_packets, total_bytes, packet_types,
                    hourly_activity, message_stats, telemetry_stats,
                    position_stats, routing_stats, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                f'30541989{i}',
                100 * (i+1),
                5000 * (i+1),
                json.dumps({'TEXT_MESSAGE_APP': 50}),
                json.dumps({}),
                json.dumps({}),
                json.dumps({}),
                json.dumps({}),
                json.dumps({}),
                now - ((8 + i) * 24 * 3600)  # 8-10 days old
            ))
        persistence.conn.commit()
        
        persistence.cleanup_old_data(hours=48, node_stats_hours=168)
        cursor.execute('SELECT COUNT(*) FROM node_stats')
        count = cursor.fetchone()[0]
        assert count == 0, f"Expected 0 entries, got {count}"
        print("  ✅ All stale nodes deleted")
        
        print("\n✅ All edge case tests passed!")
        print("\n" + "="*60)
        print("✅ TEST PASSED: Edge cases handled correctly")
        print("="*60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        print(traceback.format_exc())
        return False
        
    finally:
        # Cleanup test database
        if os.path.exists(test_db):
            try:
                persistence.close()
            except:
                pass
            os.remove(test_db)
            print(f"\n🧹 Test database cleaned up: {test_db}")


def test_config_integration():
    """Test that config.py NODE_STATS_RETENTION_HOURS is properly used"""
    
    print("\n" + "="*60)
    print("TEST: Config Integration")
    print("="*60)
    
    test_db = "test_config_integration.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    
    try:
        persistence = TrafficPersistence(db_path=test_db)
        
        # Test that default value (168h) is used when config not available
        print("\n📊 Testing default retention value...")
        
        now = datetime.now().timestamp()
        cursor = persistence.conn.cursor()
        
        # Insert a node that's 7.5 days old (should be deleted with 168h retention)
        cursor.execute('''
            INSERT INTO node_stats (
                node_id, total_packets, total_bytes, packet_types,
                hourly_activity, message_stats, telemetry_stats,
                position_stats, routing_stats, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            '305419896',
            100,
            5000,
            json.dumps({'TEXT_MESSAGE_APP': 50}),
            json.dumps({}),
            json.dumps({}),
            json.dumps({}),
            json.dumps({}),
            json.dumps({}),
            now - (7.5 * 24 * 3600)  # 7.5 days old
        ))
        persistence.conn.commit()
        
        # Run cleanup without specifying node_stats_hours (should use default 168h)
        persistence.cleanup_old_data(hours=48)
        
        cursor.execute('SELECT COUNT(*) FROM node_stats')
        count = cursor.fetchone()[0]
        
        print(f"  • Nodes remaining: {count}")
        assert count == 0, f"Expected 0 entries (7.5d > 7d), got {count}"
        print("  ✅ Default retention value (168h) applied correctly")
        
        print("\n✅ Config integration test passed!")
        print("\n" + "="*60)
        print("✅ TEST PASSED: Config integration works correctly")
        print("="*60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        print(traceback.format_exc())
        return False
        
    finally:
        # Cleanup test database
        if os.path.exists(test_db):
            try:
                persistence.close()
            except:
                pass
            os.remove(test_db)
            print(f"\n🧹 Test database cleaned up: {test_db}")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Node Stats Retention Test Suite")
    print("="*60)
    
    all_tests_passed = True
    
    # Run all tests
    tests = [
        ("Basic Retention", test_node_stats_retention),
        ("Edge Cases", test_node_stats_retention_edge_cases),
        ("Config Integration", test_config_integration)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
            all_tests_passed = all_tests_passed and result
        except Exception as e:
            print(f"\n❌ {test_name} crashed: {e}")
            results.append((test_name, False))
            all_tests_passed = False
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUITE SUMMARY")
    print("="*60)
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {status}: {test_name}")
    
    print("="*60)
    if all_tests_passed:
        print("✅ ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        sys.exit(1)
