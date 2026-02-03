#!/usr/bin/env python3
"""
Diagnostic script to identify why no packet logs appear
Checks configuration, interface status, and packet reception
"""

import sys
import time
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_config():
    """Check configuration settings"""
    print("=" * 80)
    print("CONFIGURATION CHECK")
    print("=" * 80)
    
    try:
        import config
        
        # Check DEBUG_MODE
        debug_mode = getattr(config, 'DEBUG_MODE', False)
        print(f"DEBUG_MODE: {debug_mode}")
        if not debug_mode:
            print("  ⚠️  DEBUG_MODE is False - packet logs will not appear!")
            print("  💡 Set DEBUG_MODE = True in config.py")
        
        # Check network mode
        dual_mode = getattr(config, 'DUAL_NETWORK_MODE', False)
        meshtastic_enabled = getattr(config, 'MESHTASTIC_ENABLED', True)
        meshcore_enabled = getattr(config, 'MESHCORE_ENABLED', False)
        
        print(f"DUAL_NETWORK_MODE: {dual_mode}")
        print(f"MESHTASTIC_ENABLED: {meshtastic_enabled}")
        print(f"MESHCORE_ENABLED: {meshcore_enabled}")
        
        # Determine mode
        if dual_mode and meshtastic_enabled and meshcore_enabled:
            print("  → Mode: DUAL (Meshtastic + MeshCore)")
        elif meshtastic_enabled and not meshcore_enabled:
            connection_mode = getattr(config, 'CONNECTION_MODE', 'serial')
            print(f"  → Mode: MESHTASTIC ({connection_mode})")
            
            if connection_mode == 'serial':
                serial_port = getattr(config, 'SERIAL_PORT', '/dev/ttyACM0')
                print(f"     Serial port: {serial_port}")
            elif connection_mode == 'tcp':
                tcp_host = getattr(config, 'TCP_HOST', '192.168.1.38')
                tcp_port = getattr(config, 'TCP_PORT', 4403)
                print(f"     TCP: {tcp_host}:{tcp_port}")
        elif meshcore_enabled and not meshtastic_enabled:
            print("  → Mode: MESHCORE COMPANION")
            meshcore_port = getattr(config, 'MESHCORE_SERIAL_PORT', '/dev/ttyUSB0')
            print(f"     MeshCore port: {meshcore_port}")
            
            # Check RX_LOG
            rx_log_enabled = getattr(config, 'MESHCORE_RX_LOG_ENABLED', True)
            print(f"     MESHCORE_RX_LOG_ENABLED: {rx_log_enabled}")
            if not rx_log_enabled:
                print("       ⚠️  RX_LOG disabled - only DMs will be received!")
                print("       💡 Set MESHCORE_RX_LOG_ENABLED = True for all packets")
        else:
            print("  ⚠️  Invalid configuration - no interface enabled!")
        
        print()
        return True
        
    except ImportError as e:
        print(f"❌ Failed to import config: {e}")
        return False

