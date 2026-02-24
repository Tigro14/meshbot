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


# ---------------------------------------------------------------------------
# 4. _log_meshtastic_channel_config — channel/LoRa info extraction
# ---------------------------------------------------------------------------

class _FakeEnum:
    """Mimics a protobuf enum value with a .name attribute."""
    def __init__(self, name):
        self.name = name
    def __str__(self):
        return self.name


class _FakeSettings:
    def __init__(self, name='', psk=b'\x01'):
        self.name = name
        self.psk = psk


class _FakeChannel:
    def __init__(self, role_name='PRIMARY', ch_name='', psk=b'\x01'):
        self.role = _FakeEnum(role_name)
        self.settings = _FakeSettings(name=ch_name, psk=psk)


class _FakeLora:
    # Use integers for region/modem_preset — mirrors protobuf 5/6.x which returns
    # plain int for enum fields (not enum objects with .name).
    # RegionCode: EU_868=3, US=1, UNSET=0
    # ModemPreset: LONG_FAST=0, LONG_SLOW=1, MEDIUM_FAST=4
    _REGION_MAP = {'EU_868': 3, 'US': 1, 'UNSET': 0}
    _PRESET_MAP = {'LONG_FAST': 0, 'LONG_SLOW': 1, 'MEDIUM_FAST': 4}

    def __init__(self, region='EU_868', preset='LONG_FAST', hop_limit=3):
        self.region = self._REGION_MAP.get(region, 0)
        self.modem_preset = self._PRESET_MAP.get(preset, 0)
        self.hop_limit = hop_limit


class _FakeLocalConfig:
    def __init__(self, lora=None):
        self.lora = lora or _FakeLora()


class _FakeLocalNode:
    def __init__(self, channels=None, local_config=None, node_num=0x16fad3dc):
        self.channels = channels
        self.localConfig = local_config or _FakeLocalConfig()
        self.nodeNum = node_num


class _FakeMTInterface:
    def __init__(self, local_node=None, nodes=None):
        self.localNode = local_node
        self.nodes = nodes or {}


def _run_channel_config_log(interface):
    """
    Replicate the logic of _log_meshtastic_channel_config and return
    (ch_name, psk_status, region, preset, hop_limit) extracted values.
    """
    local_node = getattr(interface, 'localNode', None)
    if not local_node:
        return None

    ch_name = ''
    psk_status = 'unknown'
    channels = getattr(local_node, 'channels', None)
    if channels:
        items = (channels.values() if isinstance(channels, dict) else channels)
        primary_ch = None
        for ch in items:
            role = getattr(ch, 'role', None)
            role_name = (getattr(role, 'name', str(role))
                         if role is not None else '')
            if role_name in ('PRIMARY', '1'):
                primary_ch = ch
                break
        if primary_ch is None:
            try:
                primary_ch = (list(channels.values())[0]
                              if isinstance(channels, dict)
                              else channels[0])
            except IndexError:
                pass
        if primary_ch is not None:
            settings = getattr(primary_ch, 'settings', None)
            if settings:
                ch_name = getattr(settings, 'name', '') or ''
                psk_bytes = getattr(settings, 'psk', None)
                if psk_bytes and len(psk_bytes) > 1:
                    psk_status = 'custom'
                elif psk_bytes:
                    psk_status = 'default'
                else:
                    psk_status = 'none/unknown'

    ch_display = ch_name if ch_name else 'LongFast (default)'

    region_name = 'UNSET'
    preset_name = 'UNKNOWN'
    hop_limit = 3
    region_int = 0
    local_config = getattr(local_node, 'localConfig', None)
    if local_config:
        lora = getattr(local_config, 'lora', None)
        if lora:
            region_int = getattr(lora, 'region', 0)
            preset_int = getattr(lora, 'modem_preset', 0)
            hop_limit = getattr(lora, 'hop_limit', 3)
            try:
                from meshtastic.protobuf import config_pb2 as _cpb2
                region_name = _cpb2.Config.LoRaConfig.RegionCode.Name(region_int)
                preset_name = _cpb2.Config.LoRaConfig.ModemPreset.Name(preset_int)
            except (ValueError, ImportError, AttributeError):
                region_name = str(region_int)
                preset_name = str(preset_int)

    return ch_display, psk_status, region_name, preset_name, hop_limit, region_int


class TestMTChannelConfig(unittest.TestCase):
    """Validate _log_meshtastic_channel_config extraction logic."""

    def test_default_channel_psk(self):
        """Single-byte PSK → status 'default'."""
        ch = _FakeChannel(role_name='PRIMARY', ch_name='', psk=b'\x01')
        node = _FakeLocalNode(channels=[ch])
        iface = _FakeMTInterface(local_node=node)
        result = _run_channel_config_log(iface)
        self.assertIsNotNone(result)
        ch_display, psk_status, region, preset, hop, region_int = result
        self.assertEqual(ch_display, 'LongFast (default)')  # empty name → default display
        self.assertEqual(psk_status, 'default')

    def test_custom_channel_name_and_psk(self):
        """16-byte PSK + custom name → custom PSK, real name shown."""
        custom_psk = b'\xde\xad\xbe\xef' * 4   # 16 bytes
        ch = _FakeChannel(role_name='PRIMARY', ch_name='MyNet', psk=custom_psk)
        node = _FakeLocalNode(channels=[ch])
        iface = _FakeMTInterface(local_node=node)
        result = _run_channel_config_log(iface)
        ch_display, psk_status, _, _, _, _ = result
        self.assertEqual(ch_display, 'MyNet')
        self.assertEqual(psk_status, 'custom')

    def test_lora_region_and_preset(self):
        """LoRa region EU_868 + preset LONG_FAST are extracted correctly (via config_pb2 enum lookup)."""
        ch = _FakeChannel()
        lora = _FakeLora(region='EU_868', preset='LONG_FAST', hop_limit=5)
        node = _FakeLocalNode(channels=[ch], local_config=_FakeLocalConfig(lora=lora))
        iface = _FakeMTInterface(local_node=node)
        result = _run_channel_config_log(iface)
        _, _, region, preset, hop, region_int = result
        # _FakeLora stores EU_868=3, LONG_FAST=0 — config_pb2 should map back to names
        self.assertEqual(region, 'EU_868')
        self.assertEqual(preset, 'LONG_FAST')
        self.assertEqual(hop, 5)
        self.assertEqual(region_int, 3)  # EU_868 integer

    def test_lora_region_unset_int_zero(self):
        """region=0 (UNSET) maps to 'UNSET' via config_pb2 — was previously '0' (bug)."""
        ch = _FakeChannel()
        lora = _FakeLora(region='UNSET', preset='LONG_FAST', hop_limit=3)
        node = _FakeLocalNode(channels=[ch], local_config=_FakeLocalConfig(lora=lora))
        iface = _FakeMTInterface(local_node=node)
        result = _run_channel_config_log(iface)
        _, _, region, preset, hop, region_int = result
        self.assertEqual(region, 'UNSET')
        self.assertEqual(region_int, 0)

    def test_no_local_node_returns_none(self):
        """If localNode is None the function returns None gracefully."""
        iface = _FakeMTInterface(local_node=None)
        result = _run_channel_config_log(iface)
        self.assertIsNone(result)

    def test_channel_dict_format(self):
        """channels can be a dict keyed by index (as returned by some firmware)."""
        custom_psk = b'\xca\xfe' * 8
        ch = _FakeChannel(role_name='PRIMARY', ch_name='DictCh', psk=custom_psk)
        node = _FakeLocalNode(channels={0: ch})
        iface = _FakeMTInterface(local_node=node)
        result = _run_channel_config_log(iface)
        ch_display, psk_status, _, _, _, _ = result
        self.assertEqual(ch_display, 'DictCh')
        self.assertEqual(psk_status, 'custom')

    def test_no_psk_bytes(self):
        """PSK field is None → status 'none/unknown'."""
        ch = _FakeChannel()
        ch.settings.psk = None
        node = _FakeLocalNode(channels=[ch])
        iface = _FakeMTInterface(local_node=node)
        result = _run_channel_config_log(iface)
        _, psk_status, _, _, _, _ = result
        self.assertEqual(psk_status, 'none/unknown')

    def test_secondary_channel_uses_primary(self):
        """Only the PRIMARY channel's config is extracted, not a SECONDARY one."""
        secondary = _FakeChannel(role_name='SECONDARY', ch_name='Side', psk=b'\x02')
        primary = _FakeChannel(role_name='PRIMARY', ch_name='Main', psk=b'\x01')
        node = _FakeLocalNode(channels=[secondary, primary])
        iface = _FakeMTInterface(local_node=node)
        result = _run_channel_config_log(iface)
        ch_display, psk_status, _, _, _, _ = result
        self.assertEqual(ch_display, 'Main')


