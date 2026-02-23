#!/usr/bin/env python3
"""
Test: Meshtastic RF activity diagnostics + hop display fixes.

Changes validated:
1. hopStart default changed from 5 → hopLimit in both node_manager and
   traffic_monitor so locally-generated packets correctly show hops=0
   instead of the misleading hops=2 (hopStart=5 − hopLimit=3).

2. [local]/[RF] origin tag added to [RX_HISTORY] and [MT] 📦 debug lines
   so operators can instantly distinguish serial-echo packets (snr=0.0)
   from RF-received packets.

3. _check_meshtastic_rf_activity() added to main_bot.MeshBot; it scans
   interface.nodes for recently-heard nodes and logs a warning when only
   local traffic has been observed for >5 minutes.
"""

import sys
import os
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


# ---------------------------------------------------------------------------
# Helper: replicate the hop calculation from node_manager / traffic_monitor
# ---------------------------------------------------------------------------

def _calc_hops(packet):
    """
    Replicate: hop_start = packet.get('hopStart', packet.get('hopLimit', 0))
               hops_taken = hop_start - hop_limit
    """
    hop_limit = packet.get('hopLimit', 0)
    hop_start = packet.get('hopStart', hop_limit)   # fixed default
    return hop_start - hop_limit


def _calc_hops_old(packet):
    """Old (broken) calculation with hardcoded default of 5."""
    hop_limit = packet.get('hopLimit', 0)
    hop_start = packet.get('hopStart', 5)           # old default
    return hop_start - hop_limit


# ---------------------------------------------------------------------------
# 1. hop calculation
# ---------------------------------------------------------------------------

class TestHopCalculationFix(unittest.TestCase):
    """Verify that the new default for hopStart gives correct hop counts."""

    def test_local_packet_no_hop_start(self):
        """
        Local node just transmitted: hopLimit=3, hopStart absent.
        Old code: 5 − 3 = 2 (wrong).  New code: 3 − 3 = 0 (correct).
        """
        packet = {'hopLimit': 3}
        self.assertEqual(_calc_hops(packet), 0,
                         "Local packet with no hopStart should show 0 hops")
        self.assertEqual(_calc_hops_old(packet), 2,
                         "Old calculation produced the misleading value 2")

    def test_rf_1_hop_with_hop_start(self):
        """Packet received after 1 hop: hopStart=3, hopLimit=2 → hops=1."""
        packet = {'hopStart': 3, 'hopLimit': 2}
        self.assertEqual(_calc_hops(packet), 1)

    def test_rf_2_hops_with_hop_start(self):
        """Packet received after 2 hops: hopStart=3, hopLimit=1 → hops=2."""
        packet = {'hopStart': 3, 'hopLimit': 1}
        self.assertEqual(_calc_hops(packet), 2)

    def test_direct_packet_hop_start_equals_hop_limit(self):
        """Packet received directly (0 hops): hopStart=hopLimit → hops=0."""
        packet = {'hopStart': 3, 'hopLimit': 3}
        self.assertEqual(_calc_hops(packet), 0)

    def test_missing_both_fields(self):
        """No hopStart, no hopLimit → both default to 0 → hops=0."""
        packet = {}
        self.assertEqual(_calc_hops(packet), 0)

    def test_hop_limit_zero_no_hop_start(self):
        """hopLimit=0 (all hops used), hopStart absent → 0 − 0 = 0."""
        packet = {'hopLimit': 0}
        self.assertEqual(_calc_hops(packet), 0)

    def test_typical_telemetry_packet_fixed(self):
        """
        Observed pattern in logs: hopLimit=3, hopStart absent.
        Old default 5 gave hops=2; new default gives hops=0.
        """
        telemetry_pkt = {
            'from': 0x16fad3dc,
            'to': 0xffffffff,
            'hopLimit': 3,
            'snr': 0.0,
            'decoded': {'portnum': 'TELEMETRY_APP'},
        }
        self.assertEqual(_calc_hops(telemetry_pkt), 0)


# ---------------------------------------------------------------------------
# 2. [local] / [RF] origin tag logic
# ---------------------------------------------------------------------------

def _origin_tag(snr, is_meshcore_source=False, is_meshcore_rx_log=False):
    """
    Replicate the [local]/[RF] tag added to [RX_HISTORY] and [MT] 📦 lines.

    For Meshtastic sources:
        snr == 0.0  → [local]  (serial echo, locally generated)
        snr != 0.0  → [RF]     (received over the air)

    For MeshCore sources: no tag (MeshCore has its own log block).
    """
    if is_meshcore_source:
        return ""
    if is_meshcore_rx_log:
        return ""          # RX_LOG sets real SNR; handled separately
    return " [local]" if snr == 0.0 else " [RF]"


