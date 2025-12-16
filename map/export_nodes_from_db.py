#!/usr/bin/env python3
"""
Export node information from MeshBot's node database (node_names.json) and SQLite database.

This script replaces the TCP-based `meshtastic --host --info` command by reading data
directly from the bot's local files, eliminating the "unique TCP session" violation.

IMPORTANT: Logs go to stderr, JSON goes to stdout (same as export_neighbors_from_db.py)
"""

import json
import sys
import os
import traceback
from datetime import datetime

# Add parent directory to path for importing utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import sanitization function to prevent XSS in exported names
try:
    from utils import clean_node_name
except ImportError:
    # Fallback if utils is not available (minimal sanitization)
    import re
    def clean_node_name(name):
        """Minimal sanitization fallback"""
        if not name:
            return ""
        # Remove HTML tags and dangerous characters
        name = re.sub(r'<[^>]*>', '', name)  # Strip HTML tags
        name = re.sub(r'[<>"\']', '', name)  # Remove dangerous chars
        return name.strip()

# Helper to log on stderr (doesn't pollute JSON on stdout)
def log(msg):
    print(msg, file=sys.stderr)

def export_nodes_from_files(node_names_file='../node_names.json', db_path='../traffic_history.db', hours=48):
    """
    Export node information from node_names.json and enrich with SQLite data
    
    Args:
        node_names_file: Path to node_names.json file
        db_path: Path to traffic_history.db
        hours: Hours of data to consider for last heard (default: 48)
    
    Returns:
        bool: Success status
    """
    log(f"🗄️  Export depuis fichiers locaux du bot")
    log(f"   • node_names.json: {node_names_file}")
    log(f"   • traffic_history.db: {db_path}")
    
    try:
        # Load node_names.json
        if not os.path.exists(node_names_file):
            log(f"❌ Fichier node_names.json introuvable: {node_names_file}")
            log(f"⚠️  Le bot n'a peut-être pas encore créé ce fichier.")
            log(f"💡 Astuce: Attendez que le bot reçoive quelques paquets NODEINFO_APP")
            return False
        
        log(f"📖 Lecture de {node_names_file}...")
        with open(node_names_file, 'r', encoding='utf-8') as f:
            node_names_data = json.load(f)
        
        log(f"✅ {len(node_names_data)} nœuds trouvés dans node_names.json")
        
        # Enrich with SQLite data (SNR, last heard, hops, neighbors, telemetry)
        snr_data = {}
        last_heard_data = {}
        hops_data = {}
        neighbors_data = {}
        mqtt_active_nodes = set()  # Track MQTT-active nodes
        mqtt_node_data = {}  # Position/name data for MQTT-active nodes from packets table
        mqtt_last_heard_data = {}  # Track when node was last heard via MQTT
        telemetry_data = {}  # Battery level and voltage from node_stats
        
        if os.path.exists(db_path):
            log(f"📊 Enrichissement avec données SQLite...")
            try:
                sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                from traffic_persistence import TrafficPersistence
                import time
                
                persistence = TrafficPersistence(db_path)
                cursor = persistence.conn.cursor()
                
                # Get latest SNR for each node (from direct reception - 0 hops)
                cutoff = time.time() - (hours * 3600)
                cursor.execute("""
                    SELECT from_id, snr, timestamp
                    FROM packets
                    WHERE timestamp > ? AND snr IS NOT NULL AND hops = 0
                    ORDER BY timestamp DESC
                """, (cutoff,))
                
                for row in cursor.fetchall():
                    from_id_str = str(row[0])
                    if from_id_str not in snr_data or row[2] > snr_data[from_id_str][1]:
                        snr_data[from_id_str] = (row[1], row[2])  # (snr, timestamp)
                
                # Get last heard timestamp for each node
                cursor.execute("""
                    SELECT from_id, MAX(timestamp) as last_ts
                    FROM packets
                    WHERE timestamp > ?
                    GROUP BY from_id
                """, (cutoff,))
                
                for row in cursor.fetchall():
                    from_id_str = str(row[0])
                    last_heard_data[from_id_str] = int(row[1])
                
                # Get minimum hop count for each node (hopsAway)
                cursor.execute("""
                    SELECT from_id, MIN(hops) as min_hops
                    FROM packets
                    WHERE timestamp > ? AND hops IS NOT NULL
                    GROUP BY from_id
                """, (cutoff,))
                
                for row in cursor.fetchall():
                    from_id_str = str(row[0])
                    hops_data[from_id_str] = row[1]
                
                # Get neighbor data from neighbors table
                neighbors_raw = persistence.load_neighbors(hours=hours)
                
                # Get node_stats data for metrics display
                node_stats_raw = persistence.load_node_stats()
                node_stats_data = {}
                for node_id_str, stats in node_stats_raw.items():
                    # Convert node_id from string to ensure consistency
                    node_stats_data[str(node_id_str)] = {
                        'total_packets': stats.get('total_packets', 0),
                        'total_bytes': stats.get('total_bytes', 0),
                        'by_type': dict(stats.get('by_type', {})),  # Convert defaultdict to dict
                        'message_stats': stats.get('message_stats', {}),
                        'telemetry_stats': stats.get('telemetry_stats', {}),
                        'position_stats': stats.get('position_stats', {}),
                        'routing_stats': stats.get('routing_stats', {})
                    }
                    
                    # Extract telemetry data for map display
                    telem_stats = stats.get('telemetry_stats', {})
                    if telem_stats:
                        telemetry_entry = {}
                        
                        # Battery metrics
                        if telem_stats.get('last_battery') is not None:
                            telemetry_entry['battery_level'] = telem_stats['last_battery']
                        if telem_stats.get('last_voltage') is not None:
                            telemetry_entry['battery_voltage'] = telem_stats['last_voltage']
                        
                        # Environment metrics
                        if telem_stats.get('last_temperature') is not None:
                            telemetry_entry['temperature'] = telem_stats['last_temperature']
                        if telem_stats.get('last_humidity') is not None:
                            telemetry_entry['humidity'] = telem_stats['last_humidity']
                        if telem_stats.get('last_pressure') is not None:
                            telemetry_entry['pressure'] = telem_stats['last_pressure']
                        if telem_stats.get('last_air_quality') is not None:
                            telemetry_entry['air_quality'] = telem_stats['last_air_quality']
                        
                        # Only add to telemetry_data if we have at least one metric
                        if telemetry_entry:
                            telemetry_data[str(node_id_str)] = telemetry_entry
                
                # Format neighbor data for map compatibility
                # Note: mqtt_last_heard_data is initialized at line 58 to avoid UnboundLocalError
                for node_id_str, neighbor_list in neighbors_raw.items():
                    formatted_neighbors = []
                    max_timestamp = 0
                    for neighbor in neighbor_list:
                        # neighbor is a dict with: node_id, snr, last_rx_time, node_broadcast_interval, timestamp
                        neighbor_id = neighbor.get('node_id')
                        neighbor_timestamp = neighbor.get('timestamp', 0)
                        
                        # Track the most recent timestamp for this node's MQTT activity
                        if neighbor_timestamp > max_timestamp:
                            max_timestamp = neighbor_timestamp
                        
                        if neighbor_id:
                            # Neighbor ID is stored in database as TEXT in format "!xxxxxxxx"
                            # The database already stores it with ! prefix
                            formatted_neighbors.append({
                                'nodeId': neighbor_id,  # Already has ! prefix from database
                                'snr': neighbor.get('snr'),
                            })
                    if formatted_neighbors:
                        # Convert node_id from hex to decimal
                        # node_id_str format from database: '!16fa4fdc' (hex with ! prefix)
                        # node_names.json keys are decimal strings: '385503196'
                        node_id_hex_stripped = node_id_str.lstrip('!')  # Strip ! prefix
                        node_id_int = int(node_id_hex_stripped, 16)  # Convert hex to decimal
                        node_key_decimal = str(node_id_int)  # Convert to string for dict key
                        
                        # Store neighbors with decimal key (matches node_names.json)
                        neighbors_data[node_key_decimal] = formatted_neighbors
                        
                        # This node sent NEIGHBORINFO, so it's MQTT-active
                        mqtt_active_nodes.add(node_key_decimal)
                        
                        # Store MQTT last heard timestamp
                        if max_timestamp > 0:
                            mqtt_last_heard_data[node_key_decimal] = int(max_timestamp)
                
                # Query packets table for position and name data for MQTT-active nodes
                # This is critical for MQTT-only nodes that aren't in node_names.json
                mqtt_node_data = {}  # {node_id_str: {name, lat, lon, alt}}
                
                for node_key in mqtt_active_nodes:
                    # node_key is now always decimal string (e.g., '385503196')
                    # derived by stripping ! prefix at lines 136-153
                    # packets table also uses decimal string from_id (e.g., '385503196')
                    node_id_str = node_key
                    
                    # Get latest position data from packets
                    cursor.execute("""
                        SELECT position, sender_name, timestamp
                        FROM packets
                        WHERE from_id = ? AND position IS NOT NULL
                        ORDER BY timestamp DESC
                        LIMIT 1
                    """, (node_id_str,))
                    
                    row = cursor.fetchone()
                    if row:
                        position_json = row[0]
                        sender_name = row[1]
                        
                        try:
                            position_data = json.loads(position_json) if position_json else None
                            if position_data:
                                lat = position_data.get('latitude') or position_data.get('latitudeI', 0) / 1e7
                                lon = position_data.get('longitude') or position_data.get('longitudeI', 0) / 1e7
                                alt = position_data.get('altitude') or position_data.get('altitudeGeodesic')
                                
                                # Only store if position is valid
                                if lat and lon and lat != 0 and lon != 0:
                                    # Sanitize sender_name to prevent XSS
                                    sanitized_name = clean_node_name(sender_name) if sender_name else f"Node-{node_key}"
                                    mqtt_node_data[node_id_str] = {
                                        'name': sanitized_name,
                                        'lat': lat,
                                        'lon': lon,
                                        'alt': alt
                                    }
                        except Exception as e:
                            log(f"⚠️  Erreur parsing position pour {node_key}: {e}")
                
                persistence.close()
                log(f"   • SNR disponible pour {len(snr_data)} nœuds")
                log(f"   • Last heard pour {len(last_heard_data)} nœuds")
                log(f"   • MQTT last heard pour {len(mqtt_last_heard_data)} nœuds")
                log(f"   • Hops disponible pour {len(hops_data)} nœuds")
                log(f"   • Neighbors disponible pour {len(neighbors_data)} nœuds")
                log(f"   • MQTT active nodes: {len(mqtt_active_nodes)} nœuds")
                log(f"   • MQTT nodes avec position (packets): {len(mqtt_node_data)} nœuds")
                log(f"   • Telemetry disponible pour {len(telemetry_data)} nœuds")
                log(f"   • Node stats disponible pour {len(node_stats_data)} nœuds")
                
                # Extract 7-day telemetry history for graphing
                log(f"📊 Extraction de l'historique télémétrie (7 jours)...")
                telemetry_history = {}
                history_days = 7
                history_cutoff = time.time() - (history_days * 24 * 3600)
                
                # Query all TELEMETRY_APP packets from last 7 days
                cursor.execute("""
                    SELECT from_id, timestamp, telemetry
                    FROM packets
                    WHERE packet_type = 'TELEMETRY_APP' 
                    AND timestamp > ? 
                    AND telemetry IS NOT NULL
                    ORDER BY from_id, timestamp ASC
                """, (history_cutoff,))
                
                telemetry_rows = cursor.fetchall()
                log(f"   • {len(telemetry_rows)} entrées de télémétrie trouvées")
                
                # Group by node and extract metrics
                for row in telemetry_rows:
                    from_id_str = str(row[0])
                    timestamp = row[1]
                    telemetry_json = row[2]
                    
                    try:
                        telemetry_obj = json.loads(telemetry_json) if telemetry_json else {}
                        
                        # Extract battery level and voltage
                        battery = telemetry_obj.get('battery')
                        voltage = telemetry_obj.get('voltage')
                        channel_util = telemetry_obj.get('channel_util')
                        air_util = telemetry_obj.get('air_util')
                        
                        # Skip if no useful data
                        if battery is None and voltage is None:
                            continue
                        
                        # Initialize history array for this node
                        if from_id_str not in telemetry_history:
                            telemetry_history[from_id_str] = []
                        
                        # Add data point
                        data_point = {'t': int(timestamp)}
                        if battery is not None:
                            data_point['b'] = battery  # battery level (%)
                        if voltage is not None:
                            data_point['v'] = round(voltage, 2)  # voltage (V)
                        if channel_util is not None:
                            data_point['c'] = round(channel_util, 1)  # channel utilization
                        if air_util is not None:
                            data_point['a'] = round(air_util, 1)  # air utilization
                        
                        telemetry_history[from_id_str].append(data_point)
                        
                    except Exception as e:
                        # Silent fail - corrupt telemetry data
                        pass
                
                # Downsample if too many points (keep max 100 points per node)
                max_points = 100
                for node_id_str in telemetry_history.keys():
                    history = telemetry_history[node_id_str]
                    if len(history) > max_points:
                        # Simple downsampling: keep every Nth point
                        step = len(history) // max_points
                        telemetry_history[node_id_str] = [history[i] for i in range(0, len(history), step)][:max_points]
                
                log(f"   • Historique télémétrie pour {len(telemetry_history)} nœuds")
                
            except Exception as e:
                log(f"⚠️  Erreur enrichissement SQLite (non bloquant): {e}")
                log(traceback.format_exc())
        else:
            log(f"⚠️  Base de données SQLite introuvable: {db_path}")
            log(f"💡 Export uniquement depuis node_names.json")
        
        # Build output structure compatible with meshtastic --info format
        output_nodes = {}
        
        for node_id_str, node_data in node_names_data.items():
            try:
                # Convert node_id to integer
                node_id = int(node_id_str)
                
                # Build node ID string with ! prefix (meshtastic format)
                node_id_hex = f"!{node_id:08x}"
                
                # Extract data from node_names.json
                name = node_data.get('name', f"Node-{node_id:08x}")
                lat = node_data.get('lat')
                lon = node_data.get('lon')
                alt = node_data.get('alt')
                
                # Get shortName and hwModel from node_names.json
                short_name = node_data.get('shortName')
                hw_model = node_data.get('hwModel')
                
                # Sanitize names to prevent XSS in exported JSON
                # This is defense in depth - names should already be sanitized in node_names.json
                name = clean_node_name(name) if name else f"Node-{node_id:08x}"
                short_name = clean_node_name(short_name) if short_name else None
                
                # Fallback: if shortName not available after sanitization, generate from name (first 4 chars)
                if not short_name:
                    short_name = name[:4].upper() if len(name) >= 4 else name.upper()
                
                # Fallback: if hwModel not available, use UNKNOWN
                if not hw_model:
                    hw_model = "UNKNOWN"
                
                node_entry = {
                    "num": node_id,
                    "user": {
                        "id": node_id_hex,
                        "longName": name,
                        "shortName": short_name,
                        "hwModel": hw_model
                    }
                }
                
                # Add position if available
                if lat is not None and lon is not None:
                    node_entry["position"] = {
                        "latitude": lat,
                        "longitude": lon
                    }
                    if alt is not None:
                        node_entry["position"]["altitude"] = int(alt)
                
                # Add SNR if available from SQLite
                if node_id_str in snr_data:
                    node_entry["snr"] = round(snr_data[node_id_str][0], 2)
                
                # Add lastHeard if available from SQLite (mesh packets)
                if node_id_str in last_heard_data:
                    node_entry["lastHeard"] = last_heard_data[node_id_str]
                elif node_id_str in mqtt_last_heard_data:
                    # Fallback: Use MQTT timestamp if no mesh packets
                    # This ensures MQTT-only nodes are not filtered out by time
                    node_entry["lastHeard"] = mqtt_last_heard_data[node_id_str]
                
                # Add MQTT last heard timestamp (always add for MQTT-active nodes)
                if node_id_str in mqtt_last_heard_data:
                    node_entry["mqttLastHeard"] = mqtt_last_heard_data[node_id_str]
                
                # Add hopsAway if available from SQLite
                if node_id_str in hops_data:
                    node_entry["hopsAway"] = hops_data[node_id_str]
                
                # Add neighbors array if available from SQLite
                if node_id_str in neighbors_data:
                    node_entry["neighbors"] = neighbors_data[node_id_str]
                
                # Add MQTT active flag if this node sent NEIGHBORINFO
                if node_id_str in mqtt_active_nodes:
                    node_entry["mqttActive"] = True
                
                # Add telemetry data if available from node_stats
                if node_id_str in telemetry_data:
                    telem = telemetry_data[node_id_str]
                    
                    # Device metrics (battery)
                    if telem.get('battery_level') is not None or telem.get('battery_voltage') is not None:
                        if "deviceMetrics" not in node_entry:
                            node_entry["deviceMetrics"] = {}
                        if telem.get('battery_level') is not None:
                            node_entry["deviceMetrics"]["batteryLevel"] = telem['battery_level']
                        if telem.get('battery_voltage') is not None:
                            node_entry["deviceMetrics"]["voltage"] = telem['battery_voltage']
                    
                    # Environment metrics (temperature, humidity, pressure, air quality)
                    if (telem.get('temperature') is not None or telem.get('humidity') is not None or
                        telem.get('pressure') is not None or telem.get('air_quality') is not None):
                        node_entry["environmentMetrics"] = {}
                        if telem.get('temperature') is not None:
                            node_entry["environmentMetrics"]["temperature"] = telem['temperature']
                        if telem.get('humidity') is not None:
                            node_entry["environmentMetrics"]["relativeHumidity"] = telem['humidity']
                        if telem.get('pressure') is not None:
                            node_entry["environmentMetrics"]["barometricPressure"] = telem['pressure']
                        if telem.get('air_quality') is not None:
                            node_entry["environmentMetrics"]["iaq"] = telem['air_quality']
                
                # Add telemetry history if available (7-day graphs)
                if node_id_str in telemetry_history and len(telemetry_history[node_id_str]) > 0:
                    node_entry["telemetryHistory"] = telemetry_history[node_id_str]
                
                output_nodes[node_id_hex] = node_entry
                
            except Exception as e:
                log(f"⚠️  Erreur traitement nœud {node_id_str}: {e}")
                continue
        
        # Phase 2: Add MQTT-only nodes that are not in node_names.json
        # These are nodes heard via MQTT NEIGHBORINFO but never heard directly via mesh
        log(f"\n🔍 Phase 2: Recherche de nœuds MQTT-only non présents dans node_names.json...")
        mqtt_only_added = 0
        
        for node_id_str in mqtt_node_data.keys():
            # Check if already processed from node_names.json
            if node_id_str in node_names_data:
                continue  # Already processed in phase 1
            
            try:
                node_id = int(node_id_str)
                node_id_hex = f"!{node_id:08x}"
                
                # Check if already in output (shouldn't be, but be safe)
                if node_id_hex in output_nodes:
                    continue
                
                # Get MQTT node data
                node_info = mqtt_node_data[node_id_str]
                name = node_info['name']  # Already sanitized when stored
                lat = node_info['lat']
                lon = node_info['lon']
                alt = node_info.get('alt')
                
                # Extract short name - generate fallback since MQTT nodes won't have it stored
                # Use sanitized name for generating short name
                short_name = name[:4].upper() if len(name) >= 4 else name.upper()
                # hwModel unknown for MQTT-only nodes
                hw_model = "UNKNOWN"
                
                log(f"   ➕ Ajout nœud MQTT-only: {name} ({node_id_hex}) @ {lat:.4f}, {lon:.4f}")
                
                # Build node entry
                node_entry = {
                    "num": node_id,
                    "user": {
                        "id": node_id_hex,
                        "longName": name,
                        "shortName": short_name,
                        "hwModel": hw_model
                    },
                    "position": {
                        "latitude": lat,
                        "longitude": lon
                    }
                }
                
                if alt is not None:
                    node_entry["position"]["altitude"] = int(alt)
                
                # Add MQTT timestamp as lastHeard (critical for time filter)
                # Use node_id_str which matches the keys in mqtt_last_heard_data, mqtt_active_nodes, etc.
                if node_id_str in mqtt_last_heard_data:
                    node_entry["lastHeard"] = mqtt_last_heard_data[node_id_str]
                    node_entry["mqttLastHeard"] = mqtt_last_heard_data[node_id_str]
                
                # Add SNR if available
                if node_id_str in snr_data:
                    node_entry["snr"] = round(snr_data[node_id_str][0], 2)
                
                # Add hopsAway if available
                if node_id_str in hops_data:
                    node_entry["hopsAway"] = hops_data[node_id_str]
                
                # Add neighbors if available
                # neighbors_data is now keyed by decimal (e.g., '385503196')
                if node_id_str in neighbors_data:
                    node_entry["neighbors"] = neighbors_data[node_id_str]
                
                # Mark as MQTT active
                # mqtt_active_nodes is now keyed by decimal (e.g., '385503196')
                if node_id_str in mqtt_active_nodes:
                    node_entry["mqttActive"] = True
                
                # Add telemetry data if available from node_stats
                if node_id_str in telemetry_data:
                    telem = telemetry_data[node_id_str]
                    
                    # Device metrics (battery)
                    if telem.get('battery_level') is not None or telem.get('battery_voltage') is not None:
                        if "deviceMetrics" not in node_entry:
                            node_entry["deviceMetrics"] = {}
                        if telem.get('battery_level') is not None:
                            node_entry["deviceMetrics"]["batteryLevel"] = telem['battery_level']
                        if telem.get('battery_voltage') is not None:
                            node_entry["deviceMetrics"]["voltage"] = telem['battery_voltage']
                    
                    # Environment metrics (temperature, humidity, pressure, air quality)
                    if (telem.get('temperature') is not None or telem.get('humidity') is not None or
                        telem.get('pressure') is not None or telem.get('air_quality') is not None):
                        node_entry["environmentMetrics"] = {}
                        if telem.get('temperature') is not None:
                            node_entry["environmentMetrics"]["temperature"] = telem['temperature']
                        if telem.get('humidity') is not None:
                            node_entry["environmentMetrics"]["relativeHumidity"] = telem['humidity']
                        if telem.get('pressure') is not None:
                            node_entry["environmentMetrics"]["barometricPressure"] = telem['pressure']
                        if telem.get('air_quality') is not None:
                            node_entry["environmentMetrics"]["iaq"] = telem['air_quality']
                
                # Add node statistics if available
                if node_id_str in node_stats_data:
                    stats = node_stats_data[node_id_str]
                    node_entry["nodeStats"] = {
                        "totalPackets": stats.get('total_packets', 0),
                        "totalBytes": stats.get('total_bytes', 0),
                        "packetTypes": stats.get('by_type', {}),
                        "messageStats": stats.get('message_stats', {}),
                        "positionStats": stats.get('position_stats', {}),
                        "routingStats": stats.get('routing_stats', {})
                    }
                
                # Add telemetry history if available (7-day graphs)
                if node_id_str in telemetry_history and len(telemetry_history[node_id_str]) > 0:
                    node_entry["telemetryHistory"] = telemetry_history[node_id_str]
                
                output_nodes[node_id_hex] = node_entry
                mqtt_only_added += 1
                
            except Exception as e:
                log(f"⚠️  Erreur ajout nœud MQTT-only {node_id_str}: {e}")
                continue
        
        log(f"✅ Phase 2 terminée: {mqtt_only_added} nœuds MQTT-only ajoutés")
        
        # Build final output structure
        output_data = {
            "Nodes in mesh": output_nodes
        }
        
        # Output JSON to stdout
        log(f"\n💾 Écriture JSON sur stdout...")
        print(json.dumps(output_data, indent=2, ensure_ascii=False))
        
        log(f"✅ Export réussi!")
        log(f"📊 Statistiques:")
        log(f"   • Total nœuds: {len(output_nodes)}")
        nodes_with_position = sum(1 for n in output_nodes.values() if 'position' in n)
        log(f"   • Nœuds avec position GPS: {nodes_with_position}")
        nodes_with_snr = sum(1 for n in output_nodes.values() if 'snr' in n)
        log(f"   • Nœuds avec SNR: {nodes_with_snr}")
        nodes_with_last_heard = sum(1 for n in output_nodes.values() if 'lastHeard' in n)
        log(f"   • Nœuds avec lastHeard: {nodes_with_last_heard}")
        nodes_with_mqtt_last_heard = sum(1 for n in output_nodes.values() if 'mqttLastHeard' in n)
        log(f"   • Nœuds avec mqttLastHeard: {nodes_with_mqtt_last_heard}")
        nodes_with_hops = sum(1 for n in output_nodes.values() if 'hopsAway' in n)
        log(f"   • Nœuds avec hopsAway: {nodes_with_hops}")
        nodes_with_neighbors = sum(1 for n in output_nodes.values() if 'neighbors' in n)
        log(f"   • Nœuds avec neighbors: {nodes_with_neighbors}")
        nodes_mqtt_active = sum(1 for n in output_nodes.values() if 'mqttActive' in n)
        log(f"   • Nœuds MQTT actifs: {nodes_mqtt_active}")
        log(f"   • Nœuds MQTT-only ajoutés: {mqtt_only_added}")
        
        return True
        
    except Exception as e:
        log(f"✗ Erreur : {e}")
        log(traceback.format_exc())
        return False