def check_serial_ports():
    """Check if serial ports are accessible"""
    print("=" * 80)
    print("SERIAL PORT CHECK")
    print("=" * 80)
    
    import subprocess
    
    # List all tty devices
    try:
        result = subprocess.run(['ls', '-la', '/dev/ttyACM*', '/dev/ttyUSB*'], 
                               capture_output=True, text=True)
        if result.returncode == 0:
            print("Available serial ports:")
            print(result.stdout)
        else:
            print("No /dev/ttyACM* or /dev/ttyUSB* devices found")
    except Exception as e:
        print(f"Failed to list serial ports: {e}")
    
    # Check if ports are in use
    try:
        import config
        serial_port = getattr(config, 'SERIAL_PORT', '/dev/ttyACM0')
        meshcore_port = getattr(config, 'MESHCORE_SERIAL_PORT', '/dev/ttyUSB0')
        
        for port in [serial_port, meshcore_port]:
            if not os.path.exists(port):
                print(f"  ⚠️  {port} does not exist")
                continue
            
            result = subprocess.run(['sudo', 'lsof', port], 
                                   capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                print(f"  ⚠️  {port} is in use:")
                print(result.stdout)
            else:
                print(f"  ✅ {port} is available")
    except Exception as e:
        print(f"Failed to check port usage: {e}")
    
    print()

def check_interface_status():
    """Check if bot interface is working"""
    print("=" * 80)
    print("INTERFACE STATUS CHECK")
    print("=" * 80)
    
    try:
        # Try to import and check main_bot
        from main_bot import MeshBot
        import config
        
        # Check if bot is running
        result = subprocess.run(['pgrep', '-f', 'main_script.py'], 
                               capture_output=True, text=True)
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            print(f"✅ Bot is running (PIDs: {', '.join(pids)})")
        else:
            print("⚠️  Bot is not running")
            print("   → Start with: python main_script.py")
        
        print()
        return True
        
    except Exception as e:
        print(f"❌ Failed to check interface: {e}")
        return False

def check_recent_logs():
    """Check recent systemd logs for errors"""
    print("=" * 80)
    print("RECENT LOG CHECK (last 50 lines)")
    print("=" * 80)
    
    import subprocess
    
    try:
        # Get last 50 lines of bot logs
        result = subprocess.run(['journalctl', '-u', 'meshtastic-bot', '-n', '50', '--no-pager'], 
                               capture_output=True, text=True)
        
        if result.returncode != 0:
            print("❌ Failed to read systemd logs")
            print("   Try: journalctl -u meshtastic-bot -n 100 --no-pager")
            return
        
        logs = result.stdout
        
        # Look for key messages
        key_phrases = [
            ("✅ Abonné aux messages", "Meshtastic subscription"),
            ("✅ Souscription à RX_LOG_DATA", "MeshCore RX_LOG subscription"),
            ("✅ Device connecté", "MeshCore connection"),
            ("🔔 on_message CALLED", "Message reception"),
            ("🔵 add_packet ENTRY", "Packet processing"),
            ("📦", "Packet logs (debug)"),
            ("❌", "Errors"),
            ("⚠️", "Warnings"),
        ]
        
        print("Looking for key indicators:")
        for phrase, description in key_phrases:
            count = logs.count(phrase)
            status = "✅" if count > 0 else "❌"
            print(f"  {status} {description}: {count} occurrences")
        
        # Show actual errors/warnings
        print("\nRecent errors and warnings:")
        for line in logs.split('\n')[-20:]:
            if '❌' in line or '⚠️' in line:
                print(f"  {line.strip()}")
        
        print()
        
    except Exception as e:
        print(f"❌ Failed to check logs: {e}")

def main():
    """Run all diagnostics"""
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "MESHBOT PACKET RECEPTION DIAGNOSTIC" + " " * 23 + "║")
    print("╚" + "═" * 78 + "╝")
    print()
    
    # Run checks
    check_config()
    check_serial_ports()
    check_interface_status()
    check_recent_logs()
    
    # Summary
    print("=" * 80)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 80)
    print()
    print("If you see NO packet logs (📦, 📡), check:")
    print("  1. DEBUG_MODE = True in config.py")
    print("  2. Interface is connected (✅ Abonné/Souscription messages)")
    print("  3. Serial port is accessible and not in use")
    print("  4. Device is powered on and transmitting")
    print("  5. If MeshCore: MESHCORE_RX_LOG_ENABLED = True")
    print()
    print("Common issues:")
    print("  • DEBUG_MODE = False → No debug logs appear")
    print("  • Serial port locked → Check with 'sudo lsof /dev/ttyACM0'")
    print("  • Device disconnected → Check USB cable and power")
    print("  • RX_LOG disabled → Only DMs appear, no broadcasts")
    print()
    print("Next steps:")
    print("  • Review recent logs: journalctl -u meshtastic-bot -f")
    print("  • Check startup logs: journalctl -u meshtastic-bot --since '5 minutes ago'")
    print("  • Enable debug: Set DEBUG_MODE = True and restart bot")
    print()

if __name__ == '__main__':
    import subprocess
    main()
