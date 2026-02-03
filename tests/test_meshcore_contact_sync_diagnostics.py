#!/usr/bin/env python3
"""
Test MeshCore contact sync diagnostic logging
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_diagnostic_messages_exist():
    """Verify diagnostic logging is present in code"""
    
    with open('meshcore_cli_wrapper.py', 'r') as f:
        code = f.read()
    
    # Check for diagnostic debug messages
    assert '🔍 [MESHCORE-SYNC] Check save conditions:' in code, \
        "Missing diagnostic condition check message"
    
    assert 'post_count > 0:' in code, \
        "Missing post_count condition check"
    
    assert 'self.node_manager exists:' in code, \
        "Missing node_manager existence check"
    
    assert 'has persistence attr:' in code, \
        "Missing persistence attribute check"
    
    # Check for error logging on save failure
    assert '❌ [MESHCORE-SYNC]' in code, \
        "Missing error message for sync failure"
    
    assert 'contacts synchronisés mais NON SAUVEGARDÉS' in code, \
        "Missing 'not saved' error message"
    
    assert 'node_manager n\'est pas configuré (None)' in code, \
        "Missing node_manager not configured error"
    
    assert 'Appeler interface.set_node_manager(node_manager) AVANT start_reading()' in code, \
        "Missing solution for node_manager not set"
    
    print("✅ All diagnostic messages present in code")


def test_sync_sequence_documented():
    """Verify sync sequence is correctly documented"""
    
    # The correct sequence should be:
    # 1. interface = MeshCoreSerialInterface(port)
    # 2. interface.connect()
    # 3. interface.set_node_manager(node_manager)  ← MUST be before start_reading
    # 4. interface.start_reading()  ← triggers async sync
    
    with open('main_bot.py', 'r') as f:
        lines = f.readlines()
    
    # Find the MeshCore initialization sequence
    meshcore_init_line = None
    set_node_manager_line = None
    start_reading_line = None
    
    for i, line in enumerate(lines):
        if 'MeshCoreSerialInterface(' in line:
            meshcore_init_line = i
        if 'set_node_manager(self.node_manager)' in line and meshcore_init_line:
            set_node_manager_line = i
        if 'start_reading()' in line and meshcore_init_line and i > meshcore_init_line:
            start_reading_line = i
            break
    
    assert meshcore_init_line is not None, "MeshCoreSerialInterface initialization not found"
    assert set_node_manager_line is not None, "set_node_manager call not found"
    assert start_reading_line is not None, "start_reading call not found"
    
    # Verify correct order
    assert meshcore_init_line < set_node_manager_line < start_reading_line, \
        f"Incorrect sequence: init={meshcore_init_line}, set_node_manager={set_node_manager_line}, start_reading={start_reading_line}"
    
    print(f"✅ Correct sequence verified:")
    print(f"   Line {meshcore_init_line + 1}: MeshCoreSerialInterface() init")
    print(f"   Line {set_node_manager_line + 1}: set_node_manager()")
    print(f"   Line {start_reading_line + 1}: start_reading()")


def test_condition_checks_comprehensive():
    """Verify all conditions are checked in detail"""
    
    with open('meshcore_cli_wrapper.py', 'r') as f:
        code = f.read()
    
    # Should check all 4 conditions from line 741:
    # 1. post_count > 0
    # 2. self.node_manager
    # 3. hasattr(self.node_manager, 'persistence')
    # 4. self.node_manager.persistence
    
    conditions = [
        'post_count > 0',
        'self.node_manager is not None',
        'hasattr(self.node_manager, \'persistence\')',
        'self.node_manager.persistence is not None'
    ]
    
    for condition in conditions:
        assert condition in code, f"Missing check for condition: {condition}"
    
    print("✅ All 4 save conditions are checked")


if __name__ == '__main__':
    print("🧪 Testing MeshCore Contact Sync Diagnostics")
    print("=" * 60)
    
    test_diagnostic_messages_exist()
    test_sync_sequence_documented()
    test_condition_checks_comprehensive()
    
    print("=" * 60)
    print("✅ All tests passed!")
    print()
    print("📋 Next Steps for Deployment:")
    print("1. Deploy updated meshcore_cli_wrapper.py to production")
    print("2. Enable DEBUG_MODE=True in config.py")
    print("3. Restart bot and wait for contact sync")
    print("4. Check logs for:")
    print("   - '🔍 [MESHCORE-SYNC] Check save conditions:'")
    print("   - Either success ('💾 ... contacts sauvegardés')")
    print("   - Or failure ('❌ ... contacts synchronisés mais NON SAUVEGARDÉS')")
    print("5. If failure, check which condition is False")
    print("6. Apply additional fix based on diagnostic output")
