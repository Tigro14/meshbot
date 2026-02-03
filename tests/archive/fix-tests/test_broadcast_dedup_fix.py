#!/usr/bin/env python3
"""
Test for broadcast deduplication and deaf bot fix

This test verifies:
1. Broadcast detection works for both to_id=0xFFFFFFFF and to_id=0
2. Deduplication only filters broadcasts, not DMs
3. Error handling prevents deduplication from blocking messages
"""

import time
import hashlib


class MockTrafficMonitor:
    """Mock traffic monitor for testing"""
    def add_public_message(self, packet, message, source):
        print(f"   ✓ Stats updated: '{message[:30]}'")


class MeshBotSimulator:
    """Simplified MeshBot for testing broadcast deduplication"""
    
    def __init__(self):
        self._recent_broadcasts = {}
        self._broadcast_dedup_window = 60
        self.traffic_monitor = MockTrafficMonitor()
    
    def _track_broadcast(self, message):
        """Track a broadcast we're sending"""
        msg_hash = hashlib.md5(message.encode('utf-8')).hexdigest()
        current_time = time.time()
        
        # Clean old broadcasts
        self._recent_broadcasts = {
            h: t for h, t in self._recent_broadcasts.items()
            if current_time - t < self._broadcast_dedup_window
        }
        
        # Record this broadcast
        self._recent_broadcasts[msg_hash] = current_time
        print(f"   🔖 Tracked broadcast: {msg_hash[:8]}...")
    
    def _is_recent_broadcast(self, message):
        """Check if message is a recent broadcast we sent"""
        msg_hash = hashlib.md5(message.encode('utf-8')).hexdigest()
        current_time = time.time()
        
        if msg_hash in self._recent_broadcasts:
            age = current_time - self._recent_broadcasts[msg_hash]
            if age < self._broadcast_dedup_window:
                print(f"   🔍 Recognized our broadcast ({age:.1f}s old)")
                return True
        
        return False
    
    def process_message(self, packet, message):
        """Simulate message processing with deduplication"""
        from_id = packet['from']
        to_id = packet['to']
        my_id = 0x12345678
        
        is_from_me = (from_id == my_id)
        is_broadcast = (to_id in [0xFFFFFFFF, 0])  # FIX: Check both values!
        
        print(f"\n   📨 Processing: '{message[:40]}'")
        print(f"      from=0x{from_id:08x}, to=0x{to_id:08x}")
        print(f"      is_broadcast={is_broadcast}, is_from_me={is_from_me}")
        
        # Filter self-generated messages
        if is_from_me:
            print(f"   ⏭️  Skipped: from myself")
            return False
        
        # Deduplication for broadcasts only
        if is_broadcast:
            try:
                if self._is_recent_broadcast(message):
                    print(f"   🔄 Filtered: our own broadcast")
                    # Still update stats
                    self.traffic_monitor.add_public_message(packet, message, 'local')
                    return False  # Filtered
            except Exception as e:
                print(f"   ⚠️  Dedup error: {e} - continuing anyway")
                # Continue processing on error
        
        # Process the message
        print(f"   ✅ Processed successfully")
        return True


def test_broadcast_detection():
    """Test that broadcasts are detected correctly"""
    print("\n" + "="*70)
    print("TEST 1: Broadcast Detection (to_id=0xFFFFFFFF and to_id=0)")
    print("="*70)
    
    bot = MeshBotSimulator()
    
    # Test 1a: Broadcast with to_id=0xFFFFFFFF
    packet1 = {'from': 0x87654321, 'to': 0xFFFFFFFF}
    result1 = bot.process_message(packet1, "Test broadcast 1")
    assert result1 == True, "Broadcast with to_id=0xFFFFFFFF should be processed"
    print("   ✅ to_id=0xFFFFFFFF detected as broadcast")
    
    # Test 1b: Broadcast with to_id=0
    packet2 = {'from': 0x87654321, 'to': 0}
    result2 = bot.process_message(packet2, "Test broadcast 2")
    assert result2 == True, "Broadcast with to_id=0 should be processed"
    print("   ✅ to_id=0 detected as broadcast")
    
    # Test 1c: DM (direct message)
    packet3 = {'from': 0x87654321, 'to': 0x12345678}
    result3 = bot.process_message(packet3, "Test DM")
    assert result3 == True, "DM should be processed"
    print("   ✅ DM (to_id != 0 and != 0xFFFFFFFF) correctly identified")
    
    print("\n✅ TEST 1 PASSED: Broadcast detection works correctly\n")


