#!/usr/bin/env python3
"""
Configuration privée pour le bot Meshtastic
Contient les paramètres sensibles (tokens, mots de passe, IDs utilisateurs)

⚠️ NE PAS COMMITER CE FICHIER DANS GIT
Copier ce fichier vers config.priv.py et remplir avec vos valeurs réelles
"""

# ========================================
# CONFIGURATION TELEGRAM - PARAMETRES SENSIBLES
# ========================================

# Token du bot Telegram
# Obtenir via @BotFather sur Telegram
TELEGRAM_BOT_TOKEN = "8370817963:AAGMr-Vgbsugn67zR4ihGTzBw564SKhpZzw"  # Token du bot Telegram

# Utilisateurs Telegram autorisés (liste vide = tous autorisés)
# Format: [123456789, 987654321, ...]
TELEGRAM_AUTHORIZED_USERS = []

# Utilisateurs Telegram à alerter (IDs Telegram)
# Si vide, utilise TELEGRAM_AUTHORIZED_USERS
TELEGRAM_ALERT_USERS = [134360030]

# Mapping des utilisateurs Telegram vers des identités Meshtastic
# Format: {telegram_id: {"node_id": 0x..., "short_name": "...", "display_name": "..."}}
TELEGRAM_TO_MESH_MAPPING = {
    134360030: {  # Clickyluke
        "node_id": 0xa76f40da,    # Node ID Meshtastic à utiliser
        "short_name": "tigro",     # Nom court pour les messages
        "display_name": "Tigro"    # Nom d'affichage pour les logs
    }        
    # Exemple:
    # 123456789: {
    #     "node_id": 0x16fad3dc,
    #     "short_name": "tigro",
    #     "display_name": "Tigro User"
    # },
    # 987654321: {
    #     "node_id": 0x12345678,
    #     "short_name": "autre",
    #     "display_name": "Autre User"
    # }
}

#MQTT_NEIGHBOR_PASSWORD = "large4cats"
MQTT_NEIGHBOR_PASSWORD = "uplink"

# ========================================
# CONFIGURATION REBOOT - PARAMETRES SENSIBLES
# ========================================

REBOOT_AUTHORIZED_USERS = [
    134360030,    # Telegram Clic
    0x16fad3dc,   # tigrobot mesh
    0xa76f40da,   # tigro t1000E
]

# Mot de passe pour la commande /rebootpi
REBOOT_PASSWORD = "4242"

# ========================================
# CONFIGURATION ALERTES MESH - PARAMETRES SENSIBLES
# ========================================

# Nœuds abonnés aux alertes (recevront des DM en cas d'alerte critique)
# Format: Liste d'IDs de nœuds (int ou hex) - Ex: [0x16fad3dc, 305419896, 0x12345678]
# Laisser vide [] pour désactiver les alertes Mesh
MESH_ALERT_SUBSCRIBED_NODES = [
    0x143bcd7f, # Tigro T1000E MC
]

# ========================================
# CONFIGURATION CLI - PARAMETRES SENSIBLES
# ========================================

# Mapping CLI vers identité Mesh (optionnel)
# Si défini, les messages CLI apparaîtront comme venant de ce nœud
CLI_TO_MESH_MAPPING = {
    0xC11A0001: {
        "mesh_name": "tigro"
    }        
    # Par défaut, la CLI n'a pas de mapping mesh
    # Décommenter et configurer si besoin:
    # 0xC11A0001: {
    #     "mesh_id": 0x12345678,
    #     "mesh_name": "DevUser"
    # }
}
