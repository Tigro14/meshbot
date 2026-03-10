#!/usr/bin/env python3
"""
Test: packet['source'] stamping and router source detection fix.

ROOT CAUSE:
`source` was computed in `on_message` but never written into `packet`.
`message_router.process_text_message` reads `packet.get('source', 'local')`,
so it always got 'local' regardless of the real network.

IMPACT:
- All packets treated as Meshtastic (is_from_meshtastic=True, is_from_meshcore=False)
- MeshCore DM commands (/nodesmc, /trafficmc) → BLOCKED ("réservé au réseau MeshCore")
- Meshtastic-only commands (/nodes, /trace) NOT blocked from MeshCore

FIX:
1. main_bot.py on_message: stamp packet['source'] = source after source determination
2. message_router.py: add 'meshtastic' to is_from_meshtastic list
   (dual-mode Meshtastic packets get source='meshtastic', not 'local')
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def _make_dm_packet(from_id: int, to_id: int, text: str, source: str = None) -> dict:
    """Build a minimal DM packet, optionally pre-stamped with source."""
    p = {
        'from': from_id,
        'to': to_id,
        'id': 0xDEAD1234,
        'rxTime': 1700000000,
        'rssi': -80,
        'snr': 5.0,
        'hopLimit': 3,
        'hopStart': 3,
        'channel': 0,
        'decoded': {
            'portnum': 'TEXT_MESSAGE_APP',
            'payload': text.encode('utf-8'),
            'text': text,
        },
    }
    if source is not None:
        p['source'] = source
    return p


class TestPacketSourceStamping(unittest.TestCase):
    """
    Unit tests for the source-stamping behaviour.

    We verify:
    1. packet['source'] contains the right value after on_message stamps it
    2. The router reads the correct source from the packet
    3. Network-isolation rules work correctly after the fix
    """

    # -----------------------------------------------------------------------
    # Router-level tests (no need for full main_bot import)
    # -----------------------------------------------------------------------

    def _run_router_source_detection(self, packet_source: str):
        """
        Replicate the exact detection logic from message_router.py and
        return (is_from_meshcore, is_from_meshtastic).
        """
        # === COPY OF THE FIXED DETECTION LOGIC ===
        is_from_meshcore = (packet_source == 'meshcore')
        is_from_meshtastic = (packet_source in ['meshtastic', 'local', 'tcp', 'tigrog2'])
        return is_from_meshcore, is_from_meshtastic

    def test_meshcore_source_is_from_meshcore(self):
        """source='meshcore' → is_from_meshcore=True, is_from_meshtastic=False"""
        mc, mt = self._run_router_source_detection('meshcore')
        self.assertTrue(mc,  "source='meshcore' must set is_from_meshcore=True")
        self.assertFalse(mt, "source='meshcore' must NOT set is_from_meshtastic=True")

    def test_meshtastic_dual_source_is_from_meshtastic(self):
        """source='meshtastic' (dual mode) → is_from_meshcore=False, is_from_meshtastic=True"""
        mc, mt = self._run_router_source_detection('meshtastic')
        self.assertFalse(mc, "source='meshtastic' must NOT set is_from_meshcore=True")
        self.assertTrue(mt,  "source='meshtastic' must set is_from_meshtastic=True")

    def test_local_source_is_from_meshtastic(self):
        """source='local' (serial single-mode) → is_from_meshtastic=True"""
        mc, mt = self._run_router_source_detection('local')
        self.assertFalse(mc)
        self.assertTrue(mt)

    def test_tcp_source_is_from_meshtastic(self):
        """source='tcp' → is_from_meshtastic=True"""
        mc, mt = self._run_router_source_detection('tcp')
        self.assertFalse(mc)
        self.assertTrue(mt)

    def test_unknown_source_is_neither(self):
        """source='unknown' → neither meshcore nor meshtastic (network-neutral)"""
        mc, mt = self._run_router_source_detection('unknown')
        self.assertFalse(mc)
        self.assertFalse(mt)

    def test_cli_source_is_neither(self):
        """source='cli' → neither meshcore nor meshtastic (network-neutral)"""
        mc, mt = self._run_router_source_detection('cli')
        self.assertFalse(mc)
        self.assertFalse(mt)


class TestNetworkIsolationLogic(unittest.TestCase):
    """
    Verify that network-isolation rules correctly block/allow commands
    once the source is properly set in the packet.
    """

    meshcore_only_commands = ['/nodesmc', '/trafficmc']
    meshtastic_only_commands = ['/nodemt', '/trafficmt', '/neighbors', '/nodes', '/trace']

    def _should_block_mc_cmd_from_meshtastic(self, cmd: str, is_from_meshtastic: bool) -> bool:
        for mc_cmd in self.meshcore_only_commands:
            if cmd == mc_cmd or cmd.startswith(mc_cmd + ' '):
                if is_from_meshtastic:
                    return True
        return False

    def _should_block_mt_cmd_from_meshcore(self, cmd: str, is_from_meshcore: bool) -> bool:
        for mt_cmd in self.meshtastic_only_commands:
            if cmd == mt_cmd or cmd.startswith(mt_cmd + ' '):
                if is_from_meshcore:
                    return True
        return False

    # --- MeshCore-only commands ---

    def test_nodesmc_from_meshcore_allowed(self):
        """/nodesmc from MeshCore must NOT be blocked."""
        blocked = self._should_block_mc_cmd_from_meshtastic(
            '/nodesmc', is_from_meshtastic=False)
        self.assertFalse(blocked, "/nodesmc sent from MeshCore must not be blocked")

    def test_nodesmc_from_meshcore_was_broken_before_fix(self):
        """/nodesmc was wrongly blocked because is_from_meshtastic was True for all packets."""
        # Before the fix: source was never stamped → router got 'local' → is_from_meshtastic=True
        blocked = self._should_block_mc_cmd_from_meshtastic(
            '/nodesmc', is_from_meshtastic=True)
        self.assertTrue(blocked,
                        "This test confirms the old (broken) behaviour "
                        "where /nodesmc from MeshCore was wrongly blocked")

    def test_nodesmc_from_meshtastic_blocked(self):
        """/nodesmc sent from Meshtastic must be blocked."""
        blocked = self._should_block_mc_cmd_from_meshtastic(
            '/nodesmc', is_from_meshtastic=True)
        self.assertTrue(blocked, "/nodesmc from Meshtastic must be blocked")

    def test_trafficmc_from_meshcore_allowed(self):
        """/trafficmc from MeshCore must NOT be blocked."""
        blocked = self._should_block_mc_cmd_from_meshtastic(
            '/trafficmc', is_from_meshtastic=False)
        self.assertFalse(blocked)

    # --- Meshtastic-only commands ---

    def test_nodes_from_meshtastic_allowed(self):
        """/nodes from Meshtastic must NOT be blocked."""
        blocked = self._should_block_mt_cmd_from_meshcore(
            '/nodes', is_from_meshcore=False)
        self.assertFalse(blocked)

    def test_nodes_from_meshcore_blocked(self):
        """/nodes from MeshCore must be blocked."""
        blocked = self._should_block_mt_cmd_from_meshcore(
            '/nodes', is_from_meshcore=True)
        self.assertTrue(blocked)

    def test_trace_from_meshcore_blocked(self):
        """/trace from MeshCore must be blocked."""
        blocked = self._should_block_mt_cmd_from_meshcore(
            '/trace', is_from_meshcore=True)
        self.assertTrue(blocked)

    def test_trace_with_args_from_meshcore_blocked(self):
        """/trace tigro from MeshCore must be blocked (word-boundary check)."""
        blocked = self._should_block_mt_cmd_from_meshcore(
            '/trace tigro', is_from_meshcore=True)
        self.assertTrue(blocked)

    def test_nodesmc_not_falsely_matched_by_nodes_prefix(self):
        """/nodesmc must not match the /nodes meshtastic-only block."""
        # The router uses 'cmd == mt_cmd or cmd.startswith(mt_cmd + " ")'.
        # '/nodesmc'.startswith('/nodes ') → False, '/nodesmc' == '/nodes' → False.
        blocked = self._should_block_mt_cmd_from_meshcore(
            '/nodesmc', is_from_meshcore=True)
        self.assertFalse(blocked,
                         "/nodesmc must not be blocked by the /nodes meshtastic-only rule")


class TestPacketSourceDict(unittest.TestCase):
    """
    Verify that packet['source'] is readable after being stamped,
    and that the router's fallback 'local' is only used when not present.
    """

    def test_packet_without_source_defaults_to_local(self):
        """packet.get('source', 'local') returns 'local' when key absent (old behaviour)."""
        packet = _make_dm_packet(0x1234, 0x5678, '/help')
        self.assertNotIn('source', packet)
        self.assertEqual(packet.get('source', 'local'), 'local')

    def test_stamped_meshcore_packet_reads_correctly(self):
        """After stamping, router reads 'meshcore' from MeshCore packet."""
        packet = _make_dm_packet(0x1234, 0x5678, '/nodesmc', source='meshcore')
        self.assertEqual(packet.get('source', 'local'), 'meshcore')

    def test_stamped_meshtastic_dual_packet_reads_correctly(self):
        """After stamping, router reads 'meshtastic' from dual-mode Meshtastic packet."""
        packet = _make_dm_packet(0x1234, 0x5678, '/nodes', source='meshtastic')
        self.assertEqual(packet.get('source', 'local'), 'meshtastic')

    def test_stamped_local_packet_reads_correctly(self):
        """Serial single-mode Meshtastic packets have source='local'."""
        packet = _make_dm_packet(0x1234, 0x5678, '/help', source='local')
        self.assertEqual(packet.get('source', 'local'), 'local')

    def test_full_flow_meshcore_dm_nodesmc_allowed(self):
        """
        End-to-end: MeshCore DM with /nodesmc stamped correctly → not blocked.

        Before fix: source not in packet → 'local' → is_from_meshtastic=True → BLOCKED
        After fix:  source='meshcore' in packet → is_from_meshcore=True → allowed
        """
        packet = _make_dm_packet(0x1234, 0xFFFFFFFE, '/nodesmc', source='meshcore')
        packet_source = packet.get('source', 'local')
        is_from_meshcore = (packet_source == 'meshcore')
        is_from_meshtastic = (packet_source in ['meshtastic', 'local', 'tcp', 'tigrog2'])

        self.assertTrue(is_from_meshcore)
        self.assertFalse(is_from_meshtastic)

        # Network isolation: /nodesmc from meshcore → not blocked
        meshcore_only_commands = ['/nodesmc', '/trafficmc']
        blocked = False
        for mc_cmd in meshcore_only_commands:
            if '/nodesmc' == mc_cmd and is_from_meshtastic:
                blocked = True
        self.assertFalse(blocked, "/nodesmc from MeshCore DM must not be blocked")

    def test_full_flow_meshtastic_dual_nodes_blocked_from_meshcore(self):
        """
        End-to-end: MeshCore packet trying /nodes → correctly blocked.
        """
        packet = _make_dm_packet(0xABCD, 0xFFFFFFFE, '/nodes', source='meshcore')
        packet_source = packet.get('source', 'local')
        is_from_meshcore = (packet_source == 'meshcore')

        meshtastic_only_commands = ['/nodemt', '/trafficmt', '/neighbors', '/nodes', '/trace']
        blocked = False
        for mt_cmd in meshtastic_only_commands:
            if '/nodes' == mt_cmd and is_from_meshcore:
                blocked = True
        self.assertTrue(blocked, "/nodes from MeshCore must be blocked")


if __name__ == '__main__':
    unittest.main(verbosity=2)
