#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gestionnaire des commandes utilitaires
"""

import time
import threading
import meshtastic.tcp_interface
from config import *
from utils import *

class UtilityCommands:
    def __init__(self, esphome_client, traffic_monitor, sender):
        self.esphome_client = esphome_client
        self.traffic_monitor = traffic_monitor
        self.sender = sender
    
    def handle_power(self, sender_id, sender_info):
        """Gérer la commande /power"""
        info_print(f"Power: {sender_info}")
        
        esphome_data = self.esphome_client.parse_esphome_data()
        self.sender.log_conversation(sender_id, sender_info, "/power", esphome_data)
        self.sender.send_chunks(esphome_data, sender_id, sender_info)
    
    def handle_legend(self, sender_id, sender_info):
        """Gérer la commande /legend"""
        info_print(f"Legend: {sender_info}")
        
        legend_text = self._format_legend()
        self.sender.log_conversation(sender_id, sender_info, "/legend", legend_text)
        self.sender.send_chunks(legend_text, sender_id, sender_info)
    
    def handle_help(self, sender_id, sender_info):
        """Gérer la commande /help"""
        info_print(f"Help: {sender_info}")
        
        try:
            help_text = self._format_help()
            info_print(f"Help text généré: {len(help_text)} caractères")
            self.sender.log_conversation(sender_id, sender_info, "/help", help_text)
            self.sender.send_single(help_text, sender_id, sender_info)
            info_print(f"Help envoyé à {sender_info}")
        except Exception as e:
            error_print(f"Erreur commande /help: {e}")
            self.sender.send_single("Erreur génération aide", sender_id, sender_info)
    
    def handle_echo(self, message, sender_id, sender_info, packet):
        """Gérer la commande /echo - tigrog2 diffuse dans le mesh"""
        # Anti-doublon
        message_id = f"{sender_id}_{message}_{int(time.time())}"
        if hasattr(self.sender, '_last_echo_id') and self.sender._last_echo_id == message_id:
            debug_print("⚠️ Echo déjà traité, ignoré")
            return
        self.sender._last_echo_id = message_id
        
        echo_text = message[6:].strip()
        
        if not echo_text:
            self.sender.send_single("Usage: /echo <texte>", sender_id, sender_info)
            return
        
        info_print(f"Echo via tigrog2: {sender_info} -> '{echo_text}'")
        
        def send_echo_via_tigrog2():
            remote_interface = None
            try:
                debug_print(f"Connexion TCP à tigrog2 pour echo...")
                remote_interface = meshtastic.tcp_interface.TCPInterface(
                    hostname=REMOTE_NODE_HOST, 
                    portNumber=4403
                )
                
                time.sleep(3)
                
                author_short = self.sender.get_short_name(sender_id)
                echo_response = f"{author_short}: {echo_text}"
                
                debug_print(f"Envoi broadcast: '{echo_response}'")
                remote_interface.sendText(echo_response)
                time.sleep(4)
                
                debug_print(f"✅ Echo diffusé via tigrog2: '{echo_response}'")
                self.sender.log_conversation(sender_id, sender_info, message, echo_response)
                
            except Exception as e:
                error_print(f"Erreur echo via tigrog2: {e}")
                try:
                    error_response = f"Erreur echo tigrog2: {str(e)[:30]}"
                    self.sender.send_single(error_response, sender_id, sender_info)
                except:
                    pass
            finally:
                if remote_interface:
                    try:
                        remote_interface.close()
                    except:
                        pass
        
        threading.Thread(target=send_echo_via_tigrog2, daemon=True).start()
    
    def handle_trafic(self, message, sender_id, sender_info):
        """Gérer la commande /trafic"""
        info_print(f"Trafic: {sender_info}")
        
        # Extraire les heures optionnelles
        hours = 8
        parts = message.split()
        if len(parts) > 1:
            try:
                hours = int(parts[1])
                hours = max(1, min(24, hours))
            except ValueError:
                hours = 8
        
        if not self.traffic_monitor:
            self.sender.send_single("❌ Traffic monitor non disponible", sender_id, sender_info)
            return
        
        try:
            report = self.traffic_monitor.get_traffic_report(hours)
            self.sender.log_conversation(sender_id, sender_info, 
                                        f"/trafic {hours}" if hours != 8 else "/trafic", 
                                        report)
            self.sender.send_chunks(report, sender_id, sender_info)
        except Exception as e:
            error_msg = f"❌ Erreur trafic: {str(e)[:50]}"
            self.sender.send_single(error_msg, sender_id, sender_info)
    
    def _format_legend(self):
        """Formater la légende des indicateurs"""
        legend_lines = [
            "📶 Indicateurs:",
            "🟢🔵=excellent",
            "🟡🟣=bon", 
            "🟠🟤=faible",
            "🔴⚫=très faible",
            "1er=RSSI 2e=SNR"
        ]
        return "\n".join(legend_lines)
    
    def _format_help(self):
        """Formater l'aide des commandes"""
        help_lines = [
            "• /bot IA",
            "• /power",
            "• /rx [page]",
            "• /sys ",
            "• /echo <msg>",
            "• /nodes",
            "• /legend ",
            "• /help"
        ]
        return "\n".join(help_lines)
