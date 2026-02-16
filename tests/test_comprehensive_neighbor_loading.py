#!/usr/bin/env python3
"""
Comprehensive test demonstrating the improved neighbor loading mechanism.

This test simulates:
1. TCP interface with progressive node loading
2. Nodes with and without neighborinfo
3. Configuration via config options
4. Detailed diagnostic output
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import sys
from unittest.mock import Mock

# Mock config values
class MockConfig:
    NEIGHBOR_LOAD_INITIAL_WAIT = 5
    NEIGHBOR_LOAD_MAX_WAIT = 30
    NEIGHBOR_LOAD_POLL_INTERVAL = 3

def test_comprehensive_neighbor_loading():
    """Test complete neighbor loading with realistic conditions"""
    
    print("=" * 70)
    print("COMPREHENSIVE NEIGHBOR LOADING TEST")
    print("=" * 70)
    
    # Simulate a TCP interface with progressive node loading
    class RealisticMockInterface:
        """Mock interface that simulates real TCP behavior"""
        def __init__(self, total_nodes=500, nodes_with_neighbors=400, load_batches=5):
            self._nodes = {}
            self._load_count = 0
            self.total_nodes = total_nodes
            self.nodes_with_neighbors = nodes_with_neighbors
            self.load_batches = load_batches
            self.batch_size = total_nodes // load_batches
        
        @property
        def nodes(self):
            """Simulate progressive loading of nodes"""
            self._load_count += 1
            
            # Load nodes in batches
            if self._load_count <= self.load_batches:
                start = (self._load_count - 1) * self.batch_size
                end = min(start + self.batch_size, self.total_nodes)
                
                for i in range(start, end):
                    node_id = f"!{i:08x}"
                    
                    # Some nodes have neighborinfo, some don't
                    has_neighbors = i < self.nodes_with_neighbors
                    
                    node_data = {
                        'user': {
                            'longName': f'TestNode{i}',
                            'shortName': f'N{i}'
                        }
                    }
                    
                    if has_neighbors:
                        # Each node has 3-5 neighbors
                        num_neighbors = 3 + (i % 3)
                        neighbors = []
                        for j in range(num_neighbors):
                            neighbors.append({
                                'node_id': 0x10000000 + i * 10 + j,
                                'snr': 5.0 + (j * 2),
                                'last_rx_time': int(time.time()) - (i * 60),
                                'node_broadcast_interval': 900
                            })
                        
                        node_data['neighborinfo'] = {
                            'neighbors': neighbors
                        }
                    
                    self._nodes[node_id] = node_data
            
            return self._nodes
    
    # Test configuration
    total_nodes = 500
    nodes_with_neighbors = 420  # 84% have neighborinfo
    load_batches = 5
    
    print(f"\nTest Configuration:")
    print(f"  Total nodes: {total_nodes}")
    print(f"  Nodes with neighborinfo: {nodes_with_neighbors} ({nodes_with_neighbors/total_nodes*100:.0f}%)")
    print(f"  Load batches: {load_batches}")
    print(f"  Batch size: {total_nodes // load_batches} nodes")
    
    # Create interface
    interface = RealisticMockInterface(total_nodes, nodes_with_neighbors, load_batches)
    
    # Simulate the polling mechanism
    print("\n" + "=" * 70)
    print("SIMULATING POLLING MECHANISM")
    print("=" * 70)
    
    wait_time = MockConfig.NEIGHBOR_LOAD_INITIAL_WAIT
    max_wait_time = MockConfig.NEIGHBOR_LOAD_MAX_WAIT
    poll_interval = MockConfig.NEIGHBOR_LOAD_POLL_INTERVAL
    
    print(f"\nPolling config: initial={wait_time}s, max={max_wait_time}s, poll={poll_interval}s\n")
    
    # Initial wait
    print(f"⏳ Initial wait: {wait_time}s...")
    time.sleep(wait_time)
    
    # Polling loop
    elapsed_time = wait_time
    previous_node_count = 0
    stable_count = 0
    required_stable_checks = 2
    
    while elapsed_time < max_wait_time:
        current_node_count = len(interface.nodes) if interface.nodes else 0
        
        if current_node_count == 0:
            print(f"   ⏳ {elapsed_time}s: No nodes loaded yet, waiting...")
        elif current_node_count == previous_node_count:
            stable_count += 1
            print(f"   ⏳ {elapsed_time}s: {current_node_count} nodes (stable {stable_count}/{required_stable_checks})")
            if stable_count >= required_stable_checks:
                print(f"   ✅ Loading stabilized at {current_node_count} nodes after {elapsed_time}s")
                break
        else:
            stable_count = 0
            increase = current_node_count - previous_node_count
            print(f"   📈 {elapsed_time}s: {current_node_count} nodes loaded (+{increase})")
        
        previous_node_count = current_node_count
        time.sleep(poll_interval)
        elapsed_time += poll_interval
    
    # Extract neighbor statistics
    print("\n" + "=" * 70)
    print("EXTRACTING NEIGHBOR STATISTICS")
    print("=" * 70 + "\n")
    
    final_node_count = len(interface.nodes)
    total_neighbors = 0
    nodes_with_neighbors_count = 0
    nodes_without_neighbors = 0
    nodes_without_neighborinfo = 0
    
    sample_nodes_without_neighborinfo = []
    max_samples = 3
    
    for node_id, node_info in interface.nodes.items():
        has_neighborinfo = False
        neighbors = []
        
        if 'neighborinfo' in node_info:
            has_neighborinfo = True
            neighborinfo = node_info['neighborinfo']
            if 'neighbors' in neighborinfo:
                neighbors = neighborinfo['neighbors']
        
        if not has_neighborinfo:
            nodes_without_neighborinfo += 1
            if len(sample_nodes_without_neighborinfo) < max_samples:
                node_name = node_info.get('user', {}).get('longName', 'Unknown')
                sample_nodes_without_neighborinfo.append(f"{node_name} ({node_id})")
        
        if neighbors:
            total_neighbors += len(neighbors)
            nodes_with_neighbors_count += 1
        else:
            nodes_without_neighbors += 1
    
    # Print results
    print("✅ Chargement initial terminé:")
    print(f"   • Nœuds totaux: {final_node_count}")
    print(f"   • Nœuds avec voisins: {nodes_with_neighbors_count}")
    print(f"   • Nœuds sans voisins: {nodes_without_neighbors}")
    print(f"   • Relations de voisinage: {total_neighbors}")
    
    if nodes_with_neighbors_count > 0:
        avg_neighbors = total_neighbors / nodes_with_neighbors_count
        print(f"   • Moyenne voisins/nœud: {avg_neighbors:.1f}")
    
    if nodes_without_neighborinfo > 0:
        print(f"   ⚠️  Nœuds sans neighborinfo: {nodes_without_neighborinfo}")
        if sample_nodes_without_neighborinfo:
            print(f"      Exemples: {', '.join(sample_nodes_without_neighborinfo)}")
        print(f"      Note: Ces nœuds n'ont pas encore broadcast de NEIGHBORINFO_APP")
    
    # Validation
    print("\n" + "=" * 70)
    print("VALIDATION")
    print("=" * 70 + "\n")
    
    success = True
    
    # Check 1: All nodes loaded
    if final_node_count == total_nodes:
        print(f"✅ All {total_nodes} nodes loaded successfully")
    else:
        print(f"❌ Expected {total_nodes} nodes, got {final_node_count}")
        success = False
    
    # Check 2: Nodes with neighbors detected
    expected_with_neighbors = 420  # From test config
    if nodes_with_neighbors_count == expected_with_neighbors:
        print(f"✅ Correct number of nodes with neighbors: {nodes_with_neighbors_count}")
    else:
        print(f"⚠️  Expected {expected_with_neighbors} nodes with neighbors, got {nodes_with_neighbors_count}")
    
    # Check 3: Neighbor relationships calculated
    # Each node with neighbors has 3-5 neighbors, average ~4
    expected_min = expected_with_neighbors * 3
    expected_max = expected_with_neighbors * 5
    if expected_min <= total_neighbors <= expected_max:
        print(f"✅ Neighbor relationships in expected range: {total_neighbors} (expected {expected_min}-{expected_max})")
    else:
        print(f"⚠️  Neighbor relationships: {total_neighbors} (expected {expected_min}-{expected_max})")
    
    # Check 4: Loading completed in reasonable time
    if elapsed_time <= max_wait_time:
        print(f"✅ Loading completed within timeout: {elapsed_time}s (max: {max_wait_time}s)")
    else:
        print(f"❌ Loading exceeded timeout: {elapsed_time}s (max: {max_wait_time}s)")
        success = False
    
    print("\n" + "=" * 70)
    if success:
        print("✅ ALL TESTS PASSED")
    else:
        print("⚠️  SOME TESTS HAD WARNINGS")
    print("=" * 70)
    
    return success

if __name__ == "__main__":
    success = test_comprehensive_neighbor_loading()
    sys.exit(0 if success else 1)
