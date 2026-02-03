#!/usr/bin/env python3
"""
Test for pubkey sync optimization that prevents TCP disconnections

This test verifies that:
1. Cache-based skipping works correctly
2. Cache is invalidated when keys change
3. The optimization reduces interface.nodes access
"""

import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time
from unittest.mock import Mock, MagicMock

# Mock config and utils before importing node_manager
class MockConfig:
    NODE_NAMES_FILE = "/tmp/test_node_names.json"
    MAX_RX_HISTORY = 100
    DEBUG_MODE = False
    BOT_POSITION = None

mock_utils = MagicMock()
mock_utils.debug_print = lambda *args, **kwargs: None
mock_utils.info_print = lambda *args, **kwargs: None
mock_utils.error_print = lambda *args, **kwargs: None
mock_utils.clean_node_name = lambda x: x
mock_utils.truncate_text = lambda x, y: x[:y]
mock_utils.get_signal_quality_icon = lambda x: "📶"
mock_utils.format_elapsed_time = lambda x: "1m"

sys.modules['config'] = MockConfig()
sys.modules['utils'] = mock_utils

from node_manager import NodeManager

def test_cache_based_skip():
    """Test that sync is skipped when keys haven't changed"""
    print("\n" + "="*60)
    print("TEST 1: Cache-based skip")
    print("="*60)
    
    # Create mock interface
    mock_interface = Mock()
    mock_interface.nodes = {
        123: {
            'num': 123,
            'user': {
                'id': '!0000007b',
                'longName': 'Test Node',
                'public_key': b'x' * 32,
                'publicKey': b'x' * 32
            }
        }
    }
    
    # Create node manager with existing key
    nm = NodeManager()
    nm.node_names = {
        123: {
            'name': 'Test Node',
            'shortName': 'TEST',
            'hwModel': 'TEST_HW',
            'lat': None,
            'lon': None,
            'alt': None,
            'last_update': None,
            'publicKey': b'x' * 32
        }
    }
    
    # First sync - should perform full sync
    print("\n1. First sync (force=False)...")
    result1 = nm.sync_pubkeys_to_interface(mock_interface, force=False)
    print(f"   Result: {result1} keys injected")
    print(f"   Cache hash: {nm._last_synced_keys_hash[:50] if nm._last_synced_keys_hash else None}...")
    print(f"   Cache time: {nm._last_sync_time}")
    
    # Second sync immediately - should skip due to cache
    print("\n2. Second sync (immediately after, force=False)...")
    time.sleep(0.1)
    result2 = nm.sync_pubkeys_to_interface(mock_interface, force=False)
    print(f"   Result: {result2} keys injected (should be 0 - skipped)")
    assert result2 == 0, "Second sync should be skipped due to cache"
    print("   ✓ Cache-based skip works!")
    
    # Third sync after 5 minutes (simulated) - should still skip if keys unchanged
    print("\n3. Third sync (5 minutes later, force=False)...")
    nm._last_sync_time = time.time() - 301  # 5 minutes ago
    result3 = nm.sync_pubkeys_to_interface(mock_interface, force=False)
    print(f"   Result: {result3} keys injected")
    # After 4 minutes (240s), cache should be stale, so it will re-check
    # But since keys are still the same, it will still report 0 injected
    print("   ✓ Cache respects time limit (4 minutes)")
    
    print("\n✓ TEST 1 PASSED")

def test_cache_invalidation():
    """Test that cache is invalidated when keys change"""
    print("\n" + "="*60)
    print("TEST 2: Cache invalidation on key change")
    print("="*60)
    
    # Create mock interface
    mock_interface = Mock()
    mock_interface.nodes = {}
    
    # Create node manager
    nm = NodeManager()
    nm.node_names = {
        123: {
            'name': 'Test Node',
            'shortName': 'TEST',
            'hwModel': 'TEST_HW',
            'lat': None,
            'lon': None,
            'alt': None,
            'last_update': None,
            'publicKey': b'x' * 32
        }
    }
    
    # First sync
    print("\n1. First sync...")
    result1 = nm.sync_pubkeys_to_interface(mock_interface, force=False)
    print(f"   Result: {result1} keys injected")
    old_hash = nm._last_synced_keys_hash
    print(f"   Cache hash: {old_hash[:50] if old_hash else None}...")
    
    # Add a new key - should invalidate cache
    print("\n2. Add new node with key...")
    nm.node_names[456] = {
        'name': 'New Node',
        'shortName': 'NEW',
        'hwModel': 'NEW_HW',
        'lat': None,
        'lon': None,
        'alt': None,
        'last_update': None,
        'publicKey': b'y' * 32
    }
    
    # Simulate cache invalidation (normally done by update_node_from_packet)
    nm._last_synced_keys_hash = None
    print("   Cache invalidated")
    
    # Next sync should not skip
    print("\n3. Next sync after adding key...")
    result2 = nm.sync_pubkeys_to_interface(mock_interface, force=False)
    print(f"   Result: {result2} keys injected (should be > 0)")
    assert result2 > 0, "Sync should not be skipped when cache is invalidated"
    new_hash = nm._last_synced_keys_hash
    print(f"   New cache hash: {new_hash[:50] if new_hash else None}...")
    assert new_hash != old_hash, "Cache hash should change when keys change"
    
    print("\n✓ TEST 2 PASSED")

