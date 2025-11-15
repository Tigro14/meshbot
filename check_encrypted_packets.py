#!/usr/bin/env python3
"""
Script de diagnostic pour vérifier les paquets encryptés
"""

import sqlite3
import sys
from datetime import datetime
from collections import defaultdict

def check_encrypted_packets(db_path='traffic_history.db'):
    """Vérifier l'état des paquets encryptés dans la base de données"""

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
    except Exception as e:
        print(f"❌ Erreur connexion DB: {e}")
        return

    print("=" * 70)
    print("🔍 DIAGNOSTIC DES PAQUETS ENCRYPTÉS")
    print("=" * 70)

    # 1. Statistiques globales
    cursor.execute("SELECT COUNT(*) FROM packets")
    total_packets = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM packets WHERE is_encrypted = 1")
    encrypted_packets = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM packets WHERE is_encrypted = 0 OR is_encrypted IS NULL")
    clear_packets = cursor.fetchone()[0]

    print(f"\n📊 STATISTIQUES GLOBALES")
    print(f"  Total paquets dans DB     : {total_packets}")
    print(f"  🔒 Paquets encryptés      : {encrypted_packets} ({encrypted_packets/total_packets*100 if total_packets > 0 else 0:.1f}%)")
    print(f"  📖 Paquets en clair       : {clear_packets} ({clear_packets/total_packets*100 if total_packets > 0 else 0:.1f}%)")

    # 2. Types de paquets
    print(f"\n📦 TYPES DE PAQUETS (Top 10)")
    cursor.execute("""
        SELECT packet_type, COUNT(*) as count, SUM(is_encrypted) as encrypted_count
        FROM packets
        GROUP BY packet_type
        ORDER BY count DESC
        LIMIT 10
    """)

    for row in cursor.fetchall():
        ptype = row['packet_type']
        count = row['count']
        enc_count = row['encrypted_count'] or 0
        enc_pct = enc_count / count * 100 if count > 0 else 0
        enc_icon = '🔒' if enc_count > 0 else '  '
        print(f"  {enc_icon} {ptype:25s} : {count:5d}  ({enc_count:3d} encryptés = {enc_pct:5.1f}%)")

    # 3. Paquets encryptés récents
    if encrypted_packets > 0:
        print(f"\n🔐 PAQUETS ENCRYPTÉS RÉCENTS (derniers 10)")
        cursor.execute("""
            SELECT timestamp, sender_name, packet_type, rssi, snr, hops
            FROM packets
            WHERE is_encrypted = 1
            ORDER BY timestamp DESC
            LIMIT 10
        """)

        for row in cursor.fetchall():
            ts = datetime.fromtimestamp(row['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
            name = row['sender_name'] or 'Unknown'
            ptype = row['packet_type']
            rssi = row['rssi'] or 'N/A'
            snr = row['snr'] or 'N/A'
            hops = row['hops'] or 0
            print(f"  🔒 {ts} | {name:15s} | {ptype:20s} | RSSI:{rssi} SNR:{snr} Hops:{hops}")
    else:
        print(f"\n⚠️  AUCUN PAQUET ENCRYPTÉ DÉTECTÉ")
        print(f"\nPOURQUOI?")
        print(f"  1. Le bot n'a pas encore collecté de paquets encryptés")
        print(f"  2. Tous les nœuds du réseau utilisent le même canal par défaut (non chiffré)")
        print(f"  3. Le bot n'est pas encore en cours d'exécution")
        print(f"\nSOLUTIONS:")
        print(f"  - Vérifier que le bot est actif: systemctl status meshbot")
        print(f"  - Attendre que du trafic soit reçu sur le réseau mesh")
        print(f"  - Vérifier les logs du bot: journalctl -u meshbot -f")
        print(f"  - Sur votre réseau, certains nœuds doivent utiliser un canal secondaire chiffré")

    # 4. Activité récente
    print(f"\n📡 ACTIVITÉ RÉCENTE (derniers 10 paquets)")
    cursor.execute("""
        SELECT timestamp, sender_name, packet_type, is_encrypted, message
        FROM packets
        ORDER BY timestamp DESC
        LIMIT 10
    """)

    for row in cursor.fetchall():
        ts = datetime.fromtimestamp(row['timestamp']).strftime('%H:%M:%S')
        name = row['sender_name'] or 'Unknown'
        ptype = row['packet_type']
        encrypted_icon = '🔒' if row['is_encrypted'] else '  '
        msg = row['message'] or ''
        msg_preview = (msg[:40] + '...') if len(msg) > 40 else msg
        print(f"  {encrypted_icon} {ts} | {name:15s} | {ptype:20s} | {msg_preview}")

    # 5. État de la base de données
    print(f"\n💾 ÉTAT DE LA BASE DE DONNÉES")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f"  Tables: {', '.join([t['name'] for t in tables])}")

    cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM packets")
    row = cursor.fetchone()
    if row[0] and row[1]:
        first = datetime.fromtimestamp(row[0]).strftime('%Y-%m-%d %H:%M:%S')
        last = datetime.fromtimestamp(row[1]).strftime('%Y-%m-%d %H:%M:%S')
        print(f"  Période: {first} → {last}")

    print("\n" + "=" * 70)
    print("✅ Diagnostic terminé")
    print("=" * 70)

    conn.close()

if __name__ == '__main__':
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'traffic_history.db'
    check_encrypted_packets(db_path)