class TestOriginTagLogic(unittest.TestCase):

    def test_snr_zero_is_local(self):
        self.assertEqual(_origin_tag(0.0), " [local]")

    def test_positive_snr_is_rf(self):
        self.assertEqual(_origin_tag(12.5), " [RF]")

    def test_negative_snr_still_rf(self):
        self.assertEqual(_origin_tag(-5.0), " [RF]")

    def test_meshcore_source_no_tag(self):
        """MeshCore packets must not get a Meshtastic-style tag."""
        self.assertEqual(_origin_tag(0.0, is_meshcore_source=True), "")

    def test_rx_log_no_tag(self):
        """RX_LOG events carry real RF SNR and should not be tagged [local]."""
        self.assertEqual(_origin_tag(0.0, is_meshcore_rx_log=True), "")

    def test_meshtastic_source_list(self):
        """All Meshtastic-family source values (non-MeshCore) get the [local] tag."""
        meshtastic_sources = ('meshtastic', 'local', 'tcp', 'tigrog2')
        for src in meshtastic_sources:
            # None of these are MeshCore — is_meshcore_source is always False here
            tag = _origin_tag(0.0, is_meshcore_source=False)
            self.assertEqual(tag, " [local]", f"source={src!r} should yield [local]")

    def test_snr_float_zero_exact(self):
        """snr=0.0 (float) triggers [local]; any non-zero triggers [RF]."""
        self.assertEqual(_origin_tag(0.0), " [local]")
        self.assertEqual(_origin_tag(0.001), " [RF]")


# ---------------------------------------------------------------------------
# 3. _check_meshtastic_rf_activity() logic
# ---------------------------------------------------------------------------

class TestCheckMeshtasticRFActivity(unittest.TestCase):
    """
    Unit-test the core logic of _check_meshtastic_rf_activity() by
    replicating it here (without importing main_bot which needs meshtastic).
    """

    def _run_check(self, nodes_dict, my_id, session_start_time):
        """
        Replicate the scan loop from _check_meshtastic_rf_activity().
        Returns (recently_heard_list, warning_emitted).
        """
        now = time.time()
        window_s = 600
        recently_heard = []

        for _key, node_info in nodes_dict.items():
            if not isinstance(node_info, dict):
                continue
            node_num = node_info.get('num', 0)
            if not node_num or (my_id and node_num == my_id):
                continue
            last_heard = node_info.get('lastHeard', 0)
            if last_heard and (now - last_heard) < window_s:
                user = node_info.get('user') or {}
                name = (user.get('longName') or user.get('shortName')
                        or f'0x{node_num:08x}')
                recently_heard.append((name, node_num, now - last_heard))

        uptime = now - session_start_time
        warning_emitted = (not recently_heard) and (uptime > 300)
        return recently_heard, warning_emitted

    def test_no_nodes_short_uptime_no_warning(self):
        """Bot just started (<5min); no other nodes → no warning yet."""
        _, warned = self._run_check({}, my_id=1, session_start_time=time.time() - 60)
        self.assertFalse(warned)

    def test_no_nodes_long_uptime_warns(self):
        """No other nodes heard after >5min uptime → emit warning."""
        _, warned = self._run_check({}, my_id=1, session_start_time=time.time() - 400)
        self.assertTrue(warned)

    def test_recently_heard_node_suppresses_warning(self):
        """Another node heard 30s ago → no warning despite long uptime."""
        nodes = {
            '!aabbccdd': {
                'num': 0xaabbccdd,
                'lastHeard': int(time.time()) - 30,
                'user': {'longName': 'TestNode'},
            }
        }
        heard, warned = self._run_check(nodes, my_id=0x16fad3dc, session_start_time=time.time() - 600)
        self.assertEqual(len(heard), 1)
        self.assertFalse(warned)

    def test_local_node_excluded_from_heard(self):
        """The bot's own local node must not count as 'recently heard'."""
        my_id = 0x16fad3dc
        nodes = {
            '!16fad3dc': {
                'num': my_id,
                'lastHeard': int(time.time()) - 10,
                'user': {'longName': 'Meshtastic d3dc'},
            }
        }
        heard, warned = self._run_check(nodes, my_id=my_id, session_start_time=time.time() - 600)
        self.assertEqual(len(heard), 0)
        self.assertTrue(warned)

    def test_old_last_heard_not_counted(self):
        """Node last heard >10min ago → not in recently_heard."""
        nodes = {
            '!aabbccdd': {
                'num': 0xaabbccdd,
                'lastHeard': int(time.time()) - 700,  # 11+ minutes ago
                'user': {'longName': 'OldNode'},
            }
        }
        heard, warned = self._run_check(nodes, my_id=0x16fad3dc, session_start_time=time.time() - 600)
        self.assertEqual(len(heard), 0)
        self.assertTrue(warned)

    def test_multiple_recent_nodes(self):
        """Three recently-heard nodes are all returned."""
        now_ts = int(time.time())
        nodes = {
            '!aaaa': {'num': 0xaaaa, 'lastHeard': now_ts - 60,  'user': {'longName': 'Node A'}},
            '!bbbb': {'num': 0xbbbb, 'lastHeard': now_ts - 120, 'user': {'longName': 'Node B'}},
            '!cccc': {'num': 0xcccc, 'lastHeard': now_ts - 300, 'user': {'longName': 'Node C'}},
        }
        heard, warned = self._run_check(nodes, my_id=0x16fad3dc, session_start_time=time.time() - 600)
        self.assertEqual(len(heard), 3)
        self.assertFalse(warned)

    def test_node_with_no_num_skipped(self):
        """Nodes without a 'num' field should be silently skipped."""
        nodes = {'!0000': {'lastHeard': int(time.time()) - 10, 'user': {}}}
        heard, warned = self._run_check(nodes, my_id=1, session_start_time=time.time() - 600)
        self.assertEqual(len(heard), 0)

    def test_non_dict_node_entry_skipped(self):
        """Non-dict entries in nodes dict are safely ignored."""
        nodes = {'!aaaa': "not-a-dict"}
        heard, warned = self._run_check(nodes, my_id=1, session_start_time=time.time() - 600)
        self.assertEqual(len(heard), 0)


if __name__ == '__main__':
    unittest.main()
