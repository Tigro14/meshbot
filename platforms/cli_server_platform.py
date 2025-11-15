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
            self.server_thread = threading.Thread(target=self._server_loop, daemon=True)
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
        # Trouver la connexion pour cet utilisateur
        conn = self.active_connections.get(user_id)

        if conn:
            try:
                # Envoyer en JSON pour parsing côté client
                response = {
                    'type': 'response',
                    'message': message
                }
                data = json.dumps(response) + '\n'
                conn.sendall(data.encode('utf-8'))
                debug_print(f"CLI→ Sent {len(message)} chars to {hex(user_id)}")
            except Exception as e:
                error_print(f"Failed to send to CLI client: {e}")
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
                    daemon=True
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
            client_socket.sendall((json.dumps(welcome) + '\n').encode('utf-8'))

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
                    buffer += data.decode('utf-8')

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

            # Créer un pseudo-packet Mesh
            mesh_id, mesh_name = self.get_user_mapping(user_id)

            if not mesh_id:
                mesh_id = user_id
                mesh_name = "CLI User"

            packet = {
                'from': mesh_id,
                'to': 0xFFFFFFFF,  # Broadcast
                'decoded': {
                    'portnum': 'TEXT_MESSAGE_APP',
                    'text': command
                },
                'id': 0,
                'rxTime': 0,
                'hopLimit': 0,
                'channel': 0
            }

            decoded = packet['decoded']

            # Traiter via le message router
            if self.message_handler and self.message_handler.router:
                self.message_handler.router.process_text_message(
                    packet,
                    decoded,
                    command
                )
            else:
                error_print("Message handler not available")

        except Exception as e:
            error_print(f"Error processing CLI command: {e}")
            import traceback
            error_print(traceback.format_exc())
