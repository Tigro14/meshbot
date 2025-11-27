#!/usr/bin/env python3
"""
🔍 DIAGNOSTIC: TCP Connection Monitor
=====================================

Test script to monitor Meshtastic TCP connection stability.
Has two modes:
1. --raw: Raw socket (no protocol) - for baseline testing
2. --meshtastic (default): Uses Meshtastic library with proper protocol

PURPOSE:
    Determine if the 3-minute disconnection issue is:
    - In the Meshtastic protocol handling
    - In the bot codebase
    - External (router, network)

USAGE:
    # Using Meshtastic library (like CLI does) - DEFAULT
    python diag_tcp_connection.py 192.168.1.38

    # Using OptimizedTCPInterface (like bot does)
    python diag_tcp_connection.py 192.168.1.38 --optimized

    # Raw socket (no Meshtastic protocol)
    python diag_tcp_connection.py 192.168.1.38 --raw

    # Extended test (30 minutes)
    python diag_tcp_connection.py 192.168.1.38 --duration 1800

OUTPUT:
    Logs every packet received with timestamp, and reports when connection dies.
"""

import socket
import select
import time
import sys
import argparse
from datetime import datetime


def format_timestamp():
    """Return formatted timestamp like bot logs"""
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def format_bytes(data):
    """Format bytes for display"""
    if len(data) <= 20:
        return data.hex()
    return f"{data[:10].hex()}...({len(data)} bytes)"


def monitor_meshtastic_connection(host, port, duration_seconds):
    """
    Monitor using standard Meshtastic TCPInterface (like CLI does).
    This properly implements the Meshtastic protocol.
    """
    print(f"\n{'='*60}")
    print(f"🔍 Meshtastic TCPInterface Monitor - DIAGNOSTIC")
    print(f"{'='*60}")
    print(f"Target: {host}:{port}")
    print(f"Duration: {duration_seconds}s ({duration_seconds//60} minutes)")
    print(f"Mode: Standard meshtastic.TCPInterface (like CLI)")
    print(f"Started: {format_timestamp()}")
    print(f"{'='*60}\n")
    
    try:
        from meshtastic.tcp_interface import TCPInterface
    except ImportError:
        print("❌ meshtastic library not installed!")
        print("   pip install meshtastic")
        return
    
    packet_count = 0
    start_time = time.time()
    
    def on_receive(packet, interface):
        nonlocal packet_count
        packet_count += 1
        elapsed = time.time() - start_time
        from_id = packet.get('fromId', 'unknown')
        portnum = packet.get('decoded', {}).get('portnum', 'unknown')
        print(f"[{format_timestamp()}] 📦 Packet #{packet_count}: {portnum} from {from_id} | elapsed={elapsed:.0f}s")
    
    try:
        print(f"[{format_timestamp()}] 🔌 Connecting with TCPInterface...")
        interface = TCPInterface(hostname=host, portNumber=port)
        
        # Subscribe to receive packets
        from pubsub import pub
        pub.subscribe(on_receive, "meshtastic.receive")
        
        print(f"[{format_timestamp()}] ✅ Connected!")
        print(f"\n[{format_timestamp()}] 📡 Monitoring... (Ctrl+C to stop)\n")
        
        # Wait for duration
        while time.time() - start_time < duration_seconds:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print(f"\n[{format_timestamp()}] ⏹️ Stopped by user")
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n{'='*60}")
        print(f"[{format_timestamp()}] ❌ ERROR: {e}")
        print(f"    Elapsed time: {elapsed:.1f}s ({elapsed/60:.1f} minutes)")
        print(f"    Packets received: {packet_count}")
        print(f"{'='*60}")
    finally:
        try:
            pub.unsubscribe(on_receive, "meshtastic.receive")
        except:
            pass
        try:
            interface.close()
        except:
            pass
        
        # Summary
        elapsed = time.time() - start_time
        print(f"\n{'='*60}")
        print(f"📊 SUMMARY (TCPInterface)")
        print(f"{'='*60}")
        print(f"Duration: {elapsed:.1f}s ({elapsed/60:.1f} minutes)")
        print(f"Packets received: {packet_count}")
        print(f"{'='*60}")


