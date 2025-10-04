#!/usr/bin/env python3
"""
Interface de débogage interactive
"""

import sys
from config import *
from utils import *

class DebugInterface:
    def __init__(self, bot):
        self.bot = bot
    
    def interactive_loop(self):
        """Boucle interactive avec gestion des noms"""
        if not DEBUG_MODE:
            return
        
        # Vérifier qu'on a un terminal interactif
        if not sys.stdin.isatty():
            debug_print("Interface debug désactivée (pas de terminal)")
            return
            
        while self.bot.running:
            try:
                command = input(f"\n[{format_timestamp()}] > ")
                
                if command.lower() in ['quit', 'exit', 'q']:
                    self.bot.running = False
                    break
                    
                self._process_debug_command(command)
                    
            except KeyboardInterrupt:
                self.bot.running = False
                break
            except EOFError:
                # Stdin fermé (ex: service systemd)
                debug_print("Interface debug fermée (EOF)")
                break
            except Exception as e:
                info_print(f"Erreur: {e}")
    
    def _process_debug_command(self, command):
        """Traiter une commande de debug"""
        if command.startswith('test '):
            self._handle_test_command(command)
        elif command == 'context':
            self._handle_context_command()
        elif command.startswith('bot '):
            self._handle_bot_command(command)
        elif command == 'power':
            self._handle_power_test()
        elif command == 'rx':
            self._handle_rx_test()
        elif command == 'legend':
            self._handle_legend_test()
        elif command == 'help':
            self._handle_help_test()
        elif command.startswith('config '):
            self._handle_config_command(command)
        elif command.startswith('tigrog2'):
            self._handle_tigrog2_test(command)
        elif command.startswith('nodes '):
            self._handle_nodes_command(command)
        elif command == 'nodes':
            self.bot.node_manager.list_known_nodes()
        elif command == 'update':
            self.bot.node_manager.update_node_database(self.bot.interface)
        elif command == 'save':
            self.bot.node_manager.save_node_names(force=True)
        elif command == 'reload':
            self.bot.node_manager.load_node_names()
        elif command == 'mem':
            self._handle_memory_command()
        elif command == 'help':
            self._show_help()
        else:
            print("Tapez 'help'")
    
    def _handle_test_command(self, command):
        """Gérer la commande test"""
        prompt = command[5:]
        info_print(f"TEST: '{prompt}'")
        response = self.bot.llama_client.query_llama_telegram(prompt)  # Sans contexte pour les tests
        info_print(f"→ {response}")
    
    def _handle_context_command(self):
        """Afficher les contextes actifs"""
        self.bot.context_manager.list_active_contexts()
    
    def _handle_bot_command(self, command):
        """Tester une commande bot"""
        question = command[4:]
        bot_command = f"/bot {question}"
        info_print(f"Envoi: '{bot_command}'")
        self.bot.interface.sendText(bot_command)
    
    def _handle_power_test(self):
        """Tester ESPHome"""
        info_print("TEST ESPHome:")
        data = self.bot.esphome_client.parse_esphome_data()
        info_print(f"→ {data}")
    
    def _handle_rx_test(self):
        """Tester le rapport RX"""
        info_print("TEST RX Report:")
        report = self.bot.node_manager.format_rx_report()
        info_print(f"→ {report}")
    
    def _handle_legend_test(self):
        """Tester la légende"""
        info_print("TEST Legend:")
        legend = self.bot.message_handler.format_legend()
        info_print(f"→ {legend}")
    
    def _handle_help_test(self):
        """Tester l'aide"""
        info_print("TEST Help:")
        help_text = self.bot.message_handler.format_help()
        info_print(f"→ {help_text}")
    
    def _handle_config_command(self, command):
        """Gérer les commandes de configuration"""
        parts = command.split(' ')
        if len(parts) >= 3:
            option = parts[1].lower()
            value = parts[2].lower() == 'true'
            
            global SHOW_RSSI, SHOW_SNR, COLLECT_SIGNAL_METRICS
            if option == 'rssi':
                SHOW_RSSI = value
                info_print(f"SHOW_RSSI = {SHOW_RSSI}")
            elif option == 'snr':
                SHOW_SNR = value
                info_print(f"SHOW_SNR = {SHOW_SNR}")
            elif option == 'collect':
                COLLECT_SIGNAL_METRICS = value
                info_print(f"COLLECT_SIGNAL_METRICS = {COLLECT_SIGNAL_METRICS}")
            else:
                info_print("Options: rssi, snr, collect")
        else:
            info_print(f"Config actuelle - RSSI:{SHOW_RSSI} SNR:{SHOW_SNR} COLLECT:{COLLECT_SIGNAL_METRICS}")
            info_print("Usage: config <option> <true/false>")
    
    def _handle_tigrog2_test(self, command):
        """Tester tigrog2 avec pagination"""
        parts = command.split()
        page = 1
        
        if len(parts) > 1:
            page = validate_page_number(parts[1], 999)
        
        info_print(f"TEST Tigrog2 Page {page}")
        try:
            report = self.bot.remote_nodes_client.get_tigrog2_paginated(page)
            info_print(f"→ {report}")
        except Exception as e:
            info_print(f"→ Erreur: {e}")
    
    def _handle_nodes_command(self, command):
        """Tester la récupération de nœuds distants"""
        parts = command.split(' ', 1)
        if len(parts) > 1:
            remote_host = parts[1].strip()
            info_print(f"TEST Remote Nodes: {remote_host}")
            nodes = self.bot.remote_nodes_client.get_remote_nodes(remote_host)
            info_print(f"→ {len(nodes)} nœuds trouvés")
            for node in nodes[:5]:  # Afficher les 5 premiers
                info_print(f"   {node['name']} - RSSI:{node.get('rssi', 0)}")
        else:
            info_print("Usage: nodes <IP_du_noeud>")
    
    def _handle_memory_command(self):
        """Afficher les informations mémoire"""
        try:
            import psutil
            import os
            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / 1024 / 1024
            active_contexts, total_messages = self.bot.context_manager.get_memory_stats()
            info_print(f"Mémoire: {memory_mb:.1f}MB, Nœuds: {len(self.bot.node_manager.node_names)}, Contextes: {active_contexts} ({total_messages} msgs)")
        except:
            active_contexts, total_messages = self.bot.context_manager.get_memory_stats()
            info_print(f"Nœuds: {len(self.bot.node_manager.node_names)}, Contextes: {active_contexts} ({total_messages} messages)")
    
    def _show_help(self):
        """Afficher l'aide des commandes debug"""
        print("Commandes:")
        print("  test <prompt>  - Test llama.cpp")
        print("  bot <question> - Via Meshtastic")
        print("  power          - Test ESPHome")
        print("  rx             - Rapport signaux reçus")
        print("  legend         - Légende des indicateurs")
        print("  help           - Cette aide")
        print("  tigrog2 [page] - Nœuds de tigrog2 (page 1-4)")
        print("  config         - Voir config affichage")
        print("  config <opt> <true/false> - Changer config")
        print("  nodes          - Lister nœuds connus")
        print("  nodes <IP>     - Nœuds d'un nœud distant")
        print("  context        - Voir contextes actifs")
        print("  update         - Mise à jour base nœuds")
        print("  save           - Sauvegarder base nœuds")
        print("  reload         - Recharger base nœuds")
        print("  mem            - Mémoire utilisée")
        print("  quit           - Quitter")