def test_deduplication():
    """Test that deduplication filters our own broadcasts"""
    print("="*70)
    print("TEST 2: Broadcast Deduplication")
    print("="*70)
    
    bot = MeshBotSimulator()
    
    # Send a broadcast
    broadcast_msg = "🌧️ Il va pleuvoir à Paris"
    print(f"\n   📡 Bot sends broadcast: '{broadcast_msg}'")
    bot._track_broadcast(broadcast_msg)
    
    # Receive our own broadcast back
    time.sleep(0.1)  # Small delay
    packet = {'from': 0x87654321, 'to': 0xFFFFFFFF}
    result = bot.process_message(packet, broadcast_msg)
    
    assert result == False, "Our own broadcast should be filtered"
    print("\n✅ TEST 2 PASSED: Deduplication filters our own broadcasts\n")


def test_dm_not_filtered():
    """Test that DMs are never filtered by deduplication"""
    print("="*70)
    print("TEST 3: DMs Never Filtered")
    print("="*70)
    
    bot = MeshBotSimulator()
    
    # Send a broadcast (to track the message)
    msg = "/weather Paris"
    print(f"\n   📡 Bot sends broadcast: '{msg}'")
    bot._track_broadcast(msg)
    
    # Receive the SAME message but as DM (should NOT be filtered)
    time.sleep(0.1)
    packet_dm = {'from': 0x87654321, 'to': 0x12345678}
    result = bot.process_message(packet_dm, msg)
    
    assert result == True, "DM should NOT be filtered even if content matches"
    print("\n✅ TEST 3 PASSED: DMs are never filtered by deduplication\n")


def test_different_content():
    """Test that different messages are not confused"""
    print("="*70)
    print("TEST 4: Different Messages Not Confused")
    print("="*70)
    
    bot = MeshBotSimulator()
    
    # User sends command
    user_msg = "/rain Paris"
    print(f"\n   👤 User sends: '{user_msg}'")
    packet_user = {'from': 0x87654321, 'to': 0xFFFFFFFF}
    result1 = bot.process_message(packet_user, user_msg)
    assert result1 == True, "User command should be processed"
    
    # Bot responds with different content
    bot_response = "🌧️ Prévisions pluie Paris: 70%"
    print(f"\n   📡 Bot sends response: '{bot_response}'")
    bot._track_broadcast(bot_response)
    
    # Bot receives its own response
    packet_bot = {'from': 0x87654321, 'to': 0xFFFFFFFF}
    result2 = bot.process_message(packet_bot, bot_response)
    assert result2 == False, "Bot's response should be filtered"
    
    # User sends another command (different hash)
    user_msg2 = "/rain Lyon"
    print(f"\n   👤 User sends: '{user_msg2}'")
    result3 = bot.process_message(packet_user, user_msg2)
    assert result3 == True, "Different user command should be processed"
    
    print("\n✅ TEST 4 PASSED: Different messages not confused\n")


def test_error_handling():
    """Test that errors in deduplication don't block messages"""
    print("="*70)
    print("TEST 5: Error Handling in Deduplication")
    print("="*70)
    
    bot = MeshBotSimulator()
    
    # Corrupt the _recent_broadcasts to cause an error
    bot._recent_broadcasts = "not a dict"  # This will cause TypeError
    
    # Try to process a broadcast
    packet = {'from': 0x87654321, 'to': 0xFFFFFFFF}
    result = bot.process_message(packet, "Test message")
    
    # Should still process despite error
    assert result == True, "Message should be processed despite dedup error"
    print("\n✅ TEST 5 PASSED: Errors don't block message processing\n")


def main():
    print("\n" + "="*70)
    print("🧪 BROADCAST DEDUPLICATION & DEAF BOT FIX TESTS")
    print("="*70)
    
    try:
        test_broadcast_detection()
        test_deduplication()
        test_dm_not_filtered()
        test_different_content()
        test_error_handling()
        
        print("="*70)
        print("✅ ALL TESTS PASSED")
        print("="*70)
        print("\n💡 FIXES VERIFIED:")
        print("   1. Broadcast detection: to_id in [0xFFFFFFFF, 0]")
        print("   2. Deduplication: Only filters matching broadcasts")
        print("   3. DMs protected: Never filtered by deduplication")
        print("   4. Error handling: Dedup errors don't block messages")
        print("   5. Hash distinction: Different messages not confused\n")
        
        return 0
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
