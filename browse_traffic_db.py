#!/usr/bin/env python3
"""
Navigateur interactif pour traffic_history.db - style lnav
Navigation avec les touches fléchées, recherche, filtrage, etc.

Touches:
  ↑/↓ ou j/k     : Naviguer dans la liste
  PgUp/PgDn      : Page précédente/suivante
  Home/End       : Début/fin de la liste
  ENTER          : Voir les détails d'un paquet
  /              : Rechercher
  f              : Filtrer par type
  e              : Filtrer chiffrement
  s              : Inverser l'ordre de tri
  v              : Changer de vue (packets/messages/nodes)
  r              : Rafraîchir les données
  x              : Exporter vers texte
  c              : Exporter vers CSV
  q ou ESC       : Quitter
  ?              : Aide
"""

import curses
import sqlite3
import sys
from datetime import datetime
from collections import defaultdict
import json
import re
import csv
import os


class TrafficDBBrowser:
    """Navigateur interactif pour la base de données traffic"""

    def __init__(self, db_path='traffic_history.db'):
        self.db_path = db_path
        self.conn = None
        self.current_view = 'packets'  # packets, messages, nodes
        self.current_row = 0
        self.scroll_offset = 0
        self.items = []
        self.filter_type = None
        self.search_term = None
        self.filter_encrypted = 'all'  # 'all', 'only', 'exclude'
        self.sort_order = 'desc'  # 'desc' (newest first) or 'asc' (oldest first)
        self.detail_mode = False
        self.detail_scroll = 0

    def connect_db(self):
        """Connexion à la base de données"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            return True
        except Exception as e:
            return False

    def load_packets(self):
        """Charge les paquets depuis la DB"""
        cursor = self.conn.cursor()

        query = 'SELECT * FROM packets'
        params = []
        conditions = []

        # Appliquer le filtre de type
        if self.filter_type:
            conditions.append('packet_type = ?')
            params.append(self.filter_type)

        # Appliquer le filtre de chiffrement
        if self.filter_encrypted == 'only':
            conditions.append('is_encrypted = 1')
        elif self.filter_encrypted == 'exclude':
            conditions.append('(is_encrypted = 0 OR is_encrypted IS NULL)')

        # Appliquer la recherche
        if self.search_term:
            conditions.append('message LIKE ?')
            params.append(f'%{self.search_term}%')

        # Construire la clause WHERE
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)

        # Appliquer l'ordre de tri
        order = 'DESC' if self.sort_order == 'desc' else 'ASC'
        query += f' ORDER BY timestamp {order} LIMIT 1000'

        cursor.execute(query, params)
        self.items = [dict(row) for row in cursor.fetchall()]

    def load_messages(self):
        """Charge les messages publics depuis la DB"""
        cursor = self.conn.cursor()

        query = 'SELECT * FROM public_messages'
        params = []

        # Appliquer la recherche
        if self.search_term:
            query += ' WHERE message LIKE ?'
            params.append(f'%{self.search_term}%')

        # Appliquer l'ordre de tri
        order = 'DESC' if self.sort_order == 'desc' else 'ASC'
        query += f' ORDER BY timestamp {order} LIMIT 1000'

        cursor.execute(query, params)
        self.items = [dict(row) for row in cursor.fetchall()]

    def load_nodes(self):
        """Charge les statistiques des nœuds depuis la DB"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM node_stats ORDER BY total_packets DESC')
        self.items = [dict(row) for row in cursor.fetchall()]

    def load_data(self):
        """Charge les données selon la vue courante"""
        if self.current_view == 'packets':
            self.load_packets()
        elif self.current_view == 'messages':
            self.load_messages()
        elif self.current_view == 'nodes':
            self.load_nodes()

        # Reset position si on dépasse
        if self.current_row >= len(self.items):
            self.current_row = max(0, len(self.items) - 1)

    def format_timestamp(self, ts):
        """Formate un timestamp"""
        if ts:
            dt = datetime.fromtimestamp(ts)
            return dt.strftime('%m-%d %H:%M:%S')
        return 'N/A'

    def format_node_id(self, node_id):
        """Formate un ID de nœud"""
        if node_id is None:
            return 'unknown'
        if isinstance(node_id, str):
            return node_id.lstrip('!')
        if isinstance(node_id, int):
            return f"{node_id:08x}"
        return str(node_id)

    def truncate(self, text, width):
        """Tronque un texte à une largeur donnée"""
        if text is None:
            return ''
        text = str(text)
        if len(text) > width:
            return text[:width-3] + '...'
        return text

    def draw_header(self, stdscr, height, width):
        """Dessine l'en-tête"""
        # Indicateurs de vue avec icônes et descriptions
        view_info = {
            'packets': ('📦', 'ALL PACKETS', 'Tous les paquets reçus'),
            'messages': ('💬', 'MESSAGES', 'Messages publics broadcast'),
            'nodes': ('🌐', 'NODES', 'Statistiques par nœud')
        }

        icon, view_name, view_desc = view_info.get(self.current_view, ('?', 'UNKNOWN', ''))

        title = f"{icon} {view_name}"
        if self.filter_type:
            title += f" [Filter: {self.filter_type}]"
        if self.filter_encrypted == 'only':
            title += f" [🔒 Encrypted only]"
        elif self.filter_encrypted == 'exclude':
            title += f" [Clear only]"
        if self.search_term:
            title += f" [Search: '{self.search_term}']"
        # Indicateur d'ordre de tri (seulement pour packets et messages)
        if self.current_view in ['packets', 'messages']:
            sort_icon = '↓' if self.sort_order == 'desc' else '↑'
            title += f" [{sort_icon}]"

        # Ligne de titre
        stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
        try:
            stdscr.addstr(0, 0, title.center(width)[:width-1])
        except curses.error:
            pass
        stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)

        # Info compteur + description de la vue
        info = f" {len(self.items)} items"
        if self.items:
            info += f" | Row {self.current_row + 1}/{len(self.items)}"
        info += f" | {view_desc}"
        try:
            stdscr.addstr(1, 0, info[:width-1])
        except curses.error:
            pass

    def draw_footer(self, stdscr, height, width):
        """Dessine le pied de page avec les raccourcis"""
        # Indiquer la prochaine vue dans le cycle
        view_cycle = {'packets': 'Messages', 'messages': 'Nodes', 'nodes': 'Packets'}
        next_view = view_cycle.get(self.current_view, 'View')

        # Indicateur du cycle de chiffrement
        enc_status = {'all': 'All', 'only': '🔒Only', 'exclude': 'Clear'}[self.filter_encrypted]

        # Indicateur d'ordre de tri
        sort_icon = '↓' if self.sort_order == 'desc' else '↑'

        footer = f"↑/↓:Nav ENTER:Details /:Search f:Type e:Enc({enc_status}) s:Sort{sort_icon} x:TXT c:CSV v:→{next_view} r:Refresh q:Quit"
        stdscr.attron(curses.color_pair(2))
        # Ne pas remplir le dernier caractère pour éviter l'erreur curses
        try:
            stdscr.addstr(height - 1, 0, footer[:width-1].ljust(width-1))
        except curses.error:
            pass
        stdscr.attroff(curses.color_pair(2))

    def draw_packet_line(self, stdscr, y, x, width, item, is_selected):
        """Dessine une ligne de paquet"""
        ts = self.format_timestamp(item.get('timestamp'))
        name = (item.get('sender_name') or 'Unknown')[:15]
        ptype = (item.get('packet_type') or 'N/A')[:20]
        source = (item.get('source') or '?')[:8]

        # Indicateur de chiffrement
        encrypted_icon = '🔒' if item.get('is_encrypted') else '  '

        msg = self.truncate(item.get('message') or '', width - 73)

        line = f"{ts} {source:8s} {name:15s} {ptype:20s} {encrypted_icon} {msg}"

        attr = curses.A_REVERSE if is_selected else curses.A_NORMAL
        try:
            stdscr.addstr(y, x, line[:width], attr)
        except curses.error:
            pass

    def draw_message_line(self, stdscr, y, x, width, item, is_selected):
        """Dessine une ligne de message"""
        ts = self.format_timestamp(item.get('timestamp'))
        name = (item.get('sender_name') or 'Unknown')[:15]
        source = (item.get('source') or '?')[:8]
        msg = self.truncate(item.get('message') or '', width - 45)

        line = f"{ts} {source:8s} {name:15s} {msg}"

        attr = curses.A_REVERSE if is_selected else curses.A_NORMAL
        try:
            stdscr.addstr(y, x, line[:width], attr)
        except curses.error:
            pass

    def draw_node_line(self, stdscr, y, x, width, item, is_selected):
        """Dessine une ligne de nœud"""
        node_id = self.format_node_id(item.get('node_id'))[:8]
        packets = item.get('total_packets', 0)
        size = item.get('total_bytes', 0) // 1024  # KB

        line = f"!{node_id:8s}  Packets: {packets:6,}  Size: {size:6,} KB"

        attr = curses.A_REVERSE if is_selected else curses.A_NORMAL
        try:
            stdscr.addstr(y, x, line[:width], attr)
        except curses.error:
            pass

    def draw_list(self, stdscr, height, width):
        """Dessine la liste d'items"""
        list_height = height - 4  # Header (2) + Column header (1) + Footer (1)
        start_y = 3  # Commence après l'en-tête de colonne

        # Dessiner l'en-tête de colonnes
        try:
            stdscr.attron(curses.A_BOLD)
            if self.current_view == 'packets':
                header = "Timestamp    Source   Sender          Type                    Message"
            elif self.current_view == 'messages':
                header = "Timestamp    Source   Sender          Message"
            elif self.current_view == 'nodes':
                header = "Node ID   Packets       Size"
            stdscr.addstr(2, 0, header[:width-1])
            stdscr.attroff(curses.A_BOLD)
        except curses.error:
            pass

        # Ajuster le scroll si nécessaire
        if self.current_row < self.scroll_offset:
            self.scroll_offset = self.current_row
        elif self.current_row >= self.scroll_offset + list_height:
            self.scroll_offset = self.current_row - list_height + 1

        # Dessiner les items visibles
        for i in range(list_height):
            item_idx = self.scroll_offset + i
            if item_idx >= len(self.items):
                break

            item = self.items[item_idx]
            is_selected = (item_idx == self.current_row)

            if self.current_view == 'packets':
                self.draw_packet_line(stdscr, start_y + i, 0, width, item, is_selected)
            elif self.current_view == 'messages':
                self.draw_message_line(stdscr, start_y + i, 0, width, item, is_selected)
            elif self.current_view == 'nodes':
                self.draw_node_line(stdscr, start_y + i, 0, width, item, is_selected)

    def draw_detail_view(self, stdscr, height, width):
        """Dessine la vue détaillée d'un item"""
        if not self.items or self.current_row >= len(self.items):
            return

        item = self.items[self.current_row]
        start_y = 2
        max_lines = height - 3

        lines = []

        if self.current_view == 'packets':
            lines.append("═" * width)
            lines.append(f"PACKET DETAILS")
            lines.append("═" * width)
            lines.append(f"Timestamp    : {self.format_timestamp(item.get('timestamp'))}")
            lines.append(f"From ID      : !{self.format_node_id(item.get('from_id'))}")
            lines.append(f"Sender       : {item.get('sender_name') or 'Unknown'}")
            lines.append(f"To ID        : {item.get('to_id') or 'N/A'}")
            lines.append(f"Source       : {item.get('source') or 'N/A'}")
            lines.append(f"Packet Type  : {item.get('packet_type') or 'N/A'}")
            lines.append(f"RSSI         : {item.get('rssi') or 'N/A'} dBm")
            lines.append(f"SNR          : {item.get('snr') or 'N/A'} dB")
            lines.append(f"Hops         : {item.get('hops') or 0}")
            lines.append(f"Size         : {item.get('size') or 0} bytes")
            lines.append(f"Broadcast    : {'Yes' if item.get('is_broadcast') else 'No'}")

            if item.get('message'):
                lines.append("")
                lines.append("Message:")
                lines.append("─" * width)
                # Découper le message en lignes
                msg = item['message']
                for line in msg.split('\n'):
                    while line:
                        lines.append(line[:width])
                        line = line[width:]

            if item.get('telemetry'):
                lines.append("")
                lines.append("Telemetry:")
                lines.append("─" * width)
                telem = json.loads(item['telemetry']) if isinstance(item['telemetry'], str) else item['telemetry']
                for k, v in telem.items():
                    if v is not None:
                        lines.append(f"  {k:20s}: {v}")

        elif self.current_view == 'messages':
            lines.append("═" * width)
            lines.append(f"MESSAGE DETAILS")
            lines.append("═" * width)
            lines.append(f"Timestamp    : {self.format_timestamp(item.get('timestamp'))}")
            lines.append(f"From ID      : !{self.format_node_id(item.get('from_id'))}")
            lines.append(f"Sender       : {item.get('sender_name') or 'Unknown'}")
            lines.append(f"Source       : {item.get('source') or 'N/A'}")
            lines.append(f"RSSI         : {item.get('rssi') or 'N/A'} dBm")
            lines.append(f"SNR          : {item.get('snr') or 'N/A'} dB")
            lines.append(f"Length       : {item.get('message_length') or 0} chars")
            lines.append("")
            lines.append("Message:")
            lines.append("─" * width)
            msg = item.get('message') or ''
            for line in msg.split('\n'):
                while line:
                    lines.append(line[:width])
                    line = line[width:]

        elif self.current_view == 'nodes':
            lines.append("═" * width)
            lines.append(f"NODE STATISTICS")
            lines.append("═" * width)
            lines.append(f"Node ID      : !{self.format_node_id(item.get('node_id'))}")
            lines.append(f"Total Packets: {item.get('total_packets', 0):,}")
            lines.append(f"Total Bytes  : {item.get('total_bytes', 0):,}")
            lines.append(f"Last Updated : {self.format_timestamp(item.get('last_updated'))}")

            if item.get('packet_types'):
                ptypes = json.loads(item['packet_types']) if isinstance(item['packet_types'], str) else item['packet_types']
                if ptypes:
                    lines.append("")
                    lines.append("Packet Types:")
                    lines.append("─" * width)
                    for ptype, count in sorted(ptypes.items(), key=lambda x: x[1], reverse=True):
                        lines.append(f"  {ptype:30s}: {count:6,}")

            if item.get('message_stats'):
                msg_stats = json.loads(item['message_stats']) if isinstance(item['message_stats'], str) else item['message_stats']
                if msg_stats and msg_stats.get('count', 0) > 0:
                    lines.append("")
                    lines.append("Message Stats:")
                    lines.append("─" * width)
                    lines.append(f"  Count       : {msg_stats.get('count', 0):,}")
                    lines.append(f"  Total chars : {msg_stats.get('total_chars', 0):,}")
                    lines.append(f"  Avg length  : {msg_stats.get('avg_length', 0):.1f}")

        # Dessiner les lignes avec scroll
        for i in range(max_lines):
            line_idx = self.detail_scroll + i
            if line_idx >= len(lines):
                break
            try:
                stdscr.addstr(start_y + i, 0, lines[line_idx][:width])
            except curses.error:
                pass

        # Indicateur de scroll
        if len(lines) > max_lines:
            scroll_info = f" [Line {self.detail_scroll + 1}-{min(self.detail_scroll + max_lines, len(lines))}/{len(lines)}]"
            try:
                stdscr.addstr(1, width - len(scroll_info) - 1, scroll_info)
            except curses.error:
                pass

    def show_help(self, stdscr):
        """Affiche l'aide"""
        help_text = [
            "TRAFFIC DB BROWSER - HELP",
            "",
            "Navigation:",
            "  ↑/↓ or j/k      - Move up/down in list",
            "  PgUp/PgDn       - Page up/down (10 items)",
            "  Home/End        - Jump to first/last item",
            "",
            "Actions:",
            "  ENTER           - View full details of selected item",
            "  /               - Search text in messages (type text + ENTER)",
            "                    Press ESC to cancel search input",
            "  f               - Filter by packet type (packets view only)",
            "  e               - Filter encryption (all/only/exclude encrypted)",
            "  s               - Toggle sort order (newest ↓ / oldest ↑ first)",
            "                    Applies to packets and messages views only",
            "  v               - Switch view mode:",
            "                    📦 Packets  → 💬 Messages → 🌐 Nodes → (cycle)",
            "  r               - Refresh data from database",
            "",
            "Export:",
            "  x               - Export current view to text file (.txt)",
            "                    Includes all filters and current sort order",
            "  c               - Export current view to CSV file (.csv)",
            "                    Structured data for spreadsheet/analysis tools",
            "",
            "Views explained:",
            "  📦 PACKETS      - All received packets (any type)",
            "  💬 MESSAGES     - Public broadcast text messages only",
            "  🌐 NODES        - Aggregated statistics per node",
            "",
            "In detail view:",
            "  ↑/↓             - Scroll through detail text",
            "  ESC or ENTER    - Return to list view",
            "",
            "Other:",
            "  q or ESC        - Quit browser (from list view)",
            "  ?               - Show this help",
            "",
            "Press any key to return..."
        ]

        stdscr.clear()
        height, width = stdscr.getmaxyx()

        for i, line in enumerate(help_text):
            if i >= height - 2:  # Laisser au moins 2 lignes de marge
                break
            try:
                stdscr.addstr(i, 2, line[:width-5])
            except curses.error:
                pass

        stdscr.refresh()
        stdscr.getch()

    def export_to_text(self):
        """Exporte la vue actuelle vers un fichier texte formaté"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"traffic_export_{self.current_view}_{timestamp}.txt"

        try:
            with open(filename, 'w', encoding='utf-8') as f:
                # En-tête
                f.write("=" * 80 + "\n")
                f.write(f"Traffic Database Export - {self.current_view.upper()} View\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total items: {len(self.items)}\n")

                if self.filter_type:
                    f.write(f"Filter: {self.filter_type}\n")
                if self.filter_encrypted != 'all':
                    f.write(f"Encryption filter: {self.filter_encrypted}\n")
                if self.search_term:
                    f.write(f"Search: '{self.search_term}'\n")

                f.write("=" * 80 + "\n\n")

                # Données
                if self.current_view == 'packets':
                    for i, item in enumerate(self.items, 1):
                        ts = datetime.fromtimestamp(item.get('timestamp')).strftime('%Y-%m-%d %H:%M:%S') if item.get('timestamp') else 'N/A'
                        f.write(f"[{i}/{len(self.items)}] {ts}\n")
                        f.write(f"  From: {item.get('sender_name') or 'Unknown'} ({item.get('from_id')})\n")
                        f.write(f"  To: {item.get('to_id')}\n")
                        f.write(f"  Source: {item.get('source')}\n")
                        f.write(f"  Type: {item.get('packet_type')}\n")
                        if item.get('is_encrypted'):
                            f.write(f"  🔒 ENCRYPTED\n")
                        if item.get('message'):
                            f.write(f"  Message: {item.get('message')}\n")
                        if item.get('rssi') is not None:
                            f.write(f"  Signal: RSSI={item.get('rssi')} dBm, SNR={item.get('snr')} dB\n")
                        if item.get('hops') is not None:
                            f.write(f"  Hops: {item.get('hops')}\n")
                        f.write("\n")

                elif self.current_view == 'messages':
                    for i, item in enumerate(self.items, 1):
                        ts = datetime.fromtimestamp(item.get('timestamp')).strftime('%Y-%m-%d %H:%M:%S') if item.get('timestamp') else 'N/A'
                        f.write(f"[{i}/{len(self.items)}] {ts}\n")
                        f.write(f"  From: {item.get('sender_name') or 'Unknown'} ({item.get('from_id')})\n")
                        f.write(f"  Source: {item.get('source')}\n")
                        f.write(f"  Message: {item.get('message') or ''}\n")
                        if item.get('rssi') is not None:
                            f.write(f"  Signal: RSSI={item.get('rssi')} dBm, SNR={item.get('snr')} dB\n")
                        f.write("\n")

                elif self.current_view == 'nodes':
                    for i, item in enumerate(self.items, 1):
                        f.write(f"[{i}/{len(self.items)}] Node: {item.get('node_id')}\n")
                        f.write(f"  Total packets: {item.get('total_packets'):,}\n")
                        f.write(f"  Total bytes: {item.get('total_bytes'):,}\n")
                        if item.get('packet_types'):
                            packet_types = json.loads(item.get('packet_types'))
                            f.write(f"  Packet types: {packet_types}\n")
                        f.write("\n")

            return filename
        except Exception as e:
            return None

    def export_to_csv(self):
        """Exporte la vue actuelle vers un fichier CSV"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"traffic_export_{self.current_view}_{timestamp}.csv"

        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                if self.current_view == 'packets':
                    fieldnames = ['timestamp', 'datetime', 'from_id', 'sender_name', 'to_id', 'source',
                                 'packet_type', 'is_encrypted', 'message', 'rssi', 'snr', 'hops', 'size']
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()

                    for item in self.items:
                        row = {
                            'timestamp': item.get('timestamp'),
                            'datetime': datetime.fromtimestamp(item.get('timestamp')).strftime('%Y-%m-%d %H:%M:%S') if item.get('timestamp') else '',
                            'from_id': item.get('from_id'),
                            'sender_name': item.get('sender_name'),
                            'to_id': item.get('to_id'),
                            'source': item.get('source'),
                            'packet_type': item.get('packet_type'),
                            'is_encrypted': 'Yes' if item.get('is_encrypted') else 'No',
                            'message': item.get('message') or '',
                            'rssi': item.get('rssi') or '',
                            'snr': item.get('snr') or '',
                            'hops': item.get('hops') or '',
                            'size': item.get('size') or ''
                        }
                        writer.writerow(row)

                elif self.current_view == 'messages':
                    fieldnames = ['timestamp', 'datetime', 'from_id', 'sender_name', 'source', 'message', 'rssi', 'snr']
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()

                    for item in self.items:
                        row = {
                            'timestamp': item.get('timestamp'),
                            'datetime': datetime.fromtimestamp(item.get('timestamp')).strftime('%Y-%m-%d %H:%M:%S') if item.get('timestamp') else '',
                            'from_id': item.get('from_id'),
                            'sender_name': item.get('sender_name'),
                            'source': item.get('source'),
                            'message': item.get('message') or '',
                            'rssi': item.get('rssi') or '',
                            'snr': item.get('snr') or ''
                        }
                        writer.writerow(row)

                elif self.current_view == 'nodes':
                    fieldnames = ['node_id', 'total_packets', 'total_bytes', 'packet_types', 'last_updated']
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()

                    for item in self.items:
                        row = {
                            'node_id': item.get('node_id'),
                            'total_packets': item.get('total_packets'),
                            'total_bytes': item.get('total_bytes'),
                            'packet_types': item.get('packet_types') or '',
                            'last_updated': item.get('last_updated') or ''
                        }
                        writer.writerow(row)

            return filename
        except Exception as e:
            return None

    def show_export_notification(self, stdscr, filename, success=True):
        """Affiche une notification d'export"""
        height, width = stdscr.getmaxyx()

        if success and filename:
            msg = f"✓ Exported to: {filename}"
        else:
            msg = "✗ Export failed"

        # Afficher en bas de l'écran pendant 2 secondes
        try:
            stdscr.attron(curses.color_pair(1) if success else curses.color_pair(2))
            stdscr.addstr(height - 2, 0, msg[:width-1].ljust(width-1))
            stdscr.attroff(curses.color_pair(1) if success else curses.color_pair(2))
            stdscr.refresh()
            curses.napms(2000)  # Pause 2 secondes
        except curses.error:
            pass

    def get_input(self, stdscr, prompt):
        """Demande une saisie utilisateur avec une meilleure interface"""
        height, width = stdscr.getmaxyx()

        # Effacer la zone de saisie
        try:
            stdscr.addstr(height - 2, 0, " " * (width - 1))
            stdscr.addstr(height - 2, 0, prompt[:width - 1])
            stdscr.refresh()
        except curses.error:
            pass

        # Activer le curseur et l'écho
        curses.curs_set(1)
        curses.echo()

        input_str = ''
        try:
            # Position du curseur pour la saisie
            cursor_x = len(prompt)

            # Boucle de saisie caractère par caractère pour plus de contrôle
            while True:
                try:
                    stdscr.move(height - 2, cursor_x + len(input_str))
                    stdscr.refresh()
                except:
                    pass

                ch = stdscr.getch()

                # Enter ou Newline
                if ch in [10, 13, curses.KEY_ENTER]:
                    break
                # Escape
                elif ch == 27:
                    input_str = ''
                    break
                # Backspace
                elif ch in [curses.KEY_BACKSPACE, 127, 8]:
                    if input_str:
                        input_str = input_str[:-1]
                        try:
                            stdscr.addstr(height - 2, cursor_x, input_str + " ")
                        except:
                            pass
                # Caractères imprimables
                elif 32 <= ch <= 126:
                    input_str += chr(ch)
                    try:
                        stdscr.addstr(height - 2, cursor_x, input_str)
                    except:
                        pass

        except Exception as e:
            pass
        finally:
            curses.noecho()
            curses.curs_set(0)
            # Effacer la ligne de saisie
            try:
                stdscr.addstr(height - 2, 0, " " * (width - 1))
            except:
                pass

        return input_str.strip()

    def filter_dialog(self, stdscr):
        """Dialogue pour filtrer par type de paquet"""
        # Récupérer les types disponibles
        cursor = self.conn.cursor()
        cursor.execute('SELECT DISTINCT packet_type FROM packets ORDER BY packet_type')
        types = [row[0] for row in cursor.fetchall()]

        if not types:
            return

        # Afficher les types
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        try:
            stdscr.addstr(0, 0, "SELECT PACKET TYPE (or press 0 to clear filter):"[:width-1])
            stdscr.addstr(1, 0, ("─" * (width-1))[:width-1])
        except curses.error:
            pass

        for i, ptype in enumerate(types[:height - 4], 1):
            try:
                stdscr.addstr(i + 1, 2, f"{i}. {ptype}"[:width-3])
            except curses.error:
                pass

        stdscr.refresh()

        # Attendre la sélection
        while True:
            key = stdscr.getch()
            if key == ord('0'):
                self.filter_type = None
                break
            elif ord('1') <= key <= ord('9'):
                idx = key - ord('1')
                if idx < len(types):
                    self.filter_type = types[idx]
                    break
            elif key == 27:  # ESC
                break

    def run(self, stdscr):
        """Boucle principale"""
        # Initialisation curses
        curses.curs_set(0)  # Cache le curseur
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_WHITE)
        stdscr.timeout(100)  # Non-blocking avec timeout

        # Charger les données
        self.load_data()

        while True:
            height, width = stdscr.getmaxyx()
            stdscr.clear()

            # Dessiner l'interface
            self.draw_header(stdscr, height, width)
            self.draw_footer(stdscr, height, width)

            if self.detail_mode:
                self.draw_detail_view(stdscr, height, width)
            else:
                self.draw_list(stdscr, height, width)

            stdscr.refresh()

            # Gestion des touches
            key = stdscr.getch()

            if key == -1:  # Timeout
                continue

            if self.detail_mode:
                # Mode détail
                if key in [27, ord('q'), curses.KEY_ENTER, 10, 13]:  # ESC, q, ENTER
                    self.detail_mode = False
                    self.detail_scroll = 0
                elif key in [curses.KEY_UP, ord('k')]:
                    self.detail_scroll = max(0, self.detail_scroll - 1)
                elif key in [curses.KEY_DOWN, ord('j')]:
                    self.detail_scroll += 1
                elif key == curses.KEY_PPAGE:
                    self.detail_scroll = max(0, self.detail_scroll - 10)
                elif key == curses.KEY_NPAGE:
                    self.detail_scroll += 10

            else:
                # Mode liste
                if key in [27, ord('q')]:  # ESC ou q
                    break
                elif key in [curses.KEY_UP, ord('k')]:
                    self.current_row = max(0, self.current_row - 1)
                elif key in [curses.KEY_DOWN, ord('j')]:
                    self.current_row = min(len(self.items) - 1, self.current_row + 1)
                elif key == curses.KEY_PPAGE:  # Page Up
                    self.current_row = max(0, self.current_row - (height - 3))
                elif key == curses.KEY_NPAGE:  # Page Down
                    self.current_row = min(len(self.items) - 1, self.current_row + (height - 3))
                elif key == curses.KEY_HOME:
                    self.current_row = 0
                elif key == curses.KEY_END:
                    self.current_row = max(0, len(self.items) - 1)
                elif key in [curses.KEY_ENTER, 10, 13]:  # ENTER
                    if self.items:
                        self.detail_mode = True
                elif key == ord('/'):  # Recherche
                    term = self.get_input(stdscr, "Search: ")
                    if term:
                        self.search_term = term
                        self.load_data()
                        self.current_row = 0
                elif key == ord('f'):  # Filtrer par type
                    if self.current_view == 'packets':
                        self.filter_dialog(stdscr)
                        self.load_data()
                        self.current_row = 0
                elif key == ord('e'):  # Filtrer chiffrement
                    if self.current_view == 'packets':
                        # Cycler entre all, only, exclude
                        if self.filter_encrypted == 'all':
                            self.filter_encrypted = 'only'
                        elif self.filter_encrypted == 'only':
                            self.filter_encrypted = 'exclude'
                        else:
                            self.filter_encrypted = 'all'
                        self.load_data()
                        self.current_row = 0
                elif key == ord('s'):  # Inverser l'ordre de tri
                    if self.current_view in ['packets', 'messages']:
                        # Basculer entre desc et asc
                        self.sort_order = 'asc' if self.sort_order == 'desc' else 'desc'
                        self.load_data()
                        # Garder la position relative (inverser la sélection)
                        if self.items:
                            self.current_row = len(self.items) - 1 - self.current_row
                elif key == ord('v'):  # Changer de vue
                    views = ['packets', 'messages', 'nodes']
                    current_idx = views.index(self.current_view)
                    self.current_view = views[(current_idx + 1) % len(views)]
                    self.filter_type = None
                    self.search_term = None
                    self.load_data()
                    self.current_row = 0
                elif key == ord('r'):  # Rafraîchir
                    self.load_data()
                elif key == ord('x'):  # Export vers texte
                    filename = self.export_to_text()
                    self.show_export_notification(stdscr, filename, success=(filename is not None))
                elif key == ord('c'):  # Export vers CSV
                    filename = self.export_to_csv()
                    self.show_export_notification(stdscr, filename, success=(filename is not None))
                elif key == ord('?'):  # Aide
                    self.show_help(stdscr)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Interactive Traffic DB Browser')
    parser.add_argument('--db', default='traffic_history.db', help='Path to database')
    args = parser.parse_args()

    browser = TrafficDBBrowser(args.db)

    if not browser.connect_db():
        print(f"Error: Cannot open database {args.db}")
        sys.exit(1)

    try:
        curses.wrapper(browser.run)
    except KeyboardInterrupt:
        pass
    finally:
        if browser.conn:
            browser.conn.close()


if __name__ == '__main__':
    main()
