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
  v              : Changer de vue (packets/messages/nodes)
  r              : Rafraîchir les données
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

        # Appliquer le filtre de type
        if self.filter_type:
            query += ' WHERE packet_type = ?'
            params.append(self.filter_type)

        # Appliquer la recherche
        if self.search_term:
            if self.filter_type:
                query += ' AND message LIKE ?'
            else:
                query += ' WHERE message LIKE ?'
            params.append(f'%{self.search_term}%')

        query += ' ORDER BY timestamp DESC LIMIT 1000'

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

        query += ' ORDER BY timestamp DESC LIMIT 1000'

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
        title = f"Traffic DB Browser - {self.current_view.upper()}"
        if self.filter_type:
            title += f" [Filter: {self.filter_type}]"
        if self.search_term:
            title += f" [Search: {self.search_term}]"

        # Ligne de titre
        stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
        stdscr.addstr(0, 0, title.center(width)[:width])
        stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)

        # Info compteur
        info = f" {len(self.items)} items"
        if self.items:
            info += f" | Row {self.current_row + 1}/{len(self.items)}"
        stdscr.addstr(1, 0, info[:width])

    def draw_footer(self, stdscr, height, width):
        """Dessine le pied de page avec les raccourcis"""
        footer = "↑/↓:Nav ENTER:Details /:Search f:Filter v:View r:Refresh q:Quit ?:Help"
        stdscr.attron(curses.color_pair(2))
        stdscr.addstr(height - 1, 0, footer[:width].ljust(width))
        stdscr.attroff(curses.color_pair(2))

    def draw_packet_line(self, stdscr, y, x, width, item, is_selected):
        """Dessine une ligne de paquet"""
        ts = self.format_timestamp(item.get('timestamp'))
        name = (item.get('sender_name') or 'Unknown')[:15]
        ptype = (item.get('packet_type') or 'N/A')[:20]
        source = (item.get('source') or '?')[:8]
        msg = self.truncate(item.get('message') or '', width - 70)

        line = f"{ts} {source:8s} {name:15s} {ptype:20s} {msg}"

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
        list_height = height - 3  # Header (2) + Footer (1)
        start_y = 2

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
            "  ↑/↓ or j/k      - Move up/down",
            "  PgUp/PgDn       - Page up/down",
            "  Home/End        - First/last item",
            "",
            "Actions:",
            "  ENTER           - View item details",
            "  /               - Search in messages",
            "  f               - Filter by packet type",
            "  v               - Change view (packets/messages/nodes)",
            "  r               - Refresh data from DB",
            "",
            "In detail view:",
            "  ↑/↓             - Scroll detail text",
            "  ESC or ENTER    - Return to list",
            "",
            "Other:",
            "  q or ESC        - Quit (from list view)",
            "  ?               - This help",
            "",
            "Press any key to return..."
        ]

        stdscr.clear()
        height, width = stdscr.getmaxyx()

        for i, line in enumerate(help_text):
            if i >= height - 1:
                break
            try:
                stdscr.addstr(i, 2, line[:width-4])
            except curses.error:
                pass

        stdscr.refresh()
        stdscr.getch()

    def get_input(self, stdscr, prompt):
        """Demande une saisie utilisateur"""
        height, width = stdscr.getmaxyx()
        curses.echo()
        try:
            stdscr.addstr(height - 2, 0, prompt[:width])
            stdscr.clrtoeol()
            stdscr.refresh()
            input_str = stdscr.getstr(height - 2, len(prompt), width - len(prompt) - 1).decode('utf-8')
        except:
            input_str = ''
        finally:
            curses.noecho()

        return input_str

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

        stdscr.addstr(0, 0, "SELECT PACKET TYPE (or press 0 to clear filter):")
        stdscr.addstr(1, 0, "─" * width)

        for i, ptype in enumerate(types[:height - 4], 1):
            stdscr.addstr(i + 1, 2, f"{i}. {ptype}")

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
                elif key == ord('f'):  # Filtrer
                    if self.current_view == 'packets':
                        self.filter_dialog(stdscr)
                        self.load_data()
                        self.current_row = 0
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
