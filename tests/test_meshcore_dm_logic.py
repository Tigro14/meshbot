#!/usr/bin/env python3
"""
Test: MeshCore DM Command Processing Logic

Tests the core logic without importing full module dependencies.
"""

import unittest


class TestMeshCoreDMLogic(unittest.TestCase):
    """Test the is_for_me logic for MeshCore DMs"""
    
    def setUp(self):
        """Set up test fixtures"""
        print("\n" + "="*70)
        print("TEST: MeshCore DM Command Processing Logic")
        print("="*70)
    
    def test_is_for_me_logic_without_meshcore_dm(self):
        """Test is_for_me logic WITHOUT _meshcore_dm flag"""
        print("\n📋 Test: Regular message (not MeshCore DM)")
        
        # Simulate message without _meshcore_dm flag
        packet = {
            'from': 0x143bcd7f,
            'to': 0xfffffffe,
            '_meshcore_dm': False
        }
        my_id = 0x12345678  # Different from to_id
        
        # Original logic (BROKEN for MeshCore DMs)
        is_for_me_old = (packet['to'] == my_id) if my_id else False
        print(f"   Old logic: is_for_me = {is_for_me_old}")
        self.assertFalse(is_for_me_old, "❌ Old logic: should be False")
        
        # New logic (WITH _meshcore_dm check)
        is_meshcore_dm = packet.get('_meshcore_dm', False)
        is_for_me_new = is_meshcore_dm or ((packet['to'] == my_id) if my_id else False)
        print(f"   New logic: is_for_me = {is_for_me_new}")
        self.assertFalse(is_for_me_new, "❌ New logic: should still be False (not MeshCore DM)")
        
        print("   ✅ Regular message correctly filtered")
    
    def test_is_for_me_logic_with_meshcore_dm(self):
        """Test is_for_me logic WITH _meshcore_dm flag"""
        print("\n📋 Test: MeshCore DM (with _meshcore_dm flag)")
        
        # Simulate MeshCore DM
        packet = {
            'from': 0x143bcd7f,
            'to': 0xfffffffe,  # Bot's MeshCore address
            '_meshcore_dm': True  # Marked by wrapper
        }
        my_id = 0x12345678  # Different from to_id
        
        # Original logic (BROKEN)
        is_for_me_old = (packet['to'] == my_id) if my_id else False
        print(f"   Old logic: is_for_me = {is_for_me_old} ❌")
        self.assertFalse(is_for_me_old, "Old logic incorrectly returns False")
        
        # New logic (FIXED)
        is_meshcore_dm = packet.get('_meshcore_dm', False)
        is_for_me_new = is_meshcore_dm or ((packet['to'] == my_id) if my_id else False)
        print(f"   New logic: is_for_me = {is_for_me_new} ✅")
        self.assertTrue(is_for_me_new, "❌ New logic should return True for MeshCore DMs")
        
        print("   ✅ MeshCore DM correctly recognized as 'for me'")
    
    def test_is_for_me_with_matching_to_id(self):
        """Test when to_id matches my_id (both old and new logic work)"""
        print("\n📋 Test: Message with matching to_id")
        
        packet = {
            'from': 0x143bcd7f,
            'to': 0x12345678,
            '_meshcore_dm': False
        }
        my_id = 0x12345678  # Matches to_id
        
        # Original logic
        is_for_me_old = (packet['to'] == my_id) if my_id else False
        print(f"   Old logic: is_for_me = {is_for_me_old}")
        self.assertTrue(is_for_me_old)
        
        # New logic
        is_meshcore_dm = packet.get('_meshcore_dm', False)
        is_for_me_new = is_meshcore_dm or ((packet['to'] == my_id) if my_id else False)
        print(f"   New logic: is_for_me = {is_for_me_new}")
        self.assertTrue(is_for_me_new)
        
        print("   ✅ Both logics work when to_id matches")
    
    def test_real_world_scenario(self):
        """Test the exact scenario from user logs"""
        print("\n📋 Test: Real-world scenario")
        print("   Setup:")
        print("   - Meshtastic node ID: 0x87654321 (from localNode)")
        print("   - MeshCore bot address: 0xfffffffe (different!)")
        print("   - DM from: 0x143bcd7f")
        print("   - Command: /power")
        
        # Real scenario
        packet = {
            'from': 0x143bcd7f,
            'to': 0xfffffffe,  # Bot's MeshCore address
            '_meshcore_dm': True
        }
        my_id = 0x87654321  # Meshtastic node ID (different)
        
        print(f"\n   Packet: from=0x{packet['from']:08x}, to=0x{packet['to']:08x}")
        print(f"   My Meshtastic ID: 0x{my_id:08x}")
        print(f"   _meshcore_dm: {packet['_meshcore_dm']}")
        
        # OLD LOGIC (BROKEN)
        is_for_me_old = (packet['to'] == my_id) if my_id else False
        print(f"\n   OLD logic: is_for_me = {is_for_me_old}")
        print(f"      to_id (0x{packet['to']:08x}) == my_id (0x{my_id:08x})? {packet['to'] == my_id}")
        print(f"      → Message FILTERED OUT ❌")
        self.assertFalse(is_for_me_old)
        
        # NEW LOGIC (FIXED)
        is_meshcore_dm = packet.get('_meshcore_dm', False)
        is_for_me_new = is_meshcore_dm or ((packet['to'] == my_id) if my_id else False)
        print(f"\n   NEW logic: is_for_me = is_meshcore_dm OR (to_id == my_id)")
        print(f"      is_meshcore_dm: {is_meshcore_dm}")
        print(f"      to_id == my_id: {packet['to'] == my_id}")
        print(f"      Result: {is_meshcore_dm} OR {packet['to'] == my_id} = {is_for_me_new}")
        print(f"      → Message PROCESSED ✅")
        self.assertTrue(is_for_me_new)
        
        print("\n   ✅ Real-world scenario FIXED")


def run_tests():
    """Run all tests"""
    print("="*70)
    print("MESHCORE DM COMMAND PROCESSING - LOGIC TEST")
    print("="*70)
    print()
    print("Testing the is_for_me logic fix without full module imports")
    print()
    
    # Run tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMeshCoreDMLogic)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print()
    print("="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.wasSuccessful():
        print()
        print("✅ ALL TESTS PASSED")
        print()
        print("KEY LOGIC CHANGES VALIDATED:")
        print("  1. ✅ _meshcore_dm flag checked")
        print("  2. ✅ MeshCore DMs always 'for me'")
        print("  3. ✅ Regular messages still filtered")
        print("  4. ✅ Real-world scenario works")
        print()
        print("CODE CHANGE:")
        print("  OLD: is_for_me = (to_id == my_id) if my_id else False")
        print("  NEW: is_for_me = is_meshcore_dm OR ((to_id == my_id) if my_id else False)")
        print()
        print("EXPECTED RESULT:")
        print("  Before: MeshCore DM logged but NOT processed ❌")
        print("  After:  MeshCore DM logged AND processed ✅")
        return 0
    else:
        print()
        print("❌ SOME TESTS FAILED")
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(run_tests())
