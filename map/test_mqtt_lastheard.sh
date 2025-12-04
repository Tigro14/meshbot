#!/bin/bash
# Test script for MQTT lastHeard timestamp feature
# Verifies that MQTT-only nodes get proper lastHeard timestamps

echo "🧪 Test MQTT LastHeard Timestamp Feature"
echo "=========================================="

# Create temporary test files
TEST_DIR="/tmp/meshbot_test_mqtt_lastheard_$$"
mkdir -p "$TEST_DIR"

# Create sample node_names.json
cat > "$TEST_DIR/node_names.json" << 'EOF'
{
  "385503196": {
    "name": "tigro G2 PV (Mesh+MQTT)",
    "lat": 47.2496,
    "lon": 6.0248,
    "alt": 350,
    "last_update": 1733175600.0
  },
  "123456789": {
    "name": "Node Alpha (MQTT Only)",
    "lat": 47.2181,
    "lon": -1.5528,
    "alt": 50,
    "last_update": 1733175500.0
  },
  "987654321": {
    "name": "Node Beta (No MQTT)",
    "lat": 47.2300,
    "lon": -1.5600,
    "alt": 60,
    "last_update": 1733175400.0
  }
}
EOF

echo "✅ Created sample node_names.json with 3 nodes"

# Create sample database
echo ""
echo "📊 Creating sample database..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_FILE="$TEST_DIR/traffic_history.db"

python3 << PYEOF
import sqlite3
import time
import sys

sys.path.insert(0, '$SCRIPT_DIR/..')
from traffic_persistence import TrafficPersistence

# Create database
persistence = TrafficPersistence('$DB_FILE')

current_time = time.time()

# Scenario 1: Node heard via MESH (has packets) AND MQTT (has neighbors)
# Expected: lastHeard from packets, mqttLastHeard from neighbors, mqttActive=True
print("Creating test data...")
print("  Scenario 1: Node 385503196 - MESH + MQTT")
persistence.conn.execute("""
    INSERT INTO packets (timestamp, from_id, to_id, packet_type, snr, hops)
    VALUES (?, ?, ?, ?, ?, ?)
""", (current_time - 100, '385503196', '4294967295', 'NODEINFO_APP', 8.5, 0))
persistence.conn.commit()

persistence.save_neighbor_info('385503196', [{
    'node_id': '123456789',
    'snr': 8.5,
    'last_rx_time': current_time - 50,
    'node_broadcast_interval': 900
}])

# Scenario 2: Node ONLY heard via MQTT (has neighbors, NO packets)
# Expected: lastHeard from MQTT timestamp (fallback), mqttLastHeard set, mqttActive=True
print("  Scenario 2: Node 123456789 - MQTT ONLY")
persistence.save_neighbor_info('123456789', [{
    'node_id': '987654321',
    'snr': 5.2,
    'last_rx_time': current_time - 200,
    'node_broadcast_interval': 900
}])

# Scenario 3: Node NOT heard via MQTT (NO neighbors, may have packets)
# Expected: No mqttActive, no mqttLastHeard
print("  Scenario 3: Node 987654321 - NO MQTT")

persistence.close()
print("✅ Database created")
PYEOF

# Run export script
echo ""
echo "📡 Running export_nodes_from_db.py..."
OUTPUT_FILE="$TEST_DIR/info.json"

"$SCRIPT_DIR/export_nodes_from_db.py" "$TEST_DIR/node_names.json" "$DB_FILE" 48 > "$OUTPUT_FILE" 2>"$TEST_DIR/export.log"

# Check if output file was created
if [ ! -f "$OUTPUT_FILE" ]; then
    echo "❌ FAIL: Output file not created"
    cat "$TEST_DIR/export.log"
    exit 1
fi

echo "✅ Output file created: $(wc -c < "$OUTPUT_FILE") bytes"

# Validate JSON syntax
echo ""
echo "🔍 Validating JSON syntax..."
if python3 -m json.tool "$OUTPUT_FILE" > /dev/null 2>&1; then
    echo "✅ JSON syntax is valid"
else
    echo "❌ FAIL: Invalid JSON"
    cat "$OUTPUT_FILE"
    exit 1
fi

# Validate MQTT lastHeard timestamps
echo ""
echo "🔍 Validating MQTT lastHeard timestamps..."
python3 << PYEOF
import json
import sys

with open('$OUTPUT_FILE') as f:
    data = json.load(f)

nodes = data['Nodes in mesh']

