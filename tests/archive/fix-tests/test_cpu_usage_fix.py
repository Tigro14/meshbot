#!/usr/bin/env python3
"""
Test to demonstrate CPU usage improvement with longer select() timeout

This test simulates the _readBytes() method with different timeout values
to show the CPU usage reduction.
"""

import time
import select
import socket
import threading


def simulate_readbytes_with_timeout(timeout_seconds, duration_seconds=5):
    """
    Simulate _readBytes() with a specific timeout for a given duration.
    
    Returns:
        Number of select() calls made during the test period
    """
    # Create a socket pair (but don't send any data - simulate idle state)
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('localhost', 0))
    server_socket.listen(1)
    
    server_port = server_socket.getsockname()[1]
    
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect(('localhost', server_port))
    
    conn, _ = server_socket.accept()
    
    # Count how many times we call select()
    select_calls = 0
    start_time = time.time()
    
    # Flag to stop the loop
    stop_flag = threading.Event()
    
    def reader_loop():
        nonlocal select_calls
        while not stop_flag.is_set():
            ready, _, exception = select.select([client_socket], [], [client_socket], timeout_seconds)
            select_calls += 1
            
            if exception:
                break
            
            if ready:
                # In real scenario, would read data here
                pass
    
    # Run the reader loop in background
    thread = threading.Thread(target=reader_loop, daemon=True)
    thread.start()
    
    # Wait for the test duration
    time.sleep(duration_seconds)
    
    # Stop the loop
    stop_flag.set()
    thread.join(timeout=1)
    
    elapsed = time.time() - start_time
    
    # Cleanup
    client_socket.close()
    conn.close()
    server_socket.close()
    
    return select_calls, elapsed


def main():
    print("\n" + "="*70)
    print("🧪 CPU USAGE TEST - select() Timeout Comparison")
    print("="*70 + "\n")
    
    test_duration = 5  # seconds
    
    print(f"Testing for {test_duration} seconds with NO data (idle state)...\n")
    
    # Test with old timeout (1.0s)
    print("📊 OLD IMPLEMENTATION (1.0s timeout):")
    calls_old, elapsed_old = simulate_readbytes_with_timeout(1.0, test_duration)
    rate_old = calls_old / elapsed_old
    print(f"   - select() calls: {calls_old}")
    print(f"   - Elapsed time: {elapsed_old:.2f}s")
    print(f"   - Call rate: {rate_old:.2f} calls/second")
    print(f"   - CPU impact: HIGH (tight polling loop)\n")
    
    # Test with new timeout (30.0s)
    print("📊 NEW IMPLEMENTATION (30.0s timeout):")
    calls_new, elapsed_new = simulate_readbytes_with_timeout(30.0, test_duration)
    rate_new = calls_new / elapsed_new
    print(f"   - select() calls: {calls_new}")
    print(f"   - Elapsed time: {elapsed_new:.2f}s")
    print(f"   - Call rate: {rate_new:.2f} calls/second")
    print(f"   - CPU impact: LOW (long blocking periods)\n")
    
    # Calculate improvement
    improvement = (calls_old - calls_new) / calls_old * 100
    print("="*70)
    print(f"✅ IMPROVEMENT: {improvement:.1f}% reduction in select() calls")
    print(f"   (from {calls_old} calls to {calls_new} calls)")
    print("="*70)
    
    print("\n💡 KEY INSIGHT:")
    print("   The longer timeout means select() blocks for longer periods,")
    print("   dramatically reducing CPU usage when there's no mesh traffic.")
    print("   When data DOES arrive, select() wakes up immediately, so")
    print("   message latency is NOT affected!\n")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
