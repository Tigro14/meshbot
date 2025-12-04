#!/bin/bash
# Test script for MQTT-only nodes (nodes NOT in node_names.json)
# Verifies that MQTT-only nodes with position data from packets appear on the map

echo "🧪 Test MQTT-Only Nodes (Not in node_names.json)"
echo "=================================================="

# Create temporary test files
TEST_DIR="/tmp/meshbot_test_mqtt_only_$$"
mkdir -p "$TEST_DIR"

# Create sample node_names.json with ONLY 2 nodes (NOT including MQTT-only node)
cat > "$TEST_DIR/node_names.json" << 'EOF'
{
  "385503196": {
    "name": "tigro G2 PV",
    "lat": 47.2496,
    "lon": 6.0248,
    "alt": 350,
    "last_update": 1733175600.0
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

echo "✅ Created sample node_names.json with 2 nodes (MQTT-only node NOT included)"

# Create sample database with MQTT-only node
echo ""
echo "📊 Creating sample database with MQTT-only node..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_FILE="$TEST_DIR/traffic_history.db"

python3 << PYEOF
import sqlite3
import time
import sys
import json

sys.path.insert(0, '$SCRIPT_DIR/..')
from traffic_persistence import TrafficPersistence

# Create database
persistence = TrafficPersistence('$DB_FILE')

current_time = time.time()

# Node 123456789 (0x075bcd15) - MQTT-ONLY NODE
# This node is NOT in node_names.json but HAS:
# 1. Position data in packets table
# 2. NEIGHBORINFO data in neighbors table
print("Creating MQTT-only node data...")

# Add position packet for MQTT-only node
position_data = {
    'latitude': 47.2181,
    'longitude': -1.5528,
    'altitude': 50
}

persistence.conn.execute("""
    INSERT INTO packets (timestamp, from_id, to_id, packet_type, position, sender_name)
    VALUES (?, ?, ?, ?, ?, ?)
""", (current_time - 300, '123456789', '4294967295', 'POSITION_APP', 
      json.dumps(position_data), 'MQTT Only Node'))
persistence.conn.commit()

# Add NEIGHBORINFO for MQTT-only node (makes it MQTT-active)
persistence.save_neighbor_info('123456789', [{
    'node_id': '385503196',
    'snr': 7.5,
    'last_rx_time': current_time - 100,
    'node_broadcast_interval': 900
}])

# Also add normal node data for tigro
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

persistence.close()
print("✅ Database created with MQTT-only node")
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

# Validate MQTT-only node is in output
echo ""
echo "🔍 Validating MQTT-only node inclusion..."
python3 << PYEOF
import json
import sys

with open('$OUTPUT_FILE') as f:
    data = json.load(f)

nodes = data['Nodes in mesh']

# CRITICAL TEST: MQTT-only node should be in output
mqtt_only_node_id = '!075bcd15'  # Node 123456789

print(f"\n{'='*60}")
print(f"CRITICAL TEST: MQTT-Only Node Inclusion")
print(f"{'='*60}")

if mqtt_only_node_id not in nodes:
    print(f"❌ FAIL: MQTT-only node {mqtt_only_node_id} NOT found in output")
    print(f"   This node was NOT in node_names.json but had:")
    print(f"   • Position data in packets table")
    print(f"   • NEIGHBORINFO data (MQTT-active)")
    print(f"   It SHOULD appear in the output!")
    print(f"\nAvailable nodes: {list(nodes.keys())}")
    sys.exit(1)

print(f"✅ MQTT-only node {mqtt_only_node_id} found in output!")

node = nodes[mqtt_only_node_id]

# Verify required fields
required_fields = ['user', 'position', 'mqttActive', 'lastHeard']
missing_fields = [f for f in required_fields if f not in node]

if missing_fields:
    print(f"❌ FAIL: Missing fields: {missing_fields}")
    print(f"Node data: {json.dumps(node, indent=2)}")
    sys.exit(1)

# Verify position data
if 'latitude' not in node['position'] or 'longitude' not in node['position']:
    print(f"❌ FAIL: Missing position coordinates")
    sys.exit(1)

lat = node['position']['latitude']
lon = node['position']['longitude']
if abs(lat - 47.2181) > 0.001 or abs(lon - (-1.5528)) > 0.001:
    print(f"❌ FAIL: Position data incorrect")
    print(f"   Expected: (47.2181, -1.5528)")
    print(f"   Got: ({lat}, {lon})")
    sys.exit(1)

print(f"✅ Position data correct: ({lat}, {lon})")

# Verify MQTT active flag
if not node.get('mqttActive'):
    print(f"❌ FAIL: mqttActive flag not set")
    sys.exit(1)

print(f"✅ mqttActive flag set correctly")

# Verify lastHeard timestamp
if 'lastHeard' not in node:
    print(f"❌ FAIL: lastHeard timestamp missing")
    print(f"   Without lastHeard, node will be filtered out by time filters!")
    sys.exit(1)

print(f"✅ lastHeard timestamp present: {node['lastHeard']}")

# Verify name
user_name = node['user'].get('longName', '')
if 'MQTT Only Node' not in user_name:
    print(f"⚠️  WARNING: Name might be incorrect: {user_name}")
else:
    print(f"✅ Name correct: {user_name}")

print(f"\n{'='*60}")
print(f"SUCCESS: MQTT-only node exported correctly!")
print(f"{'='*60}")
print(f"This node will now appear on map.html with:")
print(f"  • Yellow MQTT-active circle")
print(f"  • Proper position on map")
print(f"  • Passes time-based filters (has lastHeard)")

PYEOF

if [ $? -ne 0 ]; then
    echo "❌ FAIL: Validation failed"
    echo ""
    echo "Output JSON:"
    cat "$OUTPUT_FILE"
    echo ""
    echo "Export logs:"
    cat "$TEST_DIR/export.log"
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
echo "✅✅✅ ALL TESTS PASSED! ✅✅✅"
echo ""
echo "MQTT-only nodes (not in node_names.json) are now:"
echo "  ✅ Exported to info.json"
echo "  ✅ Have position data from packets table"
echo "  ✅ Have lastHeard timestamp (MQTT fallback)"
echo "  ✅ Marked as mqttActive"
echo "  ✅ Will appear on map.html with yellow circles"
echo ""
exit 0
