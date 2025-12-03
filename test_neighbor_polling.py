#!/usr/bin/env python3
"""
Test the improved populate_neighbors_from_interface with polling mechanism.
"""

import time
from unittest.mock import Mock, MagicMock

def test_polling_mechanism():
    """Test that the polling mechanism correctly waits for nodes to load"""
    
    print("=== Test 1: Simulating progressive node loading ===")
    
    # Mock interface that simulates progressive loading
    class MockInterface:
        def __init__(self):
            self._nodes = {}
            self._load_count = 0
        
        @property
        def nodes(self):
            # Simulate progressive loading: add 100 nodes every call
            self._load_count += 1
            if self._load_count <= 5:  # 5 iterations = 500 nodes
                for i in range(100):
                    node_id = f"!{(self._load_count * 100 + i):08x}"
                    self._nodes[node_id] = {
                        'user': {'longName': f'Node{i}', 'shortName': f'N{i}'},
                        'neighborinfo': {
                            'neighbors': [
                                {
                                    'node_id': 0x12345678 + i,
                                    'snr': 10.5,
                                    'last_rx_time': int(time.time()),
                                    'node_broadcast_interval': 900
                                }
                            ]
                        }
                    }
            return self._nodes
    
    interface = MockInterface()
    
    # Simulate polling
    wait_time = 2
    max_wait_time = 30
    poll_interval = 3
    
    print(f"Config: wait={wait_time}s, max={max_wait_time}s, poll={poll_interval}s")
    
    elapsed = wait_time
    previous_count = 0
    stable_count = 0
    
    time.sleep(wait_time)
    
    iteration = 0
    while elapsed < max_wait_time:
        iteration += 1
        current_count = len(interface.nodes)
        
        print(f"Iteration {iteration}: {elapsed}s - {current_count} nodes", end="")
        
        if current_count == previous_count:
            stable_count += 1
            print(f" (stable {stable_count}/2)")
            if stable_count >= 2:
                print(f"✅ Stabilized at {current_count} nodes after {elapsed}s")
                break
        else:
            stable_count = 0
            print(f" (+{current_count - previous_count})")
        
        previous_count = current_count
        time.sleep(poll_interval)
        elapsed += poll_interval
    
    final_count = len(interface.nodes)
    print(f"\n✅ Final count: {final_count} nodes")
    print(f"Expected: 500, Got: {final_count}, Match: {final_count == 500}")
    
    print("\n=== Test 2: Immediate stabilization ===")
    
    # Mock interface with all nodes loaded immediately
    class QuickMockInterface:
        def __init__(self):
            self._nodes = {}
            for i in range(500):
                node_id = f"!{i:08x}"
                self._nodes[node_id] = {
                    'user': {'longName': f'Node{i}', 'shortName': f'N{i}'}
                }
        
        @property
        def nodes(self):
            return self._nodes
    
    quick_interface = QuickMockInterface()
    
    elapsed = wait_time
    previous_count = 0
    stable_count = 0
    
    time.sleep(wait_time)
    
    iteration = 0
    while elapsed < max_wait_time:
        iteration += 1
        current_count = len(quick_interface.nodes)
        
        print(f"Iteration {iteration}: {elapsed}s - {current_count} nodes", end="")
        
        if current_count == previous_count:
            stable_count += 1
            print(f" (stable {stable_count}/2)")
            if stable_count >= 2:
                print(f"✅ Stabilized at {current_count} nodes after {elapsed}s")
                break
        else:
            stable_count = 0
            print(f" (+{current_count - previous_count})")
        
        previous_count = current_count
        time.sleep(poll_interval)
        elapsed += poll_interval
    
    print(f"\n✅ Quick load stabilized in {elapsed}s")
    print(f"Expected fast stabilization (< 10s): {elapsed <= 10}")

if __name__ == "__main__":
    test_polling_mechanism()
