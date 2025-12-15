#!/bin/bash
# Verification script to check if telemetry fix is working correctly
# Run this after deploying the fix and running infoup_db.sh

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 Telemetry Fix Verification Script"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Configuration
DB_PATH="${DB_PATH:-/home/dietpi/bot/traffic_history.db}"
INFO_JSON="${INFO_JSON:-/home/dietpi/bot/map/info.json}"
MAP_DIR="${MAP_DIR:-/home/dietpi/bot/map}"

# Check 1: Database has telemetry data
echo "📊 Check 1: Database telemetry data"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ ! -f "$DB_PATH" ]; then
    echo "❌ Database not found: $DB_PATH"
    exit 1
fi

NODES_WITH_BATTERY=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM node_stats WHERE last_battery_level IS NOT NULL;" 2>/dev/null || echo "0")
NODES_WITH_TEMP=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM node_stats WHERE last_temperature IS NOT NULL;" 2>/dev/null || echo "0")

echo "   Nodes with battery data: $NODES_WITH_BATTERY"
echo "   Nodes with temperature data: $NODES_WITH_TEMP"

if [ "$NODES_WITH_BATTERY" -eq 0 ] && [ "$NODES_WITH_TEMP" -eq 0 ]; then
    echo "⚠️  No telemetry data in database yet"
    echo "   This is normal if nodes haven't sent telemetry packets recently"
    echo "   Telemetry packets are sent every 5-15 minutes"
    echo ""
else
    echo "✅ Database contains telemetry data"
    echo ""
    
    # Show sample data
    echo "   Sample telemetry data:"
    sqlite3 "$DB_PATH" "
        SELECT 
            node_id,
            last_battery_level as 'Battery %',
            printf('%.2f', last_battery_voltage) as 'Voltage V',
            printf('%.1f', last_temperature) as 'Temp °C'
        FROM node_stats 
        WHERE last_battery_level IS NOT NULL OR last_temperature IS NOT NULL
        LIMIT 3;
    " -header -column 2>/dev/null || echo "   (Unable to query database)"
    echo ""
fi

# Check 2: Export script has the fix
echo "📝 Check 2: Export script contains fix"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

EXPORT_SCRIPT="$MAP_DIR/export_nodes_from_db.py"
if [ ! -f "$EXPORT_SCRIPT" ]; then
    echo "❌ Export script not found: $EXPORT_SCRIPT"
    exit 1
fi

if grep -q "Extract telemetry data for map display" "$EXPORT_SCRIPT"; then
    echo "✅ Export script contains telemetry extraction code"
    echo ""
else
    echo "❌ Export script missing telemetry extraction code"
    echo "   Please ensure you've deployed the latest version"
    exit 1
fi

# Check 3: info.json has deviceMetrics
echo "🗺️  Check 3: Map JSON contains telemetry"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ ! -f "$INFO_JSON" ]; then
    echo "⚠️  info.json not found: $INFO_JSON"
    echo "   Run: cd $MAP_DIR && ./infoup_db.sh"
    exit 0
fi

# Check if jq is available
if ! command -v jq &> /dev/null; then
    echo "⚠️  jq not installed, skipping JSON validation"
    echo "   Install with: apt-get install jq"
    echo ""
else
    NODES_WITH_DEVICE_METRICS=$(jq '[.["Nodes in mesh"] | to_entries[] | select(.value.deviceMetrics)] | length' "$INFO_JSON" 2>/dev/null || echo "0")
    NODES_WITH_ENV_METRICS=$(jq '[.["Nodes in mesh"] | to_entries[] | select(.value.environmentMetrics)] | length' "$INFO_JSON" 2>/dev/null || echo "0")
    TOTAL_NODES=$(jq '.["Nodes in mesh"] | length' "$INFO_JSON" 2>/dev/null || echo "0")
    
    echo "   Total nodes in JSON: $TOTAL_NODES"
    echo "   Nodes with deviceMetrics: $NODES_WITH_DEVICE_METRICS"
    echo "   Nodes with environmentMetrics: $NODES_WITH_ENV_METRICS"
    echo ""
    
    if [ "$NODES_WITH_DEVICE_METRICS" -gt 0 ] || [ "$NODES_WITH_ENV_METRICS" -gt 0 ]; then
        echo "✅ Telemetry data successfully exported to JSON!"
        echo ""
        
        # Show sample telemetry
        echo "   Sample node with telemetry:"
        jq -r '.["Nodes in mesh"] | to_entries[] | select(.value.deviceMetrics or .value.environmentMetrics) | 
            "   Node: \(.value.user.longName) (\(.key))" +
            (if .value.deviceMetrics.batteryLevel then "\n   🔋 Battery: \(.value.deviceMetrics.batteryLevel)%" else "" end) +
            (if .value.deviceMetrics.voltage then "\n   ⚡ Voltage: \(.value.deviceMetrics.voltage)V" else "" end) +
            (if .value.environmentMetrics.temperature then "\n   🌡️ Temperature: \(.value.environmentMetrics.temperature)°C" else "" end)
        ' "$INFO_JSON" 2>/dev/null | head -10
        echo ""
    else
        echo "⚠️  No telemetry found in JSON"
        if [ "$NODES_WITH_BATTERY" -gt 0 ] || [ "$NODES_WITH_TEMP" -gt 0 ]; then
            echo "   Database has telemetry but it's not in JSON"
            echo "   Try running: cd $MAP_DIR && ./infoup_db.sh"
        else
            echo "   Database doesn't have telemetry data yet"
            echo "   Wait for nodes to send telemetry packets (5-15 minutes)"
        fi
        echo ""
    fi
fi

# Check 4: infoup_db.sh log output
echo "📋 Check 4: Last export script run"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "   Running export to check output..."
cd "$MAP_DIR"
OUTPUT=$(./export_nodes_from_db.py /home/dietpi/bot/node_names.json "$DB_PATH" 720 2>&1 | grep "Telemetry disponible" || echo "")

if [ -n "$OUTPUT" ]; then
    echo "   $OUTPUT"
    if echo "$OUTPUT" | grep -q "Telemetry disponible pour 0"; then
        echo "   ⚠️  Export script reports 0 nodes with telemetry"
    else
        echo "   ✅ Export script successfully processes telemetry"
    fi
else
    echo "   ⚠️  Unable to determine telemetry count from export"
fi
echo ""

# Final summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

ALL_GOOD=true

if [ "$NODES_WITH_BATTERY" -eq 0 ] && [ "$NODES_WITH_TEMP" -eq 0 ]; then
    echo "⏳ Status: Waiting for telemetry data"
    echo "   Action: Wait 5-15 minutes for nodes to send telemetry"
    ALL_GOOD=false
elif command -v jq &> /dev/null && [ "$NODES_WITH_DEVICE_METRICS" -eq 0 ] && [ "$NODES_WITH_ENV_METRICS" -eq 0 ]; then
    echo "🔄 Status: Need to regenerate map data"
    echo "   Action: Run ./infoup_db.sh in $MAP_DIR"
    ALL_GOOD=false
elif ! grep -q "Extract telemetry data for map display" "$EXPORT_SCRIPT"; then
    echo "❌ Status: Fix not deployed"
    echo "   Action: Deploy latest version of export_nodes_from_db.py"
    ALL_GOOD=false
else
    echo "✅ Status: Telemetry fix working correctly!"
    echo "   • Database contains telemetry: ✅"
    echo "   • Export script has fix: ✅"
    if command -v jq &> /dev/null; then
        echo "   • JSON contains telemetry: ✅"
    fi
    echo ""
    echo "🎉 Open map.html and click any node to see telemetry!"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
