#!/usr/bin/env python3
"""
Test to simulate the Telegram /keys a76f40d flow
"""

class MockNodeManager:
    def __init__(self):
        # Simulate nodes in database
        self.node_names = {
            0xa76f40da: {'name': 'tigro t1000E'},
            305419896: {'name': 'TestNode'},
        }

class MockInterface:
    def __init__(self):
        # Simulate interface.nodes with different key formats
        # Let's test with the STRING format which is common
        self.nodes = {
            str(0xa76f40da): {  # "2809086170" - string key
                'user': {
                    'id': f"!{0xa76f40da:08x}",
                    'longName': 'tigro t1000E',
                    'shortName': 'tigro',
                    'publicKey': 'test_key_data=='
                }
            }
        }

def simulate_find_node(search_term, node_manager):
    """Simulate _find_node logic"""
    target_search = search_term.strip().lower()
    target_search = target_search.lstrip('!')
    target_search = target_search.rstrip(')')
    
    matching_nodes = []
    exact_matches = []
    
    if node_manager and hasattr(node_manager, 'node_names'):
        for node_id, node_data in node_manager.node_names.items():
            node_name = node_data.get('name', '').lower()
            node_id_hex = f"{node_id:x}".lower()
            node_id_hex_padded = f"{node_id:08x}".lower()
            
            # Check exact match
            if target_search == node_name or target_search == node_id_hex or target_search == node_id_hex_padded:
                result = node_data.copy()
                result['id'] = node_id
                exact_matches.append(result)
                print(f"  ✓ EXACT match: node_id={node_id:08x}")
            # Partial match
            elif target_search in node_name or target_search in node_id_hex or target_search in node_id_hex_padded:
                result = node_data.copy()
                result['id'] = node_id
                matching_nodes.append(result)
                print(f"  ✓ PARTIAL match: node_id={node_id:08x}")
    
    if len(exact_matches) == 1:
        return exact_matches[0]
    elif len(exact_matches) == 0 and len(matching_nodes) == 1:
        return matching_nodes[0]
    elif len(exact_matches) > 1 or len(matching_nodes) > 1:
        all_matches = exact_matches if exact_matches else matching_nodes
        return all_matches[0]
    
    return None

def simulate_check_node_keys(search_term, interface, node_manager):
    """Simulate _check_node_keys logic"""
    print(f"\n1️⃣ Finding node: '{search_term}'")
    target_node = simulate_find_node(search_term, node_manager)
    
    if not target_node:
        return f"❌ Nœud '{search_term}' introuvable"
    
    node_name = target_node.get('name', 'Unknown')
    node_id = target_node.get('id')
    
    print(f"2️⃣ Found node: {node_name} (id={node_id:08x})")
    
    if not node_id:
        return f"❌ ID du nœud '{node_name}' introuvable"
    
    if not interface or not hasattr(interface, 'nodes'):
        return "⚠️ Interface non disponible"
    
    # Multi-format search (THE FIX)
    nodes = interface.nodes
    node_info = None
    search_keys = [node_id, str(node_id), f"!{node_id:08x}", f"{node_id:08x}"]
    
    print(f"3️⃣ Trying keys in interface.nodes:")
    print(f"   Available keys in interface.nodes: {list(nodes.keys())}")
    print(f"   Search keys to try: {search_keys}")
    
    for key in search_keys:
        print(f"   Trying key={key} (type={type(key).__name__})...", end='')
        if key in nodes:
            node_info = nodes[key]
            print(f" ✅ FOUND")
            break
        else:
            print(f" ❌")
    
    if node_info is None:
        return f"⚠️ {node_name}: Pas de NODEINFO reçu"
    
    # Check for public key
    user_info = node_info.get('user', {})
    public_key = user_info.get('public_key') or user_info.get('publicKey')
    
    if public_key:
        return f"✅ {node_name}: Clé OK ({public_key[:8]}...)"
    else:
        return f"❌ {node_name}: Pas de clé publique"

# Run the test
print("="*70)
print("SIMULATION: /keys a76f40d on Telegram")
print("="*70)

node_manager = MockNodeManager()
interface = MockInterface()

result = simulate_check_node_keys("a76f40d", interface, node_manager)

print(f"\n4️⃣ RESULT:")
print(f"   {result}")
print()
print("="*70)
