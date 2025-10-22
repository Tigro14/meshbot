#!/usr/bin/env python3
import traceback
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
        elif command == 'channels':
            self._handle_channels_command()
        elif command == 'nodes':
            self.bot.node_manager.list_known_nodes()
        elif command == 'update':
            self.bot.node_manager.update_node_database(self.bot.interface)
        elif command == 'save':
            self.bot.node_manager.save_node_names(force=True)
        elif command.startswith('send '):
            self._handle_direct_send(command)
        elif command == 'reload':
            self.bot.node_manager.load_node_names()
        elif command == 'mem':
            self._handle_memory_command()
        elif command == 'cpu':
            self._handle_cpu_command()
        elif command.startswith('histo'):
            self._handle_histo_test(command)
        elif command == 'pstats':
            self._handle_packet_stats()
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
        except Exception as e:
            active_contexts, total_messages = self.bot.context_manager.get_memory_stats()
            info_print(f"Nœuds: {len(self.bot.node_manager.node_names)}, Contextes: {active_contexts} ({total_messages} messages)")

    def _handle_cpu_command(self):
        """Afficher l'utilisation CPU en temps réel"""
        try:
            import psutil
            import os
            process = psutil.Process(os.getpid())
            
            info_print("📊 Monitoring CPU (10 secondes)...")
            for i in range(10):
                cpu = process.cpu_percent(interval=1.0)
                threads = len(process.threads())
                mem = process.memory_info().rss / 1024 / 1024
                info_print(f"  [{i+1}/10] CPU: {cpu:.1f}% | Threads: {threads} | RAM: {mem:.0f}MB")
            
            # Moyenne
            cpu_avg = process.cpu_percent(interval=1.0)
            info_print(f"✅ Moyenne: {cpu_avg:.1f}%")
            
        except ImportError:
            info_print("❌ psutil non installé")
        except Exception as e:
            info_print(f"❌ Erreur: {e}") 

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
        print("  channels       - Inspecter canaux tigrog2")  # ✅ NOUVEAU
        print("  echotest <msg> - Tester echo sur tous canaux")  # ✅ NOUVEAU
        print("  send <msg>     - send direct message")  # ✅ NOUVEAU
        print("  config         - Voir config affichage")
        print("  config <opt> <true/false> - Changer config")
        print("  nodes          - Lister nœuds connus")
        print("  nodes <IP>     - Nœuds d'un nœud distant")
        print("  context        - Voir contextes actifs")
        print("  update         - Mise à jour base nœuds")
        print("  save           - Sauvegarder base nœuds")
        print("  reload         - Recharger base nœuds")
        print("  mem            - Mémoire utilisée")
        print("  cpu            - Monitoring CPU 10s")
        print("  histo [type] [h] - Histogramme distribution horaire")
        print("  pstats           - Statistiques paquets collectés")
        print("  quit           - Quitter")

    def _handle_cpu_profiling(self):
        """Profiling CPU détaillé"""
        try:
            import psutil
            import os
            process = psutil.Process(os.getpid())
            
            info_print("🔍 Profiling threads CPU...")
            for thread in process.threads():
                info_print(f"  Thread {thread.id}: {thread.user_time + thread.system_time:.2f}s CPU")
            
            # Connections réseau
            connections = process.connections()
            info_print(f"📡 Connections actives: {len(connections)}")
            
        except Exception as e:
            info_print(f"Erreur profiling: {e}")        

    def _handle_channels_command(self):
        """Inspecter les canaux de tigrog2"""
        try:
            import meshtastic.tcp_interface
            from config import REMOTE_NODE_HOST
            
            info_print(f"Connexion à tigrog2 pour inspecter les canaux...")
            
            remote_interface = meshtastic.tcp_interface.TCPInterface(
                hostname=REMOTE_NODE_HOST,
                portNumber=4403
            )
            
            time.sleep(3)
            
            info_print("=" * 60)
            info_print("📻 CONFIGURATION DES CANAUX TIGROG2")
            info_print("=" * 60)
            
            # Récupérer les channels
            if hasattr(remote_interface, 'localNode') and remote_interface.localNode:
                local_node = remote_interface.localNode
                
                # Node info
                if hasattr(local_node, 'shortName'):
                    info_print(f"Node: {local_node.shortName}")
                if hasattr(local_node, 'nodeNum'):
                    info_print(f"ID: !{local_node.nodeNum:08x}")
                
                info_print("")
                
                # Channels
                if hasattr(local_node, 'channels'):
                    channels = local_node.channels
                    info_print(f"Nombre de canaux configurés: {len(channels)}")
                    info_print("")
                    
                    for i, channel in enumerate(channels):
                        if channel and hasattr(channel, 'settings'):
                            settings = channel.settings
                            
                            info_print(f"CANAL {i}:")
                            
                            if hasattr(settings, 'name'):
                                name = settings.name or "(sans nom)"
                                info_print(f"  Nom: {name}")
                            
                            if hasattr(settings, 'psk'):
                                psk_len = len(settings.psk) if settings.psk else 0
                                info_print(f"  PSK: {'Oui' if psk_len > 0 else 'Non'} ({psk_len} bytes)")
                            
                            if hasattr(channel, 'role'):
                                role = channel.role
                                role_str = {0: 'DISABLED', 1: 'PRIMARY', 2: 'SECONDARY'}.get(role, f'UNKNOWN({role})')
                                info_print(f"  Rôle: {role_str}")
                            
                            if hasattr(settings, 'module_settings'):
                                info_print(f"  Module: {settings.module_settings}")
                            
                            info_print("")
                else:
                    info_print("⚠️ Impossible de récupérer les canaux")
            else:
                info_print("⚠️ localNode non disponible")
            
            info_print("=" * 60)
            
            remote_interface.close()
            info_print("✅ Inspection terminée")
            
        except Exception as e:
            error_print(f"Erreur inspection canaux: {e}")
            error_print(traceback.format_exc())



    def _handle_direct_send(self, command):
        """Envoyer un message direct via tigrog2 (debug)"""
        try:
            parts = command.split(' ', 1)
            if len(parts) < 2:
                info_print("Usage: send <message>")
                return

            message = parts[1]

            import meshtastic.tcp_interface
            remote_interface = meshtastic.tcp_interface.TCPInterface(
                hostname=REMOTE_NODE_HOST,
                portNumber=4403
            )

            time.sleep(3)

            info_print(f"Envoi direct: '{message}'")
            remote_interface.sendText(message)
            info_print("✅ Message envoyé")

            time.sleep(5)
            remote_interface.close()

        except Exception as e:
            error_print(f"Erreur: {e}")
            error_print(traceback.format_exc())

    def _handle_send_test(self, command):
        """Tester l'envoi direct via tigrog2"""
        try:
            parts = command.split(' ', 1)
            if len(parts) < 2:
                info_print("Usage: send <message>")
                return
            
            message = parts[1]
            
            import meshtastic.tcp_interface
            from config import REMOTE_NODE_HOST
            
            info_print("=" * 60)
            info_print(f"📤 TEST ENVOI DIRECT: '{message}'")
            info_print("=" * 60)
            
            info_print(f"Connexion à {REMOTE_NODE_HOST}...")
            remote_interface = meshtastic.tcp_interface.TCPInterface(
                hostname=REMOTE_NODE_HOST,
                portNumber=4403
            )
            
            info_print("✅ Connecté")
            info_print("⏳ Attente 5s...")
            time.sleep(5)
            
            info_print(f"📤 Envoi message: '{message}'")
            
            # TEST 1: Sans paramètres
            info_print("\n--- TEST 1: sendText() simple ---")
            try:
                remote_interface.sendText(message)
                info_print("✅ Envoyé sans paramètres")
            except Exception as e:
                error_print(f"❌ Échec: {e}")
            
            time.sleep(10)
            
            # TEST 2: Avec destinationId
            info_print("\n--- TEST 2: sendText() avec destinationId ---")
            try:
                remote_interface.sendText(
                    message + " [TEST2]",
                    destinationId='^all'
                )
                info_print("✅ Envoyé avec destinationId='^all'")
            except Exception as e:
                error_print(f"❌ Échec: {e}")
            
            time.sleep(10)
            
            # TEST 3: Avec tous les paramètres
            info_print("\n--- TEST 3: sendText() avec tous paramètres ---")
            try:
                remote_interface.sendText(
                    text=message + " [TEST3]",
                    destinationId='^all',
                    channelIndex=0,
                    wantAck=False,
                    wantResponse=False
                )
                info_print("✅ Envoyé avec tous paramètres")
            except Exception as e:
                error_print(f"❌ Échec: {e}")
            
            time.sleep(10)
            
            info_print("\n🔌 Fermeture connexion...")
            remote_interface.close()
            info_print("=" * 60)
            info_print("✅ Tests terminés - vérifiez votre radio mesh")
            info_print("=" * 60)
            
        except Exception as e:
            error_print(f"❌ Erreur test: {e}")
            error_print(traceback.format_exc())            

    
    def _handle_histo_test(self, command):
        """
        Tester la commande /histo en mode debug
        
        Usage:
        > histo
        > histo messages
        > histo pos 12
        > histo all 48
        """
        info_print("TEST Histo:")
        
        # Parser les arguments
        parts = command.split()
        packet_filter = 'all'  # Défaut
        hours = 24  # Défaut
        
        if len(parts) > 1:
            packet_filter = parts[1]
        
        if len(parts) > 2:
            try:
                hours = int(parts[2])
                hours = max(1, min(72, hours))
            except ValueError:
                hours = 24
        
        try:
            histogram = self.bot.traffic_monitor.get_hourly_histogram(packet_filter, hours)
            info_print(f"→ {histogram}")
            
            # Afficher aussi le nombre de paquets en mémoire
            total_packets = len(self.bot.traffic_monitor.packet_history)
            info_print(f"\n📊 Total paquets en mémoire: {total_packets}")
            
            # Afficher la répartition par type
            type_counts = {}
            for pkt in self.bot.traffic_monitor.packet_history:
                pkt_type = pkt['type']
                type_counts[pkt_type] = type_counts.get(pkt_type, 0) + 1
            
            if type_counts:
                info_print("📋 Répartition par type:")
                for pkt_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
                    percentage = (count / total_packets * 100) if total_packets > 0 else 0
                    info_print(f"   {pkt_type:15s}: {count:4d} ({percentage:5.1f}%)")
            
        except Exception as e:
            info_print(f"→ Erreur: {e}")
            traceback.print_exc()


    # ============================================================
    # AJOUT: Méthode _handle_packet_stats dans DebugInterface
    # ============================================================

    def _handle_packet_stats(self):
        """
        Afficher les statistiques détaillées des paquets collectés
        
        Usage:
        > pstats
        """
        info_print("📊 Statistiques paquets:")
        
        try:
            total_packets = len(self.bot.traffic_monitor.packet_history)
            
            if total_packets == 0:
                info_print("  Aucun paquet en mémoire")
                return
            
            info_print(f"  Total paquets: {total_packets}")
            
            # Répartition par type
            type_counts = defaultdict(int)
            for pkt in self.bot.traffic_monitor.packet_history:
                type_counts[pkt['type']] += 1
            
            info_print("\n  Par type:")
            for pkt_type in sorted(type_counts.keys()):
                count = type_counts[pkt_type]
                percentage = (count / total_packets * 100)
                bar_length = int(percentage / 5)  # Max 20 chars
                bar = "█" * bar_length + "░" * (20 - bar_length)
                info_print(f"    {pkt_type:15s} {bar} {count:4d} ({percentage:5.1f}%)")
            
            # Nœuds actifs
            unique_nodes = set(pkt['from_id'] for pkt in self.bot.traffic_monitor.packet_history)
            info_print(f"\n  Nœuds uniques: {len(unique_nodes)}")
            
            # Top 5 émetteurs
            node_counts = defaultdict(int)
            for pkt in self.bot.traffic_monitor.packet_history:
                node_counts[pkt['sender_name']] += 1
            
            top_nodes = sorted(node_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            
            if top_nodes:
                info_print("\n  Top 5 émetteurs:")
                for i, (name, count) in enumerate(top_nodes, 1):
                    percentage = (count / total_packets * 100)
                    info_print(f"    {i}. {name:20s}: {count:4d} ({percentage:5.1f}%)")
            
            # Période couverte
            if self.bot.traffic_monitor.packet_history:
                oldest = min(pkt['timestamp'] for pkt in self.bot.traffic_monitor.packet_history)
                newest = max(pkt['timestamp'] for pkt in self.bot.traffic_monitor.packet_history)
                
                from datetime import datetime
                oldest_dt = datetime.fromtimestamp(oldest)
                newest_dt = datetime.fromtimestamp(newest)
                duration_hours = (newest - oldest) / 3600
                
                info_print(f"\n  Période:")
                info_print(f"    Plus ancien: {oldest_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                info_print(f"    Plus récent: {newest_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                info_print(f"    Durée: {duration_hours:.1f}h")
            
        except Exception as e:
            info_print(f"  Erreur: {e}")
            traceback.print_exc()


