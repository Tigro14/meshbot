#!/usr/bin/env python3
"""
Test script to verify duplicate debug line removal.

This script simulates packet processing and verifies that:
1. Only 2 lines are printed per packet (instead of 4-5)
2. No duplicate "📦" messages
3. No redundant "📊 Paquet enregistré" lines
4. Clean concise output with all necessary information
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock config before imports
class MockConfig:
    DEBUG_MODE = True
    
import config
for attr in dir(MockConfig):
    if not attr.startswith('_'):
        setattr(config, attr, getattr(MockConfig, attr))

from traffic_monitor import TrafficMonitor
from node_manager import NodeManager
from traffic_persistence import TrafficPersistence
from utils import debug_print_mt, debug_print_mc
import time

def count_debug_lines(packet_type, source='local'):
    """
    Count how many debug lines are printed for a single packet.
    Expected: 2 lines (header + details)
    """
    # Capture stdout
    from io import StringIO
    import sys
    old_stderr = sys.stderr
    sys.stderr = StringIO()
    
    # Create test objects
    node_mgr = NodeManager()
    persistence = TrafficPersistence(':memory:')
    monitor = TrafficMonitor(node_mgr, persistence)
    
    # Create test packet
    test_packet = {
        'from': 0x12345678,
        'to': 0xFFFFFFFF,
        'id': 123456789,
        'rxTime': time.time(),
        'rxRssi': -85,
        'rxSnr': 5.5,
        'hopLimit': 3,
        'hopStart': 3,
        'channel': 0,
        'decoded': {
            'portnum': packet_type,
        }
    }
    
    # Add type-specific data
    if packet_type == 'TEXT_MESSAGE_APP':
        test_packet['decoded']['text'] = 'Test message'
    elif packet_type == 'POSITION_APP':
        test_packet['decoded']['position'] = {
            'latitudeI': 488000000,  # 48.8°N
            'longitudeI': 23000000,  # 2.3°E
            'altitude': 100
        }
    elif packet_type == 'NODEINFO_APP':
        test_packet['decoded']['user'] = {
            'id': '!12345678',
            'longName': 'Test Node',
            'shortName': 'TST',
            'hwModel': 'TBEAM'
        }
    elif packet_type == 'TELEMETRY_APP':
        test_packet['decoded']['telemetry'] = {
            'deviceMetrics': {
                'batteryLevel': 85,
                'voltage': 4.2,
                'channelUtilization': 15.5
            }
        }
    
    # Add node to manager
    node_mgr.nodes[0x12345678] = {
        'num': 0x12345678,
        'user': {
            'id': '!12345678',
            'longName': 'Test Node',
            'shortName': 'TST'
        }
    }
    
    # Process packet
    monitor.add_packet(test_packet, source=source)
    
    # Get captured output
    output = sys.stderr.getvalue()
    sys.stderr = old_stderr
    
    # Count debug lines
    lines = [line for line in output.split('\n') if line.strip() and '[DEBUG]' in line]
    
    return lines, output

def test_packet_types():
    """Test various packet types to ensure no duplicates."""
    packet_types = [
        'TEXT_MESSAGE_APP',
        'POSITION_APP',
        'NODEINFO_APP',
        'TELEMETRY_APP',
        'NEIGHBORINFO_APP'
    ]
    
    print("=" * 80)
    print("Testing Duplicate Debug Line Removal")
    print("=" * 80)
    print()
    
    all_pass = True
    
    for pkt_type in packet_types:
        print(f"\nTesting {pkt_type}:")
        print("-" * 60)
        
        lines, output = count_debug_lines(pkt_type, source='local')
        
        # Print captured output
        for line in lines:
            print(line)
        
        # Check for issues
        issues = []
        
        # Count lines
        if len(lines) > 2:
            issues.append(f"❌ Expected 2 lines, got {len(lines)}")
            all_pass = False
        else:
            print(f"✅ Line count OK: {len(lines)} lines")
        
        # Check for duplicates
        packet_emoji_lines = [l for l in lines if '📦' in l]
        if len(packet_emoji_lines) > 0:
            issues.append(f"❌ Found {len(packet_emoji_lines)} lines with '📦' emoji (should be 0 now)")
            all_pass = False
        else:
            print("✅ No duplicate '📦' lines")
        
        # Check for "Paquet enregistré"
        enregistre_lines = [l for l in lines if 'Paquet enregistré' in l]
        if len(enregistre_lines) > 0:
            issues.append(f"❌ Found {len(enregistre_lines)} 'Paquet enregistré' lines (should be 0)")
            all_pass = False
        else:
            print("✅ No 'Paquet enregistré' lines")
        
        # Check for comprehensive debug (should have 2 lines: header + details)
        has_header = any('🌐' in l or '🔗' in l for l in lines)
        has_details = any('└─' in l for l in lines)
        
        if not has_header:
            issues.append("❌ Missing header line (🌐 or 🔗)")
            all_pass = False
        else:
            print("✅ Header line present")
        
        if not has_details:
            issues.append("❌ Missing details line (└─)")
            all_pass = False
        else:
            print("✅ Details line present")
        
        # Print issues
        if issues:
            print("\nIssues found:")
            for issue in issues:
                print(f"  {issue}")
    
    print("\n" + "=" * 80)
    if all_pass:
        print("✅ ALL TESTS PASSED - No duplicate debug lines!")
        return 0
    else:
        print("❌ SOME TESTS FAILED - Review output above")
        return 1

if __name__ == '__main__':
    sys.exit(test_packet_types())
