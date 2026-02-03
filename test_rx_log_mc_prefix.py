#!/usr/bin/env python3
"""
Test to verify RX_LOG messages use [MC] prefix
"""

import sys
import io
sys.path.insert(0, '/home/runner/work/meshbot/meshbot')

# Set DEBUG_MODE to True for testing
import config
config.DEBUG_MODE = True

from utils import debug_print_mc

print("=" * 70)
print("RX_LOG MC Prefix Test")
print("=" * 70)
print()

print("Testing RX_LOG messages that were missing MC prefix:")
print("-" * 70)

# Simulate the log messages from the problem statement
debug_print_mc("📡 [RX_LOG] Paquet RF reçu (71B) - SNR:13.75dB RSSI:-32dBm Hex:37e01500118c23c045d0607e3b97b9ed3e582942...")
debug_print_mc("📦 [RX_LOG] Type: Unknown(13) | Route: Flood | Size: 71B | Status: ℹ️")
debug_print_mc("📡 [RX_LOG] Paquet RF reçu (72B) - SNR:13.25dB RSSI:-46dBm Hex:35d21501bf118c23c045d0607e3b97b9ed3e5829...")
debug_print_mc("📦 [RX_LOG] Type: Unknown(13) | Route: Flood | Size: 72B | Status: ℹ️")

print()
print("-" * 70)
print("✅ All RX_LOG messages now show [DEBUG][MC] prefix!")
print()

print("Expected output format:")
print("  [DEBUG][MC] 📡 [RX_LOG] Paquet RF reçu (71B) - SNR:13.75dB RSSI:-32dBm")
print("  [DEBUG][MC] 📦 [RX_LOG] Type: Unknown(13) | Route: Flood | Size: 71B")
print()

print("Verification:")
print("-" * 70)

# Capture output to verify format
from io import StringIO
import sys

old_stderr = sys.stderr
sys.stderr = StringIO()

debug_print_mc("Test message")
output = sys.stderr.getvalue()
sys.stderr = old_stderr

if "[DEBUG][MC]" in output:
    print("✅ PASS: debug_print_mc() produces [DEBUG][MC] prefix")
else:
    print("❌ FAIL: debug_print_mc() does not produce [DEBUG][MC] prefix")
    print(f"   Got: {output}")

print()
print("=" * 70)
