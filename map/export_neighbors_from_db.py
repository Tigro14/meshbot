#!/usr/bin/env python3
"""
Export neighbor data from MeshBot's SQLite database to JSON format.

This script replaces the TCP-based export_neighbors.py by reading data
directly from the bot's database, eliminating the "unique TCP session" violation.

IMPORTANT: Logs go to stderr, JSON goes to stdout (same as original script)
"""

import json
import sys
import os

# Helper pour logger sur stderr (ne pollue pas le JSON sur stdout)
def log(msg):
    print(msg, file=sys.stderr)

def export_from_database(db_path='../traffic_history.db', hours=48):
    """
    Export neighbor data from the SQLite database
    
    Args:
        db_path: Path to traffic_history.db
        hours: Hours of data to export (default: 48)
    
    Returns:
        bool: Success status
    """
    log(f"🗄️  Export depuis base de données: {db_path}")
    
    try:
        # Add parent directory to path to import TrafficPersistence
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from traffic_persistence import TrafficPersistence
        
        # Connect to database
        if not os.path.exists(db_path):
            log(f"❌ Base de données introuvable: {db_path}")
            return False
        
        persistence = TrafficPersistence(db_path)
        
        # Export neighbor data
        log(f"⏳ Export des données de voisinage ({hours}h)...")
        output_data = persistence.export_neighbors_to_json(hours=hours)
        
        if not output_data or not output_data.get('nodes'):
            log("⚠️  Aucune donnée de voisinage trouvée dans la base")
            # Return empty but valid JSON structure
            output_data = {
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
        
        # Statistics
        stats = output_data.get('statistics', {})
        total_nodes = output_data.get('total_nodes', 0)
        
        log(f"\n💾 Écriture JSON sur stdout...")
        print(json.dumps(output_data, indent=2, ensure_ascii=False))
        
        log(f"✅ Export réussi!")
        log(f"📊 Statistiques:")
        log(f"   • Nœuds avec voisins: {stats.get('nodes_with_neighbors', 0)}/{total_nodes}")
        log(f"   • Total entrées voisins: {stats.get('total_neighbor_entries', 0)}")
        if total_nodes > 0:
            log(f"   • Moyenne voisins/nœud: {stats.get('average_neighbors', 0):.1f}")
        
        persistence.close()
        return True
        
    except Exception as e:
        log(f"✗ Erreur : {e}")
        import traceback
        log(traceback.format_exc())
        return False

if __name__ == "__main__":
    # Configuration
    DB_PATH = "../traffic_history.db"  # Relative to map/ directory
    HOURS = 48  # 48 hours of data
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] in ['--help', '-h']:
            log("Usage: export_neighbors_from_db.py [db_path] [hours]")
            log("  db_path: Path to traffic_history.db (default: ../traffic_history.db)")
            log("  hours: Hours of data to export (default: 48)")
            log("")
            log("Output: JSON data on stdout, logs on stderr")
            sys.exit(0)
        DB_PATH = sys.argv[1]
    
    if len(sys.argv) > 2:
        try:
            HOURS = int(sys.argv[2])
        except ValueError:
            log(f"⚠️  Invalid hours value: {sys.argv[2]}, using default: 48")
            HOURS = 48
    
    # Export data
    success = export_from_database(DB_PATH, HOURS)
    sys.exit(0 if success else 1)
