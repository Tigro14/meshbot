#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wrapper sécurisé pour les connexions TCP Meshtastic
Garantit la fermeture propre et évite les fuites de threads
"""

import time
import threading
import meshtastic.tcp_interface
from contextlib import contextmanager
from utils import debug_print, error_print, info_print

class SafeTCPConnection:
    """
    Wrapper thread-safe pour TCPInterface avec fermeture garantie
    """
    _lock = threading.Lock()
    _active_connections = []
    
    @classmethod
    @contextmanager
    def connect(cls, hostname, port=4403, timeout=30):
        """
        Context manager pour connexion TCP sécurisée
        
        Usage:
            with SafeTCPConnection.connect(REMOTE_NODE_HOST) as interface:
                interface.sendText("Hello")
        """
        interface = None
        start_time = time.time()
        
        try:
            debug_print(f"🔌 Ouverture connexion TCP sécurisée vers {hostname}:{port}")
            
            # Créer la connexion
            interface = meshtastic.tcp_interface.TCPInterface(
                hostname=hostname,
                portNumber=port
            )
            
            # Ajouter à la liste des connexions actives
            with cls._lock:
                cls._active_connections.append(interface)
            
            # Attendre que la connexion soit établie
            time.sleep(2)
            
            # Vérifier timeout
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Connexion TCP timeout après {timeout}s")
            
            yield interface
            
        except Exception as e:
            error_print(f"❌ Erreur connexion TCP {hostname}:{port} - {e}")
            return None
            
        finally:
            # CRITIQUE : Fermeture garantie
            if interface:
                try:
                    debug_print(f"🔌 Fermeture connexion TCP {hostname}:{port}")
                    
                    # Forcer l'arrêt du thread de lecture
                    if hasattr(interface, '_reader_thread'):
                        interface._reader_thread.stop()
                    
                    # Fermer la connexion
                    interface.close()
                    
                    # Retirer de la liste
                    with cls._lock:
                        if interface in cls._active_connections:
                            cls._active_connections.remove(interface)
                    
                    # Petit délai pour laisser le thread se terminer
                    time.sleep(0.5)
                    
                except Exception as e:
                    error_print(f"⚠️ Erreur fermeture TCP: {e}")
    
    @classmethod
    def cleanup_all(cls):
        """
        Fermer toutes les connexions actives (appelé à l'arrêt du bot)
        """
        with cls._lock:
            for interface in cls._active_connections[:]:
                try:
                    interface.close()
                except Exception as e:
                    pass
            cls._active_connections.clear()
        info_print("✅ Toutes les connexions TCP fermées")
    
    @classmethod
    def get_active_count(cls):
        """Nombre de connexions actives"""
        with cls._lock:
            return len(cls._active_connections)


def send_text_to_remote(hostname, message, port=4403):
    """
    Helper pour envoyer un texte simple via TCP
    
    Args:
        hostname: IP du nœud distant
        message: Texte à envoyer
        port: Port TCP (défaut 4403)
    
    Returns:
        bool: True si succès
    """
    try:
        with SafeTCPConnection.connect(hostname, port) as interface:
            interface.sendText(message)
            time.sleep(2)  # Laisser le temps d'envoyer
            return True
    except Exception as e:
        error_print(f"Erreur envoi TCP: {e}")
        return False


def get_remote_config(hostname, port=4403):
    """
    Helper pour récupérer la config d'un nœud distant
    
    Args:
        hostname: IP du nœud distant
        port: Port TCP (défaut 4403)
    
    Returns:
        dict: Configuration ou None si erreur
    """
    try:
        with SafeTCPConnection.connect(hostname, port) as interface:
            time.sleep(2)
            
            if hasattr(interface, 'localNode'):
                return {
                    'shortName': getattr(interface.localNode, 'shortName', 'Unknown'),
                    'nodeNum': getattr(interface.localNode, 'nodeNum', 0),
                    'nodes_count': len(interface.nodes) if hasattr(interface, 'nodes') else 0
                }
            return None
            
    except Exception as e:
        error_print(f"Erreur récupération config: {e}")
        return None
