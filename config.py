#!/usr/bin/env python3
"""
Configuration centralisée pour le bot Meshtastic

Ce fichier contient les paramètres PUBLICS (non sensibles).
Les paramètres sensibles (tokens, mots de passe, IDs) sont dans config.priv.py
"""

# ========================================
# IMPORT CONFIGURATION PRIVÉE
# ========================================
# Importer les paramètres sensibles depuis config.priv.py
# Si le fichier n'existe pas, créer le depuis config.priv.py.sample
try:
    from config_priv import *
except (ImportError, SyntaxError) as e:
    import os
    import sys
    import traceback
    
    # Afficher le chemin où Python cherche le fichier
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_priv_path = os.path.join(current_dir, 'config_priv.py')
    
    print("⚠️  ATTENTION: Impossible d'importer config_priv.py!")
    print(f"   Répertoire actuel: {current_dir}")
    print(f"   Fichier recherché: {config_priv_path}")
    print(f"   Fichier existe: {os.path.exists(config_priv_path)}")
    
    if os.path.exists(config_priv_path):
        print(f"   Permissions: {oct(os.stat(config_priv_path).st_mode)[-3:]}")
        print(f"   Taille: {os.path.getsize(config_priv_path)} octets")
        print(f"   ⚠️  ERREUR: {type(e).__name__}: {e}")
        if isinstance(e, SyntaxError):
            print("   → Le fichier contient une ERREUR DE SYNTAXE Python")
            print(f"   → Ligne {e.lineno}: {e.text.strip() if e.text else 'N/A'}")
        else:
            print("   → Le fichier existe mais l'import a échoué")
        print("   → Vérifier le contenu avec: python3 -m py_compile config_priv.py")
        print("   → Ou utiliser: python3 diagnose_config_priv.py")
    else:
        print("   → Le fichier n'existe pas à cet emplacement")
        print("   → Copier config.priv.py.sample vers config_priv.py et remplir vos valeurs")
    
    print("\n   ⚠️  Utilisation des valeurs par défaut (non fonctionnelles)")
    
    # Valeurs par défaut pour éviter les erreurs d'import
    TELEGRAM_BOT_TOKEN = "******************"
    TELEGRAM_AUTHORIZED_USERS = []
    TELEGRAM_ALERT_USERS = []
    TELEGRAM_TO_MESH_MAPPING = {}
    MQTT_NEIGHBOR_PASSWORD = "your_mqtt_password_here"
    REBOOT_AUTHORIZED_USERS = []
    REBOOT_PASSWORD = "your_password_secret"
    MESH_ALERT_SUBSCRIBED_NODES = []
    CLI_TO_MESH_MAPPING = {}

# ========================================
# CONFIGURATION MODE DE CONNEXION
# ========================================

DUAL_NETWORK_MODE=True

# Activer/désactiver la connexion Meshtastic
# Si False, le bot peut fonctionner en mode "companion" pour MeshCore
# sans aucune connexion Meshtastic active
MESHTASTIC_ENABLED = True  # True = Connexion Meshtastic active, False = Mode standalone
BOT_POSITION = (48.8252, 2.3622)

# Mode de connexion au réseau Meshtastic (utilisé si MESHTASTIC_ENABLED=True)
# Options disponibles:
#   'serial' - Connexion via port série USB/UART (configuration classique)
#   'tcp'    - Connexion via réseau TCP/IP à un node distant (WiFi/Ethernet)
#
# NOTE: En mode single-node (recommandé pour simplicité):
#   - Choisir 'serial' pour un node connecté directement au RPi
#   - Choisir 'tcp' pour un node ROUTER accessible en réseau
CONNECTION_MODE = 'serial'  # 'serial' ou 'tcp'

# Configuration connexion série Meshtastic (utilisée si CONNECTION_MODE='serial')
#SERIAL_PORT = "/dev/ttyACM0"
SERIAL_PORT = "auto:manufacturer=Heltec"

# Configuration connexion TCP Meshtastic (utilisée si CONNECTION_MODE='tcp')
#TCP_HOST = "192.168.1.38"
#TCP_PORT = 4403

