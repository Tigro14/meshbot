#!/usr/bin/env python3
"""
Test: MeshCore DM Pubkey Derivation Fix

PROBLEM:
- MeshCore DM arrives with pubkey_prefix: '143bcd7f1b1f'
- Device has 0 contacts in contact list (companion mode or new contact)
- query_contact_by_pubkey_prefix() returns None
- sender_id remains None → message from 0xFFFFFFFF (unknown)
- Bot can't respond to DM

ROOT CAUSE:
- Contact isn't in device's contact list yet
- sync_contacts() returns 0 contacts
- No way to resolve pubkey_prefix to node_id

SOLUTION:
- DERIVE node_id from pubkey_prefix
- In MeshCore/Meshtastic, node_id = first 4 bytes of 32-byte public key
- pubkey_prefix '143bcd7f1b1f' → first 8 hex chars → node_id 0x143bcd7f
- Save derived contact for future reference

This test validates the fix works correctly.
"""

import unittest
from unittest.mock import MagicMock, patch, call
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))


class TestMeshCorePubkeyDerive(unittest.TestCase):
    """Test pubkey → node_id derivation for MeshCore DMs"""
    
    def setUp(self):
        """Set up test fixtures"""
        print("\n" + "="*70)
        print("TEST: MeshCore Pubkey Derivation Fix")
        print("="*70)
    
    def test_derive_node_id_from_pubkey_prefix(self):
        """Test that node_id can be derived from pubkey_prefix"""
        print("\n📋 Test: Derive node_id from pubkey_prefix")
        
        # Test case from logs: pubkey_prefix = '143bcd7f1b1f'
        pubkey_prefix = '143bcd7f1b1f'
        
        # Expected node_id: first 8 hex chars (4 bytes)
        expected_node_id = 0x143bcd7f
        
        # Derive node_id (first 8 hex chars = 4 bytes)
        node_id_hex = pubkey_prefix[:8]
        derived_node_id = int(node_id_hex, 16)
        
        print(f"   Pubkey prefix: {pubkey_prefix}")
        print(f"   First 8 hex chars: {node_id_hex}")
        print(f"   Derived node_id: 0x{derived_node_id:08x}")
        print(f"   Expected: 0x{expected_node_id:08x}")
        
        self.assertEqual(derived_node_id, expected_node_id, 
                        f"❌ Derivation failed: got 0x{derived_node_id:08x}, expected 0x{expected_node_id:08x}")
        print("   ✅ Node_id correctly derived from pubkey_prefix")
    
    def test_on_contact_message_derives_sender_id(self):
        """Test that _on_contact_message() derives sender_id when not in contacts"""
        print("\n📋 Test: _on_contact_message() derives sender_id")
        
        # Mock meshcore object with empty contacts
        mock_meshcore = MagicMock()
        mock_meshcore.contacts = []  # Empty - contact not found
        mock_meshcore.get_contact_by_key_prefix = MagicMock(return_value=None)
        
        # Mock node_manager with empty meshcore contacts
        mock_node_manager = MagicMock()
        mock_node_manager.find_meshcore_contact_by_pubkey_prefix = MagicMock(return_value=None)
        
        # Mock persistence for saving derived contact
        mock_persistence = MagicMock()
        mock_persistence.save_meshcore_contact = MagicMock()
        mock_node_manager.persistence = mock_persistence
        
        # Mock message callback
        mock_callback = MagicMock()
        
        # Create wrapper instance (mock import)
        with patch('meshcore_cli_wrapper.MeshCore'):
            with patch('meshcore_cli_wrapper.MESHCORE_CLI_AVAILABLE', True):
                from meshcore_cli_wrapper import MeshCoreCLIWrapper
                
                # Create wrapper and inject mocked objects
                wrapper = MeshCoreCLIWrapper('/dev/ttyUSB0')
                wrapper.meshcore = mock_meshcore
                wrapper.node_manager = mock_node_manager
                wrapper.message_callback = mock_callback
                
                # Create mock event with pubkey_prefix (like real MeshCore event)
                mock_event = MagicMock()
                mock_event.payload = {
                    'type': 'PRIV',
                    'pubkey_prefix': '143bcd7f1b1f',  # Real pubkey from logs
                    'text': '/power',
                    'contact_id': None,  # Not in contacts
                    'sender_id': None
                }
                
                # Call _on_contact_message
                print("   Calling _on_contact_message with pubkey_prefix='143bcd7f1b1f'...")
                wrapper._on_contact_message(mock_event)
                
                # Verify message_callback was called
                self.assertTrue(mock_callback.called, 
                              "❌ message_callback was NOT called")
                print("   ✅ message_callback was called")
                
                # Extract the packet passed to callback
                call_args = mock_callback.call_args[0]
                packet = call_args[0]
                
                # Verify sender_id was derived correctly
                expected_sender_id = 0x143bcd7f
                actual_sender_id = packet['from']
                
                print(f"   Packet sender_id: 0x{actual_sender_id:08x}")
                print(f"   Expected: 0x{expected_sender_id:08x}")
                
                self.assertEqual(actual_sender_id, expected_sender_id,
                               f"❌ Wrong sender_id: got 0x{actual_sender_id:08x}, expected 0x{expected_sender_id:08x}")
                print("   ✅ Sender_id correctly derived from pubkey_prefix")
                
                # Verify sender_id is NOT 0xFFFFFFFF (unknown)
                self.assertNotEqual(actual_sender_id, 0xFFFFFFFF,
                                  "❌ Sender_id is still 0xFFFFFFFF (unknown)")
                print("   ✅ Sender_id is NOT 0xFFFFFFFF (not unknown)")
                
                # Verify derived contact was saved
                self.assertTrue(mock_persistence.save_meshcore_contact.called,
                              "❌ Derived contact was NOT saved")
                
                # Check saved contact data
                save_call_args = mock_persistence.save_meshcore_contact.call_args[0]
                saved_contact = save_call_args[0]
                
                self.assertEqual(saved_contact['node_id'], expected_sender_id,
                               "❌ Saved contact has wrong node_id")
                self.assertEqual(saved_contact['source'], 'meshcore_derived',
                               "❌ Saved contact should be marked as 'meshcore_derived'")
                print("   ✅ Derived contact saved to database")
    
    def test_pubkey_prefix_too_short(self):
        """Test handling of pubkey_prefix that's too short"""
        print("\n📋 Test: Handle too-short pubkey_prefix")
        
        # Mock node_manager
        mock_node_manager = MagicMock()
        mock_node_manager.find_meshcore_contact_by_pubkey_prefix = MagicMock(return_value=None)
        
        # Create wrapper instance
        with patch('meshcore_cli_wrapper.MeshCore'):
            with patch('meshcore_cli_wrapper.MESHCORE_CLI_AVAILABLE', True):
                from meshcore_cli_wrapper import MeshCoreCLIWrapper
                
                wrapper = MeshCoreCLIWrapper('/dev/ttyUSB0')
                wrapper.node_manager = mock_node_manager
                wrapper.meshcore = MagicMock()
                wrapper.message_callback = MagicMock()
                
                # Create event with too-short pubkey_prefix
                mock_event = MagicMock()
                mock_event.payload = {
                    'pubkey_prefix': '143b',  # Only 4 hex chars, need at least 8
                    'text': '/power',
                    'contact_id': None
                }
                
                print("   Testing with short pubkey_prefix: '143b'")
                wrapper._on_contact_message(mock_event)
                
                # Should fallback to 0xFFFFFFFF (unknown)
                call_args = wrapper.message_callback.call_args[0]
                packet = call_args[0]
                sender_id = packet['from']
                
                print(f"   Sender_id with short prefix: 0x{sender_id:08x}")
                self.assertEqual(sender_id, 0xFFFFFFFF,
                               "❌ Should fallback to 0xFFFFFFFF for short prefix")
                print("   ✅ Correctly falls back to 0xFFFFFFFF for short prefix")
    
    def test_pubkey_prefix_padding(self):
        """Test that partial pubkey_prefix is padded correctly"""
        print("\n📋 Test: Pubkey prefix padding")
        
        # pubkey_prefix might be partial (e.g., 12 hex chars instead of 64)
        partial_prefix = '143bcd7f1b1f'
        
        # Should pad to 64 hex chars (32 bytes)
        full_pubkey_hex = partial_prefix + '0' * (64 - len(partial_prefix))
        
        print(f"   Partial prefix: {partial_prefix} ({len(partial_prefix)} chars)")
        print(f"   Padded to: {len(full_pubkey_hex)} chars")
        
        self.assertEqual(len(full_pubkey_hex), 64, 
                        "❌ Padded hex should be 64 chars (32 bytes)")
        self.assertTrue(full_pubkey_hex.startswith(partial_prefix),
                       "❌ Padded hex should start with original prefix")
        print("   ✅ Prefix correctly padded to 64 hex chars")
        
        # Verify we can convert to bytes
        try:
            public_key_bytes = bytes.fromhex(full_pubkey_hex)
            self.assertEqual(len(public_key_bytes), 32,
                           "❌ Public key should be 32 bytes")
            print(f"   ✅ Converted to {len(public_key_bytes)} bytes")
        except Exception as e:
            self.fail(f"❌ Failed to convert to bytes: {e}")
    
    def test_real_world_scenario(self):
        """Test real-world scenario from logs"""
        print("\n📋 Test: Real-world scenario from logs")
        print("   Scenario:")
        print("   - DM arrives with pubkey_prefix: '143bcd7f1b1f'")
        print("   - Device has 0 contacts (companion mode)")
        print("   - Bot must derive node_id and process message")
        
        # Real data from logs
        pubkey_prefix = '143bcd7f1b1f'
        message_text = '/power'
        
        # Expected derived node_id
        expected_node_id = 0x143bcd7f
        
        # Mock everything
        mock_meshcore = MagicMock()
        mock_meshcore.contacts = []
        mock_meshcore.get_contact_by_key_prefix = MagicMock(return_value=None)
        
        mock_node_manager = MagicMock()
        mock_node_manager.find_meshcore_contact_by_pubkey_prefix = MagicMock(return_value=None)
        mock_persistence = MagicMock()
        mock_node_manager.persistence = mock_persistence
        
        mock_callback = MagicMock()
        
        with patch('meshcore_cli_wrapper.MeshCore'):
            with patch('meshcore_cli_wrapper.MESHCORE_CLI_AVAILABLE', True):
                from meshcore_cli_wrapper import MeshCoreCLIWrapper
                
                wrapper = MeshCoreCLIWrapper('/dev/ttyUSB0')
                wrapper.meshcore = mock_meshcore
                wrapper.node_manager = mock_node_manager
                wrapper.message_callback = mock_callback
                
                # Create event exactly like real MeshCore event
                mock_event = MagicMock()
                mock_event.payload = {
                    'type': 'PRIV',
                    'SNR': 0.0,
                    'pubkey_prefix': pubkey_prefix,
                    'path_len': 0,
                    'txt_type': 0,
                    'sender_timestamp': 1738445453,
                    'text': message_text,
                    'contact_id': None
                }
                
                print(f"   Processing DM: '{message_text}'")
                print(f"   Pubkey prefix: {pubkey_prefix}")
                
                # Process the message
                wrapper._on_contact_message(mock_event)
                
                # Verify results
                self.assertTrue(mock_callback.called, "❌ Callback not called")
                
                packet = mock_callback.call_args[0][0]
                actual_sender_id = packet['from']
                actual_text = packet['decoded']['payload'].decode('utf-8')
                
                print(f"   ✅ Message processed")
                print(f"   Sender_id: 0x{actual_sender_id:08x}")
                print(f"   Message text: {actual_text}")
                
                # Verify sender_id derived correctly
                self.assertEqual(actual_sender_id, expected_node_id,
                               f"❌ Wrong sender_id: 0x{actual_sender_id:08x} != 0x{expected_node_id:08x}")
                
                # Verify message text preserved
                self.assertEqual(actual_text, message_text,
                               f"❌ Wrong message text: {actual_text}")
                
                # Verify NOT marked as broadcast (to != 0xFFFFFFFF)
                to_id = packet['to']
                self.assertNotEqual(to_id, 0xFFFFFFFF,
                                  "❌ Message should NOT be marked as broadcast")
                
                print("   ✅ Real-world scenario PASSED")
                print(f"   Bot can now respond to DM from 0x{actual_sender_id:08x}")


