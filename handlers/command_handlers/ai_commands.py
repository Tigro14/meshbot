#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gestionnaire des commandes IA
"""

import time
from utils import info_print

class AICommands:
    def __init__(self, llama_client, sender):
        self.llama_client = llama_client
        self.sender = sender
    
    def handle_bot(self, message, sender_id, sender_info):
        """Gérer la commande /bot"""
        prompt = message[5:].strip()
        info_print(f"Bot: {sender_info}: '{prompt}'")
        
        if prompt:
            start_time = time.time()
            # Utiliser la méthode spécifique Mesh pour les réponses courtes
            response = self.llama_client.query_llama_mesh(prompt, sender_id)
            end_time = time.time()
            
            self.sender.log_conversation(sender_id, sender_info, prompt, response, end_time - start_time)
            self.sender.send_chunks(response, sender_id, sender_info)
            
            # Nettoyage après traitement
            self.llama_client.cleanup_cache()
        else:
            self.sender.send_single("Usage: /bot <question>", sender_id, sender_info)