def monitor_optimized_connection(host, port, duration_seconds):
    """
    Monitor using OptimizedTCPInterface (like bot does).
    This uses our CPU-optimized wrapper.
    """
    print(f"\n{'='*60}")
    print(f"🔍 OptimizedTCPInterface Monitor - DIAGNOSTIC")
    print(f"{'='*60}")
    print(f"Target: {host}:{port}")
    print(f"Duration: {duration_seconds}s ({duration_seconds//60} minutes)")
    print(f"Mode: OptimizedTCPInterface (like bot)")
    print(f"Started: {format_timestamp()}")
    print(f"{'='*60}\n")
    
    try:
        from tcp_interface_patch import OptimizedTCPInterface
    except ImportError:
        print("❌ tcp_interface_patch not found!")
        print("   Run from the bot directory")
        return
    
    packet_count = 0
    start_time = time.time()
    reconnection_count = 0
    
    def on_receive(packet, interface):
        nonlocal packet_count
        packet_count += 1
        elapsed = time.time() - start_time
        from_id = packet.get('fromId', 'unknown')
        portnum = packet.get('decoded', {}).get('portnum', 'unknown')
        print(f"[{format_timestamp()}] 📦 Packet #{packet_count}: {portnum} from {from_id} | elapsed={elapsed:.0f}s")
    
    def on_dead_socket():
        nonlocal reconnection_count
        reconnection_count += 1
        elapsed = time.time() - start_time
        print(f"\n[{format_timestamp()}] 🔌 SOCKET DEAD via callback (reconnection #{reconnection_count})")
        print(f"    Elapsed time: {elapsed:.1f}s ({elapsed/60:.1f} minutes)")
        print(f"    Packets so far: {packet_count}")
        print(f"    (Internal reconnection should occur automatically...)\n")
    
    try:
        print(f"[{format_timestamp()}] 🔌 Connecting with OptimizedTCPInterface...")
        interface = OptimizedTCPInterface(hostname=host, portNumber=port)
        interface.set_dead_socket_callback(on_dead_socket)
        
        # Subscribe to receive packets
        from pubsub import pub
        pub.subscribe(on_receive, "meshtastic.receive")
        
        print(f"[{format_timestamp()}] ✅ Connected!")
        print(f"\n[{format_timestamp()}] 📡 Monitoring... (Ctrl+C to stop)\n")
        
        # Wait for duration (reconnections happen automatically via internal reconnect)
        while time.time() - start_time < duration_seconds:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print(f"\n[{format_timestamp()}] ⏹️ Stopped by user")
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n{'='*60}")
        print(f"[{format_timestamp()}] ❌ ERROR: {e}")
        print(f"    Elapsed time: {elapsed:.1f}s ({elapsed/60:.1f} minutes)")
        print(f"    Packets received: {packet_count}")
        print(f"{'='*60}")
    finally:
        try:
            pub.unsubscribe(on_receive, "meshtastic.receive")
        except:
            pass
        try:
            interface.close()
        except:
            pass
        
        # Summary
        elapsed = time.time() - start_time
        print(f"\n{'='*60}")
        print(f"📊 SUMMARY (OptimizedTCPInterface)")
        print(f"{'='*60}")
        print(f"Duration: {elapsed:.1f}s ({elapsed/60:.1f} minutes)")
        print(f"Packets received: {packet_count}")
        print(f"Reconnections: {reconnection_count}")
        if reconnection_count > 0:
            print(f"Average time between reconnections: {elapsed/reconnection_count:.1f}s")
        print(f"{'='*60}")


