#!/usr/bin/env python3
"""
Fonctions utilitaires pour le bot Meshtastic
"""

import sys
import time
from datetime import datetime
from config import DEBUG_MODE

def lazy_import_requests():
    """Import requests seulement quand nécessaire"""
    global requests
    if 'requests' not in globals():
        import requests
    return requests

def lazy_import_re():
    """Import re seulement quand nécessaire"""
    global re
    if 're' not in globals():
        import re
    return re

def debug_print(message, source=None):
    """
    Affiche seulement en mode debug
    
    Args:
        message: Message à afficher
        source: Source optionnelle ('MC' pour MeshCore, 'MT' pour Meshtastic)
    """
    if DEBUG_MODE:
        if source:
            print(f"[DEBUG][{source}] {message}", file=sys.stderr, flush=True)
        else:
            print(f"[DEBUG] {message}", file=sys.stderr, flush=True)

def info_print(message, source=None):
    """
    Affiche toujours (logs importants)
    
    Args:
        message: Message à afficher
        source: Source optionnelle ('MC' pour MeshCore, 'MT' pour Meshtastic)
    """
    if source:
        print(f"[INFO][{source}] {message}", flush=True)
    else:
        print(f"[INFO] {message}", flush=True)

# Convenience functions for MeshCore logs
def debug_print_mc(message):
    """Affiche un message debug MeshCore [DEBUG][MC]"""
    debug_print(message, source='MC')

def info_print_mc(message):
    """Affiche un message info MeshCore [INFO][MC]"""
    info_print(message, source='MC')

# Convenience functions for Meshtastic logs
def debug_print_mt(message):
    """Affiche un message debug Meshtastic [DEBUG][MT]"""
    debug_print(message, source='MT')

def info_print_mt(message):
    """Affiche un message info Meshtastic [INFO][MT]"""
    info_print(message, source='MT')

def conversation_print(message):
    """Log spécial pour les conversations"""
    print(f"[CONVERSATION] {message}", flush=True)

def error_print(message):
    """Affiche un message d'erreur avec horodatage et traceback"""
    import sys
    import traceback
    
    timestamp = time.strftime("%H:%M:%S")
    
    # ✅ CAPTURE COMPLÈTE si message est None
    if message is None or str(message) == "None":
        print(f"[ERROR] {timestamp} - NoneType: None", flush=True)
        print(f"[ERROR] ⚠️  STACK TRACE (qui a appelé error_print avec None):", flush=True)
        
        # Afficher toute la pile d'appels
        stack = traceback.extract_stack()[:-1]  # Exclure cette fonction
        for frame in stack:
            print(f"[ERROR]   Fichier: {frame.filename}:{frame.lineno}", flush=True)
            print(f"[ERROR]     dans {frame.name}", flush=True)
            print(f"[ERROR]     >> {frame.line}", flush=True)
        return
    
    print(f"[ERROR] {timestamp} - {message}", flush=True)
    
    # Si on est dans un contexte d'exception, afficher le traceback
    if sys.exc_info()[0] is not None:
        print("[ERROR] Traceback complet:", flush=True)
        traceback.print_exc()

def format_timestamp():
    """Format timestamp pour l'affichage"""
    return datetime.now().strftime("%H:%M:%S")

def format_elapsed_time(timestamp):
    """Formater le temps écoulé depuis un timestamp"""
    if timestamp <= 0:
        return "n/a"
    
    elapsed = int(time.time() - timestamp)
    if elapsed < 60:
        return f"{elapsed}s"
    elif elapsed < 3600:
        return f"{elapsed//60}m"
    elif elapsed < 86400:
        return f"{elapsed//3600}h"
    else:
        return f"{elapsed//86400}j"

def get_signal_quality_icon(snr):
    """Retourne l'icône de qualité basée UNIQUEMENT sur le SNR"""
    if snr >= 10:
        return "🟢"  # Excellent SNR
    elif snr >= 5:
        return "🟡"  # Bon SNR
    elif snr >= 0:
        return "🟠"  # SNR faible mais positif
    elif snr >= -5:
        return "🔴"  # SNR négatif mais décodable
    elif snr < -5 and snr != 0:
        return "⚫"   # SNR très négatif
    else:
        return "📶"  # Par défaut (pas de données)

