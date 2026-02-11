#!/usr/bin/env python3
"""
Test: RX_LOG forwards ALL packet types to bot

Verifies that the _on_rx_log_data callback forwards all packet types,
not just TEXT_MESSAGE_APP, so that traffic statistics include all packets.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestRXLogForwardsAllPackets(unittest.TestCase):
    """Test that RX_LOG callback forwards all packet types"""
    
    def setUp(self):
        """Set up test environment"""
        # Mock dependencies
        self.mock_meshcore = Mock()
        self.mock_events = Mock()
        self.mock_meshcore.events = self.mock_events
        
        # Track forwarded packets
        self.forwarded_packets = []
        
        def message_callback(packet, interface):
            self.forwarded_packets.append(packet)
        
        self.message_callback = message_callback
    
    @patch('meshcore_cli_wrapper.MESHCORE_CLI_AVAILABLE', True)
    @patch('meshcore_cli_wrapper.MESHCORE_DECODER_AVAILABLE', True)
    @patch('meshcore_cli_wrapper.MeshCoreDecoder')
    @patch('meshcore_cli_wrapper.MeshCore')
    def test_text_message_forwarded(self, mock_meshcore_class, mock_decoder_class):
        """Test TEXT_MESSAGE_APP packets are forwarded"""
        from meshcore_cli_wrapper import MeshCoreCLIWrapper
        
        # Create wrapper
        wrapper = MeshCoreCLIWrapper('/dev/ttyUSB0')
        wrapper.message_callback = self.message_callback
        wrapper.localNode = Mock(nodeNum=0x12345678)
        
        # Mock decoded packet with text message
        mock_packet = Mock()
        mock_packet.payload = {'decoded': Mock(
            text='Hello world',
            public_key='143bcd7f1234567890abcdef'
        )}
        mock_packet.route_type = Mock()
        mock_packet.path_length = 0
        mock_packet.payload_type = Mock(name='TextMessage')
        
        mock_decoder_class.decode.return_value = mock_packet
        
        # Create RX_LOG event
        event = Mock()
        event.payload = {
            'snr': 5.0,
            'rssi': -80,
            'raw_hex': 'aabbccdd'
        }
        
        # Trigger callback
        wrapper._on_rx_log_data(event)
        
        # Verify packet was forwarded
        self.assertEqual(len(self.forwarded_packets), 1)
        forwarded = self.forwarded_packets[0]
        self.assertEqual(forwarded['decoded']['portnum'], 'TEXT_MESSAGE_APP')
        self.assertIn('Hello world', forwarded['decoded']['payload'].decode('utf-8'))
    
    @patch('meshcore_cli_wrapper.MESHCORE_CLI_AVAILABLE', True)
    @patch('meshcore_cli_wrapper.MESHCORE_DECODER_AVAILABLE', True)
    @patch('meshcore_cli_wrapper.MeshCoreDecoder')
    @patch('meshcore_cli_wrapper.MeshCore')
    def test_nodeinfo_forwarded(self, mock_meshcore_class, mock_decoder_class):
        """Test NODEINFO_APP packets are forwarded"""
        from meshcore_cli_wrapper import MeshCoreCLIWrapper
        
        # Create wrapper
        wrapper = MeshCoreCLIWrapper('/dev/ttyUSB0')
        wrapper.message_callback = self.message_callback
        wrapper.localNode = Mock(nodeNum=0x12345678)
        
        # Mock decoded packet with node info
        mock_packet = Mock()
        mock_packet.payload = {'decoded': Mock(
            app_data={'name': 'TestNode', 'role': 'CLIENT'},
            public_key='143bcd7f1234567890abcdef'
        )}
        mock_packet.route_type = Mock()
        mock_packet.path_length = 0
        mock_packet.payload_type = Mock(name='Advert')
        
        # Remove text attribute
        delattr(mock_packet.payload['decoded'], 'text')
        
        mock_decoder_class.decode.return_value = mock_packet
        
        # Create RX_LOG event
        event = Mock()
        event.payload = {
            'snr': 5.0,
            'rssi': -80,
            'raw_hex': 'aabbccdd'
        }
        
        # Trigger callback
        wrapper._on_rx_log_data(event)
        
        # Verify packet was forwarded
        self.assertEqual(len(self.forwarded_packets), 1)
        forwarded = self.forwarded_packets[0]
        self.assertEqual(forwarded['decoded']['portnum'], 'NODEINFO_APP')
    
    @patch('meshcore_cli_wrapper.MESHCORE_CLI_AVAILABLE', True)
    @patch('meshcore_cli_wrapper.MESHCORE_DECODER_AVAILABLE', True)
    @patch('meshcore_cli_wrapper.MeshCoreDecoder')
    @patch('meshcore_cli_wrapper.MeshCore')
    def test_telemetry_forwarded(self, mock_meshcore_class, mock_decoder_class):
        """Test TELEMETRY_APP packets are forwarded"""
        from meshcore_cli_wrapper import MeshCoreCLIWrapper
        
        # Create wrapper
        wrapper = MeshCoreCLIWrapper('/dev/ttyUSB0')
        wrapper.message_callback = self.message_callback
        wrapper.localNode = Mock(nodeNum=0x12345678)
        
        # Mock decoded packet with telemetry
        mock_packet = Mock()
        mock_decoded = Mock()
        # Remove text and app_data attributes
        if hasattr(mock_decoded, 'text'):
            delattr(mock_decoded, 'text')
        if hasattr(mock_decoded, 'app_data'):
            delattr(mock_decoded, 'app_data')
        mock_decoded.public_key = '143bcd7f1234567890abcdef'
        
        mock_packet.payload = {'decoded': mock_decoded}
        mock_packet.route_type = Mock()
        mock_packet.path_length = 0
        mock_packet.payload_type = Mock(name='TelemetryApp')
        
        mock_decoder_class.decode.return_value = mock_packet
        
        # Create RX_LOG event
        event = Mock()
        event.payload = {
            'snr': 5.0,
            'rssi': -80,
            'raw_hex': 'aabbccdd'
        }
        
        # Trigger callback
        wrapper._on_rx_log_data(event)
        
        # Verify packet was forwarded
        self.assertEqual(len(self.forwarded_packets), 1)
        forwarded = self.forwarded_packets[0]
        self.assertEqual(forwarded['decoded']['portnum'], 'TELEMETRY_APP')
    
    @patch('meshcore_cli_wrapper.MESHCORE_CLI_AVAILABLE', True)
    @patch('meshcore_cli_wrapper.MESHCORE_DECODER_AVAILABLE', True)
    @patch('meshcore_cli_wrapper.MeshCoreDecoder')
    @patch('meshcore_cli_wrapper.MeshCore')
    def test_position_forwarded(self, mock_meshcore_class, mock_decoder_class):
        """Test POSITION_APP packets are forwarded"""
        from meshcore_cli_wrapper import MeshCoreCLIWrapper
        
        # Create wrapper
        wrapper = MeshCoreCLIWrapper('/dev/ttyUSB0')
        wrapper.message_callback = self.message_callback
        wrapper.localNode = Mock(nodeNum=0x12345678)
        
        # Mock decoded packet with position
        mock_packet = Mock()
        mock_decoded = Mock()
        if hasattr(mock_decoded, 'text'):
            delattr(mock_decoded, 'text')
        if hasattr(mock_decoded, 'app_data'):
            delattr(mock_decoded, 'app_data')
        mock_decoded.public_key = '143bcd7f1234567890abcdef'
        
        mock_packet.payload = {'decoded': mock_decoded}
        mock_packet.route_type = Mock()
        mock_packet.path_length = 0
        mock_packet.payload_type = Mock(name='Position')
        
        mock_decoder_class.decode.return_value = mock_packet
        
        # Create RX_LOG event
        event = Mock()
        event.payload = {
            'snr': 5.0,
            'rssi': -80,
            'raw_hex': 'aabbccdd'
        }
        
        # Trigger callback
        wrapper._on_rx_log_data(event)
        
        # Verify packet was forwarded
        self.assertEqual(len(self.forwarded_packets), 1)
        forwarded = self.forwarded_packets[0]
        self.assertEqual(forwarded['decoded']['portnum'], 'POSITION_APP')
    
    @patch('meshcore_cli_wrapper.MESHCORE_CLI_AVAILABLE', True)
    @patch('meshcore_cli_wrapper.MESHCORE_DECODER_AVAILABLE', True)
    @patch('meshcore_cli_wrapper.MeshCoreDecoder')
    @patch('meshcore_cli_wrapper.MeshCore')
    def test_all_packets_have_rx_log_flag(self, mock_meshcore_class, mock_decoder_class):
        """Test all forwarded packets have _meshcore_rx_log flag"""
        from meshcore_cli_wrapper import MeshCoreCLIWrapper
        
        # Create wrapper
        wrapper = MeshCoreCLIWrapper('/dev/ttyUSB0')
        wrapper.message_callback = self.message_callback
        wrapper.localNode = Mock(nodeNum=0x12345678)
        
        # Test multiple packet types
        packet_types = [
            ('TextMessage', 'text', 'Hello'),
            ('Advert', 'app_data', {'name': 'Node'}),
            ('TelemetryApp', None, None),
            ('Position', None, None)
        ]
        
        for payload_type_name, attr_name, attr_value in packet_types:
            self.forwarded_packets.clear()
            
            # Mock decoded packet
            mock_packet = Mock()
            mock_decoded = Mock()
            
            # Set attribute based on type
            if attr_name and attr_value:
                setattr(mock_decoded, attr_name, attr_value)
            
            # Always set public key
            mock_decoded.public_key = '143bcd7f1234567890abcdef'
            
            mock_packet.payload = {'decoded': mock_decoded}
            mock_packet.route_type = Mock()
            mock_packet.path_length = 0
            mock_packet.payload_type = Mock(name=payload_type_name)
            
            mock_decoder_class.decode.return_value = mock_packet
            
            # Create RX_LOG event
            event = Mock()
            event.payload = {
                'snr': 5.0,
                'rssi': -80,
                'raw_hex': 'aabbccdd'
            }
            
            # Trigger callback
            wrapper._on_rx_log_data(event)
            
            # Verify packet was forwarded with flag
            self.assertEqual(len(self.forwarded_packets), 1)
            forwarded = self.forwarded_packets[0]
            self.assertTrue(forwarded.get('_meshcore_rx_log'), 
                          f"Packet type {payload_type_name} missing _meshcore_rx_log flag")


if __name__ == '__main__':
    unittest.main()
