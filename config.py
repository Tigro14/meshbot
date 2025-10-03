#!/usr/bin/env python3
"""
Configuration centralisée pour le bot Meshtastic
"""

# Configuration Meshtastic
SERIAL_PORT = "/dev/ttyACM0"

# Configuration Llama
LLAMA_HOST = "127.0.0.1"
LLAMA_PORT = 8080

# Configuration ESPHome
ESPHOME_HOST = "192.168.1.27"
ESPHOME_PORT = 80

# Configuration nœuds distants
REMOTE_NODE_HOST = "192.168.1.38"
REMOTE_NODE_NAME = "tigrog2"
TIGROG2_NODE_ID = 0x16fad3dc

# Configuration base de données des nœuds
NODE_NAMES_FILE = "node_names.json"
NODE_UPDATE_INTERVAL = 300  # 5 minutes

# Configuration affichage des métriques de signal
SHOW_RSSI = False  # Afficher les valeurs RSSI (-85dB)
SHOW_SNR = False   # Afficher les valeurs SNR (SNR:8.5)
COLLECT_SIGNAL_METRICS = True  # Collecter RSSI/SNR pour le tri

# Limites mémoire
MAX_CACHE_SIZE = 5
MAX_RX_HISTORY = 50
MAX_CONTEXT_MESSAGES = 6  # 3 échanges (user + assistant)
CONTEXT_TIMEOUT = 1800  # 30 minutes

# Limites messages
MAX_MESSAGE_SIZE = 180

# Configuration throttling commandes
MAX_COMMANDS_PER_WINDOW = 5  # Nombre max de commandes
COMMAND_WINDOW_SECONDS = 300  # Fenêtre de temps en secondes (5 minutes)

# Configuration IA pour Meshtastic (LoRa) - Réponses très courtes
MESH_AI_CONFIG = {
    "system_prompt": "Tu es un assistant accessible via le réseau Meshtastic en LoRa. Réponds en français, très court, 320 caractères maximum. Sois précis et concis, maintiens la continuité de la conversation.",
    "max_tokens": 1500,
    "temperature": 0.7,
    "top_p": 0.95,
    "top_k": 20,
    "timeout": 60,  # 1 minute pour LoRa
    "max_response_chars": 320
}

# Configuration IA pour Telegram - Réponses plus développées
TELEGRAM_AI_CONFIG = {
    "system_prompt": "Tu es un assistant intelligent accessible via Telegram, connecté à un réseau Meshtastic LoRa. Tu peux donner des réponses plus détaillées et développées. Réponds en français de manière claire et complète, tu peux utiliser des emojis pour rendre tes réponses plus engageantes. Tu es utile, créatif et bienveillant.",
    "max_tokens": 4000,
    "temperature": 0.8,  # Légèrement plus créatif pour Telegram
    "top_p": 0.95,
    "top_k": 25,
    "timeout": 120,  # 2 minutes pour Telegram
    "max_response_chars": 3000  # Plus long pour Telegram
}

# Configuration Telegram Bridge
TELEGRAM_ENABLED = True  # Activer/désactiver l'intégration Telegram
TELEGRAM_BOT_TOKEN = "8370817963:AAG3tUW1Qvw_4dQyKlJKR1VGIZo4KxsQULQ"  # Token du bot Telegram

# Utilisateurs Telegram autorisés (liste vide = tous autorisés)
# Format: [123456789, 987654321, ...]
TELEGRAM_AUTHORIZED_USERS = []

# Mapping des utilisateurs Telegram vers des identités Meshtastic
# Format: {telegram_id: {"node_id": 0x..., "short_name": "...", "display_name": "..."}}
TELEGRAM_TO_MESH_MAPPING = {
    134360030: {  # Clickyluke
        "node_id": 0xa76f40da,    # Node ID Meshtastic à utiliser
        "short_name": "tigro",     # Nom court pour les messages
        "display_name": "Tigro"    # Nom d'affichage pour les logs
    }
    # Ajouter d'autres mappings ici si nécessaire
    # 987654321: {
    #     "node_id": 0x12345678,
    #     "short_name": "autre",
    #     "display_name": "Autre User"
    # }
}

# Variables globales d'état
DEBUG_MODE = False
