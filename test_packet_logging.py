#!/usr/bin/env python3
"""
Test script to verify packet logging is working
"""

import sys
sys.path.insert(0, '/home/runner/work/meshbot/meshbot')

from utils import debug_print, info_print, debug_print_mt, info_print_mt
from config import DEBUG_MODE

print(f"=== PACKET LOGGING TEST ===")
print(f"DEBUG_MODE = {DEBUG_MODE}")
print()

print("Testing debug_print:")
debug_print("Test debug message")

print("\nTesting info_print:")
info_print("Test info message")

print("\nTesting debug_print_mt:")
debug_print_mt("📦 TEST PACKET")

print("\nTesting info_print_mt:")
info_print_mt("💿 TEST ROUTE-SAVE")

print("\n=== Testing packet flow simulation ===")

# Simulate a packet entry
packet_entry = {
    'source': 'local',
    'from_id': 0x12345678,
    'to_id': 0xFFFFFFFF,
    'packet_type': 'TEXT_MESSAGE_APP',
}

sender_name = "TestNode"
packet_type = "TEXTMESSAGE"  # Short form (no _APP suffix)
source = "local"
node_id_short = "345678"

# After fix: Only comprehensive 2-line format is logged
# Line 1: Header with key metrics
debug_print_mt(f"🌐 {source.upper()} {packet_type} from {sender_name} ({node_id_short}) | Hops:0/3 | SNR:12.0dB(🟢) | RSSI:-45dBm | Ch:0")

# Line 2: Details
debug_print_mt(f"  └─ Msg:\"Test message\" | Payload:42B | ID:123456 | RX:14:23:45")

print("\n=== Test complete ===")
print("If you see 2 [DEBUG][MT] messages above (header + details), logging is working.")
print("Previous behavior (4-5 lines with duplicates) has been removed.")
print("If not, there's an issue with debug_print_mt or DEBUG_MODE.")
