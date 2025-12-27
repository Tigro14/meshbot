#!/usr/bin/env python3
"""
Enhanced diagnostic for /keys discrepancy

This script helps diagnose why /keys reports "sans clés" when periodic sync
shows keys are present in interface.nodes.

Run this during production to see the actual state.
"""

print("="*70)
print("DIAGNOSTIC: /keys Discrepancy Analysis")
print("="*70)
print()

print("This diagnostic helps understand why:")
print("  • Periodic sync logs show: 'Key already present and matches'")
print("  • But /keys reports: '155 sans clés'")
print()

print("Possible causes:")
print()

print("1. TIMING ISSUE")
print("   • Periodic sync ran AFTER /keys was executed")
print("   • Solution: Run /keys again after seeing sync logs")
print()

print("2. DIFFERENT INTERFACE OBJECTS")
print("   • Periodic sync modifies one interface.nodes")
print("   • /keys command checks a different interface.nodes")
print("   • This would be a serious bug")
print()

print("3. NODE ID FORMAT MISMATCH")
print("   • Nodes stored in interface.nodes with one format (e.g., '!abc123')")
print("   • /keys searches with different formats (e.g., 0xabc123)")
print("   • The code tries multiple formats, but maybe misses some")
print()

print("4. NODES IN TRAFFIC BUT NOT IN NODEINFO")
print("   • Some nodes send regular packets (appear in traffic)")
print("   • But never send NODEINFO (no entry in node_names.json)")
print("   • These nodes legitimately have no keys available")
print()

print("5. INTERFACE.NODES GETS CLEARED")
print("   • Something clears interface.nodes between sync and /keys")
print("   • Very unlikely, but possible")
print()

print("="*70)
print("WHAT TO CHECK:")
print("="*70)
print()

print("A. Immediately after seeing 'Key already present' logs, run /keys")
print("   → If still shows 'sans clés', it's not a timing issue")
print()

print("B. Check if DEBUG_MODE is enabled:")
print("   → Logs will show: '[DEBUG] 🔑 Created interface.nodes entry'")
print("   → Or: '[DEBUG] 🔑 Immediately synced key'")
print()

print("C. Check the count:")
print("   → If sync logs show ~50 nodes with keys")
print("   → But /keys shows '155 sans clés'")
print("   → That means 105 nodes never sent NODEINFO (expected)")
print()

print("D. Look for this specific pattern:")
print("   Periodic sync logs:")
print("     [INFO] Processing Node-A: has key in DB")
print("     [INFO]    Found in interface.nodes with key: !abc123")
print("     [INFO]    ℹ️ Key already present and matches")
print()
print("   Then immediately run /keys and check output:")
print("     If it says 'Node-A: ❌ Sans clé' → BUG")
print("     If it doesn't mention Node-A → Node-A not in traffic")
print()

print("="*70)
print("TO FIX:")
print("="*70)
print()

print("If it's cause #4 (nodes in traffic but no NODEINFO):")
print("   → This is NORMAL behavior")
print("   → /keys correctly reports these as 'sans clés'")
print("   → They will get keys when they broadcast NODEINFO")
print()

print("If it's cause #1 (timing):")
print("   → Just wait for periodic sync (every 5 min)")
print("   → Or restart bot (sync runs at startup)")
print()

print("If it's cause #2 or #5 (interface object issues):")
print("   → This is a BUG that needs code fix")
print("   → Need to investigate why interface.nodes is different/cleared")
print()

print("="*70)
print("NEXT STEPS FOR USER:")
print("="*70)
print()

print("1. Wait for next periodic sync logs (every 5 minutes)")
print("2. When you see logs like:")
print("   [INFO] Processing CHATO PCS1 (0xdb295204): has key in DB")
print("   [INFO]    ℹ️ Key already present and matches")
print()
print("3. IMMEDIATELY run /keys command")
print()
print("4. Share BOTH outputs:")
print("   • The sync logs")
print("   • The FULL /keys output (not just summary)")
print()
print("5. This will help determine if it's timing or a real bug")
print()

print("="*70)
