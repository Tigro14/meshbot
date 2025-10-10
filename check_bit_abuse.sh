#!/bin/bash
# Script de détection d'abus du bot Telegram
# Analyse les logs pour identifier comportements suspects

echo "=================================================="
echo "🔍 ANALYSE LOGS BOT - DÉTECTION D'ABUS"
echo "=================================================="
echo ""

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Analyser les dernières 24h de logs
echo "📅 Analyse des 24 dernières heures..."
echo ""

# 1. Compter les erreurs Telegram
echo "1️⃣  ERREURS TELEGRAM:"
TELEGRAM_ERRORS=$(journalctl -u meshtastic-bot --since "24 hours ago" | grep -i "telegram.error" | wc -l)
echo "   Total erreurs: $TELEGRAM_ERRORS"

if [ $TELEGRAM_ERRORS -gt 100 ]; then
    echo -e "   ${RED}⚠️  CRITIQUE : >100 erreurs Telegram${NC}"
    echo "   → Probable cause de rate limiting"
elif [ $TELEGRAM_ERRORS -gt 50 ]; then
    echo -e "   ${YELLOW}⚠️  ÉLEVÉ : >50 erreurs${NC}"
else
    echo -e "   ${GREEN}✅ Normal${NC}"
fi
echo ""

# 2. Compter les timeouts
echo "2️⃣  TIMEOUTS:"
TIMEOUT_COUNT=$(journalctl -u meshtastic-bot --since "24 hours ago" | grep -i "timed out\|timeout" | wc -l)
echo "   Total timeouts: $TIMEOUT_COUNT"

if [ $TIMEOUT_COUNT -gt 50 ]; then
    echo -e "   ${RED}⚠️  CRITIQUE : >50 timeouts${NC}"
    echo "   → Connexion instable ou Telegram bloque"
elif [ $TIMEOUT_COUNT -gt 20 ]; then
    echo -e "   ${YELLOW}⚠️  ÉLEVÉ : >20 timeouts${NC}"
else
    echo -e "   ${GREEN}✅ Normal${NC}"
fi
echo ""

# 3. Compter les connexions
echo "3️⃣  CONNEXIONS TELEGRAM:"
CONNECTIONS=$(journalctl -u meshtastic-bot --since "24 hours ago" | grep -i "polling\|updater" | wc -l)
echo "   Tentatives connexion: $CONNECTIONS"

if [ $CONNECTIONS -gt 1000 ]; then
    echo -e "   ${RED}⚠️  SUSPECT : >1000 tentatives${NC}"
    echo "   → Possible boucle de reconnexion"
elif [ $CONNECTIONS -gt 500 ]; then
    echo -e "   ${YELLOW}⚠️  ÉLEVÉ : >500 tentatives${NC}"
else
    echo -e "   ${GREEN}✅ Normal${NC}"
fi
echo ""

# 4. Compter les messages envoyés
echo "4️⃣  MESSAGES ENVOYÉS:"
SENT_MESSAGES=$(journalctl -u meshtastic-bot --since "24 hours ago" | grep -i "send_message\|sendText" | wc -l)
echo "   Messages envoyés: $SENT_MESSAGES"

if [ $SENT_MESSAGES -gt 2000 ]; then
    echo -e "   ${RED}⚠️  SUSPECT : >2000 messages/jour${NC}"
    echo "   → Au-dessus limite Telegram (30/s = 2592000/jour théorique)"
elif [ $SENT_MESSAGES -gt 1000 ]; then
    echo -e "   ${YELLOW}⚠️  ÉLEVÉ : >1000 messages/jour${NC}"
else
    echo -e "   ${GREEN}✅ Normal${NC}"
fi
echo ""

# 5. Détecter les patterns de boucle
echo "5️⃣  PATTERNS SUSPECTS:"
RESTART_LOOPS=$(journalctl -u meshtastic-bot --since "24 hours ago" | grep -i "démarrage\|start\|started" | wc -l)
echo "   Redémarrages: $RESTART_LOOPS"

if [ $RESTART_LOOPS -gt 50 ]; then
    echo -e "   ${RED}⚠️  CRITIQUE : Bot redémarre trop souvent${NC}"
    echo "   → Probable crash loop"
