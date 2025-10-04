#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wrapper de compatibilité pour MessageHandler
Utilise la nouvelle architecture modulaire en interne
"""

from handlers import MessageRouter

class MessageHandler:
    """
    Classe de compatibilité qui délègue au MessageRouter
    Permet de garder l'interface existante sans casser le code
    """
    
    def __init__(self, llama_client, esphome_client, remote_nodes_client, 
                 node_manager, context_manager, interface, traffic_monitor=None):
        
        # Créer le router qui gère tout
        self.router = MessageRouter(
            llama_client,
            esphome_client,
            remote_nodes_client,
            node_manager,
            context_manager,
            interface,
            traffic_monitor
        )
        
        # Exposer les propriétés nécessaires pour compatibilité
        self.llama_client = llama_client
        self.esphome_client = esphome_client
        self.remote_nodes_client = remote_nodes_client
        self.node_manager = node_manager
        self.context_manager = context_manager
        self.interface = interface
        self.traffic_monitor = traffic_monitor
    
    def process_text_message(self, packet, decoded, message):
        """Déléguer au router"""
        self.router.process_text_message(packet, decoded, message)
    
    def cleanup_throttling_data(self):
        """Déléguer au router"""
        self.router.cleanup_throttling_data()
    
    # Méthodes publiques pour accès direct si nécessaire
    def format_legend(self):
        """Format légende - pour compatibilité"""
        return self.router.utility_handler._format_legend()
    
    def format_help(self):
        """Format aide - pour compatibilité"""
        return self.router.utility_handler._format_help()

    def format_help_telegram(self, user_id=None):
        """Format aide détaillée pour Telegram - pour compatibilité"""
        return self.router.format_help_telegram(user_id)
