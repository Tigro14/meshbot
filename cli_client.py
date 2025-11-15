#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Client CLI pour se connecter au serveur MeshBot
Usage: python cli_client.py [--host HOST] [--port PORT]
"""

import socket
import sys
import threading
import json
import argparse

class CLIClient:
    """Client CLI qui se connecte au serveur MeshBot"""

    def __init__(self, host='127.0.0.1', port=9999):
        self.host = host
        self.port = port
        self.socket = None
        self.running = False
        self.receive_thread = None

    def connect(self):
        """Se connecter au serveur MeshBot"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.running = True

            # Démarrer le thread de réception
            self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receive_thread.start()

            return True

        except ConnectionRefusedError:
            print(f"❌ Could not connect to MeshBot server at {self.host}:{self.port}")
            print("   Make sure the bot is running with CLI_ENABLED = True")
            return False
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False

    def disconnect(self):
        """Se déconnecter du serveur"""
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass

    def send_command(self, command):
        """
        Envoyer une commande au serveur

        Args:
            command: Commande texte
        """
        if not self.socket:
            return False

        try:
            # Envoyer avec newline
            self.socket.sendall((command + '\n').encode('utf-8'))
            return True
        except Exception as e:
            print(f"❌ Send error: {e}")
            return False

    def _receive_loop(self):
        """
        Boucle de réception des réponses du serveur
        Tourne dans un thread séparé
        """
        buffer = ""

        while self.running:
            try:
                data = self.socket.recv(4096)

                if not data:
                    # Connexion fermée
                    print("\n❌ Connection closed by server")
                    self.running = False
                    break

                # Décoder et ajouter au buffer
                buffer += data.decode('utf-8')

                # Traiter les messages complets (JSON séparés par \n)
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)

                    if line.strip():
                        self._handle_message(line.strip())

            except Exception as e:
                if self.running:
                    print(f"\n❌ Receive error: {e}")
                break

    def _handle_message(self, message_str):
        """
        Traiter un message reçu du serveur

        Args:
            message_str: Message JSON en string
        """
        try:
            message = json.loads(message_str)

            msg_type = message.get('type', 'unknown')
            content = message.get('message', '')

            if msg_type == 'welcome':
                # Message de bienvenue
                print(content)
                print("─" * 60)

            elif msg_type == 'response':
                # Réponse à une commande
                print("\n" + "─" * 60)
                print("🤖 Bot:")
                print(content)
                print("─" * 60)

            else:
                # Message inconnu, afficher tel quel
                print(f"\n[{msg_type}] {content}")

            # Re-afficher le prompt
            print("\n> ", end='', flush=True)

        except json.JSONDecodeError:
            # Pas du JSON, afficher tel quel
            print(f"\n{message_str}")
            print("\n> ", end='', flush=True)
        except Exception as e:
            print(f"\n⚠️ Message handling error: {e}")

    def interactive_loop(self):
        """
        Boucle interactive de saisie utilisateur
        """
        print("\n━" * 60)
        print("🖥️  MeshBot CLI Client")
        print("━" * 60)
        print("Connected to bot. Type commands or 'quit' to exit.")
        print("━" * 60)

        try:
            while self.running:
                try:
                    # Prompt
                    user_input = input("\n> ").strip()

                    if not user_input:
                        continue

                    # Commandes locales
                    if user_input.lower() in ['quit', 'exit', 'q']:
                        print("👋 Disconnecting...")
                        break

                    if user_input.lower() == 'clear':
                        # Clear screen
                        print("\033[2J\033[H")
                        continue

                    # Envoyer au serveur
                    if not self.send_command(user_input):
                        print("❌ Failed to send command")
                        break

                except EOFError:
                    # Ctrl+D
                    print("\n👋 Disconnecting...")
                    break

                except KeyboardInterrupt:
                    # Ctrl+C
                    print("\n👋 Disconnecting...")
                    break

        finally:
            self.disconnect()


def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(description='MeshBot CLI Client')
    parser.add_argument('--host', default='127.0.0.1', help='Server host (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=9999, help='Server port (default: 9999)')

    args = parser.parse_args()

    # Créer le client
    client = CLIClient(host=args.host, port=args.port)

    # Se connecter
    if not client.connect():
        sys.exit(1)

    # Boucle interactive
    try:
        client.interactive_loop()
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
