#!/bin/bash
# Installation et configuration du bot Telegram pour Meshtastic

echo "🤖 Installation Bot Telegram Meshtastic Bridge"
echo "=============================================="

# Vérifier Python 3.8+
python_version=$(python3 --version 2>&1 | grep -oP '\d+\.\d+')
if (( $(echo "$python_version < 3.8" | bc -l) )); then
    echo "❌ Python 3.8+ requis. Version détectée: $python_version"
    exit 1
fi

# Installer les dépendances
echo "📦 Installation des dépendances..."
pip3 install python-telegram-bot==20.7
pip3 install requests
pip3 install asyncio

# Créer le répertoire de configuration
mkdir -p /opt/meshtastic-telegram
cd /opt/meshtastic-telegram

# Créer le fichier de configuration
echo "⚙️ Configuration du bot..."
cat > telegram_config.py << 'EOF'
#!/usr/bin/env python3
"""
Configuration du bot Telegram Meshtastic
"""

# TOKEN du bot Telegram (obtenir via @BotFather)
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

# Utilisateurs autorisés (vide = tous autorisés)
# Format: [123456789, 987654321]
AUTHORIZED_USERS = []

# Configuration API Meshtastic
MESHTASTIC_BOT_API_URL = "http://localhost:8000"

# Configuration logging
LOG_LEVEL = "INFO"
LOG_FILE = "/var/log/telegram-mesh-bot.log"

# Configuration bridge
COMMAND_TIMEOUT = 30  # secondes
MAX_MESSAGE_LENGTH = 4096  # limite Telegram
RATE_LIMIT_PER_USER = 10  # commandes par minute
EOF

# Créer un wrapper avec l'interface de communication
echo "🔗 Création de l'interface avec le bot Meshtastic..."
cat > meshtastic_interface.py << 'EOF'
#!/usr/bin/env python3
"""
Interface entre le bot Telegram et le bot Meshtastic
"""

import json
import time
import asyncio
import subprocess
import tempfile
import os
from pathlib import Path

class MeshtasticInterface:
    def __init__(self):
        self.queue_file = "/tmp/telegram_mesh_queue.json"
        self.response_file = "/tmp/mesh_telegram_response.json"
        
    async def send_command(self, command, user_info):
        """Envoyer une commande au bot Meshtastic"""
        request_data = {
            "id": f"tg_{int(time.time()*1000)}",
            "command": command,
            "source": "telegram",
            "user": {
                "telegram_id": user_info.id,
                "username": user_info.username or user_info.first_name,
                "first_name": user_info.first_name
            },
            "timestamp": time.time()
        }
        
        # Écrire la requête dans le fichier de queue
        try:
            # Lire les requêtes existantes
            requests = []
            if os.path.exists(self.queue_file):
                with open(self.queue_file, 'r') as f:
                    try:
                        requests = json.load(f)
                    except json.JSONDecodeError:
                        requests = []
            
            # Ajouter la nouvelle requête
            requests.append(request_data)
            
            # Écrire toutes les requêtes
            with open(self.queue_file, 'w') as f:
                json.dump(requests, f)
            
            # Attendre la réponse (avec timeout)
            return await self.wait_for_response(request_data["id"], timeout=30)
            
        except Exception as e:
            return f"Erreur interface: {str(e)}"
    
    async def wait_for_response(self, request_id, timeout=30):
        """Attendre la réponse du bot Meshtastic"""
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            try:
                if os.path.exists(self.response_file):
                    with open(self.response_file, 'r') as f:
                        try:
                            responses = json.load(f)
                        except json.JSONDecodeError:
                            responses = []
                    
                    # Chercher notre réponse
                    for i, response in enumerate(responses):
                        if response.get("request_id") == request_id:
                            result = response.get("response", "Pas de réponse")
                            
                            # Supprimer la réponse traitée
                            responses.pop(i)
                            with open(self.response_file, 'w') as f:
                                json.dump(responses, f)
                            
                            return result
                
                await asyncio.sleep(0.5)  # Attendre 500ms
                
            except Exception as e:
                continue
        
        return "⏰ Timeout - pas de réponse du bot Meshtastic"
    
    async def send_echo(self, text, node_id, username):
        """Envoyer un echo via tigrog2"""
        command = f"/echo {text}"
        return await self.send_command(command, type('User', (), {
            'id': node_id,
            'username': username,
            'first_name': username
        })())
    
    async def get_status(self):
        """Obtenir le statut du système"""
        return await self.send_command("/sys", type('User', (), {
            'id': 999999999,
            'username': 'telegram_status',
            'first_name': 'Telegram'
        })())
    
    async def get_nodes(self):
        """Obtenir la liste des nœuds"""
        return await self.send_command("/rx", type('User', (), {
            'id': 999999998,
            'username': 'telegram_nodes', 
            'first_name': 'Telegram'
        })())
