#!/usr/bin/env python3
"""
Tests for ECDH DM foreign-packet classification.

Problem: MeshCore encrypted payload types 12/13/15 with a specific (non-broadcast)
receiver_id are private ECDH DMs between *other* nodes.  Attempting PSK decryption
on them always produces garbage, which was being stored in the DB as '[ENCRYPTED]'
or garbled text (e.g. 'γD', '1plH') mixed with real traffic.

Fix:
  1. meshcore_cli_wrapper.py – when payload_type in (12,13,15) AND receiver_id is
     not broadcast (0xFFFFFFFF), set portnum='ECDH_DM' / packet_text='[FOREIGN_DM]'
     and skip the pointless PSK decryption attempt.
  2. traffic_monitor.py – safety-net: any meshcore TEXT_MESSAGE_APP arriving with
     message='[ENCRYPTED]' and a non-broadcast to_id is reclassified to ECDH_DM /
     '[FOREIGN_DM]' before saving to the DB.

Both fixes leave the packet in the DB (for statistics) but under the distinct
'ECDH_DM' type so it does not pollute the TEXT_MESSAGE_APP view.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BROADCAST_ID = 0xFFFFFFFF
OUR_NODE_ID  = 0x02ce115f   # Example local node


# ---------------------------------------------------------------------------
# Helpers that mirror the new logic in meshcore_cli_wrapper.py
# ---------------------------------------------------------------------------

def classify_rx_log_packet(payload_type_value, receiver_id):
    """
    Mirror the classification added in meshcore_cli_wrapper._on_rx_log_data()
    for payload types 12/13/15.

    Returns: (portnum, packet_text)
    """
    if payload_type_value not in (12, 13, 15):
        return 'UNKNOWN_APP', None

    if receiver_id != BROADCAST_ID:
        # Private ECDH DM – label without attempting decryption
        return 'ECDH_DM', '[FOREIGN_DM]'

    # Broadcast – PSK decryption would be attempted (not modelled here)
    return 'TEXT_MESSAGE_APP', None   # placeholder: decryption result TBD


# ---------------------------------------------------------------------------
# Helpers that mirror the safety net in traffic_monitor.add_packet()
# ---------------------------------------------------------------------------

def safety_net_reclassify(source, packet_type, message_text, to_id):
    """
    Mirror the updated safety-net block in traffic_monitor.add_packet().
    Returns (new_packet_type, new_message_text).
    """
    if (source == 'meshcore' and
            packet_type == 'TEXT_MESSAGE_APP' and
            message_text == '[ENCRYPTED]'):
        if to_id not in (BROADCAST_ID, 0):
            return 'ECDH_DM', '[FOREIGN_DM]'
        else:
            return 'OTHER_CHANNEL', '[UNKNOWN_CHANNEL]'
    return packet_type, message_text


# ---------------------------------------------------------------------------
# Tests – meshcore_cli_wrapper classification
# ---------------------------------------------------------------------------

def test_type12_directed_is_ecdh_dm():
    print("\n🧪 Test: type=12 directed → ECDH_DM")
    portnum, text = classify_rx_log_packet(12, 0x3e3fd4e0)
    assert portnum == 'ECDH_DM', f"Expected ECDH_DM, got {portnum}"
    assert text == '[FOREIGN_DM]', f"Expected [FOREIGN_DM], got {text}"
    print("  ✅ type=12 directed → ECDH_DM / [FOREIGN_DM]")
    return True


def test_type13_directed_is_ecdh_dm():
    print("\n🧪 Test: type=13 directed → ECDH_DM")
    portnum, text = classify_rx_log_packet(13, 0x3fd4e056)
    assert portnum == 'ECDH_DM'
    assert text == '[FOREIGN_DM]'
    print("  ✅ type=13 directed → ECDH_DM / [FOREIGN_DM]")
    return True


def test_type15_directed_is_ecdh_dm():
    print("\n🧪 Test: type=15 directed → ECDH_DM")
    portnum, text = classify_rx_log_packet(15, 0xd4e056e6)
    assert portnum == 'ECDH_DM'
    assert text == '[FOREIGN_DM]'
    print("  ✅ type=15 directed → ECDH_DM / [FOREIGN_DM]")
    return True


def test_type15_broadcast_tries_psk():
    print("\n🧪 Test: type=15 broadcast → PSK decryption path (not ECDH_DM)")
    portnum, text = classify_rx_log_packet(15, BROADCAST_ID)
    assert portnum != 'ECDH_DM', f"Broadcast should NOT be ECDH_DM, got {portnum}"
    print(f"  ✅ type=15 broadcast → {portnum} (PSK path, not labelled ECDH_DM)")
    return True


def test_type1_text_message_unaffected():
    print("\n🧪 Test: type=1 (TEXT_MESSAGE_APP) unaffected")
    portnum, text = classify_rx_log_packet(1, 0x3e3fd4e0)
    assert portnum == 'UNKNOWN_APP'  # type=1 is handled in a different branch
    print("  ✅ type=1 is outside this branch – unaffected")
    return True


# ---------------------------------------------------------------------------
# Tests – traffic_monitor safety net
# ---------------------------------------------------------------------------

def test_safetynet_reclassifies_encrypted_directed():
    print("\n🧪 Test: safety-net reclassifies [ENCRYPTED] directed meshcore DM")
    pt, msg = safety_net_reclassify('meshcore', 'TEXT_MESSAGE_APP', '[ENCRYPTED]', 0x3e3fd4e0)
    assert pt == 'ECDH_DM', f"Expected ECDH_DM, got {pt}"
    assert msg == '[FOREIGN_DM]', f"Expected [FOREIGN_DM], got {msg}"
    print("  ✅ [ENCRYPTED] directed meshcore → ECDH_DM / [FOREIGN_DM]")
    return True


def test_safetynet_broadcast_encrypted_becomes_other_channel():
    print("\n🧪 Test: safety-net reclassifies broadcast [ENCRYPTED] as OTHER_CHANNEL")
    pt, msg = safety_net_reclassify('meshcore', 'TEXT_MESSAGE_APP', '[ENCRYPTED]', BROADCAST_ID)
    assert pt == 'OTHER_CHANNEL', f"Broadcast should become OTHER_CHANNEL, got {pt}"
    assert msg == '[UNKNOWN_CHANNEL]'
    print("  ✅ [ENCRYPTED] broadcast → OTHER_CHANNEL / [UNKNOWN_CHANNEL]")
    return True


def test_safetynet_keeps_meshtastic_encrypted():
    print("\n🧪 Test: safety-net does not affect Meshtastic [ENCRYPTED] packets")
    pt, msg = safety_net_reclassify('local', 'TEXT_MESSAGE_APP', '[ENCRYPTED]', 0x3e3fd4e0)
    assert pt == 'TEXT_MESSAGE_APP', f"Meshtastic packet should stay TEXT_MESSAGE_APP, got {pt}"
    print("  ✅ Meshtastic [ENCRYPTED] directed → unchanged (safety-net does not apply)")
    return True


def test_safetynet_keeps_clear_messages():
    print("\n🧪 Test: safety-net does not touch clear-text meshcore messages")
    pt, msg = safety_net_reclassify('meshcore', 'TEXT_MESSAGE_APP', 'Bonjour!', 0x3e3fd4e0)
    assert pt == 'TEXT_MESSAGE_APP'
    assert msg == 'Bonjour!'
    print("  ✅ Clear-text meshcore message → unchanged")
    return True


def test_safetynet_to_id_zero_becomes_other_channel():
    print("\n🧪 Test: safety-net reclassifies to_id=0 [ENCRYPTED] as OTHER_CHANNEL")
    pt, msg = safety_net_reclassify('meshcore', 'TEXT_MESSAGE_APP', '[ENCRYPTED]', 0)
    assert pt == 'OTHER_CHANNEL', f"to_id=0 should become OTHER_CHANNEL, got {pt}"
    assert msg == '[UNKNOWN_CHANNEL]'
    print("  ✅ to_id=0 [ENCRYPTED] → OTHER_CHANNEL / [UNKNOWN_CHANNEL]")
    return True


# ---------------------------------------------------------------------------
# Tests – _fmt_node compact label helper
# ---------------------------------------------------------------------------

def fmt_node(node_id, known_names=None):
    """
    Mirror the _fmt_node() method added to MeshCoreCLIWrapper.
    known_names: dict {node_id: name} simulating node_manager state.
    """
    # Simulate _get_node_name: returns "0x{node_id:08x}" for unknown nodes
    if known_names and node_id in known_names:
        name = known_names[node_id]
    else:
        name = f"0x{node_id:08x}"  # fallback used by _get_node_name

    if name.startswith("0x") or name == "Unknown":
        return f"{node_id & 0xFFFFFF:06x}"
    return name[:12]


def compact_log_label(node_id, node_name):
    """
    Mirror the inline compact label used in the traffic_monitor safety-net.
    node_name: result of node_manager.get_node_name(node_id)
    """
    if node_name.startswith('Node-'):
        return f"{node_id & 0xFFFFFF:06x}"
    return node_name


def test_fmt_node_unknown_returns_last6hex():
    print("\n🧪 Test: _fmt_node unknown node → last 6 hex chars")
    label = fmt_node(0x56e6ca82)
    assert label == 'e6ca82', f"Expected 'e6ca82', got '{label}'"
    print(f"  ✅ 0x56e6ca82 → '{label}'")
    return True


def test_fmt_node_known_short_name():
    print("\n🧪 Test: _fmt_node known node → short name")
    label = fmt_node(0x02ce115f, known_names={0x02ce115f: 'tigro'})
    assert label == 'tigro', f"Expected 'tigro', got '{label}'"
    print(f"  ✅ 0x02ce115f (known) → '{label}'")
    return True


def test_fmt_node_long_name_truncated():
    print("\n🧪 Test: _fmt_node long real name is truncated to 12 chars")
    label = fmt_node(0x12345678, known_names={0x12345678: 'tigroPVCavityA'})
    assert len(label) <= 12, f"Name too long: '{label}'"
    assert label == 'tigroPVCavit', f"Expected 'tigroPVCavit', got '{label}'"
    print(f"  ✅ 'tigroPVCavityA' → '{label}' (truncated)")
    return True


def test_compact_label_node_dash_fallback():
    print("\n🧪 Test: compact_log_label 'Node-XXXXXXXX' → last 6 hex")
    label = compact_log_label(0xe6ca825f, 'Node-e6ca825f')
    assert label == 'ca825f', f"Expected 'ca825f', got '{label}'"
    print(f"  ✅ 'Node-e6ca825f' → '{label}'")
    return True


def test_compact_label_real_name_kept():
    print("\n🧪 Test: compact_log_label real name → kept as-is")
    label = compact_log_label(0x02ce115f, 'tigro')
    assert label == 'tigro', f"Expected 'tigro', got '{label}'"
    print(f"  ✅ 'tigro' → '{label}'")
    return True


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_all_tests():
    print("\n" + "=" * 60)
    print("ECDH DM FOREIGN PACKET FILTER TESTS")
    print("=" * 60)

    results = [
        ("type=12 directed → ECDH_DM",                  test_type12_directed_is_ecdh_dm()),
        ("type=13 directed → ECDH_DM",                  test_type13_directed_is_ecdh_dm()),
        ("type=15 directed → ECDH_DM",                  test_type15_directed_is_ecdh_dm()),
        ("type=15 broadcast → PSK path",                test_type15_broadcast_tries_psk()),
        ("type=1 unaffected",                            test_type1_text_message_unaffected()),
        ("safety-net: [ENCRYPTED] directed MC",         test_safetynet_reclassifies_encrypted_directed()),
        ("safety-net: broadcast → OTHER_CHANNEL",        test_safetynet_broadcast_encrypted_becomes_other_channel()),
        ("safety-net: Meshtastic unchanged",             test_safetynet_keeps_meshtastic_encrypted()),
        ("safety-net: clear-text unchanged",             test_safetynet_keeps_clear_messages()),
        ("safety-net: to_id=0 → OTHER_CHANNEL",         test_safetynet_to_id_zero_becomes_other_channel()),
        ("_fmt_node: unknown → last-6-hex",              test_fmt_node_unknown_returns_last6hex()),
        ("_fmt_node: known short name",                  test_fmt_node_known_short_name()),
        ("_fmt_node: long name truncated",               test_fmt_node_long_name_truncated()),
        ("compact_label: Node-XXXX → last-6-hex",       test_compact_label_node_dash_fallback()),
        ("compact_label: real name kept",                test_compact_label_real_name_kept()),
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
