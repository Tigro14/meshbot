#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Plateforme CLI locale pour interaction directe avec le bot
Permet de tester et débugger sans dépendre de Telegram
"""

import sys
import threading
from .platform_interface import MessagingPlatform
from utils import info_print, debug_print, error_print

class CLIPlatform(MessagingPlatform):
    """
    Plateforme en ligne de commande locale
    Permet d'interagir avec le bot via stdin/stdout
    """

    def __init__(self, config, message_handler, node_manager, context_manager):
        super().__init__(config, message_handler, node_manager, context_manager)
        self.running = False
        self.input_thread = None

        # ID utilisateur fictif pour la CLI (configurable)
        self.cli_user_id = config.extra_config.get('cli_user_id', 0xC11A0001)  # CLI = C11
        self.cli_username = config.extra_config.get('cli_username', 'CLI User')

    def start(self):
        """Démarrer la plateforme CLI"""
        if not self.config.enabled:
            debug_print("CLI platform disabled")
            return

        self.running = True

        # Démarrer le thread d'input
        self.input_thread = threading.Thread(target=self._input_loop, daemon=True)
        self.input_thread.start()

        info_print("✅ CLI Platform started")
        info_print("━" * 60)
        info_print("🖥️  CLI LOCALE ACTIVÉE")
        info_print("━" * 60)
        info_print("Tapez vos commandes directement (ex: /help, /bot bonjour)")
        info_print("Tapez 'quit' ou Ctrl+C pour sortir")
        info_print("━" * 60)

    def stop(self):
        """Arrêter la plateforme CLI"""
        self.running = False
        info_print("CLI Platform stopped")

    def send_message(self, user_id, message):
        """
        Envoyer un message à l'utilisateur CLI
        Affiche simplement sur stdout
        """
        # Pour la CLI, on affiche juste sur stdout
        # Formater avec un préfixe pour distinguer des logs
        print("\n" + "─" * 60)
        print("🤖 Bot:")
        print(message)
        print("─" * 60)
        print("\n> ", end='', flush=True)

    def is_enabled(self):
        """Vérifier si la plateforme est activée"""
        return self.config.enabled

    def get_user_mapping(self, platform_user_id):
        """
        Mapper l'utilisateur CLI vers un ID Mesh

        Returns:
            tuple: (mesh_id, mesh_name) ou (None, None)
        """
        # Pour la CLI, utiliser le mapping configuré
        mapping = self.config.user_to_mesh_mapping.get(platform_user_id)
        if mapping:
            return mapping.get('mesh_id'), mapping.get('mesh_name')
        return None, None

    def _input_loop(self):
        """
        Boucle d'input pour lire les commandes depuis stdin
        Tourne dans un thread séparé
        """
        while self.running:
            try:
                # Prompt
                print("> ", end='', flush=True)

                # Lire la ligne
                user_input = input().strip()

                if not user_input:
                    continue

                # Commandes spéciales CLI
                if user_input.lower() in ['quit', 'exit', 'q']:
                    info_print("Sortie de la CLI (bot continue de tourner)")
                    self.running = False
                    break

                if user_input.lower() == 'clear':
                    # Clear screen
                    print("\033[2J\033[H")
                    continue

                # Simuler un message Mesh entrant
                self._process_cli_message(user_input)

            except EOFError:
                # Fin de l'input (ex: Ctrl+D)
                self.running = False
                break
            except KeyboardInterrupt:
                # Ctrl+C
                print("\n")
                info_print("CLI interrompue (bot continue)")
                self.running = False
                break
            except Exception as e:
                error_print(f"Erreur CLI input: {e}")

    def _process_cli_message(self, message):
        """
        Traiter un message CLI comme s'il venait du mesh

        Args:
            message: Texte entré par l'utilisateur
        """
        try:
            # Créer un pseudo-packet Mesh
            # Structure minimale pour compatibilité avec message_handler

            # Obtenir le mapping mesh si configuré
            mesh_id, mesh_name = self.get_user_mapping(self.cli_user_id)

            if not mesh_id:
                # Fallback: utiliser l'ID CLI directement
                mesh_id = self.cli_user_id
                mesh_name = self.cli_username

            packet = {
                'from': mesh_id,
                'to': 0xFFFFFFFF,  # Broadcast
                'decoded': {
                    'portnum': 'TEXT_MESSAGE_APP',
                    'text': message
                },
                'id': 0,  # Pas important pour la CLI
                'rxTime': 0,
                'hopLimit': 0,  # Direct
                'channel': 0
            }

            decoded = packet['decoded']

            # Utiliser le message_handler pour traiter
            if self.message_handler and self.message_handler.router:
                debug_print(f"CLI→ {message}")
                self.message_handler.router.process_text_message(
                    packet,
                    decoded,
                    message
                )
            else:
                error_print("Message handler non disponible")

        except Exception as e:
            error_print(f"Erreur traitement message CLI: {e}")
            import traceback
            error_print(traceback.format_exc())

    def broadcast_to_mesh(self, message):
        """
        Envoyer un message de la CLI vers le mesh
        (Fonctionnalité optionnelle pour envoyer des messages au réseau)

        Args:
            message: Texte à envoyer
        """
        # TODO: Implémenter si nécessaire
        # Permettrait de faire : "> @mesh Hello everyone"
        # Et envoyer vraiment sur le réseau Meshtastic
        pass
