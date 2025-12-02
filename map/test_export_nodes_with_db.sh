#!/bin/bash
# Enhanced test script for export_nodes_from_db.py with database
# Creates sample data including database with hops and neighbors

echo "🧪 Test export_nodes_from_db.py with Database"
echo "=============================================="

# Create temporary test files
TEST_DIR="/tmp/meshbot_test_db_$$"
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
    "name": "Node Without GPS",
    "lat": null,
    "lon": null,
    "alt": null,
    "last_update": null
  }
}
EOF

echo "✅ Created sample node_names.json with 3 nodes"

# Create sample database with hops and neighbors
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

# Add sample packets with hops
current_time = time.time()

# Node 385503196 - direct (0 hops)
cursor = persistence.conn.cursor()
cursor.execute("""
    INSERT INTO packets (timestamp, from_id, to_id, source, packet_type, hops, snr)
    VALUES (?, ?, ?, ?, ?, ?, ?)
""", (current_time - 100, '385503196', 'broadcast', 'local', 'NODEINFO_APP', 0, 9.5))

# Node 123456789 - 1 hop
cursor.execute("""
    INSERT INTO packets (timestamp, from_id, to_id, source, packet_type, hops, snr)
    VALUES (?, ?, ?, ?, ?, ?, ?)
""", (current_time - 200, '123456789', 'broadcast', 'local', 'NODEINFO_APP', 1, 5.2))

# Node 987654321 - 2 hops
cursor.execute("""
    INSERT INTO packets (timestamp, from_id, to_id, source, packet_type, hops, snr)
    VALUES (?, ?, ?, ?, ?, ?, ?)
""", (current_time - 300, '987654321', 'broadcast', 'local', 'NODEINFO_APP', 2, 3.1))

persistence.conn.commit()

# Add neighbor relationships
# Node 385503196 has neighbor 123456789
persistence.save_neighbor_info('385503196', [{
    'node_id': '123456789',
    'snr': 8.5,
    'last_rx_time': current_time - 50,
    'node_broadcast_interval': 900
}])

# Node 123456789 has neighbor 987654321
persistence.save_neighbor_info('123456789', [{
    'node_id': '987654321',
    'snr': 4.2,
    'last_rx_time': current_time - 100,
    'node_broadcast_interval': 900
}])

persistence.close()
print("✅ Created sample database with hops and neighbors")
PYEOF

# Run export script
echo ""
echo "📡 Running export_nodes_from_db.py with database..."
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

# Check for hopsAway field
echo ""
echo "🔍 Checking for hopsAway field..."
if grep -q '"hopsAway"' "$OUTPUT_FILE"; then
    echo "✅ hopsAway field present"
    # Count nodes with hopsAway
    HOPS_COUNT=$(python3 -c "import json; data = json.load(open('$OUTPUT_FILE')); print(sum(1 for n in data['Nodes in mesh'].values() if 'hopsAway' in n))")
    echo "   • Nodes with hopsAway: $HOPS_COUNT/3"
else
    echo "❌ FAIL: Missing hopsAway field"
    exit 1
fi

# Check for neighbors field
echo ""
echo "🔍 Checking for neighbors field..."
if grep -q '"neighbors"' "$OUTPUT_FILE"; then
    echo "✅ neighbors field present"
    # Count nodes with neighbors
    NEIGHBORS_COUNT=$(python3 -c "import json; data = json.load(open('$OUTPUT_FILE')); print(sum(1 for n in data['Nodes in mesh'].values() if 'neighbors' in n))")
    echo "   • Nodes with neighbors: $NEIGHBORS_COUNT/3"
else
    echo "❌ FAIL: Missing neighbors field"
    exit 1
fi

# Validate hopsAway values
echo ""
echo "🔍 Validating hopsAway values..."
python3 << PYEOF
import json

with open('$OUTPUT_FILE') as f:
    data = json.load(f)

nodes = data['Nodes in mesh']

# Expected hopsAway values
expected = {
    '!16fa4fdc': 0,  # Node 385503196
    '!075bcd15': 1,  # Node 123456789
    '!3ade68b1': 2   # Node 987654321
}

all_correct = True
for node_id, expected_hops in expected.items():
    if node_id in nodes:
        actual_hops = nodes[node_id].get('hopsAway')
        if actual_hops == expected_hops:
            print(f"✅ {node_id}: hopsAway={actual_hops} (correct)")
        else:
            print(f"❌ {node_id}: hopsAway={actual_hops}, expected {expected_hops}")
            all_correct = False
    else:
        print(f"❌ Node {node_id} not found in output")
        all_correct = False

if not all_correct:
    import sys
    sys.exit(1)
PYEOF

if [ $? -ne 0 ]; then
    echo "❌ FAIL: Invalid hopsAway values"
    exit 1
fi

# Show sample output
echo ""
echo "📄 Full JSON output:"
cat "$OUTPUT_FILE"

# Show logs
echo ""
echo "📋 Export logs:"
cat "$TEST_DIR/export.log"

# Cleanup
echo ""
echo "🧹 Cleaning up..."
rm -rf "$TEST_DIR"

echo ""
echo "✅ All tests passed! hopsAway and neighbors fields are present and correct!"
exit 0
