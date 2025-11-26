#!/usr/bin/env python3
"""
🔍 DIAGNOSTIC: TCP Connection Monitor
=====================================

Simple test script to monitor a raw TCP connection to a Meshtastic node.
This script does NOT use any bot code - only raw socket operations.

PURPOSE:
    Determine if the 3-minute disconnection issue is:
    - External (Meshtastic node, router, network)
    - Or caused by something in the bot codebase

USAGE:
    python diag_tcp_connection.py 192.168.1.38 4403

    # With custom timeout (default: 600s = 10 minutes)
    python diag_tcp_connection.py 192.168.1.38 4403 --duration 1800

OUTPUT:
    Logs every packet received with timestamp, and reports when connection dies.
    If connection dies after ~3 minutes consistently, the issue is EXTERNAL.
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


def monitor_tcp_connection(host, port, duration_seconds, keepalive=True):
    """
    Open a raw TCP connection and monitor for disconnection.
    
    Args:
        host: Meshtastic node IP
        port: Meshtastic port (usually 4403)
        duration_seconds: How long to monitor
        keepalive: Whether to enable TCP keepalive
    """
    print(f"\n{'='*60}")
    print(f"🔍 TCP Connection Monitor - DIAGNOSTIC")
    print(f"{'='*60}")
    print(f"Target: {host}:{port}")
    print(f"Duration: {duration_seconds}s ({duration_seconds//60} minutes)")
    print(f"Keepalive: {'enabled' if keepalive else 'disabled'}")
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
        print(f"📊 SUMMARY")
        print(f"{'='*60}")
        print(f"Duration: {elapsed:.1f}s ({elapsed/60:.1f} minutes)")
        print(f"Packets received: {packet_count}")
        print(f"Total bytes: {total_bytes}")
        print(f"Connection status: {'still alive' if packet_count > 0 else 'unknown'}")
        print(f"{'='*60}")
        
        sock.close()


def main():
    parser = argparse.ArgumentParser(
        description="Monitor a raw TCP connection to a Meshtastic node"
    )
    parser.add_argument("host", help="Meshtastic node IP address (e.g., 192.168.1.38)")
    parser.add_argument("port", type=int, nargs="?", default=4403, help="Port (default: 4403)")
    parser.add_argument("--duration", "-d", type=int, default=600, 
                       help="Duration in seconds (default: 600 = 10 minutes)")
    parser.add_argument("--no-keepalive", action="store_true",
                       help="Disable TCP keepalive")
    
    args = parser.parse_args()
    
    monitor_tcp_connection(
        args.host, 
        args.port, 
        args.duration,
        keepalive=not args.no_keepalive
    )


if __name__ == "__main__":
    main()
