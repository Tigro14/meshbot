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
TIGROG2_NODE_ID = 0x16fad3dc  # Node ID du tigrog2

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

# Throttling des commandes utilisateurs
MAX_COMMANDS_PER_WINDOW = 5  # 5 commandes max
COMMAND_WINDOW_SECONDS = 300  # par tranche de 5 minutes (300s)

# Variables globales d'état
DEBUG_MODE = True
