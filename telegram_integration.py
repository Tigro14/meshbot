#!/usr/bin/env python3
"""
Module d'intégration Telegram dans le bot Meshtastic existant
À ajouter dans main_bot.py
"""

import json
import os
import time
import threading
from config import *
from utils import *

# Importer spécifiquement le mapping s'il existe
try:
    from config import TELEGRAM_TO_MESH_MAPPING
except ImportError:
    # Fallback si pas défini dans la config
    TELEGRAM_TO_MESH_MAPPING = {}

class TelegramIntegration:
    def __init__(self, message_handler, node_manager, context_manager):
        self.message_handler = message_handler
        self.node_manager = node_manager
        self.context_manager = context_manager
        
        # Utiliser les configurations centralisées
        self.queue_file = TELEGRAM_QUEUE_FILE
        self.response_file = TELEGRAM_RESPONSE_FILE
        
        self.running = False
        self.processor_thread = None
        
        # Créer les fichiers s'ils n'existent pas
        self._ensure_files_exist()
        
    def _ensure_files_exist(self):
        """Créer les fichiers de communication s'ils n'existent pas"""
        for file_path in [self.queue_file, self.response_file]:
            if not os.path.exists(file_path):
                try:
                    with open(file_path, 'w') as f:
                        json.dump([], f)
                    debug_print(f"Fichier créé: {file_path}")
                except Exception as e:
                    error_print(f"Erreur création {file_path}: {e}")
    
    def start(self):
        """Démarrer le processeur de requêtes Telegram"""
        if self.running:
            return
        
        self.running = True
        self.processor_thread = threading.Thread(target=self._process_telegram_requests, daemon=True)
        self.processor_thread.start()
        info_print("🔗 Interface Telegram démarrée")
    
    def stop(self):
        """Arrêter le processeur"""
        self.running = False
        if self.processor_thread:
            self.processor_thread.join(timeout=5)
        info_print("🔗 Interface Telegram arrêtée")
    
    def _process_telegram_requests(self):
        """Traiter les requêtes Telegram en continu"""
        while self.running:
            try:
                self._check_and_process_queue()
                time.sleep(1)  # Vérifier chaque seconde
            except Exception as e:
                error_print(f"Erreur processeur Telegram: {e}")
                time.sleep(5)  # Attendre plus longtemps en cas d'erreur
    
    def _check_and_process_queue(self):
        """Vérifier et traiter la queue des requêtes"""
        try:
            if not os.path.exists(self.queue_file):
                return
            
            # Lire les requêtes
            requests_to_process = []
            try:
                with open(self.queue_file, 'r') as f:
                    requests_data = json.load(f)
                    if isinstance(requests_data, list):
                        requests_to_process = requests_data.copy()
            except (json.JSONDecodeError, FileNotFoundError):
                return
            
            if not requests_to_process:
                return
            
            # Vider le fichier de queue immédiatement pour éviter les doublons
            try:
                with open(self.queue_file, 'w') as f:
                    json.dump([], f)
            except Exception as e:
                error_print(f"Erreur vidage queue: {e}")
            
            # Traiter chaque requête
            for request in requests_to_process:
                try:
                    request_id = request.get("id", "unknown")
                    debug_print(f"Traitement requête Telegram: {request_id}")
                    
                    response = self._process_single_request(request)
                    self._send_response(request_id, response)
                    
                    info_print(f"✅ Requête Telegram {request_id} traitée")
                    
                except Exception as e:
                    error_response = f"Erreur traitement: {str(e)[:80]}"
                    request_id = request.get("id", "unknown")
                    self._send_response(request_id, error_response)
                    error_print(f"Erreur traitement requête Telegram {request_id}: {e}")
                
        except Exception as e:
            error_print(f"Erreur lecture queue Telegram: {e}")
    
    def _get_mesh_identity(self, telegram_id, telegram_username):
        """Obtenir l'identité Meshtastic pour un utilisateur Telegram"""
        # Vérifier s'il y a un mapping configuré
        if telegram_id in TELEGRAM_TO_MESH_MAPPING:
            mapping = TELEGRAM_TO_MESH_MAPPING[telegram_id]
            return {
                "node_id": mapping["node_id"],
                "short_name": mapping["short_name"],
                "display_name": mapping["display_name"]
            }
        
        # Fallback : utiliser l'ID Telegram comme base
        fallback_node_id = telegram_id & 0xFFFFFFFF
        return {
            "node_id": fallback_node_id,
            "short_name": telegram_username[:8] if telegram_username else f"{fallback_node_id:08x}"[-4:],
            "display_name": f"TG:{telegram_username}" if telegram_username else f"TG:{fallback_node_id:08x}"
        }
    
    def _process_single_request(self, request):
        """Traiter une requête Telegram individuelle"""
        command = request.get("command", "").strip()
        user_info = request.get("user", {})
        telegram_id = user_info.get("telegram_id", 0)
        telegram_username = user_info.get("username", "Telegram")
        
        debug_print(f"🔄 Commande Telegram: '{command}' de {telegram_username}")
        
        # Obtenir l'identité Meshtastic configurée
        mesh_identity = self._get_mesh_identity(telegram_id, telegram_username)
        sender_id = mesh_identity["node_id"]
        sender_info = mesh_identity["display_name"]
        
        debug_print(f"🎯 Mapping: {telegram_username} ({telegram_id}) -> {mesh_identity['short_name']} (0x{sender_id:08x})")
        
        # Router la commande vers le gestionnaire approprié
        try:
            if command.startswith('/bot '):
                return self._handle_bot_command(command, sender_id, sender_info)
            elif command.startswith('/power'):
                return self._handle_power_command(sender_id, sender_info)
            elif command.startswith('/rx'):
                return self._handle_rx_command(command, sender_id, sender_info)
            elif command.startswith('/my'):
                return self._handle_my_command(sender_id, sender_info)
            elif command.startswith('/sys'):
                return self._handle_sys_command(sender_id, sender_info)
            elif command.startswith('/legend'):
                return self._handle_legend_command(sender_id, sender_info)
            elif command.startswith('/echo '):
                return self._handle_echo_command(command, sender_id, sender_info, mesh_identity)
            elif command.startswith('/help'):
                return self._handle_help_command(sender_id, sender_info)
            else:
                return f"❓ Commande inconnue: {command}\n\nTapez /help pour l'aide"
                
        except Exception as e:
            error_print(f"Erreur traitement commande '{command}': {e}")
            return f"❌ Erreur interne: {str(e)[:100]}"
    
    def _handle_bot_command(self, command, sender_id, sender_info):
        """Traiter /bot depuis Telegram"""
        try:
            prompt = command[5:].strip()
            if not prompt:
                return "Usage: /bot <question>"
            
            debug_print(f"🤖 Bot IA pour {sender_info}: '{prompt}'")
            response = self.message_handler.llama_client.query_llama(prompt, sender_id)
            
            # Logger la conversation
            self.message_handler.log_conversation(sender_id, sender_info, prompt, response)
            
            return response
            
        except Exception as e:
            return f"❌ Erreur /bot: {str(e)[:80]}"
    
    def _handle_power_command(self, sender_id, sender_info):
        """Traiter /power depuis Telegram"""
        try:
            debug_print(f"🔋 Power pour {sender_info}")
            esphome_data = self.message_handler.esphome_client.parse_esphome_data()
            
            # Logger la conversation
            self.message_handler.log_conversation(sender_id, sender_info, "/power", esphome_data)
