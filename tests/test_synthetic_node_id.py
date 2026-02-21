#!/usr/bin/env python3
"""
Tests for _synthetic_node_id() and the channel-message sender-ID fallback fix.

Problem: When a public-channel CHANNEL_MSG_RECV event has no pubkey_prefix and
the sender is not in node_names, the code fell back to sender_id = 0xFFFFFFFF
(broadcast address), creating "Node-ffffffff" rows in the DB.

Fix:
  1. Added _synthetic_node_id(name) helper in MeshCoreCLIWrapper: deterministic
     CRC32-based ID from the sender name, never 0 / 0xFFFFFFFF / 0xFFFFFFFE.
  2. In _on_channel_message final fallback: when message has "Name: text" prefix
     and sender_id is still None, derive synthetic ID from extracted name and
     register it in node_manager.node_names so future messages are consistent.
  3. In _on_contact_message (DM) final fallback: use synthetic ID from
     pubkey_prefix CRC instead of 0xFFFFFFFF when pubkey is available but too
     short to derive the real node ID.
"""
import sys
import os
import zlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BROADCAST_ID  = 0xFFFFFFFF
LOCAL_SENTINEL = 0xFFFFFFFE


# ---------------------------------------------------------------------------
# Mirror of _synthetic_node_id() from meshcore_cli_wrapper.py
# ---------------------------------------------------------------------------

def synthetic_node_id(name):
    """
    Deterministic CRC32-based node ID from a sender name.
    Mirrors MeshCoreCLIWrapper._synthetic_node_id().
    """
    crc = zlib.crc32(name.encode('utf-8', errors='replace')) & 0xFFFFFFFF
    if crc in (0, BROADCAST_ID, LOCAL_SENTINEL):
        crc = 0x00000001
    return crc


# ---------------------------------------------------------------------------
# Mirror of channel-message sender_id final-fallback logic
# ---------------------------------------------------------------------------

def channel_sender_id_fallback(message_text, node_names=None):
    """
    Mirror the final fallback block in _on_channel_message after all normal
    resolution methods have failed (sender_id is still None).

    Returns (sender_id, registered_name) where registered_name is the name
    stored in node_names (if any), else None.
    """
    if node_names is None:
        node_names = {}

    registered_name = None

    if ': ' in message_text:
        extracted_name = message_text.split(': ', 1)[0]
        sender_id = synthetic_node_id(extracted_name)
        if sender_id not in node_names:
            node_names[sender_id] = {
                'name': extracted_name,
                'shortName': None,
                'hwModel': None,
                'lat': None, 'lon': None, 'alt': None,
                'last_update': None,
            }
            registered_name = extracted_name
        return sender_id, registered_name
    else:
        return BROADCAST_ID, None  # Truly unknown, no name prefix


# ---------------------------------------------------------------------------
# Tests – _synthetic_node_id
# ---------------------------------------------------------------------------

def test_synthetic_id_is_deterministic():
    print("\n🧪 Test: same name always gives same ID")
    id1 = synthetic_node_id("RR49F1")
    id2 = synthetic_node_id("RR49F1")
    assert id1 == id2, f"IDs differ: {id1} != {id2}"
    print(f"  ✅ 'RR49F1' → 0x{id1:08x} (stable)")
    return True


def test_synthetic_id_different_names_differ():
    print("\n🧪 Test: different names give different IDs")
    id1 = synthetic_node_id("RR49F1")
    id2 = synthetic_node_id("Étienne T-Deck")
    id3 = synthetic_node_id("glu 📟")
    assert id1 != id2 != id3, "IDs collided"
    assert id1 != id3
    print(f"  ✅ 'RR49F1'={hex(id1)}, 'Étienne T-Deck'={hex(id2)}, 'glu 📟'={hex(id3)}")
    return True


def test_synthetic_id_never_broadcast():
    print("\n🧪 Test: synthetic ID is never the broadcast address")
    # Generate a large batch of IDs and verify none are reserved values
    names = [f"Node{i}" for i in range(1000)] + ["RR49F1", "Étienne T-Deck", "glu 📟", "Random_Mobi"]
    for name in names:
        nid = synthetic_node_id(name)
        assert nid != BROADCAST_ID, f"Got broadcast for '{name}'"
        assert nid != LOCAL_SENTINEL, f"Got local-sentinel for '{name}'"
        assert nid != 0, f"Got zero for '{name}'"
    print(f"  ✅ None of {len(names)} names produces a reserved ID")
    return True


