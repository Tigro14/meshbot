#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test for /trafficmc command - MeshCore traffic filtering
"""

import sys
import os
import time
from collections import deque

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from traffic_monitor import TrafficMonitor
from node_manager import NodeManager


class MockNodeManager:
    """Mock NodeManager for testing"""
    def __init__(self):
        self.nodes = {}
        self.rx_history = {}
    
    def get_node_name(self, node_id, interface=None):
        """Return a mock node name"""
        return f"TestNode{node_id:04x}"


class MockPersistence:
    """Mock TrafficPersistence for testing"""
    def save_public_message(self, message_entry):
        """Mock save method"""
        pass


def test_traffic_report_mc_filtering():
    """Test that get_traffic_report_mc only shows MeshCore traffic"""
    print("=" * 60)
    print("TEST: MeshCore Traffic Filtering")
    print("=" * 60)
    
    # Create mock node manager
    node_manager = MockNodeManager()
    
    # Create traffic monitor
    traffic_monitor = TrafficMonitor(node_manager)
    
    # Mock the persistence layer
    traffic_monitor.persistence = MockPersistence()
    
    # Add test messages with different sources
    current_time = time.time()
    
    # Add Meshtastic messages
    for i in range(3):
        packet = {
            'from': 0x1000 + i,
            'to': 0xFFFFFFFF,
            'rssi': -80,
            'snr': 5.0
        }
        message = f"Meshtastic message {i+1}"
        traffic_monitor.add_public_message(packet, message, source='local')
    
    # Add MeshCore messages
    for i in range(5):
        packet = {
            'from': 0x2000 + i,
            'to': 0xFFFFFFFF,
            'rssi': -75,
            'snr': 8.0
        }
        message = f"MeshCore message {i+1}"
        traffic_monitor.add_public_message(packet, message, source='meshcore')
    
    # Add more Meshtastic messages
    for i in range(2):
        packet = {
            'from': 0x3000 + i,
            'to': 0xFFFFFFFF,
            'rssi': -85,
            'snr': 3.0
        }
        message = f"Meshtastic TCP message {i+1}"
        traffic_monitor.add_public_message(packet, message, source='tcp')
    
    print(f"\n📊 Total messages added: {len(traffic_monitor.public_messages)}")
    print(f"   - Meshtastic (local): 3")
    print(f"   - MeshCore: 5")
    print(f"   - Meshtastic (tcp): 2")
    
    # Test get_traffic_report (all traffic)
    print("\n" + "=" * 60)
    print("TEST 1: get_traffic_report() - Should show ALL messages")
    print("=" * 60)
    report_all = traffic_monitor.get_traffic_report(hours=24)
    print(report_all)
    
    # Count messages in report
    all_count = report_all.count("[TestNode")
    print(f"\n✅ Messages in all traffic report: {all_count}")
    assert all_count == 10, f"Expected 10 messages, got {all_count}"
    
    # Test get_traffic_report_mc (MeshCore only)
    print("\n" + "=" * 60)
    print("TEST 2: get_traffic_report_mc() - Should show ONLY MeshCore messages")
    print("=" * 60)
    report_mc = traffic_monitor.get_traffic_report_mc(hours=24)
    print(report_mc)
    
    # Count messages in report
    mc_count = report_mc.count("[TestNode")
    print(f"\n✅ Messages in MeshCore traffic report: {mc_count}")
    assert mc_count == 5, f"Expected 5 MeshCore messages, got {mc_count}"
    
    # Verify MeshCore messages are present
    for i in range(5):
        expected_msg = f"MeshCore message {i+1}"
        assert expected_msg in report_mc, f"Missing: {expected_msg}"
    
    # Verify Meshtastic messages are NOT present
    for i in range(3):
        unexpected_msg = f"Meshtastic message {i+1}"
        assert unexpected_msg not in report_mc, f"Should not contain: {unexpected_msg}"
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
    print("\nSummary:")
    print(f"  ✅ get_traffic_report() shows all {all_count} messages")
    print(f"  ✅ get_traffic_report_mc() shows only {mc_count} MeshCore messages")
    print(f"  ✅ Filtering works correctly")


def test_empty_meshcore_traffic():
    """Test behavior when no MeshCore traffic exists"""
    print("\n" + "=" * 60)
    print("TEST 3: Empty MeshCore Traffic")
    print("=" * 60)
    
    # Create mock node manager
    node_manager = MockNodeManager()
    
    # Create traffic monitor
    traffic_monitor = TrafficMonitor(node_manager)
    
    # Mock the persistence layer
    traffic_monitor.persistence = MockPersistence()
    
    # Add only Meshtastic messages
    for i in range(3):
        packet = {
            'from': 0x1000 + i,
            'to': 0xFFFFFFFF,
            'rssi': -80,
            'snr': 5.0
        }
        message = f"Meshtastic message {i+1}"
        traffic_monitor.add_public_message(packet, message, source='local')
    
    # Get MeshCore report
    report_mc = traffic_monitor.get_traffic_report_mc(hours=24)
    print(report_mc)
    
    # Should show "no messages" text
    assert "Aucun message public MeshCore" in report_mc, "Should indicate no MeshCore messages"
    
    print("\n✅ Empty MeshCore traffic handled correctly")


if __name__ == "__main__":
    try:
        test_traffic_report_mc_filtering()
        test_empty_meshcore_traffic()
        
        print("\n" + "=" * 60)
        print("🎉 ALL TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
