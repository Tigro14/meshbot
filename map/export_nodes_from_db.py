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
        
        # Enrich with SQLite data (SNR, last heard, hops, neighbors)
        snr_data = {}
        last_heard_data = {}
        hops_data = {}
        neighbors_data = {}
        
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
                
                # Format neighbor data for map compatibility
                for node_id_str, neighbor_list in neighbors_raw.items():
                    formatted_neighbors = []
                    for neighbor in neighbor_list:
                        # neighbor is a dict with: node_id, snr, last_rx_time, node_broadcast_interval
                        neighbor_id = neighbor.get('node_id')
                        if neighbor_id:
                            # Neighbor ID is stored in database as TEXT in format "!xxxxxxxx"
                            # The database already stores it with ! prefix
                            formatted_neighbors.append({
                                'nodeId': neighbor_id,  # Already has ! prefix from database
                                'snr': neighbor.get('snr'),
                            })
                    if formatted_neighbors:
                        # Remove ! prefix from node_id_str for consistency with node_names.json keys
                        node_key = node_id_str.lstrip('!')
                        neighbors_data[node_key] = formatted_neighbors
                
                persistence.close()
                log(f"   • SNR disponible pour {len(snr_data)} nœuds")
                log(f"   • Last heard pour {len(last_heard_data)} nœuds")
                log(f"   • Hops disponible pour {len(hops_data)} nœuds")
                log(f"   • Neighbors disponible pour {len(neighbors_data)} nœuds")
                
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
                
                # Build user info
                # Try to extract shortName from longName (take first 4 chars)
                short_name = name[:4].upper() if len(name) >= 4 else name.upper()
                
                node_entry = {
                    "num": node_id,
                    "user": {
                        "id": node_id_hex,
                        "longName": name,
                        "shortName": short_name,
                        "hwModel": "UNKNOWN"  # Not available in node_names.json
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
                
                # Add lastHeard if available from SQLite
                if node_id_str in last_heard_data:
                    node_entry["lastHeard"] = last_heard_data[node_id_str]
                
                # Add hopsAway if available from SQLite
                if node_id_str in hops_data:
                    node_entry["hopsAway"] = hops_data[node_id_str]
                
                # Add neighbors array if available from SQLite
                if node_id_str in neighbors_data:
                    node_entry["neighbors"] = neighbors_data[node_id_str]
                
                output_nodes[node_id_hex] = node_entry
                
            except Exception as e:
                log(f"⚠️  Erreur traitement nœud {node_id_str}: {e}")
                continue
        
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
        nodes_with_hops = sum(1 for n in output_nodes.values() if 'hopsAway' in n)
        log(f"   • Nœuds avec hopsAway: {nodes_with_hops}")
        nodes_with_neighbors = sum(1 for n in output_nodes.values() if 'neighbors' in n)
        log(f"   • Nœuds avec neighbors: {nodes_with_neighbors}")
        
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