def test_synthetic_id_unicode_name():
    print("\n🧪 Test: unicode sender name produces valid ID")
    nid = synthetic_node_id("glu 📟")
    assert isinstance(nid, int)
    assert 0 < nid < 0xFFFFFFFF
    print(f"  ✅ 'glu 📟' → 0x{nid:08x}")
    return True


# ---------------------------------------------------------------------------
# Tests – channel_sender_id_fallback
# ---------------------------------------------------------------------------

def test_fallback_extracts_name_prefix():
    print("\n🧪 Test: 'Name: message' → synthetic ID derived from 'Name'")
    node_names = {}
    sid, reg = channel_sender_id_fallback("RR49F1: @[DAN94] entendu !", node_names)
    expected = synthetic_node_id("RR49F1")
    assert sid == expected, f"Expected 0x{expected:08x}, got 0x{sid:08x}"
    assert sid != BROADCAST_ID, "Must not be broadcast"
    assert reg == "RR49F1"
    print(f"  ✅ 'RR49F1: …' → 0x{sid:08x}")
    return True


def test_fallback_no_prefix_gives_broadcast():
    print("\n🧪 Test: message without 'Name: ' prefix → 0xFFFFFFFF (truly unknown)")
    node_names = {}
    sid, reg = channel_sender_id_fallback("no colon here", node_names)
    assert sid == BROADCAST_ID, f"Expected broadcast, got 0x{sid:08x}"
    assert reg is None
    print("  ✅ No prefix → 0xFFFFFFFF (only acceptable case)")
    return True


def test_fallback_registers_name_in_node_names():
    print("\n🧪 Test: extracted name is registered in node_names")
    node_names = {}
    sid, _ = channel_sender_id_fallback("Étienne T-Deck: Salut 👋", node_names)
    assert sid in node_names, "Name not registered"
    assert node_names[sid]['name'] == "Étienne T-Deck"
    print(f"  ✅ 'Étienne T-Deck' registered as 0x{sid:08x}")
    return True


def test_fallback_consistent_across_messages():
    print("\n🧪 Test: two messages from same sender give same ID")
    node_names = {}
    sid1, _ = channel_sender_id_fallback("glu 📟: Coucou !", node_names)
    sid2, _ = channel_sender_id_fallback("glu 📟: À bientôt", node_names)
    assert sid1 == sid2, f"Inconsistent: 0x{sid1:08x} vs 0x{sid2:08x}"
    print(f"  ✅ Both 'glu 📟' messages → 0x{sid1:08x}")
    return True


def test_fallback_does_not_overwrite_existing_node():
    print("\n🧪 Test: existing node_names entry is not overwritten by fallback")
    real_id = 0x12345678
    node_names = {real_id: {'name': 'RealName', 'shortName': 'RN', 'hwModel': None,
                             'lat': None, 'lon': None, 'alt': None, 'last_update': None}}
    # Put a pre-existing mapping for the synthetic ID (same name hypothetically)
    sid = synthetic_node_id("RR49F1")
    original_entry = {'name': 'pre-existing', 'shortName': None, 'hwModel': None,
                      'lat': None, 'lon': None, 'alt': None, 'last_update': None}
    node_names[sid] = original_entry
    _, reg = channel_sender_id_fallback("RR49F1: test", node_names)
    # Should NOT re-register (returns None for registered_name)
    assert reg is None, "Should not overwrite existing entry"
    assert node_names[sid]['name'] == 'pre-existing', "Existing entry was overwritten"
    print("  ✅ Existing node_names entry preserved")
    return True


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_all_tests():
    print("\n" + "=" * 60)
    print("SYNTHETIC NODE ID / CHANNEL FALLBACK TESTS")
    print("=" * 60)

    results = [
        ("synthetic ID is deterministic",               test_synthetic_id_is_deterministic()),
        ("different names → different IDs",             test_synthetic_id_different_names_differ()),
        ("synthetic ID never 0/broadcast/sentinel",     test_synthetic_id_never_broadcast()),
        ("unicode name produces valid ID",              test_synthetic_id_unicode_name()),
        ("fallback extracts 'Name: text' prefix",       test_fallback_extracts_name_prefix()),
        ("no prefix → 0xFFFFFFFF (only ok case)",       test_fallback_no_prefix_gives_broadcast()),
        ("extracted name registered in node_names",     test_fallback_registers_name_in_node_names()),
        ("two msgs from same sender → same ID",         test_fallback_consistent_across_messages()),
        ("existing node_names entry not overwritten",   test_fallback_does_not_overwrite_existing_node()),
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
