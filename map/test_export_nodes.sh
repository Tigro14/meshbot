#!/bin/bash
# Test script for export_nodes_from_db.py
# Creates sample data and validates the export

echo "🧪 Test export_nodes_from_db.py"
echo "================================"

# Create temporary test files
TEST_DIR="/tmp/meshbot_test_$$"
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

# Run export script
echo ""
echo "📡 Running export_nodes_from_db.py..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_FILE="$TEST_DIR/info.json"

"$SCRIPT_DIR/export_nodes_from_db.py" "$TEST_DIR/node_names.json" "$TEST_DIR/nonexistent.db" 48 > "$OUTPUT_FILE" 2>"$TEST_DIR/export.log"

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

# Check JSON structure
echo ""
echo "🔍 Checking JSON structure..."

# Check for "Nodes in mesh" key
if ! grep -q '"Nodes in mesh"' "$OUTPUT_FILE"; then
    echo "❌ FAIL: Missing 'Nodes in mesh' key"
    exit 1
fi
echo "✅ Has 'Nodes in mesh' key"

# Check for expected node IDs
if ! grep -q '"!16fa4fdc"' "$OUTPUT_FILE"; then
    echo "❌ FAIL: Missing expected node ID !16fa4fdc"
    exit 1
fi
echo "✅ Found node !16fa4fdc"

# Check for user information
if ! grep -q '"longName"' "$OUTPUT_FILE"; then
    echo "❌ FAIL: Missing user information"
    exit 1
fi
echo "✅ Has user information"

# Check for position data
if ! grep -q '"position"' "$OUTPUT_FILE"; then
    echo "❌ FAIL: Missing position data"
    exit 1
fi
echo "✅ Has position data"

# Count nodes
NODE_COUNT=$(python3 -c "import json; data = json.load(open('$OUTPUT_FILE')); print(len(data['Nodes in mesh']))")
if [ "$NODE_COUNT" -ne 3 ]; then
    echo "❌ FAIL: Expected 3 nodes, found $NODE_COUNT"
    exit 1
fi
echo "✅ Correct node count: $NODE_COUNT"

# Show sample output
echo ""
echo "📄 Sample output (first 30 lines):"
head -30 "$OUTPUT_FILE"

# Show logs
echo ""
echo "📋 Export logs:"
cat "$TEST_DIR/export.log"

# Cleanup
echo ""
echo "🧹 Cleaning up..."
rm -rf "$TEST_DIR"

echo ""
echo "✅ All tests passed!"
exit 0