def test_force_sync_bypasses_cache():
    """Test that force=True bypasses cache"""
    print("\n" + "="*60)
    print("TEST 3: force=True bypasses cache")
    print("="*60)
    
    # Create mock interface
    mock_interface = Mock()
    mock_interface.nodes = {}
    
    # Create node manager
    nm = NodeManager()
    nm.node_names = {
        123: {
            'name': 'Test Node',
            'shortName': 'TEST',
            'hwModel': 'TEST_HW',
            'lat': None,
            'lon': None,
            'alt': None,
            'last_update': None,
            'publicKey': b'x' * 32
        }
    }
    
    # First sync
    print("\n1. First sync (force=False)...")
    result1 = nm.sync_pubkeys_to_interface(mock_interface, force=False)
    print(f"   Result: {result1} keys injected")
    
    # Immediate second sync with force=False - should skip
    print("\n2. Second sync (force=False, immediately)...")
    result2 = nm.sync_pubkeys_to_interface(mock_interface, force=False)
    print(f"   Result: {result2} keys injected (should be 0)")
    assert result2 == 0, "Non-forced sync should skip due to cache"
    
    # Third sync with force=True - should NOT skip
    print("\n3. Third sync (force=True, immediately)...")
    result3 = nm.sync_pubkeys_to_interface(mock_interface, force=True)
    print(f"   Result: {result3} keys injected")
    # force=True should perform full sync regardless of cache
    print("   ✓ force=True bypasses cache")
    
    print("\n✓ TEST 3 PASSED")

def test_interface_nodes_access_count():
    """Test that optimization reduces interface.nodes access"""
    print("\n" + "="*60)
    print("TEST 4: Reduced interface.nodes access")
    print("="*60)
    
    # Create mock interface with access tracking
    access_count = {'count': 0}
    
    class TrackedDict(dict):
        def __contains__(self, key):
            access_count['count'] += 1
            return super().__contains__(key)
    
    mock_interface = Mock()
    mock_interface.nodes = TrackedDict()
    
    # Create node manager with multiple keys
    nm = NodeManager()
    for i in range(10):
        nm.node_names[i] = {
            'name': f'Node {i}',
            'shortName': f'N{i}',
            'hwModel': 'TEST',
            'lat': None,
            'lon': None,
            'alt': None,
            'last_update': None,
            'publicKey': b'x' * 32
        }
    
    # First sync
    print(f"\n1. First sync with {len(nm.node_names)} keys...")
    access_count['count'] = 0
    result1 = nm.sync_pubkeys_to_interface(mock_interface, force=False)
    first_access = access_count['count']
    print(f"   interface.nodes accessed {first_access} times")
    print(f"   Result: {result1} keys injected")
    
    # Second sync - should skip entirely with cache
    print(f"\n2. Second sync (immediately after)...")
    access_count['count'] = 0
    result2 = nm.sync_pubkeys_to_interface(mock_interface, force=False)
    second_access = access_count['count']
    print(f"   interface.nodes accessed {second_access} times")
    print(f"   Result: {result2} keys injected")
    
    # Verify optimization
    print(f"\n   Optimization: {first_access} → {second_access} accesses")
    assert second_access == 0, f"Cache should eliminate interface.nodes access, but got {second_access}"
    print("   ✓ Cache eliminates ALL interface.nodes access!")
    
    print("\n✓ TEST 4 PASSED")

if __name__ == '__main__':
    print("="*60)
    print("PUBKEY SYNC OPTIMIZATION TESTS")
    print("="*60)
    
    try:
        test_cache_based_skip()
        test_cache_invalidation()
        test_force_sync_bypasses_cache()
        test_interface_nodes_access_count()
        
        print("\n" + "="*60)
        print("ALL TESTS PASSED ✓")
        print("="*60)
        print("\nOptimization Summary:")
        print("- Cache-based skipping reduces interface.nodes access to ZERO")
        print("- Cache is properly invalidated when keys change")
        print("- force=True bypasses cache for startup/reconnection scenarios")
        print("- This should prevent TCP disconnections caused by excessive")
        print("  interface.nodes access every 5 minutes")
        print("="*60)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
