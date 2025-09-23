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

def debug_print(message):
    """Affiche seulement en mode debug"""
    if DEBUG_MODE:
        print(f"[DEBUG] {message}", file=sys.stderr, flush=True)

def info_print(message):
    """Affiche toujours (logs importants)"""
    print(f"[INFO] {message}", flush=True)

def conversation_print(message):
    """Log spécial pour les conversations"""
    print(f"[CONVERSATION] {message}", flush=True)

def error_print(message):
    """Log d'erreur"""
    print(f"[ERROR] {message}", file=sys.stderr, flush=True)

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

def get_signal_quality_icon(rssi):
    """Retourne l'icône de qualité basée sur le RSSI"""
    if rssi >= -80:
        return "🟢"  # Excellent
    elif rssi >= -100:
        return "🟡"  # Bon
    elif rssi >= -120:
        return "🟠"  # Faible
    elif rssi < -120 and rssi != 0:
        return "🔴"  # Très faible
    else:
        return "📶"  # Par défaut

def get_snr_quality_icon(snr):
    """Retourne l'icône de qualité basée sur le SNR"""
    if snr >= 10:
        return "🔵"    # Excellent SNR
    elif snr >= 5:
        return "🟣"    # Bon SNR
    elif snr >= 0:
        return "🟤"    # SNR faible mais positif
    elif snr < 0 and snr != 0:
        return "⚫"    # SNR négatif
    else:
        return ""

def truncate_text(text, max_length, suffix="..."):
    """Tronquer un texte si trop long"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix

def clean_node_name(name):
    """Nettoyer et valider un nom de nœud"""
    if not name:
        return ""
    return name.strip()

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