#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gestion de l'envoi de messages et throttling
"""

import time
from config import *
from utils import *

class MessageSender:
    def __init__(self, interface, node_manager):
        self.interface = interface
        self.node_manager = node_manager
        
        # Throttling des commandes utilisateurs
        self.user_commands = {}  # user_id -> [timestamps des commandes]
        self._last_echo_id = None  # Cache doublons echo
    
    def check_throttling(self, sender_id, sender_info):
        """Vérifier le throttling des commandes pour un utilisateur"""
        current_time = time.time()
        
        # Nettoyer d'abord les anciennes entrées
        if sender_id in self.user_commands:
            self.user_commands[sender_id] = [
                cmd_time for cmd_time in self.user_commands[sender_id]
                if current_time - cmd_time < COMMAND_WINDOW_SECONDS
            ]
        else:
            self.user_commands[sender_id] = []
        
        # Vérifier le nombre de commandes dans la fenêtre
        command_count = len(self.user_commands[sender_id])
        
        if command_count >= MAX_COMMANDS_PER_WINDOW:
            # Calculer le temps d'attente
            oldest_command = min(self.user_commands[sender_id])
            wait_time = int(COMMAND_WINDOW_SECONDS - (current_time - oldest_command))
            
            # Envoyer message de throttling
            throttle_msg = f"⏱️ Limite: {MAX_COMMANDS_PER_WINDOW} cmd/5min. Attendez {wait_time}s"
            try:
                self.send_single(throttle_msg, sender_id, sender_info)
            except Exception as e:
                debug_print(f"Envoi message throttling échoué: {e}")
            
            info_print(f"THROTTLE: {sender_info} - {command_count}/{MAX_COMMANDS_PER_WINDOW} commandes")
            return False
        
        # Ajouter la commande actuelle
        self.user_commands[sender_id].append(current_time)
        debug_print(f"Throttling {sender_info}: {command_count + 1}/{MAX_COMMANDS_PER_WINDOW} commandes")
        return True
    
    def cleanup_throttling(self):
        """Nettoyer les données de throttling anciennes"""
        current_time = time.time()
        users_to_remove = []
        
        for user_id, command_times in self.user_commands.items():
            recent_commands = [
                cmd_time for cmd_time in command_times
                if current_time - cmd_time < COMMAND_WINDOW_SECONDS
            ]
            
            if recent_commands:
                self.user_commands[user_id] = recent_commands
            else:
                users_to_remove.append(user_id)
        
        for user_id in users_to_remove:
            del self.user_commands[user_id]
        
        if users_to_remove and DEBUG_MODE:
            debug_print(f"Nettoyage throttling: {len(users_to_remove)} utilisateurs supprimés")
    
    def send_single(self, message, sender_id, sender_info):
        """Envoyer un message simple"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.interface.sendText(message, destinationId=sender_id)
                debug_print(f"Message → {sender_info}")
                return True
            except MeshInterface.MeshInterfaceError as e:
                error_print(f"Échec envoi → {sender_info}: {e}")
                # Essayer avec le format hex string
                try:
                    hex_id = f"!{sender_id:08x}"
                    self.interface.sendText(message, destinationId=hex_id)
                    debug_print(f"Message → {sender_info} (hex format)")
                except Exception as e2:
                    error_print(f"Échec envoi définitif → {sender_info}: {e2}")
                    if "Timed out waiting for connection" in str(e):
                        print(f"Tentative {attempt+1}/{max_retries} - Reconnexion...")
                        error_print(f"Échec envoi définitif → {sender_info}: {e2}")
                        self._reconnect()
                        time.sleep(2)
                    else:
                        raise
        return False

    def _reconnect(self):
        try:
            self.interface.close()
        except:
            pass
        # Réinitialiser la connexion
        self.interface = meshtastic.serial_interface.SerialInterface()


    def send_chunks(self, response, sender_id, sender_info):
        """Diviser et envoyer un long message"""
        try:
            max_length = MAX_MESSAGE_SIZE
            
            if len(response) <= max_length:
                self.send_single(response, sender_id, sender_info)
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
                    
                    self.send_single(formatted_chunk, sender_id, sender_info)
                    if i < len(chunks):
                        time.sleep(2)
                        
        except Exception as e:
            error_print(f"Erreur division: {e}")
            fallback = truncate_text(response, max_length-3, "...")
            self.send_single(fallback, sender_id, sender_info)
    
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
    
    def get_short_name(self, node_id):
        """Obtenir le nom court d'un nœud"""
        try:
            if hasattr(self.interface, 'nodes') and node_id in self.interface.nodes:
                node_info = self.interface.nodes[node_id]
                if isinstance(node_info, dict) and 'user' in node_info:
                    user_info = node_info['user']
                    if isinstance(user_info, dict):
                        short_name = user_info.get('shortName', '').strip()
                        if short_name:
                            return short_name
            
            # Fallback : 4 derniers caractères de l'ID
            return f"{node_id:08x}"[-4:]
                
        except Exception as e:
            debug_print(f"Erreur récupération nom court {node_id}: {e}")
            return f"{node_id:08x}"[-4:]