# ---------------------------------------------------------------------------
# 5. Enhanced warning: known_count distinction
# ---------------------------------------------------------------------------

class TestMTRFActivityEnhancedWarning(unittest.TestCase):
    """
    Validate the enhanced _check_meshtastic_rf_activity warning that
    distinguishes 'NEVER heard' (0 known nodes) vs 'known but silent'.
    """

    def _classify_warning(self, nodes_dict, my_id=0x16fad3dc,
                           session_age_s=400):
        """
        Replicate the warning-classification logic and return
        (recently_heard_count, known_count, warning_type)
        where warning_type is 'none', 'never_heard', or 'known_but_silent'.
        """
        now = time.time()
        window_s = 600
        recently_heard = []
        all_other_nodes = []

        for _key, node_info in nodes_dict.items():
            if not isinstance(node_info, dict):
                continue
            node_num = node_info.get('num', 0)
            if not node_num or (my_id and node_num == my_id):
                continue
            all_other_nodes.append(node_num)
            last_heard = node_info.get('lastHeard', 0)
            if last_heard and (now - last_heard) < window_s:
                user = node_info.get('user') or {}
                name = (user.get('longName') or user.get('shortName')
                        or f'0x{node_num:08x}')
                recently_heard.append((name, node_num, now - last_heard))

        uptime = session_age_s
        if recently_heard:
            return len(recently_heard), len(all_other_nodes), 'none'

        if uptime <= 300:
            return 0, len(all_other_nodes), 'none'

        known_count = len(all_other_nodes)
        if known_count == 0:
            return 0, 0, 'never_heard'
        else:
            return 0, known_count, 'known_but_silent'

    def test_never_heard_any_node(self):
        """Empty nodes dict → 'never_heard' warning (channel mismatch hint)."""
        _, known, wtype = self._classify_warning({})
        self.assertEqual(wtype, 'never_heard')
        self.assertEqual(known, 0)

    def test_only_local_node_known(self):
        """Only the bot's own node in nodes dict → 'never_heard'."""
        nodes = {
            '!16fad3dc': {
                'num': 0x16fad3dc,
                'lastHeard': int(time.time()) - 10,
                'user': {'longName': 'Meshtastic d3dc'},
            }
        }
        _, known, wtype = self._classify_warning(nodes, my_id=0x16fad3dc)
        self.assertEqual(wtype, 'never_heard')
        self.assertEqual(known, 0)   # local node excluded from count

    def test_known_nodes_not_heard_recently(self):
        """Nodes in DB but last heard >10min ago → 'known_but_silent'."""
        nodes = {
            '!aabbccdd': {
                'num': 0xaabbccdd,
                'lastHeard': int(time.time()) - 800,  # 13+ min ago
                'user': {'longName': 'SilentNode'},
            }
        }
        _, known, wtype = self._classify_warning(nodes, my_id=0x16fad3dc)
        self.assertEqual(wtype, 'known_but_silent')
        self.assertEqual(known, 1)

    def test_recently_heard_suppresses_warning(self):
        """Node heard 60s ago → no warning."""
        nodes = {
            '!aabbccdd': {
                'num': 0xaabbccdd,
                'lastHeard': int(time.time()) - 60,
                'user': {'longName': 'ActiveNode'},
            }
        }
        heard, _, wtype = self._classify_warning(nodes, my_id=0x16fad3dc)
        self.assertEqual(wtype, 'none')
        self.assertEqual(heard, 1)

    def test_short_uptime_suppresses_warning(self):
        """Uptime <5min: no warning even if no RF heard."""
        _, _, wtype = self._classify_warning({}, session_age_s=100)
        self.assertEqual(wtype, 'none')

    def test_three_known_silent_nodes(self):
        """Three nodes in DB but all silent → known_count=3, 'known_but_silent'."""
        old_ts = int(time.time()) - 900  # 15 minutes ago — outside 10-min window
        nodes = {
            '!aabbccdd': {'num': 0xaabbccdd, 'lastHeard': old_ts, 'user': {}},  # arbitrary test ID
            '!bbccddee': {'num': 0xbbccddee, 'lastHeard': old_ts, 'user': {}},  # arbitrary test ID
            '!ccddeeff': {'num': 0xccddeeff, 'lastHeard': old_ts, 'user': {}},  # arbitrary test ID
        }
        _, known, wtype = self._classify_warning(nodes)
        self.assertEqual(wtype, 'known_but_silent')
        self.assertEqual(known, 3)
