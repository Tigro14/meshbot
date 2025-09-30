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
        self._last_echo_id = None  # Cache doublons echo 

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
        
        # ⚠️ ANTI-DOUBLON : Vérifier si on a déjà traité ce message récemment
        message_id = f"{sender_id}_{message}_{int(time.time())}"
        if hasattr(self, '_last_echo_id') and self._last_echo_id == message_id:
            debug_print("⚠️ Echo déjà traité, ignoré")
            return
        self._last_echo_id = message_id
        
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
            remote_interface = None
            try:
                # Se connecter à tigrog2 via TCP
                import meshtastic.tcp_interface
                
                debug_print(f"Connexion TCP à tigrog2 pour echo...")
                remote_interface = meshtastic.tcp_interface.TCPInterface(
                    hostname=REMOTE_NODE_HOST, 
                    portNumber=4403
                )
                
                # Attendre la connexion stable
                time.sleep(3)
                
                # Créer la réponse avec l'identifiant court en préambule
                author_short = self._get_short_name(sender_id)
                echo_response = f"{author_short}: {echo_text}"
                
                debug_print(f"Envoi broadcast: '{echo_response}'")
                
                # Envoyer le message en BROADCAST via tigrog2
                remote_interface.sendText(echo_response)
                
                # Attendre que le message soit bien transmis au radio
                time.sleep(4)
                
                debug_print(f"✅ Echo diffusé via tigrog2: '{echo_response}'")
                
                # Log de la conversation
                self.log_conversation(sender_id, sender_info, message, echo_response)
                
            except Exception as e:
                error_print(f"Erreur echo via tigrog2: {e}")
                try:
                    error_response = f"Erreur echo tigrog2: {str(e)[:30]}"
                    self.send_single_message(error_response, sender_id, sender_info)
                except Exception as e2:
                    debug_print(f"Envoi erreur echo échoué: {e2}")
            finally:
                # Fermeture propre avec gestion d'erreur silencieuse
                if remote_interface:
                    try:
                        remote_interface.close()
                    except:
                        pass  # Ignorer les erreurs de fermeture
        
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
                        if 'temp=' in temp_output:
                            temp_value = temp_output.split('=')[1].replace("'C", "°C")
                            system_info.append(f"🌡️ CPU: {temp_value}")
                        else:
                            system_info.append(f"🌡️ CPU: {temp_output}")
                    else:
                        # Fallback: lecture du fichier thermal_zone
                        try:
                            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                                temp_millis = int(f.read().strip())
                                temp_celsius = temp_millis / 1000.0
                                system_info.append(f"🌡️ CPU: {temp_celsius:.1f}°C")
                        except:
                            system_info.append("🌡️ CPU: N/A")
                            
                except Exception as e:
                    debug_print(f"Erreur température: {e}")
                    system_info.append("🌡️ CPU: Error")
                
                # 2. Uptime simplifié
                try:
                    # Méthode 1: uptime -p (format simple)
                    uptime_cmd = ['uptime', '-p']
                    uptime_result = subprocess.run(uptime_cmd, 
                                                 capture_output=True, 
                                                 text=True, 
                                                 timeout=5)
                    
                    if uptime_result.returncode == 0:
                        uptime_output = uptime_result.stdout.strip()
                        uptime_clean = uptime_output.replace('up ', '')
                        system_info.append(f"⏱️ Up: {uptime_clean}")
                    else:
                        # Fallback: /proc/uptime
                        with open('/proc/uptime', 'r') as f:
                            uptime_seconds = float(f.read().split()[0])
                            days = int(uptime_seconds // 86400)
                            hours = int((uptime_seconds % 86400) // 3600)
                            minutes = int((uptime_seconds % 3600) // 60)
                            
                            if days > 0:
                                uptime_str = f"{days}d {hours}h"
                            elif hours > 0:
                                uptime_str = f"{hours}h {minutes}m"
                            else:
                                uptime_str = f"{minutes}m"
                            
                            system_info.append(f"⏱️ Up: {uptime_str}")
                            
                except Exception as e:
                    debug_print(f"Erreur uptime: {e}")
                    system_info.append("⏱️ Uptime: Error")
                
                # 3. Load Average
                try:
                    with open('/proc/loadavg', 'r') as f:
                        loadavg = f.read().strip().split()
                        # Format: "0.15 0.25 0.30 1/123 12345"
                        load_1m = float(loadavg[0])
                        load_5m = float(loadavg[1])
                        load_15m = float(loadavg[2])
                        system_info.append(f"📊 Load: {load_1m:.2f} {load_5m:.2f} {load_15m:.2f}")
                        
                except Exception as e:
                    debug_print(f"Erreur load average: {e}")
                
                # 4. Mémoire
                try:
                    with open('/proc/meminfo', 'r') as f:
                        meminfo = f.read()
                    
                    mem_total = None
                    mem_available = None
                    
                    for line in meminfo.split('\n'):
                        if line.startswith('MemTotal:'):
                            mem_total = int(line.split()[1])
                        elif line.startswith('MemAvailable:'):
                            mem_available = int(line.split()[1])
                    
                    if mem_total and mem_available:
                        mem_used = mem_total - mem_available
                        mem_percent = (mem_used / mem_total) * 100
                        mem_total_mb = mem_total // 1024
                        mem_used_mb = mem_used // 1024
                        
                        system_info.append(f"💾 RAM: {mem_used_mb}MB/{mem_total_mb}MB ({mem_percent:.0f}%)")
                        
                except Exception as e:
                    debug_print(f"Erreur mémoire: {e}")
                
                # Construire la réponse finale
                if system_info:
                    response = "🖥️ Système RPI5:\n" + "\n".join(system_info)
                else:
                    response = "⚠️ Impossible de récupérer les infos système"
                
                self.send_response_chunks(response, sender_id, sender_info)
                self.log_conversation(sender_id, sender_info, "/sys", response)
                
            except Exception as e:
                error_msg = f"⚠️ Erreur système: {str(e)[:100]}"
                error_print(f"Erreur sys: {e}")
                self.send_single_message(error_msg, sender_id, sender_info)
        
        # Lancer dans un thread séparé pour ne pas bloquer
        threading.Thread(target=get_system_info, daemon=True).start()

    def handle_my_command(self, sender_id, sender_info):
        """Gérer la commande /my - infos signal vues par tigrog2 uniquement (antenne locale non fiable)"""
        info_print(f"My: {sender_info}")
        
        import threading
        
        def get_remote_signal_info():
            try:
                # Récupérer les nœuds de tigrog2 avec leurs informations de signal
                remote_nodes = self.remote_nodes_client.get_remote_nodes(REMOTE_NODE_HOST)
                
                if not remote_nodes:
                    response = f"⚠️ {REMOTE_NODE_NAME} inaccessible"
                    self.send_single_message(response, sender_id, sender_info)
                    return
                
                # Chercher le nœud expéditeur dans les données de tigrog2
                sender_node_data = None
                for node in remote_nodes:
                    if node['id'] == sender_id:
                        sender_node_data = node
                        break
                
                if sender_node_data:
                    # Debug : examiner toutes les données reçues
                    debug_print(f"Données complètes pour {sender_info}: {sender_node_data}")
                    
                    # Infos tigrog2 uniquement (source fiable)
                    response_parts = []
                    
                    # RSSI + SNR sur une ligne
                    rssi = sender_node_data.get('rssi', 0)
                    snr = sender_node_data.get('snr', 0.0)
                    
                    # Debug spécifique RSSI
                    debug_print(f"RSSI brut: {rssi} (type: {type(rssi)})")
                    debug_print(f"SNR brut: {snr} (type: {type(snr)})")
                    
                    # Estimation RSSI depuis SNR si RSSI=0
                    display_rssi = rssi
                    rssi_estimated = False
                    
                    if rssi == 0 and snr != 0:
                        # Formule empirique : RSSI ≈ -100 + (SNR * 2.5)
                        # Cette estimation est basée sur des observations terrain LoRa
                        display_rssi = int(-100 + (snr * 2.5))
                        rssi_estimated = True
                        debug_print(f"RSSI estimé depuis SNR: {display_rssi}dBm")
                    
                    if display_rssi != 0 or snr != 0:
                        rssi_icon = get_signal_quality_icon(display_rssi) if display_rssi != 0 else "📶"
                        
                        if rssi_estimated:
                            rssi_str = f"~{display_rssi}dBm"  # ~ pour indiquer estimation
                        elif display_rssi != 0:
                            rssi_str = f"{display_rssi}dBm"
                        else:
                            rssi_str = "n/a"
                        
                        snr_str = f"SNR:{snr:.1f}dB" if snr != 0 else "SNR:n/a"
                        response_parts.append(f"{rssi_icon} {rssi_str} {snr_str}")
                    
                    # Qualité + temps sur une ligne (utiliser RSSI estimé pour la qualité)
                    quality_desc = self._get_signal_quality_description(display_rssi, snr)
                    last_heard = sender_node_data.get('last_heard', 0)
                    if last_heard > 0:
                        time_str = format_elapsed_time(last_heard)
                        response_parts.append(f"📈 {quality_desc} ({time_str})")
                    else:
                        response_parts.append(f"📈 {quality_desc}")
                    
                    # Distance de tigrog2 si disponible (utiliser RSSI estimé)
                    if display_rssi != 0 and display_rssi > -150:
                        distance_est = self._estimate_distance_from_rssi(display_rssi)
                        response_parts.append(f"📍 ~{distance_est} de {REMOTE_NODE_NAME}")
                    
                    # Statut liaison directe avec tigrog2
                    response_parts.append(f"🎯 Direct → {REMOTE_NODE_NAME}")
                    
                    response = "\n".join(response_parts)
                    
                else:
                    # Nœud pas trouvé dans tigrog2 - probablement relayé
                    response_parts = [
                        f"⚠️ Pas direct → {REMOTE_NODE_NAME}",
                        "🔀 Messages relayés"
                    ]
                    
                    # Suggérer des nœuds tigrog2 comme relays potentiels
                    potential_relays = self._find_tigrog2_relays(remote_nodes)
                    if potential_relays:
                        best_relay = potential_relays[0]  # Le plus fort
                        response_parts.append(f"📡 Via réseau mesh")
                        response_parts.append(f"   (ex: {truncate_text(best_relay['name'], 8)})")
                    else:
                        response_parts.append("❓ Route mesh complexe")
                    
                    response = "\n".join(response_parts)
                
                self.log_conversation(sender_id, sender_info, "/my", response)
                self.send_response_chunks(response, sender_id, sender_info)
                
            except Exception as e:
                error_print(f"Erreur commande /my: {e}")
                try:
                    error_response = f"⚠️ Erreur: {str(e)[:30]}"
                    self.send_single_message(error_response, sender_id, sender_info)
                except Exception as e2:
                    debug_print(f"Envoi erreur /my échoué: {e2}")
        
        # Lancer dans un thread séparé pour ne pas bloquer
        threading.Thread(target=get_remote_signal_info, daemon=True).start()
    
    def _get_signal_quality_description(self, rssi, snr):
        """Obtenir une description textuelle de la qualité du signal"""
        if rssi == 0 and snr == 0:
            return "Inconnue"
        
        # Classification basée sur RSSI principalement
        if rssi >= -80:
            return "Excellente"
        elif rssi >= -100:
            if snr >= 5:
                return "Très bonne"
            else:
                return "Bonne"
        elif rssi >= -120:
            if snr >= 0:
                return "Correcte"
            else:
                return "Faible"
        elif rssi > -150:
            if snr >= -5:
                return "Très faible"
            else:
                return "Critique"
        else:
            return "Inconnue"
    
    def _estimate_distance_from_rssi(self, rssi):
        """Estimation approximative de distance basée sur RSSI (LoRa 868MHz)"""
        # Formule approximative : distance = 10^((Tx_Power - RSSI - 32.44 - 20*log10(freq_MHz)) / 20)
        # Supposons Tx_Power = 20dBm, freq = 868MHz
        # Simplification pour estimation rapide
        
        if rssi >= -80:
            return "<100m"
        elif rssi >= -90:
            return "100-300m" 
        elif rssi >= -100:
            return "300m-1km"
        elif rssi >= -110:
            return "1-3km"
        elif rssi >= -120:
            return "3-10km"
        elif rssi >= -130:
            return "10-20km"
        else:
            return ">20km"
    
    def _find_tigrog2_relays(self, remote_nodes):
        """Trouver les meilleurs relays potentiels dans les données tigrog2"""
        if not remote_nodes:
            return []
        
        # Trier par qualité de signal (RSSI décroissant)
        sorted_relays = sorted(
            [node for node in remote_nodes if node.get('rssi', 0) != 0],
            key=lambda x: x.get('rssi', -999),
            reverse=True
        )
        
        return sorted_relays[:3]  # Top 3 des meilleurs relays potentiels
    
    def process_text_message(self, packet, decoded, message):
        """Traiter un message texte"""
        sender_id = packet.get('from', 0)
        to_id = packet.get('to', 0)
        my_id = None
        
        if hasattr(self.interface, 'localNode') and self.interface.localNode:
            my_id = getattr(self.interface.localNode, 'nodeNum', 0)
        
        is_for_me = (to_id == my_id) if my_id else False
        is_from_me = (sender_id == my_id) if my_id else False
        is_broadcast = to_id in [0xFFFFFFFF, 0]  # Messages broadcast
        sender_info = self.node_manager.get_node_name(sender_id, self.interface)
        
        # NOUVEAU : Gérer /echo sur les messages publics
        if message.startswith('/echo ') and (is_broadcast or is_for_me) and not is_from_me:
            # /echo fonctionne sur les messages publics ET privés, mais pas de nous-mêmes
            info_print(f"ECHO PUBLIC de {sender_info}: '{message}' (Broadcast:{is_broadcast})")
            self.handle_echo_command(message, sender_id, sender_info, packet)
            return
        
        # Messages publics (broadcast) - ignorer les autres commandes
        if is_broadcast and not is_from_me:
            if DEBUG_MODE and not message.startswith('/echo'):
                debug_print(f"Message public ignoré: '{message}'")
            return
        
        # Log seulement les messages pour nous ou en mode debug
        if is_for_me or DEBUG_MODE:
            info_print(f"MESSAGE REÇU de {sender_info}: '{message}' (ForMe:{is_for_me})")
        
        # Traiter les commandes seulement si c'est pour nous
        if not is_for_me:
            if DEBUG_MODE:
                debug_print("Message public ignoré")
            return
        
        # Router les commandes
        if message.startswith('/bot '):
            self.handle_bot_command(message, sender_id, sender_info)
        elif message.startswith('/power'):
            self.handle_power_command(sender_id, sender_info)
        elif message.startswith('/rx'):
            self.handle_rx_command(message, sender_id, sender_info)
        elif message.startswith('/my'):
            self.handle_my_command(sender_id, sender_info)
        elif message.startswith('/echo '):
            self.handle_echo_command(message, sender_id, sender_info, packet)
        elif message.startswith('/legend'):
            self.handle_legend_command(sender_id, sender_info)
        elif message.startswith('/help'):
            self.handle_help_command(sender_id, sender_info)
        elif message.startswith('/rebootg2'):
            self.handle_rebootg2_command(sender_id, sender_info)
        elif message.startswith('/rebootpi'):
            self.handle_reboot_command(sender_id, sender_info)
        elif message.startswith('/g2'):
            self.handle_g2_command(sender_id, sender_info)
        elif message.startswith('/sys'):
            self.handle_sys_command(sender_id, sender_info)
        else:
            # Commande non reconnue - afficher l'aide au lieu de l'ignorer
            if message.startswith('/'):
                info_print(f"Commande inconnue de {sender_info}: '{message}'")
                self.handle_help_command(sender_id, sender_info)
            else:
                # Message normal (pas de commande)
                if DEBUG_MODE:
                    debug_print(f"Message normal reçu: '{message}'")