def get_snr_quality_description(snr):
    """Description textuelle de la qualité basée sur SNR"""
    if snr >= 10:
        return "Excellente"
    elif snr >= 5:
        return "Très bonne"
    elif snr >= 0:
        return "Bonne"
    elif snr >= -5:
        return "Correcte"
    elif snr >= -10:
        return "Faible"
    elif snr < -10 and snr != 0:
        return "Très faible"
    else:
        return "Inconnue"

def estimate_distance_from_snr(snr):
    """Estimation approximative de distance basée UNIQUEMENT sur SNR (LoRa)"""
    # Basé sur des observations terrain LoRa - SNR vs distance
    if snr >= 10:
        return "<500m"
    elif snr >= 5:
        return "500m-2km"
    elif snr >= 0:
        return "2-5km"
    elif snr >= -5:
        return "5-15km"
    elif snr >= -10:
        return "15-25km"
    elif snr < -10 and snr != 0:
        return ">25km"
    else:
        return "?"

def truncate_text(text, max_length, suffix="..."):
    """Tronquer un texte si trop long"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix

def is_emoji(char):
    """
    Check if a character is an emoji.
    Covers common emoji Unicode ranges.
    
    Args:
        char: A single character to check
        
    Returns:
        bool: True if the character is an emoji, False otherwise
    """
    try:
        code = ord(char)
    except (TypeError, ValueError):
        # Handle invalid input (not a single character or surrogate pairs)
        return False
    
    return (
        0x1F600 <= code <= 0x1F64F or  # Emoticons
        0x1F300 <= code <= 0x1F5FF or  # Symbols & Pictographs
        0x1F680 <= code <= 0x1F6FF or  # Transport & Map
        0x1F700 <= code <= 0x1F77F or  # Alchemical Symbols
        0x1F780 <= code <= 0x1F7FF or  # Geometric Shapes Extended
        0x1F800 <= code <= 0x1F8FF or  # Supplemental Arrows-C
        0x1F900 <= code <= 0x1F9FF or  # Supplemental Symbols and Pictographs
        0x1FA00 <= code <= 0x1FA6F or  # Chess Symbols
        0x1FA70 <= code <= 0x1FAFF or  # Symbols and Pictographs Extended-A
        0x2600 <= code <= 0x26FF or    # Miscellaneous Symbols
        0x2700 <= code <= 0x27BF or    # Dingbats
        0xFE00 <= code <= 0xFE0F or    # Variation Selectors
        0x1F1E6 <= code <= 0x1F1FF     # Regional Indicator Symbols (flags)
    )

def clean_node_name(name):
    """
    Nettoyer et valider un nom de nœud pour prévenir les injections SQL et XSS.
    
    Filtre tous les caractères sauf:
    - Alphanumériques (a-z, A-Z, 0-9)
    - Espaces, tirets, underscores
    - Emojis (préservés pour les noms de nœuds personnalisés)
    
    Bloque:
    - Balises HTML (<script>, <img>, etc.)
    - Tentatives d'injection SQL (', --, ;, etc.)
    - Caractères spéciaux dangereux
    
    Args:
        name: Nom de nœud brut (longName ou shortName)
    
    Returns:
        Nom nettoyé et sécurisé
    """
    if not name:
        return ""
    
    # Import re module for whitespace normalization
    re_module = lazy_import_re()
    
    # Remove leading/trailing whitespace
    name = name.strip()
    
    # Build a cleaned version keeping only safe characters and emojis
    cleaned = []
    for char in name:
        # Keep alphanumeric, spaces, hyphens, underscores, and emojis
        if char.isalnum() or char in ' -_' or is_emoji(char):
            cleaned.append(char)
    
    result = ''.join(cleaned)
    
    # Collapse multiple spaces into one
    result = re_module.sub(r'\s+', ' ', result)
    
    return result.strip()

def validate_page_number(page_str, total_pages):
    """Valider et normaliser un numéro de page"""
    try:
        page = int(page_str)
        if page < 1:
            return 1
        elif page > total_pages:
            return total_pages
        return page
    except (ValueError, TypeError):
        return 1
