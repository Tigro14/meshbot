#!/usr/bin/env python3
"""
Script CLI pour visualiser le contenu de la base de données traffic_history.db
Usage: python3 view_traffic_db.py [commande]
"""

import sqlite3
import sys
import argparse
from datetime import datetime
from collections import defaultdict
import json

# Couleurs ANSI pour le terminal
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def format_timestamp(ts):
    """Convertit un timestamp en datetime lisible"""
    if ts:
        return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
    return 'N/A'


def format_size(size_bytes):
    """Formate une taille en octets de manière lisible"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def print_header(title):
    """Affiche un en-tête formaté"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 80}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{title.center(80)}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 80}{Colors.ENDC}\n")


def print_section(title):
    """Affiche une section"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{title}{Colors.ENDC}")
    print(f"{Colors.BLUE}{'-' * len(title)}{Colors.ENDC}")


def get_db_connection(db_path='traffic_history.db'):
    """Ouvre une connexion à la base de données"""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"{Colors.RED}❌ Erreur connexion DB: {e}{Colors.ENDC}")
        sys.exit(1)


def show_summary(conn):
    """Affiche un résumé global de la base de données"""
    print_header("📊 RÉSUMÉ DE LA BASE DE DONNÉES")

    cursor = conn.cursor()

    # Informations générales
    print_section("Statistiques générales")

    # Nombre de paquets
    cursor.execute('SELECT COUNT(*) as count FROM packets')
    total_packets = cursor.fetchone()['count']
    print(f"  📦 Total paquets stockés : {Colors.GREEN}{total_packets:,}{Colors.ENDC}")

    # Nombre de messages
    cursor.execute('SELECT COUNT(*) as count FROM public_messages')
    total_messages = cursor.fetchone()['count']
    print(f"  💬 Messages publics : {Colors.GREEN}{total_messages:,}{Colors.ENDC}")

    # Nombre de nœuds
    cursor.execute('SELECT COUNT(*) as count FROM node_stats')
    total_nodes = cursor.fetchone()['count']
    print(f"  🌐 Nœuds uniques : {Colors.GREEN}{total_nodes}{Colors.ENDC}")

    # Période couverte
    cursor.execute('SELECT MIN(timestamp) as oldest, MAX(timestamp) as newest FROM packets')
    row = cursor.fetchone()
    if row['oldest']:
        oldest = format_timestamp(row['oldest'])
        newest = format_timestamp(row['newest'])
        duration = (row['newest'] - row['oldest']) / 3600  # heures
        print(f"  📅 Période : {Colors.YELLOW}{oldest}{Colors.ENDC} → {Colors.YELLOW}{newest}{Colors.ENDC}")
        print(f"  ⏱️  Durée couverte : {Colors.YELLOW}{duration:.1f}h{Colors.ENDC}")

    # Taille de la base
    cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
    db_size = cursor.fetchone()['size']
    print(f"  💾 Taille base de données : {Colors.YELLOW}{format_size(db_size)}{Colors.ENDC}")

    # Répartition par type de paquet
    print_section("Répartition par type de paquet")
    cursor.execute('''
        SELECT packet_type, COUNT(*) as count
        FROM packets
        GROUP BY packet_type
        ORDER BY count DESC
    ''')

    for row in cursor.fetchall():
        ptype = row['packet_type']
        count = row['count']
        percentage = (count / total_packets * 100) if total_packets > 0 else 0
        bar = '█' * int(percentage / 2)
        print(f"  {ptype:25s} {Colors.GREEN}{count:6,}{Colors.ENDC} {Colors.CYAN}({percentage:5.1f}%){Colors.ENDC} {bar}")

    # Top 10 nœuds les plus actifs
    print_section("Top 10 nœuds les plus actifs")
    cursor.execute('''
        SELECT from_id, sender_name, COUNT(*) as count
        FROM packets
        GROUP BY from_id
        ORDER BY count DESC
        LIMIT 10
    ''')

    for i, row in enumerate(cursor.fetchall(), 1):
        from_id = row['from_id']
        name = row['sender_name'] or 'Inconnu'
        count = row['count']
        print(f"  {i:2d}. {Colors.YELLOW}{name:20s}{Colors.ENDC} (!{from_id:08x}) - {Colors.GREEN}{count:,}{Colors.ENDC} paquets")


def show_recent_packets(conn, limit=20):
    """Affiche les derniers paquets reçus"""
    print_header(f"📦 DERNIERS {limit} PAQUETS")

    cursor = conn.cursor()
    cursor.execute('''
        SELECT timestamp, from_id, sender_name, packet_type, source, rssi, snr, hops, message
        FROM packets
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (limit,))

    for row in cursor.fetchall():
        ts = format_timestamp(row['timestamp'])
        name = row['sender_name'] or 'Inconnu'
        ptype = row['packet_type']
        source = row['source'] or '?'
        rssi = row['rssi'] if row['rssi'] is not None else 'N/A'
        snr = row['snr'] if row['snr'] is not None else 'N/A'
        hops = row['hops'] if row['hops'] is not None else 0

        print(f"\n{Colors.BOLD}[{ts}]{Colors.ENDC} {Colors.CYAN}{source:8s}{Colors.ENDC}")
        print(f"  De : {Colors.YELLOW}{name}{Colors.ENDC} (!{row['from_id']:08x})")
        print(f"  Type : {Colors.GREEN}{ptype}{Colors.ENDC}")
        print(f"  Signal : RSSI={rssi} dBm, SNR={snr} dB, Hops={hops}")

        if row['message']:
            msg = row['message'][:100]
            print(f"  Message : {Colors.CYAN}{msg}{Colors.ENDC}")


def show_recent_messages(conn, limit=20):
    """Affiche les derniers messages publics"""
    print_header(f"💬 DERNIERS {limit} MESSAGES PUBLICS")

    cursor = conn.cursor()
    cursor.execute('''
        SELECT timestamp, from_id, sender_name, message, rssi, snr, source
        FROM public_messages
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (limit,))

    for row in cursor.fetchall():
        ts = format_timestamp(row['timestamp'])
        name = row['sender_name'] or 'Inconnu'
        message = row['message'] or ''
        source = row['source'] or '?'
        rssi = row['rssi'] if row['rssi'] is not None else 'N/A'
        snr = row['snr'] if row['snr'] is not None else 'N/A'

        print(f"\n{Colors.BOLD}[{ts}]{Colors.ENDC} {Colors.CYAN}{source:8s}{Colors.ENDC}")
        print(f"  {Colors.YELLOW}{name}{Colors.ENDC} (!{row['from_id']:08x})")
        print(f"  {Colors.GREEN}{message}{Colors.ENDC}")
        print(f"  Signal : RSSI={rssi} dBm, SNR={snr} dB")


def show_node_stats(conn, node_id=None):
    """Affiche les statistiques par nœud"""
    print_header("🌐 STATISTIQUES PAR NŒUD")

    cursor = conn.cursor()

    if node_id:
        # Stats pour un nœud spécifique
        cursor.execute('''
            SELECT * FROM node_stats WHERE node_id = ?
        ''', (node_id,))
        rows = [cursor.fetchone()]
    else:
        # Tous les nœuds
        cursor.execute('''
            SELECT * FROM node_stats ORDER BY total_packets DESC
        ''')
        rows = cursor.fetchall()

    for row in rows:
        if not row:
            print(f"{Colors.RED}Nœud {node_id} non trouvé{Colors.ENDC}")
            continue

        print(f"\n{Colors.BOLD}Nœud : !{row['node_id']:08x}{Colors.ENDC}")
        print(f"  Total paquets : {Colors.GREEN}{row['total_packets']:,}{Colors.ENDC}")
        print(f"  Total octets : {Colors.GREEN}{format_size(row['total_bytes'])}{Colors.ENDC}")
        print(f"  Dernière maj : {Colors.YELLOW}{format_timestamp(row['last_updated'])}{Colors.ENDC}")

        # Types de paquets
        if row['packet_types']:
            packet_types = json.loads(row['packet_types'])
            if packet_types:
                print(f"\n  Types de paquets :")
                for ptype, count in sorted(packet_types.items(), key=lambda x: x[1], reverse=True):
                    print(f"    {ptype:25s} {Colors.CYAN}{count:6,}{Colors.ENDC}")

        # Activité horaire
        if row['hourly_activity']:
            hourly = json.loads(row['hourly_activity'])
            if hourly:
                print(f"\n  Activité horaire (top 5) :")
                for hour, count in sorted(hourly.items(), key=lambda x: int(x[1]), reverse=True)[:5]:
                    print(f"    {hour:02s}h : {Colors.GREEN}{'█' * (count // 10)}{Colors.ENDC} {count}")

        # Stats de messages
        if row['message_stats']:
            msg_stats = json.loads(row['message_stats'])
            if msg_stats and msg_stats.get('count', 0) > 0:
                print(f"\n  Messages :")
                print(f"    Nombre : {Colors.GREEN}{msg_stats.get('count', 0)}{Colors.ENDC}")
                print(f"    Total caractères : {Colors.GREEN}{msg_stats.get('total_chars', 0)}{Colors.ENDC}")
                print(f"    Longueur moyenne : {Colors.GREEN}{msg_stats.get('avg_length', 0):.1f}{Colors.ENDC}")

        # Stats de télémétrie
        if row['telemetry_stats']:
            telem_stats = json.loads(row['telemetry_stats'])
            if telem_stats and telem_stats.get('count', 0) > 0:
                print(f"\n  Télémétrie :")
                print(f"    Nombre : {Colors.GREEN}{telem_stats.get('count', 0)}{Colors.ENDC}")
                if telem_stats.get('last_battery'):
                    print(f"    Batterie : {Colors.YELLOW}{telem_stats['last_battery']}%{Colors.ENDC}")
                if telem_stats.get('last_voltage'):
                    print(f"    Tension : {Colors.YELLOW}{telem_stats['last_voltage']:.2f}V{Colors.ENDC}")
                if telem_stats.get('last_channel_util'):
                    print(f"    Util. canal : {Colors.YELLOW}{telem_stats['last_channel_util']:.1f}%{Colors.ENDC}")


def show_global_stats(conn):
    """Affiche les statistiques globales"""
    print_header("🌍 STATISTIQUES GLOBALES")

    cursor = conn.cursor()

    # Stats globales
    cursor.execute('SELECT * FROM global_stats WHERE id = 1')
    row = cursor.fetchone()

    if row:
        print_section("Statistiques globales")
        print(f"  Total paquets : {Colors.GREEN}{row['total_packets']:,}{Colors.ENDC}")
        print(f"  Total octets : {Colors.GREEN}{format_size(row['total_bytes'])}{Colors.ENDC}")
        print(f"  Dernière réinit : {Colors.YELLOW}{format_timestamp(row['last_reset'])}{Colors.ENDC}")

        if row['unique_nodes']:
            unique_nodes = json.loads(row['unique_nodes'])
            print(f"  Nœuds uniques : {Colors.GREEN}{len(unique_nodes)}{Colors.ENDC}")

        if row['packet_types']:
            packet_types = json.loads(row['packet_types'])
            print_section("Types de paquets")
            for ptype, count in sorted(packet_types.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / row['total_packets'] * 100) if row['total_packets'] > 0 else 0
                bar = '█' * int(percentage / 2)
                print(f"  {ptype:25s} {Colors.GREEN}{count:6,}{Colors.ENDC} {Colors.CYAN}({percentage:5.1f}%){Colors.ENDC} {bar}")

    # Stats réseau
    cursor.execute('SELECT * FROM network_stats WHERE id = 1')
    row = cursor.fetchone()

    if row:
        print_section("Statistiques réseau")
        print(f"  Total hops : {Colors.GREEN}{row['total_hops']:,}{Colors.ENDC}")
        print(f"  Hops max observé : {Colors.GREEN}{row['max_hops_seen']}{Colors.ENDC}")
        print(f"  RSSI moyen : {Colors.YELLOW}{row['avg_rssi']:.1f} dBm{Colors.ENDC}")
        print(f"  SNR moyen : {Colors.YELLOW}{row['avg_snr']:.1f} dB{Colors.ENDC}")
        print(f"  Paquets directs (0 hop) : {Colors.GREEN}{row['packets_direct']:,}{Colors.ENDC}")
        print(f"  Paquets relayés : {Colors.GREEN}{row['packets_relayed']:,}{Colors.ENDC}")


def search_packets(conn, search_term):
    """Recherche dans les paquets"""
    print_header(f"🔍 RECHERCHE : '{search_term}'")

    cursor = conn.cursor()

    # Recherche dans les messages
    cursor.execute('''
        SELECT timestamp, from_id, sender_name, message, source
        FROM packets
        WHERE message LIKE ?
        ORDER BY timestamp DESC
        LIMIT 50
    ''', (f'%{search_term}%',))

    results = cursor.fetchall()

    if results:
        print(f"\n{Colors.GREEN}✓ {len(results)} résultat(s) trouvé(s){Colors.ENDC}\n")
        for row in results:
            ts = format_timestamp(row['timestamp'])
            name = row['sender_name'] or 'Inconnu'
            message = row['message'] or ''
            source = row['source'] or '?'

            # Highlight du terme recherché
            highlighted = message.replace(search_term, f"{Colors.YELLOW}{Colors.BOLD}{search_term}{Colors.ENDC}{Colors.GREEN}")

            print(f"{Colors.BOLD}[{ts}]{Colors.ENDC} {Colors.CYAN}{source:8s}{Colors.ENDC} {Colors.YELLOW}{name}{Colors.ENDC}")
            print(f"  {Colors.GREEN}{highlighted}{Colors.ENDC}\n")
    else:
        print(f"{Colors.RED}✗ Aucun résultat trouvé{Colors.ENDC}")


def main():
    parser = argparse.ArgumentParser(
        description='Visualiseur de base de données traffic_history.db',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples d'utilisation:
  %(prog)s summary              # Résumé global
  %(prog)s packets              # Derniers paquets
  %(prog)s messages             # Derniers messages
  %(prog)s nodes                # Stats par nœud
  %(prog)s global               # Stats globales et réseau
  %(prog)s search "bonjour"     # Rechercher un terme
  %(prog)s node 0x123abc        # Stats d'un nœud spécifique
        """
    )

    parser.add_argument('command', nargs='?', default='summary',
                        choices=['summary', 'packets', 'messages', 'nodes', 'global', 'search', 'node'],
                        help='Commande à exécuter')
    parser.add_argument('args', nargs='*', help='Arguments de la commande')
    parser.add_argument('--db', default='traffic_history.db', help='Chemin vers la base de données')
    parser.add_argument('--limit', type=int, default=20, help='Nombre de résultats à afficher')

    args = parser.parse_args()

    # Connexion à la base
    conn = get_db_connection(args.db)

    try:
        if args.command == 'summary':
            show_summary(conn)
        elif args.command == 'packets':
            show_recent_packets(conn, args.limit)
        elif args.command == 'messages':
            show_recent_messages(conn, args.limit)
        elif args.command == 'nodes':
            show_node_stats(conn)
        elif args.command == 'global':
            show_global_stats(conn)
        elif args.command == 'search':
            if args.args:
                search_packets(conn, ' '.join(args.args))
            else:
                print(f"{Colors.RED}❌ Veuillez spécifier un terme de recherche{Colors.ENDC}")
        elif args.command == 'node':
            if args.args:
                node_id = args.args[0]
                # Convertir en int si nécessaire
                if node_id.startswith('0x'):
                    node_id = int(node_id, 16)
                elif node_id.startswith('!'):
                    node_id = int(node_id[1:], 16)
                else:
                    try:
                        node_id = int(node_id, 16)
                    except:
                        node_id = int(node_id)
                show_node_stats(conn, node_id)
            else:
                print(f"{Colors.RED}❌ Veuillez spécifier un ID de nœud{Colors.ENDC}")

    finally:
        conn.close()

    print()  # Ligne vide finale


if __name__ == '__main__':
    main()
