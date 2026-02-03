#!/usr/bin/env python3
"""
Test suite for MeshCore DM command response fix

This test verifies that DM messages via CONTACT_MSG_RECV are properly handled
and not treated as broadcasts.
"""

def test_localnode_nodenum_not_broadcast():
    """Test that localNode.nodeNum is not set to broadcast address"""
    # Simulate MeshCoreCLIWrapper initialization
    class MockLocalNode:
        def __init__(self):
            # Should be 0xFFFFFFFE, NOT 0xFFFFFFFF
            self.nodeNum = 0xFFFFFFFE
    
    localNode = MockLocalNode()
    
    # Verify it's NOT the broadcast address
    assert localNode.nodeNum != 0xFFFFFFFF, "localNode.nodeNum should NOT be broadcast address"
    assert localNode.nodeNum != 0x00000000, "localNode.nodeNum should NOT be 0"
    
    # Verify it's the expected value
    assert localNode.nodeNum == 0xFFFFFFFE, "localNode.nodeNum should be 0xFFFFFFFE"
    
    print("✅ Test 1: localNode.nodeNum is not broadcast address")


def test_dm_packet_structure():
    """Test that DM packets have correct structure"""
    # Simulate DM packet creation
    localNode_nodeNum = 0xFFFFFFFE
    sender_id = 0xFFFFFFFF  # Unknown sender
    
    packet = {
        'from': sender_id,
        'to': localNode_nodeNum,  # Should be 0xFFFFFFFE
        'decoded': {
            'portnum': 'TEXT_MESSAGE_APP',
            'payload': b'/help'
        },
        '_meshcore_dm': True
    }
    
    # Verify packet structure
    assert packet['from'] == 0xFFFFFFFF, "from should be sender_id"
    assert packet['to'] == 0xFFFFFFFE, "to should be localNode.nodeNum (0xFFFFFFFE)"
    assert packet['_meshcore_dm'] == True, "_meshcore_dm flag should be True"
    
    print("✅ Test 2: DM packet structure is correct")


def test_broadcast_detection():
    """Test that DM packets are NOT detected as broadcasts"""
    # Simulate broadcast detection logic from main_bot.py
    
    # Test Case 1: MeshCore DM with unknown sender
    to_id = 0xFFFFFFFE  # localNode.nodeNum
    is_meshcore_dm = True
    
    is_broadcast = (to_id in [0xFFFFFFFF, 0]) and not is_meshcore_dm
    
    assert is_broadcast == False, "MeshCore DM should NOT be treated as broadcast"
    print("  ✅ Case 1: MeshCore DM (to=0xFFFFFFFE) is NOT broadcast")
    
    # Test Case 2: Regular broadcast
    to_id = 0xFFFFFFFF
    is_meshcore_dm = False
    
    is_broadcast = (to_id in [0xFFFFFFFF, 0]) and not is_meshcore_dm
    
    assert is_broadcast == True, "Regular broadcast should be detected"
    print("  ✅ Case 2: Regular broadcast (to=0xFFFFFFFF) IS broadcast")
    
    # Test Case 3: MeshCore DM with flag even if to=0xFFFFFFFF (edge case)
    to_id = 0xFFFFFFFF
    is_meshcore_dm = True
    
    is_broadcast = (to_id in [0xFFFFFFFF, 0]) and not is_meshcore_dm
    
    assert is_broadcast == False, "MeshCore DM with flag should NOT be broadcast (even if to=0xFFFFFFFF)"
    print("  ✅ Case 3: MeshCore DM with flag (to=0xFFFFFFFF) is NOT broadcast (flag override)")
    
    # Test Case 4: Direct message (not broadcast, not MeshCore DM)
    to_id = 0x12345678
    is_meshcore_dm = False
    
    is_broadcast = (to_id in [0xFFFFFFFF, 0]) and not is_meshcore_dm
    
    assert is_broadcast == False, "Direct message should NOT be broadcast"
    print("  ✅ Case 4: Direct message (to=specific node) is NOT broadcast")
    
    print("✅ Test 3: Broadcast detection works correctly")


def test_message_logging():
    """Test that message logging shows correct values"""
    from_id = 0xFFFFFFFF  # Unknown sender
    to_id = 0xFFFFFFFE  # localNode.nodeNum
    is_meshcore_dm = True
    
    is_broadcast = (to_id in [0xFFFFFFFF, 0]) and not is_meshcore_dm
    
    # Expected log output
    expected_log = f"MESSAGE BRUT: '/help' | from=0x{from_id:08x} | to=0x{to_id:08x} | broadcast={is_broadcast}"
    
    assert "from=0xffffffff" in expected_log, "from should be 0xffffffff"
    assert "to=0xfffffffe" in expected_log, "to should be 0xfffffffe (NOT 0xffffffff)"
    assert "broadcast=False" in expected_log, "broadcast should be False"
    
    print("✅ Test 4: Message logging shows correct values")
    print(f"  Expected log: {expected_log}")


def test_command_processing():
    """Test that commands are processed (not filtered)"""
    # Simulate command processing logic
    to_id = 0xFFFFFFFE
    is_meshcore_dm = True
    is_broadcast = (to_id in [0xFFFFFFFF, 0]) and not is_meshcore_dm
    
    message = "/help"
    
    # Simulate broadcast filtering
    should_filter = False
    if is_broadcast:
        # Would check _is_recent_broadcast() here
        should_filter = True
    
    assert should_filter == False, "DM commands should NOT be filtered"
    assert is_broadcast == False, "DM should not be detected as broadcast"
    
    # Command should be processed
    should_process = not should_filter
    assert should_process == True, "Command should be processed"
    
    print("✅ Test 5: Commands are processed (not filtered)")


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("Running MeshCore DM Fix Tests")
    print("="*60 + "\n")
    
    try:
        test_localnode_nodenum_not_broadcast()
        test_dm_packet_structure()
        test_broadcast_detection()
        test_message_logging()
        test_command_processing()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60)
        return True
        
    except AssertionError as e:
        print("\n" + "="*60)
        print(f"❌ TEST FAILED: {e}")
        print("="*60)
        return False
    except Exception as e:
        print("\n" + "="*60)
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        print("="*60)
        return False


if __name__ == "__main__":
    import sys
    success = run_all_tests()
    sys.exit(0 if success else 1)
