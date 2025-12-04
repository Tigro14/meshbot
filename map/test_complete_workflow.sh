#!/bin/bash
# Complete workflow test: Database → Export → Verify mqttActive

set -e

echo "🧪 Complete MQTT Active Workflow Test"
echo "======================================="

# Create temporary test environment
TEST_DIR="/tmp/meshbot_workflow_$$"
mkdir -p "$TEST_DIR"

# Step 1: Create node_names.json
echo ""
echo "📝 Step 1: Creating node_names.json with sample nodes..."
cat > "$TEST_DIR/node_names.json" << 'NODES'
{
  "385503196": {
    "name": "Node Alpha",
    "lat": 47.2496,
    "lon": 6.0248,
    "alt": 350
  },
  "123456789": {
    "name": "Node Beta",
    "lat": 47.2181,
    "lon": -1.5528,
    "alt": 50
  },
  "987654321": {
    "name": "Node Gamma",
    "lat": 47.2300,
    "lon": -1.5600,
    "alt": 60
  }
}
NODES
echo "✅ Created 3 nodes in node_names.json"

# Step 2: Create database with NEIGHBORINFO data
echo ""
echo "📊 Step 2: Simulating NEIGHBORINFO packets in database..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_FILE="$TEST_DIR/traffic_history.db"

python3 << PYEOF
import sys
import time
sys.path.insert(0, '$SCRIPT_DIR/..')
from traffic_persistence import TrafficPersistence

# Initialize database
persistence = TrafficPersistence('$DB_FILE')
current_time = time.time()

# Node 385503196 sends NEIGHBORINFO (MQTT active)
persistence.save_neighbor_info('385503196', [{
    'node_id': '123456789',
    'snr': 8.5,
    'last_rx_time': current_time - 50,
    'node_broadcast_interval': 900
}, {
    'node_id': '987654321',
    'snr': 6.2,
    'last_rx_time': current_time - 100,
    'node_broadcast_interval': 900
}])

# Node 123456789 sends NEIGHBORINFO (MQTT active)
persistence.save_neighbor_info('123456789', [{
    'node_id': '385503196',
    'snr': 7.8,
    'last_rx_time': current_time - 75,
    'node_broadcast_interval': 900
}])

# Node 987654321 does NOT send NEIGHBORINFO (not MQTT active)

persistence.close()
print("✅ Saved NEIGHBORINFO data:")
print("   • Node 385503196: 2 neighbors → MQTT active")
print("   • Node 123456789: 1 neighbor  → MQTT active")
print("   • Node 987654321: 0 neighbors → NOT MQTT active")
PYEOF

# Step 3: Run export script
echo ""
echo "�� Step 3: Exporting nodes from database..."
OUTPUT_FILE="$TEST_DIR/info.json"
"$SCRIPT_DIR/export_nodes_from_db.py" "$TEST_DIR/node_names.json" "$DB_FILE" 48 > "$OUTPUT_FILE" 2>"$TEST_DIR/export.log"

if [ ! -f "$OUTPUT_FILE" ]; then
    echo "❌ FAIL: Export failed, no output file"
    cat "$TEST_DIR/export.log"
    exit 1
fi

echo "✅ Exported $(wc -c < "$OUTPUT_FILE") bytes to info.json"

# Step 4: Validate mqttActive flags
echo ""
echo "🔍 Step 4: Validating mqttActive flags..."
python3 << PYEOF
import json
import sys

with open('$OUTPUT_FILE') as f:
    data = json.load(f)

nodes = data['Nodes in mesh']

# Expected: Node Alpha and Beta are MQTT active, Gamma is not
expected = {
    '!16fa4fdc': ('Node Alpha', True),   # 385503196
    '!075bcd15': ('Node Beta', True),    # 123456789
    '!3ade68b1': ('Node Gamma', False)   # 987654321
}

all_ok = True
mqtt_count = 0

for node_id, (name, should_be_mqtt) in expected.items():
    if node_id not in nodes:
        print(f"❌ Node {node_id} ({name}) not found in output")
        all_ok = False
        continue
    
    node = nodes[node_id]
    is_mqtt = node.get('mqttActive', False)
    has_neighbors = 'neighbors' in node
    
    if should_be_mqtt:
        if is_mqtt and has_neighbors:
            print(f"✅ {name} ({node_id}): mqttActive=True, has {len(node['neighbors'])} neighbors")
            mqtt_count += 1
        else:
            print(f"❌ {name} ({node_id}): Expected MQTT active with neighbors")
            print(f"   Got: mqttActive={is_mqtt}, neighbors={has_neighbors}")
            all_ok = False
    else:
        if not is_mqtt and not has_neighbors:
            print(f"✅ {name} ({node_id}): mqttActive=False, no neighbors (correct)")
        elif is_mqtt:
            print(f"❌ {name} ({node_id}): Should NOT be MQTT active")
            all_ok = False

print(f"\n📊 Summary: {mqtt_count}/2 nodes correctly marked as MQTT active")

if not all_ok:
    sys.exit(1)
PYEOF

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Validation failed!"
    echo ""
    echo "Generated JSON:"
    cat "$OUTPUT_FILE"
    exit 1
fi

# Step 5: Show sample output
echo ""
echo "📄 Step 5: Sample mqttActive node from info.json:"
python3 << PYEOF
import json

with open('$OUTPUT_FILE') as f:
    data = json.load(f)

nodes = data['Nodes in mesh']
for node_id, node in nodes.items():
    if node.get('mqttActive'):
        print(f"\nNode ID: {node_id}")
        print(f"  Name: {node['user']['longName']}")
        print(f"  MQTT Active: {node.get('mqttActive')}")
        print(f"  Neighbors: {len(node.get('neighbors', []))}")
        if node.get('neighbors'):
            for nb in node['neighbors'][:2]:
                print(f"    • Neighbor: {nb['nodeId']}, SNR: {nb.get('snr')} dB")
        break
PYEOF

# Step 6: Verify visualization readiness
echo ""
echo "🎨 Step 6: Checking visualization compatibility..."
echo ""
echo "The following nodes will show yellow circles on map.html:"
python3 << PYEOF
import json

with open('$OUTPUT_FILE') as f:
    data = json.load(f)

nodes = data['Nodes in mesh']
mqtt_nodes = [(node_id, node['user']['longName']) for node_id, node in nodes.items() if node.get('mqttActive')]

for node_id, name in mqtt_nodes:
    print(f"  🟡 {name} ({node_id})")

print(f"\nTotal MQTT-active nodes: {len(mqtt_nodes)}")
PYEOF

# Cleanup
echo ""
echo "🧹 Cleaning up test files..."
rm -rf "$TEST_DIR"

echo ""
echo "✅✅✅ COMPLETE WORKFLOW TEST PASSED! ✅✅✅"
echo ""
echo "Summary:"
echo "  ✅ Node database created with neighbor data"
echo "  ✅ Export script correctly processed neighbors"
echo "  ✅ mqttActive flags set correctly based on NEIGHBORINFO"
echo "  ✅ Output JSON ready for map.html visualization"
echo ""
echo "Next steps for production:"
echo "  1. Run: ./map/infoup_db.sh"
echo "  2. Open: map.html in browser"
echo "  3. Verify: Yellow circles appear on MQTT-active nodes"
exit 0
