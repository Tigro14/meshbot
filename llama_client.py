#!/usr/bin/env python3
"""
Client pour l'API Llama
"""

import time
import gc
from config import *
from utils import *

class LlamaClient:
    def __init__(self, context_manager):
        self.context_manager = context_manager
        # Cache limité pour les réponses
        self._response_cache = {}
        # Patterns compilés une seule fois
        self._clean_patterns = None
    
    def _get_clean_patterns(self):
        """Initialise les patterns regex une seule fois"""
        if self._clean_patterns is None:
            re_module = lazy_import_re()
            self._clean_patterns = [
                re_module.compile(r'<think>.*?</think>', re_module.DOTALL | re_module.IGNORECASE),
                re_module.compile(r'<thinking>.*?</thinking>', re_module.DOTALL | re_module.IGNORECASE)
            ]
        return self._clean_patterns
    
    def test_connection(self):
        """Test du serveur llama - version allégée"""
        try:
            requests_module = lazy_import_requests()
            response = requests_module.get(f"http://{LLAMA_HOST}:{LLAMA_PORT}/health", timeout=3)
            success = response.status_code == 200
            del response
            if success:
                info_print("Serveur llama.cpp connecté")
            return success
        except Exception as e:
            error_print(f"Serveur llama.cpp inaccessible: {e}")
            return False
    
    def clean_ai_response(self, content):
        """Nettoie la réponse de l'IA - version optimisée mémoire"""
        try:
            debug_print(f"Nettoyage: '{content[:50]}...'")
            
            patterns = self._get_clean_patterns()
            for pattern in patterns:
                content = pattern.sub('', content)
            
            # Nettoyage efficace des espaces
            content = ' '.join(content.split())
            
            if not content or len(content.strip()) < 2:
                content = "Pas de réponse"
                
            debug_print(f"Nettoyé: '{content[:50]}...'")
            return content
            
        except Exception as e:
            debug_print(f"Erreur nettoyage: {e}")
            return content if content else "Erreur"
    
    def query_llama(self, prompt, node_id=None):
        """Requête au serveur llama avec contexte conversationnel"""
        try:
            requests_module = lazy_import_requests()
            debug_print(f"Envoi à llama: '{prompt[:30]}...'")
            
            # Construire les messages avec contexte
            messages = [
                {
                    "role": "system",
                    "content": "Tu es un assistant accessible via le réseau Meshtastic en LoRa. Réponds en français, très court, 320 caractères. Maintiens la continuité de la conversation."
                }
            ]
            
            # Ajouter le contexte conversationnel si disponible
            if node_id and self.context_manager:
                context = self.context_manager.get_conversation_context(node_id)
                if context:
                    debug_print(f"📚 Utilise contexte: {len(context)} messages")
                    # Ajouter les messages du contexte (en gardant l'ordre chronologique)
                    for ctx_msg in context:
                        messages.append({
                            "role": ctx_msg['role'],
                            "content": ctx_msg['content']
                        })
                else:
                    debug_print("🆕 Nouvelle conversation")
            
            # Ajouter la nouvelle question
            messages.append({
                "role": "user",
                "content": prompt
            })
            
            data = {
                "messages": messages,
                "max_tokens": 2000,
                "temperature": 0.7,  # Légèrement plus élevé pour plus de variété
                "top_p": 0.95,
                "top_k": 20
            }
            
            debug_print(f"📊 Messages envoyés: {len(messages)} (dont {len(messages)-2} contexte)")
            
            start_time = time.time()
            response = requests_module.post(f"http://{LLAMA_HOST}:{LLAMA_PORT}/v1/chat/completions", 
                                          json=data, timeout=60)
            end_time = time.time()
            
            debug_print(f"Temps: {end_time - start_time:.2f}s")
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content'].strip() if 'choices' in result else "Pas de réponse"
                
                # Sauvegarder dans le contexte
                if node_id and self.context_manager:
                    self.context_manager.add_to_context(node_id, 'user', prompt)
                    self.context_manager.add_to_context(node_id, 'assistant', content)
                
                # Libérer immédiatement
                del response, result, data, messages
                gc.collect()
                
                return self.clean_ai_response(content)
            else:
                del response, data, messages
                return "Erreur serveur"
                
        except Exception as e:
            error_msg = f"Erreur IA: {str(e)[:30]}"
            error_print(error_msg)
            return error_msg
    
    def cleanup_cache(self):
        """Nettoyage périodique du cache"""
        if len(self._response_cache) > MAX_CACHE_SIZE:
            items = list(self._response_cache.items())
            self._response_cache = dict(items[-3:])
        gc.collect() 