# ========================================
# CONFIGURATION MODE MESHCORE COMPANION
# ========================================
# Mode companion pour MeshCore - Connexion serial uniquement pour DM
# Permet d'utiliser le bot avec MeshCore sans connexion Meshtastic
# Les fonctionnalités disponibles en mode companion:
#   - /bot (AI), /weather, /rain, /power, /sys, /help
#   - /blitz (si activé), /vigilance (si activé)
# Les fonctionnalités désactivées en mode companion:
#   - /nodes, /my, /trace, /neighbors, /stats (requièrent Meshtastic)
MESHCORE_ENABLED = True  # True = Activer mode companion MeshCore
#MESHCORE_SERIAL_PORT = "/dev/ttyACM2"  # Port série pour MeshCore
MESHCORE_SERIAL_PORT = "auto:SERIAL=7CEF06581293BD9C"
MESHCORE_PUBLIC_PSK = "izOH6cXN6mrJ5e26oRXNcg=="  # Base64 format

# MeshCore RX_LOG_DATA monitoring (only works when MESHCORE_ENABLED=True)
# RX_LOG_DATA provides raw RF packet visibility of ALL mesh traffic (not just DMs)
#
# ⚠️ IMPORTANT: RX_LOG_DATA shows RF activity but CANNOT parse packet content
#    - You will see: SNR, RSSI, raw hex data
#    - You will NOT see: from/to IDs, message content, packet types
#    - Full parsing requires MeshCore protocol specification (not yet available)
#
# Use cases:
#   ✅ Monitor RF activity (know when packets are received)
#   ✅ Track signal quality (SNR/RSSI for all packets)
#   ✅ Verify mesh network is active
#   ❌ Parse packet details (use CONTACT_MSG_RECV for DMs only)
#
# Recommendations:
#   - Enable if you want to see ALL RF activity in logs (debugging)
#   - Disable if you only care about DMs (less log spam)
MESHCORE_RX_LOG_ENABLED = False  # Use library events (CHANNEL_MSG_RECV)

# Auto-reboot du nœud distant en cas d'échec de connexion TCP initial
# Si True, le bot tentera automatiquement de rebooter le nœud distant
# via 'meshtastic --host <IP> --reboot' en cas d'erreur de connexion
# (ex: "No route to host", timeout, connexion refusée)
#TCP_AUTO_REBOOT_ON_FAILURE = True
# Délai d'attente après reboot avant de retenter la connexion (secondes)
#TCP_REBOOT_WAIT_TIME = 45

# ========================================
# DÉCHIFFREMENT DES MESSAGES DIRECTS (DM)
# ========================================
# Meshtastic 2.7.15+ chiffre tous les DMs avec la PSK du canal 0
# 
# PSK du canal 0 de votre réseau (encodée en base64)
# - Laisser None pour utiliser la PSK par défaut de Meshtastic ("1PG7OiApB1nwvP+rz05pAQ==")
# - Pour un réseau avec PSK personnalisée, spécifier la PSK encodée en base64
# - Exemple: CHANNEL_0_PSK = "votre_psk_base64_ici"
#
# Pour obtenir votre PSK:
#   1. Via l'app Meshtastic: Paramètres → Canaux → Canal 0 → Voir la clé
#   2. Via CLI: meshtastic --info (section channels)
#   3. Via Python: interface.localNode.channels[0].settings.psk (en base64)
CHANNEL_0_PSK = None  # None = utiliser la PSK par défaut Meshtastic

# ========================================
# CONFIGURATION NŒUD DISTANT (OPTIONNEL)
# ========================================
# Configuration pour monitorer un nœud distant via TCP (ex: tigrog2)
# ⚠️ IMPORTANT: Ces paramètres sont utilisés par:
#   1. CONNECTION_MODE='tcp' : Connexion principale au bot
#   2. TIGROG2_MONITORING_ENABLED=True : Surveillance d'un nœud distant
#
# Si vous ne voulez PAS de connexions TCP vers ce nœud:
#   → Mettez TIGROG2_MONITORING_ENABLED = False (section ALERTES plus bas)
#
# NOTE: L'ID du node (nodeNum) est automatiquement détecté depuis la connexion
#       via interface.localNode.nodeNum - pas besoin de le configurer manuellement
#REMOTE_NODE_HOST = "192.168.1.38"  # IP du node distant (TCP mode ou monitoring)
REMOTE_NODE_NAME = "tigro G2 MiniPV"        # Nom d'affichage pour les alertes

