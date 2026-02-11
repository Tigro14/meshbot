#!/usr/bin/env python3
"""
Demo: How to Send Messages on Public Channel via MeshCore

This script demonstrates the correct way to send broadcast messages
on the public default channel using MeshCore.

Usage:
    python3 demo_send_public_channel.py [message]

Example:
    python3 demo_send_public_channel.py "Hello mesh network!"
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from meshcore_serial_interface import MeshCoreSerialInterface
from utils import info_print, debug_print, error_print
import time


def demo_send_to_public_channel():
    """Demonstrate sending a message to the public channel"""
    
    print("=" * 80)
    print("DEMO: Send Message on Public Channel via MeshCore")
    print("=" * 80)
    print()
    
    # Get message from command line or use default
    if len(sys.argv) > 1:
        message = " ".join(sys.argv[1:])
    else:
        message = "Test broadcast from MeshBot demo script"
    
    print(f"📝 Message to send: '{message}'")
    print()
    
    # Step 1: Create interface
    print("Step 1: Create MeshCoreSerialInterface")
    print("-" * 80)
    
    # Note: Update this to your actual serial port
    serial_port = "/dev/ttyUSB0"  # Common for USB devices
    # Alternative ports: /dev/ttyACM0, /dev/ttyUSB1, etc.
    
    print(f"  Port: {serial_port}")
    print(f"  Baudrate: 115200")
    print()
    
    try:
        interface = MeshCoreSerialInterface(port=serial_port, baudrate=115200)
        print("✅ Interface created successfully")
    except Exception as e:
        error_print(f"❌ Failed to create interface: {e}")
        print()
        print("💡 TIP: Make sure the serial port is correct.")
        print("   Common ports: /dev/ttyUSB0, /dev/ttyACM0")
        print("   List ports: ls -la /dev/tty{USB,ACM}*")
        return False
    
    print()
    
    # Step 2: Connect
    print("Step 2: Connect to MeshCore device")
    print("-" * 80)
    
    try:
        if not interface.connect():
            error_print("❌ Failed to connect to MeshCore device")
            return False
        print("✅ Connected successfully")
    except Exception as e:
        error_print(f"❌ Connection error: {e}")
        return False
    
    print()
    
    # Step 3: Send to public channel
    print("Step 3: Send broadcast on public channel")
    print("-" * 80)
    
    print("  Calling sendText() with:")
    print(f"    message: '{message}'")
    print(f"    destinationId: 0xFFFFFFFF (broadcast)")
    print(f"    channelIndex: 0 (public channel)")
    print()
    
    try:
        result = interface.sendText(
            message=message,
            destinationId=0xFFFFFFFF,  # Broadcast address
            channelIndex=0             # Public channel (default)
        )
        
        if result:
            print("✅ Message sent successfully!")
            print()
            print("📡 Binary packet sent with:")
            print("   - Start marker: 0x3C ('<')")
            print("   - Command: CMD_SEND_CHANNEL_TXT_MSG (0x03)")
            print("   - Channel: 0 (public)")
            print(f"   - Message length: {len(message)} characters")
        else:
            error_print("❌ Failed to send message")
            return False
            
    except Exception as e:
        error_print(f"❌ Send error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print()
    
    # Step 4: Cleanup
    print("Step 4: Disconnect")
    print("-" * 80)
    interface.disconnect()
    print("✅ Disconnected")
    print()
    
    return True


def show_interface_comparison():
    """Show comparison between different interfaces"""
    
    print()
    print("=" * 80)
    print("INTERFACE COMPARISON")
    print("=" * 80)
    print()
    
    print("┌" + "─" * 78 + "┐")
    print("│ Interface                  │ Broadcast │ Channel │ Notes              │")
    print("├" + "─" * 78 + "┤")
    print("│ MeshCoreSerialInterface    │    ✅     │   ✅    │ Binary protocol    │")
    print("│ MeshCoreCLIWrapper         │    ❌     │   ❌    │ DM only            │")
    print("│ Meshtastic                 │    ✅     │   ✅    │ Standard behavior  │")
    print("└" + "─" * 78 + "┘")
    print()
    
    print("Key Points:")
    print("  • MeshCoreSerialInterface = BEST for broadcasts")
    print("  • MeshCoreCLIWrapper = Only for direct messages")
    print("  • Use destinationId=0xFFFFFFFF for broadcast")
    print("  • Use channelIndex=0 for public channel")
    print()


def show_code_example():
    """Show code example"""
    
    print()
    print("=" * 80)
    print("CODE EXAMPLE")
    print("=" * 80)
    print()
    
    example_code = """
# Import the interface
from meshcore_serial_interface import MeshCoreSerialInterface

# Create and connect
interface = MeshCoreSerialInterface('/dev/ttyUSB0', 115200)
interface.connect()

# Send to public channel (broadcast)
interface.sendText(
    message="Hello mesh network!",
    destinationId=0xFFFFFFFF,  # Broadcast
    channelIndex=0             # Public channel
)

# Send direct message to specific node
interface.sendText(
    message="Private message",
    destinationId=0x12345678,  # Specific node
    channelIndex=0             # Ignored for DMs
)

# Cleanup
interface.disconnect()
"""
    
    print(example_code)
    print()


def main():
    """Main entry point"""
    
    print()
    
    # Show interface comparison
    show_interface_comparison()
    
    # Show code example
    show_code_example()
    
    # Run demo
    print("=" * 80)
    print("RUNNING DEMO")
    print("=" * 80)
    print()
    
    success = demo_send_to_public_channel()
    
    print()
    print("=" * 80)
    if success:
        print("✅ DEMO COMPLETED SUCCESSFULLY")
    else:
        print("❌ DEMO FAILED")
    print("=" * 80)
    print()
    
    if not success:
        print("Troubleshooting:")
        print("  1. Check serial port: ls -la /dev/tty{USB,ACM}*")
        print("  2. Check permissions: sudo usermod -aG dialout $USER")
        print("  3. Check device connection")
        print("  4. Try different serial port")
        print()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
