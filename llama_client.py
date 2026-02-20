#!/usr/bin/env python3
import traceback
# -*- coding: utf-8 -*-
"""
Client pour l'API Llama avec configurations différenciées et protections système
VERSION AVEC VÉRIFICATIONS TEMPÉRATURE CPU ET BATTERIE
"""

import time
import gc
from config import *
from utils import *
from system_checks import SystemChecks

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
    
    def clean_ai_response(self, content, max_chars=None):
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
            
            # Tronquer si nécessaire selon le canal
            if max_chars and len(content) > max_chars:
                content = content[:max_chars-3] + "..."
                
            debug_print(f"Nettoyé: '{content[:2000]}...'")
            return content
            
        except Exception as e:
            debug_print(f"Erreur nettoyage: {e}")
            return content if content else "Erreur"
    
    def query_llama_mesh(self, prompt, node_id=None):
        """Requête optimisée pour Meshtastic (réponses courtes)"""
        return self.query_llama(prompt, node_id, "mesh")
    
    def query_llama_telegram(self, prompt, node_id=None):
        """Requête optimisée pour Telegram (réponses étendues)"""
        info_print("=== DEBUT query_llama_telegram ===")
        
        try:
            result = self.query_llama(prompt, node_id, "telegram")
            info_print(f"=== FIN query_llama_telegram OK: {len(result)} chars ===")
            return result
        except Exception as e:
            error_print(f"=== ERREUR query_llama_telegram: {e} ===")
            error_print(f"Stack trace: {traceback.format_exc()}")
            return f"Erreur Telegram: {str(e)}"
    
    def query_llama(self, prompt, node_id=None, source_type="mesh"):
        """
        Requête au serveur llama avec contexte conversationnel
        source_type: "mesh" ou "telegram" pour adapter les paramètres
        
        ⚡ VERSION AVEC PROTECTION TEMPÉRATURE CPU ET BATTERIE ⚡
        """
        info_print(f"STEP 0: Vérification conditions système...")
        
        # === NOUVELLE VÉRIFICATION: CONDITIONS SYSTÈME ===
        try:
            allowed, block_reason = SystemChecks.check_llm_conditions()
            
            if not allowed:
                info_print(f"🚫 LLM BLOQUÉ: {block_reason}")
                # Retourner le message d'erreur à l'utilisateur
                return block_reason
            
            info_print("✅ Conditions système OK, poursuite requête LLM")
            
        except Exception as check_error:
            # Si la vérification échoue, on log mais on continue (fail-open)
            error_print(f"⚠️ Erreur vérification système: {check_error}")
            info_print("⚠️ Vérification système échouée, autorisation par défaut")
        
        # === SUITE DU CODE NORMAL ===
        info_print(f"STEP 1: Début query_llama source_type={source_type}")
        
        try:
            requests_module = lazy_import_requests()
            info_print(f"Envoi à llama ({source_type}): '{prompt[:300]}...'")
            
            # Sélectionner la configuration selon la source
            if source_type == "telegram":
                ai_config = TELEGRAM_AI_CONFIG
                debug_print("Configuration Telegram (réponses étendues)")
            else:
                ai_config = MESH_AI_CONFIG
                debug_print("Configuration Mesh (réponses courtes)")
            
            info_print(f"STEP 2: Configuration chargée, timeout={ai_config['timeout']}s")
            
            # Construire les messages avec contexte
            messages = [
                {
                    "role": "system",
                    "content": ai_config["system_prompt"]
                }
            ]
            
            info_print("STEP 3: Message système ajouté")
            
            # Ajouter le contexte conversationnel si disponible
            if node_id and self.context_manager:
                info_print("STEP 4a: Récupération contexte...")
                try:
                    context = self.context_manager.get_conversation_context(node_id)
                    if context:
                        debug_print(f"Utilise contexte: {len(context)} messages")
                        # Ajouter les messages du contexte (en gardant l'ordre chronologique)
                        for ctx_msg in context:
                            messages.append({
                                "role": ctx_msg['role'],
                                "content": ctx_msg['content']
                            })
                        info_print(f"STEP 4b: {len(context)} messages de contexte ajoutés")
                    else:
                        debug_print("Nouvelle conversation")
                        info_print("STEP 4b: Nouvelle conversation, pas de contexte")
                except Exception as context_error:
                    error_print(f"ERREUR contexte: {context_error}")
                    info_print("STEP 4b: Erreur contexte, continuation sans")
            else:
                info_print("STEP 4: Pas de contexte demandé")
            
            # Ajouter la nouvelle question
            messages.append({
                "role": "user",
                "content": prompt
            })
            
            info_print("STEP 5: Question utilisateur ajoutée")
            
            # Configuration de la requête avec paramètres adaptés
            data = {
                "messages": messages,
                "max_tokens": ai_config["max_tokens"],
                "temperature": ai_config["temperature"],
                "top_p": ai_config["top_p"],
                "top_k": ai_config["top_k"]
            }
            
            info_print(f"STEP 6: Payload préparé, {len(messages)} messages total")
            debug_print(f"Messages envoyés: {len(messages)} (dont {len(messages)-2} contexte)")
            debug_print(f"Config: tokens={ai_config['max_tokens']}, temp={ai_config['temperature']}, timeout={ai_config['timeout']}s")
            
            info_print("STEP 7: Début appel HTTP à llama.cpp...")
            start_time = time.time()
            
            # POINT CRITIQUE: L'appel HTTP
            try:
                response = requests_module.post(
                    f"http://{LLAMA_HOST}:{LLAMA_PORT}/v1/chat/completions", 
                    json=data, 
                    timeout=ai_config["timeout"]  # Timeout adapté
                )
                info_print("STEP 8: Appel HTTP terminé, traitement réponse...")
            except Exception as http_error:
                error_print(f"ERREUR HTTP: {http_error}")
                raise http_error
            
            end_time = time.time()
            
            debug_print(f"Temps: {end_time - start_time:.2f}s")
            info_print(f"STEP 9: Réponse reçue en {end_time - start_time:.2f}s, status={response.status_code}")
            
            if response.status_code == 200:
                info_print("STEP 10: Status 200, parsing JSON...")
                try:
                    result = response.json()
                    info_print("STEP 11: JSON parsé avec succès")
                except Exception as json_error:
                    error_print(f"ERREUR parsing JSON: {json_error}")
                    error_print(f"Contenu brut: {response.text[:200]}...")
                    raise json_error
                
                content = result['choices'][0]['message']['content'].strip() if 'choices' in result else "Pas de réponse"
                info_print(f"STEP 12: Contenu extrait: {len(content)} chars")
                
                # Sauvegarder dans le contexte
                if node_id and self.context_manager:
                    info_print("STEP 13: Sauvegarde contexte...")
                    try:
                        self.context_manager.add_to_context(node_id, 'user', prompt)
                        self.context_manager.add_to_context(node_id, 'assistant', content)
                        info_print("STEP 14: Contexte sauvegardé")
                    except Exception as save_error:
                        error_print(f"ERREUR sauvegarde contexte: {save_error}")
                else:
                    info_print("STEP 13-14: Pas de sauvegarde contexte")
                
                # Libérer immédiatement
                info_print("STEP 15: Nettoyage mémoire...")
                try:
                    del response, result, data, messages
                    gc.collect()
                    info_print("STEP 16: Nettoyage mémoire OK")
                except Exception as cleanup_error:
                    error_print(f"ERREUR nettoyage: {cleanup_error}")
                
                # Nettoyer avec la limite de caractères appropriée
                info_print("STEP 17: Nettoyage réponse IA...")
                try:
                    cleaned_response = self.clean_ai_response(content, ai_config["max_response_chars"])
                    info_print(f"STEP 18: Nettoyage OK, {len(cleaned_response)} chars finaux")
                    return cleaned_response
                except Exception as clean_error:
                    error_print(f"ERREUR nettoyage réponse: {clean_error}")
                    return content  # Retourner non nettoyé en fallback
            else:
                error_print(f"STEP 10: Status {response.status_code}")
                error_print(f"Erreur HTTP {response.status_code}: {response.text[:100]}")
                del response, data, messages
                return "Erreur serveur IA"
                
        except Exception as e:
            # Detect connection errors (llama.cpp unavailable) for a clear user message
            try:
                is_connection_error = isinstance(e, requests_module.exceptions.ConnectionError)
            except Exception:
                is_connection_error = False
            if is_connection_error:
                error_msg = "❌ llama.cpp non disponible"
            else:
                error_msg = f"Erreur IA ({source_type}): {str(e)[:50]}"
            error_print(f"EXCEPTION GLOBALE: {error_msg}")
            error_print(f"Stack trace complet: {traceback.format_exc()}")
            return error_msg
    
    def cleanup_cache(self):
        """Nettoyage périodique du cache"""
        if len(self._response_cache) > MAX_CACHE_SIZE:
            items = list(self._response_cache.items())
            self._response_cache = dict(items[-3:])
        gc.collect()
