#!/usr/bin/env python3
"""
Test script to explore meshcore library API for broadcast support.

This script investigates the meshcore library to find the correct way
to send broadcasts on the public channel.
"""

import sys
import time

def test_meshcore_library():
    """Test meshcore library API to find broadcast support."""
    try:
        import meshcore
        print("✅ meshcore library imported successfully")
        print(f"   Version: {meshcore.__version__ if hasattr(meshcore, '__version__') else 'unknown'}")
        print()
    except ImportError as e:
        print(f"❌ Cannot import meshcore library: {e}")
        print("   Install with: pip install meshcore")
        return False
    
    # List all available modules/classes
    print("=" * 60)
    print("Available meshcore modules:")
    print("=" * 60)
    for attr in dir(meshcore):
        if not attr.startswith('_'):
            obj = getattr(meshcore, attr)
            print(f"  - {attr}: {type(obj).__name__}")
    print()
    
    # Check commands module
    if hasattr(meshcore, 'commands'):
        print("=" * 60)
        print("meshcore.commands methods:")
        print("=" * 60)
        for attr in dir(meshcore.commands):
            if not attr.startswith('_'):
                obj = getattr(meshcore.commands, attr)
                if callable(obj):
                    print(f"  - {attr}()")
                    # Try to get docstring
                    if obj.__doc__:
                        doc_lines = obj.__doc__.strip().split('\n')
                        print(f"      {doc_lines[0]}")
        print()
        
        # Explore MessagingCommands class in detail
        if hasattr(meshcore.commands, 'MessagingCommands'):
            print("=" * 60)
            print("MessagingCommands class methods:")
            print("=" * 60)
            try:
                msg_cmd = meshcore.commands.MessagingCommands
                for attr in dir(msg_cmd):
                    if not attr.startswith('_'):
                        obj = getattr(msg_cmd, attr)
                        if callable(obj):
                            print(f"  - {attr}()")
                            # Try to get signature
                            try:
                                import inspect
                                sig = inspect.signature(obj)
                                print(f"      Signature: {sig}")
                            except:
                                pass
            except Exception as e:
                print(f"  Error exploring MessagingCommands: {e}")
            print()
    
    # Check for broadcast-related methods
    print("=" * 60)
    print("Searching for broadcast-related methods:")
    print("=" * 60)
    
    broadcast_keywords = ['broadcast', 'public', 'channel', 'send']
    found_methods = []
    
    for module_name in dir(meshcore):
        if module_name.startswith('_'):
            continue
        module = getattr(meshcore, module_name)
        if hasattr(module, '__dict__'):
            for attr in dir(module):
                if any(keyword in attr.lower() for keyword in broadcast_keywords):
                    if not attr.startswith('_'):
                        found_methods.append(f"{module_name}.{attr}")
    
    if found_methods:
        for method in found_methods:
            print(f"  ✓ {method}")
    else:
        print("  ℹ️  No obvious broadcast methods found")
    print()
    
    # Explore EventType enum
    if hasattr(meshcore, 'EventType'):
        print("=" * 60)
        print("EventType enum values:")
        print("=" * 60)
        try:
            for event in meshcore.EventType:
                print(f"  - {event.name}: {event.value}")
                if 'CHANNEL' in event.name:
                    print(f"      ⭐ CHANNEL-RELATED EVENT!")
        except Exception as e:
            print(f"  Error exploring EventType: {e}")
        print()
    
    # Check send_msg signature
    if hasattr(meshcore, 'commands') and hasattr(meshcore.commands, 'send_msg'):
        print("=" * 60)
        print("send_msg() signature:")
        print("=" * 60)
        import inspect
        try:
            sig = inspect.signature(meshcore.commands.send_msg)
            print(f"  send_msg{sig}")
            
            # Get docstring
            if meshcore.commands.send_msg.__doc__:
                print("\n  Documentation:")
                for line in meshcore.commands.send_msg.__doc__.strip().split('\n'):
                    print(f"    {line}")
        except Exception as e:
            print(f"  Error getting signature: {e}")
        print()
    
    # Check if there's a Connection class or similar
    if hasattr(meshcore, 'Connection'):
        print("=" * 60)
        print("meshcore.Connection methods:")
        print("=" * 60)
        for attr in dir(meshcore.Connection):
            if not attr.startswith('_'):
                obj = getattr(meshcore.Connection, attr)
                if callable(obj):
                    print(f"  - {attr}()")
        print()
    
    return True

def test_meshcore_instance(port='/dev/ttyACM2'):
    """Test creating a meshcore connection instance."""
    try:
        import meshcore
        
        print("=" * 60)
        print(f"Testing meshcore connection to {port}")
        print("=" * 60)
        
        # Try to create a connection
        print("Creating connection...")
        conn = meshcore.SerialConnection(port, baudrate=115200)
        print("✅ Connection created")
        
        # Check available methods on the instance
        print("\nConnection instance methods:")
        for attr in dir(conn):
            if not attr.startswith('_'):
                obj = getattr(conn, attr)
                if callable(obj):
                    print(f"  - {attr}()")
        
        # Check for send-related methods
        print("\nSend-related methods:")
        for attr in dir(conn):
            if 'send' in attr.lower() and not attr.startswith('_'):
                print(f"  ✓ {attr}()")
        
        # Clean up
        if hasattr(conn, 'close'):
            conn.close()
            print("\n✅ Connection closed")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    port = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyACM2'
    
    print("MeshCore Library API Explorer")
    print("=" * 60)
    print()
    
    # Test 1: Explore library API
    if not test_meshcore_library():
        sys.exit(1)
    
    # Test 2: Create connection instance
    print("\n" + "=" * 60)
    test_meshcore_instance(port)
    
    print("\n" + "=" * 60)
    print("Exploration complete!")
    print("=" * 60)
