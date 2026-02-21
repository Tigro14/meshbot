#!/usr/bin/env python3
"""
Tests for the _regroup_path_bytes() fix.

Bug: meshcoredecoder library returns packet.path as a flat list of individual
bytes (each 0-255) instead of a list of 4-byte little-endian uint32 node IDs,
causing hop counts like 143 for a packet that should show ~35 hops.

Fix: detect byte-list paths and regroup as 4-byte little-endian node IDs.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meshcore_cli_wrapper import _regroup_path_bytes


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_byte_path(*node_ids):
    """Flatten a list of uint32 node IDs into individual little-endian bytes."""
    result = []
    for nid in node_ids:
        result += [(nid >> (8 * i)) & 0xFF for i in range(4)]
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_empty_path():
    """Empty path → 0 hops, empty list."""
    hops, path = _regroup_path_bytes([])
    assert hops == 0, f"Expected 0 hops, got {hops}"
    assert path == [], f"Expected [], got {path}"
    print("  ✅ Empty path → 0 hops")
    return True


def test_real_node_ids_unchanged():
    """Path already containing uint32 node IDs (values > 255) is not modified."""
    node_ids = [0xd511345f, 0xeee083fe, 0x889fa138]
    hops, path = _regroup_path_bytes(node_ids)
    assert hops == 3, f"Expected 3 hops, got {hops}"
    assert path == node_ids, f"Expected {node_ids}, got {path}"
    print("  ✅ Real uint32 node IDs passed through unchanged")
    return True


def test_byte_list_regrouped_to_node_ids():
    """Flat byte list is regrouped into 4-byte little-endian node IDs."""
    node_ids = [0xd511345f, 0xeee083fe, 0x889fa138]
    byte_path = _make_byte_path(*node_ids)
    assert len(byte_path) == 12  # 3 nodes × 4 bytes each

    hops, path = _regroup_path_bytes(byte_path)
    assert hops == 3, f"Expected 3 hops, got {hops}"
    assert path == node_ids, f"Expected {[hex(n) for n in node_ids]}, got {[hex(n) for n in path]}"
    print(f"  ✅ 12-byte path → 3 node IDs: {[hex(n) for n in path]}")
    return True


def test_large_byte_path_169b_packet():
    """Simulate the actual 169-byte Path packet from the bug report.

    sender=0xd511345f, receiver=0xeee083fe followed by ~35 routing node IDs.
    The library was returning 143 individual bytes → should become ~35 hops.
    """
    # Build a realistic path: 35 node IDs = 140 bytes
    routing_nodes = [0x4b3ec152 + i for i in range(35)]
    byte_path = _make_byte_path(*routing_nodes)
    assert len(byte_path) == 140

    hops, path = _regroup_path_bytes(byte_path)
    assert hops == 35, f"Expected 35 hops, got {hops}"
    assert len(path) == 35
    assert path[0] == routing_nodes[0]
    assert path[-1] == routing_nodes[-1]
    print(f"  ✅ 140-byte path → 35 hops (not 140)")
    return True


def test_path_length_exceeds_64_triggers_regroup():
    """When library reports path_length > 64, corrected value must be ≤ 64."""
    # Simulate 8 real routing nodes (8*4 = 32 bytes), passed as individual bytes
    routing_nodes = [0x11223344, 0x55667788, 0x99aabbcc, 0xddeeff00,
                     0x01020304, 0x05060708, 0x090a0b0c, 0x0d0e0f10]
    byte_path = _make_byte_path(*routing_nodes)
    fake_path_length = len(byte_path)  # 32 — wrong value from library

    corrected_hops, _ = _regroup_path_bytes(byte_path)
    # Apply the same logic as meshcore_cli_wrapper.py
    display_hops = corrected_hops if fake_path_length > 64 else fake_path_length

    # 32 < 64 so we'd use fake_path_length; let's use a bigger example
    routing_nodes_big = routing_nodes * 4  # 32 nodes → 128 bytes
    byte_path_big = _make_byte_path(*routing_nodes_big)
    fake_big = len(byte_path_big)  # 128 — way > 64

    corrected_hops2, _ = _regroup_path_bytes(byte_path_big)
    display_hops2 = corrected_hops2 if fake_big > 64 else fake_big

    assert display_hops2 <= 64, f"Corrected hops should be ≤ 64, got {display_hops2}"
    assert display_hops2 == 32, f"Expected 32 corrected hops, got {display_hops2}"
    print(f"  ✅ 128-byte path (library says 128 hops) → corrected to {display_hops2} hops")
    return True


def test_odd_length_byte_path_truncates_remainder():
    """Odd-length byte paths: trailing bytes that don't form a full node ID are dropped."""
    # 14 bytes = 3 complete node IDs (12 bytes) + 2 leftover bytes
    # Build byte path: each node ID stored as 4 bytes, little-endian.
    # 0xd511345f → bytes [0x5f, 0x34, 0x11, 0xd5]
    # 0xeee083fe → bytes [0xfe, 0x83, 0xe0, 0xee]
    # 0x889fa138 → bytes [0x38, 0xa1, 0x9f, 0x88]
    byte_path = [0x5f, 0x34, 0x11, 0xd5,   # 0xd511345f (little-endian)
                 0xfe, 0x83, 0xe0, 0xee,    # 0xeee083fe (little-endian)
                 0x38, 0xa1, 0x9f, 0x88,    # 0x889fa138 (little-endian)
                 0xAB, 0xCD]                 # leftover — dropped

    hops, path = _regroup_path_bytes(byte_path)
    assert hops == 3, f"Expected 3 hops, got {hops}"
    assert len(path) == 3
    print(f"  ✅ 14-byte path with 2 leftover bytes → 3 hops (remainder dropped)")
    return True


def run_all_tests():
    print("\n" + "=" * 70)
    print("_regroup_path_bytes() — FIX FOR MESHCOREDECODER BYTE-LIST PATH BUG")
    print("=" * 70)

    tests = [
        ("Empty path",                        test_empty_path),
        ("Real uint32 node IDs unchanged",    test_real_node_ids_unchanged),
        ("Byte list regrouped to node IDs",   test_byte_list_regrouped_to_node_ids),
        ("169B Path packet → ~35 hops",       test_large_byte_path_169b_packet),
        (">64 path_length corrected",         test_path_length_exceeds_64_triggers_regroup),
        ("Odd-length byte path truncation",   test_odd_length_byte_path_truncates_remainder),
    ]

    results = []
    for name, fn in tests:
        print(f"\n🧪 {name}")
        print("-" * 60)
        try:
            ok = fn()
        except AssertionError as exc:
            print(f"  ❌ FAIL: {exc}")
            ok = False
        except Exception as exc:
            print(f"  ❌ ERROR: {exc}")
            ok = False
        results.append((name, ok))

    print("\n" + "=" * 70)
    passed = sum(1 for _, r in results if r)
    total = len(results)
    for name, ok in results:
        print(f"  {'✅ PASS' if ok else '❌ FAIL'}: {name}")
    print(f"\n{'✅ ALL TESTS PASSED' if passed == total else '⚠️  SOME TESTS FAILED'} ({passed}/{total})")
    print("=" * 70)
    return passed == total


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
