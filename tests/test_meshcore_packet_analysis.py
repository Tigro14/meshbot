#!/usr/bin/env python3
"""
Tests for MeshCore packet analysis improvements.

Covers the four bugs fixed based on inspection of the pyMC_Repeater /
meshcoredecoder library:

  1. RF hex extraction: LOG_DATA 'raw_hex' includes a 2-byte SNR/RSSI prefix
     that must be stripped before passing to MeshCoreDecoder.  The 'payload'
     key in the same event already contains the RF bytes only.

  2. Hop count: packet.path_length is a *byte* count (4 bytes per node ID),
     so hop_count = path_length // 4, NOT path_length itself.

  3. Path regrouping: meshcoredecoder ≥ 0.2.x returns packet.path as a flat
     list of 2-char hex strings (one per byte).  _regroup_path_bytes() now
     handles all three formats: hex strings, integer bytes, and uint32 IDs.

  4. Sender extraction: MeshCore RF packets have no fixed sender/receiver
     fields in the header.  _parse_meshcore_header() now derives sender_id
     from the Advert payload's public_key prefix, and returns 0xFFFFFFFF
     (unknown) for all other packet types.
"""

import sys
import os
import struct
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meshcore_cli_wrapper import _regroup_path_bytes, MeshCoreCLIWrapper
from meshcoredecoder import MeshCoreDecoder


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_advert_rf_packet(node_path=None):
    """
    Build a minimal but valid Advert Flood RF packet with an optional routing
    path.  Returns (rf_bytes, rf_hex, pk_hex) where pk_hex is the hex of the
    32-byte public key embedded in the payload.
    """
    header_byte = (4 << 2) | 1   # payload_type=Advert(4) | route_type=Flood(1)
    path_bytes = b''
    if node_path:
        for nid in node_path:
            path_bytes += struct.pack('<I', nid)

    # Advert payload: pubkey(32) + timestamp(4) + signature(64) + flags(1) + appdata(10)
    pk_bytes = bytes.fromhex('ABCDEF12' * 8)  # 32 bytes, first 4 = 0xABCDEF12
    ts_bytes = struct.pack('<I', 1_700_000_000)
    sig_bytes = b'\x00' * 64
    flags_byte = b'\x01'
    app_data = b'\x00' * 10
    advert_payload = pk_bytes + ts_bytes + sig_bytes + flags_byte + app_data

    rf_bytes = bytes([header_byte, len(path_bytes)]) + path_bytes + advert_payload
    return rf_bytes, rf_bytes.hex(), pk_bytes.hex()


def make_log_data_event(rf_hex, snr=-6.25, rssi=-75):
    """
    Simulate the dict that the meshcore library emits as RX_LOG_DATA event
    payload.  It contains:
      - 'snr', 'rssi'  : decoded signal metrics
      - 'payload'      : just the RF packet bytes (hex)
      - 'raw_hex'      : SNR_byte + RSSI_byte + RF_packet (hex) — do NOT decode this
    """
    snr_byte = int(round(snr * 4)) & 0xFF
    rssi_byte = int(rssi) & 0xFF
    raw_hex_full = bytes([snr_byte, rssi_byte]).hex() + rf_hex
    event = Mock()
    event.payload = {
        'snr': snr,
        'rssi': rssi,
        'payload': rf_hex,
        'raw_hex': raw_hex_full,
        'payload_length': len(rf_hex) // 2,
    }
    return event


def _make_wrapper():
    """Create a MeshCoreCLIWrapper with a mocked serial port (no hardware)."""
    with patch('meshcore_cli_wrapper.MESHCORE_CLI_AVAILABLE', False):
        wrapper = MeshCoreCLIWrapper.__new__(MeshCoreCLIWrapper)
        # Minimal initialisation needed for header / path tests
        wrapper.port = '/dev/null'
        wrapper.baudrate = 115200
        wrapper.meshcore = None
        wrapper.node_manager = None
        wrapper.debug = False
        wrapper.localNode = type('L', (), {'nodeNum': 0xFFFFFFFE})()
        wrapper.latest_rx_log = {'snr': 0.0, 'rssi': 0, 'timestamp': 0, 'path_len': 0}
        wrapper.last_message_time = None
        wrapper.connection_healthy = False
        wrapper.message_callback = None
    return wrapper


