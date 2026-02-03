#!/usr/bin/env python3
"""
Debug script to understand why node names aren't being resolved
"""

print("="*60)
print("DEBUGGING NODE NAME LOOKUP")
print("="*60)

# Simulate the problem
node_id_decimal = 2415836690
node_id_hex = f"!{node_id_decimal:08x}"

print(f"\nNode ID (decimal): {node_id_decimal}")
print(f"Node ID (hex): {node_id_hex}")
print(f"Expected format: !8ffebe12")

# The issue is clear - the user's output shows:
# "Node-2415836690 (ID: !2415836690)"
# 
# This means:
# 1. get_node_name() is being called with the integer 2415836690
# 2. It's not finding it in node_names dict
# 3. It's not finding it in interface.nodes
# 4. It's falling back to f"Node-{node_id:08x}" = "Node-8ffebe12"
#
# BUT the output shows "Node-2415836690" which suggests it's using
# the DECIMAL format instead of hex!

# Let me check the fallback code
print("\n" + "="*60)
print("CHECKING FALLBACK BEHAVIOR")
print("="*60)

# If we look at node_manager.py line 182:
# return f"Node-{node_id:08x}"
#
# This should produce "Node-8ffebe12" for 2415836690
# But the user is seeing "Node-2415836690"
#
# This means the code is NOT reaching line 182!
# It must be hitting line 179 instead:
# if isinstance(node_id, str):
#     return node_id

print("\nHypothesis: node_id is being passed as a STRING")
print("Let's verify...")

test_id = "2415836690"  # String decimal
if isinstance(test_id, str):
    print(f"  ✅ String check passes")
    print(f"  Returns: {test_id}")
    print(f"  This matches the output: 'Node-2415836690'")

print("\n" + "="*60)
print("ROOT CAUSE FOUND")
print("="*60)
print("""
The problem is that node IDs from the DATABASE are stored as STRINGS,
not integers. When we do:

    from_id_db = link['from_id']  # This is a STRING like "2415836690"
    from_id = from_id_db
    
    if isinstance(from_id, str):
        from_id = int(from_id[1:], 16) if from_id.startswith('!') else int(from_id, 16)

The conversion on line 2530 is trying to parse it as HEX, but the database
stores DECIMAL strings! So int("2415836690", 16) will fail or give wrong result.

Let's test this:
""")

# Test the current conversion logic
from_id_db = "2415836690"  # What's in the database
print(f"Database value: '{from_id_db}'")

try:
    # Current code (line 2530)
    if from_id_db.startswith('!'):
        from_id = int(from_id_db[1:], 16)
    else:
        from_id = int(from_id_db, 16)  # This is WRONG for decimal strings!
    print(f"Current conversion: {from_id} (WRONG!)")
except ValueError as e:
    print(f"Conversion failed: {e}")

# Correct conversion
from_id_correct = int(from_id_db)  # Just convert to int, it's already decimal
print(f"Correct conversion: {from_id_correct}")
print(f"Hex format: !{from_id_correct:08x}")

print("\n" + "="*60)
print("SOLUTION")
print("="*60)
print("""
Fix the conversion logic in traffic_monitor.py around line 2530:

CURRENT (WRONG):
    if isinstance(from_id, str):
        from_id = int(from_id[1:], 16) if from_id.startswith('!') else int(from_id, 16)

CORRECT:
    if isinstance(from_id, str):
        if from_id.startswith('!'):
            from_id = int(from_id[1:], 16)
        else:
            from_id = int(from_id)  # Decimal string, not hex!
""")
