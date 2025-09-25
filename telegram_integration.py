#!/usr/bin/env python3
"""
Module d'intégration Telegram dans le bot Meshtastic existant
Version améliorée avec commande /nodes optimisée
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
        info_print("🔗 Interface Telegram démarrée")
    
    def stop(self):
        """Arrêter le processeur"""
        self.running = False
        if self.processor_thread:
            self.processor_thread.join(timeout=5)
        info_print("🔗 Interface Telegram arrêtée")
    
    def _process_telegram_requests(self):
        """Traiter les requêtes Telegram en continu"""
        while self.running:
            try:
                self._check_and_process_queue()
                time.sleep(1)  # Vérifier chaque seconde
            except Exception as e:
                error_print(f"Erreur processeur Telegram: {e}")
                time.sleep(5)  # Attendre plus longtemps en cas d'erreur
    
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
            
            # Traiter chaque requête
            processed_requests = []
            for request in requests:
                try:
                    response = self._process_single_request(request)
                    self._send_response(request["id"], response)
                    debug_print(f"Requête Telegram traitée: {request['command']}")
                except Exception as e:
                    error_response = f"Erreur traitement: {str(e)}"
                    self._send_response(request["id"], error_response)
                    error_print(f"Erreur traitement requête Telegram: {e}")
            
            # Vider la queue (toutes les requêtes ont été traitées)
            with open(self.queue_file, 'w') as f:
                json.dump([], f)
                
        except Exception as e:
            debug_print(f"Erreur lecture queue Telegram: {e}")
    
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
        elif command.startswith('/nodes'):
            return self._handle_nodes_command(sender_id, sender_info)
        elif command.startswith('/my'):
            return self._handle_my_command(sender_id, sender_info)
        elif command.startswith('/sys'):
            return self._handle_sys_command(sender_id, sender_info)
        elif command.startswith('/legend'):
            return self._handle_legend_command(sender_id, sender_info)
        elif command.startswith('/echo '):
            return self._handle_echo_command(command, sender_id, sender_info)
        elif command.startswith('/help'):
            return self._handle_help_command(sender_id, sender_info)
        else:
            return f"Commande inconnue: {command}"
    
    def _handle_nodes_command(self, sender_id, sender_info):
        """Traiter /nodes depuis Telegram - Version étendue optimisée pour Telegram"""
        try:
            info_print(f"Nodes (étendu): {sender_info}")
            
            # Récupérer les nœuds distants avec toutes les informations
            remote_nodes = self.message_handler.remote_nodes_client.get_remote_nodes(REMOTE_NODE_HOST)
            
            if not remote_nodes:
                return f"❌ Aucun nœud direct trouvé sur {REMOTE_NODE_NAME}"
            
            # Trier par SNR décroissant (plus fiable que RSSI en LoRa)
            remote_nodes.sort(key=lambda x: x.get('snr', -999), reverse=True)
            
            # Format étendu pour Telegram (sans pagination, noms longs)
            lines = []
            lines.append(f"📡 **Nœuds DIRECTS de {REMOTE_NODE_NAME}** ({len(remote_nodes)} nœuds):")
            
            for i, node in enumerate(remote_nodes, 1):
                # Informations complètes pour chaque nœud
                node_id = node['id']
                name = node['name']
                rssi = node.get('rssi', 0)
                snr = node.get('snr', 0.0)
                last_heard = node.get('last_heard', 0)
                
                # Debug temporaire pour voir les valeurs extraites des données Meshtastic
                debug_print(f"DEBUG node {name}: rssi={rssi}, snr={snr} (type: {type(snr)})")
                
                # Icône de qualité basée uniquement sur SNR (RSSI supprimé car buggé)
                if snr >= 10.0:  # Test avec vos valeurs les plus hautes
                    debug_print(f"DEBUG: SNR {snr} -> 🟢 (≥ 10.0)")
                    signal_icon = "🟢"  # Excellent SNR
                elif snr >= 5.0:
                    debug_print(f"DEBUG: SNR {snr} -> 🟡 (≥ 5.0)")
                    signal_icon = "🟡"  # Bon SNR
                elif snr >= 0.0:
                    debug_print(f"DEBUG: SNR {snr} -> 🟠 (≥ 0.0)")
                    signal_icon = "🟠"  # SNR faible mais utilisable
                else:
                    debug_print(f"DEBUG: SNR {snr} -> 🔴 (< 0.0)")
                    signal_icon = "🔴"  # SNR critique
                
                # Temps écoulé depuis dernière réception
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
                
                # Construire les métriques affichées
                metrics = []
                
                # RSSI seulement si non-zéro
                if rssi != 0:
                    metrics.append(f"RSSI: {rssi}dBm")
                
                # SNR toujours affiché
                metrics.append(f"SNR: {snr:.1f}dB")
                
                # Temps
                metrics.append(time_str)
                
                # Ligne formatée compacte (une seule ligne)
                line = f"{signal_icon} **{name}** - {' | '.join(metrics)}"
                
                lines.append(line)
            
            # Ajouter un footer informatif
            lines.append("")
            lines.append(f"🔍 Légende: 🟢 Excellent | 🟡 Bon | 🟠 Faible | 🔴 Critique")
            lines.append(f"📊 Triés par SNR (qualité LoRa), <3 jours")
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"❌ Erreur /nodes: {str(e)[:50]}"
    
    def _handle_bot_command(self, command, sender_id, sender_info):
        """Traiter /bot depuis Telegram"""
        try:
            # Capturer la sortie de la commande bot
            import io
            import sys
            from contextlib import redirect_stdout, redirect_stderr
            
            # Buffer pour capturer la réponse
            captured_output = io.StringIO()
            
            # Simuler l'interface pour éviter l'envoi réel de messages
            class TelegramInterface:
                def sendText(self, message, destinationId=None):
                    captured_output.write(message)
            
            # Remplacer temporairement l'interface
            original_interface = self.message_handler.interface
            self.message_handler.interface = TelegramInterface()
            
            try:
                self.message_handler.handle_bot_command(command, sender_id, sender_info)
                response = captured_output.getvalue()
                return response if response else "Pas de réponse du bot IA"
            finally:
                self.message_handler.interface = original_interface
                
        except Exception as e:
            return f"Erreur /bot: {str(e)}"
    
    def _handle_power_command(self, sender_id, sender_info):
        """Traiter /power depuis Telegram"""
        try:
            esphome_data = self.message_handler.esphome_client.parse_esphome_data()
            return esphome_data
        except Exception as e:
            return f"Erreur /power: {str(e)}"
    
    def _handle_rx_command(self, command, sender_id, sender_info):
        """Traiter /rx depuis Telegram"""
        try:
            # Extraire le numéro de page
            page = 1
            parts = command.split()
            if len(parts) > 1:
                try:
                    page = int(parts[1])
                except ValueError:
                    page = 1
            
            report = self.message_handler.remote_nodes_client.get_tigrog2_paginated(page)
            return report
        except Exception as e:
            return f"Erreur /rx: {str(e)}"
    
    def _handle_my_command(self, sender_id, sender_info):
        """Traiter /my depuis Telegram (pas applicable pour Telegram)"""
        return "Commande /my non applicable depuis Telegram (réservée aux utilisateurs mesh)"
    
    def _handle_sys_command(self, sender_id, sender_info):
        """Traiter /sys depuis Telegram - VERSION CORRIGÉE"""
        try:
            import subprocess
            
            system_info = []
            
            # 1. Température CPU
            try:
                temp_result = subprocess.run(['vcgencmd', 'measure_temp'], 
                                           capture_output=True, text=True, timeout=5)
                if temp_result.returncode == 0:
                    temp_output = temp_result.stdout.strip()
                    if 'temp=' in temp_output:
                        temp_value = temp_output.split('=')[1].replace("'C", "°C")
                        system_info.append(f"🌡 CPU: {temp_value}")
                    else:
                        system_info.append(f"🌡 CPU: {temp_output}")
                else:
                    # Fallback thermal_zone
                    try:
                        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                            temp_millis = int(f.read().strip())
                            temp_celsius = temp_millis / 1000.0
                            system_info.append(f"🌡 CPU: {temp_celsius:.1f}°C")
                    except:
                        system_info.append("🌡 CPU: N/A")
            except:
                system_info.append("🌡 CPU: N/A")
            
            # 2. Uptime ET Load - CORRECTION
            try:
                uptime_result = subprocess.run(['uptime'], capture_output=True, text=True, timeout=5)
                if uptime_result.returncode == 0:
                    uptime_output = uptime_result.stdout.strip()
                    
                    # Parser correctement uptime
                    if 'load average:' in uptime_output:
                        uptime_part, load_part = uptime_output.split('load average:', 1)
                        
                        # Extraire uptime
                        if ' up ' in uptime_part:
                            after_up = uptime_part.split(' up ')[1]
                            if 'user' in after_up:
                                up_time_parts = after_up.split(',')[:-1]  # Enlever "X users"
                                up_info = ','.join(up_time_parts).strip()
                            else:
                                up_info = after_up.strip()
                            system_info.append(f"⏱ Up: {up_info}")
                        
                        # Extraire load average
                        load_values = load_part.strip()
                        system_info.append(f"📊 Load: {load_values}")
                    else:
                        # Pas de load average
                        if ' up ' in uptime_output:
                            up_info = uptime_output.split(' up ')[1].split(',')[0].strip()
                            system_info.append(f"⏱ Up: {up_info}")
                else:
                    system_info.append("⏱ Uptime: Error")
            except:
                system_info.append("⏱ Uptime: Error")
            
            # 3. Mémoire
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
            except:
                pass
            
            if system_info:
                return "🖥 Système RPI5:\n" + "\n".join(system_info)
            else:
                return "Impossible de récupérer les infos système"
                
        except Exception as e:
            return f"Erreur /sys: {str(e)}"
        
    def _handle_legend_command(self, sender_id, sender_info):
        """Traiter /legend depuis Telegram"""
        try:
            legend_text = self.message_handler.format_legend()
            return legend_text
        except Exception as e:
            return f"Erreur /legend: {str(e)}"
    
    def _handle_echo_command(self, command, sender_id, sender_info):
        """Traiter /echo depuis Telegram"""
        try:
            echo_text = command[6:].strip()  # Retirer "/echo "
            
            if not echo_text:
                return "Usage: /echo <texte>"
            
            # Utiliser la méthode existante mais adaptée pour Telegram
            import threading
            import time
            
            def send_echo_via_tigrog2():
                try:
                    import meshtastic.tcp_interface
                    
                    remote_interface = meshtastic.tcp_interface.TCPInterface(
                        hostname=REMOTE_NODE_HOST, 
                        portNumber=4403
                    )
                    
                    time.sleep(1)
                    
                    # Utiliser le nom d'utilisateur Telegram comme identifiant
                    username = sender_info.split(':')[1] if ':' in sender_info else sender_info
                    echo_response = f"TG-{username}: {echo_text}"
                    
                    remote_interface.sendText(echo_response)
                    remote_interface.close()
                    
                    debug_print(f"Echo Telegram diffusé via tigrog2: '{echo_response}'")
                    
                except Exception as e:
                    error_print(f"Erreur echo Telegram via tigrog2: {e}")
            
            # Lancer en thread
            threading.Thread(target=send_echo_via_tigrog2, daemon=True).start()
            
            return f"📡 Echo diffusé: {echo_text}"
            
        except Exception as e:
            return f"Erreur /echo: {str(e)}"
    
    def _handle_help_command(self, sender_id, sender_info):
        """Traiter /help depuis Telegram"""
        help_text = """🤖 Bot Meshtastic - Commandes Telegram:

/bot <question> - Chat avec l'IA
/power - Info batterie/solaire
/rx [page] - Nœuds vus par tigrog2 (paginé)
/nodes - Liste complète des nœuds (format étendu)
/my - Vos signaux vus par tigrog2
/sys - Info système Pi5
/echo <texte> - Diffuser via tigrog2
/legend - Légende signaux
/help - Cette aide

Note: /my non disponible depuis Telegram pour les vraies métriques"""
        
        return help_text
    
    def _send_response(self, request_id, response):
        """Envoyer une réponse vers Telegram"""
        try:
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
            
            # Écrire les réponses
            with open(self.response_file, 'w') as f:
                json.dump(responses, f)
            
        except Exception as e:
            error_print(f"Erreur envoi réponse Telegram: {e}")

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
        info_print("✅ Interface Telegram intégrée")
    except ImportError:
        debug_print("📱 Module Telegram non disponible")
    except Exception as e:
        error_print(f"Erreur intégration Telegram: {e}")
    
    # Dans DebugMeshBot.stop():
    if self.telegram_integration:
        self.telegram_integration.stop()
    """
    pass