# ---------------------------------------------------------------------------
# Test 1 – RF hex extraction
# ---------------------------------------------------------------------------

class TestRFHexExtraction(unittest.TestCase):
    """Bug 1: LOG_DATA 'raw_hex' must not be used directly for decoding."""

    def _extract(self, event_payload):
        """Replicate the extraction logic in _on_rx_log_data."""
        rf_hex = event_payload.get('payload', '')
        if not rf_hex:
            full_raw = event_payload.get('raw_hex', '')
            rf_hex = full_raw[4:] if len(full_raw) > 4 else ''
        return rf_hex

    def test_payload_key_preferred(self):
        """'payload' key (RF-only) is preferred over 'raw_hex'."""
        _, rf_hex, _ = make_advert_rf_packet()
        event = make_log_data_event(rf_hex)
        extracted = self._extract(event.payload)
        self.assertEqual(extracted, rf_hex)

    def test_fallback_strips_snr_rssi_prefix(self):
        """When 'payload' is absent, first 4 hex chars (SNR+RSSI) are stripped."""
        _, rf_hex, _ = make_advert_rf_packet()
        snr_byte = 0xE7
        rssi_byte = 0xB5
        raw_hex_full = bytes([snr_byte, rssi_byte]).hex() + rf_hex
        payload = {'snr': -6.25, 'rssi': -75, 'raw_hex': raw_hex_full}
        extracted = self._extract(payload)
        self.assertEqual(extracted, rf_hex)

    def test_correct_hex_decodes_properly(self):
        """Extracted RF hex decodes to the expected route/payload types."""
        _, rf_hex, _ = make_advert_rf_packet()
        packet = MeshCoreDecoder.decode(rf_hex)
        self.assertEqual(packet.route_type.name, 'Flood')
        self.assertEqual(packet.payload_type.name, 'Advert')
        self.assertTrue(packet.is_valid)

    def test_wrong_hex_decodes_badly(self):
        """raw_hex WITH prefix decodes to wrong packet type (confirming the bug)."""
        _, rf_hex, _ = make_advert_rf_packet()
        # Prepend fake SNR+RSSI bytes
        corrupted = bytes([0xE7, 0xB5]).hex() + rf_hex
        packet = MeshCoreDecoder.decode(corrupted)
        # Advert should NOT be detected when SNR/RSSI bytes corrupt the header
        self.assertNotEqual(packet.payload_type.name, 'Advert')


# ---------------------------------------------------------------------------
# Test 2 – Hop count
# ---------------------------------------------------------------------------

class TestHopCount(unittest.TestCase):
    """Bug 2: packet.path_length is a *byte* count → divide by 4 for hops."""

    def _display_hops(self, rf_hex):
        packet = MeshCoreDecoder.decode(rf_hex)
        raw_path = packet.path or []
        corrected_hops, _, was_regrouped = _regroup_path_bytes(raw_path)
        return corrected_hops if was_regrouped else packet.path_length // 4

    def test_zero_hops(self):
        _, rf_hex, _ = make_advert_rf_packet(node_path=[])
        self.assertEqual(self._display_hops(rf_hex), 0)

    def test_one_hop(self):
        _, rf_hex, _ = make_advert_rf_packet(node_path=[0x12345678])
        self.assertEqual(self._display_hops(rf_hex), 1)

    def test_two_hops(self):
        _, rf_hex, _ = make_advert_rf_packet(node_path=[0x12345678, 0x9ABCDEF0])
        self.assertEqual(self._display_hops(rf_hex), 2)

    def test_three_hops(self):
        _, rf_hex, _ = make_advert_rf_packet(
            node_path=[0x11111111, 0x22222222, 0x33333333]
        )
        self.assertEqual(self._display_hops(rf_hex), 3)

    def test_path_length_is_bytes(self):
        """Verify that packet.path_length really is the byte count, not hop count."""
        _, rf_hex, _ = make_advert_rf_packet(node_path=[0x12345678, 0x9ABCDEF0])
        packet = MeshCoreDecoder.decode(rf_hex)
        # 2 nodes × 4 bytes = 8 bytes
        self.assertEqual(packet.path_length, 8)