# ---------------------------------------------------------------------------
# 6. _log_meshtastic_channel_config: interface.nodes count reported
# ---------------------------------------------------------------------------

class TestMTNodesCount(unittest.TestCase):
    """Validate the new interface.nodes count extraction in _log_meshtastic_channel_config."""

    def _count_nodes(self, nodes_dict, my_id=0x16fad3dc):
        """Replicate the nodes-count logic added to _log_meshtastic_channel_config."""
        total = len(nodes_dict)
        other = sum(
            1 for _k, v in nodes_dict.items()
            if isinstance(v, dict) and v.get('num', 0) != my_id
        )
        return total, other

    def test_empty_nodes(self):
        """Empty interface.nodes → 0 total, 0 other."""
        total, other = self._count_nodes({})
        self.assertEqual(total, 0)
        self.assertEqual(other, 0)

    def test_only_local_node(self):
        """Only the local node → 1 total, 0 other."""
        nodes = {'!16fad3dc': {'num': 0x16fad3dc}}
        total, other = self._count_nodes(nodes)
        self.assertEqual(total, 1)
        self.assertEqual(other, 0)

    def test_local_plus_two_remote(self):
        """Local + 2 remote → 3 total, 2 other."""
        nodes = {
            '!16fad3dc': {'num': 0x16fad3dc},
            '!a3fe27d3': {'num': 0xa3fe27d3},
            '!82cae656': {'num': 0x82cae656},
        }
        total, other = self._count_nodes(nodes)
        self.assertEqual(total, 3)
        self.assertEqual(other, 2)

    def test_non_dict_entry_ignored(self):
        """Non-dict entries in nodes are skipped for the 'other' count."""
        nodes = {
            '!16fad3dc': {'num': 0x16fad3dc},
            '!xxxxxxxx': 'not-a-dict',   # malformed entry — should be skipped
            '!a3fe27d3': {'num': 0xa3fe27d3},
        }
        total, other = self._count_nodes(nodes)
        self.assertEqual(total, 3)  # total counts all keys
        self.assertEqual(other, 1)  # only the valid remote dict is counted


# ---------------------------------------------------------------------------
# 7. on_message: encrypted TEXT_MESSAGE_APP must produce a debug log not a
#    silent return
# ---------------------------------------------------------------------------

class TestOnMessageEncryptedDropLog(unittest.TestCase):
    """
    Validate that the encrypted TEXT_MESSAGE_APP fix emits a debug log
    rather than silently returning.
    """

    def _simulate_encrypted_text_handling(self, payload):
        """
        Replicate the fixed on_message TEXT_MESSAGE_APP logic and return
        (message_or_none, logged_msg) where logged_msg contains the
        debug string that would have been emitted.
        """
        logged = []
        message = None
        try:
            message = payload.decode('utf-8').strip()
        except Exception:
            logged.append(
                f"🔐 [MT] Encrypted TEXT_MESSAGE_APP from 0x12345678"
                f" ({len(payload)}B) — cannot decode, skipping command processing"
            )
            return None, logged
        return message, logged

    def test_plaintext_no_log(self):
        """Plain UTF-8 payload → decoded normally, no encryption log."""
        msg, logs = self._simulate_encrypted_text_handling(b'/help')
        self.assertEqual(msg, '/help')
        self.assertEqual(logs, [])

    def test_binary_encrypted_payload_logs(self):
        """Binary (non-UTF-8) payload → None returned, log emitted."""
        binary = b'\x00\xff\xfe\xab\xcd\xef'
        msg, logs = self._simulate_encrypted_text_handling(binary)
        self.assertIsNone(msg)
        self.assertEqual(len(logs), 1)
        self.assertIn('🔐 [MT] Encrypted TEXT_MESSAGE_APP', logs[0])
        self.assertIn('6B', logs[0])
        self.assertIn('cannot decode', logs[0])

    def test_empty_bytes_decodes_successfully(self):
        """Empty bytes decode as empty string (no exception, no log emitted).

        Empty bytes are valid UTF-8 and decode to ''; the downstream
        ``if not message: return`` check handles the empty-string case.
        This test verifies the exception path is NOT taken for empty bytes.
        """
        msg, logs = self._simulate_encrypted_text_handling(b'')
        # empty bytes decode fine as UTF-8 to ''
        self.assertEqual(msg, '')
        self.assertEqual(logs, [])

    def test_partial_utf8_logs(self):
        """Partial/invalid UTF-8 sequence → log emitted."""
        invalid_utf8 = b'\xff\xfe\x00\x01'
        msg, logs = self._simulate_encrypted_text_handling(invalid_utf8)
        self.assertIsNone(msg)
        self.assertIn('cannot decode', logs[0])


# ---------------------------------------------------------------------------
# 8. DualInterfaceManager: Packet #N log now includes portnum + from_id
# ---------------------------------------------------------------------------

class TestDualManagerPacketLog(unittest.TestCase):
    """Verify the enhanced Packet #N received log format."""

    def _build_log_line(self, packet, count):
        """Replicate the new log format in on_meshtastic_message."""
        _portnum = (packet.get('decoded', {}).get('portnum', 'UNKNOWN')
                    if packet else 'NONE')
        _from_id = packet.get('from', 0) if packet else 0
        return (
            f"📡 [MESHTASTIC] Packet #{count} received:"
            f" {_portnum} from 0x{_from_id:08x}"
        )

    def test_telemetry_local(self):
        pkt = {'from': 0x16fad3dc, 'decoded': {'portnum': 'TELEMETRY_APP'}}
        line = self._build_log_line(pkt, 5)
        self.assertIn('TELEMETRY_APP', line)
        self.assertIn('0x16fad3dc', line)
        self.assertIn('Packet #5', line)

    def test_text_from_other_node(self):
        pkt = {'from': 0xa3fe27d3, 'decoded': {'portnum': 'TEXT_MESSAGE_APP'}}
        line = self._build_log_line(pkt, 12)
        self.assertIn('TEXT_MESSAGE_APP', line)
        self.assertIn('0xa3fe27d3', line)
        self.assertIn('Packet #12', line)

    def test_none_packet(self):
        """None packet → NONE portnum, 0x00000000 from_id."""
        line = self._build_log_line(None, 1)
        self.assertIn('NONE', line)
        self.assertIn('0x00000000', line)

    def test_missing_decoded(self):
        """Packet with no 'decoded' key → UNKNOWN portnum."""
        pkt = {'from': 0xdeadbeef}
        line = self._build_log_line(pkt, 3)
        self.assertIn('UNKNOWN', line)
        self.assertIn('0xdeadbeef', line)


