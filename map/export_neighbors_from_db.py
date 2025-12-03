#!/usr/bin/env python3
"""
Export neighbor data from MeshBot's SQLite database to JSON format.

This script can operate in two modes:
1. DATABASE-ONLY (default): Read from bot's SQLite database (safe, no TCP conflicts)
2. HYBRID: Query TCP node for complete data + merge with database (more complete, may conflict)

IMPORTANT: Logs go to stderr, JSON goes to stdout (same as original script)
"""

import json
import sys
import os
import time

# Helper pour logger sur stderr (ne pollue pas le JSON sur stdout)
def log(msg):
    print(msg, file=sys.stderr)

def query_tcp_neighbors(host, port=4403):
    """
    Query neighbor data directly from Meshtastic node via TCP.
    
    WARNING: This can conflict with bot's TCP connection if bot uses same node.
    Only use when bot is stopped or uses different node.
    
    Args:
        host: Node IP address
        port: TCP port (default: 4403)
    
    Returns:
        dict: Neighbor data in same format as database export, or None on error
    """
    log(f"🔌 Requête TCP vers {host}:{port}...")
    log("⚠️  ATTENTION: Peut causer des conflits si le bot utilise ce nœud!")
    
    try:
        import meshtastic.tcp_interface
        from datetime import datetime
        
        interface = meshtastic.tcp_interface.TCPInterface(
            hostname=host,
            portNumber=port
        )
        
        # Wait for node data to load
        # Note: 10 seconds is a heuristic based on typical network conditions.
        # May need adjustment for slow networks or very large node databases.
        # Alternative: Implement polling with timeout, but adds complexity.
        log("⏳ Chargement des données (10 secondes)...")
        time.sleep(10)
        
        nodes = interface.nodes
        log(f"📊 {len(nodes)} nœuds trouvés via TCP")
        
        # Extract neighbor info from each node
        output_data = {
            'export_time': datetime.now().isoformat(),
            'source': f'tcp_query_{host}',
            'total_nodes': 0,
            'nodes': {}
        }
        
        for node_id, node_info in nodes.items():
            # Normalize node_id to !xxxxxxxx format
            if isinstance(node_id, str):
                if node_id.startswith('!'):
                    node_id_clean = node_id
                else:
                    node_id_clean = f"!{int(node_id, 16):08x}"
            else:
                node_id_clean = f"!{node_id:08x}"
            
            # Extract neighbors from node
            neighbors = []
            try:
                # Check for neighborinfo attribute
                neighborinfo = None
                if hasattr(node_info, 'neighborinfo'):
                    neighborinfo = node_info.neighborinfo
                elif isinstance(node_info, dict) and 'neighborinfo' in node_info:
                    neighborinfo = node_info['neighborinfo']
                
                if neighborinfo:
                    # Get neighbors list
                    neighbor_list = None
                    if hasattr(neighborinfo, 'neighbors'):
                        neighbor_list = neighborinfo.neighbors
                    elif isinstance(neighborinfo, dict) and 'neighbors' in neighborinfo:
                        neighbor_list = neighborinfo['neighbors']
                    
                    if neighbor_list:
                        for neighbor in neighbor_list:
                            neighbor_data = {}
                            
                            # Extract node_id
                            if hasattr(neighbor, 'node_id'):
                                neighbor_data['node_id'] = neighbor.node_id
                            elif isinstance(neighbor, dict) and 'node_id' in neighbor:
                                neighbor_data['node_id'] = neighbor['node_id']
                            else:
                                continue  # Skip if no node_id
                            
                            # Extract SNR
                            if hasattr(neighbor, 'snr'):
                                neighbor_data['snr'] = neighbor.snr
                            elif isinstance(neighbor, dict) and 'snr' in neighbor:
                                neighbor_data['snr'] = neighbor['snr']
                            
                            # Extract last_rx_time
                            if hasattr(neighbor, 'last_rx_time'):
                                neighbor_data['last_rx_time'] = neighbor.last_rx_time
                            elif isinstance(neighbor, dict) and 'last_rx_time' in neighbor:
                                neighbor_data['last_rx_time'] = neighbor['last_rx_time']
                            
                            # Extract node_broadcast_interval
                            if hasattr(neighbor, 'node_broadcast_interval'):
                                neighbor_data['node_broadcast_interval'] = neighbor.node_broadcast_interval
                            elif isinstance(neighbor, dict) and 'node_broadcast_interval' in neighbor:
                                neighbor_data['node_broadcast_interval'] = neighbor['node_broadcast_interval']
                            
                            neighbors.append(neighbor_data)
            
            except Exception as e:
                log(f"⚠️  Erreur extraction voisins pour {node_id_clean}: {e}")
            
            # Only add node if it has neighbors
            if neighbors:
                output_data['nodes'][node_id_clean] = {
                    'neighbors_extracted': neighbors,
                    'neighbor_count': len(neighbors),
                    'export_timestamp': datetime.now().isoformat()
                }
        
        interface.close()
        
        # Update total_nodes count
        output_data['total_nodes'] = len(output_data['nodes'])
        
        # Calculate statistics
        total_neighbors = sum(
            len(node.get('neighbors_extracted', [])) 
            for node in output_data['nodes'].values()
        )
        nodes_with_neighbors = len([
            node for node in output_data['nodes'].values() 
            if len(node.get('neighbors_extracted', [])) > 0
        ])
        
        output_data['statistics'] = {
            'nodes_with_neighbors': nodes_with_neighbors,
            'total_neighbor_entries': total_neighbors,
            'average_neighbors': total_neighbors / output_data['total_nodes'] if output_data['total_nodes'] > 0 else 0
        }
        
        log(f"✅ Requête TCP réussie: {nodes_with_neighbors} nœuds avec voisins")
        return output_data
        
    except Exception as e:
        log(f"✗ Erreur requête TCP: {e}")
        import traceback
        log(traceback.format_exc())
        return None