elif [ $RESTART_LOOPS -gt 10 ]; then
    echo -e "   ${YELLOW}⚠️  Plusieurs redémarrages${NC}"
else
    echo -e "   ${GREEN}✅ Normal${NC}"
fi
echo ""

# 6. Dernières erreurs
echo "6️⃣  DERNIÈRES ERREURS (10):"
echo "=================================================="
journalctl -u meshtastic-bot --since "24 hours ago" | grep -i "error\|exception" | tail -10 | sed 's/^/   /'
echo ""

# 7. Rate limiting détecté ?
echo "7️⃣  RATE LIMITING:"
RATE_LIMIT=$(journalctl -u meshtastic-bot --since "24 hours ago" | grep -i "429\|too many\|rate limit" | wc -l)
echo "   Détections: $RATE_LIMIT"

if [ $RATE_LIMIT -gt 0 ]; then
    echo -e "   ${RED}⚠️  CONFIRMÉ : Rate limiting détecté${NC}"
    echo "   → Telegram a bloqué temporairement le bot"
    echo ""
    echo "   Dernières détections:"
    journalctl -u meshtastic-bot --since "24 hours ago" | grep -i "429\|too many\|rate limit" | tail -5 | sed 's/^/      /'
else
    echo -e "   ${GREEN}✅ Aucun rate limiting détecté${NC}"
fi
echo ""

# 8. Verdict global
echo "=================================================="
echo "🎯 VERDICT GLOBAL"
echo "=================================================="

SCORE=0
[ $TELEGRAM_ERRORS -gt 100 ] && SCORE=$((SCORE + 3))
[ $TELEGRAM_ERRORS -gt 50 ] && SCORE=$((SCORE + 1))
[ $TIMEOUT_COUNT -gt 50 ] && SCORE=$((SCORE + 3))
[ $TIMEOUT_COUNT -gt 20 ] && SCORE=$((SCORE + 1))
[ $CONNECTIONS -gt 1000 ] && SCORE=$((SCORE + 2))
[ $SENT_MESSAGES -gt 2000 ] && SCORE=$((SCORE + 2))
[ $RESTART_LOOPS -gt 50 ] && SCORE=$((SCORE + 3))
[ $RATE_LIMIT -gt 0 ] && SCORE=$((SCORE + 5))

if [ $SCORE -ge 8 ]; then
    echo -e "${RED}🔴 CRITIQUE${NC}"
    echo "   Le bot a probablement été rate-limité ou banni"
    echo ""
    echo "💡 ACTIONS RECOMMANDÉES:"
    echo "   1. Arrêter le bot: sudo systemctl stop meshtastic-bot"
    echo "   2. Attendre 6-24 heures"
    echo "   3. Augmenter poll_interval à 60s"
    echo "   4. Vérifier le code pour boucles infinies"
    echo "   5. Contacter @BotSupport si ban permanent"
elif [ $SCORE -ge 4 ]; then
    echo -e "${YELLOW}⚠️  AVERTISSEMENT${NC}"
    echo "   Comportement suspect détecté"
    echo ""
    echo "💡 ACTIONS RECOMMANDÉES:"
    echo "   1. Augmenter poll_interval à 60s"
    echo "   2. Réduire la fréquence des commandes"
    echo "   3. Surveiller les logs"
else
    echo -e "${GREEN}✅ NORMAL${NC}"
    echo "   Pas de comportement abusif détecté"
    echo ""
    echo "💡 Le timeout vient probablement de:"
    echo "   - Connexion réseau lente"
    echo "   - Timeouts trop courts (augmenter à 120s)"
fi
echo ""

# 9. Informations supplémentaires
echo "=================================================="
echo "ℹ️  INFORMATIONS SUPPLÉMENTAIRES"
echo "=================================================="
echo "Pour plus de détails:"
echo "  • Voir tous les logs: journalctl -u meshtastic-bot -n 1000"
echo "  • Logs erreurs: journalctl -u meshtastic-bot | grep ERROR"
echo "  • Logs temps réel: journalctl -u meshtastic-bot -f"
echo ""
echo "Limites Telegram (officielles):"
echo "  • 30 messages/seconde par bot"
echo "  • 20 appels getUpdates/minute"
echo "  • Bans temporaires si abus"
echo ""
