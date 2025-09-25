#!/usr/bin/env python3
"""
Module d'intégration Telegram dans le bot Meshtastic existant
"""

import json
import os
import time
import threading
from config import *
from utils import *

# Importer spécifiquement le mapping s'il existe
try:
    from config import TELEGRAM_TO_MESH_MAPPING
except ImportError:
    TELEGRAM_TO_MESH_MAPPING = {}

class TelegramIntegration:
    def __init__(self, message_handler, node_manager, context_manager):
        self.message_handler = message_handler
        self.node_manager = node_manager
        self.context_manager = context_manager
        
        self.queue_file = TELEGRAM_QUEUE_FILE
        self.response_file = TELEGRAM_RESPONSE_FILE
        
        self.running = False
        self.processor_thread = None
        
        self._ensure_files_exist()
        
    def _ensure_files_exist(self):
        """Créer les fichiers de communication s'ils n'existent pas"""
        for file_path in [self.queue_file, self.response_file]:
            if not os.path.exists(file_path):
                try:
                    with open(file_path, 'w') as f:
                        json.dump([], f)
                    debug_print(f"Fichier créé: {file_path}")
                except Exception as e:
                    error_print(f"Erreur création {file_path}: {e}")
    
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
                time.sleep(1)
            except Exception as e:
                error_print(f"Erreur processeur Telegram: {e}")
                time.sleep(5)
    
    def _check_and_process_queue(self):
        """Vérifier et traiter la queue des requêtes"""
        try:
            if not os.path.exists(self.queue_file):
                return
            
            requests_to_process = []
            try:
                with open(self.queue_file, 'r') as f:
                    requests_data = json.load(f)
                    if isinstance(requests_data, list):
                        requests_to_process = requests_data.copy()
            except (json.JSONDecodeError, FileNotFoundError):
                return
            
            if not requests_to_process:
                return
            
            # Vider le fichier de queue
            try:
                with open(self.queue_file, 'w') as f:
                    json.dump([], f)
            except Exception as e:
                error_print(f"Erreur vidage queue: {e}")
            
            # Traiter chaque requête
            for request in requests_to_process:
                try:
                    request_id = request.get("id", "unknown")
                    debug_print(f"Traitement requête Telegram: {request_id}")
                    
                    response = self._process_single_request(request)
                    self._send_response(request_id, response)
                    
                    info_print(f"✅ Requête Telegram {request_id} traitée")
                    
                except Exception as e:
                    error_response = f"Erreur traitement: {str(e)[:80]}"
                    request_id = request.get("id", "unknown")
                    self._send_response(request_id, error_response)
                    error_print(f"Erreur traitement requête Telegram {request_id}: {e}")
                
        except Exception as e:
            error_print(f"Erreur lecture queue Telegram: {e}")
    
    def _get_mesh_identity(self, telegram_id, telegram_username):
        """Obtenir l'identité Meshtastic pour un utilisateur Telegram"""
        if telegram_id in TELEGRAM_TO_MESH_MAPPING:
            mapping = TELEGRAM_TO_MESH_MAPPING[telegram_id]
            return {
                "node_id": mapping["node_id"],
                "short_name": mapping["short_name"],
                "display_name": mapping["display_name"]
            }
        
        fallback_node_id = telegram_id & 0xFFFFFFFF
        return {
            "node_id": fallback_node_id,
            "short_name": telegram_username[:8] if telegram_username else f"{fallback_node_id:08x}"[-4:],
            "display_name": f"TG:{telegram_username}" if telegram_username else f"TG:{fallback_node_id:08x}"
        }
    
    def _process_single_request(self, request):
        """Traiter une requête Telegram individuelle"""
        command = request.get("command", "").strip()
        user_info = request.get("user", {})
        telegram_id = user_info.get("telegram_id", 0)
        telegram_username = user_info.get("username", "Telegram")
        
        debug_print(f"🔄 Commande Telegram: '{command}' de {telegram_username}")
        
        mesh_identity = self._get_mesh_identity(telegram_id, telegram_username)
        sender_id = mesh_identity["node_id"]
        sender_info = mesh_identity["display_name"]
        
        debug_print(f"🎯 Mapping: {telegram_username} ({telegram_id}) -> {mesh_identity['short_name']} (0x{sender_id:08x})")
        
        try:
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
                return self._handle_echo_command(command, sender_id, sender_info, mesh_identity)
            elif command.startswith('/help'):
                return self._handle_help_command(sender_id, sender_info)
            else:
                return f"❓ Commande inconnue: {command}\n\nTapez /help pour l'aide"
                
        except Exception as e:
            error_print(f"Erreur traitement commande '{command}': {e}")
            return f"❌ Erreur interne: {str(e)[:100]}"
    
    def _handle_bot_command(self, command, sender_id, sender_info):
        """Traiter /bot depuis Telegram"""
        try:
            prompt = command[5:].strip()
            if not prompt:
                return "Usage: /bot <question>"
            
            debug_print(f"🤖 Bot IA pour {sender_info}: '{prompt}'")
            response = self.message_handler.llama_client.query_llama(prompt, sender_id)
            
            self.message_handler.log_conversation(sender_id, sender_info, prompt, response)
            
            return response
            
        except Exception as e:
            return f"❌ Erreur /bot: {str(e)[:80]}"
    
    def _handle_power_command(self, sender_id, sender_info):
        """Traiter /power depuis Telegram"""
        try:
            debug_print(f"🔋 Power pour {sender_info}")
            esphome_data = self.message_handler.esphome_client.parse_esphome_data()
            
            self.message_handler.log_conversation(sender_id, sender_info, "/power", esphome_data)
            
            return esphome_data
        except Exception as e:
            return f"❌ Erreur /power: {str(e)[:80]}"
    
    def _handle_rx_command(self, command, sender_id, sender_info):
        """Traiter /rx depuis Telegram"""
        try:
            page = 1
            parts = command.split()
            if len(parts) > 1:
                try:
                    page = int(parts[1])
                except ValueError:
                    page = 1
            
            debug_print(f"📡 RX page {page} pour {sender_info}")
            report = self.message_handler.remote_nodes_client.get_tigrog2_paginated(page)
            
            cmd_log = f"/rx {page}" if page > 1 else "/rx"
            self.message_handler.log_conversation(sender_id, sender_info, cmd_log, report)
            
            return report
        except Exception as e:
            return f"❌ Erreur /rx: {str(e)[:80]}"
    
    def _handle_my_command(self, sender_id, sender_info):
        """Traiter /my depuis Telegram (pas applicable)"""
        return "⚠️ Commande /my non applicable depuis Telegram\n(réservée aux utilisateurs mesh avec vraie position/signal)"
    
    def _handle_sys_command(self, sender_id, sender_info):
        """Traiter /sys depuis Telegram"""
        try:
            import subprocess
            
            debug_print(f"💻 Sys pour {sender_info}")
            system_info = []
            
            # Température CPU
            try:
                temp_result = subprocess.run(['vcgencmd', 'measure_temp'], 
                                           capture_output=True, text=True, timeout=5)
                if temp_result.returncode == 0:
                    temp_output = temp_result.stdout.strip()
                    if 'temp=' in temp_output:
                        temp_value = temp_output.split('=')[1].replace("'C", "°C")
                        system_info.append(f"🌡️ CPU: {temp_value}")
                    else:
                        system_info.append(f"🌡️ CPU: {temp_output}")
                else:
                    try:
                        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                            temp_millis = int(f.read().strip())
                            temp_celsius = temp_millis / 1000.0
                            system_info.append(f"🌡️ CPU: {temp_celsius:.1f}°C")
                    except:
                        system_info.append("🌡️ CPU: N/A")
            except:
                system_info.append("🌡️ CPU: Error")
            
            # Uptime
            try:
                uptime_result = subprocess.run(['uptime'], capture_output=True, text=True, timeout=5)
                if uptime_result.returncode == 0:
                    uptime_output = uptime_result.stdout.strip()
                    if 'up' in uptime_output:
                        parts = uptime_output.split('up')[1].split(',')[0].strip()
                        system_info.append(f"⏱️ Up: {parts}")
            except:
                system_info.append("⏱️ Uptime: Error")
            
            # Mémoire
            try:
                with open('/proc/meminfo', 'r') as f:
                    meminfo = f.read()
                
                mem_total = mem_available = None
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
                result = "🖥️ Système RPI5:\n" + "\n".join(system_info)
            else:
                result = "❌ Impossible de récupérer les infos système"
            
            self.message_handler.log_conversation(sender_id, sender_info, "/sys", result)
            
            return result
                
        except Exception as e:
            return f"❌ Erreur /sys: {str(e)[:80]}"
    
    def _handle_legend_command(self, sender_id, sender_info):
        """Traiter /legend depuis Telegram"""
        try:
            debug_print(f"📶 Legend pour {sender_info}")
            legend_text = self.message_handler.format_legend()
            
            self.message_handler.log_conversation(sender_id, sender_info, "/legend", legend_text)
            
            return legend_text
        except Exception as e:
            return f"❌ Erreur /legend: {str(e)[:80]}"
    
    def _handle_echo_command(self, command, sender_id, sender_info, mesh_identity):
        """Traiter /echo depuis Telegram avec identité Meshtastic mappée"""
        try:
            echo_text = command[6:].strip()
            
            if not echo_text:
                return "Usage: /echo <texte>"
            
            debug_print(f"📢 Echo pour {sender_info}: '{echo_text}'")
            
            def send_echo_via_tigrog2():
                try:
                    import meshtastic.tcp_interface
                    
                    remote_interface = meshtastic.tcp_interface.TCPInterface(
                        hostname=REMOTE_NODE_HOST, 
                        portNumber=4403
                    )
                    
                    time.sleep(1)
                    
                    short_name = mesh_identity["short_name"]
                    echo_response = f"{short_name}: {echo_text}"
                    
                    remote_interface.sendText(echo_response)
                    remote_interface.close()
                    
                    debug_print(f"📡 Echo diffusé via tigrog2: '{echo_response}'")
                    info_print(f"📡 Echo Telegram->Mesh: {mesh_identity['display_name']} -> {short_name}: {echo_text}")
                    
                    self.message_handler.log_conversation(sender_id, sender_info, command, f"Echo diffusé: {echo_response}")
                    
                except Exception as e:
                    error_print(f"Erreur echo via tigrog2: {e}")
            
            threading.Thread(target=send_echo_via_tigrog2, daemon=True).start()
            
            return f"📡 Echo diffusé: {mesh_identity['short_name']}: {echo_text}"
            
        except Exception as e:
            return f"❌ Erreur /echo: {str(e)[:80]}"
    
    def _handle_help_command(self, sender_id, sender_info):
        """Traiter /help depuis Telegram"""
        mapped_name = "nom_telegram"
        
        for tg_id, mapping in TELEGRAM_TO_MESH_MAPPING.items():
            if mapping["node_id"] == sender_id:
                mapped_name = mapping["short_name"]
                break
        
        help_text = f"""🤖 Bot Meshtastic - Commandes Telegram:

/bot <question> - Chat avec l'IA
/power - Info batterie/solaire  
/rx [page] - Nœuds vus par tigrog2
/sys - Info système Pi5
/echo <texte> - Diffuser via tigrog2
/legend - Légende signaux
/help - Cette aide

💡 Raccourci: Tapez directement votre message pour /bot

🎯 Vos messages /echo apparaissent comme: {mapped_name}: ...

⚠️ Note: /my non disponible depuis Telegram"""
        
        self.message_handler.log_conversation(sender_id, sender_info, "/help", help_text)
        
        return help_text
    
    def _send_response(self, request_id, response):
        """Envoyer une réponse vers Telegram"""
        try:
            responses = []
            try:
                if os.path.exists(self.response_file):
                    with open(self.response_file, 'r') as f:
                        existing_data = json.load(f)
                        if isinstance(existing_data, list):
                            responses = existing_data
            except (json.JSONDecodeError, FileNotFoundError):
                responses = []
            
            response_data = {
                "request_id": request_id,
                "response": response,
                "timestamp": time.time()
            }
            
            responses.append(response_data)
            
            if len(responses) > 100:
                responses = responses[-50:]
            
            with open(self.response_file, 'w') as f:
                json.dump(responses, f, indent=2)
            
            debug_print(f"📤 Réponse {request_id} envoyée vers Telegram")
            
        except Exception as e:
            error_print(f"Erreur envoi réponse Telegram {request_id}: {e}")
