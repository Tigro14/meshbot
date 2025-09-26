async def send_to_meshtastic(self, command, user):
        """Envoyer une commande au bot Meshtastic via API avec timeout adapté"""
        request_data = {
            "id": f"tg_{int(time.time()*1000)}",
            "command": command,
            "source": "telegram",
            "user": {
                "telegram_id": user.id,
                "username": user.username or user.first_name,
                "first_name": user.first_name
            },
            "timestamp": time.time()
        }
        
        try:
            # Écrire la requête dans le fichier de queue
            requests = []
            if os.path.exists(self.queue_file):
                with open(self.queue_file, 'r') as f:
                    try:
                        requests = json.load(f)
                    except json.JSONDecodeError:
                        requests = []
            
            requests.append(request_data)
            
            with open(self.queue_file, 'w') as f:
                json.dump(requests, f)
            
            # Attendre la réponse avec timeout adapté selon le type de commande
            if command.startswith('/bot '):
                # Timeout plus long pour les commandes IA
                timeout = TELEGRAM_AI_CONFIG["timeout"] + 30  # Marge de sécurité
                logger.info(f"⏳ Attente réponse IA (timeout: {timeout}s)")
            else:
                # Timeout standard pour les autres commandes
                timeout = TELEGRAM_COMMAND_TIMEOUT
            
            return await self.wait_for_response(request_data["id"], timeout=timeout)
            
        except Exception as e:
            logger.error(f"Erreur interface Telegram: {e}")
            return f"Erreur interface: {str(e)}"
    
    async def wait_for_response(self, request_id, timeout=150):
        """Attendre la réponse du bot Meshtastic avec timeout configurable"""
        start_time = time.time()
        check_interval = 0.5  # Vérifier toutes les 500ms
        
        while (time.time() - start_time) < timeout:
            try:
                if os.path.exists(self.response_file):
                    with open(self.response_file, 'r') as f:
                        try:
                            responses = json.load(f)
                        except json.JSONDecodeError:
                            responses = []
                    
                    # Chercher notre réponse
                    for i, response in enumerate(responses):
                        if response.get("request_id") == request_id:
                            result = response.get("response", "Pas de réponse")
                            
                            # Supprimer la réponse traitée
                            responses.pop(i)
                            with open(self.response_file, 'w') as f:
                                json.dump(responses, f)
                            
                            elapsed = time.time() - start_time
                            logger.info(f"✅ Réponse reçue en {elapsed:.1f}s")
                            return result
                
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                logger.error(f"Erreur attente réponse: {e}")
                continue
        
        logger.warning(f"⏰ Timeout après {timeout}s pour request_id: {request_id}")
        return f"⏰ Timeout - pas de réponse du bot Meshtastic après {timeout}s"
