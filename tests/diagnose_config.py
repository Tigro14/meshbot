#!/usr/bin/env python3
"""
Quick diagnostic script to check bot configuration and status
Run this to see what mode the bot is configured for
"""

import sys
import os

print("=" * 80)
print("🔍 MESHBOT CONFIGURATION DIAGNOSTIC")
print("=" * 80)
print()

# Try to import config
try:
    sys.path.insert(0, '/home/dietpi/bot')
    from config import *
    print("✅ Config loaded from /home/dietpi/bot/config.py")
except ImportError as e:
    print(f"❌ Cannot import config: {e}")
    print("   Make sure you're running this from the bot directory")
    sys.exit(1)

print()
print("📋 KEY CONFIGURATION VALUES:")
print("-" * 80)

# Check mode settings
meshtastic_enabled = globals().get('MESHTASTIC_ENABLED', True)
meshcore_enabled = globals().get('MESHCORE_ENABLED', False)
dual_mode = globals().get('DUAL_NETWORK_MODE', False)
connection_mode = globals().get('CONNECTION_MODE', 'serial')

print(f"   MESHTASTIC_ENABLED = {meshtastic_enabled}")
print(f"   MESHCORE_ENABLED = {meshcore_enabled}")
print(f"   DUAL_NETWORK_MODE = {dual_mode}")
print(f"   CONNECTION_MODE = {connection_mode}")

# Check DEBUG_MODE
debug_mode = globals().get('DEBUG_MODE', False)
print(f"   DEBUG_MODE = {debug_mode}")

print()

# Determine mode
if dual_mode:
    print("🔀 MODE: DUAL NETWORK (Meshtastic + MeshCore)")
    print("   → Both interfaces active")
    print("   → Packets come from BOTH sources")
elif meshtastic_enabled and not meshcore_enabled:
    print("📡 MODE: MESHTASTIC ONLY")
    print("   → Meshtastic interface active")
    print("   → Should subscribe to 'meshtastic.receive'")
    print("   → Packets via pubsub")
elif meshcore_enabled and not meshtastic_enabled:
    print("🔌 MODE: MESHCORE COMPANION ONLY")
    print("   → MeshCore interface active")
    print("   → Direct callback, NOT pubsub")
    print("   → Only DM messages")
elif not meshtastic_enabled and not meshcore_enabled:
    print("⚠️  MODE: STANDALONE (Neither enabled)")
    print("   → No mesh connectivity!")
else:
    print("🤔 MODE: UNKNOWN CONFIGURATION")

print()

# Check serial ports
if connection_mode == 'serial':
    serial_port = globals().get('SERIAL_PORT', '/dev/ttyACM0')
    print(f"📟 SERIAL PORT: {serial_port}")
    
    # Check if port exists
    if os.path.exists(serial_port):
        print(f"   ✅ Port exists")
        
        # Check permissions
        import stat
        st = os.stat(serial_port)
        print(f"   Permissions: {oct(st.st_mode)[-3:]}")
        
        # Check if locked
        try:
            import subprocess
            result = subprocess.run(['lsof', serial_port], 
                                  capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                print(f"   ⚠️  Port is LOCKED by:")
                for line in result.stdout.strip().split('\n')[1:]:  # Skip header
                    print(f"      {line}")
            else:
                print(f"   ✅ Port is available")
        except:
            print(f"   ⚠️  Cannot check if port is locked (lsof not available)")
    else:
        print(f"   ❌ Port does NOT exist!")
        print(f"   Check: ls -la /dev/ttyACM* /dev/ttyUSB*")
else:
    tcp_host = globals().get('REMOTE_NODE_HOST', '192.168.1.38')
    tcp_port = globals().get('REMOTE_NODE_PORT', 4403)
    print(f"🌐 TCP CONNECTION: {tcp_host}:{tcp_port}")

print()
print("-" * 80)
print()

# Expected behavior
print("📝 EXPECTED BEHAVIOR WITH CURRENT CONFIG:")
print()

if meshtastic_enabled:
    print("When bot starts, you should see:")
    print("  1. Huge banner with '🔔 SUBSCRIPTION SETUP'")
    print("  2. '✅ ✅ ✅ SUBSCRIBED TO meshtastic.receive ✅ ✅ ✅'")
    print("  3. '🧪 Testing pubsub mechanism...'")
    print("  4. 'Subscribers to meshtastic.receive: 1' (or more)")
    print()
    print("When packets arrive, you should see:")
    print("  - '🔔🔔🔔 on_message CALLED (logger) ...'")
    print("  - '🔔🔔🔔 on_message CALLED (print) ...'")
    print("  - '[INFO] 🔵 add_packet ENTRY ...'")
    print()
    if not debug_mode:
        print("⚠️  WARNING: DEBUG_MODE = False")
        print("   You will NOT see [DEBUG] packet logs!")
        print("   But you WILL see [INFO] logs (🔔, 🔵, etc.)")
else:
    print("MeshCore mode - different behavior:")
    print("  - No pubsub subscription")
    print("  - Direct callback from MeshCore")
    print("  - Should see '🔔🔔🔔 on_message CALLED' from MeshCore")

print()
print("=" * 80)
print("🔍 DIAGNOSTIC COMPLETE")
print("=" * 80)
print()
print("Next steps:")
print("1. Restart bot: sudo systemctl restart meshtastic-bot")
print("2. Watch logs: journalctl -u meshtastic-bot -f")
print("3. Look for the startup banner with '🔔 SUBSCRIPTION SETUP'")
print("4. Report what you see!")
