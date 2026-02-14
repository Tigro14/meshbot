#!/usr/bin/env python3
"""
Test for verifying non-dict payload handling in CHANNEL_MSG_RECV

This test validates that _on_channel_message doesn't fail with
non-dict payloads and can extract data from multiple sources.
"""

import sys
import unittest
from unittest.mock import Mock, MagicMock


class TestChannelMessageNonDictPayload(unittest.TestCase):
    """Test _on_channel_message handles non-dict payloads correctly"""
    
    def test_non_dict_payload_does_not_exit_early(self):
        """Test that non-dict payload doesn't cause early return"""
        from meshcore_cli_wrapper import MeshCoreCLIWrapper
        
        wrapper = MeshCoreCLIWrapper(port='/dev/ttyUSB0', baudrate=115200)
        wrapper.message_callback = Mock()
        
        # Create event where payload is not a dict but event has attributes
        mock_event = Mock()
        mock_event.payload = "not_a_dict"  # Non-dict payload
        mock_event.sender_id = 0x6e3f11bf
        mock_event.text = "/echo test"
        
        # This should NOT return early, should extract from event.sender_id
        wrapper._on_channel_message(mock_event)
        
        # Should forward to callback because sender_id and text extracted
        wrapper.message_callback.assert_called_once()
        call_args = wrapper.message_callback.call_args
        packet = call_args[0][0]
        
        self.assertEqual(packet['from'], 0x6e3f11bf)
        print("✅ Non-dict payload does not cause early return")
    
    def test_event_object_payload_extracts_from_event(self):
        """Test extraction from event when payload is event itself"""
        from meshcore_cli_wrapper import MeshCoreCLIWrapper
        
        wrapper = MeshCoreCLIWrapper(port='/dev/ttyUSB0', baudrate=115200)
        wrapper.message_callback = Mock()
        
        # Create event without payload attribute - payload becomes event
        mock_event = Mock()
        # Remove payload attribute to trigger fallback
        del mock_event.payload
        mock_event.sender_id = 0x12345678
        mock_event.text = "/echo from event"
        
        wrapper._on_channel_message(mock_event)
        
        # Should extract from event directly
        wrapper.message_callback.assert_called_once()
        call_args = wrapper.message_callback.call_args
        packet = call_args[0][0]
        
        self.assertEqual(packet['from'], 0x12345678)
        self.assertEqual(packet['decoded']['payload'], b'/echo from event')
        print("✅ Data extracted from event when payload is event itself")
    
    def test_dict_payload_still_works(self):
        """Test that dict payloads still work correctly"""
        from meshcore_cli_wrapper import MeshCoreCLIWrapper
        
        wrapper = MeshCoreCLIWrapper(port='/dev/ttyUSB0', baudrate=115200)
        wrapper.message_callback = Mock()
        
        # Create event with proper dict payload
        mock_event = Mock()
        mock_event.payload = {
            'sender_id': 0xABCDEF01,
            'channel_idx': 0,
            'text': '/echo dict payload',
            'type': 11
        }
        
        wrapper._on_channel_message(mock_event)
        
        # Should work as before
        wrapper.message_callback.assert_called_once()
        call_args = wrapper.message_callback.call_args
        packet = call_args[0][0]
        
        self.assertEqual(packet['from'], 0xABCDEF01)
        print("✅ Dict payload extraction still works")
    
    def test_mixed_extraction_sources(self):
        """Test extraction from mixed sources (payload + event)"""
        from meshcore_cli_wrapper import MeshCoreCLIWrapper
        
        wrapper = MeshCoreCLIWrapper(port='/dev/ttyUSB0', baudrate=115200)
        wrapper.message_callback = Mock()
        
        # Payload has text but no sender_id
        # Event has sender_id
        mock_event = Mock()
        mock_event.payload = {
            'text': '/echo mixed',
            'channel_idx': 1
        }
        mock_event.sender_id = 0xFEDCBA98
        
        wrapper._on_channel_message(mock_event)
        
        # Should extract sender_id from event, text from payload
        wrapper.message_callback.assert_called_once()
        call_args = wrapper.message_callback.call_args
        packet = call_args[0][0]
        
        self.assertEqual(packet['from'], 0xFEDCBA98)
        self.assertEqual(packet['channel'], 1)
        print("✅ Mixed extraction from payload and event works")
    
    def test_no_text_still_returns_early(self):
        """Test that messages without text are still ignored (correct behavior)"""
        from meshcore_cli_wrapper import MeshCoreCLIWrapper
        
        wrapper = MeshCoreCLIWrapper(port='/dev/ttyUSB0', baudrate=115200)
        wrapper.message_callback = Mock()
        
        # Event with sender_id but no text
        mock_event = Mock()
        mock_event.sender_id = 0x11111111
        mock_event.payload = {}
        # No text attribute
        
        wrapper._on_channel_message(mock_event)
        
        # Should NOT forward - no text to process
        wrapper.message_callback.assert_not_called()
        print("✅ Messages without text are correctly ignored")


if __name__ == '__main__':
    print("\n" + "="*70)
    print("TEST: Non-Dict Payload Handling in CHANNEL_MSG_RECV")
    print("="*70 + "\n")
    
    print("Testing that interface doesn't become 'deaf' with non-dict payloads")
    print("-" * 70 + "\n")
    
    # Run tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestChannelMessageNonDictPayload)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "="*70)
    if result.wasSuccessful():
        print("✅ ALL TESTS PASSED")
        print("\nValidated behaviors:")
        print("  1. ✅ Non-dict payload doesn't cause early return")
        print("  2. ✅ Event object as payload extracts from event")
        print("  3. ✅ Dict payloads still work correctly")
        print("  4. ✅ Mixed extraction from payload + event")
        print("  5. ✅ Messages without text still ignored")
        print("\nThe fix prevents interface from becoming 'deaf'")
        print("by continuing extraction even with non-dict payloads.")
    else:
        print("❌ SOME TESTS FAILED")
        sys.exit(1)
    print("="*70 + "\n")