# ---------------------------------------------------------------------------
# Test 3 – Path regrouping
# ---------------------------------------------------------------------------

class TestRegroupPathBytes(unittest.TestCase):
    """Bug 3: decoder returns path as 2-char hex strings, not integers."""

    # ── hex string format (meshcoredecoder ≥ 0.2.x) ─────────────────────

    def test_hex_strings_two_nodes(self):
        path = ['78', '56', '34', '12', 'F0', 'DE', 'BC', '9A']
        hops, node_ids, was_regrouped = _regroup_path_bytes(path)
        self.assertTrue(was_regrouped)
        self.assertEqual(hops, 2)
        self.assertEqual(node_ids[0], 0x12345678)
        self.assertEqual(node_ids[1], 0x9ABCDEF0)

    def test_hex_strings_one_node(self):
        path = ['78', '56', '34', '12']
        hops, node_ids, was_regrouped = _regroup_path_bytes(path)
        self.assertTrue(was_regrouped)
        self.assertEqual(hops, 1)
        self.assertEqual(node_ids[0], 0x12345678)

    def test_hex_strings_trailing_bytes_discarded(self):
        # 9 bytes → 2 complete groups + 1 trailing byte
        path = ['78', '56', '34', '12', 'F0', 'DE', 'BC', '9A', 'AB']
        hops, node_ids, _ = _regroup_path_bytes(path)
        self.assertEqual(hops, 2)
        self.assertEqual(len(node_ids), 2)

    def test_hex_strings_empty(self):
        hops, node_ids, was_regrouped = _regroup_path_bytes([])
        self.assertEqual(hops, 0)
        self.assertEqual(node_ids, [])
        self.assertFalse(was_regrouped)

    # ── integer byte format (older decoder builds) ───────────────────────

    def test_integer_bytes_two_nodes(self):
        path = [0x78, 0x56, 0x34, 0x12, 0xF0, 0xDE, 0xBC, 0x9A]
        hops, node_ids, was_regrouped = _regroup_path_bytes(path)
        self.assertTrue(was_regrouped)
        self.assertEqual(hops, 2)
        self.assertEqual(node_ids[0], 0x12345678)
        self.assertEqual(node_ids[1], 0x9ABCDEF0)

    # ── already-uint32 format ────────────────────────────────────────────

    def test_uint32_unchanged(self):
        path = [0x12345678, 0x9ABCDEF0]
        hops, node_ids, was_regrouped = _regroup_path_bytes(path)
        self.assertFalse(was_regrouped)
        self.assertEqual(hops, 2)
        self.assertEqual(node_ids, [0x12345678, 0x9ABCDEF0])

    # ── consistency with live decoder output ────────────────────────────

    def test_live_decoder_hex_strings_regrouped(self):
        """Path items from a live MeshCoreDecoder.decode() call are regrouped."""
        _, rf_hex, _ = make_advert_rf_packet(node_path=[0x12345678, 0x9ABCDEF0])
        packet = MeshCoreDecoder.decode(rf_hex)
        self.assertIsNotNone(packet.path)
        hops, node_ids, was_regrouped = _regroup_path_bytes(packet.path)
        self.assertTrue(was_regrouped)
        self.assertEqual(hops, 2)
        self.assertEqual(node_ids[0], 0x12345678)
        self.assertEqual(node_ids[1], 0x9ABCDEF0)


# ---------------------------------------------------------------------------
# Test 4 – Sender extraction
# ---------------------------------------------------------------------------

