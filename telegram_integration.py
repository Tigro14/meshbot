#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module d'intégration Telegram dans le bot Meshtastic existant
Avec debug systemd complet
"""

import json
import os
import time
import threading
from config import *
from utils import *

class TelegramIntegration:
    def __init__(self, message_handler, node_manager, context_manager):
        self.message_handler = message_handler
        self.node_manager = node_manager
        self.context_manager = context_manager
        
        # Utiliser les configurations centralisées
        self.queue_file = TELEGRAM_QUEUE_FILE
        self.response_file = TELEGRAM_RESPONSE_FILE
        
        self.running = False
        self.processor_thread = None
        
        # Créer les fichiers s'ils n'existent pas
        self._ensure_files_exist()
        
    def _ensure_files_exist(self):
        """Créer les fichiers de communication s'ils n'existent pas"""
        for file_path in [self.queue_file, self.response_file]:
            if not os.path.exists(file_path):
                with open(file_path, 'w') as f:
                    json.dump([], f)
    
    def start(self):
        """Démarrer le processeur de requêtes Telegram"""
        if self.running:
            return
        
        self.running = True
        self.processor_thread = threading.Thread(target=self._process_telegram_requests, daemon=True)
        self.processor_thread.start()
        info_print("Interface Telegram démarrée avec debug complet")
    
    def stop(self):
        """Arrêter le processeur"""
        self.running = False
        if self.processor_thread:
            self.processor_thread.join(timeout=5)
        info_print("Interface Telegram arrêtée")
    
    def _process_telegram_requests(self):
        """Traiter les requêtes Telegram en continu"""
        info_print("Thread processeur Telegram démarré")
        
        while self.running:
            try:
                self._check_and_process_queue()
                time.sleep(1)  # Vérifier chaque seconde
            except Exception as e:
                error_print(f"Erreur processeur Telegram: {e}")
                import traceback
                error_print(f"Stack trace: {traceback.format_exc()}")
                time.sleep(5)  # Attendre plus longtemps en cas d'erreur
        
        info_print("Thread processeur Telegram terminé")
    
    def _check_and_process_queue(self):
        """Vérifier et traiter la queue des requêtes"""
        try:
            if not os.path.exists(self.queue_file):
                return
            
            # Lire les requêtes
            with open(self.queue_file, 'r') as f:
                try:
                    requests = json.load(f)
                except json.JSONDecodeError:
                    return
            
            if not requests:
                return
            
            debug_print(f"{len(requests)} requêtes Telegram en attente")
            
            # Traiter chaque requête
            for request in requests:
                try:
                    request_id = request.get("id", "unknown")
                    command = request.get("command", "")
                    user_info = request.get("user", {})
                    username = user_info.get("username", "Unknown")
                    
                    info_print(f"Traitement requête Telegram {request_id}: {command} de {username}")
                    
                    start_processing = time.time()
                    response = self._process_single_request(request)
                    end_processing = time.time()
                    
                    processing_duration = end_processing - start_processing
                    info_print(f"Requête {request_id} traitée en {processing_duration:.2f}s")
                    
                    self._send_response(request["id"], response)
                    
                except Exception as e:
                    error_response = f"Erreur traitement: {str(e)}"
                    error_print(f"Erreur traitement requête Telegram: {e}")
                    import traceback
                    error_print(f"Stack trace: {traceback.format_exc()}")
                    self._send_response(request.get("id", "unknown"), error_response)
            
            # Vider la queue (toutes les requêtes ont été traitées)
            with open(self.queue_file, 'w') as f:
                json.dump([], f)
                
        except Exception as e:
            error_print(f"Erreur lecture queue Telegram: {e}")
            import traceback
            error_print(f"Stack trace: {traceback.format_exc()}")
    
    def _process_single_request(self, request):
        """Traiter une requête Telegram individuelle"""
        command = request.get("command", "").strip()
        user_info = request.get("user", {})
        telegram_id = user_info.get("telegram_id", 0)
        username = user_info.get("username", "Telegram")
        
        debug_print(f"Traitement commande Telegram: {command} de {username}")
        
        # Simuler un sender_id Meshtastic basé sur l'ID Telegram
        # Utiliser les 4 derniers octets de l'ID Telegram
        sender_id = telegram_id & 0xFFFFFFFF
        sender_info = f"TG:{username}"
        
        # Router la commande vers le gestionnaire approprié
        if command.startswith('/bot '):
            return self._handle_bot_command(command, sender_id, sender_info)
        elif command.startswith('/power'):
            return self._handle_power_command(sender_id, sender_info)
        elif command.startswith('/rx'):
            return self._handle_rx_command(command, sender_id, sender_info)
        elif command.startswith('/my'):
            return self._handle_my_command(sender_id, sender_info)
        elif command.startswith('/sys'):
            return self._handle_sys_command(sender_id, sender_info)
        elif command.startswith('/legend'):
            return self._handle_legend_command(sender_id, sender_info)
        elif command.startswith('/echo '):
            return self._handle_echo_command(command, sender_id, sender_info)
        elif command.startswith('/nodes '):
            return self._handle_nodes_command(command, sender_id, sender_info)
        elif command.startswith('/help'):
            return self._handle_help_command(sender_id, sender_info)
        else:
            return f"Commande inconnue: {command}"
    
    def _handle_bot_command(self, command, sender_id, sender_info):
        """Traiter /bot depuis Telegram avec debug complet"""
        try:
            prompt = command[5:].strip()  # Retirer "/bot "
            
            if not prompt:
                return "Usage: /bot <question>"
            
            info_print(f"Bot Telegram: {sender_info}: '{prompt}'")
            
            # Vérifier la disponibilité de llama.cpp
            if not self.message_handler.llama_client.test_connection():
                error_print("Serveur llama.cpp non disponible pour requête Telegram")
                return "Erreur: Serveur IA non disponible"
            
            start_time = time.time()
            info_print(f"Début traitement IA Telegram à {time.strftime('%H:%M:%S')}")
            
            # IMPORTANT: Utiliser la méthode spécifique Telegram pour les réponses étendues
            try:
                response = self.message_handler.llama_client.query_llama_telegram(prompt, sender_id)
                info_print(f"Réponse IA reçue: '{response[:50]}...'")
            except Exception as llama_error:
                error_print(f"Erreur lors de l'appel à llama: {llama_error}")
                import traceback
                error_print(f"Stack trace llama: {traceback.format_exc()}")
                return f"Erreur IA: {str(llama_error)[:100]}"
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            # Log spécialisé pour Telegram avec debug complet
            info_print(f"Traitement IA Telegram terminé en {processing_time:.2f}s")
            conversation_print("=" * 50)
            conversation_print(f"TELEGRAM USER: {sender_info} ({sender_id})")
            conversation_print(f"TELEGRAM QUERY: {prompt}")
            conversation_print(f"TELEGRAM RESPONSE: {response}")
            conversation_print(f"TELEGRAM TIME: {processing_time:.2f}s")
            conversation_print(f"TELEGRAM CONFIG: timeout={TELEGRAM_AI_CONFIG['timeout']}s, max_tokens={TELEGRAM_AI_CONFIG['max_tokens']}")
            conversation_print("=" * 50)
            
            # Nettoyage
            try:
                self.message_handler.llama_client.cleanup_cache()
                debug_print("Cache IA nettoyé après requête Telegram")
            except Exception as cleanup_error:
                error_print(f"Erreur nettoyage cache: {cleanup_error}")
            
            return response
            
        except Exception as e:
            error_print(f"Erreur /bot Telegram: {e}")
            import traceback
            error_print(f"Stack trace _handle_bot_command: {traceback.format_exc()}")
            return f"Erreur IA Telegram: {str(e)[:100]}"
    
    def _handle_power_command(self, sender_id, sender_info):
        """Traiter /power depuis Telegram"""
        try:
            info_print(f"Power Telegram: {sender_info}")
            esphome_data = self.message_handler.esphome_client.parse_esphome_data()
            info_print(f"Données ESPHome récupérées: {len(esphome_data)} chars")
            return esphome_data
        except Exception as e:
            error_print(f"Erreur /power Telegram: {e}")
            return f"Erreur /power: {str(e)}"
    
    def _handle_rx_command(self, command, sender_id, sender_info):
        """Traiter /rx depuis Telegram"""
        try:
            info_print(f"RX Telegram: {sender_info}")
            # Extraire le numéro de page
            page = 1
            parts = command.split()
            if len(parts) > 1:
                try:
                    page = int(parts[1])
                except ValueError:
                    page = 1
            
            report = self.message_handler.remote_nodes_client.get_tigrog2_paginated(page)
            info_print(f"Rapport RX généré: {len(report)} chars")
            return report
        except Exception as e:
            error_print(f"Erreur /rx Telegram: {e}")
            return f"Erreur /rx: {str(e)}"
    
    def _handle_my_command(self, sender_id, sender_info):
        """Traiter /my depuis Telegram (pas applicable pour Telegram)"""
        return "Commande /my non applicable depuis Telegram (réservée aux utilisateurs mesh)"
    
    def _handle_sys_command(self, sender_id, sender_info):
        """Traiter /sys depuis Telegram avec debug"""
        try:
            info_print(f"Sys Telegram: {sender_info}")
            import subprocess
            
            system_info = []
            
            # Température CPU
            try:
                temp_result = subprocess.run(['vcgencmd', 'measure_temp'], 
                                           capture_output=True, text=True, timeout=5)
                if temp_result.returncode == 0:
                    temp_output = temp_result.stdout.strip()
                    if 'temp=' in temp_output:
                        temp_value = temp_output.split('=')[1].replace("'C", "°C")
                        system_info.append(f"CPU: {temp_value}")
                    else:
                        system_info.append(f"CPU: {temp_output}")
                else:
                    system_info.append("CPU: N/A")
            except Exception as temp_error:
                error_print(f"Erreur température: {temp_error}")
                system_info.append("CPU: Error")
            
            # Uptime
            try:
                uptime_result = subprocess.run(['uptime'], capture_output=True, text=True, timeout=5)
                if uptime_result.returncode == 0:
                    uptime_output = uptime_result.stdout.strip()
                    uptime_clean = uptime_output.replace('  ', ' ')
                    parts = uptime_clean.split(',')
                    if len(parts) >= 1:
                        uptime_part = parts[0].strip()
                        if 'up' in uptime_part:
                            up_info = uptime_part.split('up')[1].strip()
                            system_info.append(f"Up: {up_info}")
                else:
                    system_info.append("Uptime: Error")
            except Exception as uptime_error:
                error_print(f"Erreur uptime: {uptime_error}")
                system_info.append("Uptime: Error")
            
            # Mémoire
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
                    system_info.append(f"RAM: {mem_used_mb}MB/{mem_total_mb}MB ({mem_percent:.0f}%)")
            except Exception as mem_error:
                error_print(f"Erreur mémoire: {mem_error}")
            
            if system_info:
                result = "Système RPI5:\n" + "\n".join(system_info)
                info_print(f"Info système générées: {len(result)} chars")
                return result
            else:
                return "Impossible de récupérer les infos système"
                
        except Exception as e:
            error_print(f"Erreur /sys Telegram: {e}")
            return f"Erreur /sys: {str(e)}"
    
    def _handle_legend_command(self, sender_id, sender_info):
        """Traiter /legend depuis Telegram"""
        try:
            info_print(f"Legend Telegram: {sender_info}")
            legend_text = self.message_handler.format_legend()
            return legend_text
        except Exception as e:
            error_print(f"Erreur /legend Telegram: {e}")
            return f"Erreur /legend: {str(e)}"
    
    def _handle_echo_command(self, command, sender_id, sender_info):
        """Traiter /echo depuis Telegram"""
        try:
            info_print(f"Echo Telegram: {sender_info}")
            echo_text = command[6:].strip()  # Retirer "/echo "
            
            if not echo_text:
                return "Usage: /echo <texte>"
            
            # Utiliser la méthode existante mais adaptée pour Telegram
            import threading
            import time
            
            def send_echo_via_tigrog2():
                try:
                    info_print(f"Connexion tigrog2 pour echo Telegram...")
                    import meshtastic.tcp_interface
                    
                    remote_interface = meshtastic.tcp_interface.TCPInterface(
                        hostname=REMOTE_NODE_HOST, 
                        portNumber=4403
                    )
                    
                    time.sleep(1)
                    
                    # Utiliser le nom d'utilisateur Telegram comme identifiant
                    username = sender_info.split(':')[1] if ':' in sender_info else sender_info
                    echo_response = f"{username}: {echo_text}"
                    
                    remote_interface.sendText(echo_response)
                    remote_interface.close()
                    
                    info_print(f"Echo Telegram diffusé via tigrog2: '{echo_response}'")
                    
                except Exception as e:
                    error_print(f"Erreur echo Telegram via tigrog2: {e}")
            
            # Lancer en thread
            threading.Thread(target=send_echo_via_tigrog2, daemon=True).start()
            
            return f"Echo diffusé: {echo_text}"
            
        except Exception as e:
            error_print(f"Erreur /echo Telegram: {e}")
            return f"Erreur /echo: {str(e)}"
    
    def _handle_nodes_command(self, command, sender_id, sender_info):
        """Traiter une commande de récupération de noeuds distants depuis Telegram"""
        try:
            info_print(f"Nodes Telegram: {sender_info}")
            parts = command.split(' ', 1)
            if len(parts) > 1:
                remote_host = parts[1].strip()
                info_print(f"Récupération noeuds distants: {remote_host}")
                nodes = self.message_handler.remote_nodes_client.get_remote_nodes(remote_host)
                
                if not nodes:
                    return f"Aucun noeud trouvé sur {remote_host}"
                
                response_lines = [f"Noeuds trouvés sur {remote_host} ({len(nodes)}):\n"]
                
                for node in nodes[:10]:  # Limiter à 10 pour Telegram
                    name = node.get('name', 'Unknown')
                    rssi = node.get('rssi', 0)
                    last_heard = node.get('last_heard', 0)
                    
                    # Temps depuis dernière réception
                    if last_heard > 0:
                        elapsed = int(time.time() - last_heard)
                        if elapsed < 60:
                            time_str = f"{elapsed}s"
                        elif elapsed < 3600:
                            time_str = f"{elapsed//60}m"
                        elif elapsed < 86400:
                            time_str = f"{elapsed//3600}h"
                        else:
                            time_str = f"{elapsed//86400}j"
                    else:
                        time_str = "n/a"
                    
                    response_lines.append(f"  • {name}: {rssi}dBm ({time_str})")
                
                if len(nodes) > 10:
                    response_lines.append(f"\n... et {len(nodes) - 10} autres")
                
                result = "\n".join(response_lines)
                info_print(f"Liste noeuds générée: {len(nodes)} noeuds")
                return result
            else:
                return "Usage: nodes <IP_du_noeud>\nEx: nodes 192.168.1.38"
                
        except Exception as e:
            error_print(f"Erreur /nodes Telegram: {e}")
            return f"Erreur nodes: {str(e)}"
    
    def _handle_help_command(self, sender_id, sender_info):
        """Traiter /help depuis Telegram"""
        help_text = """Bot Meshtastic - Commandes Telegram:

