#!/usr/bin/env python3
"""
Test intelligent public key synchronization that skips redundant syncs

This tests the optimization where periodic sync intelligently skips
when all keys are already present in interface.nodes, while still
forcing full sync at startup and after reconnection.
"""

import sys
import os
import json
import tempfile
from unittest.mock import Mock, MagicMock

def test_forced_sync_at_startup():
    """Test that force=True always performs full sync (startup scenario)"""
    print("\n" + "="*70)
    print("TEST 1: Forced Sync at Startup (force=True)")
    print("="*70)
    
    # Mock config
    class MockConfig:
        NODE_NAMES_FILE = tempfile.mktemp(suffix='.json')
        DEBUG_MODE = True
    
    sys.modules['config'] = MockConfig()
    
    from node_manager import NodeManager
    
    # Create node manager
    nm = NodeManager()
    
    # Add some keys to database
    nm.node_names[0x433e38ec] = {
        'name': '14FRS3278',
        'publicKey': 'ABC123KEY1',
        'lat': None,
        'lon': None,
        'alt': None
    }
    nm.node_names[0x16fad3dc] = {
        'name': 'tigro t1000E',
        'publicKey': 'DEF456KEY2',
        'lat': None,
        'lon': None,
        'alt': None
    }
    
    print(f"Database: {len(nm.node_names)} nodes with keys")
    
    # Create empty interface (startup scenario)
    mock_interface = Mock()
    mock_interface.nodes = {}
    
    print("\nScenario: Bot startup with empty interface.nodes")
    print(f"interface.nodes: {len(mock_interface.nodes)} nodes")
    
    # Call with force=True (as done at startup)
    injected = nm.sync_pubkeys_to_interface(mock_interface, force=True)
    
    print(f"\nResult: {injected} keys injected")
    print(f"interface.nodes now has: {len(mock_interface.nodes)} nodes")
    
    assert injected == 2, f"Expected 2 keys injected, got {injected}"
    assert len(mock_interface.nodes) == 2, "interface.nodes should have 2 nodes"
    
    print("✅ Forced sync works correctly at startup")


def test_skip_when_all_keys_present():
    """Test that force=False skips when all keys already present (periodic scenario)"""
    print("\n" + "="*70)
    print("TEST 2: Skip Sync When All Keys Present (force=False)")
    print("="*70)
    
    # Mock config
    class MockConfig:
        NODE_NAMES_FILE = tempfile.mktemp(suffix='.json')
        DEBUG_MODE = True
    
    sys.modules['config'] = MockConfig()
    
    from node_manager import NodeManager
    
    # Create node manager
    nm = NodeManager()
    
    # Add keys to database
    nm.node_names[0x433e38ec] = {
        'name': '14FRS3278',
        'publicKey': 'ABC123KEY1',
        'lat': None,
        'lon': None,
        'alt': None
    }
    nm.node_names[0x16fad3dc] = {
        'name': 'tigro t1000E',
        'publicKey': 'DEF456KEY2',
        'lat': None,
        'lon': None,
        'alt': None
    }
    
    # Create interface with keys already present
    mock_interface = Mock()
    mock_interface.nodes = {
        0x433e38ec: {
            'num': 0x433e38ec,
            'user': {
                'longName': '14FRS3278',
                'publicKey': 'ABC123KEY1'
            }
        },
        0x16fad3dc: {
            'num': 0x16fad3dc,
            'user': {
                'longName': 'tigro t1000E',
                'publicKey': 'DEF456KEY2'
            }
        }
    }
    
    print(f"Database: {len(nm.node_names)} nodes with keys")
    print(f"interface.nodes: {len(mock_interface.nodes)} nodes with keys")
    print("\nScenario: Periodic sync with all keys already present")
    
    # Call with force=False (as done in periodic cleanup)
    injected = nm.sync_pubkeys_to_interface(mock_interface, force=False)
    
    print(f"\nResult: {injected} keys injected")
    
    assert injected == 0, f"Expected 0 keys injected (skip), got {injected}"
    
    print("✅ Periodic sync correctly skipped when all keys present")


