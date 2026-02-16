#!/usr/bin/env python3
"""
Démonstration de la commande /db nb
Affiche les résultats formatés pour mesh et telegram
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import os
import sys
import sqlite3
import time

def create_demo_db(db_path="demo_neighbors.db"):
    """Créer une DB de démo avec des données de voisinage réalistes"""
    if os.path.exists(db_path):
        os.remove(db_path)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS neighbors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            node_id TEXT NOT NULL,
            neighbor_id TEXT NOT NULL,
            snr REAL,
            last_rx_time INTEGER,
            node_broadcast_interval INTEGER
        )
    ''')
    
    # Données de démo réalistes
    neighbors_data = [
        # tigrog2 (nœud principal) - 5 voisins
        ("!16fad3dc", "!12345678", 9.5, int(time.time()), 900, time.time() - 300),
        ("!16fad3dc", "!87654321", 8.2, int(time.time()), 900, time.time() - 300),
        ("!16fad3dc", "!abcdef12", 7.8, int(time.time()), 900, time.time() - 300),
        ("!16fad3dc", "!11111111", 6.5, int(time.time()), 900, time.time() - 300),
        ("!16fad3dc", "!22222222", 8.9, int(time.time()), 900, time.time() - 300),
        
        # Node proche - 4 voisins
        ("!12345678", "!16fad3dc", 9.3, int(time.time()), 900, time.time() - 600),
        ("!12345678", "!87654321", 7.1, int(time.time()), 900, time.time() - 600),
        ("!12345678", "!abcdef12", 6.8, int(time.time()), 900, time.time() - 600),
        ("!12345678", "!11111111", 5.5, int(time.time()), 900, time.time() - 600),
        
        # Node moyen - 3 voisins
        ("!87654321", "!16fad3dc", 8.0, int(time.time()), 900, time.time() - 1200),
        ("!87654321", "!12345678", 7.0, int(time.time()), 900, time.time() - 1200),
        ("!87654321", "!abcdef12", 6.2, int(time.time()), 900, time.time() - 1200),
        
        # Node distant - 2 voisins
        ("!abcdef12", "!16fad3dc", 7.5, int(time.time()), 900, time.time() - 1800),
        ("!abcdef12", "!12345678", 6.5, int(time.time()), 900, time.time() - 1800),
        
        # Node isolé - 1 voisin
        ("!11111111", "!16fad3dc", 6.0, int(time.time()), 900, time.time() - 2400),
        
        # Node très isolé - 1 voisin
        ("!22222222", "!16fad3dc", 5.8, int(time.time()), 900, time.time() - 3000),
    ]
    
    for node_id, neighbor_id, snr, last_rx, interval, timestamp in neighbors_data:
        cursor.execute("""
            INSERT INTO neighbors (node_id, neighbor_id, snr, last_rx_time, node_broadcast_interval, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (node_id, neighbor_id, snr, last_rx, interval, timestamp))
    
    conn.commit()
    return conn


def simulate_get_neighbors_stats(conn, channel='mesh'):
    """Simuler l'exécution de _get_neighbors_stats"""
    cursor = conn.cursor()
    
    # Compter les entrées totales
    cursor.execute("SELECT COUNT(*) FROM neighbors")
    total_entries = cursor.fetchone()[0]
    
    if total_entries == 0:
        if channel == 'mesh':
            return "👥 Aucune donnée voisinage"
        else:
            return "👥 **AUCUNE DONNÉE DE VOISINAGE**"
    
    # Compter les nœuds uniques
    cursor.execute("SELECT COUNT(DISTINCT node_id) FROM neighbors")
    unique_nodes = cursor.fetchone()[0]
    
    # Compter les relations uniques
    cursor.execute("""
        SELECT COUNT(DISTINCT node_id || '-' || neighbor_id) 
        FROM neighbors
    """)
    unique_relationships = cursor.fetchone()[0]
    
    # Plage temporelle
    cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM neighbors")
    result = cursor.fetchone()
    min_ts, max_ts = result
    from datetime import datetime
    oldest = datetime.fromtimestamp(min_ts).strftime('%d/%m %H:%M')
    newest = datetime.fromtimestamp(max_ts).strftime('%d/%m %H:%M')
    span_hours = (max_ts - min_ts) / 3600
    
    # Moyenne de voisins par nœud
    avg_neighbors = unique_relationships / unique_nodes if unique_nodes > 0 else 0
    
    # Top 5 des nœuds
    cursor.execute("""
        SELECT node_id, COUNT(DISTINCT neighbor_id) as neighbor_count
        FROM neighbors
        GROUP BY node_id
        ORDER BY neighbor_count DESC
        LIMIT 5
    """)
    top_nodes = cursor.fetchall()
    
    # Format selon canal
    if channel == 'mesh':
        lines = [
            f"👥 Voisinage:",
            f"{unique_nodes}nœuds {unique_relationships}liens",
            f"{total_entries}entrées",
            f"Moy:{avg_neighbors:.1f}v/nœud"
        ]
    else:  # telegram
        lines = [
            "👥 **STATISTIQUES DE VOISINAGE**",
            "=" * 50,
            "",
            f"📊 **Données globales:**",
            f"• Total entrées: {total_entries:,}",
            f"• Nœuds avec voisins: {unique_nodes:,}",
            f"• Relations uniques: {unique_relationships:,}",
            f"• Moyenne voisins/nœud: {avg_neighbors:.2f}",
            "",
            f"⏰ **Plage temporelle:**",
            f"• Plus ancien: {oldest}",
            f"• Plus récent: {newest}",
            f"• Durée: {span_hours:.1f} heures",
        ]
        
        if top_nodes:
            lines.append("")
            lines.append("🏆 **Top 5 nœuds (plus de voisins):**")
            for node_id, count in top_nodes:
                lines.append(f"• {node_id}: {count} voisins")
    
    return "\n".join(lines)


if __name__ == "__main__":
    print("=" * 70)
    print("DÉMONSTRATION: /db nb (neighbors stats)")
    print("=" * 70)
    
    conn = create_demo_db()
    
    print("\n📱 FORMAT MESH (compact, <= 180 chars):")
    print("-" * 70)
    mesh_output = simulate_get_neighbors_stats(conn, channel='mesh')
    print(mesh_output)
    print(f"\nLongueur: {len(mesh_output)} caractères")
    
    print("\n" + "=" * 70)
    print("\n💬 FORMAT TELEGRAM (détaillé):")
    print("-" * 70)
    telegram_output = simulate_get_neighbors_stats(conn, channel='telegram')
    print(telegram_output)
    print(f"\nLongueur: {len(telegram_output)} caractères")
    
    print("\n" + "=" * 70)
    print("\n✅ Démonstration terminée")
    
    conn.close()
    os.remove("demo_neighbors.db")
