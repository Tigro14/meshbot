#!/usr/bin/env python3
"""
Tests for the directed-relay-noise → OTHER_CHANNEL reclassification.

Problem: types 12/13/15 with non-broadcast receiver_id were all classified as
ECDH_DM regardless of whether either endpoint belongs to our network.  In
practice, a large fraction of these are relay hops from another MeshCore
network passing through our area.  Both sender and receiver IDs exhibit the
"sliding-window" byte pattern (consecutive raw bytes from the relay stream).

Fix: in `_on_rx_log_data` (types 12/13/15, non-broadcast receiver):
  - is_to_us = (receiver_id == local_node_id)
  - sender_known  = sender_id in node_manager.node_names
  - receiver_known = is_to_us OR receiver_id in node_manager.node_names
  - if not sender_known and not receiver_known → OTHER_CHANNEL / [UNKNOWN_CHANNEL]
  - else → ECDH_DM / [FOREIGN_DM]  (genuine DM involving known nodes)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUR_NODE_ID  = 0x02ce115f   # Example local node
BROADCAST_ID = 0xFFFFFFFF

# ── realistic sliding-window ECDH_DM IDs from the bug report ──────────────
RELAY_NOISE_IDS = [
    0xa3344b93, 0x5f344b93, 0xb2344b93, 0x46344b93,
    0x344b933d, 0x4a4b933d, 0x9ab14282, 0x9ab142cd,
    0x02f2cd42, 0xb65f3469, 0x38695f4a, 0x6df9cd34,
]

# ── two real contacts in our mesh ──────────────────────────────────────────
KNOWN_NODE_A = 0x16fad3dc   # Tigro's node
KNOWN_NODE_B = 0x3e3fd4e0   # Another known contact


# ---------------------------------------------------------------------------
# Mirror of the fixed classification logic in _on_rx_log_data
# ---------------------------------------------------------------------------

def classify_directed_packet(sender_id, receiver_id, local_node_id, node_names):
    """
    Mirrors the updated types-12/13/15 non-broadcast branch in _on_rx_log_data.
    Returns ('ECDH_DM', '[FOREIGN_DM]') or ('OTHER_CHANNEL', '[UNKNOWN_CHANNEL]').
    """
    if receiver_id == BROADCAST_ID:
        return 'BROADCAST', ''  # handled by the PSK decryption path, not here

    is_to_us       = (receiver_id == local_node_id)
    sender_known   = sender_id  in node_names
    receiver_known = is_to_us or (receiver_id in node_names)

    if not sender_known and not receiver_known:
        return 'OTHER_CHANNEL', '[UNKNOWN_CHANNEL]'
    return 'ECDH_DM', '[FOREIGN_DM]'


# ---------------------------------------------------------------------------
# Tests – relay noise (both endpoints unknown)
# ---------------------------------------------------------------------------

def test_both_unknown_is_other_channel():
    print("\n🧪 Test: both endpoints unknown → OTHER_CHANNEL")
    node_names = {}  # empty — no known contacts
    for sender_id in RELAY_NOISE_IDS:
        # Use another noise ID as receiver (simulates relay pair)
        receiver_id = RELAY_NOISE_IDS[(RELAY_NOISE_IDS.index(sender_id) + 1) % len(RELAY_NOISE_IDS)]
        portnum, text = classify_directed_packet(sender_id, receiver_id, OUR_NODE_ID, node_names)
        assert portnum == 'OTHER_CHANNEL', (
            f"Expected OTHER_CHANNEL for {sender_id:08x}→{receiver_id:08x}, got {portnum}"
        )
        assert text == '[UNKNOWN_CHANNEL]'
    print(f"  ✅ All {len(RELAY_NOISE_IDS)} relay-noise pairs → OTHER_CHANNEL")
    return True


def test_unknown_sender_unknown_receiver_is_other_channel():
    print("\n🧪 Test: specific bug-report IDs all → OTHER_CHANNEL with empty node_names")
    node_names = {}
    from itertools import combinations
    tested = 0
    for s, r in list(combinations(RELAY_NOISE_IDS, 2))[:10]:
        portnum, _ = classify_directed_packet(s, r, OUR_NODE_ID, node_names)
        assert portnum == 'OTHER_CHANNEL', f"Expected OTHER_CHANNEL, got {portnum}"
        tested += 1
    print(f"  ✅ {tested} sliding-window combinations → OTHER_CHANNEL")
    return True


# ---------------------------------------------------------------------------
# Tests – genuine ECDH DMs (at least one known endpoint)
# ---------------------------------------------------------------------------

def test_dm_to_us_is_ecdh_dm():
    print("\n🧪 Test: receiver == our node → ECDH_DM (DM addressed to us)")
    node_names = {}  # even with no known contacts
    for sender_id in RELAY_NOISE_IDS:
        portnum, text = classify_directed_packet(sender_id, OUR_NODE_ID, OUR_NODE_ID, node_names)
        assert portnum == 'ECDH_DM', f"Expected ECDH_DM, got {portnum}"
        assert text == '[FOREIGN_DM]'
    print(f"  ✅ DMs addressed to our node → ECDH_DM regardless of sender")
    return True


def test_known_sender_is_ecdh_dm():
    print("\n🧪 Test: sender is a known contact → ECDH_DM")
    node_names = {KNOWN_NODE_A: {'name': 'Tigro', 'shortName': 'TGR'}}
    portnum, text = classify_directed_packet(
        KNOWN_NODE_A, 0xdeadbeef, OUR_NODE_ID, node_names
    )
    assert portnum == 'ECDH_DM', f"Expected ECDH_DM, got {portnum}"
    assert text == '[FOREIGN_DM]'
    print(f"  ✅ Known sender → ECDH_DM")
    return True


def test_known_receiver_is_ecdh_dm():
    print("\n🧪 Test: receiver is a known contact (not us) → ECDH_DM")
    node_names = {KNOWN_NODE_B: {'name': 'OtherNode', 'shortName': 'OTH'}}
    portnum, text = classify_directed_packet(
        0xdeadbeef, KNOWN_NODE_B, OUR_NODE_ID, node_names
    )
    assert portnum == 'ECDH_DM', f"Expected ECDH_DM, got {portnum}"
    assert text == '[FOREIGN_DM]'
    print(f"  ✅ Known receiver (not us) → ECDH_DM")
    return True


def test_both_known_is_ecdh_dm():
    print("\n🧪 Test: both endpoints known → ECDH_DM")
    node_names = {
        KNOWN_NODE_A: {'name': 'Tigro',     'shortName': 'TGR'},
        KNOWN_NODE_B: {'name': 'OtherNode', 'shortName': 'OTH'},
    }
    portnum, text = classify_directed_packet(
        KNOWN_NODE_A, KNOWN_NODE_B, OUR_NODE_ID, node_names
    )
    assert portnum == 'ECDH_DM', f"Expected ECDH_DM, got {portnum}"
    print(f"  ✅ Both known → ECDH_DM")
    return True


def test_dm_to_us_from_unknown_is_still_ecdh_dm():
    print("\n🧪 Test: DM to us from unknown sender → ECDH_DM (new contact)")
    node_names = {}
    portnum, text = classify_directed_packet(
        0xdeadbeef, OUR_NODE_ID, OUR_NODE_ID, node_names
    )
    assert portnum == 'ECDH_DM', f"Expected ECDH_DM, got {portnum}"
    print(f"  ✅ DM to us from unknown sender → ECDH_DM (is_to_us overrides)")
    return True


# ---------------------------------------------------------------------------
# Tests – broadcast path unaffected
# ---------------------------------------------------------------------------

def test_broadcast_receiver_not_in_scope():
    print("\n🧪 Test: broadcast receiver → BROADCAST (not handled here)")
    node_names = {}
    portnum, _ = classify_directed_packet(
        RELAY_NOISE_IDS[0], BROADCAST_ID, OUR_NODE_ID, node_names
    )
    assert portnum == 'BROADCAST'
    print(f"  ✅ Broadcast receiver → BROADCAST (PSK path, unaffected)")
    return True


# ---------------------------------------------------------------------------
# Tests – edge cases
# ---------------------------------------------------------------------------

def test_no_node_manager_treats_all_as_unknown():
    print("\n🧪 Test: node_names=None treated as no known contacts → OTHER_CHANNEL")
    # When node_manager is None we can't look up nodes; receiver != our ID → OTHER_CHANNEL
    portnum, _ = classify_directed_packet(
        RELAY_NOISE_IDS[0], RELAY_NOISE_IDS[1],
        local_node_id=OUR_NODE_ID,
        node_names={}  # empty dict == no known contacts
    )
    assert portnum == 'OTHER_CHANNEL'
    print(f"  ✅ No known nodes → OTHER_CHANNEL")
    return True


def test_node_id_zero_not_treated_as_ours():
    print("\n🧪 Test: local_node_id=None doesn't misclassify receiver=0 as 'to us'")
    # When local_node_id is None, is_to_us should always be False
    # (receiver_id == None is always False in Python for int comparisons)
    portnum, _ = classify_directed_packet(
        RELAY_NOISE_IDS[0], 0,
        local_node_id=None,
        node_names={}
    )
    # receiver_id=0 is NOT broadcast and NOT our node → OTHER_CHANNEL
    assert portnum == 'OTHER_CHANNEL'
    print(f"  ✅ local_node_id=None → is_to_us=False → OTHER_CHANNEL for unknown receiver=0")
    return True


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_all_tests():
    print("\n" + "=" * 60)
    print("DIRECTED RELAY NOISE → OTHER_CHANNEL FILTER TESTS")
    print("=" * 60)

    results = [
        ("both endpoints unknown → OTHER_CHANNEL",           test_both_unknown_is_other_channel()),
        ("sliding-window ID combos → OTHER_CHANNEL",         test_unknown_sender_unknown_receiver_is_other_channel()),
        ("DM to our node → ECDH_DM",                        test_dm_to_us_is_ecdh_dm()),
        ("known sender → ECDH_DM",                           test_known_sender_is_ecdh_dm()),
        ("known receiver (not us) → ECDH_DM",               test_known_receiver_is_ecdh_dm()),
        ("both known → ECDH_DM",                             test_both_known_is_ecdh_dm()),
        ("DM to us from unknown sender → ECDH_DM",           test_dm_to_us_from_unknown_is_still_ecdh_dm()),
        ("broadcast receiver → BROADCAST (unaffected)",      test_broadcast_receiver_not_in_scope()),
        ("no known nodes → OTHER_CHANNEL",                   test_no_node_manager_treats_all_as_unknown()),
        ("local_node_id=None → no false is_to_us",          test_node_id_zero_not_treated_as_ours()),
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
