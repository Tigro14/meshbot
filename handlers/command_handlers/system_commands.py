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
    
    def handle_rebootpi(self, sender_id, sender_info):
        """Gérer la commande /rebootpi"""
        info_print(f"REBOOT PI5 demandé par: {sender_info}")
        
        def reboot_pi5():
            try:
                self.sender.send_single("🔄 Redémarrage Pi5 en cours...", sender_id, sender_info)
                info_print(f"🚨 REDÉMARRAGE PI5 INITIÉ PAR {sender_info} (!{sender_id:08x})")
                
                time.sleep(3)
                
                # Sauvegarder avant redémarrage
                if self.node_manager:
                    self.node_manager.save_node_names(force=True)
                    debug_print("💾 Base de nœuds sauvegardée")
                
                # Créer fichier signal
                try:
                    signal_file = '/tmp/reboot_requested'
                    with open(signal_file, 'w') as f:
                        f.write(f"Redémarrage demandé par {sender_info} (!{sender_id:08x})\n")
                        f.write(f"Timestamp: {time.time()}\n")
                    
                    debug_print(f"Fichier signal créé: {signal_file}")
                    info_print("📝 Signal de redémarrage créé")
                    
                    try:
                        self.sender.send_single("📝 Signal redémarrage créé", sender_id, sender_info)
                    except:
                        pass
                    
                except Exception as e:
                    error_msg = f"⚠️ Erreur signal: {str(e)[:50]}"
                    debug_print(error_msg)
                    try:
                        self.sender.send_single(error_msg, sender_id, sender_info)
                    except:
                        pass
                
            except Exception as e:
                error_msg = f"⚠️ Erreur redémarrage: {str(e)[:50]}"
                error_print(f"Erreur reboot Pi5: {e}")
                try:
                    self.sender.send_single(error_msg, sender_id, sender_info)
                except:
                    pass
        
        threading.Thread(target=reboot_pi5, daemon=True).start()
    
    def handle_rebootg2(self, sender_id, sender_info):
        """Gérer la commande /rebootg2"""
        info_print(f"RebootG2: {sender_info}")
        
        def reboot_and_telemetry():
            try:
                target_node_id = TIGROG2_NODE_ID
                target_node_hex = f"!{target_node_id:08x}"
                
                debug_print(f"Envoi reboot via API vers {target_node_hex}")
                
                # Reboot via API
                try:
                    if hasattr(self.interface, 'reboot'):
                        self.interface.reboot(target_node_id)
                        info_print("Commande reboot API envoyée")
                    else:
                        admin_msg = {"reboot": True}
                        self.interface.sendData(
                            str(admin_msg).encode(),
                            destinationId=target_node_id,
                            portNum="ADMIN_APP",
                            wantAck=True
                        )
                        info_print("Commande reboot admin envoyée")
                    
                    debug_print("Attente redémarrage (50s)...")
                    time.sleep(50)
                    
                    try:
                        self.sender.send_single(f"🔄 Reboot {REMOTE_NODE_NAME} effectué", sender_id, sender_info)
                        time.sleep(2)
                    except:
                        pass
                        
                except Exception as e:
                    error_print(f"Erreur reboot API: {e}")
                    time.sleep(10)
                    try:
                        self.sender.send_single(f"⚠️ Erreur reboot: {str(e)[:50]}", sender_id, sender_info)
                    except:
                        pass
                    return
                
                # Request telemetry
                time.sleep(5)
                
                try:
                    debug_print("Demande télémétrie via commande système")
                    
                    telemetry_cmd = [
                        'meshtastic', 
                        '--port', SERIAL_PORT, 
                        '--dest', target_node_hex, 
                        '--request-telemetry'
                    ]
                    
                    result = subprocess.run(telemetry_cmd, capture_output=True, text=True, timeout=30)
                    
                    if result.returncode == 0:
                        telemetry_output = result.stdout.strip()
                        if telemetry_output and len(telemetry_output) > 10:
                            lines = telemetry_output.split('\n')
                            useful_lines = []
                            
                            for line in lines:
                                line = line.strip()
                                if line and not line.startswith('Connected') and not line.startswith('Requesting'):
                                    if any(kw in line.lower() for kw in ['voltage', 'current', 'temperature', 'humidity', 'pressure', 'battery']):
                                        useful_lines.append(line)
                            
                            if useful_lines:
                                response = f"📊 Télémétrie {REMOTE_NODE_NAME}:\n" + "\n".join(useful_lines[:5])
                            else:
                                response = f"📊 Télémétrie {REMOTE_NODE_NAME}:\n{telemetry_output[:150]}"
                        else:
                            response = f"📊 Télémétrie {REMOTE_NODE_NAME} (aucune donnée)"
                        
                        time.sleep(3)
                        try:
                            self.sender.send_chunks(response, sender_id, sender_info)
                            self.sender.log_conversation(sender_id, sender_info, "/rebootg2", response)
                        except:
                            pass
                    else:
                        try:
                            error_output = result.stderr.strip() if result.stderr else "Erreur inconnue"
                            self.sender.send_single(f"⚠️ Erreur télémétrie: {error_output[:80]}", sender_id, sender_info)
                        except:
                            pass
                        
                except subprocess.TimeoutExpired:
                    try:
                        self.sender.send_single("⏱️ Timeout télémétrie", sender_id, sender_info)
                    except:
                        pass
                except Exception as e:
                    error_print(f"Erreur télémétrie: {e}")
                    try:
                        self.sender.send_single(f"⚠️ Erreur: {str(e)[:60]}", sender_id, sender_info)
                    except:
                        pass
                
            except Exception as e:
                time.sleep(10)
                error_print(f"Erreur rebootg2: {e}")
                try:
                    self.sender.send_single(f"⚠️ Erreur: {str(e)[:80]}", sender_id, sender_info)
                except:
                    pass
        
        threading.Thread(target=reboot_and_telemetry, daemon=True).start()
    
    def handle_g2(self, sender_id, sender_info):
        """Gérer la commande /g2"""
        info_print(f"G2 Config: {sender_info}")
        
        def get_g2_config():
            try:
                debug_print(f"Connexion TCP à {REMOTE_NODE_HOST}...")
                remote_interface = meshtastic.tcp_interface.TCPInterface(
                    hostname=REMOTE_NODE_HOST, 
                    portNumber=4403
                )
                
                time.sleep(2)
                
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
                
                remote_interface.close()
                
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
        
        threading.Thread(target=get_g2_config, daemon=True).start()