def merge_neighbor_data(db_data, tcp_data):
    """
    Merge database and TCP neighbor data, preferring TCP data when available.
    
    Args:
        db_data: Neighbor data from database
        tcp_data: Neighbor data from TCP query
    
    Returns:
        dict: Merged neighbor data
    """
    log("🔀 Fusion des données database + TCP...")
    
    if not tcp_data or not tcp_data.get('nodes'):
        log("⚠️  Pas de données TCP, utilisation database uniquement")
        return db_data
    
    if not db_data or not db_data.get('nodes'):
        log("⚠️  Pas de données database, utilisation TCP uniquement")
        return tcp_data
    
    from datetime import datetime
    
    # Start with TCP data (more complete)
    merged_data = {
        'export_time': datetime.now().isoformat(),
        'source': 'hybrid_db+tcp',
        'nodes': {}
    }
    
    # Copy all TCP nodes
    tcp_node_ids = set()
    for node_id, node_data in tcp_data.get('nodes', {}).items():
        merged_data['nodes'][node_id] = node_data.copy()
        tcp_node_ids.add(node_id)
    
    # Add database-only nodes (nodes not in TCP data)
    db_only_count = 0
    for node_id, node_data in db_data.get('nodes', {}).items():
        if node_id not in tcp_node_ids:
            merged_data['nodes'][node_id] = node_data.copy()
            db_only_count += 1
    
    # Recalculate statistics
    total_nodes = len(merged_data['nodes'])
    total_neighbors = sum(
        len(node.get('neighbors_extracted', [])) 
        for node in merged_data['nodes'].values()
    )
    nodes_with_neighbors = len([
        node for node in merged_data['nodes'].values() 
        if len(node.get('neighbors_extracted', [])) > 0
    ])
    
    merged_data['total_nodes'] = total_nodes
    merged_data['statistics'] = {
        'nodes_with_neighbors': nodes_with_neighbors,
        'total_neighbor_entries': total_neighbors,
        'average_neighbors': total_neighbors / total_nodes if total_nodes > 0 else 0,
        'tcp_nodes': len(tcp_node_ids),
        'db_only_nodes': db_only_count
    }
    
    log(f"✅ Fusion réussie:")
    log(f"   • Nœuds TCP: {len(tcp_node_ids)}")
    log(f"   • Nœuds DB uniquement: {db_only_count}")
    log(f"   • Total nœuds: {total_nodes}")
    
    return merged_data

