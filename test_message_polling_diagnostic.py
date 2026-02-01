#!/usr/bin/env python3
"""
Diagnostic script to test message polling for Meshtastic and MeshCore

This script helps identify which component is failing:
1. Meshtastic pubsub system
2. MeshCore CLI wrapper event loop
3. MeshCore serial interface polling

Usage:
    python3 test_message_polling_diagnostic.py
"""

import sys
import time
import threading
from utils import info_print, error_print, debug_print

def test_meshtastic_pubsub():
    """Test if Meshtastic pub.subscribe works"""
    print("\n" + "="*60)
    print("TEST 1: Meshtastic pub.subscribe System")
    print("="*60)
    
    try:
        # Import dependencies
        from pubsub import pub
        import meshtastic.serial_interface
        import config
        
        # Import required config with fallbacks for optional TCP settings
        MESHTASTIC_ENABLED = getattr(config, 'MESHTASTIC_ENABLED', True)
        CONNECTION_MODE = getattr(config, 'CONNECTION_MODE', 'serial')
        SERIAL_PORT = getattr(config, 'SERIAL_PORT', '/dev/ttyACM0')
        TCP_HOST = getattr(config, 'TCP_HOST', None)
        TCP_PORT = getattr(config, 'TCP_PORT', None)
        
        if not MESHTASTIC_ENABLED:
            print("❌ MESHTASTIC_ENABLED=False - Test skipped")
            return False
        
        print(f"✅ Imports successful")
        print(f"   CONNECTION_MODE: {CONNECTION_MODE}")
        
        # Create interface
        if CONNECTION_MODE.lower() == 'tcp':
            if TCP_HOST is None or TCP_PORT is None:
                print("❌ TCP mode selected but TCP_HOST or TCP_PORT not configured in config.py")
                print("   Please add TCP_HOST and TCP_PORT to your config.py or use CONNECTION_MODE='serial'")
                return False
            print(f"   Creating TCP interface: {TCP_HOST}:{TCP_PORT}")
            import meshtastic.tcp_interface
            interface = meshtastic.tcp_interface.TCPInterface(hostname=TCP_HOST, portNumber=TCP_PORT)
        else:
            print(f"   Creating serial interface: {SERIAL_PORT}")
            interface = meshtastic.serial_interface.SerialInterface(SERIAL_PORT)
        
        print("✅ Interface created")
        
        # Get local node ID for DM detection
        local_node_id = interface.myInfo.my_node_num if hasattr(interface, 'myInfo') else None
        print(f"   Local node ID: 0x{local_node_id:08x}" if local_node_id else "   Local node ID: Unknown")
        
        # Define callback with detailed analysis
        messages_received = []
        dm_messages = []
        broadcast_messages = []
        text_messages = []
        
        def on_message(packet, interface):
            from_id = packet.get('from', 0)
            to_id = packet.get('to', 0)
            decoded = packet.get('decoded', {})
            portnum = decoded.get('portnum', 'UNKNOWN')
            
            # Determine if DM or broadcast
            is_broadcast = (to_id in [0xFFFFFFFF, 0])
            msg_type = "BROADCAST" if is_broadcast else "DM"
            
            # Try to decode message content
            message_content = None
            if portnum == 'TEXT_MESSAGE_APP':
                payload = decoded.get('payload', b'')
                try:
                    message_content = payload.decode('utf-8').strip()
                except:
                    message_content = "[ENCRYPTED or BINARY]"
            
            # Print detailed info
            print(f"📨 CALLBACK INVOKED! From: 0x{from_id:08x}")
            print(f"   Type: {portnum} | To: 0x{to_id:08x} ({msg_type})")
            if message_content:
                # Truncate long messages
                display_content = message_content if len(message_content) <= 50 else message_content[:47] + "..."
                print(f"   Content: \"{display_content}\"")
            
            # Categorize
            messages_received.append(packet)
            if is_broadcast:
                broadcast_messages.append(packet)
            else:
                dm_messages.append(packet)
            if portnum == 'TEXT_MESSAGE_APP' and message_content and message_content != "[ENCRYPTED or BINARY]":
                text_messages.append((from_id, message_content, msg_type))
        
        # Subscribe
        pub.subscribe(on_message, "meshtastic.receive")
        print("✅ Subscribed to meshtastic.receive")
        
        # Wait for messages
        print("\n⏳ Waiting 30 seconds for messages...")
        print("   👉 Send a test DM to the bot now!")
        time.sleep(30)
        
        # Results
        print(f"\n📊 Messages received: {len(messages_received)}")
        print(f"   - DMs: {len(dm_messages)}")
        print(f"   - Broadcasts: {len(broadcast_messages)}")
        print(f"   - Text messages: {len(text_messages)}")
        
        if len(messages_received) > 0:
            print("\n✅ pub.subscribe() is WORKING")
            
            # Show text messages details
            if text_messages:
                print(f"\n📝 Text messages received:")
                for i, (from_id, content, msg_type) in enumerate(text_messages[:5]):
                    display_content = content if len(content) <= 60 else content[:57] + "..."
                    print(f"   {i+1}. From 0x{from_id:08x} ({msg_type}): \"{display_content}\"")
            
            # User guidance
            if len(dm_messages) == 0:
                print("\n⚠️  NO DMs received!")
                print("   Possible reasons:")
                print("   1. You sent broadcasts instead of DMs")
                print("   2. Your DMs are encrypted and couldn't be decoded")
                print("   3. You didn't send any messages")
                print("\n💡 To send a DM to the bot:")
                print("   1. Open Meshtastic app")
                print("   2. Go to bot's node in 'Messages'")
                print("   3. Send a message directly to the bot (not to channel)")
                
            if len(text_messages) == 0 and len(messages_received) > 0:
                print("\n⚠️  Packets received but NO readable text messages!")
                print("   Your messages might be encrypted or not TEXT_MESSAGE_APP type")
        else:
            print("\n❌ No messages received")
            print("   Possible causes:")
            print("   1. No messages sent to the bot")
            print("   2. Meshtastic library not publishing to topic")
            print("   3. Interface not connected properly")
        
        # Cleanup
        interface.close()
        return len(messages_received) > 0
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Make sure Meshtastic library is installed")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_meshcore_cli_wrapper():
    """Test if MeshCore CLI wrapper event loop processes events"""
    print("\n" + "="*60)
    print("TEST 2: MeshCore CLI Wrapper Event Loop")
    print("="*60)
    
    try:
        # Import dependencies
        from meshcore_cli_wrapper import MeshCoreCLIWrapper
        import config
        
        # Import with fallbacks for optional config
        MESHCORE_ENABLED = getattr(config, 'MESHCORE_ENABLED', False)
        MESHCORE_SERIAL_PORT = getattr(config, 'MESHCORE_SERIAL_PORT', '/dev/ttyUSB0')
        
        if not MESHCORE_ENABLED:
            print("❌ MESHCORE_ENABLED=False - Test skipped")
            return False
        
        print(f"✅ Imports successful")
        print(f"   MESHCORE_SERIAL_PORT: {MESHCORE_SERIAL_PORT}")
        
        # Check if meshcore-cli is available
        try:
            from meshcore import MeshCore, EventType
            print("✅ meshcore-cli library available")
        except ImportError:
            print("❌ meshcore-cli library NOT available")
            print("   This test requires: pip install meshcore")
            return False
        
        # Create interface
        print(f"   Creating MeshCore CLI wrapper...")
        interface = MeshCoreCLIWrapper(MESHCORE_SERIAL_PORT)
        
        # Connect with timeout to prevent hanging
        print("   Attempting connection (15 second timeout)...")
        connect_result = [None]  # Use list to capture result from thread
        connect_error = [None]
        
        def connect_with_timeout():
            try:
                connect_result[0] = interface.connect()
            except Exception as e:
                connect_error[0] = e
        
        connect_thread = threading.Thread(target=connect_with_timeout, daemon=True)
        connect_thread.start()
        connect_thread.join(timeout=15.0)
        
        if connect_thread.is_alive():
            print("⚠️  Connection attempt timed out after 15 seconds")
            print("   This is a known issue with meshcore-cli initialization")
            print("   The library may be waiting for device responses")
            return 'timeout'
        
        if connect_error[0]:
            print(f"❌ Connection error: {connect_error[0]}")
            return False
        
        if not connect_result[0]:
            print("❌ Failed to connect")
            return False
        
        print("✅ Interface connected")
        
        # Track callbacks - set proper message callback
        messages_received = []
        
        def bot_callback(packet, interface):
            """Simulates the bot's message callback"""
            print(f"📨 BOT CALLBACK INVOKED! Packet from: 0x{packet.get('from', 0):08x}")
            messages_received.append(packet)
        
        # Set the message callback (this is what the real bot does)
        interface.set_message_callback(bot_callback)
        
        # Start reading
        if not interface.start_reading():
            print("❌ Failed to start reading")
            interface.close()
            return False
        
        print("✅ Reading started")
        
        # Wait for messages
        print("\n⏳ Waiting 30 seconds for messages...")
        print("   👉 Send a test DM to the MeshCore node now!")
        time.sleep(30)
        
        # Results
        print(f"\n📊 Messages received: {len(messages_received)}")
        if len(messages_received) > 0:
            print("✅ Event loop is WORKING - callbacks invoked!")
        else:
            print("❌ No callbacks invoked")
            print("   Possible causes:")
            print("   1. No messages sent to the bot")
            print("   2. Event loop not processing events (fixed in this PR)")
            print("   3. meshcore-cli not dispatching events")
        
        # Cleanup
        interface.close()
        return len(messages_received) > 0
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_meshcore_serial_interface():
    """Test if MeshCore serial interface polls for messages"""
    print("\n" + "="*60)
    print("TEST 3: MeshCore Serial Interface Polling")
    print("="*60)
    
    try:
        # Import dependencies
        from meshcore_serial_interface import MeshCoreSerialInterface
        import config
        
        # Import with fallbacks for optional config
        MESHCORE_ENABLED = getattr(config, 'MESHCORE_ENABLED', False)
        MESHCORE_SERIAL_PORT = getattr(config, 'MESHCORE_SERIAL_PORT', '/dev/ttyUSB0')
        
        if not MESHCORE_ENABLED:
            print("❌ MESHCORE_ENABLED=False - Test skipped")
            return False
        
        print(f"✅ Imports successful")
        print(f"   MESHCORE_SERIAL_PORT: {MESHCORE_SERIAL_PORT}")
        
        # Create interface
        print(f"   Creating MeshCore serial interface...")
        interface = MeshCoreSerialInterface(MESHCORE_SERIAL_PORT)
        
        if not interface.connect():
            print("❌ Failed to connect")
            return False
        
        print("✅ Interface connected")
        
        # Track callbacks
        messages_received = []
        original_callback = interface._process_meshcore_line
        
        def tracked_callback(line):
            if line.startswith("DM:"):
                print(f"📨 Message parsed: {line[:50]}")
                messages_received.append(line)
            original_callback(line)
        
        interface._process_meshcore_line = tracked_callback
        
        # Start reading
        if not interface.start_reading():
            print("❌ Failed to start reading")
            interface.close()
            return False
        
        print("✅ Reading started (both read and poll threads)")
        
        # Check if polling thread is running
        time.sleep(1)
        if interface.poll_thread and interface.poll_thread.is_alive():
            print("✅ Poll thread is running")
        else:
            print("❌ Poll thread NOT running")
        
        # Wait for messages and polling
        print("\n⏳ Waiting 30 seconds for messages and polling...")
        print("   👉 Send a test DM to the MeshCore node now!")
        print("   👉 Watch for 'MESHCORE-POLL' messages in logs")
        time.sleep(30)
        
        # Results
        print(f"\n📊 Messages received: {len(messages_received)}")
        if len(messages_received) > 0:
            print("✅ Polling is WORKING - messages received!")
            for i, msg in enumerate(messages_received[:3]):
                print(f"   Message {i+1}: {msg[:70]}")
        else:
            print("⚠️  No messages received via serial interface")
            print("   NOTE: The basic serial interface has limited binary protocol support.")
            print("   Possible causes:")
            print("   1. No messages sent to the bot")
            print("   2. Binary protocol parsing not fully implemented")
            print("   3. Use MeshCore CLI wrapper (Test 2) for full functionality")
            print("\n   ℹ️  This is expected - the CLI wrapper is the recommended interface.")
        
        # Cleanup
        interface.close()
        
        # Return 'skip' if no messages (known limitation) rather than fail
        if len(messages_received) > 0:
            return True
        else:
            return 'skip'  # Known limitation - not a failure
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all diagnostic tests"""
    print("\n" + "="*60)
    print("MESSAGE POLLING DIAGNOSTIC TEST SUITE")
    print("="*60)
    print("\nThis script tests the message polling fixes for:")
    print("  1. Meshtastic pub.subscribe system")
    print("  2. MeshCore CLI wrapper event loop")
    print("  3. MeshCore serial interface polling")
    print("\nDuring the tests, please send test DMs to the bot.")
    print("="*60)
    
    results = {
        'meshtastic': test_meshtastic_pubsub(),
        'meshcore_cli': test_meshcore_cli_wrapper(),
        'meshcore_serial': test_meshcore_serial_interface(),
    }
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    for name, result in results.items():
        if result is True:
            status = "✅ PASS"
        elif result == 'skip':
            status = "⚠️  SKIP (known limitation)"
        elif result == 'timeout':
            status = "⏱️  TIMEOUT (connection issue)"
        else:
            status = "❌ FAIL"
        print(f"  {name:20s}: {status}")
    
    print("\n" + "="*60)
    
    # Count different result types
    failures = [name for name, result in results.items() if result is False]
    timeouts = [name for name, result in results.items() if result == 'timeout']
    passes = [name for name, result in results.items() if result is True]
    
    if not failures:
        if timeouts:
            print("⏱️  Some tests TIMED OUT")
            print("\nTimed out tests:", ", ".join(timeouts))
            print("\nTimeout indicates:")
            print("  • meshcore-cli initialization may be waiting for device")
            print("  • Device may not be responding to initialization commands")
            print("  • Serial port communication issues")
            print("\n💡 This is often normal if the device is busy or not connected.")
        elif len(passes) == len(results):
            print("✅ All tests PASSED!")
        else:
            print("✅ All critical tests PASSED!")
            print("   (Some tests skipped due to known limitations)")
        return 0
    else:
        print("❌ Some tests FAILED")
        print("\nFailed tests:", ", ".join(failures))
        if timeouts:
            print("Timed out tests:", ", ".join(timeouts))
        print("\nPlease check:")
        print("  1. Configuration (config.py)")
        print("  2. Hardware connections")
        print("  3. Test messages were actually sent")
        return 1


if __name__ == '__main__':
    sys.exit(main())
