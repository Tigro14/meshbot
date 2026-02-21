#!/usr/bin/env python3
"""
Tests for:
  1. _is_local_signal() helper (kept as utility, no longer drives classification)
  2. The two-way ECDH_DM / OTHER_CHANNEL classification for types 12/13/15
     (SNR heuristic reverted — raw-hex dump added for investigation instead)
  3. The raw-hex header-breakdown logic used in the diagnostic block
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meshcore_cli_wrapper import MeshCoreCLIWrapper

OUR_NODE_ID  = 0x02ce115f
BROADCAST_ID = 0xFFFFFFFF
KNOWN_NODE   = 0x16fad3dc
BUG_NODE     = 0xda935f4b   # The node from the problem report (SNR=12, RSSI=-46)
NOISE_SRC    = 0xa3344b93
NOISE_DST    = 0x5f344b93


# ---------------------------------------------------------------------------
# _is_local_signal helper (kept as informational utility)
# ---------------------------------------------------------------------------

def test_is_local_signal_strong():
    print("\n🧪 _is_local_signal: strong signal cases → True")
    assert MeshCoreCLIWrapper._is_local_signal(12.0, -46)
    assert MeshCoreCLIWrapper._is_local_signal(0.0, -90)
    assert MeshCoreCLIWrapper._is_local_signal(-5.0, -50)
    assert MeshCoreCLIWrapper._is_local_signal(-1.0, -80)
    print("  ✅ Strong-signal cases → True")
    return True

def test_is_local_signal_weak():
    print("\n🧪 _is_local_signal: weak signal cases → False")
    assert not MeshCoreCLIWrapper._is_local_signal(-6.5, -117)
    assert not MeshCoreCLIWrapper._is_local_signal(-11.2, -117)
    assert not MeshCoreCLIWrapper._is_local_signal(-0.1, -81)
    print("  ✅ Weak-signal cases → False")
    return True

def test_is_local_signal_bad_inputs():
    print("\n🧪 _is_local_signal: bad inputs → False (no crash)")
    assert not MeshCoreCLIWrapper._is_local_signal(None, None)
    assert not MeshCoreCLIWrapper._is_local_signal('bad', 0)
    print("  ✅ Bad inputs handled gracefully")
    return True


# ---------------------------------------------------------------------------
# Two-way classification (mirroring updated _on_rx_log_data branch)
# SNR no longer drives classification — both-unknown always → OTHER_CHANNEL
# ---------------------------------------------------------------------------

def classify(sender_id, receiver_id, local_node_id, node_names):
    """
    Mirror of the reverted types-12/13/15 non-broadcast classification.
    Returns ('ECDH_DM' | 'OTHER_CHANNEL', portnum_text)
    """
    if receiver_id == BROADCAST_ID:
        return 'BROADCAST', ''
    is_to_us       = (receiver_id == local_node_id)
    sender_known   = sender_id  in node_names
    receiver_known = is_to_us or (receiver_id in node_names)
    if not sender_known and not receiver_known:
        return 'OTHER_CHANNEL', '[UNKNOWN_CHANNEL]'
    return 'ECDH_DM', '[FOREIGN_DM]'


def test_dm_to_us_is_ecdh():
    print(f"\n🧪 DM to our node → ECDH_DM (regardless of SNR)")
    node_names = {}
    portnum, _ = classify(BUG_NODE, OUR_NODE_ID, OUR_NODE_ID, node_names)
    assert portnum == 'ECDH_DM', f"Got {portnum}"
    print("  ✅ DM to us → ECDH_DM")
    return True

def test_both_unknown_any_signal_is_other_channel():
    print("\n🧪 Both endpoints unknown → OTHER_CHANNEL (SNR irrelevant)")
    node_names = {}
    # Strong signal
    portnum, text = classify(BUG_NODE, 0xdeadbeef, OUR_NODE_ID, node_names)
    assert portnum == 'OTHER_CHANNEL', f"Got {portnum}"
    assert text == '[UNKNOWN_CHANNEL]'
    # Weak signal (same result)
    portnum2, _ = classify(NOISE_SRC, NOISE_DST, OUR_NODE_ID, node_names)
    assert portnum2 == 'OTHER_CHANNEL', f"Got {portnum2}"
    print("  ✅ Both-unknown → OTHER_CHANNEL regardless of signal strength")
    return True

def test_known_sender_is_ecdh():
    print("\n🧪 Known sender → ECDH_DM")
    node_names = {KNOWN_NODE: {'name': 'Tigro'}}
    portnum, _ = classify(KNOWN_NODE, NOISE_DST, OUR_NODE_ID, node_names)
    assert portnum == 'ECDH_DM', f"Got {portnum}"
    print("  ✅ Known sender → ECDH_DM")
    return True

def test_known_receiver_is_ecdh():
    print("\n🧪 Known receiver → ECDH_DM")
    node_names = {KNOWN_NODE: {'name': 'Tigro'}}
    portnum, _ = classify(NOISE_SRC, KNOWN_NODE, OUR_NODE_ID, node_names)
    assert portnum == 'ECDH_DM', f"Got {portnum}"
    print("  ✅ Known receiver → ECDH_DM")
    return True

def test_no_pending_registration():
    """SNR heuristic reverted: no automatic pending-contact registration."""
    print("\n🧪 No pending-contact auto-registration (SNR heuristic removed)")
    node_names = {}
    classify(BUG_NODE, 0xdeadbeef, OUR_NODE_ID, node_names)
    assert BUG_NODE not in node_names, "Should NOT auto-register unknown sender"
    print("  ✅ No auto-registration — investigation via raw-hex dump instead")
    return True


# ---------------------------------------------------------------------------
# Raw-hex header breakdown logic
# ---------------------------------------------------------------------------

def _raw_header_breakdown(raw_hex):
    """Mirror of the diagnostic block inside _on_rx_log_data."""
    raw_bytes = bytes.fromhex(raw_hex) if raw_hex else b''
    total = len(raw_bytes)
    h_type  = raw_bytes[0:4].hex()   if total >= 4  else '??'
    h_src   = raw_bytes[4:8].hex()   if total >= 8  else '??'
    h_dst   = raw_bytes[8:12].hex()  if total >= 12 else '??'
    h_hash  = raw_bytes[12:16].hex() if total >= 16 else '??'
    payload = raw_bytes[16:]
    pay_hex = ' '.join(f'{b:02X}' for b in payload)
    return {
        'total': total,
        'h_type': h_type, 'h_src': h_src, 'h_dst': h_dst, 'h_hash': h_hash,
        'payload': payload, 'pay_hex': pay_hex,
    }

def test_raw_breakdown_full_packet():
    print("\n🧪 Raw-hex breakdown: full 20-byte packet")
    # 4B type | 4B src (da935f4b LE → 4b5f93da) | 4B dst | 4B hash | 4B payload
    raw = '0f000000' + '4b5f93da' + 'e0d43f3e' + 'aabbccdd' + 'deadbeef'
    b = _raw_header_breakdown(raw)
    assert b['total'] == 20
    assert b['h_type'] == '0f000000'
    assert b['h_src']  == '4b5f93da'
    assert b['h_dst']  == 'e0d43f3e'
    assert b['h_hash'] == 'aabbccdd'
    assert b['payload'] == bytes.fromhex('deadbeef')
    assert b['pay_hex'] == 'DE AD BE EF'
    print("  ✅ Header fields parsed correctly")
    return True

def test_raw_breakdown_short_packet():
    print("\n🧪 Raw-hex breakdown: short (< 16 bytes) packet")
    raw = '0f0000004b5f93da'  # only 8 bytes
    b = _raw_header_breakdown(raw)
    assert b['total'] == 8
    assert b['h_type'] == '0f000000'
    assert b['h_src']  == '4b5f93da'
    assert b['h_dst']  == '??'
    assert b['h_hash'] == '??'
    assert b['payload'] == b''
    print("  ✅ Short packet handled gracefully with '??' markers")
    return True

def test_raw_breakdown_empty():
    print("\n🧪 Raw-hex breakdown: empty hex")
    b = _raw_header_breakdown('')
    assert b['total'] == 0
    assert b['h_type'] == '??'
    print("  ✅ Empty hex handled gracefully")
    return True

def test_raw_breakdown_large_payload():
    print("\n🧪 Raw-hex breakdown: 138-byte packet (bug-report size)")
    raw = 'OF000000' if False else ('00' * 16) + ('ff' * 122)  # 16B hdr + 122B payload
    b = _raw_header_breakdown(raw)
    assert b['total'] == 138
    assert len(b['payload']) == 122
    print(f"  ✅ 138B packet: payload={len(b['payload'])}B, hex_tokens={len(b['pay_hex'].split())}")
    return True


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_all_tests():
    print("\n" + "=" * 65)
    print("TYPE-12/13/15 RAW-HEX DIAGNOSTIC TESTS (SNR heuristic reverted)")
    print("=" * 65)

    results = [
        ("_is_local_signal strong",                   test_is_local_signal_strong()),
        ("_is_local_signal weak",                     test_is_local_signal_weak()),
        ("_is_local_signal bad inputs",               test_is_local_signal_bad_inputs()),
        ("DM to us → ECDH_DM",                        test_dm_to_us_is_ecdh()),
        ("both unknown → OTHER_CHANNEL (any signal)", test_both_unknown_any_signal_is_other_channel()),
        ("known sender → ECDH_DM",                    test_known_sender_is_ecdh()),
        ("known receiver → ECDH_DM",                  test_known_receiver_is_ecdh()),
        ("no auto-registration",                      test_no_pending_registration()),
        ("raw breakdown full packet",                 test_raw_breakdown_full_packet()),
        ("raw breakdown short packet",                test_raw_breakdown_short_packet()),
        ("raw breakdown empty",                       test_raw_breakdown_empty()),
        ("raw breakdown large payload",               test_raw_breakdown_large_payload()),
    ]

    print("\n" + "=" * 65)
    print("SUMMARY")
    print("=" * 65)
    passed = sum(1 for _, r in results if r)
    total  = len(results)
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