def export_from_database(db_path='../traffic_history.db', hours=48, tcp_host=None, tcp_port=4403):
    """
    Export neighbor data from the SQLite database, optionally with TCP query.
    
    Args:
        db_path: Path to traffic_history.db
        hours: Hours of data to export (default: 48)
        tcp_host: If provided, query this host via TCP and merge with DB data
        tcp_port: TCP port for Meshtastic node (default: 4403)
    
    Returns:
        bool: Success status
    """
    log(f"🗄️  Export depuis base de données: {db_path}")
    if tcp_host:
        log(f"🔌 Mode HYBRIDE: database + requête TCP vers {tcp_host}:{tcp_port}")
        log(f"⚠️  ATTENTION: Peut causer des conflits si le bot utilise {tcp_host}!")
    else:
        log(f"💾 Mode DATABASE UNIQUEMENT (sûr, pas de conflits TCP)")
    
    try:
        # Add parent directory to path to import TrafficPersistence
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from traffic_persistence import TrafficPersistence
        
        # Connect to database
        if not os.path.exists(db_path):
            log(f"❌ Base de données introuvable: {db_path}")
            return False
        
        persistence = TrafficPersistence(db_path)
        
        # Export neighbor data from database
        log(f"⏳ Export des données de voisinage depuis DB ({hours}h)...")
        db_data = persistence.export_neighbors_to_json(hours=hours)
        
        if not db_data or not db_data.get('nodes'):
            log("⚠️  Aucune donnée de voisinage trouvée dans la base")
            db_data = {
                'export_time': '',
                'source': 'meshbot_database',
                'total_nodes': 0,
                'nodes': {},
                'statistics': {
                    'nodes_with_neighbors': 0,
                    'total_neighbor_entries': 0,
                    'average_neighbors': 0
                }
            }
        
        # Query TCP if requested (hybrid mode)
        output_data = db_data
        if tcp_host:
            tcp_data = query_tcp_neighbors(tcp_host, tcp_port)
            if tcp_data:
                output_data = merge_neighbor_data(db_data, tcp_data)
            else:
                log("⚠️  Échec requête TCP, utilisation données DB uniquement")
        
        # Statistics
        stats = output_data.get('statistics', {})
        total_nodes = output_data.get('total_nodes', 0)
        
        log(f"\n💾 Écriture JSON sur stdout...")
        print(json.dumps(output_data, indent=2, ensure_ascii=False))
        
        log(f"✅ Export réussi!")
        log(f"📊 Statistiques finales:")
        log(f"   • Source: {output_data.get('source', 'unknown')}")
        log(f"   • Nœuds avec voisins: {stats.get('nodes_with_neighbors', 0)}/{total_nodes}")
        log(f"   • Total entrées voisins: {stats.get('total_neighbor_entries', 0)}")
        if total_nodes > 0:
            log(f"   • Moyenne voisins/nœud: {stats.get('average_neighbors', 0):.1f}")
        if 'tcp_nodes' in stats:
            log(f"   • Nœuds TCP: {stats.get('tcp_nodes', 0)}")
            log(f"   • Nœuds DB uniquement: {stats.get('db_only_nodes', 0)}")
        
        persistence.close()
        return True
        
    except Exception as e:
        log(f"✗ Erreur : {e}")
        import traceback
        log(traceback.format_exc())
        return False

if __name__ == "__main__":
    # Configuration defaults
    DB_PATH = "../traffic_history.db"  # Relative to map/ directory
    HOURS = 48  # 48 hours of data
    TCP_HOST = None  # No TCP query by default (safe mode)
    TCP_PORT = 4403
    
    # Parse command line arguments
    if len(sys.argv) > 1 and sys.argv[1] in ['--help', '-h']:
        log("Usage: export_neighbors_from_db.py [options] [db_path] [hours]")
        log("")
        log("Options:")
        log("  --tcp-query HOST[:PORT]  Query node via TCP for complete data (may conflict with bot)")
        log("  --help, -h               Show this help message")
        log("")
        log("Arguments:")
        log("  db_path: Path to traffic_history.db (default: ../traffic_history.db)")
        log("  hours: Hours of data to export (default: 48)")
        log("")
        log("Modes:")
        log("  DATABASE-ONLY (default, safe):")
        log("    ./export_neighbors_from_db.py")
        log("    - Reads only from bot's database")
        log("    - Safe to run while bot is running")
        log("    - May have incomplete data (only packets bot received)")
        log("")
        log("  HYBRID (complete, may conflict):")
        log("    ./export_neighbors_from_db.py --tcp-query 192.168.1.38")
        log("    - Queries node via TCP for full neighbor data")
        log("    - Merges with database data for completeness")
        log("    - WARNING: May conflict if bot uses same TCP node")
        log("    - Recommended: Stop bot first or use different node")
        log("")
        log("Output: JSON data on stdout, logs on stderr")
        sys.exit(0)
    
    # Parse options and arguments
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        
        if arg == '--tcp-query':
            if i + 1 < len(args):
                tcp_spec = args[i + 1]
                if ':' in tcp_spec:
                    host, port = tcp_spec.split(':', 1)
                    TCP_HOST = host
                    try:
                        TCP_PORT = int(port)
                    except ValueError:
                        log(f"⚠️  Invalid port: {port}, using default: 4403")
                        TCP_PORT = 4403
                else:
                    TCP_HOST = tcp_spec
                i += 2
            else:
                log("❌ --tcp-query requires a hostname")
                sys.exit(1)
        elif not arg.startswith('--'):
            # Positional arguments
            if DB_PATH == "../traffic_history.db":
                DB_PATH = arg
            elif HOURS == 48:
                try:
                    HOURS = int(arg)
                except ValueError:
                    log(f"⚠️  Invalid hours value: {arg}, using default: 48")
                    HOURS = 48
            i += 1
        else:
            log(f"❌ Unknown option: {arg}")
            sys.exit(1)
    
    # Export data
    success = export_from_database(DB_PATH, HOURS, TCP_HOST, TCP_PORT)
    sys.exit(0 if success else 1)
