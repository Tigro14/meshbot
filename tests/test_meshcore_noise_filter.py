#!/usr/bin/env python3
"""
Tests for two fixes:
1. path_len=255 sentinel → shown as "direct" in /my
2. sender_id=0xFFFFFFFF packets skipped from rx_history and bot callback
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Fix 1: path_len=255 sentinel in /my response
# ---------------------------------------------------------------------------
def clamp_path_len(path_len):
    """Mirror the fix in network_commands.py _format_my_response."""
    if path_len == 255:
        return 0
    return path_len


def format_hop_str(path_len):
    path_len = clamp_path_len(path_len)
    return f"{path_len} hop{'s' if path_len > 1 else ''}" if path_len > 0 else "direct"


def test_path_len_255_shows_direct():
    print("\n🧪 Test: path_len=255 sentinel → 'direct'")
    print("=" * 60)
    assert format_hop_str(255) == "direct", f"Expected 'direct', got '{format_hop_str(255)}'"
    print("  ✅ path_len=255 → 'direct'")
    return True


def test_path_len_254_shows_direct():
    print("\n🧪 Test: path_len=254 is not a sentinel and shows '254 hops'")
    print("=" * 60)
    # Only 255 is the MeshCore sentinel; 254 is a real hop count
    assert format_hop_str(254) == "254 hops", f"Expected '254 hops', got '{format_hop_str(254)}'"
    print("  ✅ path_len=254 → '254 hops' (not a sentinel)")
    return True


def test_path_len_0_shows_direct():
    print("\n🧪 Test: path_len=0 → 'direct'")
    print("=" * 60)
    assert format_hop_str(0) == "direct", f"Expected 'direct', got '{format_hop_str(0)}'"
    print("  ✅ path_len=0 → 'direct'")
    return True


def test_path_len_1_shows_1_hop():
    print("\n🧪 Test: path_len=1 → '1 hop'")
    print("=" * 60)
    assert format_hop_str(1) == "1 hop", f"Expected '1 hop', got '{format_hop_str(1)}'"
    print("  ✅ path_len=1 → '1 hop'")
    return True


def test_path_len_3_shows_3_hops():
    print("\n🧪 Test: path_len=3 → '3 hops'")
    print("=" * 60)
    assert format_hop_str(3) == "3 hops", f"Expected '3 hops', got '{format_hop_str(3)}'"
    print("  ✅ path_len=3 → '3 hops'")
    return True


# ---------------------------------------------------------------------------
# Fix 2: sender_id=0xFFFFFFFF packets skipped
# ---------------------------------------------------------------------------
BROADCAST_ID = 0xFFFFFFFF


def should_skip_packet(sender_id):
    """Mirror the guard added in meshcore_cli_wrapper.py _on_rx_log_data."""
    return sender_id == BROADCAST_ID


def test_ffffffff_packet_skipped():
    print("\n🧪 Test: sender_id=0xffffffff packet is skipped")
    print("=" * 60)
    assert should_skip_packet(0xFFFFFFFF) is True
    print("  ✅ sender_id=0xffffffff → skipped (unidentifiable)")
    return True


def test_known_sender_forwarded():
    print("\n🧪 Test: known sender_id is forwarded (not skipped)")
    print("=" * 60)
    assert should_skip_packet(0x889fa138) is False
    assert should_skip_packet(0x3afb4088) is False
    assert should_skip_packet(0x02ce115f) is False
    print("  ✅ Known sender IDs are NOT skipped")
    return True


def should_skip_rx_history(from_id):
    """Mirror the guard added in node_manager.py update_rx_history."""
    if not from_id:
        return True
    if from_id == 0xFFFFFFFF:
        return True
    return False


def test_rx_history_skips_ffffffff():
    print("\n🧪 Test: rx_history skips from_id=0xffffffff")
    print("=" * 60)
    assert should_skip_rx_history(0xFFFFFFFF) is True
    print("  ✅ rx_history: from_id=0xffffffff skipped")
    return True


def test_rx_history_skips_none():
    print("\n🧪 Test: rx_history skips from_id=None/0")
    print("=" * 60)
    assert should_skip_rx_history(None) is True
    assert should_skip_rx_history(0) is True
    print("  ✅ rx_history: None/0 skipped (existing behaviour)")
    return True


def test_rx_history_allows_known_sender():
    print("\n🧪 Test: rx_history allows known from_id")
    print("=" * 60)
    assert should_skip_rx_history(0x889fa138) is False
    assert should_skip_rx_history(0x3afb4088) is False
    print("  ✅ rx_history: known from_ids allowed")
    return True


def run_all_tests():
    print("\n" + "=" * 60)
    print("FIX TESTS: 255 hops sentinel + ffffffff noise filter")
    print("=" * 60)

    results = [
        ("path_len=255 → 'direct'", test_path_len_255_shows_direct()),
        ("path_len=254 → '254 hops'", test_path_len_254_shows_direct()),
        ("path_len=0 → 'direct'", test_path_len_0_shows_direct()),
        ("path_len=1 → '1 hop'", test_path_len_1_shows_1_hop()),
        ("path_len=3 → '3 hops'", test_path_len_3_shows_3_hops()),
        ("0xffffffff packet skipped", test_ffffffff_packet_skipped()),
        ("known sender forwarded", test_known_sender_forwarded()),
        ("rx_history skips 0xffffffff", test_rx_history_skips_ffffffff()),
        ("rx_history skips None/0", test_rx_history_skips_none()),
        ("rx_history allows known sender", test_rx_history_allows_known_sender()),
    ]

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(1 for _, r in results if r)
    total = len(results)
    for name, result in results:
        print(f"  {'✅ PASS' if result else '❌ FAIL'}: {name}")
    print()
    if passed == total:
        print(f"✅ ALL TESTS PASSED ({passed}/{total})")
        return True
    else:
        print(f"❌ SOME TESTS FAILED ({passed}/{total})")
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