# ---------------------------------------------------------------------------
# 9. _check_meshtastic_rf_activity: enhanced cause message for NEVER heard
# ---------------------------------------------------------------------------

class TestMTRFActivityCauseMessage(unittest.TestCase):
    """Validate the updated cause hint mentions antenna check."""

    def _get_cause_string(self, known_count):
        if known_count == 0:
            return (
                "NEVER heard any RF peer → check antenna, channel PSK,"
                " LoRa region/preset, and that other nodes are nearby"
            )
        return (
            f"{known_count} node(s) known from DB but none"
            " heard recently → coverage gap or nodes went silent"
        )

    def test_never_heard_mentions_antenna(self):
        cause = self._get_cause_string(0)
        self.assertIn('antenna', cause)
        self.assertIn('PSK', cause)
        self.assertIn('region', cause)

    def test_known_but_silent_mentions_coverage(self):
        cause = self._get_cause_string(3)
        self.assertIn('coverage gap', cause)
        self.assertIn('3', cause)


# ---------------------------------------------------------------------------
# 10. _check_meshtastic_rf_activity: empty nodes dict must NOT cause early exit
# ---------------------------------------------------------------------------

class TestMTRFActivityEmptyNodesDict(unittest.TestCase):
    """
    Bug fix: the old guard ``not mt_interface.nodes`` returned silently when
    the radio had never heard any RF peer (nodes = {}).  The warning must now
    fire even with an empty nodes dict.
    """

    def _run_check_with_nodes(self, nodes_dict, session_age_s=400):
        """
        Replicate the post-fix logic of _check_meshtastic_rf_activity.
        Returns (warning_type, known_count) where warning_type is
        'none', 'never_heard', or 'known_but_silent'.
        """
        # Simulate the fixed early-return: only bail when nodes attr missing
        if nodes_dict is None:
            return 'no_attr', 0

        # nodes can be empty {} — that is valid, continue processing
        nodes = nodes_dict or {}

        my_id = 0x16fad3dc
        now = time.time()
        window_s = 600
        recently_heard = []
        all_other_nodes = []

        for _key, node_info in nodes.items():
            if not isinstance(node_info, dict):
                continue
            node_num = node_info.get('num', 0)
            if not node_num or node_num == my_id:
                continue
            all_other_nodes.append(node_num)
            last_heard = node_info.get('lastHeard', 0)
            if last_heard and (now - last_heard) < window_s:
                recently_heard.append(node_num)

        if recently_heard:
            return 'none', len(all_other_nodes)

        uptime = session_age_s
        if uptime <= 300:
            return 'none', len(all_other_nodes)

        known_count = len(all_other_nodes)
        if known_count == 0:
            return 'never_heard', 0
        return 'known_but_silent', known_count

    def test_empty_nodes_warns_never_heard(self):
        """Empty {} nodes dict → 'never_heard' (bug fix: was silently returning)."""
        wtype, known = self._run_check_with_nodes({})
        self.assertEqual(wtype, 'never_heard')
        self.assertEqual(known, 0)

    def test_none_nodes_treated_as_no_attr(self):
        """None (missing attribute) → early return, no warning spam."""
        wtype, _ = self._run_check_with_nodes(None)
        self.assertEqual(wtype, 'no_attr')

    def test_only_local_node_warns_never_heard(self):
        """Only the bot's own entry in nodes (no RF peer) → 'never_heard'."""
        nodes = {'!16fad3dc': {'num': 0x16fad3dc, 'lastHeard': int(time.time()) - 30}}
        wtype, known = self._run_check_with_nodes(nodes)
        self.assertEqual(wtype, 'never_heard')
        self.assertEqual(known, 0)

    def test_stale_remote_node_warns_known_but_silent(self):
        """Remote node in DB but heard >10min ago → 'known_but_silent'."""
        nodes = {
            '!a3fe27d3': {'num': 0xa3fe27d3, 'lastHeard': int(time.time()) - 700}
        }
        wtype, known = self._run_check_with_nodes(nodes)
        self.assertEqual(wtype, 'known_but_silent')
        self.assertEqual(known, 1)

    def test_recent_remote_node_no_warning(self):
        """Remote node heard 90s ago → no warning."""
        nodes = {
            '!a3fe27d3': {'num': 0xa3fe27d3, 'lastHeard': int(time.time()) - 90}
        }
        wtype, _ = self._run_check_with_nodes(nodes)
        self.assertEqual(wtype, 'none')


# ---------------------------------------------------------------------------
# 11. Subscription health check: re-subscribe logic
# ---------------------------------------------------------------------------

class TestMeshtasticSubscriptionHealthCheck(unittest.TestCase):
    """
    Validate the subscription health-check logic added to
    _check_meshtastic_rf_activity: detects a dead subscription and
    re-subscribes automatically.
    """

    def _simulate_health_check(self, is_subscribed, is_dual_mode,
                               has_listener=True):
        """
        Replicate the subscription health-check logic.
        Returns (resubscribed, log_messages) where resubscribed is True if
        a re-subscription was attempted.
        """
        logs = []
        resubscribed = False

        # Simulate pub.isSubscribed result
        def fake_is_subscribed(listener, topic):
            return is_subscribed

        def fake_subscribe(listener, topic):
            nonlocal resubscribed
            resubscribed = True
            logs.append(f"✅ [MT-SUB] Re-subscribed to {topic}")

        listener = object() if has_listener else None

        if is_dual_mode:
            if listener is not None and not fake_is_subscribed(listener, 'meshtastic.receive'):
                logs.append("⚠️  [MT-SUB] Subscription silently dropped — re-subscribing...")
                fake_subscribe(listener, 'meshtastic.receive')
        else:
            on_message = object()  # stand-in for self.on_message
            if not fake_is_subscribed(on_message, 'meshtastic.receive'):
                logs.append("⚠️  [MT-SUB] Subscription silently dropped — re-subscribing...")
                fake_subscribe(on_message, 'meshtastic.receive')

        return resubscribed, logs

    def test_alive_subscription_no_action(self):
        """Subscription alive → no re-subscribe, no warning log."""
        resubscribed, logs = self._simulate_health_check(
            is_subscribed=True, is_dual_mode=False
        )
        self.assertFalse(resubscribed)
        self.assertEqual(logs, [])

    def test_dead_subscription_single_mode_resubscribes(self):
        """Dead subscription in single mode → re-subscribe attempt + warning."""
        resubscribed, logs = self._simulate_health_check(
            is_subscribed=False, is_dual_mode=False
        )
        self.assertTrue(resubscribed)
        self.assertTrue(any('⚠️' in m for m in logs))
        self.assertTrue(any('Re-subscribed' in m for m in logs))

    def test_dead_subscription_dual_mode_with_listener_resubscribes(self):
        """Dead subscription in dual mode (listener present) → re-subscribe."""
        resubscribed, logs = self._simulate_health_check(
            is_subscribed=False, is_dual_mode=True, has_listener=True
        )
        self.assertTrue(resubscribed)

    def test_dead_subscription_dual_mode_no_listener_no_crash(self):
        """Dead subscription in dual mode but listener is None → no crash, no re-subscribe."""
        resubscribed, logs = self._simulate_health_check(
            is_subscribed=False, is_dual_mode=True, has_listener=False
        )
        self.assertFalse(resubscribed)

    def test_alive_subscription_dual_mode_no_action(self):
        """Alive subscription in dual mode → no action."""
        resubscribed, logs = self._simulate_health_check(
            is_subscribed=True, is_dual_mode=True, has_listener=True
        )
        self.assertFalse(resubscribed)
        self.assertEqual(logs, [])


