#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gestionnaire des messages et commandes
"""

import time
import meshtastic
from config import *
from utils import *

class MessageHandler:
    def __init__(self, llama_client, esphome_client, remote_nodes_client, node_manager, context_manager, interface):
        self.llama_client = llama_client
        self.esphome_client = esphome_client
        self.remote_nodes_client = remote_nodes_client
        self.node_manager = node_manager
        self.context_manager = context_manager
        self.interface = interface
        
        # Throttling des commandes utilisateurs
        self.user_commands = {}  # user_id -> [timestamps des commandes]
    
    def log_conversation(self, sender_id, sender_info, query, response, processing_time=None):
        """Log une conversation complète"""
        try:
            conversation_print("=" * 40)
            conversation_print(f"USER: {sender_info} (!{sender_id:08x})")
            conversation_print(f"QUERY: {query}")
            conversation_print(f"RESPONSE: {response}")
            if processing_time:
                conversation_print(f"TIME: {processing_time:.2f}s")
            conversation_print("=" * 40)
        except Exception as e:
            error_print(f"Erreur logging: {e}")
    
    def send_response_chunks(self, response, sender_id, sender_info):
        """Divise et envoie - version simplifiée"""
        try:
            max_length = MAX_MESSAGE_SIZE
            
            if len(response) <= max_length:
                self.send_single_message(response, sender_id, sender_info)
            else:
                # Division simple
                chunks = []
                for i in range(0, len(response), max_length-20):
                    chunk = response[i:i+max_length-20]
                    if i + max_length-20 < len(response):
                        chunk += "..."
                    chunks.append(chunk)
                
                for i, chunk in enumerate(chunks, 1):
                    if len(chunks) > 1:
                        formatted_chunk = f"({i}/{len(chunks)}) {chunk}"
                    else:
                        formatted_chunk = chunk
                    
                    self.send_single_message(formatted_chunk, sender_id, sender_info)
                    if i < len(chunks):
                        time.sleep(2)
                        
        except Exception as e:
            error_print(f"Erreur division: {e}")
            fallback = truncate_text(response, max_length-3, "...")
            self.send_single_message(fallback, sender_id, sender_info)
    
    def send_single_message(self, message, sender_id, sender_info):
        """Envoie un message - version simplifiée"""
        try:
            self.interface.sendText(message, destinationId=sender_id)
            debug_print(f"Message → {sender_info}")
        except Exception as e1:
            error_print(f"Échec envoi → {sender_info}: {e1}")
            # Essayer avec le format hex string
            try:
                hex_id = f"!{sender_id:08x}"
                self.interface.sendText(message, destinationId=hex_id)
                debug_print(f"Message → {sender_info} (hex format)")
            except Exception as e2:
                error_print(f"Échec envoi définitif → {sender_info}: {e2}")
    
    def _get_short_name(self, node_id):
        """Obtenir le nom court d'un nœud (shortName ou les 4 derniers caractères hex de l'ID)"""
        try:
            # Essayer d'obtenir le shortName depuis l'interface
            if hasattr(self.interface, 'nodes') and node_id in self.interface.nodes:
                node_info = self.interface.nodes[node_id]
                if isinstance(node_info, dict) and 'user' in node_info:
                    user_info = node_info['user']
                    if isinstance(user_info, dict):
                        short_name = user_info.get('shortName', '').strip()
                        if short_name:
                            return short_name
            
            # Fallback : toujours utiliser les 4 derniers caractères de l'ID
            return f"{node_id:08x}"[-4:]
                
        except Exception as e:
            debug_print(f"Erreur récupération nom court {node_id}: {e}")
            return f"{node_id:08x}"[-4:]
    
    def check_command_throttling(self, sender_id, sender_info):
        """Vérifier le throttling des commandes pour un utilisateur"""
        current_time = time.time()
        
        # Nettoyer d'abord les anciennes entrées
        if sender_id in self.user_commands:
            # Garder seulement les commandes dans la fenêtre temporelle
            self.user_commands[sender_id] = [
                cmd_time for cmd_time in self.user_commands[sender_id]
                if current_time - cmd_time < COMMAND_WINDOW_SECONDS
            ]
        else:
            self.user_commands[sender_id] = []
        
        # Vérifier le nombre de commandes dans la fenêtre
        command_count = len(self.user_commands[sender_id])
        
        if command_count >= MAX_COMMANDS_PER_WINDOW:
            # Calculer le temps d'attente
            oldest_command = min(self.user_commands[sender_id])
            wait_time = int(COMMAND_WINDOW_SECONDS - (current_time - oldest_command))
            
            # Envoyer message de throttling
            throttle_msg = f"⏱️ Limite: {MAX_COMMANDS_PER_WINDOW} cmd/5min. Attendez {wait_time}s"
            try:
                self.send_single_message(throttle_msg, sender_id, sender_info)
            except Exception as e:
                debug_print(f"Envoi message throttling échoué: {e}")
            
            # Logger le throttling
            info_print(f"THROTTLE: {sender_info} - {command_count}/{MAX_COMMANDS_PER_WINDOW} commandes")
            return False
        
        # Ajouter la commande actuelle
        self.user_commands[sender_id].append(current_time)
        
        # Logger pour debug
        debug_print(f"Throttling {sender_info}: {command_count + 1}/{MAX_COMMANDS_PER_WINDOW} commandes")
        return True
    
    def cleanup_throttling_data(self):
        """Nettoyer les données de throttling anciennes (appelé périodiquement)"""
        current_time = time.time()
        users_to_remove = []
        
        for user_id, command_times in self.user_commands.items():
            # Nettoyer les commandes anciennes
            recent_commands = [
                cmd_time for cmd_time in command_times
                if current_time - cmd_time < COMMAND_WINDOW_SECONDS
            ]
            
            if recent_commands:
                self.user_commands[user_id] = recent_commands
            else:
                # Plus de commandes récentes, supprimer l'utilisateur
                users_to_remove.append(user_id)
        
        # Supprimer les utilisateurs inactifs
        for user_id in users_to_remove:
            del self.user_commands[user_id]
        
        if users_to_remove and DEBUG_MODE:
            debug_print(f"Nettoyage throttling: {len(users_to_remove)} utilisateurs supprimés")
    
    def format_legend(self):
        """Formater la légende des indicateurs colorés - version compacte"""
        legend_lines = [
            "📶 Indicateurs:",
            "🟢🔵=excellent",
            "🟡🟣=bon", 
            "🟠🟤=faible",
            "🔴⚫=très faible",
            "1er=RSSI 2e=SNR"
        ]
        
        return "\n".join(legend_lines)
    
    def format_help(self):
        """Formater l'aide des commandes disponibles - version compacte"""
        help_lines = [
            "🤖 Commandes bot:",
            "/bot <question>",
            "/power",
            "/rx [page]", 
            "/my",
            "/sys",
            "/echo <texte>",
            "/legend"
        ]
        
        return "\n".join(help_lines)
    
    def handle_bot_command(self, message, sender_id, sender_info):
        """Gérer la commande /bot"""
        prompt = message[5:].strip()
        info_print(f"Bot: {sender_info}: '{prompt}'")
        
        if prompt:
            start_time = time.time()
            # IMPORTANT: Utiliser la méthode spécifique Mesh pour les réponses courtes
            response = self.llama_client.query_llama_mesh(prompt, sender_id)
            end_time = time.time()
            
            self.log_conversation(sender_id, sender_info, prompt, response, end_time - start_time)
            self.send_response_chunks(response, sender_id, sender_info)
            
            # Nettoyage après traitement
            self.llama_client.cleanup_cache()
        else:
            self.interface.sendText("Usage: /bot <question>", destinationId=sender_id)
    
    def handle_power_command(self, sender_id, sender_info):
        """Gérer la commande /power"""
        info_print(f"Power: {sender_info}")
        
        esphome_data = self.esphome_client.parse_esphome_data()
        self.log_conversation(sender_id, sender_info, "/power", esphome_data)
        self.send_response_chunks(esphome_data, sender_id, sender_info)
    
    def handle_rx_command(self, message, sender_id, sender_info):
        """Gérer la commande /rx (anciennement /tigrog2)"""
        # Extraire le numéro de page
        page = 1
        parts = message.split()
        
        # Format "/rx 2" - la page est le 2ème élément
        if len(parts) > 1:
            page = validate_page_number(parts[1], 999)
        
        info_print(f"RX Page {page}: {sender_info}")
        
        try:
            report = self.remote_nodes_client.get_tigrog2_paginated(page)
            self.log_conversation(sender_id, sender_info, f"/rx {page}" if page > 1 else "/rx", report)
            self.send_single_message(report, sender_id, sender_info)
        except Exception as e:
            error_msg = f"Erreur rx page {page}: {str(e)[:50]}"
            self.send_single_message(error_msg, sender_id, sender_info)
    
    def handle_legend_command(self, sender_id, sender_info):
        """Gérer la commande /legend"""
        info_print(f"Legend: {sender_info}")
        
        legend_text = self.format_legend()
        self.log_conversation(sender_id, sender_info, "/legend", legend_text)
        self.send_response_chunks(legend_text, sender_id, sender_info)
    
    def handle_help_command(self, sender_id, sender_info):
        """Gérer la commande /help"""
        info_print(f"Help: {sender_info}")
        
        try:
            help_text = self.format_help()
            info_print(f"Help text généré: {len(help_text)} caractères")
            self.log_conversation(sender_id, sender_info, "/help", help_text)
            self.send_single_message(help_text, sender_id, sender_info)
            info_print(f"Help envoyé à {sender_info}")
        except Exception as e:
            error_print(f"Erreur commande /help: {e}")
            self.send_single_message("Erreur génération aide", sender_id, sender_info)
    
    def handle_echo_command(self, message, sender_id, sender_info, packet):
        """Gérer la commande /echo - tigrog2 diffuse l'echo dans le mesh"""
        echo_text = message[6:].strip()  # Retirer "/echo "
        
        if not echo_text:
            # Répondre en privé avec usage
            response = f"Usage: /echo <texte>"
            self.send_single_message(response, sender_id, sender_info)
            return
        
        # Log de la commande
        info_print(f"Echo via tigrog2: {sender_info} -> '{echo_text}'")
        
        import threading
        
        def send_echo_via_tigrog2():
            try:
                # Se connecter à tigrog2 via TCP
                import meshtastic.tcp_interface
                
                debug_print(f"Connexion TCP à tigrog2 pour echo...")
                remote_interface = meshtastic.tcp_interface.TCPInterface(
                    hostname=REMOTE_NODE_HOST, 
                    portNumber=4403
                )
                
                # Attendre la connexion
                time.sleep(1)
                
                # Créer la réponse avec l'identifiant court en préambule
                author_short = self._get_short_name(sender_id)
                echo_response = f"{author_short}: {echo_text}"
                
                # Envoyer le message en broadcast via tigrog2
                remote_interface.sendText(echo_response)
                
                debug_print(f"Echo diffusé via tigrog2: '{echo_response}'")
                
                # Fermer la connexion
                remote_interface.close()
                
                # Log de la conversation
                self.log_conversation(sender_id, sender_info, message, echo_response)
                
            except Exception as e:
                error_print(f"Erreur echo via tigrog2: {e}")
                try:
                    error_response = f"Erreur echo tigrog2: {str(e)[:30]}"
                    self.send_single_message(error_response, sender_id, sender_info)
                except Exception as e2:
                    debug_print(f"Envoi erreur echo échoué: {e2}")
        
        # Lancer dans un thread séparé pour ne pas bloquer
        threading.Thread(target=send_echo_via_tigrog2, daemon=True).start()
    
    def handle_rebootg2_command(self, sender_id, sender_info):
        """Gérer la commande /rebootg2 (non documentée)"""
        info_print(f"RebootG2: {sender_info}")
        
        import subprocess
        import threading
        
        def reboot_and_telemetry():
            try:
                # Utiliser la configuration centralisée
                target_node_id = TIGROG2_NODE_ID
                target_node_hex = f"!{target_node_id:08x}"
                
                debug_print(f"Envoi reboot via API vers {target_node_hex}")
                
                # Commande 1: Reboot via l'API Meshtastic (fonctionne bien)
                try:
                    # Méthode plus simple : utiliser la méthode reboot de l'interface
                    if hasattr(self.interface, 'reboot'):
                        self.interface.reboot(target_node_id)
                        info_print("Commande reboot API envoyée avec succès")
                    else:
                        # Fallback: envoyer un message admin
                        admin_msg = {"reboot": True}
                        self.interface.sendData(
                            str(admin_msg).encode(),
                            destinationId=target_node_id,
                            portNum="ADMIN_APP",
                            wantAck=True
                        )
                        info_print("Commande reboot admin envoyée avec succès")
                    
                    # Attendre que l'interface se stabilise et que le nœud redémarre
                    debug_print("Attente redémarrage et stabilisation (50s)...")
                    time.sleep(50)
                    
                    # Envoyer confirmation après stabilisation
                    try:
                        self.send_single_message(f"🔄 Reboot {REMOTE_NODE_NAME} effectué", sender_id, sender_info)
                        time.sleep(2)
                    except Exception as e:
                        debug_print(f"Confirmation reboot échouée: {e}")
                        
                except Exception as e:
                    error_print(f"Erreur envoi reboot API: {e}")
                    time.sleep(10)
                    try:
                        error_msg = f"⚠️ Erreur reboot API: {str(e)[:50]}"
                        self.send_single_message(error_msg, sender_id, sender_info)
                    except Exception as e2:
                        debug_print(f"Message d'erreur reboot échoué: {e2}")
                    return
                
                # Commande 2: Request telemetry via commande système (plus fiable)
                time.sleep(5)  # Petit délai supplémentaire
                
                try:
                    import subprocess
                    debug_print("Demande télémétrie via commande système")
                    
                    # Utiliser la configuration centralisée pour le port
                    telemetry_cmd = [
                        'meshtastic', 
                        '--port', SERIAL_PORT, 
                        '--dest', target_node_hex, 
                        '--request-telemetry'
                    ]
                    
                    debug_print(f"Exécution: {' '.join(telemetry_cmd)}")
                    result = subprocess.run(telemetry_cmd, 
                                          capture_output=True, 
                                          text=True, 
                                          timeout=30)
                    
                    if result.returncode == 0:
                        # Parser et formater le résultat de télémétrie
                        telemetry_output = result.stdout.strip()
                        if telemetry_output and len(telemetry_output) > 10:
                            # Extraire les informations pertinentes et nettoyer
                            lines = telemetry_output.split('\n')
                            useful_lines = []
                            
                            for line in lines:
                                line = line.strip()
                                if line and not line.startswith('Connected to') and not line.startswith('Requesting'):
                                    # Garder les lignes avec des données utiles
                                    if any(keyword in line.lower() for keyword in ['voltage', 'current', 'temperature', 'humidity', 'pressure', 'battery']):
                                        useful_lines.append(line)
                            
                            if useful_lines:
                                response = f"📊 Télémétrie {REMOTE_NODE_NAME}:\n" + "\n".join(useful_lines[:5])  # Max 5 lignes
                            else:
                                response = f"📊 Télémétrie {REMOTE_NODE_NAME}:\n{telemetry_output[:150]}"
                        else:
                            response = f"📊 Télémétrie {REMOTE_NODE_NAME} (aucune donnée reçue)"
                        
                        # Attendre un peu avant d'envoyer la télémétrie
                        time.sleep(3)
                        try:
                            self.send_response_chunks(response, sender_id, sender_info)
                            self.log_conversation(sender_id, sender_info, "/rebootg2", response)
                        except Exception as e:
                            debug_print(f"Envoi télémétrie échoué: {e}")
                    else:
                        try:
                            error_output = result.stderr.strip() if result.stderr else "Erreur inconnue"
                            error_msg = f"⚠️ Erreur télémétrie: {error_output[:80]}"
                            self.send_single_message(error_msg, sender_id, sender_info)
                        except Exception as e:
                            debug_print(f"Message d'erreur télémétrie échoué: {e}")
                        
                except subprocess.TimeoutExpired:
                    try:
                        self.send_single_message("⏱️ Timeout demande télémétrie", sender_id, sender_info)
                    except Exception as e:
                        debug_print(f"Message timeout télémétrie échoué: {e}")
                except Exception as e:
                    error_print(f"Erreur demande télémétrie: {e}")
                    try:
                        error_msg = f"⚠️ Erreur télémétrie: {str(e)[:60]}"
                        self.send_single_message(error_msg, sender_id, sender_info)
                    except Exception as e2:
                        debug_print(f"Message d'erreur télémétrie échoué: {e2}")
                
            except Exception as e:
                time.sleep(10)
                try:
                    error_msg = f"⚠️ Erreur général: {str(e)[:80]}"
                    error_print(f"Erreur rebootg2: {e}")
                    self.send_single_message(error_msg, sender_id, sender_info)
                except Exception as e2:
                    debug_print(f"Message d'erreur général échoué: {e2}")
        
        # Lancer dans un thread séparé pour ne pas bloquer
        threading.Thread(target=reboot_and_telemetry, daemon=True).start()
    
    def handle_reboot_command(self, sender_id, sender_info):
        """Gérer la commande /reboot - redémarrage du Pi5 (commande cachée)"""
        info_print(f"REBOOT PI5 demandé par: {sender_info}")
        
        import subprocess
        import threading
        
        def reboot_pi5():
            try:
                # Message de confirmation
                self.send_single_message("🔄 Redémarrage Pi5 en cours...", sender_id, sender_info)
                
                # Log de sécurité
                info_print(f"🚨 REDÉMARRAGE PI5 INITIÉ PAR {sender_info} (!{sender_id:08x})")
                
                # Attendre 3 secondes pour envoyer le message
                time.sleep(3)
                
                # Arrêt propre du bot
                info_print("🛑 Arrêt du bot avant redémarrage système")
                
                # Sauvegarder les données avant redémarrage
                if self.node_manager:
                    self.node_manager.save_node_names(force=True)
                    debug_print("💾 Base de nœuds sauvegardée")
                
                # Commande de redémarrage système - méthode fichier signal
                try:
                    # Créer un fichier signal pour le redémarrage
                    signal_file = '/tmp/reboot_requested'
                    with open(signal_file, 'w') as f:
                        f.write(f"Redémarrage demandé par {sender_info} (!{sender_id:08x})\n")
                        f.write(f"Timestamp: {time.time()}\n")
                    
                    debug_print(f"Fichier signal créé: {signal_file}")
                    info_print("📁 Signal de redémarrage créé - nécessite script de surveillance système")
                    
                    # Message alternatif à l'utilisateur
                    try:
                        self.send_single_message("📁 Signal redémarrage créé", sender_id, sender_info)
                    except:
                        pass
                    
                except Exception as e:
                    error_msg = f"⚠️ Erreur création signal: {str(e)[:50]}"
                    debug_print(error_msg)
                    try:
                        self.send_single_message(error_msg, sender_id, sender_info)
                    except:
                        pass
                
            except subprocess.TimeoutExpired:
                info_print("⏱️ Timeout sur commande reboot (normal)")
            except Exception as e:
                error_msg = f"⚠️ Erreur redémarrage: {str(e)[:50]}"
                error_print(f"Erreur reboot Pi5: {e}")
                try:
                    self.send_single_message(error_msg, sender_id, sender_info)
                except:
                    pass  # Si le système redémarre, l'envoi peut échouer
        
        # Lancer dans un thread séparé
        threading.Thread(target=reboot_pi5, daemon=True).start()
    
    def handle_g2_command(self, sender_id, sender_info):
        """Gérer la commande /g2 - paramètres de configuration tigrog2 (commande cachée)"""
        info_print(f"G2 Config: {sender_info}")
        
        import threading
        
        def get_g2_config():
            try:
                # Se connecter à tigrog2 via TCP
                import meshtastic.tcp_interface
                
                debug_print(f"Connexion TCP à {REMOTE_NODE_HOST}...")
                remote_interface = meshtastic.tcp_interface.TCPInterface(
                    hostname=REMOTE_NODE_HOST, 
                    portNumber=4403
                )
                
                # Attendre la connexion
                time.sleep(2)
                
                # Récupérer les informations de configuration
                config_info = []
                
                # 1. Informations générales du nœud
                if hasattr(remote_interface, 'localNode') and remote_interface.localNode:
                    local_node = remote_interface.localNode
                    
                    # Nom du nœud
                    if hasattr(local_node, 'shortName'):
                        config_info.append(f"📡 {local_node.shortName}")
                    
                    # ID du nœud
                    if hasattr(local_node, 'nodeNum'):
                        config_info.append(f"🔢 ID: !{local_node.nodeNum:08x}")
                    
                    # Version firmware si disponible
                    if hasattr(local_node, 'firmwareVersion'):
                        config_info.append(f"📦 FW: {local_node.firmwareVersion}")
                
                # 2. Configuration LoRa si accessible
                try:
                    # Essayer de récupérer la configuration radio
                    if hasattr(remote_interface, 'getNode') and hasattr(remote_interface, 'localNode'):
                        node_info = remote_interface.localNode
                        if hasattr(node_info, 'radioConfig'):
                            radio_config = node_info.radioConfig
                            if hasattr(radio_config, 'modemConfig'):
                                config_info.append(f"📻 Preset: {radio_config.modemConfig}")
                except:
                    debug_print("Configuration radio non accessible")
                
                # 3. Statistiques des nœuds
                nodes_count = len(getattr(remote_interface, 'nodes', {}))
                config_info.append(f"🗂️ Nœuds: {nodes_count}")
                
                # 4. Informations réseau si disponibles
                try:
                    nodes = getattr(remote_interface, 'nodes', {})
                    direct_nodes = 0
                    for node_id, node_info in nodes.items():
                        if isinstance(node_info, dict):
                            hops_away = node_info.get('hopsAway', None)
                            if hops_away == 0:
                                direct_nodes += 1
                    
                    config_info.append(f"🎯 Direct: {direct_nodes}")
                except:
                    debug_print("Statistiques réseau non disponibles")
                
                remote_interface.close()
                
                # Construire la réponse
                if config_info:
                    response = f"⚙️ Config {REMOTE_NODE_NAME}:\n" + "\n".join(config_info)
                else:
                    response = f"⚠️ {REMOTE_NODE_NAME} config inaccessible"
                
                self.log_conversation(sender_id, sender_info, "/g2", response)
                self.send_response_chunks(response, sender_id, sender_info)
                
            except Exception as e:
                error_msg = f"⚠️ Erreur config {REMOTE_NODE_NAME}: {str(e)[:50]}"
                error_print(f"Erreur G2 config: {e}")
                try:
                    self.send_single_message(error_msg, sender_id, sender_info)
                except Exception as e2:
                    debug_print(f"Envoi erreur /g2 échoué: {e2}")
        
        # Lancer dans un thread séparé pour ne pas bloquer
        threading.Thread(target=get_g2_config, daemon=True).start()
    
    def handle_sys_command(self, sender_id, sender_info):
        """Gérer la commande /sys"""
        info_print(f"Sys: {sender_info}")
        
        import subprocess
        import threading
        
        def get_system_info():
            try:
                system_info = []
                
                # 1. Température CPU (RPI5)
                try:
                    # Méthode 1: vcgencmd (Raspberry Pi)
                    temp_cmd = ['vcgencmd', 'measure_temp']
                    temp_result = subprocess.run(temp_cmd, 
                                               capture_output=True, 
                                               text=True, 
                                               timeout=5)
                    
                    if temp_result.returncode == 0:
                        temp_output = temp_result.stdout.strip()
                        # Format: temp=45.1'C
                        if 'temp=' in temp_output:
                            temp_value = temp_output.split('=')[1].replace("'C", "°C")
                            system_info.append(f"🌡️ CPU: {temp_value}")
                        else:
                            system_info.append(f"🌡️ CPU: {temp_output}")
                    else:
                        # Fallback: lecture du fichier thermal_zone
                        try:
                            with open('/sys/class/thermal/thermal_zone0/
