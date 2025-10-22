#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Context manager pour gérer proprement les connexions TCP Meshtastic
Évite les fuites de CPU causées par _readBytes en boucle
"""

import time
import meshtastic.tcp_interface
from utils import debug_print, error_print


class SafeTCPConnection:
    """
    Context manager pour les connexions TCP Meshtastic
    
    Usage:
        with SafeTCPConnection(host, port, wait_time=2) as interface:
            interface.sendText("message")
            nodes = interface.nodes
    """
    
    def __init__(self, hostname, port=4403, wait_time=2, timeout=10):
        """
        Args:
            hostname: IP du nœud distant
            port: Port TCP (défaut: 4403)
            wait_time: Temps d'attente après connexion (défaut: 2s)
            timeout: Timeout global de la connexion (défaut: 10s)
        """
        self.hostname = hostname
        self.port = port
        self.wait_time = wait_time
        self.timeout = timeout
        self.interface = None
        self._start_time = None
        
    def __enter__(self):
        """Ouvrir la connexion"""
        try:
            self._start_time = time.time()
            debug_print(f"🔌 Connexion TCP à {self.hostname}:{self.port}")
            
            self.interface = meshtastic.tcp_interface.TCPInterface(
                hostname=self.hostname,
                portNumber=self.port
            )
            
            # Attendre que les données se chargent
            if self.wait_time > 0:
                debug_print(f"⏱️  Attente {self.wait_time}s pour chargement des données...")
                time.sleep(self.wait_time)
            
            elapsed = time.time() - self._start_time
            debug_print(f"✅ Connexion établie en {elapsed:.2f}s")
            
            return self.interface
            
        except Exception as e:
            error_print(f"❌ Erreur connexion TCP {self.hostname}: {e}")
            self.interface = None
            raise
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Fermer proprement la connexion"""
        if self.interface:
            try:
                elapsed = time.time() - self._start_time if self._start_time else 0
                debug_print(f"🔌 Fermeture connexion TCP {self.hostname} (durée: {elapsed:.2f}s)")
                self.interface.close()
                debug_print(f"✅ Connexion fermée proprement")
            except Exception as e:
                error_print(f"⚠️  Erreur fermeture connexion: {e}")
            finally:
                self.interface = None
        
        # Ne pas supprimer l'exception si elle existe
        return False


    def quick_tcp_command(hostname, command, port=4403, wait_time=3):
        """
        Helper pour envoyer une commande rapide via TCP
        
        Args:
            hostname: IP du nœud
            command: Commande texte à envoyer
            port: Port TCP
            wait_time: Temps d'attente après envoi
            
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            with SafeTCPConnection(hostname, port, wait_time=2) as interface:
                interface.sendText(command)
                debug_print(f"✅ Commande '{command}' envoyée à {hostname}")
                
                # Attendre que le message parte
                time.sleep(wait_time)
                
                return True, f"✅ Commande envoyée"
                
        except Exception as e:
            error_print(f"❌ Erreur envoi commande: {e}")
            return False, f"❌ Erreur: {str(e)[:50]}"

    @staticmethod
    def send_text_to_remote(hostname, text, port=4403, wait_time=2):
        """
        Envoyer un texte via TCP à un nœud distant

        Args:
            hostname: IP du nœud
            text: Texte à envoyer
            port: Port TCP (défaut: 4403)
            wait_time: Temps d'attente après envoi

        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            with SafeTCPConnection(hostname, port, wait_time=wait_time, timeout=15) as interface:
                interface.sendText(text)
                debug_print(f"✅ Texte envoyé à {hostname}: {text}")
                return True, "✅ Message envoyé"
        except Exception as e:
            error_print(f"❌ Erreur envoi texte: {e}")
            return False, f"❌ Erreur: {str(e)[:50]}"


    # Exemple d'utilisation
    if __name__ == "__main__":
        # Test basique
        try:
            with SafeTCPConnection("192.168.1.100") as interface:
                print(f"Nœuds connectés: {len(interface.nodes)}")
                interface.sendText("Test message")
        except Exception as e:
            print(f"Erreur: {e}")
