#!/usr/bin/env python3
"""
Configuration Telegram - Fichier exemple
IMPORTANT: Ce fichier peut être supprimé si vous utilisez config.py principal
"""

# Import depuis la configuration principale du bot Meshtastic
import sys
import os

# Ajouter le chemin vers le bot principal (ajustez selon votre installation)
BOT_PATH = "/home/dietpi/bot"
if os.path.exists(BOT_PATH):
    sys.path.insert(0, BOT_PATH)

try:
    # Importer depuis config.py principal
    from config import (
        TELEGRAM_BOT_TOKEN,
        TELEGRAM_AUTHORIZED_USERS,
        TELEGRAM_QUEUE_FILE,
        TELEGRAM_RESPONSE_FILE,
        TELEGRAM_COMMAND_TIMEOUT,
        TELEGRAM_MAX_MESSAGE_LENGTH,
        TELEGRAM_LOG_LEVEL,
        TELEGRAM_LOG_FILE
    )
    
    print("✅ Configuration importée depuis config.py principal")
    
except ImportError as e:
    print(f"⚠️ Impossible d'importer config.py: {e}")
    print("📝 Utilisation de la configuration locale par défaut")
    
    # Configuration locale de fallback
    TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
    TELEGRAM_AUTHORIZED_USERS = []
    TELEGRAM_QUEUE_FILE = "/tmp/telegram_mesh_queue.json"
    TELEGRAM_RESPONSE_FILE = "/tmp/mesh_telegram_response.json"
    TELEGRAM_COMMAND_TIMEOUT = 30
    TELEGRAM_MAX_MESSAGE_LENGTH = 4096
    TELEGRAM_LOG_LEVEL = "INFO"
    TELEGRAM_LOG_FILE = "/var/log/telegram-mesh-bot.log"

# Validation de la configuration
def validate_config():
    """Valider la configuration Telegram"""
    errors = []
    
    if TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        errors.append("❌ TELEGRAM_BOT_TOKEN n'est pas configuré")
    
    if not isinstance(TELEGRAM_AUTHORIZED_USERS, list):
        errors.append("❌ TELEGRAM_AUTHORIZED_USERS doit être une liste")
    
    if TELEGRAM_COMMAND_TIMEOUT <= 0:
        errors.append("❌ TELEGRAM_COMMAND_TIMEOUT doit être > 0")
    
    return errors

if __name__ == "__main__":
    # Test de la configuration
    print("🧪 Test de la configuration Telegram...")
    print("=" * 50)
    
    errors = validate_config()
    
    if errors:
        print("⚠️ Erreurs de configuration:")
        for error in errors:
            print(f"   {error}")
    else:
        print("✅ Configuration valide")
    
    print(f"📱 Token configuré: {'Oui' if TELEGRAM_BOT_TOKEN != 'YOUR_TELEGRAM_BOT_TOKEN' else 'Non'}")
    print(f"👥 Utilisateurs autorisés: {len(TELEGRAM_AUTHORIZED_USERS)} ({'Tous' if not TELEGRAM_AUTHORIZED_USERS else 'Liste spécifique'})")
    print(f"📁 Fichier queue: {TELEGRAM_QUEUE_FILE}")
    print(f"📁 Fichier réponse: {TELEGRAM_RESPONSE_FILE}")
    print(f"⏱️ Timeout: {TELEGRAM_COMMAND_TIMEOUT}s")
    print(f"📊 Log level: {TELEGRAM_LOG_LEVEL}")
