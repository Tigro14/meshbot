#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Context manager pour gérer proprement les connexions TCP Meshtastic
"""

import time
import meshtastic.tcp_interface
from utils import debug_print, error_print


class SafeTCPConnection:
    """Context manager pour les connexions TCP Meshtastic"""
    
    def __init__(self, hostname, port=4403, wait_time=2, timeout=10):
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
            
            if self.wait_time > 0:
                debug_print(f"⏱️  Attente {self.wait_time}s...")
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
                debug_print(f"🔌 Fermeture connexion (durée: {elapsed:.2f}s)")
                self.interface.close()
                debug_print(f"✅ Connexion fermée")
            except Exception as e:
                error_print(f"⚠️  Erreur fermeture: {e}")
            finally:
                self.interface = None
        
        return False


# ✅ FONCTION HELPER AU NIVEAU MODULE - FACILE À IMPORTER
def send_text_to_remote(hostname, text, port=4403, wait_time=10):
    """
    Envoyer un texte via TCP à un nœud distant
    
    Args:
        hostname: IP du nœud
        text: Texte à envoyer
        port: Port TCP (défaut: 4403)
        wait_time: Temps d'attente après envoi (défaut: 10s)
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        debug_print(f"🔌 Connexion à {hostname}:{port}...")
        
        with SafeTCPConnection(hostname, port, wait_time=wait_time, timeout=15) as interface:
            debug_print(f"✅ Connexion établie")
            debug_print(f"📤 Envoi texte: '{text}'")
            
            interface.sendText(text)
            debug_print(f"✅ sendText() appelé")
            
            # Attendre que le message parte
            debug_print(f"⏳ Attente 5s pour transmission...")
            time.sleep(5)
            
            debug_print(f"✅ Texte envoyé à {hostname}")
            return True, "✅ Message envoyé"
            
    except Exception as e:
        error_print(f"❌ Erreur envoi texte à {hostname}: {e}")
        import traceback
        error_print(traceback.format_exc())
        return False, f"❌ Erreur: {str(e)[:50]}"


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
            
            time.sleep(wait_time)
            
            return True, f"✅ Commande envoyée"
            
    except Exception as e:
        error_print(f"❌ Erreur envoi commande: {e}")
        return False, f"❌ Erreur: {str(e)[:50]}"

