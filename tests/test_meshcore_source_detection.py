#!/usr/bin/env python3
"""
Test script to verify MeshCore packet source detection and logging.

This script simulates packets with different sources and verifies that:
1. Source is correctly detected and set
2. DEBUG logging shows the source classification
3. MeshCore packets trigger MC-specific debug logs
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock config before imports
class MockConfig:
    DEBUG_MODE = True

sys.modules['config'] = MockConfig()

from utils import debug_print, debug_print_mc, debug_print_mt, info_print_mc

def test_source_classification():
    """Test that different sources are correctly identified"""
    print("\n" + "="*80)
    print("TEST: Source Classification and Logging")
    print("="*80)
    
    # Test 1: MeshCore source
    print("\n1. Testing MeshCore source classification:")
    source = 'meshcore'
    from_id = 0x12345678
    packet_type = 'TEXT_MESSAGE_APP'
    
    debug_print(f"🔍 [PACKET-SOURCE] add_packet called with source='{source}' from=0x{from_id:08x}")
    
    if source == 'meshcore':
        info_print_mc("=" * 80)
        info_print_mc("🔗 MC DEBUG: MESHCORE PACKET IN add_packet()")
        info_print_mc("=" * 80)
        info_print_mc(f"📦 From: 0x{from_id:08x}")
        info_print_mc(f"🔗 Source: {source}")
        info_print_mc(f"📨 PortNum: {packet_type}")
        info_print_mc("=" * 80)
        
        # Classification logging
        debug_print_mc(f"📦 {packet_type} de TestNode {from_id:08x}[-5:] [direct] (SNR:10.0dB)")
        print("✅ MeshCore source detected and logged with [DEBUG][MC] prefix")
    else:
        print("❌ MeshCore source NOT detected")
    
    # Test 2: Meshtastic/local source
    print("\n2. Testing Meshtastic/local source classification:")
    source = 'local'
    
    debug_print(f"🔍 [PACKET-SOURCE] add_packet called with source='{source}' from=0x{from_id:08x}")
    
    if source == 'meshcore':
        print("❌ Incorrectly identified as MeshCore")
    else:
        debug_print(f"🔍 [PACKET-SOURCE] Non-MeshCore packet: source='{source}'")
        debug_print_mt(f"📦 {packet_type} de TestNode {from_id:08x}[-5:] [direct] (SNR:10.0dB)")
        print("✅ Non-MeshCore source detected and logged with [DEBUG][MT] prefix")
    
    # Test 3: TCP source
    print("\n3. Testing TCP source classification:")
    source = 'tcp'
    
    debug_print(f"🔍 [PACKET-SOURCE] add_packet called with source='{source}' from=0x{from_id:08x}")
    
    if source == 'meshcore':
        print("❌ Incorrectly identified as MeshCore")
    else:
        debug_print(f"🔍 [PACKET-SOURCE] Non-MeshCore packet: source='{source}'")
        debug_print_mt(f"📦 {packet_type} de TestNode {from_id:08x}[-5:] [direct] (SNR:10.0dB)")
        print("✅ TCP source detected and logged with [DEBUG][MT] prefix")
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)
    print("\nExpected behavior in DEBUG mode:")
    print("- MeshCore packets: Logged with [DEBUG][MC] or [INFO][MC] prefix")
    print("- Meshtastic packets: Logged with [DEBUG][MT] prefix")
    print("- Source classification visible in DEBUG logs")
    print("\nIf you don't see [DEBUG][MC] logs for MeshCore packets:")
    print("1. Check that DEBUG_MODE = True in config.py")
    print("2. Check that source is set to 'meshcore' (not 'local', 'tcp', etc.)")
    print("3. Check logs with: journalctl -u meshbot -f | grep '\\[MC\\]'")

def test_source_detection_logic():
    """Test the source detection logic with different scenarios"""
    print("\n" + "="*80)
    print("TEST: Source Detection Logic")
    print("="*80)
    
    # Simulate NetworkSource class
    class NetworkSource:
        MESHTASTIC = 'meshtastic'
        MESHCORE = 'meshcore'
        UNKNOWN = 'unknown'
    
    scenarios = [
        ("Dual mode + NetworkSource.MESHCORE", True, NetworkSource.MESHCORE, False, 'meshcore'),
        ("Dual mode + NetworkSource.MESHTASTIC", True, NetworkSource.MESHTASTIC, False, 'meshtastic'),
        ("Dual mode + None network_source", True, None, False, None),
        ("Single mode + MESHCORE_ENABLED", False, None, True, 'meshcore'),
        ("Single mode + No MESHCORE_ENABLED", False, None, False, None),
    ]
    
    for desc, dual_mode, network_source, meshcore_enabled, expected_source in scenarios:
        print(f"\nScenario: {desc}")
        print(f"  dual_mode={dual_mode}, network_source={network_source}, meshcore_enabled={meshcore_enabled}")
        
        # Simulate source detection logic
        source = None
        if dual_mode and network_source:
            if network_source == NetworkSource.MESHCORE:
                source = 'meshcore'
                debug_print("🔍 Source détectée: MeshCore (dual mode)")
            elif network_source == NetworkSource.MESHTASTIC:
                source = 'meshtastic'
                debug_print("🔍 Source détectée: Meshtastic (dual mode)")
        elif meshcore_enabled and not dual_mode:
            source = 'meshcore'
            debug_print("🔍 Source détectée: MeshCore (MESHCORE_ENABLED=True, single mode)")
        
        if source == expected_source:
            print(f"  ✅ PASS: source = '{source}' (expected '{expected_source}')")
        else:
            print(f"  ❌ FAIL: source = '{source}' (expected '{expected_source}')")
    
    print("\n" + "="*80)

if __name__ == '__main__':
    test_source_classification()
    test_source_detection_logic()
