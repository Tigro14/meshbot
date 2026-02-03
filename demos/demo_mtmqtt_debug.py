#!/usr/bin/env python3
"""
Demonstration of MTMQTT_DEBUG flag functionality

This script shows how MTMQTT_DEBUG controls debug output visibility
for Meshtastic MQTT traffic without requiring full DEBUG_MODE.
"""

import sys


def print_section(title):
    """Print a section header"""
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def demo_config():
    """Demonstrate configuration options"""
    print_section("1. Configuration Options")
    
    print("\nIn config.py:")
    print("-" * 70)
    print("""
# ========================================
# MTMQTT DEBUG (Meshtastic MQTT Traffic)
# ========================================
MTMQTT_DEBUG = False  # Default: minimal logging
# MTMQTT_DEBUG = True   # Enable: detailed MQTT traffic debug
""")
    
    print("\n✓ Easy to enable/disable")
    print("✓ Independent from DEBUG_MODE")
    print("✓ Safe to use in production")


def demo_output_disabled():
    """Demonstrate output when MTMQTT_DEBUG=False"""
    print_section("2. Output when MTMQTT_DEBUG=False (Default)")
    
    print("\nMinimal logging - only critical events:")
    print("-" * 70)
    print("""
[INFO] 👥 MQTT Neighbor Collector initialisé
[INFO]    Serveur: serveurperso.com:1883
[INFO]    Topic root: msh
[INFO] 👥 Connexion à serveurperso.com:1883...
[INFO] 👥 Connecté au serveur MQTT Meshtastic
[INFO]    Abonné à: msh/EU_868/2/e/MediumFast/# (topic spécifique)
[INFO] 👥 Thread MQTT démarré avec auto-reconnect (non-bloquant)
""")
    
    print("✓ Clean, minimal output")
    print("✓ Only shows connection status")
    print("✓ No traffic details")


def demo_output_enabled():
    """Demonstrate output when MTMQTT_DEBUG=True"""
    print_section("3. Output when MTMQTT_DEBUG=True (Verbose)")
    
    print("\nDetailed logging - full MQTT traffic visibility:")
    print("-" * 70)
    print("""
[INFO] 👥 MQTT Neighbor Collector initialisé
[INFO]    Serveur: serveurperso.com:1883
[INFO]    Topic root: msh
[INFO] [MTMQTT] Starting connection to serveurperso.com:1883
[INFO] 👥 Connexion à serveurperso.com:1883...
[INFO] 👥 Connecté au serveur MQTT Meshtastic
[INFO]    Abonné à: msh/EU_868/2/e/MediumFast/# (topic spécifique)
[INFO] [MTMQTT] Topic subscription: msh/EU_868/2/e/MediumFast/#
[INFO] [MTMQTT] Connected to serveurperso.com:1883
[INFO] [MTMQTT] Ready to receive Meshtastic MQTT traffic
[INFO] 👥 Thread MQTT démarré avec auto-reconnect (non-bloquant)

[INFO] [MTMQTT] Received message on topic: msh/EU_868/2/e/MediumFast/!a1b2c3d4
[INFO] [MTMQTT] Packet from !5e6f7g8h (ID: 123456789) via gateway: !a1b2c3d4
[INFO] [MTMQTT] Processing NEIGHBORINFO_APP packet from !5e6f7g8h
[INFO] [MTMQTT] Processing NEIGHBORINFO from !5e6f7g8h
[INFO] [MTMQTT] Node !5e6f7g8h reports 4 neighbors
[INFO] [MTMQTT]   → Neighbor !9i0j1k2l SNR=12.5dB
[INFO] [MTMQTT]   → Neighbor !3m4n5o6p SNR=8.2dB
[INFO] [MTMQTT]   → Neighbor !7q8r9s0t SNR=15.7dB
[INFO] [MTMQTT]   → Neighbor !1u2v3w4x SNR=6.9dB

[INFO] [MTMQTT] Received message on topic: msh/EU_868/2/e/MediumFast/!a1b2c3d4
[INFO] [MTMQTT] Packet from !9y0z1a2b (ID: 987654321) via gateway: !a1b2c3d4
[INFO] [MTMQTT] Processing POSITION_APP packet from !9y0z1a2b

[INFO] [MTMQTT] Received message on topic: msh/EU_868/2/e/MediumFast/!a1b2c3d4
[INFO] [MTMQTT] Duplicate packet filtered: 123456789 from !5e6f7g8h
""")
    
    print("✓ Detailed traffic information")
    print("✓ Shows all packet processing")
    print("✓ Neighbor details with SNR values")
    print("✓ Deduplication events")
    print("✓ Easy filtering with [MTMQTT] prefix")


def demo_filtering():
    """Demonstrate log filtering"""
    print_section("4. Log Filtering Examples")
    
    print("\nFilter only MTMQTT debug messages:")
    print("-" * 70)
    print("""
# View only MTMQTT debug logs
journalctl -u meshbot | grep '\\[MTMQTT\\]'

# View last 100 MTMQTT logs
journalctl -u meshbot -n 100 | grep '\\[MTMQTT\\]'

# Follow live MTMQTT logs
journalctl -u meshbot -f | grep --line-buffered '\\[MTMQTT\\]'

# Count MTMQTT messages in last hour
journalctl -u meshbot --since "1 hour ago" | grep -c '\\[MTMQTT\\]'

# Show only neighbor reports
journalctl -u meshbot | grep '\\[MTMQTT\\]' | grep 'reports.*neighbors'
""")
    
    print("✓ Easy to filter with [MTMQTT] prefix")
    print("✓ Works with standard grep/journalctl")
    print("✓ Can combine with other filters")


