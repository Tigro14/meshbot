#!/usr/bin/env python3
"""
Test script to verify the save_packet fix for hop_limit and hop_start fields.
Tests that packets with these fields can be saved without errors.
"""

import os
import sys
import sqlite3
import tempfile

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Create a minimal config module for testing
class MockConfig:
    DEBUG_MODE = False

sys.modules['config'] = MockConfig()

from traffic_persistence import TrafficPersistence


def test_save_packet_with_hop_fields():
    """Test that save_packet works with hop_limit and hop_start fields."""
    
    # Create a temporary database
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name
    
    try:
        print("Creating TrafficPersistence with new database...")
        persistence = TrafficPersistence(db_path=db_path)
        
        # Create a test packet with all fields including hop_limit and hop_start
        test_packet = {
            'timestamp': 1234567890.123,
            'from_id': '!12345678',
            'to_id': '^all',
            'source': 'local',
            'sender_name': 'TestNode',
            'packet_type': 'TEXT_MESSAGE_APP',
            'message': 'Test message',
            'rssi': -100,
            'snr': 5.5,
            'hops': 1,
            'size': 50,
            'is_broadcast': True,
            'is_encrypted': False,
            'telemetry': None,
            'position': None,
            'hop_limit': 3,  # This field was causing the error
            'hop_start': 3   # This field was causing the error
        }
        
        print("\nSaving test packet with hop_limit and hop_start...")
        persistence.save_packet(test_packet)
        print("✅ Packet saved successfully!")
        
        # Verify the packet was saved
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM packets")
        rows = cursor.fetchall()
        
        print(f"\n📊 Database contains {len(rows)} packet(s)")
        
        if len(rows) > 0:
            # Verify columns exist
            cursor.execute("PRAGMA table_info(packets)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            print(f"📋 Table columns: {', '.join(column_names)}")
            
            if 'hop_limit' in column_names and 'hop_start' in column_names:
                print("✅ hop_limit and hop_start columns exist")
                
                # Verify the data
                cursor.execute("SELECT hop_limit, hop_start FROM packets WHERE id = 1")
                row = cursor.fetchone()
                if row:
                    hop_limit, hop_start = row
                    print(f"✅ Saved values: hop_limit={hop_limit}, hop_start={hop_start}")
                    
                    if hop_limit == 3 and hop_start == 3:
                        print("\n🎉 SUCCESS: All tests passed!")
                        return True
                    else:
                        print(f"\n❌ FAIL: Expected hop_limit=3, hop_start=3, got {hop_limit}, {hop_start}")
                        return False
            else:
                print("❌ hop_limit or hop_start column missing")
                return False
        else:
            print("❌ No packets found in database")
            return False
        
        conn.close()
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.remove(db_path)
            print(f"\n🗑️  Cleaned up test database: {db_path}")


def test_migration_existing_db():
    """Test that migration code still works for existing databases."""
    
    # Create a temporary database with old schema (without hop_limit/hop_start)
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name
    
    try:
        print("\n" + "="*60)
        print("Testing migration for existing database...")
        print("="*60)
        
        # Create old schema manually
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
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
                position TEXT
            )
        ''')
        conn.commit()
        
        # Check columns before migration
        cursor.execute("PRAGMA table_info(packets)")
        columns_before = [col[1] for col in cursor.fetchall()]
        print(f"Columns before migration: {', '.join(columns_before)}")
        
        conn.close()
        
        # Now open with TrafficPersistence (should trigger migration)
        print("\nOpening database with TrafficPersistence (should trigger migration)...")
        persistence = TrafficPersistence(db_path=db_path)
        
        # Check columns after migration
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(packets)")
        columns_after = [col[1] for col in cursor.fetchall()]
        print(f"Columns after migration: {', '.join(columns_after)}")
        
        if 'hop_limit' in columns_after and 'hop_start' in columns_after:
            print("✅ Migration added hop_limit and hop_start columns")
            
            # Try to save a packet
            test_packet = {
                'timestamp': 1234567890.456,
                'from_id': '!87654321',
                'to_id': '^all',
                'source': 'local',
                'sender_name': 'MigratedNode',
                'packet_type': 'POSITION_APP',
                'message': None,
                'rssi': -95,
                'snr': 7.2,
                'hops': 2,
                'size': 40,
                'is_broadcast': True,
                'is_encrypted': False,
                'telemetry': None,
                'position': None,
                'hop_limit': 5,
                'hop_start': 5
            }
            
            print("\nSaving packet to migrated database...")
            persistence.save_packet(test_packet)
            print("✅ Packet saved successfully to migrated database!")
            
            print("\n🎉 SUCCESS: Migration test passed!")
            return True
        else:
            print("❌ Migration failed to add columns")
            return False
        
        conn.close()
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.remove(db_path)
            print(f"\n🗑️  Cleaned up test database: {db_path}")


if __name__ == "__main__":
    print("="*60)
    print("Testing save_packet fix for hop_limit and hop_start")
    print("="*60)
    
    # Test 1: New database with updated schema
    test1_passed = test_save_packet_with_hop_fields()
    
    # Test 2: Migration of existing database
    test2_passed = test_migration_existing_db()
    
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    print(f"Test 1 (New database):      {'✅ PASS' if test1_passed else '❌ FAIL'}")
    print(f"Test 2 (Database migration): {'✅ PASS' if test2_passed else '❌ FAIL'}")
    
    if test1_passed and test2_passed:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed")
        sys.exit(1)