EOF

# Créer le service systemd
echo "🔧 Configuration du service systemd..."
sudo tee /etc/systemd/system/telegram-mesh-bot.service > /dev/null << EOF
[Unit]
Description=Telegram Meshtastic Bridge Bot
Documentation=https://github.com/votre-repo/meshtastic-bot
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=pi
WorkingDirectory=/opt/meshtastic-telegram
ExecStart=/usr/bin/python3 /opt/meshtastic-telegram/telegram_bridge.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Variables d'environnement
Environment=PYTHONPATH=/opt/meshtastic-telegram
Environment=LOG_LEVEL=INFO

[Install]
WantedBy=multi-user.target
EOF

# Créer le script de démarrage
echo "🚀 Création du script de gestion..."
cat > manage_telegram_bot.sh << 'EOF'
#!/bin/bash
# Script de gestion du bot Telegram

case "$1" in
    start)
        echo "▶️  Démarrage du bot Telegram..."
        sudo systemctl start telegram-mesh-bot.service
        ;;
    stop)
        echo "⏹️  Arrêt du bot Telegram..."
        sudo systemctl stop telegram-mesh-bot.service
        ;;
    restart)
        echo "🔄 Redémarrage du bot Telegram..."
        sudo systemctl restart telegram-mesh-bot.service
        ;;
    status)
        sudo systemctl status telegram-mesh-bot.service
        ;;
    logs)
        sudo journalctl -u telegram-mesh-bot.service -f
        ;;
    config)
        nano telegram_config.py
        ;;
    test)
        echo "🧪 Test de la configuration..."
        python3 -c "
import telegram_config
if telegram_config.TELEGRAM_BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
    print('❌ Token Telegram non configuré')
else:
    print('✅ Configuration semble OK')
"
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs|config|test}"
        exit 1
        ;;
esac
EOF

chmod +x manage_telegram_bot.sh

# Instructions finales
echo ""
echo "✅ Installation terminée!"
echo ""
echo "📋 Prochaines étapes:"
echo "1. Créer un bot via @BotFather sur Telegram"
echo "2. Configurer le token: nano telegram_config.py"
echo "3. Tester: ./manage_telegram_bot.sh test"
echo "4. Démarrer: ./manage_telegram_bot.sh start"
echo ""
echo "🔧 Commandes utiles:"
echo "• ./manage_telegram_bot.sh status  - État du service"
echo "• ./manage_telegram_bot.sh logs    - Voir les logs"
echo "• ./manage_telegram_bot.sh config  - Éditer config"
echo ""
echo "📁 Fichiers créés dans: /opt/meshtastic-telegram/"
echo ""

# Afficher le guide de création du bot
echo "🤖 Guide création bot Telegram:"
echo "================================"
echo "1. Ouvrir Telegram et chercher @BotFather"
echo "2. Envoyer: /newbot"
echo "3. Choisir un nom: Meshtastic Bridge Bot"
echo "4. Choisir un username: votrebot_mesh_bot"
echo "5. Copier le token et le mettre dans telegram_config.py"
echo "6. Optionnel: /setdescription pour ajouter une description"
echo "7. Optionnel: /setcommands pour définir les commandes"

echo ""
echo "Pressez Entrée pour continuer..."
read
