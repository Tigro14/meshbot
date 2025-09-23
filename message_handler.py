#!/usr/bin/env python3
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
            "/sys",
            "/legend",
            "/help"
        ]
        
        return "\n".join(help_lines)
    
    def handle_bot_command(self, message, sender_id, sender_info):
        """Gérer la commande /bot"""
        prompt = message[5:].strip()
        info_print(f"Bot: {sender_info}: '{prompt}'")
        
        if prompt:
            start_time = time.time()
            response = self.llama_client.query_llama(prompt, sender_id)
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
                        error_msg = f"❌ Erreur reboot API: {str(e)[:50]}"
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
                            error_msg = f"❌ Erreur télémétrie: {error_output[:80]}"
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
                        error_msg = f"❌ Erreur télémétrie: {str(e)[:60]}"
                        self.send_single_message(error_msg, sender_id, sender_info)
                    except Exception as e2:
                        debug_print(f"Message d'erreur télémétrie échoué: {e2}")
                
            except Exception as e:
                time.sleep(10)
                try:
                    error_msg = f"❌ Erreur général: {str(e)[:80]}"
                    error_print(f"Erreur rebootg2: {e}")
                    self.send_single_message(error_msg, sender_id, sender_info)
                except Exception as e2:
                    debug_print(f"Message d'erreur général échoué: {e2}")
        
        # Lancer dans un thread séparé pour ne pas bloquer
        threading.Thread(target=reboot_and_telemetry, daemon=True).start()
    
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
                            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                                temp_millis = int(f.read().strip())
                                temp_celsius = temp_millis / 1000.0
                                system_info.append(f"🌡️ CPU: {temp_celsius:.1f}°C")
                        except:
                            system_info.append("🌡️ CPU: N/A")
                            
                except Exception as e:
                    debug_print(f"Erreur température: {e}")
                    system_info.append("🌡️ CPU: Error")
                
                # 2. Uptime
                try:
                    uptime_cmd = ['uptime']
                    uptime_result = subprocess.run(uptime_cmd, 
                                                 capture_output=True, 
                                                 text=True, 
                                                 timeout=5)
                    
                    if uptime_result.returncode == 0:
                        uptime_output = uptime_result.stdout.strip()
                        # Nettoyer et simplifier l'output uptime
                        uptime_clean = uptime_output.replace('  ', ' ')
                        
                        # Extraire les parties importantes
                        parts = uptime_clean.split(',')
                        if len(parts) >= 3:
                            # Uptime + load average
                            uptime_part = parts[0].strip()  # "up X days, Y hours"
                            load_parts = [p.strip() for p in parts[-3:]]  # derniers 3 éléments (load avg)
                            
                            # Formater de manière compacte
                            if 'up' in uptime_part:
                                up_info = uptime_part.split('up')[1].strip()
                                system_info.append(f"⏱️ Up: {up_info}")
                            
                            # Load average (simplifier)
                            load_info = ', '.join(load_parts)
                            if 'load average:' in load_info:
                                load_values = load_info.split('load average:')[1].strip()
                                system_info.append(f"📊 Load: {load_values}")
                        else:
                            # Fallback: uptime complet mais tronqué
                            system_info.append(f"⏱️ {uptime_clean[:50]}")
                    else:
                        system_info.append("⏱️ Uptime: Error")
                        
                except Exception as e:
                    debug_print(f"Erreur uptime: {e}")
                    system_info.append("⏱️ Uptime: Error")
                
                # 3. Informations mémoire (bonus)
                try:
                    # Récupérer info mémoire rapidement
                    with open('/proc/meminfo', 'r') as f:
                        meminfo = f.read()
                    
                    mem_total = None
                    mem_available = None
                    
                    for line in meminfo.split('\n'):
                        if line.startswith('MemTotal:'):
                            mem_total = int(line.split()[1])  # en kB
                        elif line.startswith('MemAvailable:'):
                            mem_available = int(line.split()[1])  # en kB
                    
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
                    response = "❌ Impossible de récupérer les infos système"
                
                self.send_response_chunks(response, sender_id, sender_info)
                self.log_conversation(sender_id, sender_info, "/sys", response)
                
            except Exception as e:
                error_msg = f"❌ Erreur système: {str(e)[:100]}"
                error_print(f"Erreur sys: {e}")
                self.send_single_message(error_msg, sender_id, sender_info)
        
        # Lancer dans un thread séparé pour ne pas bloquer
        threading.Thread(target=get_system_info, daemon=True).start()
    
    def process_text_message(self, packet, decoded, message):
        """Traiter un message texte"""
        sender_id = packet.get('from', 0)
        to_id = packet.get('to', 0)
        my_id = None
        
        if hasattr(self.interface, 'localNode') and self.interface.localNode:
            my_id = getattr(self.interface.localNode, 'nodeNum', 0)
        
        is_for_me = (to_id == my_id) if my_id else False
        sender_info = self.node_manager.get_node_name(sender_id, self.interface)
        
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
        elif message.startswith('/legend'):
            self.handle_legend_command(sender_id, sender_info)
        elif message.startswith('/help'):
            self.handle_help_command(sender_id, sender_info)
        elif message.startswith('/rebootg2'):
            self.handle_rebootg2_command(sender_id, sender_info)
        elif message.startswith('/sys'):
            self.handle_sys_command(sender_id, sender_info)
        else:
            # Message normal (pas de commande)
            if DEBUG_MODE:
                debug_print(f"Message normal reçu: '{message}'")
