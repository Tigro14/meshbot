#!/usr/bin/env python3
"""
Utilitaires pour l'analyse de signal
"""

def get_signal_quality_description(rssi, snr):
    """Obtenir une description textuelle de la qualité du signal"""
    if rssi == 0 and snr == 0:
        return "Inconnue"
    
    # Classification basée sur RSSI principalement
    if rssi >= -80:
        return "Excellente"
    elif rssi >= -100:
        if snr >= 5:
            return "Très bonne"
        else:
            return "Bonne"
    elif rssi >= -120:
        if snr >= 0:
            return "Correcte"
        else:
            return "Faible"
    elif rssi > -150:
        if snr >= -5:
            return "Très faible"
        else:
            return "Critique"
    else:
        return "Inconnue"

def estimate_distance_from_rssi(rssi):
    """Estimation approximative de distance basée sur RSSI (LoRa 868MHz)"""
    if rssi >= -80:
        return "<100m"
    elif rssi >= -90:
        return "100-300m" 
    elif rssi >= -100:
        return "300m-1km"
    elif rssi >= -110:
        return "1-3km"
    elif rssi >= -120:
        return "3-10km"
    elif rssi >= -130:
        return "10-20km"
    else:
        return ">20km"

def estimate_rssi_from_snr(snr):
    """Estimer RSSI depuis SNR (formule empirique)"""
    if snr == 0:
        return 0
    # Formule empirique : RSSI ≈ -100 + (SNR * 2.5)
    return int(-100 + (snr * 2.5))

def find_best_relays(remote_nodes, max_relays=3):
    """Trouver les meilleurs relays potentiels"""
    if not remote_nodes:
        return []
    
    # Trier par qualité de signal (RSSI décroissant)
    sorted_relays = sorted(
        [node for node in remote_nodes if node.get('rssi', 0) != 0],
        key=lambda x: x.get('rssi', -999),
        reverse=True
    )
    
    return sorted_relays[:max_relays]
