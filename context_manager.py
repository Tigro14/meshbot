#!/usr/bin/env python3
"""
Gestionnaire des contextes conversationnels
"""

import time
from config import *
from utils import *

class ContextManager:
    def __init__(self, node_manager):
        self.node_manager = node_manager
        self.conversation_context = {}  # node_id -> [{'role': 'user'/'assistant', 'content': str, 'timestamp': float}]
    
    def get_conversation_context(self, node_id):
        """Récupérer le contexte conversationnel pour un nœud"""
        try:
            if node_id not in self.conversation_context:
                return []
            
            current_time = time.time()
            context = self.conversation_context[node_id]
            
            # Filtrer les messages trop anciens
            valid_context = [
                msg for msg in context 
                if current_time - msg['timestamp'] <= CONTEXT_TIMEOUT
            ]
            
            # Mettre à jour si des messages ont été supprimés
            if len(valid_context) != len(context):
                self.conversation_context[node_id] = valid_context
                debug_print(f"🧹 Contexte nettoyé pour {self.node_manager.get_node_name(node_id)}: {len(valid_context)} messages")
            
            return valid_context
            
        except Exception as e:
            debug_print(f"Erreur contexte: {e}")
            return []
    
    def add_to_context(self, node_id, role, content):
        """Ajouter un message au contexte conversationnel"""
        try:
            current_time = time.time()
            
            if node_id not in self.conversation_context:
                self.conversation_context[node_id] = []
            
            # Ajouter le nouveau message
            message = {
                'role': role,
                'content': content,
                'timestamp': current_time
            }
            
            self.conversation_context[node_id].append(message)
            
            # Limiter la taille du contexte (garder les plus récents)
            if len(self.conversation_context[node_id]) > MAX_CONTEXT_MESSAGES:
                self.conversation_context[node_id] = self.conversation_context[node_id][-MAX_CONTEXT_MESSAGES:]
            
            debug_print(f"📝 Contexte {self.node_manager.get_node_name(node_id)}: +{role} ({len(self.conversation_context[node_id])} msgs)")
            
        except Exception as e:
            debug_print(f"Erreur ajout contexte: {e}")
    
    def cleanup_old_contexts(self):
        """Nettoyer les contextes trop anciens"""
        try:
            current_time = time.time()
            nodes_to_remove = []
            
            for node_id, context in self.conversation_context.items():
                # Filtrer les messages valides
                valid_messages = [
                    msg for msg in context 
                    if current_time - msg['timestamp'] <= CONTEXT_TIMEOUT
                ]
                
                if not valid_messages:
                    # Aucun message valide, supprimer le contexte
                    nodes_to_remove.append(node_id)
                elif len(valid_messages) != len(context):
                    # Certains messages expirés, nettoyer
                    self.conversation_context[node_id] = valid_messages
            
            # Supprimer les contextes vides
            for node_id in nodes_to_remove:
                del self.conversation_context[node_id]
                debug_print(f"🗑️ Contexte supprimé: {self.node_manager.get_node_name(node_id)}")
                
        except Exception as e:
            debug_print(f"Erreur nettoyage contexte: {e}")
    
    def list_active_contexts(self):
        """Lister les contextes actifs (pour debug)"""
        if not DEBUG_MODE:
            return
        
        info_print("📚 Contextes conversationnels:")
        if not self.conversation_context:
            info_print("  Aucun contexte actif")
        else:
            for node_id, context in self.conversation_context.items():
                name = self.node_manager.get_node_name(node_id)
                info_print(f"  {name} (!{node_id:08x}): {len(context)} messages")
    
    def get_memory_stats(self):
        """Obtenir les statistiques mémoire des contextes"""
        active_contexts = len(self.conversation_context)
        total_messages = sum(len(ctx) for ctx in self.conversation_context.values())
        return active_contexts, total_messages
