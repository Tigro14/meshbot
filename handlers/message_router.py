#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Routeur principal des messages et commandes
Orchestre tous les gestionnaires de commandes
"""

from config import DEBUG_MODE
from utils import info_print, debug_print
from .message_sender import MessageSender
from .command_handlers import (
    AICommands,
    NetworkCommands,
    SystemCommands,
    UtilityCommands
)

class MessageRouter:
    def __init__(self, llama_client, esphome_client, remote_nodes_client, 
                 node_manager, context_manager, interface, traffic_monitor=None):
        
        # Dépendances
        self.node_manager = node_manager
        self.interface = interface
        
        # Message sender (gère envoi et throttling)
        self.sender = MessageSender(interface, node_manager)
        
        # Gestionnaires de commandes par domaine
        self.ai_handler = AICommands(llama_client, self.sender)
        self.network_handler = NetworkCommands(remote_nodes_client, self.sender)
        self.system_handler = SystemCommands(interface, node_manager, self.sender)
        self.utility_handler = UtilityCommands(esphome_client, traffic_monitor, self.sender)
    
    def process_text_message(self, packet, decoded, message):
        """Point d'entrée principal pour traiter un message texte"""
        sender_id = packet.get('from', 0)
        to_id = packet.get('to', 0)
        my_id = None

        if hasattr(self.interface, 'localNode') and self.interface.localNode:
            my_id = getattr(self.interface.localNode, 'nodeNum', 0)

        is_for_me = (to_id == my_id) if my_id else False
        is_from_me = (sender_id == my_id) if my_id else False
        is_broadcast = to_id in [0xFFFFFFFF, 0]
        sender_info = self.node_manager.get_node_name(sender_id, self.interface)

        # Gérer /echo et /my sur messages publics
        if (message.startswith('/echo ') or message.startswith('/my')) and (is_broadcast or is_for_me) and not is_from_me:
            if message.startswith('/echo '):
                info_print(f"ECHO PUBLIC de {sender_info}: '{message}'")
                self.utility_handler.handle_echo(message, sender_id, sender_info, packet)
            elif message.startswith('/my'):
                info_print(f"MY PUBLIC de {sender_info}")
                self.network_handler.handle_my(sender_id, sender_info, is_broadcast=is_broadcast)
            return

        # Messages publics - ignorer les autres commandes
        if is_broadcast and not is_from_me:
            if DEBUG_MODE and not message.startswith('/echo') and not message.startswith('/my'):
                debug_print(f"Message public ignoré: '{message}'")
            return

        # Log messages pour nous
        if is_for_me or DEBUG_MODE:
            info_print(f"MESSAGE REÇU de {sender_info}: '{message}'")

        # Traiter seulement si pour nous
        if not is_for_me:
            return

        # Router la commande
        self._route_command(message, sender_id, sender_info, packet)
    
    def _route_command(self, message, sender_id, sender_info, packet):
        """Router une commande vers le bon gestionnaire"""
        
        # Commandes IA
        if message.startswith('/bot '):
            self.ai_handler.handle_bot(message, sender_id, sender_info)
        
        # Commandes réseau
        elif message.startswith('/rx'):
            self.network_handler.handle_rx(message, sender_id, sender_info)
        elif message.startswith('/my'):
            self.network_handler.handle_my(sender_id, sender_info, is_broadcast=False)
        
        # Commandes système
        elif message.startswith('/sys'):
            self.system_handler.handle_sys(sender_id, sender_info)
        elif message.startswith('/rebootpi'):
            parts = message.split()
            response = self.handle_reboot_command(from_id, parts)
        elif message.startswith('/rebootg2'):
            parts = message.split()
            response = self.handle_rebootg2_command(from_id, parts)
        elif message.startswith('/g2'):
            self.system_handler.handle_g2(sender_id, sender_info)
        
        # Commandes utilitaires
        elif message.startswith('/power'):
            self.utility_handler.handle_power(sender_id, sender_info)
        elif message.startswith('/graph'):
            self.utility_handler.handle_graphs_command(sender_id, from_id, text_parts)
        elif message.startswith('/echo '):
            self.utility_handler.handle_echo(message, sender_id, sender_info, packet)
        elif message.startswith('/trafic'):
            self.utility_handler.handle_trafic(message, sender_id, sender_info)
        elif message.startswith('/legend'):
            self.utility_handler.handle_legend(sender_id, sender_info)
        elif message.startswith('/help'):
            self.utility_handler.handle_help(sender_id, sender_info)
        
        # Commande inconnue
        else:
            if message.startswith('/'):
                info_print(f"Commande inconnue de {sender_info}: '{message}'")
                self.utility_handler.handle_help(sender_id, sender_info)
            else:
                if DEBUG_MODE:
                    debug_print(f"Message normal reçu: '{message}'")
    
    def cleanup_throttling_data(self):
        """Nettoyer les données de throttling (appelé périodiquement)"""
        self.sender.cleanup_throttling()

    def format_help_telegram(self, user_id=None):
        """Format aide détaillée pour Telegram"""
        help_text = self.utility_handler._format_help_telegram()

        # Remplacer le placeholder user_id si fourni
        if user_id:
            help_text = help_text.replace("{user_id}", str(user_id))
        else:
            help_text = help_text.replace("\nVotre ID Telegram : {user_id}", "")

        return help_text
