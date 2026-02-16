#!/usr/bin/env python3
"""
Démonstration de l'utilité des champs hop_limit et hop_start
Ces champs permettent une analyse plus fine du routage mesh.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import sys
from datetime import datetime, timedelta


def analyze_hop_patterns(db_path='traffic_history.db'):
    """
    Analyse les patterns de routage en utilisant hop_limit et hop_start.
    """
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print("=== Analyse des Patterns de Routage Mesh ===\n")
        
        # Vérifier que les colonnes existent
        cursor.execute("PRAGMA table_info(packets)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'hop_limit' not in columns or 'hop_start' not in columns:
            print("❌ Les colonnes hop_limit et hop_start n'existent pas encore.")
            print("   Exécutez le bot une fois pour déclencher la migration.")
            return
        
        print("✅ Colonnes hop_limit et hop_start présentes\n")
        
        # 1. Statistiques générales sur les hops
        print("1. Statistiques de Routage\n")
        
        # Paquets avec données hop complètes
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                AVG(hops) as avg_hops,
                MIN(hops) as min_hops,
                MAX(hops) as max_hops
            FROM packets
            WHERE hop_limit IS NOT NULL AND hop_start IS NOT NULL
        """)
        row = cursor.fetchone()
        
        if row and row['total'] > 0:
            print(f"   Paquets avec données hop complètes: {row['total']}")
            print(f"   Nombre moyen de sauts: {row['avg_hops']:.2f}")
            print(f"   Sauts minimum: {row['min_hops']}")
            print(f"   Sauts maximum: {row['max_hops']}")
        else:
            print("   Aucun paquet avec données hop complètes encore.")
        
        print()
        
        # 2. Distribution des hop_start (configuration TTL initiale)
        print("2. Configuration TTL Initiale (hop_start)\n")
        
        cursor.execute("""
            SELECT 
                hop_start,
                COUNT(*) as count,
                ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM packets WHERE hop_start IS NOT NULL), 1) as percentage
            FROM packets
            WHERE hop_start IS NOT NULL
            GROUP BY hop_start
            ORDER BY count DESC
        """)
        
        ttl_configs = cursor.fetchall()
        if ttl_configs:
            print("   TTL   Paquets  %")
            print("   ----  -------  -----")
            for row in ttl_configs:
                print(f"   {row['hop_start']:4d}  {row['count']:7d}  {row['percentage']:5.1f}%")
        else:
            print("   Aucune donnée TTL disponible encore.")
        
        print()
        
        # 3. Analyse de l'épuisement des hops (hop_limit = 0)
        print("3. Paquets en Limite de Portée (hop_limit = 0)\n")
        
        cursor.execute("""
            SELECT 
                COUNT(*) as exhausted_count,
                ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM packets WHERE hop_limit IS NOT NULL), 1) as percentage
            FROM packets
            WHERE hop_limit = 0
        """)
        row = cursor.fetchone()
        
        if row and row['exhausted_count'] is not None:
            print(f"   Paquets ayant atteint leur limite: {row['exhausted_count']} ({row['percentage']}%)")
            if row['percentage'] > 10:
                print("   ⚠️  Taux élevé - certains nœuds peuvent être hors de portée")
        else:
            print("   Aucune donnée disponible.")
        
        print()
        
        # 4. Analyse par nœud source
        print("4. Top 10 Nœuds par Hops Moyens\n")
        
        cursor.execute("""
            SELECT 
                from_id,
                sender_name,
                COUNT(*) as packet_count,
                AVG(hops) as avg_hops,
                AVG(hop_start) as avg_hop_start,
                AVG(hop_limit) as avg_hop_limit
            FROM packets
            WHERE hop_limit IS NOT NULL AND hop_start IS NOT NULL
            GROUP BY from_id
            HAVING packet_count >= 5
            ORDER BY avg_hops DESC
            LIMIT 10
        """)
        
        nodes = cursor.fetchall()
        if nodes:
            print("   Nœud ID      Nom             Paquets  Hops Moy  Start  Limit")
            print("   -----------  --------------  -------  --------  -----  -----")
            for row in nodes:
                node_id = row['from_id'] or 'N/A'
                node_name = row['sender_name'] or 'Inconnu'
                print(f"   {node_id:11s}  {node_name:14s}  {row['packet_count']:7d}  {row['avg_hops']:8.2f}  {row['avg_hop_start']:5.1f}  {row['avg_hop_limit']:5.1f}")
        else:
            print("   Aucune donnée suffisante.")
        
        print()
        
        # 5. Exemples de paquets avec info hop complète
        print("5. Exemples de Paquets Récents (avec hop data)\n")
        
        cursor.execute("""
            SELECT 
                timestamp,
                from_id,
                sender_name,
                packet_type,
                hop_start,
                hop_limit,
                hops
            FROM packets
            WHERE hop_limit IS NOT NULL AND hop_start IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT 5
        """)
        
        recent = cursor.fetchall()
        if recent:
            for row in recent:
                ts = datetime.fromtimestamp(row['timestamp']).strftime('%H:%M:%S')
                node = row['sender_name'] or row['from_id']
                ptype = row['packet_type']
                print(f"   [{ts}] {node} - {ptype}")
                print(f"      hop_start={row['hop_start']}, hop_limit={row['hop_limit']}, hops={row['hops']}")
        else:
            print("   Aucun paquet récent avec données hop.")
        
        print()
        
        # 6. Utilité pour le débogage
        print("6. Cas d'Usage pour le Débogage\n")
        print("   • hop_start: Configuration TTL initiale du nœud émetteur")
        print("   • hop_limit: TTL restant (nombre de sauts encore possibles)")
        print("   • hops (calculé): Nombre de sauts effectués = hop_start - hop_limit")
        print()
        print("   Exemple d'analyse:")
        print("   - Si hop_limit = 0: paquet en limite de portée")
        print("   - Si hops > 3: paquet très relayé, source probablement loin")
        print("   - Si hop_start varie: différentes configs TTL dans le réseau")
        print("   - Permet de détecter les zones mal couvertes")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"❌ Erreur SQLite: {e}")
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'traffic_history.db'
    print(f"Base de données: {db_path}\n")
    analyze_hop_patterns(db_path)
