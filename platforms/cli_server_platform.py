#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Plateforme serveur CLI pour connexions TCP locales
Le bot écoute sur localhost:9999 et accepte des connexions CLI
"""

import socket
import threading
import json
from .platform_interface import MessagingPlatform
from utils import info_print, debug_print, error_print


class CLIMessageSender:
    """
    Message sender pour CLI qui redirige vers le socket TCP
    au lieu de l'interface Meshtastic
    """

    def __init__(self, cli_platform, user_id, interface_provider=None):
        self.cli_platform = cli_platform
        self.user_id = user_id
        self.interface_provider = interface_provider  # Store interface provider for _get_interface()

    def send_message(self, message, recipient_id, recipient_info):
        """Envoyer un message au client CLI"""
        # Ignorer recipient_id (serait pour mesh), envoyer au client CLI
        debug_print(f"[CLI] CLIMessageSender.send_message() called, message length: {len(message)}")
        self.cli_platform.send_message(self.user_id, message)

    def send_chunks(self, message, recipient_id, recipient_info):
        """Envoyer un message long au client CLI (pas de chunking nécessaire)"""
        # Pour CLI, pas besoin de chunking (pas de limite 180 chars)
        debug_print(f"[CLI] CLIMessageSender.send_chunks() called, message length: {len(message)}")
        self.cli_platform.send_message(self.user_id, message)

    def send_single(self, message, recipient_id, recipient_info):
        """Envoyer un message simple au client CLI"""
        debug_print(f"[CLI] CLIMessageSender.send_single() called, message length: {len(message)}")
        self.cli_platform.send_message(self.user_id, message)

    def log_conversation(self, sender_id, sender_info, query, response, processing_time=None):
        """Log une conversation (pour CLI, juste loguer dans console)"""
        from utils import conversation_print
        try:
            conversation_print("=" * 40)
            conversation_print(f"CLI USER: {sender_info} (!{sender_id:08x})")
            conversation_print(f"QUERY: {query}")
            conversation_print(f"RESPONSE: {response}")
            if processing_time:
                conversation_print(f"TIME: {processing_time:.2f}s")
            conversation_print("=" * 40)
        except Exception as e:
            error_print(f"Erreur logging CLI: {e}")

    def check_throttling(self, sender_id, sender_info):
        """Pas de throttling pour CLI locale"""
        return True

    def get_short_name(self, node_id):
        """Obtenir le nom court d'un nœud (pour compatibilité avec MessageSender)"""
        # Pour CLI, on peut essayer de récupérer depuis la plateforme ou utiliser un fallback
        try:
            # Accéder au node_manager via la plateforme CLI si disponible
            if hasattr(self.cli_platform, 'node_manager'):
                node_manager = self.cli_platform.node_manager
                if hasattr(node_manager, 'get_node_name'):
                    name = node_manager.get_node_name(node_id)
                    if name and name != "unknown":
                        # Prendre les 4 premiers caractères du nom
                        return name[:4] if len(name) > 4 else name
            
            # Fallback : 4 derniers caractères de l'ID en hex
            return f"{node_id:08x}"[-4:]
        except Exception as e:
            error_print(f"Erreur get_short_name CLI: {e}")
            return f"{node_id:08x}"[-4:]

    def _get_interface(self):
        """
        Récupérer l'interface Meshtastic partagée
        Nécessaire pour des commandes comme /echo qui ont besoin d'accéder à l'interface
        """
        try:
            if self.interface_provider is None:
                debug_print("[CLI] No interface_provider available")
                return None
                
            # Si c'est un serial_manager, get_interface() retourne l'interface connectée
            if hasattr(self.interface_provider, 'get_interface'):
                interface = self.interface_provider.get_interface()
                debug_print(f"[CLI] Got interface via get_interface(): {interface}")
                return interface
            
            # Sinon, c'est déjà l'interface directe
            debug_print(f"[CLI] Using interface_provider directly: {self.interface_provider}")
            return self.interface_provider
            
        except Exception as e:
            error_print(f"[CLI] Error getting interface: {e}")
            import traceback
            error_print(traceback.format_exc())
            return None


