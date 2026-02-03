#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Context manager pour gérer proprement les connexions TCP Meshtastic

PURPOSE:
    Provides a context manager wrapper around OptimizedTCPInterface for
    TEMPORARY connections to Meshtastic nodes (port 4403 only).
    
    This is NOT for HTTP/MQTT services - those use their own libraries:
    - ESPHome: requests library (esphome_client.py)
    - Weather: curl subprocess (utils_weather.py)
    - Blitzortung: paho-mqtt library (blitz_monitor.py)

RELATIONSHIP TO tcp_interface_patch.py:
    SafeTCPConnection uses OptimizedTCPInterface internally.
    
    - OptimizedTCPInterface: Low-level CPU-optimized Meshtastic TCP
    - SafeTCPConnection: High-level context manager for temporary queries

ARCHITECTURE:
    See TCP_ARCHITECTURE.md for full documentation on the network stack design.

    For LONG-LIVED connections (main bot interface):
        Use OptimizedTCPInterface directly in main_bot.py
        
    For SHORT-LIVED connections (queries, one-off commands):
        Use SafeTCPConnection context manager (this module)

Ce module fournit:
1. SafeTCPConnection: Context manager pour gérer les connexions TCP
2. send_text_to_remote(): Fonction simple pour envoyer un message
3. quick_tcp_command(): Fonction pour envoyer une commande rapide
4. broadcast_message(): Fonction pour diffuser un message sur le réseau

Exemples d'utilisation:
    # Avec context manager (pour usage avancé)
    with SafeTCPConnection("192.168.1.100") as interface:
        interface.sendText("Hello!")
    
    # Avec fonction helper (recommandé pour messages simples)
    success, msg = send_text_to_remote("192.168.1.100", "Hello!")
    
    # Commande rapide (pour commandes système)
    success, msg = quick_tcp_command("192.168.1.100", "/reboot")
    
    # Broadcast sur le réseau
    success, msg = broadcast_message("192.168.1.100", "Alert: system update")
"""

import time
import meshtastic.tcp_interface
from tcp_interface_patch import OptimizedTCPInterface  # ✅ PATCH CPU
from utils import debug_print, error_print, info_print, debug_print_mt, info_print_mt


class SafeTCPConnection:
    """
    Context manager pour les connexions TCP Meshtastic
    
    Gère automatiquement:
    - L'ouverture de la connexion
    - Le délai d'attente pour la stabilisation
    - La fermeture propre même en cas d'erreur
    - Le tracking du temps de connexion
    
    Args:
        hostname (str): Adresse IP ou hostname du nœud
        port (int): Port TCP (défaut: 4403)
        wait_time (int): Temps d'attente après connexion en secondes (défaut: 2)
        timeout (int): Timeout de connexion en secondes (défaut: 10)
    
    Example:
        with SafeTCPConnection("192.168.1.100", wait_time=3) as interface:
            interface.sendText("Hello World!")
            # Connexion fermée automatiquement à la fin du with
    """
    
    def __init__(self, hostname, port=4403, wait_time=2, timeout=10):
        self.hostname = hostname
        self.port = port
        self.wait_time = wait_time
        self.timeout = timeout
        self.interface = None
        self._start_time = None
        
    def __enter__(self):
        """
        Ouvrir la connexion TCP
        
        Returns:
            TCPInterface: Interface Meshtastic connectée
            
        Raises:
            Exception: Si la connexion échoue
        """
        try:
            self._start_time = time.time()
            debug_print_mt(f"🔌 Connexion TCP à {self.hostname}:{self.port}")
            
            self.interface = OptimizedTCPInterface(
                hostname=self.hostname,
                portNumber=self.port
            )
            
            if self.wait_time > 0:
                debug_print_mt(f"⏱️  Attente {self.wait_time}s...")
                time.sleep(self.wait_time)
            
            elapsed = time.time() - self._start_time
            debug_print_mt(f"✅ Connexion établie en {elapsed:.2f}s")
            
            return self.interface
            
        except Exception as e:
            error_print(f"❌ Erreur connexion TCP {self.hostname}: {e}")
            self.interface = None
            raise
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Fermer proprement la connexion
        
        Args:
            exc_type: Type d'exception si levée
            exc_val: Valeur de l'exception si levée
            exc_tb: Traceback de l'exception si levée
            
        Returns:
            bool: False pour propager les exceptions
        """
        if self.interface:
            try:
                elapsed = time.time() - self._start_time if self._start_time else 0
                debug_print_mt(f"🔌 Fermeture connexion (durée: {elapsed:.2f}s)")
                self.interface.close()
                debug_print_mt(f"✅ Connexion fermée")
            except Exception as e:
                error_print(f"⚠️  Erreur fermeture: {e}")
            finally:
                self.interface = None
        
        return False  # Ne pas supprimer les exceptions


# ========================================
# FONCTIONS HELPER NIVEAU MODULE
# ========================================

