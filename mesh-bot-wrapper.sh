#!/bin/bash
# Script de gestion du bot Meshtastic

SERVICE_NAME="meshtastic-bot"

case "$1" in
    start)
        echo "🚀 Démarrage du bot Meshtastic..."
        sudo systemctl start $SERVICE_NAME
        sleep 2
        sudo systemctl status $SERVICE_NAME --no-pager
        ;;
    stop)
        echo "⏹️  Arrêt du bot Meshtastic..."
        sudo systemctl stop $SERVICE_NAME
        sleep 1
        echo "✅ Bot arrêté"
        ;;
    restart)
        echo "🔄 Redémarrage du bot Meshtastic..."
        sudo systemctl restart $SERVICE_NAME
        sleep 2
        sudo systemctl status $SERVICE_NAME --no-pager
        ;;
    status)
        echo "📊 État du bot Meshtastic:"
        sudo systemctl status $SERVICE_NAME --no-pager
        ;;
    debug)
        echo "🔧 Mode debug interactif..."
        echo "⚠️  Cela va arrêter le service s'il tourne"
        sudo systemctl stop $SERVICE_NAME 2>/dev/null || true
        sleep 2
        echo "🚀 Lancement en mode debug..."
        python3 /home/dietpi/bot/main_bot.py --debug
        ;;
    run)
        echo "🔧 Mode normal interactif..."
        echo "⚠️  Cela va arrêter le service s'il tourne" 
        sudo systemctl stop $SERVICE_NAME 2>/dev/null || true
        sleep 2
        echo "🚀 Lancement en mode normal..."
        python3 /home/dietpi/debug_mesh_bot.py
        ;;
    logs-conversations)
        echo "📋 Logs des conversations (Ctrl+C pour quitter):"
        sudo journalctl -u $SERVICE_NAME -f | grep --line-buffered "\[CONVERSATION\]"
        ;;
    logs-conv-today)
        echo "📋 Conversations d'aujourd'hui:"
        sudo journalctl -u $SERVICE_NAME --since today --no-pager | grep "\[CONVERSATION\]"
        ;;
    logs-conv-stats)
        echo "📊 Statistiques des conversations:"
        echo ""
        echo "📈 Conversations totales:"
        sudo journalctl -u $SERVICE_NAME --no-pager | grep -c "QUERY:" || echo "0"
        
        echo ""
        echo "📅 Conversations aujourd'hui:"
        sudo journalctl -u $SERVICE_NAME --since today --no-pager | grep -c "QUERY:" || echo "0"
        
        echo ""
        echo "⏱️  Temps de traitement récents (10 derniers):"
        sudo journalctl -u $SERVICE_NAME --no-pager | grep "PROCESSING_TIME:" | tail -10
        
        echo ""
        echo "👥 Utilisateurs récents (10 derniers):"
        sudo journalctl -u $SERVICE_NAME --no-pager | grep "USER:" | tail -10 | sed 's/.*USER: //'
        ;;
    logs-conv-search)
        if [ -z "$2" ]; then
            echo "Usage: $0 logs-conv-search <terme_recherche>"
            exit 1
        fi
        echo "🔍 Recherche '$2' dans les conversations:"
        sudo journalctl -u $SERVICE_NAME --no-pager | grep -A5 -B5 -i "$2" | grep "\[CONVERSATION\]"
        ;;
    logs-errors-only)
        echo "📋 Erreurs uniquement:"
        sudo journalctl -u $SERVICE_NAME --no-pager | grep "\[ERROR\]"
        ;;
    logs-info-only)
        echo "📋 Informations uniquement:"
        sudo journalctl -u $SERVICE_NAME --no-pager | grep "\[INFO\]"
        ;;
    logs)
        echo "📋 Logs du bot (Ctrl+C pour quitter):"
        sudo journalctl -u $SERVICE_NAME -f
        ;;
    logs-today)
        echo "📋 Logs d'aujourd'hui:"
        sudo journalctl -u $SERVICE_NAME --since today --no-pager
        ;;
    logs-errors)
        echo "📋 Logs d'erreurs récentes:"
        sudo journalctl -u $SERVICE_NAME -p err --since "1 hour ago" --no-pager
        ;;
    enable)
        echo "🔧 Activation du démarrage automatique..."
        sudo systemctl enable $SERVICE_NAME
        echo "✅ Le bot démarrera automatiquement au boot"
        ;;
    disable)
        echo "🔧 Désactivation du démarrage automatique..."
        sudo systemctl disable $SERVICE_NAME
        echo "✅ Le bot ne démarrera plus automatiquement"
        ;;
    install)
        echo "📦 Installation du service..."
        if [ -f "./install_service.sh" ]; then
            bash ./install_service.sh
        else
            echo "❌ Fichier install_service.sh introuvable"
            exit 1
        fi
        ;;
    uninstall)
        echo "🗑️  Désinstallation du service..."
        sudo systemctl stop $SERVICE_NAME 2>/dev/null || true
        sudo systemctl disable $SERVICE_NAME 2>/dev/null || true
        sudo rm -f /etc/systemd/system/$SERVICE_NAME.service
        sudo systemctl daemon-reload
        echo "✅ Service désinstallé"
        ;;
    test-logs)
        echo "🧪 Test des logs systemd..."
        echo "Génération de logs de test..."
        python3 /home/dietpi/test_logs.py
        sleep 2
        echo ""
        echo "📋 Vérification dans journalctl (5 dernières secondes):"
        sudo journalctl -u $SERVICE_NAME --since "5 seconds ago" --no-pager
        echo ""
        echo "💡 Si vous ne voyez pas les logs ci-dessus, il y a un problème de configuration"
        ;;
    test-connection)
        echo "🧪 Test de connexion au nœud Meshtastic..."
        if [ -c "/dev/ttyACM0" ]; then
            echo "✅ Port série trouvé"
            timeout 10s python3 -c "
