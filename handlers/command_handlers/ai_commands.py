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
        Gérer la commande /bot ou /ia (alias français)
        
        Args:
            message: Message complet (ex: "/bot quelle heure est-il?" ou "/ia quelle heure est-il?")
            sender_id: ID de l'expéditeur
            sender_info: Infos sur l'expéditeur
            is_broadcast: Si True, répondre en broadcast public
        """
        # Détecter la commande utilisée (/bot ou /ia) et extraire le prompt
        if message.startswith('/ia'):
            prompt = message[3:].strip()  # Longueur de "/ia"
            command_name = "/ia"
        else:  # /bot
            prompt = message[4:].strip()  # Longueur de "/bot"
            command_name = "/bot"
        
        info_print(f"Bot: {sender_info}: '{prompt}' (broadcast={is_broadcast}, command={command_name})")
        
        if prompt:
            start_time = time.time()
            # Utiliser la méthode spécifique Mesh pour les réponses courtes
            response = self.llama_client.query_llama_mesh(prompt, sender_id)
            end_time = time.time()
            
            # Log conversation (pour tous les modes)
            self.sender.log_conversation(sender_id, sender_info, prompt, response, end_time - start_time)
            
            # Envoyer selon le mode (broadcast ou direct)
            if is_broadcast:
                self._send_broadcast_via_tigrog2(response, sender_id, sender_info, command_name)
            else:
                self.sender.send_chunks(response, sender_id, sender_info)
            
            # Nettoyage après traitement
            self.llama_client.cleanup_cache()
        else:
            usage_msg = f"Usage: {command_name} <question>"
            if is_broadcast:
                self._send_broadcast_via_tigrog2(usage_msg, sender_id, sender_info, command_name)
            else:
                self.sender.send_single(usage_msg, sender_id, sender_info)
    
    def _send_broadcast_via_tigrog2(self, message, sender_id, sender_info, command):
        """
        Envoyer un message en broadcast via l'interface partagée
        
        Note: Utilise l'interface existante au lieu de créer une nouvelle connexion TCP.
        Cela évite les conflits de socket avec la connexion principale.
        
        Note: Ne log PAS la conversation ici - c'est fait par l'appelant avant l'envoi.
        Cela évite les logs en double.
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
            
            # Detect interface type to handle MeshCore vs Meshtastic differences
            is_meshcore = hasattr(interface, '__class__') and 'MeshCore' in interface.__class__.__name__
            
            if is_meshcore:
                # MeshCore: Send as broadcast (0xFFFFFFFF) on public channel (channelIndex=0)
                debug_print("🔍 Interface MeshCore détectée - envoi broadcast sur canal public")
                interface.sendText(message, destinationId=0xFFFFFFFF, channelIndex=0)
                info_print(f"✅ Broadcast {command} diffusé via MeshCore (canal public)")
            else:
                # Meshtastic: Broadcast on public channel (channelIndex=0 is default)
                debug_print("🔍 Interface Meshtastic détectée - envoi broadcast sur canal public")
                interface.sendText(message, channelIndex=0)
                info_print(f"✅ Broadcast {command} diffusé via Meshtastic (canal public)")
            
        except Exception as e:
            error_print(f"❌ Échec broadcast {command}: {e}")
            error_print(traceback.format_exc())