def send_text_to_remote(hostname, text, port=4403, wait_time=10):
    """
    Envoyer un texte via TCP à un nœud distant (fonction simplifiée)
    
    Cette fonction gère automatiquement la connexion et la déconnexion.
    Recommandée pour l'envoi de messages simples.
    
    Args:
        hostname (str): IP du nœud distant
        text (str): Texte à envoyer
        port (int): Port TCP (défaut: 4403)
        wait_time (int): Temps d'attente après envoi en secondes (défaut: 10)
    
    Returns:
        tuple: (success: bool, message: str)
            - success: True si envoi réussi, False sinon
            - message: Message de confirmation ou d'erreur
    
    Example:
        success, msg = send_text_to_remote("192.168.1.100", "Hello!")
        if success:
            print(f"Message envoyé: {msg}")
        else:
            print(f"Erreur: {msg}")
    """
    try:
        debug_print_mt(f"📤 send_text_to_remote: {hostname} <- '{text}'")
        
        with SafeTCPConnection(hostname, port, wait_time=2, timeout=15) as interface:
            debug_print_mt(f"✅ Connexion établie")
            debug_print_mt(f"📤 Envoi texte: '{text}'")
            
            interface.sendText(text)
            debug_print_mt(f"✅ sendText() appelé")
            
            # Attendre que le message parte
            debug_print_mt(f"⏳ Attente {wait_time}s pour transmission...")
            time.sleep(wait_time)
            
            info_print(f"✅ Texte envoyé à {hostname}")
            return True, "✅ Message envoyé"
            
    except Exception as e:
        error_print(f"❌ Erreur envoi texte à {hostname}: {e}")
        import traceback
        error_print(traceback.format_exc())
        return False, f"❌ Erreur: {str(e)[:100]}"


def quick_tcp_command(hostname, command, port=4403, wait_time=3):
    """
    Envoyer une commande rapide via TCP (optimisé pour les commandes système)
    
    Version optimisée avec temps d'attente réduit, idéale pour les commandes
    système comme /reboot, /shutdown, etc.
    
    Args:
        hostname (str): IP du nœud distant
        command (str): Commande texte à envoyer (ex: "/reboot")
        port (int): Port TCP (défaut: 4403)
        wait_time (int): Temps d'attente après envoi en secondes (défaut: 3)
        
    Returns:
        tuple: (success: bool, message: str)
            - success: True si envoi réussi, False sinon
            - message: Message de confirmation ou d'erreur
    
    Example:
        success, msg = quick_tcp_command("192.168.1.100", "/reboot")
        if success:
            print("Reboot lancé")
    """
    try:
        debug_print_mt(f"⚡ quick_tcp_command: {hostname} <- '{command}'")
        
        with SafeTCPConnection(hostname, port, wait_time=2) as interface:
            interface.sendText(command)
            info_print(f"✅ Commande '{command}' envoyée à {hostname}")
            
            time.sleep(wait_time)
            
            return True, f"✅ Commande envoyée"
            
    except Exception as e:
        error_print(f"❌ Erreur envoi commande à {hostname}: {e}")
        import traceback
        error_print(traceback.format_exc())
        return False, f"❌ Erreur: {str(e)[:100]}"


def broadcast_message(hostname, message, port=4403, wait_time=3):
    """
    Diffuser un message sur le réseau via un nœud distant
    
    Envoie un message qui sera diffusé à tous les nœuds du réseau mesh.
    Identique à send_text_to_remote mais avec sémantique de broadcast.
    
    Args:
        hostname (str): IP du nœud qui diffusera le message
        message (str): Message à diffuser sur le réseau
        port (int): Port TCP (défaut: 4403)
        wait_time (int): Temps d'attente pour la propagation (défaut: 3)
        
    Returns:
        tuple: (success: bool, message: str)
    
    Example:
        success, msg = broadcast_message("192.168.1.100", "Alert: maintenance")
    """
    try:
        debug_print_mt(f"📡 broadcast_message: via {hostname} -> réseau")
        
        with SafeTCPConnection(hostname, port, wait_time=2) as interface:
            interface.sendText(message)
            info_print(f"📡 Message diffusé via {hostname}")
            
            # Attendre propagation sur le réseau
            time.sleep(wait_time)
            
            return True, "✅ Message diffusé"
            
    except Exception as e:
        error_print(f"❌ Erreur broadcast via {hostname}: {e}")
        import traceback
        error_print(traceback.format_exc())
        return False, f"❌ Erreur: {str(e)[:100]}"


# ========================================
# FONCTION DE TEST
# ========================================

def test_connection(hostname, port=4403):
    """
    Tester la connexion à un nœud distant
    
    Args:
        hostname (str): IP du nœud à tester
        port (int): Port TCP (défaut: 4403)
    
    Returns:
        tuple: (success: bool, message: str, elapsed_time: float)
    """
    try:
        start = time.time()
        with SafeTCPConnection(hostname, port, wait_time=1) as interface:
            elapsed = time.time() - start
            return True, f"✅ Connexion OK ({elapsed:.2f}s)", elapsed
    except Exception as e:
        elapsed = time.time() - start
        return False, f"❌ Échec: {str(e)[:100]}", elapsed


if __name__ == "__main__":
    """Tests rapides du module"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python safe_tcp_connection.py <hostname> [message]")
        print("Exemple: python safe_tcp_connection.py 192.168.1.100 'Hello'")
        sys.exit(1)
    
    hostname = sys.argv[1]
    message = sys.argv[2] if len(sys.argv) > 2 else "Test message"
    
    print(f"\n🧪 Test de connexion à {hostname}...")
    success, msg, elapsed = test_connection(hostname)
    print(f"Résultat: {msg}\n")
    
    if success:
        print(f"📤 Envoi de message: '{message}'")
        success, msg = send_text_to_remote(hostname, message)
        print(f"Résultat: {msg}")
