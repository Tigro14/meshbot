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
packet_type = "TEXT_MESSAGE_APP"
source = "local"

# This is what should appear in logs
source_tag = f"[{packet_entry.get('source', '?')}]"
debug_print_mt(f"📊 Paquet enregistré ({source_tag}): {packet_type} de {sender_name}")

node_id_short = "45678"
route_info = " [direct] (SNR:12.0dB)"
debug_print_mt(f"📦 {packet_type} de {sender_name} {node_id_short}{route_info}")

print("\n=== Test complete ===")
print("If you see [DEBUG][MT] messages above, logging is working.")
print("If not, there's an issue with debug_print_mt or DEBUG_MODE.")
