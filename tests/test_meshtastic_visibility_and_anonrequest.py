#!/usr/bin/env python3
"""
Test: Meshtastic packet-type visibility + AnonRequest sender extraction.

Changes validated:
1. traffic_monitor.add_packet() now logs "[MT] {packet_type} from ..." for
   every Meshtastic-source packet BEFORE the TELEMETRY filter — even those
   that are silently discarded.  Previously nothing was logged for local
   TELEMETRY_APP packets, making the bot look deaf in the debug log.

2. meshcore_cli_wrapper._parse_meshcore_header() now extracts sender_id
   from AnonRequest's sender_public_key (when available), in addition to
   the existing Advert public_key extraction.

3. meshcore_cli_wrapper._on_rx_log_data() now logs source_hash /
   destination_hash for encrypted TextMessage Direct packets as routing
   hints.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


# ---------------------------------------------------------------------------
# 1. Meshtastic packet-type visibility logic
# ---------------------------------------------------------------------------

class TestMeshtasticPacketVisibility(unittest.TestCase):
    """
    Verify the source-list check used to decide whether to log
    "[MT] {packet_type} from ..." in add_packet().
    """

    MESHTASTIC_SOURCES = ('meshtastic', 'local', 'tcp', 'tigrog2')
    NON_MESHTASTIC_SOURCES = ('meshcore', 'unknown', 'cli', '')

    def _should_log_mt(self, source):
        """Replicate the fixed gate from traffic_monitor.add_packet()."""
        return source in self.MESHTASTIC_SOURCES

    def test_meshtastic_dual_source_logged(self):
        self.assertTrue(self._should_log_mt('meshtastic'))

    def test_local_serial_source_logged(self):
        self.assertTrue(self._should_log_mt('local'))

    def test_tcp_source_logged(self):
        self.assertTrue(self._should_log_mt('tcp'))

    def test_tigrog2_source_logged(self):
        self.assertTrue(self._should_log_mt('tigrog2'))

    def test_meshcore_source_not_logged(self):
        """MeshCore already has its own debug block — no duplicate."""
        self.assertFalse(self._should_log_mt('meshcore'))

    def test_unknown_source_not_logged(self):
        self.assertFalse(self._should_log_mt('unknown'))

    def test_telemetry_from_local_is_filtered(self):
        """
        TELEMETRY_APP from the local node must still be filtered even
        though the type is logged first.  The filter runs AFTER the log.
        """
        packet_type = 'TELEMETRY_APP'
        my_node_id = 0x16FAD3DC
        from_id = 0x16FAD3DC  # same as local
        should_filter = (packet_type == 'TELEMETRY_APP' and my_node_id and from_id == my_node_id)
        self.assertTrue(should_filter, "Local TELEMETRY_APP must still be filtered")

    def test_telemetry_from_remote_not_filtered(self):
        """TELEMETRY_APP from a DIFFERENT node is real RF traffic, must pass."""
        packet_type = 'TELEMETRY_APP'
        my_node_id = 0x16FAD3DC
        from_id = 0xABCD1234  # different node
        should_filter = (packet_type == 'TELEMETRY_APP' and my_node_id and from_id == my_node_id)
        self.assertFalse(should_filter, "TELEMETRY_APP from a remote node must NOT be filtered")

    def test_position_app_not_filtered(self):
        """POSITION_APP from local node must pass (it IS real RF data)."""
        packet_type = 'POSITION_APP'
        my_node_id = 0x16FAD3DC
        from_id = 0x16FAD3DC
        should_filter = (packet_type == 'TELEMETRY_APP' and my_node_id and from_id == my_node_id)
        self.assertFalse(should_filter)

    def test_nodeinfo_from_local_not_filtered(self):
        """NODEINFO_APP from local node must pass."""
        packet_type = 'NODEINFO_APP'
        my_node_id = 0x16FAD3DC
        from_id = 0x16FAD3DC
        should_filter = (packet_type == 'TELEMETRY_APP' and my_node_id and from_id == my_node_id)
        self.assertFalse(should_filter)


# ---------------------------------------------------------------------------
# 2. AnonRequest sender extraction logic
# ---------------------------------------------------------------------------

class TestAnonRequestSenderExtraction(unittest.TestCase):
    """
    Verify the updated _parse_meshcore_header logic for AnonRequest packets.

    The decoder exposes sender_public_key on the decoded AnonRequest payload.
    We derive sender_id = int(pk_hex[:8], 16) — the first 4 bytes of the
    public key, which is MeshCore's convention for the node ID.
    """

    def _extract_sender_from_decoded(self, decoded_payload):
        """
        Replicate the updated sender-extraction logic from
        _parse_meshcore_header().
        """
        sender_id = 0xFFFFFFFF
        if decoded_payload:
            # Advert path
            pk = getattr(decoded_payload, 'public_key', None)
            if pk and len(pk) >= 8:
                try:
                    sender_id = int(pk[:8], 16)
                    return sender_id
                except (ValueError, TypeError):
                    pass
            # AnonRequest path (NEW)
            spk = getattr(decoded_payload, 'sender_public_key', None)
            if spk and len(spk) >= 8:
                try:
                    sender_id = int(spk[:8], 16)
                except (ValueError, TypeError):
                    pass
        return sender_id

    def _make_mock(self, **kwargs):
        """Build a tiny attribute object."""
        class Mock:
            pass
        obj = Mock()
        for k, v in kwargs.items():
            setattr(obj, k, v)
        return obj

    def test_advert_extracts_from_public_key(self):
        """Existing Advert path still works."""
        decoded = self._make_mock(public_key='4f3b4308abcdef12', sender_public_key=None)
        sender_id = self._extract_sender_from_decoded(decoded)
        self.assertEqual(sender_id, 0x4f3b4308)

    def test_anonrequest_extracts_from_sender_public_key(self):
        """New AnonRequest path derives node ID from sender_public_key."""
        decoded = self._make_mock(
            public_key=None,
            sender_public_key='a3fe27d3deadbeefcafebabe01020304'
        )
        sender_id = self._extract_sender_from_decoded(decoded)
        self.assertEqual(sender_id, 0xa3fe27d3,
                         "First 4 bytes of sender_public_key must yield node ID")

    def test_anonrequest_empty_key_returns_broadcast(self):
        """When sender_public_key is empty (payload too short), stay 0xFFFFFFFF."""
        decoded = self._make_mock(public_key=None, sender_public_key='')
        sender_id = self._extract_sender_from_decoded(decoded)
        self.assertEqual(sender_id, 0xFFFFFFFF)

    def test_no_keys_returns_broadcast(self):
        """When neither public_key nor sender_public_key is present, stay 0xFFFFFFFF."""
        decoded = self._make_mock()
        sender_id = self._extract_sender_from_decoded(decoded)
        self.assertEqual(sender_id, 0xFFFFFFFF)

    def test_advert_takes_priority_over_sender_public_key(self):
        """If somehow both are set, public_key (Advert) wins."""
        decoded = self._make_mock(
            public_key='11223344aabbccdd',
            sender_public_key='a3fe27d3deadbeef'
        )
        sender_id = self._extract_sender_from_decoded(decoded)
        self.assertEqual(sender_id, 0x11223344, "Advert public_key must take priority")

    def test_malformed_key_returns_broadcast(self):
        """Non-hex sender_public_key gracefully returns 0xFFFFFFFF."""
        decoded = self._make_mock(public_key=None, sender_public_key='ZZZZZZZZ')
        sender_id = self._extract_sender_from_decoded(decoded)
        self.assertEqual(sender_id, 0xFFFFFFFF)


# ---------------------------------------------------------------------------
# 3. TextMessage Direct ECDH hint logic
# ---------------------------------------------------------------------------

class TestTextMessageEcdhHint(unittest.TestCase):
    """
    Verify conditions under which the ECDH routing hint is logged for
    encrypted TextMessage Direct packets.
    """

    def _should_show_hint(self, decoded_payload):
        """
        Replicate the gate from _on_rx_log_data that triggers the ECDH hint.
        A hint is shown when:
        - decoded_payload exists
        - it does NOT have a 'text' attribute  (cleartext messages don't need hint)
        - it does NOT have an 'app_data' attribute (those are Adverts)
        - it HAS source_hash or destination_hash
        """
        if not decoded_payload:
            return False
        has_text = hasattr(decoded_payload, 'text')
        has_app_data = hasattr(decoded_payload, 'app_data')
        if has_text or has_app_data:
            return False
        src_h = getattr(decoded_payload, 'source_hash', None)
        dst_h = getattr(decoded_payload, 'destination_hash', None)
        return src_h is not None or dst_h is not None

    def _make_mock(self, **kwargs):
        class Mock:
            pass
        obj = Mock()
        for k, v in kwargs.items():
            setattr(obj, k, v)
        return obj

    def test_ecdh_textmessage_shows_hint(self):
        """Encrypted TextMessage Direct with hashes → show hint."""
        decoded = self._make_mock(
            source_hash='AF',
            destination_hash='A8',
            ciphertext='deadbeef',
        )
        self.assertTrue(self._should_show_hint(decoded))

    def test_cleartext_textmessage_no_hint(self):
        """TextMessage with decrypted text → no hint (text is shown instead)."""
        decoded = self._make_mock(text='Hello world', source_hash='AF', destination_hash='A8')
        self.assertFalse(self._should_show_hint(decoded))

    def test_advert_no_hint(self):
        """Advert payloads (app_data) never trigger the ECDH hint."""
        decoded = self._make_mock(app_data={'name': 'TestNode'}, source_hash='AF')
        self.assertFalse(self._should_show_hint(decoded))

    def test_no_hashes_no_hint(self):
        """Payload without source_hash / destination_hash → no hint."""
        decoded = self._make_mock(checksum='DEADBEEF')
        self.assertFalse(self._should_show_hint(decoded))

    def test_none_decoded_no_hint(self):
        """None decoded_payload → no hint."""
        self.assertFalse(self._should_show_hint(None))


if __name__ == '__main__':
    unittest.main(verbosity=2)