# ---------------------------------------------------------------------------
# 9. numTotalNodes extraction from local TELEMETRY_APP
# ---------------------------------------------------------------------------

class TestNumTotalNodesExtraction(unittest.TestCase):
    """
    Validate the numTotalNodes extraction logic added to
    node_manager.update_rx_history() and the enhanced RF activity warning.
    """

    def _extract_hw_num_total_nodes(self, packet, source='meshtastic', snr=0.0):
        """
        Replicate the extraction logic added to update_rx_history():
        When snr=0.0 AND source is meshtastic/local AND portnum=TELEMETRY_APP,
        pull numTotalNodes from decoded.telemetry.localStats and return it.
        Returns None if conditions are not met or field is absent.
        """
        if snr != 0.0 or source not in ('meshtastic', 'local'):
            return None
        portnum_check = packet.get('decoded', {}).get('portnum', '')
        if portnum_check != 'TELEMETRY_APP':
            return None
        telemetry = packet.get('decoded', {}).get('telemetry', {})
        local_stats = telemetry.get('localStats', {})
        return local_stats.get('numTotalNodes')

    def _build_local_telemetry_packet(self, num_total_nodes):
        """Build a minimal local-node TELEMETRY_APP packet with localStats."""
        return {
            'from': 0x16fad3dc,
            'to': 0xffffffff,
            'decoded': {
                'portnum': 'TELEMETRY_APP',
                'telemetry': {
                    'time': 79280,
                    'localStats': {
                        'uptimeSeconds': 79280,
                        'numTotalNodes': num_total_nodes,
                        'heapTotalBytes': 156724,
                        'heapFreeBytes': 85936,
                    },
                },
            },
        }

    def test_num_total_nodes_extracted_when_1(self):
        """Local TELEMETRY_APP with numTotalNodes=1 → extracted correctly."""
        pkt = self._build_local_telemetry_packet(1)
        result = self._extract_hw_num_total_nodes(pkt)
        self.assertEqual(result, 1)

    def test_num_total_nodes_extracted_when_5(self):
        """Local TELEMETRY_APP with numTotalNodes=5 → extracted correctly."""
        pkt = self._build_local_telemetry_packet(5)
        result = self._extract_hw_num_total_nodes(pkt)
        self.assertEqual(result, 5)

    def test_not_extracted_when_rf_packet(self):
        """snr != 0.0 (RF packet from another node) → not extracted."""
        pkt = self._build_local_telemetry_packet(3)
        result = self._extract_hw_num_total_nodes(pkt, snr=12.5)
        self.assertIsNone(result)

    def test_not_extracted_for_meshcore_source(self):
        """MeshCore-source packet → not extracted (only meshtastic/local)."""
        pkt = self._build_local_telemetry_packet(2)
        result = self._extract_hw_num_total_nodes(pkt, source='meshcore')
        self.assertIsNone(result)

    def test_not_extracted_when_no_local_stats(self):
        """TELEMETRY_APP without localStats (e.g. deviceMetrics only) → None."""
        pkt = {
            'from': 0x16fad3dc,
            'decoded': {
                'portnum': 'TELEMETRY_APP',
                'telemetry': {'time': 100, 'deviceMetrics': {'batteryLevel': 78}},
            },
        }
        result = self._extract_hw_num_total_nodes(pkt)
        self.assertIsNone(result)

    def test_not_extracted_for_wrong_portnum(self):
        """Non-TELEMETRY_APP packet → not extracted."""
        pkt = {
            'from': 0x16fad3dc,
            'decoded': {'portnum': 'NODEINFO_APP', 'telemetry': {'localStats': {'numTotalNodes': 5}}},
        }
        result = self._extract_hw_num_total_nodes(pkt)
        self.assertIsNone(result)

    # --- enhanced warning with hw_nodes ---

    def _classify_warning_with_hw(self, nodes, hw_nodes=None, session_age_s=600, my_id=0x16fad3dc):
        """
        Replicate the _check_meshtastic_rf_activity warning logic with the
        hw_nodes (numTotalNodes) addition.  Returns a dict describing the warning.
        """
        now = time.time()
        window_s = 600
        recently_heard = []
        all_other_nodes = []
        for _key, node_info in nodes.items():
            if not isinstance(node_info, dict):
                continue
            node_num = node_info.get('num', 0)
            if not node_num or node_num == my_id:
                continue
            all_other_nodes.append(node_num)
            last_heard = node_info.get('lastHeard', 0)
            if last_heard and (now - last_heard) < window_s:
                recently_heard.append(node_num)

        if recently_heard:
            return {'type': 'none', 'hw_nodes': hw_nodes}

        if session_age_s < 300:
            return {'type': 'none', 'hw_nodes': hw_nodes}

        known_count = len(all_other_nodes)
        hw_suffix = f" | hw_nodes={hw_nodes}" if hw_nodes is not None else ""
        hw_alarm = (hw_nodes is not None and hw_nodes <= 1)
        return {
            'type': 'never' if known_count == 0 else 'known_but_silent',
            'known': known_count,
            'hw_suffix': hw_suffix,
            'hw_alarm': hw_alarm,
            'hw_nodes': hw_nodes,
        }

    def test_hw_suffix_included_when_hw_nodes_known(self):
        """hw_nodes known → hw_suffix is non-empty."""
        result = self._classify_warning_with_hw({}, hw_nodes=1)
        self.assertIn('hw_nodes=1', result['hw_suffix'])

    def test_hw_suffix_absent_when_hw_nodes_unknown(self):
        """hw_nodes=None → hw_suffix is empty string."""
        result = self._classify_warning_with_hw({}, hw_nodes=None)
        self.assertEqual(result['hw_suffix'], '')

    def test_hw_alarm_fires_when_hw_nodes_1(self):
        """hw_nodes=1 → hw_alarm True (radio confirms no RF peers seen)."""
        result = self._classify_warning_with_hw({}, hw_nodes=1)
        self.assertTrue(result['hw_alarm'])

    def test_hw_alarm_fires_when_hw_nodes_0(self):
        """hw_nodes=0 → hw_alarm True (edge case: firmware might report 0)."""
        result = self._classify_warning_with_hw({}, hw_nodes=0)
        self.assertTrue(result['hw_alarm'])

    def test_hw_alarm_does_not_fire_when_hw_nodes_5(self):
        """hw_nodes=5 → hw_alarm False (radio has heard other nodes)."""
        result = self._classify_warning_with_hw({}, hw_nodes=5)
        self.assertFalse(result['hw_alarm'])

    def test_hw_alarm_absent_when_hw_nodes_unknown(self):
        """hw_nodes=None → hw_alarm False (no data)."""
        result = self._classify_warning_with_hw({}, hw_nodes=None)
        self.assertFalse(result['hw_alarm'])

    def test_warning_type_never_when_no_nodes_at_all(self):
        """No nodes in DB and hw_nodes=1 → warning type 'never'."""
        result = self._classify_warning_with_hw({}, hw_nodes=1)
        self.assertEqual(result['type'], 'never')
        self.assertTrue(result['hw_alarm'])


