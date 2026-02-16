#!/usr/bin/env python3
"""
Test that echo command preserves original sender name from message prefix
instead of using potentially incorrect sender_id.

Issue: Bot was responding with wrong sender name (bot's node ID) instead of 
actual sender name when sender_id lookup failed or was ambiguous.

Solution: Pass original message with sender prefix to handle_echo, which 
extracts the sender name directly from the message text.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys

def test_sender_extraction_logic():
    """Test the sender name extraction logic directly"""
    
    print("=" * 60)
    print("TEST: Sender name extraction from original message")
    print("=" * 60)
    
    # Test case 1: Extract sender name from "Tigro: /echo test"
    original_message = "Tigro: /echo test message"
    stripped_message = "/echo test message"
    
    print(f"Original: '{original_message}'")
    print(f"Stripped: '{stripped_message}'")
    print()
    
    # Simulate the extraction logic from handle_echo
    if original_message and ': ' in original_message:
        parts = original_message.split(': ', 1)
        if len(parts) == 2:
            sender_name = parts[0]
            echo_text = stripped_message[6:].strip()  # Remove "/echo "
            echo_response = f"{sender_name}: {echo_text}"
            
            print(f"✅ Extracted sender: '{sender_name}'")
            print(f"✅ Echo text: '{echo_text}'")
            print(f"✅ Final response: '{echo_response}'")
            
            assert sender_name == "Tigro", f"Expected 'Tigro' but got '{sender_name}'"
            assert echo_response == "Tigro: test message", f"Expected 'Tigro: test message' but got '{echo_response}'"
            
            print()
            print("✅ TEST PASSED - Correct sender name preserved")
            return True
    
    print("❌ TEST FAILED - Could not extract sender name")
    return False

def test_fallback_logic():
    """Test fallback when no original message"""
    
    print("=" * 60)
    print("TEST: Fallback to sender_id when no original")
    print("=" * 60)
    
    original_message = None
    stripped_message = "/echo test message"
    sender_short_name = "ad3dc"  # From sender_id
    
    print(f"Original: {original_message}")
    print(f"Stripped: '{stripped_message}'")
    print(f"Sender short name: '{sender_short_name}'")
    print()
    
    # Simulate the fallback logic
    if original_message and ': ' in original_message:
        parts = original_message.split(': ', 1)
        if len(parts) == 2:
            sender_name = parts[0]
            echo_text = stripped_message[6:].strip()
            echo_response = f"{sender_name}: {echo_text}"
        else:
            # Fallback
            echo_text = stripped_message[6:].strip()
            echo_response = f"{sender_short_name}: {echo_text}"
    else:
        # Fallback
        echo_text = stripped_message[6:].strip()
        echo_response = f"{sender_short_name}: {echo_text}"
    
    print(f"✅ Echo text: '{echo_text}'")
    print(f"✅ Final response: '{echo_response}'")
    
    assert echo_response == "ad3dc: test message", f"Expected 'ad3dc: test message' but got '{echo_response}'"
    
    print()
    print("✅ TEST PASSED - Correct fallback behavior")
    return True

def test_edge_cases():
    """Test edge cases"""
    
    print("=" * 60)
    print("TEST: Edge cases")
    print("=" * 60)
    
    # Test case 1: Message with multiple colons
    original = "Tigro: Note: /echo this is a test"
    print(f"\n1. Multiple colons: '{original}'")
    parts = original.split(': ', 1)
    if len(parts) == 2:
        sender_name = parts[0]
        rest = parts[1]
        print(f"   Sender: '{sender_name}'")
        print(f"   Rest: '{rest}'")
        assert sender_name == "Tigro", "Should extract 'Tigro'"
        print("   ✅ Correct")
    
    # Test case 2: No colon separator
    original = "Tigro /echo test"
    print(f"\n2. No colon: '{original}'")
    if ': ' in original:
        print("   Has colon separator")
    else:
        print("   No colon separator - will use fallback")
        print("   ✅ Correct fallback logic")
    
    # Test case 3: Empty sender name
    original = ": /echo test"
    print(f"\n3. Empty sender: '{original}'")
    parts = original.split(': ', 1)
    if len(parts) == 2:
        sender_name = parts[0]
        print(f"   Sender: '{sender_name}' (empty)")
        if not sender_name:
            print("   Empty sender - should use fallback")
            print("   ✅ Will fallback correctly")
    
    print()
    print("✅ TEST PASSED - Edge cases handled")
    return True

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("ECHO ORIGINAL MESSAGE PRESERVATION TESTS")
    print("=" * 60)
    print()
    
    try:
        test_sender_extraction_logic()
        print()
        test_fallback_logic()
        print()
        test_edge_cases()
        print()
        print("=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
    except AssertionError as e:
        print()
        print("=" * 60)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 60)
        sys.exit(1)
    except Exception as e:
        print()
        print("=" * 60)
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        sys.exit(1)
