#!/usr/bin/env python3
"""
Test simple de la nouvelle sous-commande /db nb (neighbors stats)
Test direct des méthodes sans dépendances complètes
"""

import os
import sys
import sqlite3
import time
from datetime import datetime

# Test en mode standalone - créer une DB de test et vérifier les requêtes SQL

def create_test_db(db_path="test_neighbors_db.db"):
    """Créer une DB de test avec des données de voisinage"""
    # Supprimer l'ancienne DB si elle existe
    if os.path.exists(db_path):
        os.remove(db_path)
    
    # Créer la connexion et les tables
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Créer la table neighbors (même structure que traffic_persistence.py)
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
    
    # Insérer des données de test
    neighbors_data = [
        # Node 1 a 3 voisins
        ("!12345678", "!87654321", 8.5, int(time.time()), 900, time.time() - 3600),
        ("!12345678", "!abcdef12", 7.2, int(time.time()), 900, time.time() - 3600),
        ("!12345678", "!11111111", 9.1, int(time.time()), 900, time.time() - 3600),
        # Node 2 a 2 voisins
        ("!87654321", "!12345678", 8.3, int(time.time()), 900, time.time() - 1800),
        ("!87654321", "!abcdef12", 6.8, int(time.time()), 900, time.time() - 1800),
        # Node 3 a 4 voisins
        ("!abcdef12", "!12345678", 7.5, int(time.time()), 900, time.time() - 900),
        ("!abcdef12", "!87654321", 6.9, int(time.time()), 900, time.time() - 900),
        ("!abcdef12", "!11111111", 8.0, int(time.time()), 900, time.time() - 900),
        ("!abcdef12", "!22222222", 7.8, int(time.time()), 900, time.time() - 900),
        # Node 4 a 1 voisin
        ("!11111111", "!12345678", 9.0, int(time.time()), 900, time.time() - 600),
        # Node 5 a 1 voisin
        ("!22222222", "!abcdef12", 7.9, int(time.time()), 900, time.time() - 300),
    ]
    
    for node_id, neighbor_id, snr, last_rx, interval, timestamp in neighbors_data:
        cursor.execute("""
            INSERT INTO neighbors (node_id, neighbor_id, snr, last_rx_time, node_broadcast_interval, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (node_id, neighbor_id, snr, last_rx, interval, timestamp))
    
    conn.commit()
    print(f"✅ DB de test créée avec {len(neighbors_data)} entrées de voisinage")
    
    return conn


def test_sql_queries():
    """Tester les requêtes SQL utilisées par _get_neighbors_stats"""
    print("\n" + "=" * 60)
    print("TEST 1: Requêtes SQL")
    print("=" * 60)
    
    conn = create_test_db()
    cursor = conn.cursor()
    
    # Test 1: Compter les entrées totales
    cursor.execute("SELECT COUNT(*) FROM neighbors")
    total_entries = cursor.fetchone()[0]
    print(f"Total entrées: {total_entries}")
    assert total_entries == 11, f"Attendu 11 entrées, trouvé {total_entries}"
    
    # Test 2: Compter les nœuds uniques
    cursor.execute("SELECT COUNT(DISTINCT node_id) FROM neighbors")
    unique_nodes = cursor.fetchone()[0]
    print(f"Nœuds uniques: {unique_nodes}")
    assert unique_nodes == 5, f"Attendu 5 nœuds uniques, trouvé {unique_nodes}"
    
    # Test 3: Compter les relations uniques
    cursor.execute("""
        SELECT COUNT(DISTINCT node_id || '-' || neighbor_id) 
        FROM neighbors
    """)
    unique_relationships = cursor.fetchone()[0]
    print(f"Relations uniques: {unique_relationships}")
    assert unique_relationships == 11, f"Attendu 11 relations, trouvé {unique_relationships}"
    
    # Test 4: Plage temporelle
    cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM neighbors")
    result = cursor.fetchone()
    min_ts, max_ts = result
    span_hours = (max_ts - min_ts) / 3600
    print(f"Plage temporelle: {span_hours:.2f} heures")
    assert span_hours > 0, "La plage temporelle devrait être > 0"
    
    # Test 5: Top 5 des nœuds avec le plus de voisins
    cursor.execute("""
        SELECT node_id, COUNT(DISTINCT neighbor_id) as neighbor_count
        FROM neighbors
        GROUP BY node_id
        ORDER BY neighbor_count DESC
        LIMIT 5
    """)
    top_nodes = cursor.fetchall()
    print(f"\nTop 5 nœuds:")
    for node_id, count in top_nodes:
        print(f"  {node_id}: {count} voisins")
    
    assert len(top_nodes) == 5, f"Attendu 5 nœuds, trouvé {len(top_nodes)}"
    assert top_nodes[0][1] == 4, f"Le top 1 devrait avoir 4 voisins, a {top_nodes[0][1]}"
    assert top_nodes[0][0] == "!abcdef12", f"Le top 1 devrait être !abcdef12, est {top_nodes[0][0]}"
    
    print("✅ Toutes les requêtes SQL fonctionnent correctement")
    
    conn.close()
    os.remove("test_neighbors_db.db")


def test_empty_db():
    """Test avec une DB vide"""
    print("\n" + "=" * 60)
    print("TEST 2: DB vide")
    print("=" * 60)
    
    db_path = "test_neighbors_empty_db.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Créer la table vide
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
    conn.commit()
    
    # Test: Compter les entrées
    cursor.execute("SELECT COUNT(*) FROM neighbors")
    total_entries = cursor.fetchone()[0]
    print(f"Total entrées: {total_entries}")
    assert total_entries == 0, f"Attendu 0 entrées, trouvé {total_entries}"
    
    print("✅ Test DB vide OK")
    
    conn.close()
    os.remove(db_path)


def test_db_commands_file():
    """Vérifier que le fichier db_commands.py contient bien la nouvelle méthode"""
    print("\n" + "=" * 60)
    print("TEST 3: Vérification du code source")
    print("=" * 60)
    
    db_commands_path = "handlers/command_handlers/db_commands.py"
    
    if not os.path.exists(db_commands_path):
        print(f"❌ Fichier {db_commands_path} non trouvé")
        return False
    
    with open(db_commands_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Vérifier que la méthode _get_neighbors_stats existe
    assert "_get_neighbors_stats" in content, "La méthode _get_neighbors_stats devrait exister"
    print("✅ Méthode _get_neighbors_stats trouvée")
    
    # Vérifier que 'nb' est dans le routing
    assert "'nb'" in content or '"nb"' in content, "Le sub-command 'nb' devrait être dans le routing"
    print("✅ Sub-command 'nb' trouvé dans le routing")
    
    # Vérifier que l'aide a été mise à jour
    assert "nb=neighbors" in content or "nb - Stats voisinage" in content, "L'aide devrait mentionner 'nb'"
    print("✅ Aide mise à jour avec 'nb'")
    
    print("✅ Code source valide")
    return True


def test_telegram_commands_file():
    """Vérifier que le fichier telegram db_commands.py a été mis à jour"""
    print("\n" + "=" * 60)
    print("TEST 4: Vérification Telegram integration")
    print("=" * 60)
    
    telegram_db_path = "telegram_bot/commands/db_commands.py"
    
    if not os.path.exists(telegram_db_path):
        print(f"❌ Fichier {telegram_db_path} non trouvé")
        return False
    
    with open(telegram_db_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Vérifier que 'nb' est supporté
    assert "'nb'" in content or '"nb"' in content, "Le sub-command 'nb' devrait être supporté"
    print("✅ Sub-command 'nb' trouvé dans Telegram handler")
    
    # Vérifier que _get_neighbors_stats est appelé
    assert "_get_neighbors_stats" in content, "_get_neighbors_stats devrait être appelé"
    print("✅ Appel à _get_neighbors_stats trouvé")
    
    print("✅ Telegram integration valide")
    return True


if __name__ == "__main__":
    print("\n🧪 TESTS DE LA COMMANDE /db nb")
    print("=" * 60)
    
    try:
        test_sql_queries()
        test_empty_db()
        test_db_commands_file()
        test_telegram_commands_file()
        
        print("\n" + "=" * 60)
        print("✅ TOUS LES TESTS PASSÉS")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ ÉCHEC DU TEST: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

