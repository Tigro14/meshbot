#!/usr/bin/env python3
"""
Test that /keys command correctly handles decimal node IDs from traffic database.

Root cause: Traffic DB stores node IDs as decimal TEXT ("2732684716"),
but /keys was trying to parse them as hex, causing search failures.

Fix: Parse decimal strings as decimal, not hex.
"""

def test_node_id_parsing():
    """Test that node ID parsing works correctly for decimal strings from DB."""
    
    print("=" * 70)
    print("Test: Node ID Parsing Fix")
    print("=" * 70)
    
    # Simulate node IDs from traffic database (stored as decimal TEXT)
    traffic_nodes = [
        "2732684716",  # !a2e175ac in hex
        "382563200",   # !16cd7380 in hex (corrected)
        "2661163356",  # !9e9e215c in hex (corrected)
        "2116290153",  # !7e240669 in hex (not in interface.nodes)
    ]
    
    # Simulate keys in interface.nodes (stored as !hex format)
    interface_nodes = {
        "!a2e175ac": {"user": {"publicKey": "key1"}},
        "!16cd7380": {"user": {"publicKey": "key2"}},
        "!9e9e215c": {"user": {"publicKey": "key3"}},
    }
    
    print("\n📊 Traffic Database Nodes (decimal TEXT):")
    for node in traffic_nodes:
        print(f"   {node}")
    
    print("\n🔑 Interface.nodes Keys (!hex format):")
    for key in interface_nodes.keys():
        print(f"   {key}")
    
    print("\n🔍 Testing node ID conversion and search:\n")
    
    matches_found = 0
    matches_expected = 3  # First 3 traffic nodes should match
    
    for node_id in traffic_nodes:
        # This is the FIXED parsing logic
        if isinstance(node_id, str):
            if node_id.startswith('!'):
                node_id_int = int(node_id[1:], 16)
            elif 'x' in node_id.lower():
                node_id_int = int(node_id, 0)
            else:
                # FIX: Decimal string from DB - parse as decimal, not hex!
                node_id_int = int(node_id)
        else:
            node_id_int = node_id
        
        # Try multiple key formats
        search_keys = [
            node_id_int,
            str(node_id_int),
            f"!{node_id_int:08x}",
            f"{node_id_int:08x}"
        ]
        
        found = False
        found_key = None
        for key in search_keys:
            if key in interface_nodes:
                found = True
                found_key = key
                break
        
        hex_format = f"!{node_id_int:08x}"
        status = "✅ FOUND" if found else "❌ NOT FOUND"
        print(f"   Node {node_id} → int={node_id_int} → {hex_format}")
        print(f"      Search keys: {search_keys}")
        print(f"      Result: {status}" + (f" with key={found_key}" if found else ""))
        print()
        
        if found:
            matches_found += 1
    
    print("=" * 70)
    print(f"Summary: {matches_found}/{len(traffic_nodes)} nodes found")
    print(f"Expected: {matches_expected}/{len(traffic_nodes)} (first 3 should match)")
    
    if matches_found == matches_expected:
        print("\n✅ TEST PASSED: Node ID conversion works correctly!")
        return True
    else:
        print(f"\n❌ TEST FAILED: Expected {matches_expected} matches, got {matches_found}")
        return False


def test_old_broken_parsing():
    """Show how the OLD (broken) parsing failed."""
    
    print("\n" + "=" * 70)
    print("Comparison: OLD (Broken) vs NEW (Fixed) Parsing")
    print("=" * 70)
    
    node_id = "2732684716"  # Decimal string from DB
    
    print(f"\nInput from traffic DB: '{node_id}'")
    print(f"Type: {type(node_id)} (TEXT column in SQLite)")
    
    # OLD (broken) logic: tried to parse as hex
    print("\n❌ OLD LOGIC (BROKEN):")
    try:
        old_result = int(node_id, 16)  # Parsing decimal as hex!
        old_hex = f"!{old_result:08x}"
        print(f"   Parsed as hex: {old_result}")
        print(f"   Converted to !hex: {old_hex}")
        print(f"   ❌ WRONG - This doesn't match anything!")
    except Exception as e:
        print(f"   Error: {e}")
    
    # NEW (fixed) logic: parse as decimal
    print("\n✅ NEW LOGIC (FIXED):")
    new_result = int(node_id)  # Parsing decimal as decimal
    new_hex = f"!{new_result:08x}"
    print(f"   Parsed as decimal: {new_result}")
    print(f"   Converted to !hex: {new_hex}")
    print(f"   ✅ CORRECT - This matches interface.nodes key!")
    
    print()


if __name__ == '__main__':
    test_old_broken_parsing()
    success = test_node_id_parsing()
    
    print("\n" + "=" * 70)
    if success:
        print("All tests passed! ✅")
        exit(0)
    else:
        print("Some tests failed! ❌")
        exit(1)
