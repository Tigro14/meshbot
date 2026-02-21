#!/usr/bin/env python3
"""
Tests for the SNR/RSSI-based local-signal heuristic and the three-way
ECDH_DM / LOCAL_DM / OTHER_CHANNEL classification.

Problem: a packet from Node-da935f4b (SNR=12dB, RSSI=-46dBm) was showing as
ECDH_DM with PK:unknown.  The node is physically nearby (strong signal) but
hasn't sent an ADVERTISEMENT yet, so it is not in node_names.  It should be
treated as a real local node (ECDH_DM + pending contact registration) rather
than silently binned as foreign relay noise (OTHER_CHANNEL).

Fix:
  _is_local_signal(snr, rssi) → True when SNR ≥ 0 dB OR RSSI ≥ -80 dBm
  In the "both endpoints unknown" branch:
    is_local=True  → ECDH_DM + register pending contact
    is_local=False → OTHER_CHANNEL  (relay noise from another network)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Import the static helper directly from the wrapper module ────────────────
from meshcore_cli_wrapper import MeshCoreCLIWrapper

OUR_NODE_ID  = 0x02ce115f
BROADCAST_ID = 0xFFFFFFFF

# Node from the bug report
BUG_NODE     = 0xda935f4b   # SNR=12dB, RSSI=-46dBm → definitely local

# Known contact
KNOWN_NODE   = 0x16fad3dc

# Typical relay-noise IDs (weak distant signal)
NOISE_SRC    = 0xa3344b93
NOISE_DST    = 0x5f344b93


# ---------------------------------------------------------------------------
# Mirror of the classification logic from _on_rx_log_data
# ---------------------------------------------------------------------------

def classify(sender_id, receiver_id, snr, rssi, local_node_id, node_names):
    """
    Mirrors the updated types-12/13/15 non-broadcast branch.
    Returns ('ECDH_DM'|'OTHER_CHANNEL', portnum_text, pending_registered: bool)
    """
    if receiver_id == BROADCAST_ID:
        return 'BROADCAST', '', False

    is_to_us       = (receiver_id == local_node_id)
    sender_known   = sender_id  in node_names
    receiver_known = is_to_us or (receiver_id in node_names)
    is_local       = MeshCoreCLIWrapper._is_local_signal(snr, rssi)

    pending = False
    if not sender_known and not receiver_known:
        if is_local:
            # Register pending contact
            if sender_id not in node_names:
                node_names[sender_id] = {
                    'name': f"Node-{sender_id:08x}",
                    'shortName': None, 'hwModel': None,
                    'lat': None, 'lon': None, 'alt': None,
                    'last_update': None, 'pending': True,
                }
                pending = True
            return 'ECDH_DM', '[FOREIGN_DM]', pending
        else:
            return 'OTHER_CHANNEL', '[UNKNOWN_CHANNEL]', False
    return 'ECDH_DM', '[FOREIGN_DM]', False


# ---------------------------------------------------------------------------
# Tests for _is_local_signal
# ---------------------------------------------------------------------------

def test_is_local_signal_strong_snr():
    print("\n🧪 _is_local_signal: strong SNR → True")
    assert MeshCoreCLIWrapper._is_local_signal(12.0, -46)   # bug-report case
    assert MeshCoreCLIWrapper._is_local_signal(0.0,  -90)   # exact boundary
    assert MeshCoreCLIWrapper._is_local_signal(5.0,  -100)  # good SNR, bad RSSI
    print("  ✅ SNR ≥ 0 cases → True")
    return True

def test_is_local_signal_strong_rssi():
    print("\n🧪 _is_local_signal: strong RSSI → True")
    assert MeshCoreCLIWrapper._is_local_signal(-5.0, -50)   # good RSSI, bad SNR
    assert MeshCoreCLIWrapper._is_local_signal(-10.0, -80)  # exact RSSI boundary
    print("  ✅ RSSI ≥ -80 cases → True")
    return True

def test_is_local_signal_weak():
    print("\n🧪 _is_local_signal: weak signal → False")
    assert not MeshCoreCLIWrapper._is_local_signal(-6.5, -117)  # relay noise case
    assert not MeshCoreCLIWrapper._is_local_signal(-11.2, -117)
    assert not MeshCoreCLIWrapper._is_local_signal(-3.0, -100)  # borderline weak
    print("  ✅ Weak-signal cases → False")
    return True

def test_is_local_signal_boundary():
    print("\n🧪 _is_local_signal: exact boundaries")
    assert     MeshCoreCLIWrapper._is_local_signal(0.0, -81)   # SNR=0 is local
    assert     MeshCoreCLIWrapper._is_local_signal(-1.0, -80)  # RSSI=-80 is local
    assert not MeshCoreCLIWrapper._is_local_signal(-0.1, -81)  # both just outside
    print("  ✅ Boundary conditions correct")
    return True

def test_is_local_signal_bad_inputs():
    print("\n🧪 _is_local_signal: bad inputs → False (no crash)")
    assert not MeshCoreCLIWrapper._is_local_signal(None, None)
    assert not MeshCoreCLIWrapper._is_local_signal('bad', 0)
    print("  ✅ Bad inputs handled gracefully")
    return True


# ---------------------------------------------------------------------------
# Tests for classification: bug-report node (strong local signal, unknown)
# ---------------------------------------------------------------------------

def test_bug_report_node_classified_as_ecdh_dm():
    print(f"\n🧪 Bug-report node {BUG_NODE:08x} (SNR=12dB, RSSI=-46dBm) → ECDH_DM")
    node_names = {}  # unknown sender
    portnum, text, pending = classify(
        BUG_NODE, OUR_NODE_ID, 12.0, -46, OUR_NODE_ID, node_names
    )
    # receiver IS our node → always ECDH_DM regardless of SNR
    assert portnum == 'ECDH_DM', f"Expected ECDH_DM, got {portnum}"
    print("  ✅ DM to our node → ECDH_DM")
    return True

def test_both_unknown_local_signal_is_ecdh_dm():
    print("\n🧪 Both unknown + strong signal → ECDH_DM + pending registration")
    node_names = {}
    portnum, text, pending = classify(
        BUG_NODE, 0xdeadbeef,   # receiver unknown but strong signal
        12.0, -46, OUR_NODE_ID, node_names
    )
    assert portnum == 'ECDH_DM', f"Expected ECDH_DM, got {portnum}"
    assert text == '[FOREIGN_DM]'
    assert pending, "Should have registered pending contact"
    assert BUG_NODE in node_names, "Sender should be in node_names now"
    assert node_names[BUG_NODE].get('pending') is True
    print("  ✅ Strong local signal + both unknown → ECDH_DM + pending registered")
    return True

def test_both_unknown_weak_signal_is_other_channel():
    print("\n🧪 Both unknown + weak signal → OTHER_CHANNEL (relay noise)")
    node_names = {}
    portnum, text, pending = classify(
        NOISE_SRC, NOISE_DST, -11.0, -117, OUR_NODE_ID, node_names
    )
    assert portnum == 'OTHER_CHANNEL', f"Expected OTHER_CHANNEL, got {portnum}"
    assert text == '[UNKNOWN_CHANNEL]'
    assert not pending
    assert NOISE_SRC not in node_names, "Noise node should NOT be registered"
    print("  ✅ Weak signal + both unknown → OTHER_CHANNEL, no registration")
    return True

def test_known_sender_always_ecdh_dm():
    print("\n🧪 Known sender → ECDH_DM regardless of signal")
    node_names = {KNOWN_NODE: {'name': 'Tigro', 'shortName': 'TGR'}}
    for snr, rssi in [(-11.0, -117), (12.0, -46)]:
        portnum, _, _ = classify(KNOWN_NODE, NOISE_DST, snr, rssi, OUR_NODE_ID, node_names)
        assert portnum == 'ECDH_DM', f"Expected ECDH_DM at SNR={snr}, got {portnum}"
    print("  ✅ Known sender → ECDH_DM at any signal strength")
    return True

def test_pending_not_registered_twice():
    print("\n🧪 Pending contact not registered twice")
    node_names = {}
    # First call: registers
    portnum1, _, pending1 = classify(BUG_NODE, 0xdeadbeef, 12.0, -46, OUR_NODE_ID, node_names)
    assert pending1, "First call should register"
    # Second call: already registered, pending=False
    portnum2, _, pending2 = classify(BUG_NODE, 0xdeadbeef, 12.0, -46, OUR_NODE_ID, node_names)
    assert not pending2, "Second call should not re-register"
    assert portnum2 == 'ECDH_DM'  # still ECDH_DM because now sender_known=True
    print("  ✅ Pending contact registered only once")
    return True

def test_borderline_snr_zero():
    print("\n🧪 SNR=0.0 dB (boundary) → local → ECDH_DM")
    node_names = {}
    portnum, _, pending = classify(BUG_NODE, 0xdeadbeef, 0.0, -110, OUR_NODE_ID, node_names)
    assert portnum == 'ECDH_DM'
    assert pending
    print("  ✅ SNR=0.0 treated as local → ECDH_DM")
    return True

def test_borderline_rssi_minus80():
    print("\n🧪 RSSI=-80 dBm (boundary) → local → ECDH_DM")
    node_names = {}
    portnum, _, pending = classify(BUG_NODE, 0xdeadbeef, -5.0, -80, OUR_NODE_ID, node_names)
    assert portnum == 'ECDH_DM'
    assert pending
    print("  ✅ RSSI=-80 treated as local → ECDH_DM")
    return True

def test_weak_snr_strong_rssi_is_local():
    print("\n🧪 Weak SNR but strong RSSI → still local → ECDH_DM")
    node_names = {}
    portnum, _, pending = classify(BUG_NODE, 0xdeadbeef, -8.0, -60, OUR_NODE_ID, node_names)
    assert portnum == 'ECDH_DM'
    print("  ✅ Weak SNR but RSSI=-60 → local → ECDH_DM")
    return True


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_all_tests():
    print("\n" + "=" * 65)
    print("SNR/RSSI LOCAL-SIGNAL HEURISTIC TESTS")
    print("=" * 65)

    results = [
        ("_is_local_signal: strong SNR → True",            test_is_local_signal_strong_snr()),
        ("_is_local_signal: strong RSSI → True",           test_is_local_signal_strong_rssi()),
        ("_is_local_signal: weak signal → False",          test_is_local_signal_weak()),
        ("_is_local_signal: exact boundaries",             test_is_local_signal_boundary()),
        ("_is_local_signal: bad inputs → False",           test_is_local_signal_bad_inputs()),
        ("bug-report node DM to us → ECDH_DM",            test_bug_report_node_classified_as_ecdh_dm()),
        ("both unknown + local signal → ECDH_DM+pending", test_both_unknown_local_signal_is_ecdh_dm()),
        ("both unknown + weak signal → OTHER_CHANNEL",    test_both_unknown_weak_signal_is_other_channel()),
        ("known sender → ECDH_DM any signal",             test_known_sender_always_ecdh_dm()),
        ("pending contact not registered twice",          test_pending_not_registered_twice()),
        ("SNR=0.0 boundary → local",                      test_borderline_snr_zero()),
        ("RSSI=-80 boundary → local",                     test_borderline_rssi_minus80()),
        ("weak SNR + strong RSSI → local",                test_weak_snr_strong_rssi_is_local()),
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