# ========================================
# CONFIGURATION LEGACY MULTI-NODES (AVANCÉ)
# ========================================
# NOTE: Configuration avancée pour l'architecture legacy multi-nodes
# La plupart des utilisateurs n'ont pas besoin de modifier ceci
# 
# Traiter les commandes depuis TCP en mode multi-nodes legacy
# True = Accepter commandes de SERIAL ET TCP - Configuration hybride (legacy)
# False = Accepter commandes UNIQUEMENT de SERIAL - Configuration historique
# NOTE: En mode single-node (CONNECTION_MODE défini), cette option est ignorée
PROCESS_TCP_COMMANDS = False  # Laisser à False sauf usage avancé

# ========================================
# CONFIGURATION LLAMA.CPP
# ========================================
LLAMA_HOST = "127.0.0.1"
LLAMA_PORT = 8080
LLAMA_HOST = "127.0.0.1"
LLAMA_PORT = 8080
LLAMA_BLOCK_ON_HIGH_TEMP = True      # Bloquer si CPU trop chaud
LLAMA_BLOCK_ON_LOW_BATTERY = True    # Bloquer si batterie faible
LLAMA_MAX_CPU_TEMP = 60.0           # °C - Température CPU maximale
LLAMA_MIN_BATTERY_VOLTAGE = 12.5    # V - Tension batterie minimale

# ========================================
# CONFIGURATION ESPHOME
# ========================================
ESPHOME_HOST = "192.168.1.27"
ESPHOME_PORT = 80

# Telemetry broadcast ESPHome
ESPHOME_TELEMETRY_ENABLED = True  # Activer/désactiver broadcast automatique de télémétrie
ESPHOME_TELEMETRY_INTERVAL = 3600  # Intervalle en secondes (3600s = 1h)

# NOTE: Lorsque ESPHOME_TELEMETRY_ENABLED = True, le bot désactive automatiquement
# la télémétrie embarquée du device Meshtastic (device_update_interval = 0) pour
# éviter le bruit mesh avec des paquets redondants. Si vous désactivez ESPHome
# plus tard, vous pouvez réactiver la télémétrie embarquée avec:
#   meshtastic --set telemetry.device_update_interval 900

# Configuration base de données des nœuds (SQLite)
# Node data is now stored in traffic_history.db (meshtastic_nodes table)
NODE_UPDATE_INTERVAL = 300  # 5 minutes

# Configuration synchronisation clés publiques périodique
PUBKEY_SYNC_ENABLE = True   # Enable/disable periodic pubkey sync (for testing)
PUBKEY_SYNC_INTERVAL = 900  # 15 minutes - Intervalle pour synchronisation clés publiques périodique

# Configuration timeout TCP pour détection de silence
# Durée maximale (en secondes) sans recevoir de paquet avant de forcer une reconnexion TCP
# Recommandations selon le type de réseau:
#   - 120s (défaut) : Réseaux actifs avec trafic régulier (paquets toutes les 30-60s)
#   - 180s : Réseaux moyennement actifs (paquets toutes les 1-3 minutes)
#   - 300s : Réseaux peu actifs/sparse (paquets toutes les 3-5 minutes)
# Note: Valeur trop faible = faux positifs, valeur trop élevée = détection lente des vrais problèmes
#TCP_SILENT_TIMEOUT = 120  # 120 secondes (2 minutes) - Timeout par défaut

# Configuration intervalle de vérification santé TCP
# Fréquence des vérifications de réception de paquets (en secondes)
# Recommandations:
#   - 30s (défaut) : Balance entre réactivité et charge système
#   - 15s : Détection plus rapide (plus de checks)
#   - 60s : Moins de checks (économie ressources pour systèmes contraints)
# Note: Plus fréquent = détection plus rapide mais plus de wake-ups CPU
#TCP_HEALTH_CHECK_INTERVAL = 30  # 30 secondes - Intervalle vérification par défaut