def test_sync_when_keys_missing():
    """Test that force=False syncs when keys are missing"""
    print("\n" + "="*70)
    print("TEST 3: Sync When Keys Missing (force=False)")
    print("="*70)
    
    # Mock config
    class MockConfig:
        NODE_NAMES_FILE = tempfile.mktemp(suffix='.json')
        DEBUG_MODE = True
    
    sys.modules['config'] = MockConfig()
    
    from node_manager import NodeManager
    
    # Create node manager
    nm = NodeManager()
    
    # Add keys to database
    nm.node_names[0x433e38ec] = {
        'name': '14FRS3278',
        'publicKey': 'ABC123KEY1',
        'lat': None,
        'lon': None,
        'alt': None
    }
    nm.node_names[0x16fad3dc] = {
        'name': 'tigro t1000E',
        'publicKey': 'DEF456KEY2',
        'lat': None,
        'lon': None,
        'alt': None
    }
    nm.node_names[0x12345678] = {
        'name': 'NewNode',
        'publicKey': 'GHI789KEY3',
        'lat': None,
        'lon': None,
        'alt': None
    }
    
    # Create interface with only 2 keys (missing the 3rd)
    mock_interface = Mock()
    mock_interface.nodes = {
        0x433e38ec: {
            'num': 0x433e38ec,
            'user': {
                'longName': '14FRS3278',
                'publicKey': 'ABC123KEY1'
            }
        },
        0x16fad3dc: {
            'num': 0x16fad3dc,
            'user': {
                'longName': 'tigro t1000E',
                'publicKey': 'DEF456KEY2'
            }
        }
    }
    
    print(f"Database: {len(nm.node_names)} nodes with keys")
    print(f"interface.nodes: {len(mock_interface.nodes)} nodes (missing 1 key)")
    print("\nScenario: Periodic sync with 1 key missing")
    
    # Call with force=False - should detect missing key and sync
    injected = nm.sync_pubkeys_to_interface(mock_interface, force=False)
    
    print(f"\nResult: {injected} keys injected")
    print(f"interface.nodes now has: {len(mock_interface.nodes)} nodes")
    
    assert injected >= 1, f"Expected at least 1 key injected, got {injected}"
    assert len(mock_interface.nodes) == 3, "interface.nodes should have 3 nodes"
    
    print("✅ Periodic sync correctly detected and synced missing key")


def test_skip_when_no_keys_in_database():
    """Test that sync skips when database has no keys"""
    print("\n" + "="*70)
    print("TEST 4: Skip When No Keys in Database")
    print("="*70)
    
    # Mock config
    class MockConfig:
        NODE_NAMES_FILE = tempfile.mktemp(suffix='.json')
        DEBUG_MODE = True
    
    sys.modules['config'] = MockConfig()
    
    from node_manager import NodeManager
    
    # Create node manager with empty database
    nm = NodeManager()
    
    # Create interface
    mock_interface = Mock()
    mock_interface.nodes = {}
    
    print("Database: 0 nodes with keys")
    print("interface.nodes: 0 nodes")
    print("\nScenario: Periodic sync with no keys in database")
    
    # Call with force=False - should skip immediately
    injected = nm.sync_pubkeys_to_interface(mock_interface, force=False)
    
    print(f"\nResult: {injected} keys injected")
    
    assert injected == 0, f"Expected 0 keys injected (skip), got {injected}"
    
    print("✅ Correctly skipped when no keys in database")


def test_forced_sync_after_reconnection():
    """Test that force=True works after TCP reconnection"""
    print("\n" + "="*70)
    print("TEST 5: Forced Sync After TCP Reconnection (force=True)")
    print("="*70)
    
    # Mock config
    class MockConfig:
        NODE_NAMES_FILE = tempfile.mktemp(suffix='.json')
        DEBUG_MODE = True
    
    sys.modules['config'] = MockConfig()
    
    from node_manager import NodeManager
    
    # Create node manager
    nm = NodeManager()
    
    # Add keys to database (from previous connection)
    nm.node_names[0x433e38ec] = {
        'name': '14FRS3278',
        'publicKey': 'ABC123KEY1',
        'lat': None,
        'lon': None,
        'alt': None
    }
    nm.node_names[0x16fad3dc] = {
        'name': 'tigro t1000E',
        'publicKey': 'DEF456KEY2',
        'lat': None,
        'lon': None,
        'alt': None
    }
    
    print(f"Database: {len(nm.node_names)} nodes with keys (from previous session)")
    
    # Simulate new interface after reconnection (empty)
    new_interface = Mock()
    new_interface.nodes = {}
    
    print("New interface after reconnection: 0 nodes")
    print("\nScenario: TCP reconnection with new empty interface")
    
    # Call with force=True (as done after reconnection)
    injected = nm.sync_pubkeys_to_interface(new_interface, force=True)
    
    print(f"\nResult: {injected} keys injected")
    print(f"New interface.nodes now has: {len(new_interface.nodes)} nodes")
    
    assert injected == 2, f"Expected 2 keys injected, got {injected}"
    assert len(new_interface.nodes) == 2, "New interface.nodes should have 2 nodes"
    
    print("✅ Forced sync works correctly after reconnection")


if __name__ == '__main__':
    print("="*70)
    print("Testing Intelligent Public Key Synchronization")
    print("="*70)
    
    try:
        test_forced_sync_at_startup()
        test_skip_when_all_keys_present()
        test_sync_when_keys_missing()
        test_skip_when_no_keys_in_database()
        test_forced_sync_after_reconnection()
        
        print("\n" + "="*70)
        print("✅ ALL TESTS PASSED")
        print("="*70)
        print("\nSummary:")
        print("• Forced sync (startup/reconnect) always works ✓")
        print("• Periodic sync skips when all keys present ✓")
        print("• Periodic sync detects missing keys ✓")
        print("• Early exit when no keys in database ✓")
        print("\nBenefits:")
        print("• Reduced log spam from 'No new keys' messages")
        print("• More efficient periodic cleanup cycle")
        print("• Safety net still active when keys missing")
        print("• Startup/reconnection always full sync")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