def run_tests():
    """Run all tests"""
    print("="*70)
    print("MESHCORE PUBKEY DERIVATION FIX - TEST SUITE")
    print("="*70)
    print()
    print("Issue: MeshCore DM with pubkey_prefix but 0 contacts in device")
    print("Fix: Derive node_id from pubkey_prefix (first 4 bytes of public key)")
    print()
    
    # Run tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMeshCorePubkeyDerive)
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
        print("KEY CHANGES VALIDATED:")
        print("  1. ✅ Node_id can be derived from pubkey_prefix")
        print("  2. ✅ Derivation works even with 0 contacts in device")
        print("  3. ✅ Derived contact is saved to database")
        print("  4. ✅ Sender_id is NOT 0xFFFFFFFF (unknown)")
        print("  5. ✅ Bot can respond to DM from derived sender")
        print()
        print("EXPECTED BEHAVIOR:")
        print("  Before fix:")
        print("    ❌ DM from unknown sender (0xFFFFFFFF)")
        print("    ❌ Bot can't respond (no sender_id)")
        print()
        print("  After fix:")
        print("    ✅ DM from 0x143bcd7f (derived from pubkey)")
        print("    ✅ Bot can respond to correct sender")
        return 0
    else:
        print()
        print("❌ SOME TESTS FAILED")
        return 1


if __name__ == '__main__':
    sys.exit(run_tests())