# ⚠️ IMPORTANT: Relation entre TIMEOUT et INTERVAL
# Pour éviter les fausses alarmes ou détections trop tardives:
#
# Le ratio TIMEOUT/INTERVAL ne devrait PAS être un nombre entier (ou proche).
# Sinon, la détection du timeout sera retardée d'un intervalle complet.
#
# Exemple PROBLÉMATIQUE:
#   • TCP_HEALTH_CHECK_INTERVAL=15s avec TCP_SILENT_TIMEOUT=90s
#   • Ratio: 90/15 = 6.0 (nombre entier!)
#   • Dernier paquet à T+0, checks à: 15s, 30s, 45s, 60s, 75s, 90s (OK), 105s (TIMEOUT)
#   • Détection à 105s au lieu de 90s → 15s de retard!
#   • Avec un paquet qui arrive à T+0.1s, c'est 104.9s de silence détecté → fausse alarme
#
# Exemple BON:
#   • TCP_HEALTH_CHECK_INTERVAL=15s avec TCP_SILENT_TIMEOUT=98s (ou 112s, ou 120s)
#   • Ratio: 98/15 = 6.5 (pas un entier)
#   • Détection à 105s avec 98s timeout → seulement 7s de retard
#
# Configurations RECOMMANDÉES (ratio avec marge):
#   • INTERVAL=15s → TIMEOUT=98s, 112s, 127s, 135s... (éviter 90s, 105s, 120s - ratios entiers)
#   • INTERVAL=30s → TIMEOUT=120s, 150s, 180s... (120=4.0× est OK car intervalle large)
#   • INTERVAL=60s → TIMEOUT=240s, 300s... (4× minimum)
#
# Le bot vous alertera au démarrage si votre configuration est problématique.

# Configuration reconnexion TCP programmée (préventive)
# Force une reconnexion TCP périodique même si la connexion semble stable
# Utile pour contourner les bugs de firmware (ex: Meshtastic 2.7.15 Station G2)
# où la connexion TCP se dégrade progressivement sans déconnexion détectable
# Recommandations:
#   - 0 (défaut) : Désactivé - Se fier uniquement à la détection de silence
#   - 180s (3 min) : Recommandé pour Station G2 avec firmware 2.7.15
#   - 300s (5 min) : Alternative plus conservatrice
# Note: Valeur trop faible = reconnexions inutiles, valeur trop élevée = dégradation prolongée
TCP_FORCE_RECONNECT_INTERVAL = 0  # 0 = désactivé, >0 = intervalle en secondes

# Configuration chargement initial des voisins au démarrage
# Polling mechanism pour attendre que interface.nodes se charge complètement
NEIGHBOR_LOAD_INITIAL_WAIT = 10    # Attente initiale avant première vérification (secondes)
NEIGHBOR_LOAD_MAX_WAIT = 60        # Timeout maximum pour chargement complet (secondes)
NEIGHBOR_LOAD_POLL_INTERVAL = 5    # Intervalle entre vérifications de progression (secondes)

# Configuration rétention des données de voisinage dans SQLite
# Durée de conservation des données de voisinage (en heures)
# 720h = 30 jours - Recommandé pour avoir une carte réseau bien peuplée
# 48h = 2 jours - Valeur historique (peut donner une carte vide)
NEIGHBOR_RETENTION_HOURS = 720  # 30 jours de rétention

# Configuration rétention des statistiques de nœuds dans SQLite
# Durée de conservation des métriques agrégées par nœud (en heures)
# 168h = 7 jours (1 semaine) - Recommandé pour garder les métriques récentes
# Les statistiques de nœuds inactifs depuis plus de 7 jours seront supprimées
NODE_STATS_RETENTION_HOURS = 168  # 7 jours de rétention

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
    "max_tokens": 1000,
    "temperature": 0.7,
    "top_p": 0.95,
    "top_k": 20,
    "timeout": 120,  # 1 minute pour LoRa
    "max_response_chars": 320
}