def monitor_raw_connection(host, port, duration_seconds, keepalive=True):
    """
    Open a raw TCP connection and monitor for disconnection.
    NOTE: This doesn't implement Meshtastic protocol, so connection
    may be closed by node for being "idle/invalid".
    
    Args:
        host: Meshtastic node IP
        port: Meshtastic port (usually 4403)
        duration_seconds: How long to monitor
        keepalive: Whether to enable TCP keepalive
    """
    print(f"\n{'='*60}")
    print(f"🔍 Raw TCP Socket Monitor - DIAGNOSTIC")
    print(f"{'='*60}")
    print(f"Target: {host}:{port}")
    print(f"Duration: {duration_seconds}s ({duration_seconds//60} minutes)")
    print(f"Keepalive: {'enabled' if keepalive else 'disabled'}")
    print(f"Mode: Raw socket (NO Meshtastic protocol)")
    print(f"⚠️  NOTE: Node may close 'idle' connections without protocol!")
    print(f"Started: {format_timestamp()}")
    print(f"{'='*60}\n")
    
    # Create socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    # Configure socket
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    
    if keepalive:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        try:
            # Linux-specific keepalive options
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
            print(f"[{format_timestamp()}] ✅ TCP keepalive: idle=30s, interval=10s, count=3")
        except (AttributeError, OSError) as e:
            print(f"[{format_timestamp()}] ⚠️ Keepalive options not available: {e}")
    
    # Connect
    try:
        print(f"[{format_timestamp()}] 🔌 Connecting to {host}:{port}...")
        sock.connect((host, port))
        print(f"[{format_timestamp()}] ✅ Connected!")
    except Exception as e:
        print(f"[{format_timestamp()}] ❌ Connection failed: {e}")
        return
    
    # Set non-blocking for select()
    sock.setblocking(False)
    
    # Monitor loop
    start_time = time.time()
    last_data_time = time.time()
    packet_count = 0
    total_bytes = 0
    
    print(f"\n[{format_timestamp()}] 📡 Monitoring... (Ctrl+C to stop)\n")
    
    try:
        while time.time() - start_time < duration_seconds:
            # Wait for data (30 second timeout)
            ready, _, _ = select.select([sock], [], [], 30.0)
            
            if ready:
                try:
                    data = sock.recv(4096)
                    
                    if not data:
                        # Empty recv = connection closed by server
                        elapsed = time.time() - start_time
                        silence = time.time() - last_data_time
                        print(f"\n{'='*60}")
                        print(f"[{format_timestamp()}] 🔌 SOCKET DEAD: recv() returned empty")
                        print(f"    Connection closed by server (FIN/RST)")
                        print(f"    Elapsed time: {elapsed:.1f}s ({elapsed/60:.1f} minutes)")
                        print(f"    Silence before death: {silence:.1f}s")
                        print(f"    Packets received: {packet_count}")
                        print(f"    Total bytes: {total_bytes}")
                        print(f"{'='*60}")
                        return
                    
                    # Got data
                    packet_count += 1
                    total_bytes += len(data)
                    last_data_time = time.time()
                    
                    # Log packet
                    elapsed = time.time() - start_time
                    print(f"[{format_timestamp()}] 📦 Packet #{packet_count}: {len(data)} bytes | elapsed={elapsed:.0f}s")
                    
                except socket.error as e:
                    print(f"[{format_timestamp()}] ⚠️ Socket error: {e}")
                    return
            else:
                # Timeout - no data for 30 seconds
                silence = time.time() - last_data_time
                print(f"[{format_timestamp()}] ⏳ No data for 30s (total silence: {silence:.0f}s)")
                
    except KeyboardInterrupt:
        print(f"\n[{format_timestamp()}] ⏹️ Stopped by user")
    finally:
        # Summary
        elapsed = time.time() - start_time
        print(f"\n{'='*60}")
        print(f"📊 SUMMARY (Raw Socket)")
        print(f"{'='*60}")
        print(f"Duration: {elapsed:.1f}s ({elapsed/60:.1f} minutes)")
        print(f"Packets received: {packet_count}")
        print(f"Total bytes: {total_bytes}")
        print(f"Connection status: {'still alive' if packet_count > 0 else 'unknown'}")
        print(f"{'='*60}")
        
        sock.close()


def main():
    parser = argparse.ArgumentParser(
        description="Monitor TCP connection to a Meshtastic node"
    )
    parser.add_argument("host", help="Meshtastic node IP address (e.g., 192.168.1.38)")
    parser.add_argument("port", type=int, nargs="?", default=4403, help="Port (default: 4403)")
    parser.add_argument("--duration", "-d", type=int, default=600, 
                       help="Duration in seconds (default: 600 = 10 minutes)")
    
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--raw", action="store_true",
                           help="Use raw socket (no Meshtastic protocol)")
    mode_group.add_argument("--optimized", action="store_true",
                           help="Use OptimizedTCPInterface (like bot)")
    mode_group.add_argument("--meshtastic", action="store_true", default=True,
                           help="Use standard TCPInterface (like CLI) - DEFAULT")
    
    parser.add_argument("--no-keepalive", action="store_true",
                       help="Disable TCP keepalive (raw mode only)")
    
    args = parser.parse_args()
    
    if args.raw:
        monitor_raw_connection(
            args.host, 
            args.port, 
            args.duration,
            keepalive=not args.no_keepalive
        )
    elif args.optimized:
        monitor_optimized_connection(
            args.host,
            args.port,
            args.duration
        )
    else:
        # Default: meshtastic
        monitor_meshtastic_connection(
            args.host,
            args.port,
            args.duration
        )


if __name__ == "__main__":
    main()
