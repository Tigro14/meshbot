#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gestionnaire des commandes système
VERSION AVEC UPTIME BOT PYTHON
"""

import time
import subprocess
import threading
import meshtastic.tcp_interface
from config import *
from utils import *

class SystemCommands:
    def __init__(self, interface, node_manager, sender, bot_start_time=None):
        self.interface_provider = interface  # ✅ Peut être interface ou serial_manager
        self.node_manager = node_manager
        self.sender = sender
        self.bot_start_time = bot_start_time  # ✅ NOUVEAU: timestamp démarrage bot
    
    def _get_interface(self):
        """Récupérer l'interface active"""
        if hasattr(self.interface_provider, 'get_interface'):
            return self.interface_provider.get_interface()
        return self.interface_provider

    def handle_sys(self, sender_id, sender_info):
        """Gérer la commande /sys - VERSION AVEC UPTIME BOT"""
        info_print(f"Sys: {sender_info}")

        # Capturer le sender actuel pour le thread (important pour CLI!)
        # Sans ça, le thread async pourrait utiliser le sender après qu'il soit restauré
        current_sender = self.sender

        def get_system_info():
            try:
                system_info = []

                info_print(f"DEBUG: bot_start_time = {self.bot_start_time}")
                # AJOUT : Uptime du bot Python
                # ========================================
                if self.bot_start_time:
                    bot_uptime_seconds = int(time.time() - self.bot_start_time)
                    
                    # Formater l'uptime
                    days = bot_uptime_seconds // 86400
                    hours = (bot_uptime_seconds % 86400) // 3600
                    minutes = (bot_uptime_seconds % 3600) // 60
                    
                    # Construction du format lisible
                    uptime_parts = []
                    if days > 0:
                        uptime_parts.append(f"{days}j")
                    if hours > 0:
                        uptime_parts.append(f"{hours}h")
                    if minutes > 0 or len(uptime_parts) == 0:  # Toujours afficher les minutes si < 1h
                        uptime_parts.append(f"{minutes}m")
                    
                    bot_uptime_str = " ".join(uptime_parts)
                    system_info.append(f"🤖 Bot: {bot_uptime_str}")

                # Température CPU
                try:
                    temp_cmd = ['vcgencmd', 'measure_temp']
                    temp_result = subprocess.run(temp_cmd, capture_output=True, text=True, timeout=5)
                    
                    if temp_result.returncode == 0:
                        temp_output = temp_result.stdout.strip()
                        if 'temp=' in temp_output:
                            temp_value = temp_output.split('=')[1].replace("'C", "°C")
                            system_info.append(f"🌡️ CPU: {temp_value}")
                    else:
                        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                            temp_celsius = int(f.read().strip()) / 1000.0
                            system_info.append(f"🌡️ CPU: {temp_celsius:.1f}°C")
                except:
                    system_info.append("🌡️ CPU: Error")
                
                # Uptime OS
                try:
                    uptime_cmd = ['uptime', '-p']
                    uptime_result = subprocess.run(uptime_cmd, capture_output=True, text=True, timeout=5)
                    if uptime_result.returncode == 0:
                        uptime_clean = uptime_result.stdout.strip().replace('up ', '')
                        system_info.append(f"⏱️ OS: {uptime_clean}")
                except:
                    pass
                
                # Load Average
                try:
                    with open('/proc/loadavg', 'r') as f:
                        loadavg = f.read().strip().split()
                        system_info.append(f"📊 Load: {loadavg[0]} {loadavg[1]} {loadavg[2]}")
                except:
                    pass
                
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
                        system_info.append(f"💾 RAM: {mem_used//1024}MB/{mem_total//1024}MB ({mem_percent:.0f}%)")
                except:
                    pass
                
                response = "🖥️ Système RPI5:\n" + "\n".join(system_info) if system_info else "⚠️ Erreur système"
                current_sender.send_chunks(response, sender_id, sender_info)
                current_sender.log_conversation(sender_id, sender_info, "/sys", response)

            except Exception as e:
                error_msg = f"⚠️ Erreur système: {str(e)[:100]}"
                error_print(f"Erreur sys: {e}")
                current_sender.send_single(error_msg, sender_id, sender_info)
        
        threading.Thread(target=get_system_info, daemon=True, name="SystemInfo").start()
    
    def _check_reboot_authorization_mesh(self, from_id, command_name, message_parts):
        """
        Vérifier autorisation pour commande reboot depuis Meshtastic
        
        Args:
            from_id: Node ID demandeur
            command_name: '/rebootpi' ou '/rebootnode'
            message_parts: ['/rebootpi', 'password'] ou ['/rebootnode', 'node', 'password']
        
        Returns:
            tuple: (authorized: bool, error_message: str or None)
        """
        node_name = self.node_manager.get_node_name(from_id, self._get_interface())
        
        # 1. Vérifier activation globale
        if not REBOOT_COMMANDS_ENABLED:
            info_print(f"🚫 {command_name} refusé (désactivé): {node_name}")
            return False, "❌ Commandes de redémarrage désactivées"
        
        # 2. Vérifier liste restreinte
        if REBOOT_AUTHORIZED_USERS and from_id not in REBOOT_AUTHORIZED_USERS:
            info_print(f"🚫 {command_name} refusé (non autorisé): {node_name} (0x{from_id:08x})")
            return False, "❌ Non autorisé pour cette commande"
        
        # 3. Vérifier mot de passe
        if len(message_parts) < 2:
            debug_print(f"⚠️ {command_name} sans mot de passe: {node_name}")
            return False, f"⚠️ Usage: {command_name} <password>"
        
        provided_password = message_parts[1]
        
        if provided_password != REBOOT_PASSWORD:
            info_print(f"🚫 {command_name} refusé (mauvais MDP): {node_name} (0x{from_id:08x})")
            return False, "❌ Mot de passe incorrect"
        
        # OK
        info_print(f"🔐 {command_name} autorisé: {node_name} (0x{from_id:08x})")
        return True, None

    def handle_reboot_command(self, from_id, message_parts):
        """
        Traiter /rebootpi de manière sécurisée
        
        Args:
            from_id: Node ID demandeur
            message_parts: ['/rebootpi', 'password'] (liste)
        
        Returns:
            str: Message de réponse
        """
        # Vérifier autorisation
        authorized, error_msg = self._check_reboot_authorization_mesh(
            from_id,
            '/rebootpi',
            message_parts
        )
        
        if not authorized:
            return error_msg
        
        # Exécuter le reboot
        try:
            node_name = self.node_manager.get_node_name(from_id, self._get_interface())
            info_print(f"🚨 REBOOT Pi5: {node_name} (0x{from_id:08x})")
            
            signal_file = "/tmp/reboot_requested"
            with open(signal_file, 'w') as f:
                f.write(f"Demandé par: {node_name}\n")
                f.write(f"Node ID: 0x{from_id:08x}\n")
                f.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            info_print(f"✅ Signal créé: {signal_file}")
            return "✅ Redémarrage Pi5 programmé"
            
        except Exception as e:
            error_print(f"Erreur reboot: {e}")
            return f"❌ Erreur: {str(e)[:50]}"

    def handle_rebootnode_command(self, from_id, message_parts):
        """
        Traiter /rebootnode <node_name> <password> de manière sécurisée
        
        Permet de redémarrer n'importe quel nœud Meshtastic via la commande /reboot
        envoyée directement au nœud cible via l'interface Python (TCP ou serial).
        
        Args:
            from_id: Node ID demandeur
            message_parts: ['/rebootnode', 'target_node', 'password'] (liste)
        
        Returns:
            str: Message de réponse
        """
        # Vérifier qu'il y a au moins 3 arguments (/rebootnode target password)
        if len(message_parts) < 3:
            return "⚠️ Usage: /rebootnode <node_name> <password>"
        
        # Vérifier autorisation (utilise password de message_parts[2])
        # Créer une liste modifiée pour la vérification d'auth
        auth_parts = [message_parts[0], message_parts[2]]  # ['/rebootnode', 'password']
        authorized, error_msg = self._check_reboot_authorization_mesh(
            from_id,
            '/rebootnode',
            auth_parts
        )
        
        if not authorized:
            return error_msg
        
        # Extraire le nom du nœud cible
        target_node_name = message_parts[1]
        requester_name = self.node_manager.get_node_name(from_id, self._get_interface())
        
        try:
            # Chercher le node_id du nœud cible
            # Utilise le même pattern que /trace: chercher d'abord dans node_manager
            matching_nodes = []
            exact_matches = []
            target_search = target_node_name.lower()
            
            # PRIORITÉ 1: Chercher dans node_manager.node_names (SQLite DB)
            if self.node_manager and hasattr(self.node_manager, 'node_names'):
                for node_id, node_data in self.node_manager.node_names.items():
                    node_name = node_data.get('name', '').lower()
                    node_id_hex = f"{node_id:x}".lower()
                    
                    # Vérifier correspondance exacte d'abord
                    if target_search == node_name or target_search == node_id_hex:
                        exact_matches.append({
                            'id': node_id,
                            'name': node_data.get('name', f"Node-{node_id:08x}")
                        })
                    # Sinon correspondance partielle
                    elif target_search in node_name or target_search in node_id_hex:
                        matching_nodes.append({
                            'id': node_id,
                            'name': node_data.get('name', f"Node-{node_id:08x}")
                        })
            
            # Déterminer le nœud cible
            target_node_id = None
            target_name = None
            
            if len(exact_matches) == 1:
                # Une seule correspondance exacte: utiliser directement
                target_node_id = exact_matches[0]['id']
                target_name = exact_matches[0]['name']
            elif len(exact_matches) > 1:
                # Plusieurs correspondances exactes: ambiguïté
                names = ', '.join([f"{n['name']} ({n['id']:08x})" for n in exact_matches[:3]])
                return f"❌ Plusieurs nœuds trouvés: {names}"
            elif len(matching_nodes) == 1:
                # Une seule correspondance partielle: utiliser directement
                target_node_id = matching_nodes[0]['id']
                target_name = matching_nodes[0]['name']
            elif len(matching_nodes) > 1:
                # Plusieurs correspondances partielles: ambiguïté
                names = ', '.join([f"{n['name']} ({n['id']:08x})" for n in matching_nodes[:3]])
                return f"❌ Plusieurs nœuds trouvés: {names}"
            else:
                # Aucune correspondance
                return f"❌ Nœud '{target_node_name}' introuvable"
            
            # Envoyer la commande /reboot au nœud cible
            info_print(f"🔄 REBOOT NODE: {requester_name} (0x{from_id:08x}) -> {target_name} (0x{target_node_id:08x})")
            
            interface = self._get_interface()
            if not interface:
                return "❌ Interface Meshtastic non disponible"
            
            # Envoyer /reboot au nœud cible via sendText avec destinationId
            # Note: destinationId peut être nodeNum (int) ou nodeId (str comme "!abc123")
            interface.sendText(
                text="/reboot",
                destinationId=target_node_id,  # Node ID (int)
                wantAck=True  # Demander accusé de réception
            )
            
            info_print(f"✅ Commande /reboot envoyée à {target_name} (0x{target_node_id:08x})")
            return f"✅ Redémarrage {target_name} lancé"
            
        except Exception as e:
            error_print(f"Erreur rebootnode {target_node_name}: {e}")
            import traceback
            error_print(traceback.format_exc())
            return f"❌ Erreur: {str(e)[:50]}"