#!/bin/bash
# Diagnostic et correction du service systemd

echo "🔧 Diagnostic et correction du service meshtastic-bot"

SERVICE_NAME="meshtastic-bot"

# 1. Arrêter le service existant
echo "⏹️ Arrêt du service existant..."
sudo systemctl stop $SERVICE_NAME 2>/dev/null || true

# 2. Vérifier la configuration actuelle
echo "🔍 Configuration actuelle:"
if sudo systemctl cat $SERVICE_NAME >/dev/null 2>&1; then
    sudo systemctl cat $SERVICE_NAME
    echo ""
else
    echo "❌ Service non trouvé"
fi

# 3. Supprimer l'ancien service
echo "🗑️ Suppression de l'ancien service..."
sudo systemctl disable $SERVICE_NAME 2>/dev/null || true
sudo rm -f /etc/systemd/system/$SERVICE_NAME.service
sudo systemctl daemon-reload

# 4. Créer une version ultra-simple pour tester
echo "📝 Création d'un service de test simple..."
sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null << 'EOF'
[Unit]
Description=Bot Meshtastic-Llama
After=network.target

[Service]
Type=simple
User=dietpi
Group=dialout
WorkingDirectory=/home/dietpi
ExecStart=/usr/bin/python3 /home/dietpi/debug_mesh_bot.py --test-logs
Restart=no
RemainAfterExit=yes

# Logs - version simplifiée
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# 5. Recharger et tester
echo "🔄 Rechargement systemd..."
sudo systemctl daemon-reload

echo "✅ Service créé. Test du logging..."
sudo systemctl start $SERVICE_NAME

sleep 3

echo "📋 Vérification des logs:"
sudo journalctl -u $SERVICE_NAME --no-pager --since "10 seconds ago"

echo ""
echo "🔍 Recherche spécifique:"
sudo journalctl -u $SERVICE_NAME --no-pager | grep -E "\[INFO\]|\[ERROR\]|\[CONVERSATION\]" || echo "❌ Aucun log trouvé"

echo ""
echo "📊 Statut du service:"
sudo systemctl status $SERVICE_NAME --no-pager

# 6. Si ça marche, recréer le vrai service
read -p "Les logs apparaissent-ils ci-dessus ? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "✅ Logs détectés! Création du service final..."
    
    sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null << 'EOF'
[Unit]
Description=Bot Meshtastic-Llama
After=network.target
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=dietpi
Group=dialout
WorkingDirectory=/home/dietpi
ExecStart=/usr/bin/python3 /home/dietpi/debug_mesh_bot.py --quiet
Restart=always
RestartSec=10

# Variables d'environnement
Environment=PATH=/usr/local/bin:/usr/bin:/bin
Environment=PYTHONPATH=/home/dietpi
Environment=HOME=/home/dietpi

# Gestion des logs
StandardOutput=journal
StandardError=journal
SyslogIdentifier=meshtastic-bot

# Sécurité basique
NoNewPrivileges=true
SupplementaryGroups=dialout tty

# Limites de ressources
LimitNOFILE=1024
MemoryMax=512M

[Install]
WantedBy=multi-user.target
EOF
    
    sudo systemctl daemon-reload
    sudo systemctl enable $SERVICE_NAME
    sudo systemctl restart $SERVICE_NAME
    
    echo "🚀 Service final installé et démarré"
    echo "📋 Vérifiez les logs avec:"
    echo "   sudo journalctl -u $SERVICE_NAME -f"
    
else
    echo "❌ Problème de logging détecté"
    echo "💡 Vérifications supplémentaires nécessaires:"
    echo "   1. sudo systemctl status systemd-journald"
    echo "   2. sudo journalctl --verify"
    echo "   3. ls -la /var/log/journal/"
fi