def demo_use_cases():
    """Demonstrate common use cases"""
    print_section("5. Common Use Cases")
    
    print("\n📌 Use Case 1: MQTT Not Connecting")
    print("-" * 70)
    print("Problem: Bot doesn't receive MQTT neighbor data")
    print("Solution: Enable MTMQTT_DEBUG=True and check:")
    print("  • Connection established?")
    print("    → Look for: [MTMQTT] Connected to ...")
    print("  • Authentication working?")
    print("    → Look for: [MTMQTT] Authentication configured")
    print("  • Topic subscription correct?")
    print("    → Look for: [MTMQTT] Topic subscription: ...")
    
    print("\n📌 Use Case 2: No Neighbor Data Saved")
    print("-" * 70)
    print("Problem: MQTT connects but no neighbors in database")
    print("Solution: Enable MTMQTT_DEBUG=True and check:")
    print("  • Messages received?")
    print("    → Look for: [MTMQTT] Received message on topic:")
    print("  • NEIGHBORINFO packets processed?")
    print("    → Look for: [MTMQTT] Processing NEIGHBORINFO from")
    print("  • Neighbors found in packets?")
    print("    → Look for: [MTMQTT] Node !xxx reports N neighbors")
    
    print("\n📌 Use Case 3: Performance Issues")
    print("-" * 70)
    print("Problem: Too many MQTT messages flooding logs")
    print("Solution: Enable MTMQTT_DEBUG=True temporarily to:")
    print("  • Count message rate")
    print("  • Identify duplicate packets")
    print("  • Check deduplication efficiency")
    print("  • Then disable MTMQTT_DEBUG after analysis")
    
    print("\n📌 Use Case 4: Development & Testing")
    print("-" * 70)
    print("Problem: Need to verify MQTT integration changes")
    print("Solution: Enable MTMQTT_DEBUG=True to:")
    print("  • Verify message flow")
    print("  • Check packet parsing")
    print("  • Validate neighbor extraction")
    print("  • Monitor error handling")


def demo_comparison():
    """Demonstrate comparison with other debug options"""
    print_section("6. Comparison with DEBUG_MODE")
    
    print("\n┌─────────────────┬───────────────────┬─────────────────┐")
    print("│ Feature         │ MTMQTT_DEBUG=True │ DEBUG_MODE=True │")
    print("├─────────────────┼───────────────────┼─────────────────┤")
    print("│ Scope           │ MQTT only         │ All components  │")
    print("│ Visibility      │ Always visible    │ Debug only      │")
    print("│ Prefix          │ [MTMQTT]          │ Various         │")
    print("│ Performance     │ Minimal impact    │ Higher impact   │")
    print("│ Use case        │ MQTT debug        │ Full bot debug  │")
    print("│ Production safe │ ✅ Yes            │ ⚠️  Verbose     │")
    print("└─────────────────┴───────────────────┴─────────────────┘")
    
    print("\n💡 Tip: Use MTMQTT_DEBUG for focused MQTT troubleshooting")
    print("        without the noise of full DEBUG_MODE")


def demo_implementation():
    """Show implementation details"""
    print_section("7. Implementation Pattern")
    
    print("\nCode pattern used throughout mqtt_neighbor_collector.py:")
    print("-" * 70)
    print("""
# Import with fallback
try:
    from config import MTMQTT_DEBUG
except ImportError:
    MTMQTT_DEBUG = False  # Default if not in config

# Conditional logging
if MTMQTT_DEBUG:
    info_print("[MTMQTT] Debug message here")

# Why info_print() instead of debug_print()?
# - debug_print() only shows when DEBUG_MODE=True
# - info_print() always shows (stdout)
# - Allows MQTT debug without full debug mode
""")
    
    print("✓ Simple and consistent pattern")
    print("✓ Minimal code changes")
    print("✓ Easy to maintain")


def demo_testing():
    """Show testing information"""
    print_section("8. Testing")
    
    print("\nRun the test suite:")
    print("-" * 70)
    print("""
python3 test_mtmqtt_debug.py
""")
    
    print("\nTests verify:")
    print("  ✓ Flag can be imported from config")
    print("  ✓ Flag is documented in config.py.sample")
    print("  ✓ Collector imports flag with fallback")
    print("  ✓ Debug logging is conditionally present")
    print("  ✓ Debug messages use info_print()")
    print("  ✓ All messages use [MTMQTT] prefix")
    print("  ✓ No breaking changes to existing code")
    print("  ✓ Collector initialization still works")


def main():
    """Run all demonstrations"""
    print("=" * 70)
    print(" MTMQTT_DEBUG Flag Demonstration")
    print(" Meshtastic MQTT Traffic Debugging")
    print("=" * 70)
    
    demo_config()
    demo_output_disabled()
    demo_output_enabled()
    demo_filtering()
    demo_use_cases()
    demo_comparison()
    demo_implementation()
    demo_testing()
    
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print("""
The MTMQTT_DEBUG flag provides:
  ✅ Granular control over Meshtastic MQTT debugging
  ✅ Independent from full DEBUG_MODE
  ✅ Easy filtering with [MTMQTT] prefix
  ✅ Minimal performance impact
  ✅ Production-safe troubleshooting
  ✅ Comprehensive MQTT lifecycle coverage

Enable it in config.py when you need to debug MQTT neighbor collection
without the noise of full debug mode!

📚 Full documentation: MTMQTT_DEBUG_DOCUMENTATION.md
🧪 Test suite: test_mtmqtt_debug.py
""")
    print("=" * 70)


if __name__ == '__main__':
    main()
