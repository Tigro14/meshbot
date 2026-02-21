#!/usr/bin/env python3
"""
Tests for _is_plausible_text() and the OTHER_CHANNEL broadcast classification.

Problem: Broadcast packets from other MeshCore networks (different PSK) arrive as
flood relay messages.  Each relay hop creates a new RX_LOG event with a DIFFERENT
relay-node ID in bytes 4-7 of the RF header (the "sliding-window" pattern confirmed
in the byte analysis).  PSK decryption of these packets either:
  - Fails entirely → stored as TEXT_MESSAGE_APP / [ENCRYPTED]
  - Produces printable-looking garbage (e.g. '=yUÐ$', '4F', 'ӿaC') that passed
    the old weak `all(c.isprintable())` check → stored as TEXT_MESSAGE_APP / <garbage>

Fix:
  1. _is_plausible_text(): stronger validator (length, first-char, ASCII-only for
     short strings, word-char ratio ≥ 60 %).  Replaces the old printability-only check.
  2. _on_rx_log_data(): broadcast + failed/implausible decryption → OTHER_CHANNEL /
     [UNKNOWN_CHANNEL] instead of TEXT_MESSAGE_APP / [ENCRYPTED].
  3. traffic_monitor.py safety net: meshcore TEXT_MESSAGE_APP + [ENCRYPTED] +
     broadcast to_id → OTHER_CHANNEL / [UNKNOWN_CHANNEL].
  4. OTHER_CHANNEL added to label dict, per-node stats counter, and /stats top breakdown.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BROADCAST_ID = 0xFFFFFFFF


# ---------------------------------------------------------------------------
# Mirror of _is_plausible_text() from meshcore_cli_wrapper.py
# ---------------------------------------------------------------------------

def is_plausible_text(text):
    """
    Mirrors MeshCoreCLIWrapper._is_plausible_text().

    Rules:
      1. At least 2 non-whitespace characters.
      2. First visible character is alphanumeric, '/', '@' or '#'.
      3. Short strings (≤ 4 chars) must be pure ASCII.
      4. At least 60 % of characters are word-like.
    """
    if not text:
        return False
    stripped = text.strip()
    n = len(stripped)
    if n < 2:
        return False
    first = stripped[0]
    if not (first.isalpha() or first.isdigit() or first in '/@#'):
        return False
    if n <= 4 and not stripped.isascii():
        return False
    word_chars = sum(
        1 for c in stripped
        if c.isalpha() or c.isdigit() or c in ' \t.,!?:;\'"/@#-\n\r'
    )
    return word_chars / n >= 0.60


# ---------------------------------------------------------------------------
# Mirror of the OTHER_CHANNEL safety-net in traffic_monitor.add_packet()
# ---------------------------------------------------------------------------

def safety_net_other_channel(source, packet_type, message_text, to_id):
    """
    Mirrors the reclassification logic added to traffic_monitor.add_packet().
    Returns (new_packet_type, new_message_text).
    """
    if source == 'meshcore' and packet_type == 'TEXT_MESSAGE_APP' and message_text == '[ENCRYPTED]':
        if to_id not in (BROADCAST_ID, 0):
            return 'ECDH_DM', '[FOREIGN_DM]'
        else:
            return 'OTHER_CHANNEL', '[UNKNOWN_CHANNEL]'
    return packet_type, message_text


# ---------------------------------------------------------------------------
# Mirror of the OTHER_CHANNEL portnum assignment in _on_rx_log_data
# ---------------------------------------------------------------------------

def rx_log_portnum(receiver_id, decrypted_text, packet_text):
    """
    Mirrors the portnum assignment for type 12/13/15 broadcast packets in
    _on_rx_log_data (simplified – after ECDH_DM has already been handled).
    """
    if (receiver_id == 0xFFFFFFFF and
            (not decrypted_text or packet_text == '[ENCRYPTED]' or
             not is_plausible_text(packet_text))):
        return 'OTHER_CHANNEL', '[UNKNOWN_CHANNEL]'
    return 'TEXT_MESSAGE_APP', packet_text


# ---------------------------------------------------------------------------
# Tests – _is_plausible_text
# ---------------------------------------------------------------------------

GARBAGE_EXAMPLES = [
    "=yUÐ$",        # starts with '='
    '"yHݼv',       # starts with '"', contains Arabic-Extended
    "4F",           # starts with '4', but len=2 ≤ 4 and ASCII ✓ — actually plausible
                    # (short but valid looking); we'll skip this edge case below
    "}S",           # starts with '}'
    "ӿaC",          # starts with Cyrillic ӿ, len=3, NOT ascii
    "$$S",          # starts with '$'
    "&zb",          # starts with '&'
    "F p+&+]+FDD",  # 11 chars but word-char ratio too low
    "҈6#6",         # starts with Cyrillic combining char, len=4, NOT ascii
    "{d",           # starts with '{'
    ",G 5r",        # starts with ','
    "7F`[&",        # starts with '7', but low word-char ratio
    "\x00\x01",     # control chars
    "   ",          # whitespace only
]

REAL_EXAMPLES = [
    "Bonjour 👋",
    "Salut 👋",
    "RR49F1: @[DAN94] entendu !",
    "/nodesmc",
    "Tigro: /echo salut",
    "@[DAN94] entendu",
    "#channel test",
    "OK",
    "Hi",
    "Test message avec accents: é è à ü",
    "/help",
    "Bonne nuitée a tous",
]


def test_garbage_rejected():
    print("\n🧪 Test: garbage text samples are rejected by _is_plausible_text")
    # Exclude "4F" from garbage — it's 2 chars, all alphanum — genuinely borderline
    definite_garbage = [g for g in GARBAGE_EXAMPLES if g not in ("4F",)]
    failures = []
    for g in definite_garbage:
        if is_plausible_text(g):
            failures.append(repr(g))
    if failures:
        print(f"  ❌ Should have been rejected: {failures}")
        return False
    print(f"  ✅ All {len(definite_garbage)} garbage samples correctly rejected")
    return True


def test_real_messages_accepted():
    print("\n🧪 Test: real message samples are accepted by _is_plausible_text")
    failures = []
    for msg in REAL_EXAMPLES:
        if not is_plausible_text(msg):
            failures.append(repr(msg))
    if failures:
        print(f"  ❌ Should have been accepted: {failures}")
        return False
    print(f"  ✅ All {len(REAL_EXAMPLES)} real messages correctly accepted")
    return True


def test_empty_and_whitespace_rejected():
    print("\n🧪 Test: empty / whitespace-only strings rejected")
    for val in ("", "   ", "\t\n", None):
        assert not is_plausible_text(val), f"Should reject {repr(val)}"
    print("  ✅ Empty / whitespace correctly rejected")
    return True


def test_short_non_ascii_rejected():
    print("\n🧪 Test: short (≤ 4 char) non-ASCII strings rejected")
    for val in ("ӿaC", "γD", "҈6#6", "Ð$x"):
        assert not is_plausible_text(val), f"Should reject {repr(val)}: len={len(val)}, ascii={val.isascii()}"
    print("  ✅ Short non-ASCII strings correctly rejected")
    return True


def test_command_slash_accepted():
    print("\n🧪 Test: '/' prefix (bot command) accepted")
    assert is_plausible_text("/help")
    assert is_plausible_text("/nodesmc")
    assert is_plausible_text("/bot Dis-moi bonjour")
    print("  ✅ Bot commands starting with '/' accepted")
    return True


def test_low_word_char_ratio_rejected():
    print("\n🧪 Test: strings with < 60 % word chars rejected")
    for val in ("F p+&+]+FDD", "7F`[&", "a+b=c*d"):
        result = is_plausible_text(val)
        assert not result, f"Should reject {repr(val)}"
    print("  ✅ Low-word-char strings correctly rejected")
    return True


# ---------------------------------------------------------------------------
# Tests – OTHER_CHANNEL safety net (traffic_monitor)
# ---------------------------------------------------------------------------

def test_broadcast_encrypted_meshcore_becomes_other_channel():
    print("\n🧪 Test: broadcast [ENCRYPTED] meshcore → OTHER_CHANNEL")
    pt, msg = safety_net_other_channel('meshcore', 'TEXT_MESSAGE_APP', '[ENCRYPTED]', BROADCAST_ID)
    assert pt == 'OTHER_CHANNEL', f"Expected OTHER_CHANNEL, got {pt}"
    assert msg == '[UNKNOWN_CHANNEL]'
    print("  ✅ broadcast [ENCRYPTED] → OTHER_CHANNEL / [UNKNOWN_CHANNEL]")
    return True


def test_broadcast_to_zero_also_other_channel():
    print("\n🧪 Test: to_id=0 [ENCRYPTED] meshcore → OTHER_CHANNEL")
    pt, msg = safety_net_other_channel('meshcore', 'TEXT_MESSAGE_APP', '[ENCRYPTED]', 0)
    assert pt == 'OTHER_CHANNEL', f"Expected OTHER_CHANNEL, got {pt}"
    print("  ✅ to_id=0 [ENCRYPTED] → OTHER_CHANNEL")
    return True


def test_directed_encrypted_meshcore_stays_ecdh_dm():
    print("\n🧪 Test: directed [ENCRYPTED] meshcore stays ECDH_DM (not OTHER_CHANNEL)")
    pt, msg = safety_net_other_channel('meshcore', 'TEXT_MESSAGE_APP', '[ENCRYPTED]', 0x3e3fd4e0)
    assert pt == 'ECDH_DM', f"Expected ECDH_DM, got {pt}"
    assert msg == '[FOREIGN_DM]'
    print("  ✅ directed [ENCRYPTED] → ECDH_DM / [FOREIGN_DM]")
    return True


def test_clear_text_not_reclassified():
    print("\n🧪 Test: clear-text meshcore message not reclassified")
    pt, msg = safety_net_other_channel('meshcore', 'TEXT_MESSAGE_APP', 'Bonjour !', BROADCAST_ID)
    assert pt == 'TEXT_MESSAGE_APP'
    assert msg == 'Bonjour !'
    print("  ✅ clear-text stays TEXT_MESSAGE_APP")
    return True


# ---------------------------------------------------------------------------
# Tests – OTHER_CHANNEL portnum assignment (_on_rx_log_data)
# ---------------------------------------------------------------------------

def test_rx_log_broadcast_failed_decrypt_is_other_channel():
    print("\n🧪 Test: broadcast + no decrypted_text → OTHER_CHANNEL")
    portnum, text = rx_log_portnum(BROADCAST_ID, None, '[ENCRYPTED]')
    assert portnum == 'OTHER_CHANNEL', f"Expected OTHER_CHANNEL, got {portnum}"
    assert text == '[UNKNOWN_CHANNEL]'
    print("  ✅ broadcast + no decrypt → OTHER_CHANNEL / [UNKNOWN_CHANNEL]")
    return True


def test_rx_log_broadcast_garbage_is_other_channel():
    print("\n🧪 Test: broadcast + garbage text → OTHER_CHANNEL")
    portnum, text = rx_log_portnum(BROADCAST_ID, "=yUÐ$", "=yUÐ$")
    assert portnum == 'OTHER_CHANNEL', f"Expected OTHER_CHANNEL, got {portnum}"
    print("  ✅ broadcast + garbage → OTHER_CHANNEL")
    return True


def test_rx_log_broadcast_good_decrypt_is_text_message():
    print("\n🧪 Test: broadcast + good decrypted text → TEXT_MESSAGE_APP")
    portnum, text = rx_log_portnum(BROADCAST_ID, "Bonjour !", "Bonjour !")
    assert portnum == 'TEXT_MESSAGE_APP', f"Expected TEXT_MESSAGE_APP, got {portnum}"
    print("  ✅ broadcast + good decrypt → TEXT_MESSAGE_APP")
    return True


def test_rx_log_directed_good_decrypt_is_text_message():
    print("\n🧪 Test: directed + good decrypted text → TEXT_MESSAGE_APP")
    portnum, text = rx_log_portnum(0x3e3fd4e0, "Salut !", "Salut !")
    assert portnum == 'TEXT_MESSAGE_APP', f"Expected TEXT_MESSAGE_APP, got {portnum}"
    print("  ✅ directed + good decrypt → TEXT_MESSAGE_APP")
    return True


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_all_tests():
    print("\n" + "=" * 60)
    print("OTHER_CHANNEL / _is_plausible_text TESTS")
    print("=" * 60)

    results = [
        ("garbage samples rejected",                        test_garbage_rejected()),
        ("real messages accepted",                          test_real_messages_accepted()),
        ("empty/whitespace rejected",                       test_empty_and_whitespace_rejected()),
        ("short non-ASCII rejected",                        test_short_non_ascii_rejected()),
        ("'/' command prefix accepted",                     test_command_slash_accepted()),
        ("low word-char ratio rejected",                    test_low_word_char_ratio_rejected()),
        ("broadcast [ENCRYPTED] → OTHER_CHANNEL",           test_broadcast_encrypted_meshcore_becomes_other_channel()),
        ("to_id=0 [ENCRYPTED] → OTHER_CHANNEL",            test_broadcast_to_zero_also_other_channel()),
        ("directed [ENCRYPTED] → ECDH_DM (unchanged)",     test_directed_encrypted_meshcore_stays_ecdh_dm()),
        ("clear-text not reclassified",                     test_clear_text_not_reclassified()),
        ("rx_log: broadcast + no decrypt → OTHER_CHANNEL", test_rx_log_broadcast_failed_decrypt_is_other_channel()),
        ("rx_log: broadcast + garbage → OTHER_CHANNEL",    test_rx_log_broadcast_garbage_is_other_channel()),
        ("rx_log: broadcast + good decrypt → TEXT",        test_rx_log_broadcast_good_decrypt_is_text_message()),
        ("rx_log: directed + good decrypt → TEXT",         test_rx_log_directed_good_decrypt_is_text_message()),
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
