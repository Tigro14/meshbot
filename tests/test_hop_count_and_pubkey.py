#!/usr/bin/env python3
"""
Tests for:
  1. _regroup_path_bytes(): fix for meshcoredecoder flat-byte-list bug now returns
     (count, path, was_regrouped).  The was_regrouped flag lets callers use the
     corrected hop count even when path_length ≤ 64 (e.g. 13 hops × 4 bytes = 52).
  2. Hop-count callers use was_regrouped to pick the right count.
  3. ECDH_DM pubkey lookup added to debug log lines.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meshcore_cli_wrapper import _regroup_path_bytes


# ---------------------------------------------------------------------------
# Helpers mirroring the fixed caller logic
# ---------------------------------------------------------------------------

def display_hops_from_path(raw_path, raw_path_length):
    """
    Mirrors the fixed logic in _on_rx_log_data / RX_LOG debug display:
        corrected_hops, corrected_path, was_regrouped = _regroup_path_bytes(raw_path)
        display_hops = corrected_hops if (was_regrouped or raw_path_length > 64) else raw_path_length
    """
    corrected_hops, _, was_regrouped = _regroup_path_bytes(raw_path)
    return corrected_hops if (was_regrouped or raw_path_length > 64) else raw_path_length


def pubkey_log_str(node_id, node_names):
    """
    Mirrors the pubkey lookup added to the ECDH_DM log lines.
    """
    node_data = node_names.get(node_id, {})
    pk = node_data.get('publicKey') if isinstance(node_data, dict) else None
    if pk:
        if isinstance(pk, (bytes, bytearray)):
            return pk.hex()
        return str(pk)
    return "unknown"


# ---------------------------------------------------------------------------
# Tests – _regroup_path_bytes return signature (was_regrouped flag)
# ---------------------------------------------------------------------------

def test_empty_path_returns_false_flag():
    print("\n🧪 Test: empty path → (0, [], False)")
    count, path, regrouped = _regroup_path_bytes([])
    assert count == 0
    assert path == []
    assert regrouped is False
    print("  ✅ Empty path returns was_regrouped=False")
    return True


def test_uint32_path_not_regrouped():
    print("\n🧪 Test: path with values > 255 → not regrouped")
    real_ids = [0x68465c04, 0x3a3a182e, 0xca20c3a4]
    count, path, regrouped = _regroup_path_bytes(real_ids)
    assert count == 3
    assert path == real_ids
    assert regrouped is False
    print(f"  ✅ uint32 path (count={count}) returned unchanged, was_regrouped=False")
    return True


def test_byte_list_52_bytes_gives_13_hops():
    print("\n🧪 Test: 52-byte flat list → 13 hops (was the 52-hop bug)")
    # Exactly the path from the bug report
    path_bytes = [
        0x04, 0x5C, 0x46, 0x68, 0x2E, 0x18, 0x3A, 0x3A,
        0xA4, 0xC3, 0x20, 0xCA, 0xDF, 0x1C, 0x45, 0xB0,
        0xC6, 0x76, 0x2E, 0x78, 0x53, 0xE7, 0x53, 0xD8,
        0x86, 0x98, 0xEB, 0xD7, 0xE7, 0x73, 0x46, 0xBE,
        0xB9, 0x87, 0x99, 0x69, 0xFF, 0x15, 0xB3, 0xC9,
        0x30, 0x6A, 0xE9, 0xBE, 0x73, 0x07, 0x05, 0x7B,
        0x3B, 0xA7, 0xA3, 0xCB,
    ]
    count, path, regrouped = _regroup_path_bytes(path_bytes)
    assert count == 13, f"Expected 13 hops, got {count}"
    assert len(path) == 13
    assert regrouped is True
    # Verify first node ID (LE bytes: 04 5C 46 68 → 0x68465c04)
    assert path[0] == 0x68465c04, f"First node ID wrong: 0x{path[0]:08x}"
    print(f"  ✅ 52 bytes → {count} hops, was_regrouped=True, first node=0x{path[0]:08x}")
    return True


def test_byte_list_regrouping_ignores_trailing_bytes():
    print("\n🧪 Test: byte list with non-multiple-of-4 length drops trailing bytes")
    # 9 bytes → 2 complete groups (8 bytes), last byte discarded
    path_bytes = [0x01, 0x02, 0x03, 0x04,  0x05, 0x06, 0x07, 0x08,  0xFF]
    count, path, regrouped = _regroup_path_bytes(path_bytes)
    assert count == 2, f"Expected 2, got {count}"
    assert regrouped is True
    assert path[0] == 0x04030201
    assert path[1] == 0x08070605
    print(f"  ✅ 9 bytes → 2 complete groups, trailing byte discarded")
    return True


# ---------------------------------------------------------------------------
# Tests – hop count caller logic (display_hops_from_path)
# ---------------------------------------------------------------------------

def test_bug_report_52_hop_now_shows_13():
    print("\n🧪 Test: bug report – path_length=52 but was_regrouped → shows 13")
    path_bytes = [
        0x04, 0x5C, 0x46, 0x68, 0x2E, 0x18, 0x3A, 0x3A,
        0xA4, 0xC3, 0x20, 0xCA, 0xDF, 0x1C, 0x45, 0xB0,
        0xC6, 0x76, 0x2E, 0x78, 0x53, 0xE7, 0x53, 0xD8,
        0x86, 0x98, 0xEB, 0xD7, 0xE7, 0x73, 0x46, 0xBE,
        0xB9, 0x87, 0x99, 0x69, 0xFF, 0x15, 0xB3, 0xC9,
        0x30, 0x6A, 0xE9, 0xBE, 0x73, 0x07, 0x05, 0x7B,
        0x3B, 0xA7, 0xA3, 0xCB,
    ]
    hops = display_hops_from_path(path_bytes, raw_path_length=52)
    assert hops == 13, f"Expected 13, got {hops} (old bug showed 52)"
    print(f"  ✅ path_length=52 + was_regrouped → display_hops={hops} (fixed!)")
    return True


def test_normal_uint32_path_uses_path_length():
    print("\n🧪 Test: normal uint32 path (no regrouping) → uses raw path_length")
    real_ids = [0x68465c04, 0x3a3a182e, 0xca20c3a4]
    # path_length = 3 (correct, matches list length)
    hops = display_hops_from_path(real_ids, raw_path_length=3)
    assert hops == 3, f"Expected 3, got {hops}"
    print(f"  ✅ Normal uint32 path with path_length=3 → display_hops={hops}")
    return True


def test_large_path_length_still_triggers_correction():
    print("\n🧪 Test: path_length > 64 still triggers correction (old overflow case)")
    # 80 bytes → 20 hops (previously caught by >64 threshold)
    path_bytes = list(range(80))
    hops = display_hops_from_path(path_bytes, raw_path_length=80)
    assert hops == 20, f"Expected 20, got {hops}"
    print(f"  ✅ path_length=80 > 64 → corrected to {hops} hops")
    return True


def test_zero_path_length_with_empty_path():
    print("\n🧪 Test: empty path with path_length=0 → 0 hops")
    hops = display_hops_from_path([], raw_path_length=0)
    assert hops == 0
    print("  ✅ Empty path → 0 hops")
    return True


# ---------------------------------------------------------------------------
# Tests – ECDH_DM pubkey lookup
# ---------------------------------------------------------------------------

def test_pubkey_bytes_returned_as_hex():
    print("\n🧪 Test: pubkey bytes → hex string in log")
    pk_bytes = bytes.fromhex("abcdef1234567890" * 2)  # 16 bytes
    node_names = {0x9ab14282: {'name': 'Node-9ab14282', 'publicKey': pk_bytes}}
    result = pubkey_log_str(0x9ab14282, node_names)
    assert result == pk_bytes.hex(), f"Expected {pk_bytes.hex()}, got {result}"
    print(f"  ✅ bytes → '{result[:16]}...'")
    return True


def test_pubkey_str_returned_as_is():
    print("\n🧪 Test: pubkey string → returned as-is")
    pk_str = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
    node_names = {0x9ab14282: {'name': 'Node-9ab14282', 'publicKey': pk_str}}
    result = pubkey_log_str(0x9ab14282, node_names)
    assert result == pk_str
    print(f"  ✅ str pk → '{result[:16]}...'")
    return True


def test_pubkey_missing_returns_unknown():
    print("\n🧪 Test: no pubkey in node_names → 'unknown'")
    node_names = {0x9ab14282: {'name': 'Node-9ab14282'}}
    result = pubkey_log_str(0x9ab14282, node_names)
    assert result == "unknown"
    print("  ✅ Missing pubkey → 'unknown'")
    return True


def test_node_not_in_node_names_returns_unknown():
    print("\n🧪 Test: node_id not in node_names → 'unknown'")
    result = pubkey_log_str(0xdeadbeef, {})
    assert result == "unknown"
    print("  ✅ Unknown node → 'unknown'")
    return True


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_all_tests():
    print("\n" + "=" * 60)
    print("HOP-COUNT FIX + ECDH_DM PUBKEY TESTS")
    print("=" * 60)

    results = [
        ("empty path → was_regrouped=False",                  test_empty_path_returns_false_flag()),
        ("uint32 path → not regrouped",                       test_uint32_path_not_regrouped()),
        ("52-byte list → 13 hops, was_regrouped=True",        test_byte_list_52_bytes_gives_13_hops()),
        ("trailing bytes discarded",                          test_byte_list_regrouping_ignores_trailing_bytes()),
        ("bug report: path_length=52 → display_hops=13",      test_bug_report_52_hop_now_shows_13()),
        ("normal uint32 path uses path_length",               test_normal_uint32_path_uses_path_length()),
        ("path_length > 64 still corrected",                  test_large_path_length_still_triggers_correction()),
        ("empty path → 0 hops",                               test_zero_path_length_with_empty_path()),
        ("pubkey bytes → hex string",                         test_pubkey_bytes_returned_as_hex()),
        ("pubkey str → returned as-is",                       test_pubkey_str_returned_as_is()),
        ("missing pubkey → 'unknown'",                        test_pubkey_missing_returns_unknown()),
        ("unknown node → 'unknown'",                          test_node_not_in_node_names_returns_unknown()),
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