# Configuration IA pour Telegram - Réponses plus développées
TELEGRAM_AI_CONFIG = {
    "system_prompt": "Tu es un assistant intelligent accessible via Telegram, connecté à un réseau Meshtastic LoRa. Tu peux donner des réponses plus détaillées et développées. Réponds en français de manière claire et complète, tu peux utiliser des emojis pour rendre tes réponses plus engageantes. Tu es utile, créatif et bienveillant.",
    "max_tokens": 4000,
    "temperature": 0.8,  # Légèrement plus créatif pour Telegram
    "top_p": 0.95,
    "top_k": 25,
    "timeout": 500,  # 2 minutes pour Telegram
    "max_response_chars": 3000  # Plus long pour Telegram
}

# ========================================
# CONFIGURATION PLATEFORMES MESSAGERIE
# ========================================

# Configuration Telegram Bridge
TELEGRAM_ENABLED = True  # Activer/désactiver l'intégration Telegram

# NOTE: Avec la nouvelle architecture modulaire, vous pouvez :
# 1. Désactiver Telegram en mettant TELEGRAM_ENABLED = False
# 2. Ajouter Discord en activant DISCORD_ENABLED = True (futur)
# 3. Activer la CLI locale avec CLI_ENABLED = True
# 4. Utiliser plusieurs plateformes en même temps
# Voir platform_config.py pour la configuration détaillée

# NOTE: TELEGRAM_BOT_TOKEN, TELEGRAM_AUTHORIZED_USERS, TELEGRAM_ALERT_USERS,
#       et TELEGRAM_TO_MESH_MAPPING sont définis dans config.priv.py

# ========================================
# CONFIGURATION CLI SERVEUR
# ========================================

# Serveur CLI TCP pour clients externes (cli_client.py)
CLI_ENABLED = True # Activer/désactiver le serveur CLI (utile pour dev/debug)
CLI_SERVER_HOST = '127.0.0.1'  # Écoute seulement en local (sécurité)
CLI_SERVER_PORT = 9999  # Port du serveur CLI

# Configuration IA pour CLI - Similaire à Telegram mais sans emojis
CLI_AI_CONFIG = {
    "system_prompt": "Tu es un assistant intelligent accessible via CLI locale. Réponds en français de manière claire et complète. Tu es utile et précis.",
    "max_tokens": 4000,
    "temperature": 0.8,
    "top_p": 0.95,
    "top_k": 25,
    "timeout": 120,
    "max_response_chars": 3000
}

# ID utilisateur CLI (utilisé pour throttling et logs)
CLI_USER_ID = 0xC11A0001  # ID fictif pour la CLI (CLI = C11)

# NOTE: CLI_TO_MESH_MAPPING est défini dans config.priv.py

# ========================================
# CONFIGURATION ALERTES TELEGRAM
# ========================================

# NOTE: TELEGRAM_ALERT_USERS est défini dans config.priv.py

# Configuration monitoring température CPU
TEMP_WARNING_ENABLED = True  # Activer/désactiver les alertes température
TEMP_WARNING_THRESHOLD = 60  # Température en °C déclenchant une alerte
TEMP_WARNING_DURATION = 300  # Durée en secondes avant alerte (5 minutes)
TEMP_CRITICAL_THRESHOLD = 68.0  # Température critique
TEMP_CHECK_INTERVAL = 60  # Vérifier la température toutes les 60 secondes