# ---------------------------------------------------------------------------
# 14. lastHeard scan in _log_meshtastic_channel_config
# ---------------------------------------------------------------------------

class TestLastHeardScan(unittest.TestCase):
    """Validate the lastHeard scan logic added to _log_meshtastic_channel_config."""

    def _run_last_heard_scan(self, nodes, my_id=0x16fad3dc, now=None):
        """
        Replicate the lastHeard scan logic from _log_meshtastic_channel_config.
        Returns dict with: last_heard_name, last_heard_ago_s, recent_24h_count,
        label ('recent'|'stale'|'never'|'no_entries').
        """
        now = now or time.time()
        last_heard_entries = []
        for _k, _v in nodes.items():
            if not isinstance(_v, dict):
                continue
            _nid = _v.get('num', 0)
            if not _nid or _nid == my_id:
                continue
            _lh = _v.get('lastHeard', 0)
            if _lh and _lh > 0:
                _user = _v.get('user') or {}
                _name = (_user.get('longName') or _user.get('shortName')
                         or f'0x{_nid:08x}')
                last_heard_entries.append((_lh, _nid, _name))

        if not last_heard_entries:
            return {'label': 'no_entries', 'recent_24h_count': 0}

        last_heard_entries.sort(reverse=True)
        _lh_ts, _lh_id, _lh_name = last_heard_entries[0]
        _ago = now - _lh_ts
        _recent_24h = sum(1 for (_t, _i, _n) in last_heard_entries
                          if (now - _t) < 86400)
        if _recent_24h:
            label = 'recent'
        else:
            label = 'stale'
        return {
            'label': label,
            'last_name': _lh_name,
            'last_ago_s': _ago,
            'recent_24h_count': _recent_24h,
        }

    def test_empty_nodes_no_entries(self):
        """No non-local nodes → label 'no_entries'."""
        result = self._run_last_heard_scan({})
        self.assertEqual(result['label'], 'no_entries')

    def test_local_only_no_entries(self):
        """Only local node in nodeDB → no entries (local is excluded)."""
        nodes = {'!16fad3dc': {'num': 0x16fad3dc, 'lastHeard': int(time.time())}}
        result = self._run_last_heard_scan(nodes)
        self.assertEqual(result['label'], 'no_entries')

    def test_recent_node_reported(self):
        """Node heard 5 minutes ago → label 'recent', recent_24h_count=1."""
        now = time.time()
        nodes = {
            '!a3fe27d3': {
                'num': 0xa3fe27d3,
                'lastHeard': int(now) - 300,  # 5 min ago
                'user': {'longName': 'TestNode'},
            }
        }
        result = self._run_last_heard_scan(nodes, now=now)
        self.assertEqual(result['label'], 'recent')
        self.assertEqual(result['recent_24h_count'], 1)
        self.assertEqual(result['last_name'], 'TestNode')
        self.assertAlmostEqual(result['last_ago_s'], 300, delta=2)

    def test_stale_node_two_days_ago(self):
        """Node heard 2 days ago → label 'stale', recent_24h_count=0."""
        now = time.time()
        nodes = {
            '!a3fe27d3': {
                'num': 0xa3fe27d3,
                'lastHeard': int(now) - 2 * 86400,
                'user': {'longName': 'StaleNode'},
            }
        }
        result = self._run_last_heard_scan(nodes, now=now)
        self.assertEqual(result['label'], 'stale')
        self.assertEqual(result['recent_24h_count'], 0)
        self.assertAlmostEqual(result['last_ago_s'], 2 * 86400, delta=2)

    def test_mixed_nodes_picks_most_recent(self):
        """With both fresh and stale nodes, most recent is selected."""
        now = time.time()
        nodes = {
            '!aaaa0001': {'num': 0xaaaa0001, 'lastHeard': int(now) - 3600,
                          'user': {'longName': 'NodeA'}},
            '!bbbb0002': {'num': 0xbbbb0002, 'lastHeard': int(now) - 300,
                          'user': {'longName': 'NodeB'}},   # most recent
            '!cccc0003': {'num': 0xcccc0003, 'lastHeard': int(now) - 7200,
                          'user': {'longName': 'NodeC'}},
        }
        result = self._run_last_heard_scan(nodes, now=now)
        self.assertEqual(result['last_name'], 'NodeB')
        self.assertEqual(result['recent_24h_count'], 3)

    def test_node_with_zero_last_heard_excluded(self):
        """lastHeard=0 means never heard via RF — excluded from entries."""
        nodes = {
            '!a3fe27d3': {'num': 0xa3fe27d3, 'lastHeard': 0, 'user': {}},
        }
        result = self._run_last_heard_scan(nodes)
        self.assertEqual(result['label'], 'no_entries')

    def test_fallback_name_from_short_name(self):
        """Node with only shortName → shortName used in output."""
        now = time.time()
        nodes = {
            '!a3fe27d3': {
                'num': 0xa3fe27d3,
                'lastHeard': int(now) - 60,
                'user': {'shortName': 'TN'},
            }
        }
        result = self._run_last_heard_scan(nodes, now=now)
        self.assertEqual(result['last_name'], 'TN')

    def test_fallback_name_from_node_id(self):
        """Node with no user info → hex ID used as name."""
        now = time.time()
        nodes = {
            '!a3fe27d3': {'num': 0xa3fe27d3, 'lastHeard': int(now) - 60}
        }
        result = self._run_last_heard_scan(nodes, now=now)
        self.assertIn('0xa3fe27d3', result['last_name'])