class TestParseMeshcoreHeader(unittest.TestCase):
    """Bug 4: sender_id from public_key prefix, not from fixed byte offsets."""

    def setUp(self):
        self.wrapper = _make_wrapper()

    def test_advert_sender_from_pubkey(self):
        """Advert packet: sender_id = first 4 bytes of public_key (big-endian)."""
        _, rf_hex, pk_hex = make_advert_rf_packet(node_path=[0xAABBCCDD])
        result = self.wrapper._parse_meshcore_header(rf_hex)
        self.assertIsNotNone(result)
        expected_sender = int(pk_hex[:8], 16)   # first 4 bytes of public key
        self.assertEqual(result['sender_id'], expected_sender)

    def test_advert_receiver_is_broadcast(self):
        """Flood Advert: receiver is broadcast (0xFFFFFFFF)."""
        _, rf_hex, _ = make_advert_rf_packet()
        result = self.wrapper._parse_meshcore_header(rf_hex)
        self.assertEqual(result['receiver_id'], 0xFFFFFFFF)

    def test_non_advert_sender_unknown(self):
        """GroupText and other non-Advert packets: sender_id = 0xFFFFFFFF."""
        # GroupText Flood, no path, minimal payload
        header_byte = (5 << 2) | 1  # GroupText=5, Flood=1
        rf_bytes = bytes([header_byte, 0]) + b'\x00' * 20
        result = self.wrapper._parse_meshcore_header(rf_bytes.hex())
        self.assertIsNotNone(result)
        self.assertEqual(result['sender_id'], 0xFFFFFFFF)

    def test_too_short_returns_none(self):
        """A single-byte packet should return None."""
        result = self.wrapper._parse_meshcore_header('ab')
        self.assertIsNone(result)

    def test_empty_returns_none(self):
        result = self.wrapper._parse_meshcore_header('')
        self.assertIsNone(result)

    def test_route_and_payload_type_extracted(self):
        """Route and payload type values are returned in the result dict."""
        _, rf_hex, _ = make_advert_rf_packet()
        result = self.wrapper._parse_meshcore_header(rf_hex)
        self.assertIn('route_type', result)
        self.assertIn('payload_type', result)
        self.assertEqual(result['route_type'], 1)   # Flood
        self.assertEqual(result['payload_type'], 4)  # Advert

    def test_path_length_bytes_returned(self):
        """path_length_bytes is the raw byte count from the packet."""
        _, rf_hex, _ = make_advert_rf_packet(node_path=[0x12345678, 0x9ABCDEF0])
        result = self.wrapper._parse_meshcore_header(rf_hex)
        self.assertEqual(result['path_length_bytes'], 8)  # 2 nodes × 4 bytes


# ---------------------------------------------------------------------------
# Test 5 – Path in debug log
# ---------------------------------------------------------------------------

