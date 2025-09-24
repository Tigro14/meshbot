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
TIGROG2_NODE_ID = 0x12345678  # À remplacer par l'ID réel de tigrog2

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

# Configuration Telegram Bridge
TELEGRAM_ENABLED = True  # Activer/désactiver l'intégration Telegram
TELEGRAM_BOT_TOKEN = "8370817963:AAG3tUW1Qvw_4dQyKlJKR1VGIZo4KxsQULQ"  # Token du bot Telegram

# Utilisateurs Telegram autorisés (liste vide = tous autorisés)
# Format: [123456789, 987654321, ...]
TELEGRAM_AUTHORIZED_USERS = []

# Configuration communication Telegram
TELEGRAM_QUEUE_FILE = "/tmp/telegram_mesh_queue.json"
TELEGRAM_RESPONSE_FILE = "/tmp/mesh_telegram_response.json"
TELEGRAM_COMMAND_TIMEOUT = 30  # Timeout pour les commandes en secondes
TELEGRAM_MAX_MESSAGE_LENGTH = 4096  # Limite de caractères Telegram
TELEGRAM_RATE_LIMIT_PER_USER = 10  # Commandes par minute par utilisateur

# Configuration logs Telegram
TELEGRAM_LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
TELEGRAM_LOG_FILE = "/var/log/telegram-mesh-bot.log"

# Variables globales d'état
DEBUG_MODE = False