# ---------------------------------------------------------------------------
# 15. numTotalNodes from deviceMetrics fallback in update_rx_history
# ---------------------------------------------------------------------------

class TestNumTotalNodesDeviceMetricsFallback(unittest.TestCase):
    """
    Validate the new fallback logic in node_manager.update_rx_history:
    numTotalNodes is tried first from localStats, then from deviceMetrics.
    """

    def _extract_hw_num_total_nodes(self, packet):
        """
        Replicate the extraction logic from update_rx_history for
        TELEMETRY_APP packets from a local source (snr=0.0).
        Returns the extracted numTotalNodes value or None.
        """
        snr = packet.get('snr', 0.0)
        if snr != 0.0:
            return None
        decoded = packet.get('decoded', {})
        if decoded.get('portnum') != 'TELEMETRY_APP':
            return None
        telemetry = decoded.get('telemetry', {})
        for sub_key in ('localStats', 'deviceMetrics'):
            sub = telemetry.get(sub_key, {})
            num = sub.get('numTotalNodes')
            if num is not None:
                return num
        return None

    def test_local_stats_preferred(self):
        """localStats.numTotalNodes is returned when present."""
        pkt = {
            'snr': 0.0,
            'decoded': {
                'portnum': 'TELEMETRY_APP',
                'telemetry': {'localStats': {'numTotalNodes': 5}},
            }
        }
        self.assertEqual(self._extract_hw_num_total_nodes(pkt), 5)

    def test_device_metrics_fallback(self):
        """deviceMetrics.numTotalNodes used when localStats absent."""
        pkt = {
            'snr': 0.0,
            'decoded': {
                'portnum': 'TELEMETRY_APP',
                'telemetry': {'deviceMetrics': {'numTotalNodes': 3}},
            }
        }
        self.assertEqual(self._extract_hw_num_total_nodes(pkt), 3)

    def test_local_stats_takes_priority_over_device_metrics(self):
        """When both present, localStats wins."""
        pkt = {
            'snr': 0.0,
            'decoded': {
                'portnum': 'TELEMETRY_APP',
                'telemetry': {
                    'localStats': {'numTotalNodes': 7},
                    'deviceMetrics': {'numTotalNodes': 2},
                },
            }
        }
        self.assertEqual(self._extract_hw_num_total_nodes(pkt), 7)

    def test_rf_packet_not_extracted(self):
        """Non-local packet (snr != 0.0) → returns None."""
        pkt = {
            'snr': 12.5,
            'decoded': {
                'portnum': 'TELEMETRY_APP',
                'telemetry': {'localStats': {'numTotalNodes': 1}},
            }
        }
        self.assertIsNone(self._extract_hw_num_total_nodes(pkt))

    def test_non_telemetry_portnum_not_extracted(self):
        """Non-TELEMETRY_APP portnum → returns None."""
        pkt = {
            'snr': 0.0,
            'decoded': {
                'portnum': 'TEXT_MESSAGE_APP',
                'telemetry': {'localStats': {'numTotalNodes': 1}},
            }
        }
        self.assertIsNone(self._extract_hw_num_total_nodes(pkt))

    def test_no_num_total_nodes_returns_none(self):
        """TELEMETRY_APP with telemetry that has no numTotalNodes → None."""
        pkt = {
            'snr': 0.0,
            'decoded': {
                'portnum': 'TELEMETRY_APP',
                'telemetry': {'localStats': {'uptimeSeconds': 3600}},
            }
        }
        self.assertIsNone(self._extract_hw_num_total_nodes(pkt))

    def test_empty_telemetry_returns_none(self):
        """Empty telemetry dict → None."""
        pkt = {
            'snr': 0.0,
            'decoded': {'portnum': 'TELEMETRY_APP', 'telemetry': {}}
        }
        self.assertIsNone(self._extract_hw_num_total_nodes(pkt))

    def test_hw_nodes_1_is_correctly_extracted(self):
        """numTotalNodes=1 (only self heard) is extracted correctly."""
        pkt = {
            'snr': 0.0,
            'decoded': {
                'portnum': 'TELEMETRY_APP',
                'telemetry': {'localStats': {'numTotalNodes': 1}},
            }
        }
        self.assertEqual(self._extract_hw_num_total_nodes(pkt), 1)


# ---------------------------------------------------------------------------
# 16. LoRa region/preset enum name lookup via config_pb2 (not .name attribute)
# ---------------------------------------------------------------------------

class TestLoRaRegionPresetEnumLookup(unittest.TestCase):
    """
    Validate that the production code uses config_pb2.Name() to resolve LoRa
    enum integers to human-readable names (EU_868, LONG_FAST, UNSET…) instead
    of relying on a .name attribute that doesn't exist on plain Python ints.
    """

    def _resolve(self, region_int, preset_int):
        """Run the same resolution logic as _log_meshtastic_channel_config."""
        try:
            from meshtastic.protobuf import config_pb2 as _cpb2
            region_name = _cpb2.Config.LoRaConfig.RegionCode.Name(region_int)
            preset_name = _cpb2.Config.LoRaConfig.ModemPreset.Name(preset_int)
        except (ValueError, ImportError, AttributeError):
            region_name = str(region_int)
            preset_name = str(preset_int)
        return region_name, preset_name

    def test_eu868_resolves_to_name(self):
        """region=3 → EU_868 (not '3')."""
        region, preset = self._resolve(3, 0)
        self.assertEqual(region, 'EU_868')
        self.assertEqual(preset, 'LONG_FAST')

    def test_unset_region_zero_resolves_to_unset(self):
        """region=0 → 'UNSET' (not '0'). Previously was shown as '0' — was a bug."""
        region, preset = self._resolve(0, 0)
        self.assertEqual(region, 'UNSET')

    def test_us_region_resolves(self):
        """region=1 → US."""
        region, _ = self._resolve(1, 0)
        self.assertEqual(region, 'US')

    def test_long_slow_preset_resolves(self):
        """preset=1 → LONG_SLOW."""
        _, preset = self._resolve(3, 1)
        self.assertEqual(preset, 'LONG_SLOW')

    def test_fake_lora_eu868_roundtrip(self):
        """_FakeLora('EU_868') stores int 3, _run_channel_config_log returns 'EU_868'."""
        ch = _FakeChannel()
        lora = _FakeLora(region='EU_868', preset='LONG_FAST', hop_limit=3)
        node = _FakeLocalNode(channels=[ch], local_config=_FakeLocalConfig(lora=lora))
        iface = _FakeMTInterface(local_node=node)
        result = _run_channel_config_log(iface)
        _, _, region, preset, hop, region_int = result
        self.assertEqual(region, 'EU_868')
        self.assertEqual(preset, 'LONG_FAST')
        self.assertEqual(region_int, 3)

    def test_fake_lora_unset_roundtrip(self):
        """_FakeLora('UNSET') stores int 0, _run_channel_config_log returns 'UNSET'."""
        ch = _FakeChannel()
        lora = _FakeLora(region='UNSET', preset='LONG_FAST')
        node = _FakeLocalNode(channels=[ch], local_config=_FakeLocalConfig(lora=lora))
        iface = _FakeMTInterface(local_node=node)
        result = _run_channel_config_log(iface)
        _, _, region, _, _, region_int = result
        self.assertEqual(region, 'UNSET')
        self.assertEqual(region_int, 0)


