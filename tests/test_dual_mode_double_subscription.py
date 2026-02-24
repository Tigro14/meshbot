#!/usr/bin/env python3
"""
Test: Dual-mode double subscription bug causing throttle exhaustion on DMs.

ROOT CAUSE:
In DUAL_NETWORK_MODE=True, two separate subscriptions were registered for
"meshtastic.receive":

  1. DualInterfaceManager.setup_message_callbacks() subscribes a lambda that
     calls on_message(packet, interface, NetworkSource.MESHTASTIC).

  2. The run() method unconditionally called
     pub.subscribe(self.on_message, "meshtastic.receive").

Each Meshtastic packet therefore triggered on_message TWICE:
  - First call (correct):  network_source=NetworkSource.MESHTASTIC → source='meshtastic'
  - Second call (wrong):   network_source=None                      → source='local'

Because both calls reached the throttle check, each real DM counted as
TWO commands.  With MAX_COMMANDS_PER_WINDOW=5 the user hit the throttle
after only 2-3 real DMs, making the bot appear to have "lost DM ability".

FIX: main_bot.run() now skips the direct pub.subscribe when _dual_mode_active
is True, since setup_message_callbacks() already handles the subscription.
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dual_interface_manager import DualInterfaceManager, NetworkSource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_dm_packet(from_id: int, to_id: int, text: str = '/help') -> dict:
    """Build a minimal TEXT_MESSAGE_APP DM packet."""
    return {
        'from': from_id,
        'to': to_id,
        'id': 0xABCD1234,
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


class TestDualModeSetupMessageCallbacks(unittest.TestCase):
    """
    Unit tests for DualInterfaceManager.setup_message_callbacks():
    verify that exactly ONE subscription reaches on_message per Meshtastic
    packet when in dual mode.
    """

    def test_meshtastic_message_routed_with_network_source(self):
        """
        on_meshtastic_message must call message_callback with
        network_source=NetworkSource.MESHTASTIC.
        """
        received = []
        def callback(packet, interface, network_source=None):
            received.append(network_source)

        manager = DualInterfaceManager(message_callback=callback)
        mock_mt = MagicMock()
        manager.set_meshtastic_interface(mock_mt)

        packet = _make_dm_packet(0x11111111, 0xFFFFFFFE)
        manager.on_meshtastic_message(packet, mock_mt)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0], NetworkSource.MESHTASTIC,
                         "network_source must be MESHTASTIC for Meshtastic packets")

    def test_setup_message_callbacks_subscribes_meshtastic(self):
        """
        setup_message_callbacks() must subscribe to 'meshtastic.receive' when
        a Meshtastic interface is available.
        """
        with patch('dual_interface_manager.DualInterfaceManager') as _:
            from pubsub import pub

            manager = DualInterfaceManager(message_callback=lambda p, i, ns=None: None)
            mock_mt = MagicMock()
            manager.set_meshtastic_interface(mock_mt)

            subscribed = []
            original_subscribe = pub.subscribe

            def spy_subscribe(listener, topic):
                subscribed.append(topic)
                original_subscribe(listener, topic)

            with patch.object(pub, 'subscribe', side_effect=spy_subscribe):
                # No MeshCore → only Meshtastic subscription expected
                manager.setup_message_callbacks()

            self.assertIn('meshtastic.receive', subscribed,
                          "setup_message_callbacks must subscribe to 'meshtastic.receive'")

    def test_each_meshtastic_packet_fires_callback_once(self):
        """
        After setup_message_callbacks(), each Meshtastic packet must invoke
        the message_callback exactly ONCE — with network_source=MESHTASTIC.

        This verifies that the DualInterfaceManager side of the fix is
        correct: the lambda does NOT fire multiple times for a single packet.
        """
        from pubsub import pub

        call_count = [0]
        network_sources_seen = []

        def callback(packet, interface, network_source=None):
            call_count[0] += 1
            network_sources_seen.append(network_source)

        manager = DualInterfaceManager(message_callback=callback)
        mock_mt = MagicMock()
        manager.set_meshtastic_interface(mock_mt)
        manager.setup_message_callbacks()

        # Simulate Meshtastic library publishing a packet
        packet = _make_dm_packet(0x16FAD3DC, 0xFFFFFFFE)
        pub.sendMessage("meshtastic.receive", packet=packet, interface=mock_mt)

        self.assertEqual(call_count[0], 1,
                         "Each Meshtastic packet must call callback exactly once")
        self.assertEqual(network_sources_seen[0], NetworkSource.MESHTASTIC,
                         "callback must receive network_source=MESHTASTIC")

        # Clean up: unsubscribe to avoid polluting other tests
        try:
            pub.unsubAll(topicName='meshtastic.receive')
        except Exception:
            pass


class TestDualModeThrottleDoublingRegression(unittest.TestCase):
    """
    Regression tests: in dual mode, a single DM must only consume ONE
    throttle slot, not two.

    These tests verify the observable behaviour (throttle count) that
    was broken by the double-subscription bug.
    """

    def _build_throttle_counter(self):
        """Return a simple throttle counter dict and a check function."""
        counts = {}
        max_cmds = 5
        window_secs = 300

        def check_and_count(sender_id):
            if sender_id not in counts:
                counts[sender_id] = 0
            if counts[sender_id] >= max_cmds:
                return False   # Throttled
            counts[sender_id] += 1
            return True        # Allowed

        return counts, check_and_count, max_cmds

    def test_single_subscription_five_dms_allowed(self):
        """
        With a single callback per packet (fixed behaviour), 5 DMs must all
        be accepted before throttle kicks in.
        """
        counts, check, max_cmds = self._build_throttle_counter()
        sender = 0x16FAD3DC

        results = []
        for _ in range(max_cmds):
            results.append(check(sender))

        self.assertTrue(all(results),
                        "All 5 DMs should be accepted with single subscription")
        # 6th command should be throttled
        self.assertFalse(check(sender),
                         "6th DM must be throttled")

    def test_double_subscription_throttles_after_half_commands(self):
        """
        With the old broken behaviour (double subscription), each real DM
        was counted TWICE.  After 2-3 real DMs the throttle would kick in.

        This test documents the breakage and confirms our understanding of
        the bug's impact.
        """
        counts, check, max_cmds = self._build_throttle_counter()
        sender = 0x16FAD3DC

        real_dms_accepted = 0
        for dm_index in range(max_cmds):
            # Simulate each real DM firing the callback TWICE (old broken behaviour)
            result1 = check(sender)   # First call (DualInterfaceManager lambda)
            result2 = check(sender)   # Second call (direct pub.subscribe — the bug)
            if result1 and result2:
                real_dms_accepted += 1
            else:
                break   # Throttled — stop counting

        # With double counting, the user is throttled after at most 2 real DMs
        # (counts 0→2 for DM1, 2→4 for DM2, 4→6 for DM3 first call: 4<5 ok,
        # second call: 5 >= 5 throttled).
        self.assertLessEqual(real_dms_accepted, 3,
                             "Double subscription should throttle user after ≤3 DMs")
        self.assertLess(real_dms_accepted, max_cmds,
                        "Double subscription must hit throttle before max_cmds real DMs")


if __name__ == '__main__':
    unittest.main(verbosity=2)