# Configuration monitoring nœud distant (tigrog2)
# ⚠️ IMPORTANT: Si activé, le bot crée des connexions TCP vers REMOTE_NODE_HOST
#    pour surveiller l'état du nœud distant.
#
# ⚠️ CONFLIT TCP EN MODE CONNECTION_MODE='tcp':
#    Si CONNECTION_MODE='tcp', le bot maintient déjà une connexion TCP permanente.
#    Activer TIGROG2_MONITORING_ENABLED créerait une SECONDE connexion TCP vers
#    le même nœud, violant la limite ESP32 d'une connexion TCP par client.
#
#    RECOMMANDATION:
#    - Si CONNECTION_MODE='tcp'    → TIGROG2_MONITORING_ENABLED = False (OBLIGATOIRE)
#    - Si CONNECTION_MODE='serial' → TIGROG2_MONITORING_ENABLED peut être True
#
TIGROG2_MONITORING_ENABLED = False  # Activer/désactiver le monitoring du nœud distant via TCP
TIGROG2_CHECK_INTERVAL = 120  # Vérifier le nœud distant toutes les 2 minutes
TIGROG2_TIMEOUT = 20  # Timeout de connexion en secondes
TIGROG2_ALERT_ON_REBOOT = True  # Alerter lors d'un redémarrage détecté
TIGROG2_ALERT_ON_DISCONNECT = True  # Alerter si le nœud distant devient inaccessible

# Configuration alertes de déconnexion TCP (mode TCP uniquement)
# Si le bot est en mode TCP et perd la connexion au nœud Meshtastic,
# une alerte est envoyée via Telegram après l'échec des tentatives de reconnexion.
TCP_DISCONNECT_ALERT_ENABLED = True  # Activer/désactiver les alertes de déconnexion TCP

# Configuration monitoring CPU du bot
CPU_WARNING_ENABLED = True  # Activer/désactiver les alertes CPU
CPU_WARNING_THRESHOLD = 90  # % CPU déclenchant une alerte (80%)
CPU_WARNING_DURATION = 300  # Durée en secondes avant alerte (5 minutes)
CPU_CRITICAL_THRESHOLD = 150  # % CPU critique (150% = 1.5 cœurs)
CPU_CHECK_INTERVAL = 30  # Vérifier le CPU toutes les 30 secondes

# Configuration vigilance météo Météo-France
VIGILANCE_ENABLED = True  # Activer/désactiver la surveillance vigilance météo
VIGILANCE_DEPARTEMENT = '75'  # Numéro du département à surveiller (ex: '75' pour Paris, '25' pour Doubs)
VIGILANCE_CHECK_INTERVAL = 28800  # Vérifier toutes les 8 heures (28800 secondes)
VIGILANCE_ALERT_THROTTLE = 3600  # Minimum 1h entre deux alertes (3600 secondes)
VIGILANCE_ALERT_LEVELS = ['Orange', 'Rouge']  # Niveaux déclenchant une alerte automatique
# Note: Niveaux disponibles: 'Vert', 'Jaune', 'Orange', 'Rouge'

# Configuration surveillance éclairs Blitzortung.org
BLITZ_ENABLED = True  # Activer/désactiver la surveillance des éclairs
BLITZ_LATITUDE = 0.0  # Latitude du point de surveillance (0.0 = auto-détection depuis GPS du node)
BLITZ_LONGITUDE = 0.0  # Longitude du point de surveillance (0.0 = auto-détection depuis GPS du node)
BLITZ_RADIUS_KM = 50  # Rayon de surveillance en km (défaut: 50km)
BLITZ_CHECK_INTERVAL = 900  # Vérifier toutes les 15 minutes (900 secondes)
BLITZ_WINDOW_MINUTES = 15  # Fenêtre temporelle pour comptage éclairs (15min)
# Note: Position GPS auto-détectée depuis le node Meshtastic local
#       Si auto-détection échoue, spécifier BLITZ_LATITUDE/BLITZ_LONGITUDE manuellement
# Utilise le serveur MQTT public: blitzortung.ha.sed.pl:1883
# Dépendances: pip install paho-mqtt pygeohash

# ========================================
# CONFIGURATION ALERTES MESH (DM)
# ========================================

# Alertes Mesh - Envoyer des alertes critiques via DM Meshtastic
# Les alertes incluent: vigilance météo (Orange/Rouge) et éclairs (au-delà d'un seuil)
MESH_ALERTS_ENABLED = True  # Activer/désactiver les alertes Mesh

# NOTE: MESH_ALERT_SUBSCRIBED_NODES est défini dans config.priv.py

