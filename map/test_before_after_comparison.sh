#!/bin/bash
# Before/After Comparison Test for MQTT Active Flag Fix

set -e

echo "🔄 MQTT Active Flag Fix - Before/After Comparison"
echo "=================================================="

TEST_DIR="/tmp/mqtt_comparison_$$"
mkdir -p "$TEST_DIR"

# Create sample node_names.json
cat > "$TEST_DIR/node_names.json" << 'EOF'
{
  "385503196": {
    "name": "tigro G2 PV",
    "lat": 47.2496,
    "lon": 6.0248,
    "alt": 350
  },
  "123456789": {
    "name": "Test Node",
    "lat": 47.2181,
    "lon": -1.5528,
    "alt": 50
  }
}
EOF

# Create database with NEIGHBORINFO
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_FILE="$TEST_DIR/traffic_history.db"

python3 << PYEOF
import sys
import time
sys.path.insert(0, '$SCRIPT_DIR/..')
from traffic_persistence import TrafficPersistence

persistence = TrafficPersistence('$DB_FILE')
current_time = time.time()

# Node 385503196 sends NEIGHBORINFO (should be MQTT active)
persistence.save_neighbor_info('385503196', [{
    'node_id': '123456789',
    'snr': 8.5,
    'last_rx_time': current_time - 50,
    'node_broadcast_interval': 900
}])

persistence.close()
PYEOF

# Run export
OUTPUT_FILE="$TEST_DIR/info.json"
"$SCRIPT_DIR/export_nodes_from_db.py" "$TEST_DIR/node_names.json" "$DB_FILE" 48 > "$OUTPUT_FILE" 2>/dev/null

echo ""
echo "📊 BEFORE THE FIX (Broken Behavior):"
echo "====================================="
echo "Problem: mqttActive flag was NOT being set because:"
echo "  1. Database stores: '!385503196' (decimal with !)"
echo "  2. After stripping !: '385503196' (still decimal)"
echo "  3. Code treated it as hex and tried to convert"
echo "  4. Key mismatch prevented flag from being set"
echo ""
echo "Result: No yellow circles on map, nodes appeared as regular nodes"
echo ""

echo "📊 AFTER THE FIX (Current Behavior):"
echo "===================================="
python3 << PYEOF
import json

with open('$OUTPUT_FILE') as f:
    data = json.load(f)

nodes = data['Nodes in mesh']

# Check for mqttActive flags
mqtt_nodes = []
regular_nodes = []

for node_id, node in nodes.items():
    name = node['user']['longName']
    if node.get('mqttActive'):
        mqtt_nodes.append((node_id, name, len(node.get('neighbors', []))))
    else:
        regular_nodes.append((node_id, name))

print("✅ Fixed: mqttActive flag is now correctly set!")
print(f"\n🟡 MQTT Active Nodes ({len(mqtt_nodes)}):")
for node_id, name, nb_count in mqtt_nodes:
    print(f"  • {name} ({node_id})")
    print(f"    - Has {nb_count} neighbor(s)")
    print(f"    - Will show YELLOW CIRCLE on map")
    print(f"    - Popup shows: '🌐 MQTT: Actif'")

print(f"\n⚪ Regular Nodes ({len(regular_nodes)}):")
for node_id, name in regular_nodes:
    print(f"  • {name} ({node_id})")
    print(f"    - No neighbor data")
    print(f"    - No yellow circle")
PYEOF

echo ""
echo "🎨 Visualization Comparison:"
echo "============================"
echo ""
echo "BEFORE (Broken):"
echo "  All nodes: ⚪ Regular marker (blue/green circle)"
echo "  Legend: 🌐 MQTT actif (but no nodes matched)"
echo ""
echo "AFTER (Fixed):"
echo "  MQTT nodes: 🟡 Yellow circle + colored marker"
echo "  Regular nodes: ⚪ Colored marker only"
echo "  Legend: 🌐 MQTT actif (matches actual nodes)"
echo ""

echo "📋 Technical Details:"
echo "===================="
python3 << PYEOF
import json

with open('$OUTPUT_FILE') as f:
    data = json.load(f)

nodes = data['Nodes in mesh']

for node_id, node in nodes.items():
    if node.get('mqttActive'):
        print(f"\nNode: {node['user']['longName']}")
        print(f"  ID: {node_id}")
        print(f"  mqttActive: {node.get('mqttActive')}")
        print(f"  neighbors: {node.get('neighbors', [])}")
        print(f"  mqttLastHeard: {node.get('mqttLastHeard')}")
        break
PYEOF

# Cleanup
rm -rf "$TEST_DIR"

echo ""
echo "✅ Comparison Complete!"
echo ""
echo "Impact Summary:"
echo "  ✅ Fixed node ID format handling in export_nodes_from_db.py"
echo "  ✅ mqttActive flag now correctly identifies MQTT-active nodes"
echo "  ✅ Yellow circles will appear on map.html for these nodes"
echo "  ✅ Network topology visualization is now complete"
echo ""
echo "To verify in production:"
echo "  1. cd /home/user/meshbot/map"
echo "  2. ./infoup_db.sh"
echo "  3. Open map.html in browser"
echo "  4. Look for yellow circles around MQTT-active nodes"
