#!/usr/bin/env python3
"""
Script de diagnostic pour vérifier le stockage et la collecte des paquets.
Affiche l'état de la base de données SQLite et la mémoire du TrafficMonitor.
"""

import sqlite3
import os
import sys
from datetime import datetime, timedelta
import time

def main():
    print("=" * 60)
    print("📊 DIAGNOSTIC DU SYSTÈME DE PAQUETS")
    print("=" * 60)

    # 1. Vérifier la base de données SQLite
    db_path = 'traffic_history.db'

    print(f"\n1️⃣  BASE DE DONNÉES: {db_path}")
    print("-" * 60)

    if not os.path.exists(db_path):
        print("❌ Base de données inexistante")
        return

    size = os.path.getsize(db_path)
    print(f"   Taille: {size:,} octets ({size / 1024:.1f} KB)")

    if size == 0:
        print("   ❌ Base de données vide (corrompue)")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Vérifier l'intégrité
        cursor.execute("PRAGMA integrity_check")
        integrity = cursor.fetchone()[0]
        if integrity == 'ok':
            print("   ✅ Intégrité: OK")
        else:
            print(f"   ❌ Intégrité compromise: {integrity}")

        # Compter les paquets totaux
        cursor.execute('SELECT COUNT(*) FROM packets')
        total = cursor.fetchone()[0]
        print(f"\n   📦 Total paquets: {total}")

        if total == 0:
            print("   ⚠️  Aucun paquet dans la base de données")
            print("   💡 Raisons possibles:")
            print("      - Le bot vient de redémarrer")
            print("      - Aucun paquet n'a été reçu")
            print("      - Problème de sauvegarde dans add_packet()")
            conn.close()
            return

        # Compter par type
        cursor.execute('SELECT packet_type, COUNT(*) FROM packets GROUP BY packet_type ORDER BY COUNT(*) DESC')
        by_type = cursor.fetchall()
        print("\n   📊 Paquets par type:")
        for ptype, count in by_type:
            pct = (count / total * 100) if total > 0 else 0
            print(f"      {ptype:25s}: {count:5d} ({pct:5.1f}%)")

        # Paquets récents (dernières 24h)
        cutoff_24h = (datetime.now() - timedelta(hours=24)).timestamp()
        cursor.execute('SELECT COUNT(*) FROM packets WHERE timestamp >= ?', (cutoff_24h,))
        recent_24h = cursor.fetchone()[0]
        print(f"\n   🕐 Dernières 24h: {recent_24h} paquets")

        # Paquets très récents (dernière heure)
        cutoff_1h = (datetime.now() - timedelta(hours=1)).timestamp()
        cursor.execute('SELECT COUNT(*) FROM packets WHERE timestamp >= ?', (cutoff_1h,))
        recent_1h = cursor.fetchone()[0]
        print(f"   🕐 Dernière heure: {recent_1h} paquets")

        # Les 5 paquets les plus récents
        cursor.execute('''
            SELECT timestamp, from_id, packet_type, source
            FROM packets
            ORDER BY timestamp DESC
            LIMIT 5
        ''')
        recent = cursor.fetchall()

        print(f"\n   🕒 5 paquets les plus récents:")
        for ts, from_id, ptype, source in recent:
            dt = datetime.fromtimestamp(ts)
            age = time.time() - ts
            age_str = f"{age/60:.0f}min" if age < 3600 else f"{age/3600:.1f}h"
            print(f"      {dt.strftime('%H:%M:%S')} ({age_str} ago) - {from_id:12s} - {ptype:20s} - {source}")

        # Nœuds actifs
        cursor.execute('SELECT COUNT(DISTINCT from_id) FROM packets WHERE timestamp >= ?', (cutoff_24h,))
        active_nodes = cursor.fetchone()[0]
        print(f"\n   👥 Nœuds actifs (24h): {active_nodes}")

        conn.close()

    except Exception as e:
        print(f"   ❌ Erreur d'accès à la DB: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("💡 RECOMMANDATIONS:")
    print("=" * 60)

    if total == 0:
        print("• La base est vide. Vérifiez que:")
        print("  1. Le bot Meshtastic est bien connecté (serial/TCP)")
        print("  2. Des paquets sont reçus sur le réseau mesh")
        print("  3. La fonction add_packet() est bien appelée")
        print("  4. Consultez les logs du bot pour les erreurs")
    elif recent_1h == 0:
        print("• Aucun paquet récent (dernière heure)")
        print("  1. Le bot est peut-être déconnecté")
        print("  2. Vérifiez la connexion Meshtastic")
    elif recent_24h < 10:
        print("• Peu de paquets sur 24h")
        print("  1. Réseau mesh peu actif ?")
        print("  2. Vérifiez que tous les types de paquets sont capturés")
    else:
        print("✅ Le système fonctionne correctement")
        print(f"   {recent_24h} paquets sur 24h, {active_nodes} nœuds actifs")

if __name__ == '__main__':
    main()
