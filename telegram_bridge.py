#!/usr/bin/env python3
# -*- coding: utf-8 -*-

    async def send_to_meshtastic(self, command, user):
        """Envoyer une commande au bot Meshtastic via API avec debug complet"""
        request_id = f"tg_{int(time.time()*1000)}"
        request_data = {
            "id": request_id,
            "command": command,
            "source": "telegram",
            "user": {
                "telegram_id": user.id,
                "username": user.username or user.first_name,
                "first_name": user.first_name
            },
            "timestamp": time.time()
        }
        
        logger.info(f"Envoi commande à Meshtastic: {command} (ID: {request_id})")
        
        try:
            # Écrire la requête dans le fichier de queue
            requests = []
            if os.path.exists(self.queue_file):
                with open(self.queue_file, 'r') as f:
                    try:
                        requests = json.load(f)
                        logger.info(f"{len(requests)} requêtes existantes dans la queue")
                    except json.JSONDecodeError:
                        logger.warning("Queue corrompue, réinitialisation")
                        requests = []
            
            requests.append(request_data)
            
            with open(self.queue_file, 'w') as f:
                json.dump(requests, f)
            
            logger.info(f"Requête {request_id} ajoutée à la queue ({len(requests)} total)")
            
            # Attendre la réponse avec timeout adapté selon le type de commande
            if command.startswith('/bot '):
                # Timeout plus long pour les commandes IA
                timeout = TELEGRAM_AI_CONFIG["timeout"] + 30  # Marge de sécurité
                logger.info(f"Attente réponse IA (timeout: {timeout}s)")
            else:
                # Timeout standard pour les autres commandes
                timeout = TELEGRAM_COMMAND_TIMEOUT
                logger.info(f"Attente réponse standard (timeout: {timeout}s)")
            
            start_wait = time.time()
            result = await self.wait_for_response(request_id, timeout=timeout)
            wait_duration = time.time() - start_wait
            
            logger.info(f"Réponse reçue après {wait_duration:.1f}s: '{result[:100]}...'")
            return result
            
        except Exception as e:
            logger.error(f"Erreur interface Telegram: {e}")
            import traceback
            logger.error(f"Stack trace send_to_meshtastic: {traceback.format_exc()}")
            return f"Erreur interface: {str(e)}"
    
    async def wait_for_response(self, request_id, timeout=150):
        """Attendre la réponse du bot Meshtastic avec debug complet"""
        logger.info(f"Début attente réponse pour {request_id} (timeout: {timeout}s)")
        start_time = time.time()
        check_interval = 0.5  # Vérifier toutes les 500ms
        checks_count = 0
        
        while (time.time() - start_time) < timeout:
            checks_count += 1
            elapsed = time.time() - start_time
            
            # Log périodique pour montrer que le processus fonctionne
            if checks_count % 20 == 0:  # Toutes les 10 secondes
                logger.info(f"Attente en cours... {elapsed:.1f}s/{timeout}s (vérification #{checks_count})")
            
            try:
                if not os.path.exists(self.response_file):
                    await asyncio.sleep(check_interval)
                    continue
                
                with open(self.response_file, 'r') as f:
                    try:
                        responses = json.load(f)
                    except json.JSONDecodeError:
                        logger.warning(f"Fichier réponse corrompu à {elapsed:.1f}s")
                        await asyncio.sleep(check_interval)
                        continue
                
                if not responses:
                    await asyncio.sleep(check_interval)
                    continue
                
                logger.debug(f"Vérification {len(responses)} réponses disponibles")
                
                # Chercher notre réponse
                for i, response in enumerate(responses):
                    if response.get("request_id") == request_id:
                        result = response.get("response", "Pas de réponse")
                        response_timestamp = response.get("timestamp", 0)
                        
                        logger.info(f"Réponse trouvée pour {request_id}!")
                        logger.info(f"Contenu: '{result[:200]}...'")
                        logger.info(f"Réponse générée à: {time.strftime('%H:%M:%S', time.localtime(response_timestamp))}")
                        
                        # Supprimer la réponse traitée
                        responses.pop(i)
                        with open(self.response_file, 'w') as f:
                            json.dump(responses, f)
                        
                        elapsed = time.time() - start_time
                        logger.info(f"Réponse {request_id} reçue en {elapsed:.1f}s après {checks_count} vérifications")
                        return result
                
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                logger.error(f"Erreur attente réponse: {e}")
                import traceback
                logger.error(f"Stack trace wait_for_response: {traceback.format_exc()}")
                await asyncio.sleep(check_interval)
                continue
        
        elapsed = time.time() - start_time
        logger.warning(f"TIMEOUT après {elapsed:.1f}s pour {request_id}")
        logger.warning(f"{checks_count} vérifications effectuées")
        
        # Diagnostics en cas de timeout
        try:
            if os.path.exists(self.response_file):
                with open(self.response_file, 'r') as f:
                    responses = json.load(f)
                logger.warning(f"{len(responses)} réponses dans le fichier au moment du timeout")
                for resp in responses:
                    resp_id = resp.get("request_id", "unknown")
                    resp_time = resp.get("timestamp", 0)
                    logger.warning(f"   - ID: {resp_id}, Time: {time.strftime('%H:%M:%S', time.localtime(resp_time))}")
            else:
                logger.warning("Fichier de réponses inexistant au moment du timeout")
                
            if os.path.exists(self.queue_file):
                with open(self.queue_file, 'r') as f:
                    queue = json.load(f)
                logger.warning(f"{len(queue)} requêtes dans la queue au moment du timeout")
        except Exception as diag_error:
            logger.error(f"Erreur diagnostics timeout: {diag_error}")
        
        return f"Timeout - pas de réponse du bot Meshtastic après {timeout}s"