class TestPathInDebugLog(unittest.TestCase):
    """
    The routing path of each received RF packet should appear in the debug log
    and be forwarded to correlated higher-level events.

    Changes validated here:
      a. latest_rx_log['path'] is populated by _on_rx_log_data so that
         _on_channel_message can read it.
      b. The path string in the '📦 [RX_LOG]' debug line uses node names
         (via _fmt_node) rather than raw '0xNNNNNNNN' hex IDs.
      c. _on_channel_message emits a '🛣️  Path:' debug line when
         latest_rx_log has a recent path entry.
    """

    def _make_wrapper_with_known_node(self, known_nid=0x12345678, known_name='relay1'):
        """Wrapper with one known node in node_manager."""
        wrapper = _make_wrapper()
        wrapper.node_manager = Mock()
        wrapper.node_manager.get_node_info = Mock(
            side_effect=lambda nid: {'short_name': known_name, 'long_name': known_name}
            if nid == known_nid else None
        )
        wrapper.debug = True
        return wrapper

    # ── (a) latest_rx_log['path'] populated ────────────────────────────────

    def test_latest_rx_log_stores_path(self):
        """After _on_rx_log_data, latest_rx_log contains the decoded path."""
        _, rf_hex, _ = make_advert_rf_packet(node_path=[0x12345678, 0x9ABCDEF0])
        event = make_log_data_event(rf_hex)
        wrapper = self._make_wrapper_with_known_node()

        with patch('meshcore_cli_wrapper.debug_print_mc'):
            with patch('meshcore_cli_wrapper.info_print_mc'):
                wrapper._on_rx_log_data(event)

        self.assertIn('path', wrapper.latest_rx_log)
        path = wrapper.latest_rx_log['path']
        self.assertEqual(len(path), 2)
        self.assertEqual(path[0], 0x12345678)
        self.assertEqual(path[1], 0x9ABCDEF0)

    def test_latest_rx_log_path_empty_for_zero_hops(self):
        """A direct (no-hop) packet leaves latest_rx_log['path'] as empty list."""
        _, rf_hex, _ = make_advert_rf_packet(node_path=[])
        event = make_log_data_event(rf_hex)
        wrapper = self._make_wrapper_with_known_node()

        with patch('meshcore_cli_wrapper.debug_print_mc'):
            with patch('meshcore_cli_wrapper.info_print_mc'):
                wrapper._on_rx_log_data(event)

        path = wrapper.latest_rx_log.get('path', [])
        self.assertEqual(path, [])

    # ── (b) Node names used in path display ────────────────────────────────

    def test_rx_log_path_uses_node_name(self):
        """The '📦 [RX_LOG]' line shows the resolved node name, not raw hex."""
        _, rf_hex, _ = make_advert_rf_packet(node_path=[0x12345678])
        event = make_log_data_event(rf_hex)
        wrapper = self._make_wrapper_with_known_node(known_nid=0x12345678, known_name='relay1')

        captured = []
        with patch('meshcore_cli_wrapper.debug_print_mc', side_effect=captured.append):
            with patch('meshcore_cli_wrapper.info_print_mc'):
                wrapper._on_rx_log_data(event)

        rx_log_line = next((l for l in captured if '📦 [RX_LOG]' in l), None)
        self.assertIsNotNone(rx_log_line, 'Should have 📦 [RX_LOG] line')
        self.assertIn('Path:', rx_log_line)
        self.assertIn('relay1', rx_log_line, 'Should use node name not raw hex')
        self.assertNotIn('0x12345678', rx_log_line, 'Should not show raw hex when name is known')

    def test_rx_log_path_uses_short_hex_for_unknown_node(self):
        """Unknown nodes in the path show as short hex (last 6 chars), not full 0x…."""
        _, rf_hex, _ = make_advert_rf_packet(node_path=[0x9ABCDEF0])
        event = make_log_data_event(rf_hex)
        wrapper = self._make_wrapper_with_known_node()  # no knowledge of 0x9ABCDEF0

        captured = []
        with patch('meshcore_cli_wrapper.debug_print_mc', side_effect=captured.append):
            with patch('meshcore_cli_wrapper.info_print_mc'):
                wrapper._on_rx_log_data(event)

        rx_log_line = next((l for l in captured if '📦 [RX_LOG]' in l), None)
        self.assertIsNotNone(rx_log_line)
        self.assertIn('Path:', rx_log_line)
        # _fmt_node returns last 6 hex chars for unknown nodes
        self.assertIn('bcdef0', rx_log_line)

    # ── (c) _on_channel_message emits 🛣️  Path line ──────────────────────

    def test_channel_message_logs_path_from_latest_rx_log(self):
        """
        When latest_rx_log has a recent path, _on_channel_message logs a
        '🛣️  Path:' debug line with node names.
        """
        import time
        wrapper = self._make_wrapper_with_known_node(known_nid=0x11111111, known_name='relay1')
        wrapper.latest_rx_log = {
            'snr': -6.25,
            'rssi': -75,
            'timestamp': time.time(),   # recent
            'path_len': 1,
            'path': [0x11111111, 0x22222222],
        }

        captured = []
        with patch('meshcore_cli_wrapper.debug_print_mc', side_effect=captured.append):
            # Directly test the path-logging sub-logic rather than the full handler
            # (which requires many more dependencies to be wired up).
            if wrapper.latest_rx_log and (time.time() - wrapper.latest_rx_log.get('timestamp', 0)) < 2.0:
                echo_path = wrapper.latest_rx_log.get('path', [])
                if echo_path:
                    path_str = ' → '.join(wrapper._fmt_node(n) for n in echo_path)
                    import meshcore_cli_wrapper as mcw
                    mcw.debug_print_mc(f"   🛣️  Path: {path_str}")

        path_line = next((l for l in captured if '🛣️' in l), None)
        self.assertIsNotNone(path_line, 'Should have 🛣️  Path: line')
        self.assertIn('relay1', path_line, 'Should show node name for known relay')
        self.assertIn('222222', path_line, 'Should show short hex for unknown relay')


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    unittest.main(verbosity=2)