/bot <question> - Chat avec l'IA
/power - Info batterie/solaire
/rx [page] - Noeuds vus par tigrog2
/sys - Info système Pi5
/echo <texte> - Diffuser via tigrog2
/nodes <IP> - Noeuds d'un hôte distant
/legend - Légende signaux
/help - Cette aide

Note: /my non disponible depuis Telegram"""
        
        return help_text
    
    def _send_response(self, request_id, response):
        """Envoyer une réponse vers Telegram avec debug"""
        try:
            info_print(f"Envoi réponse Telegram pour {request_id}: {len(response)} chars")
            
            # Lire les réponses existantes
            responses = []
            if os.path.exists(self.response_file):
                with open(self.response_file, 'r') as f:
                    try:
                        responses = json.load(f)
                    except json.JSONDecodeError:
                        responses = []
            
            # Ajouter la nouvelle réponse
            response_data = {
                "request_id": request_id,
                "response": response,
                "timestamp": time.time()
            }
            
            responses.append(response_data)
            
            # Limiter le nombre de réponses stockées
            if len(responses) > 100:
                responses = responses[-50:]  # Garder les 50 plus récentes
                debug_print("File réponses Telegram nettoyée")
            
            # Écrire les réponses
            with open(self.response_file, 'w') as f:
                json.dump(responses, f)
            
            info_print(f"Réponse Telegram sauvegardée pour {request_id}")
            
        except Exception as e:
            error_print(f"Erreur envoi réponse Telegram: {e}")
            import traceback
            error_print(f"Stack trace _send_response: {traceback.format_exc()}")

# Fonction d'intégration dans main_bot.py
def integrate_telegram_bridge(bot_instance):
    """
    Fonction à ajouter dans main_bot.py pour intégrer Telegram
    
    Usage dans main_bot.py:
    
    # Après l'initialisation des gestionnaires, ajouter:
    from telegram_integration import integrate_telegram_bridge
    
    # Dans DebugMeshBot.__init__():
    self.telegram_integration = None
    
    # Dans DebugMeshBot.start(), après l'initialisation du message_handler:
    try:
        from telegram_integration import TelegramIntegration
        self.telegram_integration = TelegramIntegration(
            self.message_handler,
            self.node_manager,
            self.context_manager
        )
        self.telegram_integration.start()
        info_print("Interface Telegram intégrée")
    except ImportError:
        debug_print("Module Telegram non disponible")
    except Exception as e:
        error_print(f"Erreur intégration Telegram: {e}")
    
    # Dans DebugMeshBot.stop():
    if self.telegram_integration:
        self.telegram_integration.stop()
    """
    pass
