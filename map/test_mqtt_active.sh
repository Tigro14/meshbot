#!/bin/bash
# Test script for MQTT active node visualization feature
# Tests export_nodes_from_db.py with mqttActive flag

echo "🧪 Test MQTT Active Node Feature"
echo "=================================="

# Create temporary test files
TEST_DIR="/tmp/meshbot_test_mqtt_$$"
mkdir -p "$TEST_DIR"

# Create sample node_names.json
cat > "$TEST_DIR/node_names.json" << 'EOF'
{
  "385503196": {
    "name": "tigro G2 PV",
    "lat": 47.2496,
    "lon": 6.0248,
    "alt": 350,
    "last_update": 1733175600.0
  },
  "123456789": {
    "name": "Test Node Alpha",
    "lat": 47.2181,
    "lon": -1.5528,
    "alt": 50,
    "last_update": 1733175500.0
  },
  "987654321": {
    "name": "Node Beta",
    "lat": 47.2300,
    "lon": -1.5600,
    "alt": 60,
    "last_update": 1733175400.0
  }
}
EOF

echo "✅ Created sample node_names.json with 3 nodes"

# Create sample database with neighbor data
echo ""
echo "📊 Creating sample database with MQTT neighbors..."

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

# Add neighbor relationships - simulating MQTT NEIGHBORINFO packets
# Node 385503196 sends NEIGHBORINFO (MQTT active)
persistence.save_neighbor_info('385503196', [{
    'node_id': '123456789',
    'snr': 8.5,
    'last_rx_time': current_time - 50,
    'node_broadcast_interval': 900
}])

# Node 123456789 sends NEIGHBORINFO (MQTT active)
persistence.save_neighbor_info('123456789', [{
    'node_id': '987654321',
    'snr': 4.2,
    'last_rx_time': current_time - 100,
    'node_broadcast_interval': 900
}])

# Node 987654321 does NOT send NEIGHBORINFO (not MQTT active)

persistence.close()
print("✅ Created sample database with MQTT neighbor data")
print("   • Node 385503196: MQTT active (has neighbors)")
print("   • Node 123456789: MQTT active (has neighbors)")
print("   • Node 987654321: NOT MQTT active (no neighbors)")
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

# Check for mqttActive field
echo ""
echo "🔍 Checking for mqttActive field..."
if grep -q '"mqttActive"' "$OUTPUT_FILE"; then
    echo "✅ mqttActive field present"
else
    echo "❌ FAIL: Missing mqttActive field"
    cat "$OUTPUT_FILE"
    exit 1
fi

# Validate mqttActive values
echo ""
echo "🔍 Validating mqttActive values..."
python3 << PYEOF
import json

with open('$OUTPUT_FILE') as f:
    data = json.load(f)

nodes = data['Nodes in mesh']

# Expected mqttActive values
expected_mqtt_active = {
    '!16fa4fdc': True,   # Node 385503196 - has neighbors
    '!075bcd15': True,   # Node 123456789 - has neighbors
    '!3ade68b1': False   # Node 987654321 - no neighbors
}

all_correct = True
mqtt_active_count = 0

for node_id, should_be_mqtt in expected_mqtt_active.items():
    if node_id in nodes:
        is_mqtt = nodes[node_id].get('mqttActive', False)
        if should_be_mqtt:
            if is_mqtt:
                print(f"✅ {node_id}: mqttActive=True (correct - has neighbors)")
                mqtt_active_count += 1
            else:
                print(f"❌ {node_id}: mqttActive=False, expected True (has neighbors)")
                all_correct = False
        else:
            if not is_mqtt:
                print(f"✅ {node_id}: mqttActive=False/absent (correct - no neighbors)")
            else:
                print(f"❌ {node_id}: mqttActive=True, expected False (no neighbors)")
                all_correct = False
    else:
        print(f"❌ Node {node_id} not found in output")
        all_correct = False

print(f"\n📊 MQTT Active Nodes: {mqtt_active_count}/3")

if not all_correct:
    import sys
    sys.exit(1)
PYEOF

if [ $? -ne 0 ]; then
    echo "❌ FAIL: Invalid mqttActive values"
    exit 1
fi

# Show sample output for mqttActive nodes
echo ""
echo "📄 Sample node with mqttActive flag:"
python3 << PYEOF
import json

with open('$OUTPUT_FILE') as f:
    data = json.load(f)

nodes = data['Nodes in mesh']
for node_id, node_data in nodes.items():
    if node_data.get('mqttActive'):
        print(f"\nNode: {node_id}")
        print(f"  Name: {node_data['user']['longName']}")
        print(f"  MQTT Active: {node_data.get('mqttActive')}")
        if 'neighbors' in node_data:
            print(f"  Neighbors: {len(node_data['neighbors'])}")
        break
PYEOF

# Show logs
echo ""
echo "📋 Export logs (last 20 lines):"
tail -20 "$TEST_DIR/export.log"

# Cleanup
echo ""
echo "🧹 Cleaning up..."
rm -rf "$TEST_DIR"

echo ""
echo "✅ All tests passed! mqttActive field is correctly set based on neighbor data!"
exit 0