if __name__ == "__main__":
    # Configuration
    NODE_NAMES_FILE = "../node_names.json"  # Relative to map/ directory
    DB_PATH = "../traffic_history.db"
    HOURS = 48  # 48 hours of data for enrichment
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] in ['--help', '-h']:
            log("Usage: export_nodes_from_db.py [node_names_file] [db_path] [hours]")
            log("  node_names_file: Path to node_names.json (default: ../node_names.json)")
            log("  db_path: Path to traffic_history.db (default: ../traffic_history.db)")
            log("  hours: Hours of data for enrichment (default: 48)")
            log("")
            log("Output: JSON data on stdout (compatible with meshtastic --info), logs on stderr")
            log("")
            log("Example:")
            log("  ./export_nodes_from_db.py > info.json")
            log("  ./export_nodes_from_db.py ../node_names.json ../traffic_history.db 72 > info.json")
            sys.exit(0)
        NODE_NAMES_FILE = sys.argv[1]
    
    if len(sys.argv) > 2:
        DB_PATH = sys.argv[2]
    
    if len(sys.argv) > 3:
        try:
            HOURS = int(sys.argv[3])
        except ValueError:
            log(f"⚠️  Invalid hours value: {sys.argv[3]}, using default: 48")
            HOURS = 48
    
    # Export data
    success = export_nodes_from_files(NODE_NAMES_FILE, DB_PATH, HOURS)
    sys.exit(0 if success else 1)