class CLIInterfaceWrapper:
    """
    Wrapper d'interface pour CLI qui redirige sendText vers le socket TCP
    Utilisé par UnifiedStatsCommands qui utilise l'interface directement
    """

    def __init__(self, original_interface, cli_platform, user_id):
        self.original_interface = original_interface
        self.cli_platform = cli_platform
        self.user_id = user_id

    def sendText(self, text, destinationId=None, wantAck=False, wantResponse=False, channelIndex=0):
        """Intercepter sendText et rediriger vers CLI"""
        # Envoyer au client CLI au lieu du mesh
        debug_print(f"[CLI] CLIInterfaceWrapper.sendText() called, text length: {len(text)}")
        self.cli_platform.send_message(self.user_id, text)

    def __getattr__(self, name):
        """Déléguer tous les autres attributs à l'interface originale"""
        return getattr(self.original_interface, name)

class CLIServerPlatform(MessagingPlatform):
    """
    Serveur TCP local pour clients CLI
    Écoute sur 127.0.0.1:9999 et traite les commandes des clients
    """

    def __init__(self, config, message_handler, node_manager, context_manager):
        super().__init__(config, message_handler, node_manager, context_manager)
        self.running = False
        self.server_socket = None
        self.server_thread = None
        self.client_threads = []

        # Configuration serveur
        self.host = config.extra_config.get('host', '127.0.0.1')
        self.port = config.extra_config.get('port', 9999)

        # ID utilisateur CLI (un par client potentiellement)
        self.cli_user_id = config.extra_config.get('cli_user_id', 0xC11A0001)

        # Stockage des connexions actives (pour envoyer réponses)
        self.active_connections = {}  # {user_id: socket}

    @property
    def platform_name(self) -> str:
        """Nom de la plateforme"""
        return 'cli_server'

    def start(self):
        """Démarrer le serveur TCP CLI"""
        if not self.config.enabled:
            debug_print("CLI server platform disabled")
            return

        self.running = True

        try:
            # Créer le socket serveur
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)

            # Démarrer le thread serveur
            self.server_thread = threading.Thread(target=self._server_loop, daemon=True, name="CLIServer")
            self.server_thread.start()

            info_print(f"✅ CLI Server started on {self.host}:{self.port}")
            info_print(f"📝 Connect with: python cli_client.py")

        except Exception as e:
            error_print(f"Failed to start CLI server: {e}")
            self.running = False

    def stop(self):
        """Arrêter le serveur TCP CLI"""
        self.running = False

        # Fermer toutes les connexions clients
        for user_id, conn in list(self.active_connections.items()):
            try:
                conn.close()
            except:
                pass

        # Fermer le socket serveur
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass

        info_print("CLI Server stopped")

    def send_message(self, user_id, message):
        """
        Envoyer un message à un client CLI connecté

        Args:
            user_id: ID du client (peut être l'ID CLI)
            message: Texte à envoyer
        """
        debug_print(f"[CLI] send_message() called for user {hex(user_id)}, message length: {len(message)}")
        # Trouver la connexion pour cet utilisateur
        conn = self.active_connections.get(user_id)

        if conn:
            debug_print(f"[CLI] Connection found for user {hex(user_id)}")
            try:
                # Envoyer en JSON pour parsing côté client
                response = {
                    'type': 'response',
                    'message': message
                }
                data = json.dumps(response) + '\n'
                conn.sendall(data.encode('utf-8', errors='replace'))
                debug_print(f"CLI→ Sent {len(message)} chars to {hex(user_id)}")
            except Exception as e:
                error_print(f"Failed to send to CLI client: {e}")
                # Nettoyer la connexion morte
                if user_id in self.active_connections:
                    del self.active_connections[user_id]
        else:
            error_print(f"[CLI] No connection found for user {hex(user_id)}")
            debug_print(f"[CLI] Active connections: {[hex(uid) for uid in self.active_connections.keys()]}")

    def send_alert(self, message):
        """
        Envoyer une alerte à tous les clients CLI connectés

        Args:
            message: Message d'alerte
        """
        # Envoyer à tous les clients connectés
        for user_id in list(self.active_connections.keys()):
            try:
                conn = self.active_connections[user_id]
                alert = {
                    'type': 'alert',
                    'message': f"🚨 ALERTE: {message}"
                }
                data = json.dumps(alert) + '\n'
                conn.sendall(data.encode('utf-8', errors='replace'))
                debug_print(f"CLI→ Alert sent to {hex(user_id)}")
            except Exception as e:
                error_print(f"Failed to send alert to CLI client: {e}")
                # Nettoyer la connexion morte
                if user_id in self.active_connections:
                    del self.active_connections[user_id]

    def is_enabled(self):
        """Vérifier si la plateforme est activée"""
        return self.config.enabled

    def get_user_mapping(self, platform_user_id):
        """
        Mapper l'utilisateur CLI vers un ID Mesh

        Returns:
            tuple: (mesh_id, mesh_name) ou (None, None)
        """
        mapping = self.config.user_to_mesh_mapping.get(platform_user_id)
        if mapping:
            return mapping.get('mesh_id'), mapping.get('mesh_name')
        return None, None

    def _server_loop(self):
        """
        Boucle principale du serveur
        Accepte les connexions et lance un thread par client
        """
        info_print(f"🎧 CLI Server listening on {self.host}:{self.port}")

        while self.running:
            try:
                # Timeout pour permettre l'arrêt propre
                self.server_socket.settimeout(1.0)

                # Accepter une connexion
                client_socket, address = self.server_socket.accept()

                info_print(f"📥 CLI client connected from {address}")

                # Lancer un thread pour ce client
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, address),
                    daemon=True,
                    name=f"CLIClient-{address[0]}:{address[1]}"
                )
                client_thread.start()
                self.client_threads.append(client_thread)

            except socket.timeout:
                # Normal, continue la boucle
                continue
            except Exception as e:
                if self.running:
                    error_print(f"Server accept error: {e}")

    def _handle_client(self, client_socket, address):
        """
        Gérer un client CLI connecté

        Args:
            client_socket: Socket du client
            address: Adresse du client
        """
        # Assigner un ID unique à ce client
        # Pour l'instant, on utilise un ID fixe (un seul client à la fois)
        user_id = self.cli_user_id

        # Enregistrer la connexion
        self.active_connections[user_id] = client_socket

        try:
            # Message de bienvenue
            welcome = {
                'type': 'welcome',
                'message': '🤖 Connected to MeshBot CLI\nType /help for commands, "quit" to exit'
            }
            client_socket.sendall((json.dumps(welcome) + '\n').encode('utf-8', errors='replace'))

            # Buffer pour messages incomplets
            buffer = ""

            # Boucle de réception
            while self.running:
                try:
                    # Recevoir des données
                    data = client_socket.recv(4096)

                    if not data:
                        # Connexion fermée par le client
                        break

                    # Décoder et ajouter au buffer
                    # Utiliser errors='replace' pour gérer les caractères UTF-8 invalides/surrogates
                    buffer += data.decode('utf-8', errors='replace')

                    # Traiter les lignes complètes (séparées par \n)
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()

                        if line:
                            self._process_client_command(user_id, line)

                except socket.timeout:
                    continue
                except Exception as e:
                    error_print(f"Client handler error: {e}")
                    break

        finally:
            # Nettoyer la connexion
            if user_id in self.active_connections:
                del self.active_connections[user_id]

            try:
                client_socket.close()
            except:
                pass

            info_print(f"📤 CLI client disconnected from {address}")

    def _process_client_command(self, user_id, command):
        """
        Traiter une commande reçue d'un client CLI

        Args:
            user_id: ID du client
            command: Commande texte
        """
        try:
            debug_print(f"CLI← {command}")

            # Commandes spéciales gérées côté client normalement
            # Mais au cas où...
            if command.lower() in ['quit', 'exit']:
                return

            # Traiter via le message router
            if self.message_handler and self.message_handler.router:
                router = self.message_handler.router

                # Créer un sender spécial CLI pour cet utilisateur
                # Pass router.interface so _get_interface() works for /echo command
                cli_sender = CLIMessageSender(self, user_id, interface_provider=router.interface)

                # Créer un pseudo-packet Mesh
                mesh_id, mesh_name = self.get_user_mapping(user_id)

                if not mesh_id:
                    mesh_id = user_id
                    mesh_name = "CLI User"

                # Obtenir l'ID du nœud local pour adresser correctement le message
                my_node_id = 0xFFFFFFFF  # Default broadcast
                try:
                    if hasattr(router.interface, 'get_interface'):
                        actual_interface = router.interface.get_interface()
                    else:
                        actual_interface = router.interface

                    if actual_interface and hasattr(actual_interface, 'localNode'):
                        if actual_interface.localNode:
                            my_node_id = getattr(actual_interface.localNode, 'nodeNum', 0xFFFFFFFF)
                            debug_print(f"[CLI] Local node ID: {hex(my_node_id)}")
                except Exception as e:
                    debug_print(f"[CLI] Could not get local node ID: {e}")

                packet = {
                    'from': mesh_id,
                    'to': my_node_id,  # Adresser au nœud local pour que le routeur traite
                    'decoded': {
                        'portnum': 'TEXT_MESSAGE_APP',
                        'text': command
                    },
                    'id': 0,
                    'rxTime': 0,
                    'hopLimit': 0,
                    'channel': 0,
                    'source': 'cli'  # Mark as CLI source to bypass network isolation checks
                }

                decoded = packet['decoded']

                # Créer un wrapper d'interface pour unified_stats
                cli_interface = CLIInterfaceWrapper(router.interface, self, user_id)

                # Sauvegarder les senders et interface originaux
                debug_print(f"[CLI] Saving original senders...")
                original_senders = {
                    'router': router.sender,  # Le sender du router lui-même (important pour /stats!)
                    'ai': router.ai_handler.sender,
                    'network': router.network_handler.sender,
                    'system': router.system_handler.sender,
                    'utility': router.utility_handler.sender,
                    'db': router.db_handler.sender if router.db_handler else None,
                    'mesh_traceroute': router.network_handler.mesh_traceroute.message_sender if (router.network_handler.mesh_traceroute) else None,
                }
                original_interface = router.unified_stats.interface if router.unified_stats else None

                try:
                    # Remplacer par le CLI sender
                    debug_print(f"[CLI] Swapping to CLI sender...")
                    router.sender = cli_sender  # IMPORTANT: Swap du sender du router (utilisé par /stats)
                    router.ai_handler.sender = cli_sender
                    router.network_handler.sender = cli_sender
                    router.system_handler.sender = cli_sender
                    router.utility_handler.sender = cli_sender
                    if router.db_handler:
                        router.db_handler.sender = cli_sender
                    if router.network_handler.mesh_traceroute:
                        router.network_handler.mesh_traceroute.message_sender = cli_sender
                        debug_print(f"[CLI] Swapped mesh_traceroute sender")

                    # Remplacer l'interface pour unified_stats
                    if router.unified_stats:
                        router.unified_stats.interface = cli_interface
                        debug_print(f"[CLI] Swapped unified_stats interface")

                    # Traiter la commande
                    debug_print(f"[CLI] Processing command: {command}")
                    router.process_text_message(
                        packet,
                        decoded,
                        command
                    )
                    debug_print(f"[CLI] Command processing completed")

                finally:
                    # Restaurer les senders originaux
                    debug_print(f"[CLI] Restoring original senders...")
                    router.sender = original_senders['router']  # Restaurer le sender du router
                    router.ai_handler.sender = original_senders['ai']
                    router.network_handler.sender = original_senders['network']
                    router.system_handler.sender = original_senders['system']
                    router.utility_handler.sender = original_senders['utility']
                    if router.db_handler and original_senders['db']:
                        router.db_handler.sender = original_senders['db']
                    if router.network_handler.mesh_traceroute and original_senders['mesh_traceroute']:
                        router.network_handler.mesh_traceroute.message_sender = original_senders['mesh_traceroute']

                    # Restaurer l'interface originale
                    if router.unified_stats and original_interface:
                        router.unified_stats.interface = original_interface

            else:
                error_print("Message handler not available")

        except Exception as e:
            error_print(f"Error processing CLI command: {e}")
            import traceback
            error_print(traceback.format_exc())
