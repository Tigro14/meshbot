#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gestionnaire des commandes système
"""

import time
import subprocess
import threading
import meshtastic.tcp_interface
from config import *
from utils import *

class SystemCommands:
    def __init__(self, interface, node_manager, sender):
        self.interface = interface
        self.node_manager = node_manager
        self.sender = sender
    
    def handle_sys(self, sender_id, sender_info):
        """Gérer la commande /sys"""
        info_print(f"Sys: {sender_info}")
        
        def get_system_info():
            try:
                system_info = []
                
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
                
                # Uptime
                try:
                    uptime_cmd = ['uptime', '-p']
                    uptime_result = subprocess.run(uptime_cmd, capture_output=True, text=True, timeout=5)
                    if uptime_result.returncode == 0:
                        uptime_clean = uptime_result.stdout.strip().replace('up ', '')
                        system_info.append(f"⏱️ Up: {uptime_clean}")
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
                self.sender.send_chunks(response, sender_id, sender_info)
                self.sender.log_conversation(sender_id, sender_info, "/sys", response)
                
            except Exception as e:
                error_msg = f"⚠️ Erreur système: {str(e)[:100]}"
                error_print(f"Erreur sys: {e}")
                self.sender.send_single(error_msg, sender_id, sender_info)
        
        threading.Thread(target=get_system_info, daemon=True).start()
    
    def _check_reboot_authorization_mesh(self, from_id, command_name, message_parts):
        """
        Vérifier autorisation pour commande reboot depuis Meshtastic
        VERSION DEBUG INTENSIVE
        """
        node_name = self.node_manager.get_node_name(from_id, self.interface)
        
        info_print("=" * 60)
        info_print(f"🔍 DEBUG AUTORISATION {command_name}")
        info_print(f"   from_id: 0x{from_id:08x} ({from_id})")
        info_print(f"   node_name: {node_name}")
        info_print(f"   message_parts: {message_parts}")
        info_print("=" * 60)
        
        # 1. Vérifier activation globale
        info_print(f"CHECK 1: REBOOT_COMMANDS_ENABLED = {REBOOT_COMMANDS_ENABLED}")
        if not REBOOT_COMMANDS_ENABLED:
            info_print(f"🚫 {command_name} refusé (désactivé): {node_name}")
            return False, "❌ Commandes de redémarrage désactivées"
        
        # 2. Vérifier liste restreinte
        info_print(f"CHECK 2: REBOOT_AUTHORIZED_USERS = {REBOOT_AUTHORIZED_USERS}")
        info_print(f"         from_id in list? {from_id in REBOOT_AUTHORIZED_USERS if REBOOT_AUTHORIZED_USERS else 'N/A (liste vide)'}")
        
        if REBOOT_AUTHORIZED_USERS and from_id not in REBOOT_AUTHORIZED_USERS:
            info_print(f"🚫 {command_name} refusé (non autorisé): {node_name} (0x{from_id:08x})")
            info_print(f"   IDs autorisés: {[f'0x{x:08x}' for x in REBOOT_AUTHORIZED_USERS]}")
            return False, "❌ Non autorisé pour cette commande"
        
        # 3. Vérifier mot de passe
        info_print(f"CHECK 3: Vérification mot de passe")
        info_print(f"         Nombre d'arguments: {len(message_parts)}")
        
        if len(message_parts) < 2:
            debug_print(f"⚠️ {command_name} sans mot de passe: {node_name}")
            return False, f"⚠️ Usage: {command_name} <password>"
        
        provided_password = message_parts[1]
        expected_password = REBOOT_PASSWORD
        
        info_print(f"         Mot de passe fourni: '{provided_password}'")
        info_print(f"         Mot de passe attendu: '{expected_password}'")
        info_print(f"         Match? {provided_password == expected_password}")
        
        if provided_password != REBOOT_PASSWORD:
            info_print(f"🚫 {command_name} refusé (mauvais MDP): {node_name} (0x{from_id:08x})")
            return False, "❌ Mot de passe incorrect"
        
        # OK
        info_print(f"🔐 {command_name} autorisé: {node_name} (0x{from_id:08x})")
        info_print("=" * 60)
        return True, None

    def handle_reboot_command(self, from_id, message_parts):
        """
        Traiter /rebootpi de manière sécurisée
        
        REMPLACE LA VERSION ACTUELLE
        
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
            node_name = self.node_manager.get_node_name(from_id, self.interface)
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


    # ==========================================
    # REMPLACEMENT DE handle_rebootg2_command
    # ==========================================

    def handle_rebootg2_command(self, from_id, message_parts):
        """
        Traiter /rebootg2 de manière sécurisée
        
        REMPLACE LA VERSION ACTUELLE
        
        Args:
            from_id: Node ID demandeur
            message_parts: ['/rebootg2', 'password'] (liste)
        
        Returns:
            str: Message de réponse
        """
        # Vérifier autorisation
        authorized, error_msg = self._check_reboot_authorization_mesh(
            from_id,
            '/rebootg2',
            message_parts
        )
        
        if not authorized:
            return error_msg
        
        # Exécuter le reboot
        try:
            import meshtastic.tcp_interface
            from config import REMOTE_NODE_HOST, REMOTE_NODE_NAME
            
            node_name = self.node_manager.get_node_name(from_id, self.interface)
            info_print(f"🔄 REBOOT G2: {node_name} (0x{from_id:08x})")
            
            remote_interface = meshtastic.tcp_interface.TCPInterface(
                hostname=REMOTE_NODE_HOST,
                portNumber=4403
            )
            time.sleep(2)
            
            remote_interface.sendText("/reboot")
            info_print(f"✅ Commande envoyée à {REMOTE_NODE_NAME}")
            
            time.sleep(1)
            remote_interface.close()
            
            return f"✅ Redémarrage {REMOTE_NODE_NAME} lancé"
            
        except Exception as e:
            error_print(f"Erreur reboot {REMOTE_NODE_NAME}: {e}")
            return f"❌ Erreur: {str(e)[:50]}"
    
    def handle_g2(self, sender_id, sender_info):
        """Gérer la commande /g2"""
        info_print(f"G2 Config: {sender_info}")

        def get_g2_config():
            remote_interface = None
            try:
                debug_print(f"Connexion TCP à {REMOTE_NODE_HOST}...")
                remote_interface = meshtastic.tcp_interface.TCPInterface(
                    hostname=REMOTE_NODE_HOST,
                    portNumber=4403
                )

                # ✅ CRITIQUE : Réduire à 1s au lieu de 2s
                time.sleep(1)

                config_info = []

                if hasattr(remote_interface, 'localNode') and remote_interface.localNode:
                    local_node = remote_interface.localNode

                    if hasattr(local_node, 'shortName'):
                        config_info.append(f"📡 {local_node.shortName}")

                    if hasattr(local_node, 'nodeNum'):
                        config_info.append(f"🔢 ID: !{local_node.nodeNum:08x}")

                    if hasattr(local_node, 'firmwareVersion'):
                        config_info.append(f"📦 FW: {local_node.firmwareVersion}")

                nodes_count = len(getattr(remote_interface, 'nodes', {}))
                config_info.append(f"🗂️ Nœuds: {nodes_count}")

                try:
                    nodes = getattr(remote_interface, 'nodes', {})
                    direct_nodes = sum(1 for n in nodes.values() if isinstance(n, dict) and n.get('hopsAway') == 0)
                    config_info.append(f"🎯 Direct: {direct_nodes}")
                except:
                    pass

                response = f"⚙️ Config {REMOTE_NODE_NAME}:\n" + "\n".join(config_info) if config_info else f"⚠️ Config inaccessible"

                self.sender.log_conversation(sender_id, sender_info, "/g2", response)
                self.sender.send_chunks(response, sender_id, sender_info)

            except Exception as e:
                error_msg = f"⚠️ Erreur config: {str(e)[:50]}"
                error_print(f"Erreur G2: {e}")
                try:
                    self.sender.send_single(error_msg, sender_id, sender_info)
                except:
                    pass
            finally:
                # ✅ CRITIQUE : TOUJOURS fermer
                if remote_interface:
                    try:
                        debug_print(f"🔒 Fermeture FORCÉE connexion {REMOTE_NODE_HOST}")
                        remote_interface.close()
                        del remote_interface
                        import gc
                        gc.collect()
                    except Exception as close_error:
                        debug_print(f"Erreur fermeture: {close_error}")

        threading.Thread(target=get_g2_config, daemon=True).start()
