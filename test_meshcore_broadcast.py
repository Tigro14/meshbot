#!/usr/bin/env python3
"""
MeshCore Broadcast Command Test Script

This script tests various MeshCore text protocol commands to identify
the correct format for broadcasting messages on the public channel.

Usage:
    python test_meshcore_broadcast.py /dev/ttyACM1
    python test_meshcore_broadcast.py /dev/ttyACM1 --interactive
"""

import sys
import serial
import time
import argparse

def test_broadcast_commands(port, baudrate=115200):
    """Test various broadcast command formats"""
    
    print(f"\n{'='*60}")
    print(f"Testing MeshCore broadcast commands on {port}")
    print(f"{'='*60}\n")
    
    # Open serial port
    try:
        ser = serial.Serial(port, baudrate, timeout=1)
        print(f"✅ Serial port opened: {port} @ {baudrate}")
        time.sleep(1)  # Wait for port to stabilize
    except Exception as e:
        print(f"❌ Failed to open port: {e}")
        return
    
    # Test commands
    test_cases = [
        ("SEND_DM:ffffffff:TEST1\n", "SEND_DM with broadcast address"),
        ("BROADCAST:TEST2\n", "BROADCAST command"),
        ("SEND_BROADCAST:TEST3\n", "SEND_BROADCAST command"),
        ("SEND_PUBLIC:TEST4\n", "SEND_PUBLIC command"),
        ("SEND_CHANNEL:0:TEST5\n", "SEND_CHANNEL with channel 0"),
    ]
    
    for i, (command, description) in enumerate(test_cases, 1):
        print(f"\nTest {i}: {description}")
        print(f"  Command: '{command.strip()}'")
        
        try:
            # Send command
            ser.write(command.encode('utf-8'))
            ser.flush()
            bytes_written = len(command.encode('utf-8'))
            print(f"  ✅ Sent: {bytes_written} bytes")
            
            # Wait for response
            print(f"  ⏳ Waiting for response...")
            time.sleep(0.5)
            
            # Read response
            if ser.in_waiting > 0:
                response = ser.read(ser.in_waiting)
                print(f"  📨 Response: {response.hex()} ({len(response)} bytes)")
                
                # Decode response
                if response:
                    if response[0] == 0x3e:  # Radio->App marker
                        if len(response) >= 4:
                            cmd = response[3] if len(response) > 3 else 0
                            if cmd == 0x01:
                                print(f"  ❌ ERROR response from device")
                            elif cmd == 0x00:
                                print(f"  ✅ SUCCESS response from device")
                            else:
                                print(f"  ℹ️  Response code: 0x{cmd:02x}")
            else:
                print(f"  ℹ️  No response from device")
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
        
        time.sleep(1)  # Wait between tests
    
    # Close port
    ser.close()
    print(f"\n{'='*60}")
    print("Testing complete!")
    print(f"{'='*60}\n")

def interactive_mode(port, baudrate=115200):
    """Interactive mode for manual command testing"""
    
    print(f"\n{'='*60}")
    print(f"Interactive MeshCore Command Testing")
    print(f"Port: {port} @ {baudrate}")
    print(f"{'='*60}\n")
    print("Enter commands to send (or 'quit' to exit)")
    print("Example: SEND_DM:ffffffff:Hello World")
    print()
    
    # Open serial port
    try:
        ser = serial.Serial(port, baudrate, timeout=1)
        print(f"✅ Serial port opened\n")
        time.sleep(1)
    except Exception as e:
        print(f"❌ Failed to open port: {e}")
        return
    
    try:
        while True:
            # Get command from user
            cmd = input("Command> ")
            
            if cmd.lower() in ['quit', 'exit', 'q']:
                break
            
            if not cmd:
                continue
            
            # Add newline if not present
            if not cmd.endswith('\n'):
                cmd += '\n'
            
            try:
                # Send command
                ser.write(cmd.encode('utf-8'))
                ser.flush()
                print(f"  ✅ Sent: {len(cmd)} bytes")
                
                # Wait for response
                time.sleep(0.5)
                
                # Read response
                if ser.in_waiting > 0:
                    response = ser.read(ser.in_waiting)
                    print(f"  📨 Response: {response.hex()} ({len(response)} bytes)")
                else:
                    print(f"  ℹ️  No response")
                    
            except Exception as e:
                print(f"  ❌ Error: {e}")
            
            print()
            
    finally:
        ser.close()
        print("\n✅ Serial port closed")

def main():
    parser = argparse.ArgumentParser(
        description='Test MeshCore broadcast commands'
    )
    parser.add_argument(
        'port',
        help='Serial port (e.g., /dev/ttyACM1)'
    )
    parser.add_argument(
        '--baudrate',
        type=int,
        default=115200,
        help='Baud rate (default: 115200)'
    )
    parser.add_argument(
        '--interactive',
        action='store_true',
        help='Run in interactive mode'
    )
    
    args = parser.parse_args()
    
    if args.interactive:
        interactive_mode(args.port, args.baudrate)
    else:
        test_broadcast_commands(args.port, args.baudrate)

if __name__ == '__main__':
    main()