# Seuil d'éclairs pour déclencher une alerte Mesh
# Alerte envoyée si nombre d'éclairs détectés >= seuil dans la fenêtre de temps
BLITZ_MESH_ALERT_THRESHOLD = 5  # Nombre minimum d'éclairs pour alerter (défaut: 5)

# Throttling des alertes Mesh - Éviter le spam
# Temps minimum entre deux alertes du même type vers le même nœud
MESH_ALERT_THROTTLE_SECONDS = 1800  # 30 minutes entre deux alertes identiques (1800 secondes)

# ========================================
# CONFIGURATION COLLECTE VOISINS MQTT
# ========================================

# Configuration collecte voisins via MQTT Meshtastic
MQTT_NEIGHBOR_ENABLED = False  # Activer/désactiver la collecte de voisins via MQTT
MQTT_NEIGHBOR_SERVER = "mqtt.meshtastic.liamcottle.net"  # Serveur MQTT Meshtastic
MQTT_NEIGHBOR_PORT = 1883  # Port MQTT (1883 standard, 8883 pour TLS)
MQTT_NEIGHBOR_USER = "uplink"  # Utilisateur MQTT
# NOTE: MQTT_NEIGHBOR_PASSWORD est défini dans config.priv.py
MQTT_NEIGHBOR_TOPIC_ROOT = "msh"  # Racine des topics MQTT (défaut: "msh")
MQTT_NEIGHBOR_TOPIC_PATTERN = "msh/EU_868/2/e/MediumFast/#"  # Topic spécifique avec /# pour capturer tous les gateways
# Note: MQTT_NEIGHBOR_TOPIC_PATTERN peut être:
#   - Un pattern wildcard: "msh/+/+/2/e/+" (pour tous les messages ServiceEnvelope)
#   - Un topic spécifique avec /# à la fin: "msh/EU_868/2/e/MediumFast/#" (recommandé pour serveurs sans wildcard complet)
#   - Un topic spécifique sans /# sera automatiquement complété par /# pour capturer les gateway IDs
# Note: Le /# final est important car les messages sont publiés comme msh/EU_868/2/e/MediumFast/!gateway_id
#       Permet de collecter les informations de voisinage (NEIGHBORINFO_APP)
#       de tous les nœuds du réseau, au-delà de la portée radio directe.
#       Les données sont automatiquement sauvegardées dans la table 'neighbors'.
# Format topic: msh/<region>/<channel>/2/json/<node_id>/NEIGHBORINFO_APP
# Dépendance: paho-mqtt (déjà installé pour Blitzortung)

# Distance maximale (km) pour afficher les voisins MQTT dans /neighbors
# Les nœuds situés à plus de cette distance du bot seront filtrés (nœuds étrangers)
NEIGHBORS_MAX_DISTANCE_KM = 100  # Défaut: 100km

# ========================================
# CONFIGURATION REBOOT
# ========================================

# NOTE: REBOOT_AUTHORIZED_USERS et REBOOT_PASSWORD sont définis dans config.priv.py
REBOOT_COMMANDS_ENABLED = True

# ========================================
# MONITORING ET AUTO-REBOOT
# ========================================

# Monitoring des erreurs de base de données avec auto-reboot
# Si activé, le bot surveille les échecs d'écriture en base de données
# et déclenche automatiquement un reboot de l'application si le nombre
# d'erreurs dépasse le seuil configuré dans la fenêtre de temps
DB_AUTO_REBOOT_ENABLED = True

# Taille de la fenêtre de temps pour compter les erreurs (en secondes)
# Valeur par défaut: 300 secondes (5 minutes)
# Les erreurs plus anciennes ne sont pas comptabilisées
DB_AUTO_REBOOT_WINDOW_SECONDS = 300

# Nombre d'erreurs nécessaires pour déclencher le reboot automatique
# Valeur par défaut: 10 erreurs dans la fenêtre de temps
# Ce seuil permet de distinguer les erreurs temporaires (quelques échecs)
# des erreurs durables (nombreux échecs répétés)
DB_AUTO_REBOOT_ERROR_THRESHOLD = 10

# Variables globales d'état
DEBUG_MODE = True
MTMQTT_DEBUG = False 
