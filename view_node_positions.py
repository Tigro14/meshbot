#!/usr/bin/env python3
"""
Helper script to view node positions from the traffic database.
Shows node positions with LongNames, SNR, RSSI, and hop information.

Usage:
    python view_node_positions.py [--hours 24] [--with-rssi]
"""

import sqlite3
import json
import sys
import argparse
from datetime import datetime, timedelta

def load_node_names(node_names_file='node_names.json'):
    """Load node names from JSON file."""
    try:
        with open(node_names_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load {node_names_file}: {e}")
        return {}

def get_node_name(node_id, node_names):
    """Get human-readable node name from node_names dict."""
    # Convert node_id to integer if it's a string
    try:
        if isinstance(node_id, str):
            # Try to parse as decimal or hex
            if node_id.startswith('!'):
                node_id_int = int(node_id[1:], 16)
            else:
                node_id_int = int(node_id)
        else:
            node_id_int = int(node_id)
    except (ValueError, TypeError):
        # If we can't convert, return the original value
        return str(node_id)
    
    # Try hex format with !
    hex_id = f"!{node_id_int:08x}"
    if hex_id in node_names:
        return node_names[hex_id].get('longName', hex_id)
    
    # Try string format
    str_id = str(node_id_int)
    if str_id in node_names:
        return node_names[str_id].get('longName', hex_id)
    
    # Return hex format as fallback
    return hex_id

def view_positions(db_path='traffic_history.db', hours=24, with_rssi=False):
    """View node positions from database with optional RSSI filtering."""
    
    # Load node names
    node_names = load_node_names()
    
    # Check if database exists
    import os
    if not os.path.exists(db_path):
        print(f"❌ Erreur: Database '{db_path}' introuvable")
        print(f"   Vérifiez que le chemin est correct et que le bot a créé la base de données.")
        sys.exit(1)
    
    # Connect to database
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
    except Exception as e:
        print(f"❌ Erreur de connexion à la base de données: {e}")
        sys.exit(1)
    
    # Check if packets table exists
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='packets'")
        if not cursor.fetchone():
            print(f"❌ Erreur: La table 'packets' n'existe pas dans {db_path}")
            print(f"   La base de données semble vide ou corrompue.")
            conn.close()
            sys.exit(1)
    except Exception as e:
        print(f"❌ Erreur lors de la vérification de la table: {e}")
        conn.close()
        sys.exit(1)
    
    # Calculate time cutoff
    cutoff = datetime.now().timestamp() - (hours * 3600)
    
    # Check which columns exist in the table
    cursor.execute("PRAGMA table_info(packets)")
    columns = [row[1] for row in cursor.fetchall()]
    has_hop_limit = 'hop_limit' in columns
    has_hop_start = 'hop_start' in columns
    
    # Build query based on available columns
    if has_hop_limit and has_hop_start:
        query = """
            SELECT from_id, to_id, position, snr, rssi, timestamp, hop_limit, hop_start, source
            FROM packets
            WHERE position IS NOT NULL
            AND timestamp > ?
            ORDER BY timestamp DESC
        """
    else:
        query = """
            SELECT from_id, to_id, position, snr, rssi, timestamp, NULL, NULL, source
            FROM packets
            WHERE position IS NOT NULL
            AND timestamp > ?
            ORDER BY timestamp DESC
        """
    
    try:
        cursor.execute(query, (cutoff,))
        rows = cursor.fetchall()
    except Exception as e:
        print(f"❌ Erreur lors de la requête: {e}")
        conn.close()
        sys.exit(1)
    
    print(f"=== Node Positions (dernières {hours}h) ===")
    print(f"Total packets with GPS: {len(rows)}")
    print()
    
    if not rows:
        print("❌ Aucune position trouvée dans la période spécifiée")
        conn.close()
        return
    
    # Group by node
    nodes_data = {}
    
    for row in rows:
        from_id, to_id, position_str, snr, rssi, ts, hop_limit, hop_start, source = row
        
        # Skip if filtering by RSSI and no RSSI data
        if with_rssi and (rssi is None or rssi == 0):
            continue
        
        # Parse position
        try:
            position = json.loads(position_str) if isinstance(position_str, str) else position_str
            lat = position.get('latitude')
            lon = position.get('longitude')
            alt = position.get('altitude', 0)
        except:
            continue
        
        if lat is None or lon is None:
            continue
        
        # Calculate hops
        hops = None
        if hop_start and hop_limit is not None:
            hops = hop_start - hop_limit
        
        # Store data for from_id (the node that sent position)
        if from_id not in nodes_data:
            nodes_data[from_id] = {
                'positions': [],
                'snr_values': [],
                'rssi_values': [],
                'hops': [],
                'sources': set()
            }
        
        nodes_data[from_id]['positions'].append({
            'lat': lat,
            'lon': lon,
            'alt': alt,
            'timestamp': ts,
            'to_id': to_id
        })
        
        if snr is not None and snr != 0:
            nodes_data[from_id]['snr_values'].append(snr)
        if rssi is not None and rssi != 0:
            nodes_data[from_id]['rssi_values'].append(rssi)
        if hops is not None:
            nodes_data[from_id]['hops'].append(hops)
        nodes_data[from_id]['sources'].add(source or 'unknown')
    
    # Display nodes
    print("📍 Nodes avec positions GPS:\n")
    
    for node_id in sorted(nodes_data.keys()):
        data = nodes_data[node_id]
        
        # Get most recent position
        latest = max(data['positions'], key=lambda p: p['timestamp'])
        
        # Calculate averages
        avg_snr = sum(data['snr_values']) / len(data['snr_values']) if data['snr_values'] else None
        avg_rssi = sum(data['rssi_values']) / len(data['rssi_values']) if data['rssi_values'] else None
        avg_hops = sum(data['hops']) / len(data['hops']) if data['hops'] else None
        
        # Get node name
        node_name = get_node_name(node_id, node_names)
        
        # Format node_id as hex
        try:
            if isinstance(node_id, str):
                if node_id.startswith('!'):
                    node_id_int = int(node_id[1:], 16)
                else:
                    node_id_int = int(node_id)
            else:
                node_id_int = int(node_id)
            hex_id = f"!{node_id_int:08x}"
        except (ValueError, TypeError):
            hex_id = str(node_id)
        
        # Format timestamp
        ts_str = datetime.fromtimestamp(latest['timestamp']).strftime('%d/%m %H:%M')
        
        # Display node information
        print(f"🔷 {node_name}")
        try:
            print(f"   ID: {hex_id} (decimal: {node_id_int})")
        except (NameError, UnboundLocalError):
            print(f"   ID: {hex_id}")
        print(f"   📍 Position: {latest['lat']:.6f}, {latest['lon']:.6f} (alt: {latest['alt']:.0f}m)")
        print(f"   🕐 Dernière: {ts_str}")
        print(f"   📊 Packets: {len(data['positions'])}")
        
        if avg_snr is not None:
            print(f"   📶 SNR moyen: {avg_snr:.1f} dB")
        else:
            print(f"   📶 SNR: N/A")
        
        if avg_rssi is not None:
            print(f"   📡 RSSI moyen: {avg_rssi:.0f} dBm")
        else:
            print(f"   📡 RSSI: N/A")
        
        if avg_hops is not None:
            print(f"   🔀 Hops moyens: {avg_hops:.1f}")
        else:
            print(f"   🔀 Hops: N/A")
        
        print(f"   📥 Sources: {', '.join(sorted(data['sources']))}")
        print()
    
    # Summary statistics
    print(f"\n=== Résumé ===")
    print(f"Total nodes avec GPS: {len(nodes_data)}")
    
    nodes_with_snr = sum(1 for d in nodes_data.values() if d['snr_values'])
    nodes_with_rssi = sum(1 for d in nodes_data.values() if d['rssi_values'])
    nodes_with_hops = sum(1 for d in nodes_data.values() if d['hops'])
    
    print(f"Nodes avec SNR: {nodes_with_snr}")
    print(f"Nodes avec RSSI: {nodes_with_rssi}")
    print(f"Nodes avec hop info: {nodes_with_hops}")
    
    if nodes_with_rssi < len(nodes_data):
        print(f"\n⚠️  {len(nodes_data) - nodes_with_rssi} nodes manquent RSSI (possiblement 0-hop/local)")
    
    conn.close()

def main():
    parser = argparse.ArgumentParser(
        description='View node positions from traffic database with LongNames, SNR, RSSI'
    )
    parser.add_argument(
        '--hours',
        type=int,
        default=24,
        help='Hours of history to show (default: 24)'
    )
    parser.add_argument(
        '--with-rssi',
        action='store_true',
        help='Only show nodes with RSSI data (filter out 0-hop nodes)'
    )
    parser.add_argument(
        '--db',
        default='traffic_history.db',
        help='Path to traffic database (default: traffic_history.db)'
    )
    
    args = parser.parse_args()
    
    view_positions(args.db, args.hours, args.with_rssi)

if __name__ == '__main__':
    main()
