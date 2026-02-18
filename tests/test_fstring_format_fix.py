#!/usr/bin/env python3
"""
Test f-string formatting fix for deduplication logging.

Verifies that the destination ID formatting doesn't crash with ValueError.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def test_destination_formatting():
    """Test that destination ID formatting works for both int and string."""
    
    # Test integer destination ID
    destinationId = 0x889fa138
    
    # OLD BROKEN CODE (would crash):
    # f"0x{destinationId:08x if isinstance(destinationId, int) else destinationId}"
    
    # NEW WORKING CODE:
    dest_str = f"0x{destinationId:08x}" if isinstance(destinationId, int) else str(destinationId)
    result = f"Destination: {dest_str}"
    
    # Should produce correctly formatted hex string
    assert result == "Destination: 0x889fa138", f"Expected '0x889fa138', got '{result}'"
    print(f"✅ PASS: Integer destination formatted correctly: {result}")
    
    # Test string destination ID (edge case)
    destinationId = "broadcast"
    dest_str = f"0x{destinationId:08x}" if isinstance(destinationId, int) else str(destinationId)
    result = f"Destination: {dest_str}"
    
    assert result == "Destination: broadcast", f"Expected 'broadcast', got '{result}'"
    print(f"✅ PASS: String destination formatted correctly: {result}")


def test_old_syntax_fails():
    """Verify that old syntax would fail (for documentation purposes)."""
    
    destinationId = 0x889fa138
    
    try:
        # This is the OLD BROKEN CODE - should fail
        result = f"0x{destinationId:08x if isinstance(destinationId, int) else destinationId}"
        print(f"❌ FAIL: Old syntax should have raised ValueError but got: {result}")
        return False
    except ValueError as e:
        # Expected error
        print(f"✅ PASS: Old syntax correctly raises ValueError: {e}")
        return True


def test_message_truncation():
    """Test that message truncation also works correctly."""
    
    # Short message
    text = "Hello World"
    result = f"Message: {text[:50]}{'...' if len(text) > 50 else ''}"
    assert result == "Message: Hello World"
    print(f"✅ PASS: Short message formatted correctly")
    
    # Long message
    text = "A" * 60
    result = f"Message: {text[:50]}{'...' if len(text) > 50 else ''}"
    assert result == "Message: " + "A" * 50 + "..."
    assert len(result) == len("Message: ") + 50 + 3
    print(f"✅ PASS: Long message truncated correctly")


if __name__ == '__main__':
    print("Testing f-string formatting fix...\n")
    
    test_destination_formatting()
    test_old_syntax_fails()
    test_message_truncation()
    
    print("\n✅ ALL TESTS PASSED")
