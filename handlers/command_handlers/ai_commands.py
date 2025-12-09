#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gestionnaire des commandes IA
"""

import time
from utils import info_print, error_print, debug_print
import traceback

class AICommands:
    def __init__(self, llama_client, sender, broadcast_tracker=None):
        self.llama_client = llama_client
        self.sender = sender
        self.broadcast_tracker = broadcast_tracker  # Callback pour tracker broadcasts
    
    def handle_bot(self, message, sender_id, sender_info, is_broadcast=False):
        """
        Gérer la commande /bot
        
        Args:
            message: Message complet (ex: "/bot quelle heure est-il?")
            sender_id: ID de l'expéditeur
            sender_info: Infos sur l'expéditeur
            is_broadcast: Si True, répondre en broadcast public
        """
        prompt = message[5:].strip()
        info_print(f"Bot: {sender_info}: '{prompt}' (broadcast={is_broadcast})")
        
        if prompt:
            start_time = time.time()
            # Utiliser la méthode spécifique Mesh pour les réponses courtes
            response = self.llama_client.query_llama_mesh(prompt, sender_id)
            end_time = time.time()
            
            self.sender.log_conversation(sender_id, sender_info, prompt, response, end_time - start_time)
            
            # Envoyer selon le mode (broadcast ou direct)
            if is_broadcast:
                self._send_broadcast_via_tigrog2(response, sender_id, sender_info, "/bot")
            else:
                self.sender.send_chunks(response, sender_id, sender_info)
            
            # Nettoyage après traitement
            self.llama_client.cleanup_cache()
        else:
            usage_msg = "Usage: /bot <question>"
            if is_broadcast:
                self._send_broadcast_via_tigrog2(usage_msg, sender_id, sender_info, "/bot")
            else:
                self.sender.send_single(usage_msg, sender_id, sender_info)
    
    def _send_broadcast_via_tigrog2(self, message, sender_id, sender_info, command):
        """
        Envoyer un message en broadcast via l'interface partagée
        
        Note: Utilise l'interface existante au lieu de créer une nouvelle connexion TCP.
        Cela évite les conflits de socket avec la connexion principale.
        """
        try:
            # Récupérer l'interface partagée (évite de créer une nouvelle connexion TCP)
            interface = self.sender._get_interface()
            
            if interface is None:
                error_print(f"❌ Interface non disponible pour broadcast {command}")
                return
            
            # Tracker le broadcast AVANT l'envoi pour éviter boucle
            if self.broadcast_tracker:
                self.broadcast_tracker(message)
            
            debug_print(f"📡 Broadcast {command} via interface partagée...")
            
            # Utiliser l'interface partagée - PAS de nouvelle connexion TCP!
            interface.sendText(message)
            
            info_print(f"✅ Broadcast {command} diffusé")
            self.sender.log_conversation(sender_id, sender_info, command, message)
            
        except Exception as e:
            error_print(f"❌ Échec broadcast {command}: {e}")
            error_print(traceback.format_exc())