# Test cases
test_cases = [
    {
        'node_id': '!16fa4fdc',  # Node 385503196
        'name': 'tigro G2 PV',
        'expected_mqtt_active': True,
        'expected_lastheard': True,  # From packets
        'expected_mqtt_lastheard': True,  # From neighbors
        'scenario': 'MESH + MQTT'
    },
    {
        'node_id': '!075bcd15',  # Node 123456789
        'name': 'Node Alpha',
        'expected_mqtt_active': True,
        'expected_lastheard': True,  # FALLBACK from MQTT timestamp
        'expected_mqtt_lastheard': True,
        'scenario': 'MQTT ONLY (fallback)'
    },
    {
        'node_id': '!3ade68b1',  # Node 987654321
        'name': 'Node Beta',
        'expected_mqtt_active': False,
        'expected_lastheard': False,
        'expected_mqtt_lastheard': False,
        'scenario': 'NO MQTT'
    }
]

all_correct = True
mqtt_only_with_lastheard = 0

for test in test_cases:
    node_id = test['node_id']
    print(f"\n{'='*60}")
    print(f"Testing {test['name']} ({test['scenario']})")
    print(f"{'='*60}")
    
    if node_id not in nodes:
        print(f"❌ FAIL: Node {node_id} not found in output")
        all_correct = False
        continue
    
    node = nodes[node_id]
    
    # Check mqttActive flag
    is_mqtt_active = node.get('mqttActive', False)
    if is_mqtt_active == test['expected_mqtt_active']:
        print(f"✅ mqttActive: {is_mqtt_active} (expected: {test['expected_mqtt_active']})")
    else:
        print(f"❌ mqttActive: {is_mqtt_active} (expected: {test['expected_mqtt_active']})")
        all_correct = False
    
    # Check lastHeard field
    has_lastheard = 'lastHeard' in node
    if has_lastheard == test['expected_lastheard']:
        if has_lastheard:
            print(f"✅ lastHeard: {node['lastHeard']} (present)")
        else:
            print(f"✅ lastHeard: Not present (as expected)")
    else:
        print(f"❌ lastHeard: Present={has_lastheard} (expected: {test['expected_lastheard']})")
        all_correct = False
    
    # Check mqttLastHeard field
    has_mqtt_lastheard = 'mqttLastHeard' in node
    if has_mqtt_lastheard == test['expected_mqtt_lastheard']:
        if has_mqtt_lastheard:
            print(f"✅ mqttLastHeard: {node['mqttLastHeard']} (present)")
        else:
            print(f"✅ mqttLastHeard: Not present (as expected)")
    else:
        print(f"❌ mqttLastHeard: Present={has_mqtt_lastheard} (expected: {test['expected_mqtt_lastheard']})")
        all_correct = False
    
    # Special check: MQTT-only node with lastHeard
    if test['scenario'] == 'MQTT ONLY (fallback)' and has_lastheard:
        mqtt_only_with_lastheard += 1
        print(f"🎯 CRITICAL FIX VERIFIED: MQTT-only node has lastHeard timestamp!")
        print(f"   This prevents time-based filtering from hiding the node.")

print(f"\n{'='*60}")
print(f"SUMMARY")
print(f"{'='*60}")
print(f"✅ MQTT-only nodes with lastHeard (fallback): {mqtt_only_with_lastheard}")
print(f"   (These nodes will now appear on map with time filters!)")

if not all_correct:
    print("\n❌ Some tests failed")
    sys.exit(1)

if mqtt_only_with_lastheard == 0:
    print("\n❌ CRITICAL: No MQTT-only nodes got lastHeard timestamp!")
    print("   This means the fix is not working.")
    sys.exit(1)

print("\n✅ All validations passed!")
PYEOF

if [ $? -ne 0 ]; then
    echo "❌ FAIL: Validation failed"
    echo ""
    echo "Output JSON:"
    cat "$OUTPUT_FILE"
    exit 1
fi

# Show export logs
echo ""
echo "📋 Export logs:"
cat "$TEST_DIR/export.log"

# Cleanup
echo ""
echo "🧹 Cleaning up..."
rm -rf "$TEST_DIR"

echo ""
echo "✅ All tests passed! MQTT lastHeard timestamps are working correctly!"
echo "   • MQTT-only nodes now have lastHeard timestamps"
echo "   • They will not be filtered out by time-based filters"
echo "   • Yellow circles should now appear on map.html"
exit 0
