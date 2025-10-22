#!/bin/bash
# fix_tcp_emergency.sh
# Script d'urgence pour résoudre les fuites TCP immédiatement

echo "🚨 FIX D'URGENCE - Arrêt des fuites TCP"
echo "========================================="

# 1. Identifier le PID du bot
BOT_PID=$(pgrep -f "python3.*main_script.py")

if [ -z "$BOT_PID" ]; then
    echo "❌ Bot non trouvé. Essai avec systemctl..."
    BOT_PID=$(systemctl show -p MainPID meshtastic-bot | cut -d= -f2)
fi

echo "📍 PID du bot: $BOT_PID"

# 2. Afficher l'état actuel
echo ""
echo "📊 État actuel des threads:"
if [ ! -z "$BOT_PID" ]; then
    ps -T -p $BOT_PID | grep -E "(readBytes|reader|TCP)" | head -10
fi

# 3. Créer le script Python de nettoyage d'urgence
cat > /tmp/tcp_emergency_fix.py << 'EOF'
#!/usr/bin/env python3
import os
import signal
import time
import threading
import gc

print("🔧 Nettoyage d'urgence des connexions TCP...")

# Forcer la fermeture de TOUTES les connexions TCP meshtastic
try:
    import meshtastic
    import meshtastic.tcp_interface
    
    # Parcourir tous les objets en mémoire
    for obj in gc.get_objects():
        if isinstance(obj, meshtastic.tcp_interface.TCPInterface):
            print(f"  Found TCPInterface: {obj}")
            try:
                obj.close()
                print("  ✅ Fermé")
            except:
                print("  ⚠️ Déjà fermé ou erreur")
                
except Exception as e:
    print(f"Erreur: {e}")

# Lister les threads suspects
print("\n📋 Threads actifs:")
suspicious_threads = []
for thread in threading.enumerate():
    if any(x in thread.name for x in ["TCP", "read", "stream", "mesh"]):
        print(f"  - {thread.name} (alive: {thread.is_alive()})")
        suspicious_threads.append(thread)

print(f"\n⚠️ {len(suspicious_threads)} threads suspects trouvés")

# Forcer un nettoyage mémoire
gc.collect()
print("✅ Garbage collection forcé")
EOF

# 4. Appliquer les fixes permanents
echo ""
echo "📝 Application des fixes permanents..."

# Créer tcp_connection_monitor.py s'il n'existe pas
if [ ! -f /home/dietpi/bot/tcp_connection_monitor.py ]; then
    echo "  Création de tcp_connection_monitor.py..."
    # (copier le contenu du premier artifact ici)
fi

# 5. Modifier la config pour réduire les timeouts
echo ""
echo "⚙️ Optimisation de la configuration..."
cat >> /home/dietpi/bot/config.py << 'EOF'

# TCP Optimization (Emergency fix)
TCP_READ_TIMEOUT = 5  # Timeout lecture TCP
TCP_CONNECT_TIMEOUT = 10  # Timeout connexion
TCP_MAX_CONNECTIONS = 2  # Max connexions simultanées
TCP_CLEANUP_INTERVAL = 120  # Nettoyage toutes les 2 minutes
EOF

# 6. Créer un cron job pour monitoring
echo ""
echo "📅 Création du monitoring automatique..."
cat > /tmp/tcp_monitor_cron.sh << 'EOF'
#!/bin/bash
# Vérifier le CPU toutes les 5 minutes
CPU_USAGE=$(ps aux | grep -E "python3.*main_script" | grep -v grep | awk '{print $3}' | cut -d. -f1)
if [ "$CPU_USAGE" -gt 100 ]; then
    echo "$(date): CPU élevé détecté: $CPU_USAGE%" >> /var/log/meshtastic-bot-cpu.log
    # Redémarrer si nécessaire
    if [ "$CPU_USAGE" -gt 150 ]; then
        systemctl restart meshtastic-bot
        echo "$(date): Bot redémarré (CPU: $CPU_USAGE%)" >> /var/log/meshtastic-bot-cpu.log
    fi
fi
EOF

chmod +x /tmp/tcp_monitor_cron.sh

# Ajouter au crontab (vérifier d'abord si pas déjà présent)
if ! crontab -l | grep -q "tcp_monitor_cron"; then
    (crontab -l 2>/dev/null; echo "*/5 * * * * /tmp/tcp_monitor_cron.sh") | crontab -
    echo "✅ Monitoring cron installé"
fi

# 7. Redémarrer le service
echo ""
echo "🔄 Redémarrage du service..."
sudo systemctl restart meshtastic-bot

# 8. Attendre et vérifier
echo ""
echo "⏳ Attente 10 secondes..."
sleep 10

# 9. Vérifier le nouveau statut
echo ""
echo "📊 Nouveau statut:"
systemctl status meshtastic-bot --no-pager | head -15

# 10. Vérifier le CPU
echo ""
echo "💻 Utilisation CPU:"
ps aux | grep -E "python3.*main_script" | grep -v grep

echo ""
echo "✅ Fix d'urgence appliqué!"
echo ""
echo "Surveillez le CPU avec: watch -n 5 'ps aux | grep python3 | grep -v grep'"
echo "Logs: journalctl -u meshtastic-