# ---------------------------------------------------------------------------
# 17. lastHeard diagnostic excludes bot-injected nodes (no lastHeard field)
# ---------------------------------------------------------------------------

class TestLastHeardExcludesBotInjectedNodes(unittest.TestCase):
    """
    Validate that the lastHeard scan correctly distinguishes between:
    - Nodes actually heard by the radio firmware (have lastHeard > 0)
    - Nodes injected by sync_pubkeys_to_interface (no lastHeard, or lastHeard=0)
    The diagnostic should report 'fw_heard' count and 'injected_count' separately.
    """

    def _run_lastheard_scan(self, nodes, my_id=0x16fad3dc):
        """
        Replicate the updated lastHeard scan from _log_meshtastic_channel_config.
        Returns (fw_heard, injected_count, last_heard_entries).
        """
        last_heard_entries = []
        injected_count = 0
        for _k, _v in nodes.items():
            if not isinstance(_v, dict):
                continue
            _nid = _v.get('num', 0)
            if not _nid or _nid == my_id:
                continue
            _lh = _v.get('lastHeard', 0)
            if _lh and _lh > 0:
                _user = _v.get('user') or {}
                _name = (_user.get('longName') or _user.get('shortName')
                         or f'0x{_nid:08x}')
                last_heard_entries.append((_lh, _nid, _name))
            else:
                injected_count += 1
        return len(last_heard_entries), injected_count, last_heard_entries

    def test_all_bot_injected_no_lastheard(self):
        """190 injected nodes (no lastHeard) → fw_heard=0, injected_count=190."""
        nodes = {}
        for i in range(1, 191):
            nodes[f'!{i:08x}'] = {
                'num': i,
                'user': {'longName': f'Node-{i}', 'publicKey': b'\xab' * 16}
                # no 'lastHeard' — injected by sync_pubkeys_to_interface
            }
        fw_heard, injected_count, entries = self._run_lastheard_scan(nodes)
        self.assertEqual(fw_heard, 0)
        self.assertEqual(injected_count, 190)
        self.assertEqual(entries, [])

    def test_mix_of_heard_and_injected(self):
        """3 heard + 5 injected → fw_heard=3, injected_count=5."""
        now = int(time.time())
        nodes = {}
        for i in range(1, 4):  # 3 actually heard
            nodes[f'!aaaa{i:04x}'] = {
                'num': 0xaaaa0000 + i,
                'lastHeard': now - i * 100,
                'user': {'longName': f'RF-Node-{i}'},
            }
        for i in range(1, 6):  # 5 injected (no lastHeard)
            nodes[f'!bbbb{i:04x}'] = {
                'num': 0xbbbb0000 + i,
                'user': {'longName': f'Injected-{i}', 'publicKey': b'\xcd' * 16}
            }
        fw_heard, injected_count, entries = self._run_lastheard_scan(nodes)
        self.assertEqual(fw_heard, 3)
        self.assertEqual(injected_count, 5)
        self.assertEqual(len(entries), 3)

    def test_only_really_heard_nodes(self):
        """All nodes have lastHeard → injected_count=0."""
        now = int(time.time())
        nodes = {
            '!a1000001': {'num': 0xa1000001, 'lastHeard': now - 60,
                          'user': {'longName': 'Peer1'}},
            '!a1000002': {'num': 0xa1000002, 'lastHeard': now - 120,
                          'user': {'longName': 'Peer2'}},
        }
        fw_heard, injected_count, entries = self._run_lastheard_scan(nodes)
        self.assertEqual(fw_heard, 2)
        self.assertEqual(injected_count, 0)

    def test_lastheard_zero_counts_as_injected(self):
        """lastHeard=0 (explicitly set) is treated the same as missing → injected."""
        nodes = {
            '!a1000001': {'num': 0xa1000001, 'lastHeard': 0,
                          'user': {'longName': 'ZeroHeard'}},
        }
        fw_heard, injected_count, _ = self._run_lastheard_scan(nodes)
        self.assertEqual(fw_heard, 0)
        self.assertEqual(injected_count, 1)

    def test_known_count_in_rf_activity_check_excludes_injected(self):
        """
        _check_meshtastic_rf_activity known_count is now based on lastHeard>0 nodes
        only — bot-injected entries (no lastHeard) must not inflate known_count.
        """
        # Replicate the updated all_other_nodes loop from _check_meshtastic_rf_activity
        now = time.time()
        window_s = 600
        my_id = 0x16fad3dc
        recently_heard = []
        all_other_nodes = []

        nodes = {}
        # 5 bot-injected nodes (no lastHeard)
        for i in range(1, 6):
            nodes[f'!{i:08x}'] = {'num': i, 'user': {'publicKey': b'\xab'}}
        # 2 genuinely heard nodes (outside 10-min window so not "recently heard")
        nodes['!a0000001'] = {'num': 0xa0000001,
                               'lastHeard': int(now) - 86400,
                               'user': {'longName': 'OldPeer1'}}
        nodes['!a0000002'] = {'num': 0xa0000002,
                               'lastHeard': int(now) - 7200,
                               'user': {'longName': 'OldPeer2'}}

        for _key, node_info in nodes.items():
            if not isinstance(node_info, dict):
                continue
            node_num = node_info.get('num', 0)
            if not node_num or node_num == my_id:
                continue
            last_heard = node_info.get('lastHeard', 0)
            if last_heard and last_heard > 0:
                all_other_nodes.append(node_num)
                if (now - last_heard) < window_s:
                    recently_heard.append(node_num)

        # known_count should be 2 (only genuinely-heard), NOT 7 (all + injected)
        self.assertEqual(len(all_other_nodes), 2)
        self.assertEqual(len(recently_heard), 0)


if __name__ == '__main__':
    unittest.main()
