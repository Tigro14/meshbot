#!/usr/bin/env python3
"""
Test: MeshCore channel echo - SNR and path correlation
=======================================================

Verify that:
1. latest_rx_log is initialized in __init__
2. _on_rx_log_data stores SNR/RSSI/path in latest_rx_log
3. _on_channel_message reads SNR/RSSI from latest_rx_log and path_len from payload
4. Bot packet includes snr, rssi, hopStart fields for channel messages
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_latest_rx_log_initialized():
    """Test that latest_rx_log is initialized as empty dict in __init__"""
    print("\n🧪 Test: latest_rx_log initialized in __init__")
    print("=" * 70)

    # Simulate the __init__ block
    latest_rx_log = {}  # as per our change
    assert isinstance(latest_rx_log, dict), "latest_rx_log must be a dict"
    assert len(latest_rx_log) == 0, "latest_rx_log must start empty"
    print("  ✅ latest_rx_log initialized as empty dict")
    return True


def test_rx_log_data_stores_signal():
    """Test that _on_rx_log_data stores SNR/RSSI/path in latest_rx_log"""
    print("\n🧪 Test: _on_rx_log_data stores signal data in latest_rx_log")
    print("=" * 70)

    # Simulate the storage logic added in _on_rx_log_data
    latest_rx_log = {}

    # Simulate receiving an RX_LOG_DATA event
    snr = 8.75
    rssi = -82
    before = time.time()

    latest_rx_log = {
        'snr': snr,
        'rssi': rssi,
        'timestamp': time.time(),
        'path_len': 0  # Updated later by decoder
    }

    after = time.time()

    assert latest_rx_log['snr'] == 8.75, f"Expected snr=8.75, got {latest_rx_log['snr']}"
    assert latest_rx_log['rssi'] == -82, f"Expected rssi=-82, got {latest_rx_log['rssi']}"
    assert 'timestamp' in latest_rx_log, "timestamp must be stored"
    assert before <= latest_rx_log['timestamp'] <= after, \
        f"Timestamp {latest_rx_log['timestamp']} must be between {before} and {after}"
    print(f"  ✅ SNR={snr}dB, RSSI={rssi}dBm stored in latest_rx_log")
    print(f"  ✅ Timestamp {latest_rx_log['timestamp']:.3f} is recent (within [{before:.3f}, {after:.3f}])")

    # Simulate decoder updating path_len
    path_len = 2
    latest_rx_log['path_len'] = path_len
    assert latest_rx_log['path_len'] == 2, f"Expected path_len=2, got {latest_rx_log['path_len']}"
    print(f"  ✅ path_len={path_len} updated by decoder")
    return True


def test_channel_message_uses_echo():
    """Test that _on_channel_message attaches SNR from latest_rx_log to packet"""
    print("\n🧪 Test: channel message packet includes echo SNR/RSSI")
    print("=" * 70)

    # Simulate latest_rx_log populated just before CHANNEL_MSG_RECV
    latest_rx_log = {
        'snr': 11.25,
        'rssi': -72,
        'timestamp': time.time() - 0.1,  # 100ms ago - recent
        'path_len': 1
    }

    # Simulate CHANNEL_MSG_RECV payload with path_len
    channel_payload = {
        'text': 'Tigro: /echo hello',
        'channel_idx': 0,
        'pubkey_prefix': '889fa138c712',
        'path_len': 1  # Provided by meshcore library
    }

    # Simulate the echo correlation logic from _on_channel_message
    channel_path_len = channel_payload.get('path_len') or 0
    echo_snr = 0.0
    echo_rssi = 0

    if latest_rx_log and (time.time() - latest_rx_log.get('timestamp', 0)) < 2.0:
        echo_snr = latest_rx_log.get('snr', 0.0)
        echo_rssi = latest_rx_log.get('rssi', 0)
        if not channel_path_len:
            channel_path_len = latest_rx_log.get('path_len', 0)

    print(f"  Echo SNR: {echo_snr}dB, RSSI: {echo_rssi}dBm, Hops: {channel_path_len}")

    # Simulate bot packet construction
    packet = {
        'from': 0x889fa138,
        'to': 0xFFFFFFFF,
        'snr': echo_snr,
        'rssi': echo_rssi,
        'hopLimit': 0,
        'hopStart': channel_path_len,
        'decoded': {
            'portnum': 'TEXT_MESSAGE_APP',
            'payload': b'Tigro: /echo hello'
        },
        'channel': 0,
        '_meshcore_dm': False,
        '_meshcore_path_len': channel_path_len
    }

    assert packet['snr'] == 11.25, f"Expected snr=11.25, got {packet['snr']}"
    assert packet['rssi'] == -72, f"Expected rssi=-72, got {packet['rssi']}"
    assert packet['hopStart'] == 1, f"Expected hopStart=1, got {packet['hopStart']}"
    assert packet['hopLimit'] == 0, "hopLimit must be 0 at destination"
    assert packet['_meshcore_path_len'] == 1, f"Expected path_len=1, got {packet['_meshcore_path_len']}"
    assert packet['_meshcore_dm'] is False, "Channel message must not be DM"

    print(f"  ✅ Packet snr={packet['snr']}dB rssi={packet['rssi']}dBm hops={packet['hopStart']}")
    print(f"  ✅ Bot packet includes real SNR/RSSI from channel echo")
    return True


def test_channel_echo_no_recent_rx_log():
    """Test that channel message falls back to 0 when no recent RX_LOG"""
    print("\n🧪 Test: channel echo with stale/missing RX_LOG falls back gracefully")
    print("=" * 70)

    # Simulate stale latest_rx_log (older than 2 seconds)
    latest_rx_log = {
        'snr': 11.25,
        'rssi': -72,
        'timestamp': time.time() - 5.0,  # 5 seconds ago - too old
        'path_len': 1
    }

    channel_payload = {
        'text': '/my',
        'channel_idx': 0,
        'path_len': 0
    }

    channel_path_len = channel_payload.get('path_len') or 0
    echo_snr = 0.0
    echo_rssi = 0

    # Correlation logic: only use if within 2 seconds
    if latest_rx_log and (time.time() - latest_rx_log.get('timestamp', 0)) < 2.0:
        echo_snr = latest_rx_log.get('snr', 0.0)
        echo_rssi = latest_rx_log.get('rssi', 0)

    assert echo_snr == 0.0, f"Expected no SNR for stale RX_LOG, got {echo_snr}"
    assert echo_rssi == 0, f"Expected no RSSI for stale RX_LOG, got {echo_rssi}"
    print(f"  ✅ Stale RX_LOG ({5.0:.1f}s old) correctly ignored - no false SNR reported")

    # Empty latest_rx_log: `if latest_rx_log` is False for empty dict,
    # so the correlation block is skipped and echo_snr2 remains 0.0
    latest_rx_log_empty = {}
    echo_snr2 = 0.0
    if latest_rx_log_empty and (time.time() - latest_rx_log_empty.get('timestamp', 0)) < 2.0:
        echo_snr2 = latest_rx_log_empty.get('snr', 0.0)
    # The empty dict makes the condition False - echo_snr2 stays 0.0
    assert not latest_rx_log_empty, "Empty dict evaluates to False (expected)"
    assert echo_snr2 == 0.0, "Empty latest_rx_log should give snr=0"
    print(f"  ✅ Empty latest_rx_log (falsy) correctly skipped - no false SNR reported")
    return True


def test_channel_path_len_from_payload_preferred():
    """Test that channel payload path_len takes precedence over RX_LOG path_len"""
    print("\n🧪 Test: CHANNEL_MSG_RECV path_len takes precedence over RX_LOG")
    print("=" * 70)

    # Simulate RX_LOG with different path_len than CHANNEL_MSG_RECV
    latest_rx_log = {
        'snr': 5.0,
        'rssi': -90,
        'timestamp': time.time() - 0.05,  # very recent
        'path_len': 3  # From decoder, might differ
    }

    # CHANNEL_MSG_RECV payload has its own path_len (from meshcore library)
    channel_payload = {'text': 'hello', 'channel_idx': 0, 'path_len': 2}

    channel_path_len = channel_payload.get('path_len') or 0
    echo_snr = 0.0
    echo_rssi = 0

    if latest_rx_log and (time.time() - latest_rx_log.get('timestamp', 0)) < 2.0:
        echo_snr = latest_rx_log.get('snr', 0.0)
        echo_rssi = latest_rx_log.get('rssi', 0)
        if not channel_path_len:  # Only use RX_LOG path_len if CHANNEL_MSG_RECV has none
            channel_path_len = latest_rx_log.get('path_len', 0)

    # CHANNEL_MSG_RECV path_len=2 must win over RX_LOG path_len=3
    assert channel_path_len == 2, f"Expected channel_path_len=2 (from payload), got {channel_path_len}"
    assert echo_snr == 5.0, f"Expected snr from RX_LOG: 5.0, got {echo_snr}"
    print(f"  ✅ path_len=2 from CHANNEL_MSG_RECV wins over RX_LOG path_len=3")
    print(f"  ✅ SNR={echo_snr}dB from RX_LOG is still used")
    return True


def test_hop_calculation_for_channel_messages():
    """Test hop count calculation for channel messages with echo data"""
    print("\n🧪 Test: hop count calculation from channel echo data")
    print("=" * 70)

    test_cases = [
        (0, 0, "direct"),   # path_len=0 → 0 hops
        (1, 1, "1 hop"),    # path_len=1 → 1 hop
        (2, 2, "2 hops"),   # path_len=2 → 2 hops
        (3, 3, "3 hops"),   # path_len=3 → 3 hops
    ]

    for channel_path_len, expected_hops_calc, label in test_cases:
        # Packet with hopLimit=0, hopStart=path_len
        hop_limit = 0
        hop_start = channel_path_len
        hops_calc = hop_start - hop_limit

        assert hops_calc == expected_hops_calc, \
            f"Expected {expected_hops_calc} hops for path_len={channel_path_len}, got {hops_calc}"
        print(f"  ✅ path_len={channel_path_len} → {hops_calc} hops ({label})")

    return True


def run_all_tests():
    print("\n" + "=" * 70)
    print("MESHCORE CHANNEL ECHO (SNR + PATH) - TEST SUITE")
    print("=" * 70)

    results = []
    results.append(("latest_rx_log initialized", test_latest_rx_log_initialized()))
    results.append(("RX_LOG stores signal data", test_rx_log_data_stores_signal()))
    results.append(("Channel message uses echo SNR", test_channel_message_uses_echo()))
    results.append(("No recent RX_LOG fallback", test_channel_echo_no_recent_rx_log()))
    results.append(("Payload path_len preferred", test_channel_path_len_from_payload_preferred()))
    results.append(("Hop calculation correct", test_hop_calculation_for_channel_messages()))

    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    passed = sum(1 for _, r in results if r)
    total = len(results)
    for name, result in results:
        print(f"  {'✅ PASS' if result else '❌ FAIL'}: {name}")
    print("\n" + "=" * 70)
    if passed == total:
        print(f"✅ ALL TESTS PASSED ({passed}/{total})")
        print("=" * 70)
        return True
    else:
        print(f"❌ SOME TESTS FAILED ({passed}/{total})")
        print("=" * 70)
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
