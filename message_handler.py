#!/usr/bin/env python3
"""
Gestionnaire des messages et commandes
"""

import time
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
            "🔶 Indicateurs:",
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
            "/rx", 
            "/tigrog2 [page]",
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
    
    def handle_tigrog2_command(self, message, sender_id, sender_info):
        """Gérer la commande /tigrog2"""
        # Extraire le numéro de page - gérer les deux formats
        page = 1
        parts = message.split()
        
        if message.startswith('/tigro G2'):
            # Format "/tigro G2 2" - la page est le 3ème élément
            if len(parts) >= 3:
                page = validate_page_number(parts[2], 999)
        else:
            # Format "/tigrog2 2" - la page est le 2ème élément
            if len(parts) > 1:
                page = validate_page_number(parts[1], 999)
        
        info_print(f"Tigrog2 Page {page}: {sender_info}")
        
        try:
            report = self.remote_nodes_client.get_tigrog2_paginated(page)
            self.log_conversation(sender_id, sender_info, f"/tigrog2 {page}" if page > 1 else "/tigrog2", report)
            self.send_single_message(report, sender_id, sender_info)
        except Exception as e:
            error_msg = f"Erreur tigrog2 page {page}: {str(e)[:50]}"
            self.send_single_message(error_msg, sender_id, sender_info)
    
    def handle_rx_command(self, sender_id, sender_info):
        """Gérer la commande /rx"""
        info_print(f"RX Report: {sender_info}")
        
        rx_report = self.node_manager.format_rx_report()
        self.log_conversation(sender_id, sender_info, "/rx", rx_report)
        self.send_response_chunks(rx_report, sender_id, sender_info)
    
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
        elif message.startswith('/tigrog2') or message.startswith('/tigro G2'):
            self.handle_tigrog2_command(message, sender_id, sender_info)
        elif message.startswith('/rx'):
            self.handle_rx_command(sender_id, sender_info)
        elif message.startswith('/legend'):
            self.handle_legend_command(sender_id, sender_info)
        elif message.startswith('/help'):
            self.handle_help_command(sender_id, sender_info)
        else:
            # Message normal (pas de commande)
            if DEBUG_MODE:
                debug_print(f"Message normal reçu: '{message}'")