#!/usr/bin/env python3
"""
Script pour migrer les paquets en mémoire vers la base de données SQLite.
À exécuter si la base de données a été corrompue/supprimée mais que les paquets
sont toujours en mémoire dans le bot.
"""

import pickle
import os
import sys
from traffic_persistence import TrafficPersistence
from traffic_monitor import TrafficMonitor
from utils import info_print, error_print

def migrate_packets():
    """
    Migrer les paquets depuis la mémoire du TrafficMonitor vers SQLite.
    """
    info_print("=== Migration des paquets vers SQLite ===")

    # Créer une instance de persistence
    persistence = TrafficPersistence()

    # Vérifier s'il y a un fichier de sauvegarde pickle
    pickle_files = [
        'traffic_monitor_state.pkl',
        'all_packets.pkl',
        '/tmp/traffic_backup.pkl'
    ]

    packets_found = False

    for pickle_file in pickle_files:
        if os.path.exists(pickle_file):
            try:
                info_print(f"Chargement depuis {pickle_file}...")
                with open(pickle_file, 'rb') as f:
                    data = pickle.load(f)

                if isinstance(data, list):
                    packets = data
                elif isinstance(data, dict) and 'all_packets' in data:
                    packets = data['all_packets']
                else:
                    error_print(f"Format non reconnu dans {pickle_file}")
                    continue

                info_print(f"Trouvé {len(packets)} paquets")

                # Sauvegarder dans SQLite
                saved = 0
                for packet in packets:
                    try:
                        persistence.save_packet(packet)
                        saved += 1
                        if saved % 100 == 0:
                            info_print(f"  {saved}/{len(packets)} paquets sauvegardés...")
                    except Exception as e:
                        error_print(f"Erreur sauvegarde paquet: {e}")

                info_print(f"✅ {saved}/{len(packets)} paquets migrés vers SQLite")
                packets_found = True
                break

            except Exception as e:
                error_print(f"Erreur lecture {pickle_file}: {e}")

    if not packets_found:
        info_print("Aucun fichier de sauvegarde trouvé.")
        info_print("Les paquets en mémoire seront automatiquement sauvegardés dans SQLite")
        info_print("au fur et à mesure de leur réception.")

    # Afficher le nombre de paquets dans la DB
    try:
        import sqlite3
        conn = sqlite3.connect('traffic_history.db')
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM packets')
        total = cursor.fetchone()[0]
        info_print(f"\n📦 Total de paquets dans SQLite: {total}")

        cursor.execute('SELECT packet_type, COUNT(*) FROM packets GROUP BY packet_type')
        by_type = cursor.fetchall()
        info_print("\nPar type:")
        for packet_type, count in by_type:
            info_print(f"  {packet_type}: {count}")

        conn.close()
    except Exception as e:
        error_print(f"Erreur vérification DB: {e}")

if __name__ == '__main__':
    migrate_packets()
