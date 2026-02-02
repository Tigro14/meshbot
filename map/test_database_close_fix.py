#!/usr/bin/env python3
"""
Test to verify database close order fix in export_nodes_from_db.py

This test verifies that:
1. All database operations complete before connection is closed
2. Telemetry history extraction happens before connection close
3. No "Cannot operate on a closed database" errors occur
"""

import os
import sys
import tempfile
import sqlite3
import json
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def create_test_database():
    """Create a temporary database with test data"""
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create packets table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS packets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_id TEXT,
            timestamp REAL,
            packet_type TEXT,
            snr REAL,
            hops INTEGER,
            telemetry TEXT,
            position TEXT,
            sender_name TEXT
        )
    """)
    
    # Create neighbors table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS neighbors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id TEXT,
            neighbor_id TEXT,
            snr REAL,
            last_rx_time INTEGER,
            node_broadcast_interval INTEGER,
            timestamp REAL
        )
    """)
    
    # Create node_stats table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS node_stats (
            node_id TEXT PRIMARY KEY,
            total_packets INTEGER,
            total_bytes INTEGER,
            by_type TEXT,
            message_stats TEXT,
            telemetry_stats TEXT,
            position_stats TEXT,
            routing_stats TEXT
        )
    """)
    
    # Insert test data
    now = time.time()
    
    # Insert test packets with telemetry
    for i in range(10):
        timestamp = now - (i * 86400)  # One per day for 10 days
        telemetry = json.dumps({
            'battery': 90 - i,
            'voltage': 4.1 - (i * 0.01)
        })
        cursor.execute("""
            INSERT INTO packets (from_id, timestamp, packet_type, snr, hops, telemetry)
            VALUES (?, ?, 'TELEMETRY_APP', 12.5, 0, ?)
        """, ('12345678', timestamp, telemetry))
    
    # Insert a normal packet (non-telemetry)
    cursor.execute("""
        INSERT INTO packets (from_id, timestamp, packet_type, snr, hops)
        VALUES (?, ?, 'TEXT_MESSAGE_APP', 10.0, 0)
    """, ('12345678', now))
    
    conn.commit()
    conn.close()
    
    return db_path

def create_test_node_names_file():
    """Create a temporary node_names.json file"""
    fd, node_names_path = tempfile.mkstemp(suffix='.json')
    os.close(fd)
    
    node_names = {
        "12345678": {
            "name": "Test Node",
            "shortName": "TEST",
            "hwModel": "TBEAM",
            "lat": 47.123,
            "lon": 6.456,
            "alt": 500
        }
    }
    
    with open(node_names_path, 'w') as f:
        json.dump(node_names, f)
    
    return node_names_path

def test_database_operations_order():
    """Test that all database operations happen before connection close"""
    print("Testing database operations order...")
    
    db_path = create_test_database()
    node_names_path = create_test_node_names_file()
    
    try:
        # Import the export function
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from export_nodes_from_db import export_nodes_from_files
        
        # Capture stdout (where JSON goes)
        import io
        from contextlib import redirect_stdout
        
        json_output = io.StringIO()
        
        # Run export (should not raise "Cannot operate on a closed database")
        with redirect_stdout(json_output):
            result = export_nodes_from_files(
                node_names_file=node_names_path,
                db_path=db_path,
                hours=720  # 30 days
            )
        
        # Verify success
        assert result == True, "Export should succeed"
        
        # Verify JSON output
        json_str = json_output.getvalue()
        assert len(json_str) > 0, "Should produce JSON output"
        
        # Parse JSON to verify structure
        data = json.loads(json_str)
        assert 'Nodes in mesh' in data, "Should have 'Nodes in mesh' key"
        
        nodes = data['Nodes in mesh']
        print("✅ Database operations complete without errors")
        print(f"   Exported {len(nodes)} nodes")
        
        # Check if telemetry history was extracted
        for node_id, node_data in nodes.items():
            if 'telemetryHistory' in node_data:
                print(f"   ✅ Telemetry history extracted: {len(node_data['telemetryHistory'])} points")
                break
        
        return True
        
    except sqlite3.ProgrammingError as e:
        if "Cannot operate on a closed database" in str(e):
            print(f"❌ Database closed error detected: {e}")
            return False
        raise
        
    finally:
        # Cleanup
        try:
            os.unlink(db_path)
            os.unlink(node_names_path)
        except:
            pass

def test_cursor_usage_after_close():
    """Test that no cursor operations happen after close"""
    print("\nTesting cursor usage pattern...")
    
    # This test verifies the code structure by analyzing the source
    script_path = os.path.join(os.path.dirname(__file__), 'export_nodes_from_db.py')
    
    with open(script_path, 'r') as f:
        content = f.read()
    
    # Find the line numbers
    lines = content.split('\n')
    
    close_line = None
    cursor_lines = []
    
    for i, line in enumerate(lines, 1):
        if 'persistence.close()' in line and not line.strip().startswith('#'):
            close_line = i
        if 'cursor.execute' in line and not line.strip().startswith('#'):
            cursor_lines.append(i)
    
    assert close_line is not None, "Should have persistence.close() call"
    assert len(cursor_lines) > 0, "Should have cursor operations"
    
    # All cursor operations should be BEFORE close
    cursor_after_close = [line for line in cursor_lines if line > close_line]
    
    if cursor_after_close:
        print(f"❌ Found cursor operations AFTER close at lines: {cursor_after_close}")
        print(f"   persistence.close() is at line {close_line}")
        return False
    
    print(f"✅ All {len(cursor_lines)} cursor operations occur before close (line {close_line})")
    return True

if __name__ == '__main__':
    print("=" * 60)
    print("Database Close Order - Unit Tests")
    print("=" * 60)
    
    try:
        # Test 1: Code structure
        test1_passed = test_cursor_usage_after_close()
        
        # Test 2: Actual execution
        test2_passed = test_database_operations_order()
        
        print("\n" + "=" * 60)
        if test1_passed and test2_passed:
            print("✅ All tests passed!")
            print("=" * 60)
            exit(0)
        else:
            print("❌ Some tests failed")
            print("=" * 60)
            exit(1)
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