import meshtastic.serial_interface
import time
print('Tentative de connexion...')
try:
    interface = meshtastic.serial_interface.SerialInterface('/dev/ttyACM0')
    time.sleep(2)
    print('✅ Connexion réussie')
    interface.close()
except Exception as e:
    print(f'❌ Erreur: {e}')
"
        else
            echo "❌ Port série /dev/ttyACM0 introuvable"
        fi
        ;;
    *)
        echo "🤖 Gestionnaire du Bot Meshtastic-Llama"
        echo "========================================"
        echo ""
        echo "Usage: $0 {commande}"
        echo ""
        echo "Commandes de service:"
        echo "  start         Démarrer le bot"
        echo "  stop          Arrêter le bot"  
        echo "  restart       Redémarrer le bot"
        echo "  status        Afficher l'état"
        echo "  enable        Activer démarrage auto"
        echo "  disable       Désactiver démarrage auto"
        echo ""
        echo "Commandes de développement:"
        echo "  debug         Lancer en mode debug interactif"
        echo "  run           Lancer en mode normal interactif"
        echo ""
        echo "Commandes de logs:"
        echo "  logs                  Logs système en temps réel"
        echo "  logs-today            Logs système d'aujourd'hui"
        echo "  logs-errors           Logs d'erreurs récentes"
        echo "  logs-conversations    Logs des conversations en temps réel"
        echo "  logs-conv-today       Conversations d'aujourd'hui"
        echo "  logs-conv-stats       Statistiques des conversations"
        echo "  logs-conv-search <terme>  Rechercher dans les conversations"
        echo "  logs-errors-only      Erreurs seulement"
        echo "  logs-info-only        Informations seulement"
        echo "              Logs système en temps réel"
        echo "  logs-today        Logs système d'aujourd'hui"
        echo "  logs-errors       Logs d'erreurs récentes"
        echo "  logs-conversations Logs des conversations en temps réel"
        echo "  logs-conv-today   Conversations d'aujourd'hui"
        echo "  logs-conv-stats   Statistiques des conversations"
        echo "  clean-logs        Nettoyer les logs de conversations"
        echo ""
        echo "Commandes d'installation:"
        echo "  install       Installer le service"
        echo "  uninstall     Désinstaller le service"
        echo ""
        echo "Commandes de diagnostic:"
        echo "  test-connection       Tester la connexion Meshtastic"
        echo "  test-logs            Tester les logs systemd"
        echo ""
        echo "Exemples:"
        echo "  $0 start"
        echo "  $0 logs"
        echo "  $0 status"
        exit 1
        ;;
esac
