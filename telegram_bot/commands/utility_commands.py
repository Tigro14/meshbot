#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Commandes utilitaires Telegram : power, weather, graphs
"""

import time
from telegram import Update
from telegram.ext import ContextTypes
from telegram_bot.command_base import TelegramCommandBase
from utils import info_print, error_print
import asyncio

# Mapping département -> nom ville (pour les plus courants)
DEPARTMENT_NAMES = {
    '75': 'Paris',
    '13': 'Marseille',
    '69': 'Lyon',
    '31': 'Toulouse',
    '06': 'Nice',
    '44': 'Nantes',
    '67': 'Strasbourg',
    '33': 'Bordeaux',
    '59': 'Lille',
    '34': 'Montpellier',
    '25': 'Doubs',
    '38': 'Isère',
    '76': 'Seine-Maritime',
    '57': 'Moselle',
    '35': 'Rennes',
}

# Emoji mapping pour les niveaux de vigilance
VIGILANCE_EMOJI_MAP = {
    'Vert': '✅',
    'Jaune': '⚠️',
    'Orange': '🟠',
    'Rouge': '🔴'
}


class UtilityCommands(TelegramCommandBase):
    """Gestionnaire des commandes utilitaires Telegram"""

    async def power_command(
            self,
            update: Update,
            context: ContextTypes.DEFAULT_TYPE):
        """Commande /power avec graphiques d'historique"""
        user = update.effective_user
        info_print(f"📱 Telegram /power: {user.username}")

        # Extraire le nombre d'heures (optionnel, défaut 24)
        hours = 24
        if context.args and len(context.args) > 0:
            try:
                hours = int(context.args[0])
                hours = max(1, min(48, hours))  # Entre 1 et 48 heures
            except ValueError:
                hours = 24

        # Message 1 : Données actuelles
        response_current = await asyncio.to_thread(
            self.message_handler.esphome_client.parse_esphome_data
        )
        await update.effective_message.reply_text(f"⚡ Power:\n{response_current}")

        # Message 2 : Graphiques d'historique
        response_graphs = await asyncio.to_thread(
            self.message_handler.esphome_client.get_history_graphs,
            hours
        )
        await update.effective_message.reply_text(response_graphs)

    async def weather_command(self, update: Update,
                              context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /weather [rain|astro] [ville] [days]

        Exemples:
        /weather → Météo locale
        /weather Paris → Météo Paris
        /weather rain → Pluie locale aujourd'hui
        /weather rain 3 → Pluie locale 3 jours
        /weather rain Paris 3 → Pluie Paris 3 jours
        /weather astro → Infos astronomiques locales
        /weather astro Paris → Infos astronomiques Paris
        """
        user = update.effective_user
        # Parser les arguments: [rain|astro|blitz|vigi] [ville] [days]
        subcommand = None
        location = None
        days = 1  # Par défaut: aujourd'hui seulement

        if context.args and len(context.args) > 0:
            # Vérifier si le premier argument est une sous-commande
            if context.args[0].lower() in ['rain', 'astro', 'blitz', 'vigi']:
                subcommand = context.args[0].lower()
                remaining = context.args[1:]  # Arguments après la sous-commande

                # Le dernier argument est un nombre de jours ?
                if remaining and remaining[-1].isdigit():
                    days_arg = int(remaining[-1])
                    if days_arg in [1, 2, 3]:
                        days = days_arg
                        remaining = remaining[:-1]

                # Ce qui reste est la ville (peut avoir des espaces)
                if remaining:
                    location = ' '.join(remaining)
            else:
                # Sinon c'est directement la ville
                location = ' '.join(context.args)

        # Si "help"/"aide", afficher l'aide
        if location and location.lower() in ['help', 'aide', '?']:
            help_text = (
                "🌤️ /weather [rain|astro|blitz|vigi] [ville] [days]\n\n"
                "Exemples:\n"
                "/weather → Météo locale\n"
                "/weather Paris → Météo Paris\n"
                "/weather rain → Pluie aujourd'hui\n"
                "/weather rain 2 → Pluie auj+demain\n"
                "/weather rain 3 → Pluie 3 jours\n"
                "/weather rain Paris 2 → Paris 2j\n"
                "/weather astro → Infos astro\n"
                "/weather astro Paris → Astro Paris\n"
                "/weather blitz → Éclairs détectés\n"
                "/weather vigi → Info VIGILANCE"
            )
            await update.effective_message.reply_text(help_text)
            return

        # Log avec détails
        cmd_str = f"/weather {subcommand or ''} {location or ''} {days if subcommand == 'rain' else ''}".strip()
        info_print(f"📱 Telegram {cmd_str}: {user.username}")

        # Utiliser les modules utils.weather appropriés
        from utils_weather import get_weather_data, get_rain_graph, get_weather_astro
        import time

        try:
            if subcommand == 'rain':
                # Graphe de précipitations (Telegram: 22h compact comme Mesh, 3 lignes, 44 chars, cache SQLite 5min)
                traffic_monitor = self.telegram.message_handler.traffic_monitor if hasattr(self.telegram.message_handler, 'traffic_monitor') else None
                persistence = traffic_monitor.persistence if traffic_monitor else None
                weather_data = await asyncio.to_thread(get_rain_graph, location, days, max_hours=22, compact_mode=True, persistence=persistence)

                # Découper et envoyer jour par jour (1 ou 3 messages)
                day_messages = weather_data.split('\n\n')
                for i, day_msg in enumerate(day_messages):
                    # Envelopper dans <pre> pour police monospace (alignement sparklines)
                    formatted_msg = f"<pre>{day_msg}</pre>"
                    await update.effective_message.reply_text(formatted_msg, parse_mode='HTML')
                    # Petit délai entre les messages
                    if i < len(day_messages) - 1:
                        await asyncio.sleep(1)

            elif subcommand == 'astro':
                # Informations astronomiques (cache SQLite 5min)
                traffic_monitor = self.telegram.message_handler.traffic_monitor if hasattr(self.telegram.message_handler, 'traffic_monitor') else None
                persistence = traffic_monitor.persistence if traffic_monitor else None
                weather_data = await asyncio.to_thread(get_weather_astro, location, persistence=persistence)
                await update.effective_message.reply_text(weather_data)

            elif subcommand == 'blitz':
                # Éclairs détectés via Blitzortung
                # Accéder au blitz_monitor via le message_handler
                blitz_monitor = None
                if hasattr(self.telegram.message_handler, 'blitz_monitor'):
                    blitz_monitor = self.telegram.message_handler.blitz_monitor

                if blitz_monitor and blitz_monitor.enabled:
                    # Récupérer les éclairs récents
                    recent_strikes = blitz_monitor.get_recent_strikes()

                    if recent_strikes:
                        # Formater le rapport (détaillé pour Telegram)
                        weather_data = blitz_monitor._format_report(recent_strikes, compact=False)
                    else:
                        weather_data = f"⚡ Aucun éclair détecté dans les {blitz_monitor.window_minutes} dernières minutes\n"
                        weather_data += f"Rayon de surveillance: {blitz_monitor.radius_km}km"

                    await update.effective_message.reply_text(weather_data)
                else:
                    await update.effective_message.reply_text("⚡ Surveillance des éclairs désactivée")

            elif subcommand == 'vigi':
                # Documentation du système VIGILANCE Météo-France
                vigi_info = """📋 **VIGILANCE Météo-France**

**Surveillance automatique des alertes:**
• Départements configurés dans config.py
• Vérification automatique toutes les 15 minutes
• Niveaux de vigilance: Vert, Jaune, Orange, Rouge
• Alerte automatique envoyée si Orange ou Rouge détecté

**Types de risques surveillés:**
• Vent violent
• Pluie-inondation
• Orages
• Neige/Verglas
• Canicule
• Grand froid
• Avalanches
• Vagues-submersion

**Configuration:**
Variables `VIGILANCE_*` dans config.py
- `VIGILANCE_ENABLED`: Activer/désactiver
- `VIGILANCE_DEPARTEMENT`: Numéro département (ex: '75')
- `VIGILANCE_CHECK_INTERVAL`: Intervalle de vérif (secondes)
- `VIGILANCE_ALERT_LEVELS`: Niveaux déclenchant alerte

**Voir status actuel:** /sys"""

                await update.effective_message.reply_text(vigi_info, parse_mode='Markdown')

            else:
                # Météo normale
                weather_data = await asyncio.to_thread(get_weather_data, location)
                await update.effective_message.reply_text(weather_data)

        except Exception as e:
            error_print(f"Erreur /weather: {e}")
            await update.effective_message.reply_text(f"❌ Erreur météo: {str(e)[:80]}")

    async def rain_command(self, update: Update,
                           context: ContextTypes.DEFAULT_TYPE):
        """
        Raccourci pour /weather rain [ville] [days]

        Exemples:
        /rain → Pluie locale aujourd'hui
        /rain Paris → Pluie Paris aujourd'hui
        /rain Paris 3 → Pluie Paris 3 jours
        """
        # Injecter 'rain' comme premier argument pour weather_command
        if context.args:
            context.args.insert(0, 'rain')
        else:
            context.args = ['rain']

        # Appeler weather_command qui traitera 'rain' comme sous-commande
        await self.weather_command(update, context)

    async def graphs_command(
            self,
            update: Update,
            context: ContextTypes.DEFAULT_TYPE):
        """Commande /graphs pour afficher uniquement les graphiques d'historique"""
        user = update.effective_user
        # Extraire le nombre d'heures (optionnel, défaut 24)
        hours = 24
        if context.args and len(context.args) > 0:
            try:
                hours = int(context.args[0])
                hours = max(1, min(48, hours))  # Entre 1 et 48 heures
            except ValueError:
                hours = 24

        info_print(f"📱 Telegram /graphs {hours}h: {user.username}")

        # Générer les graphiques
        response = await asyncio.to_thread(
            self.message_handler.esphome_client.get_history_graphs,
            hours
        )
        await update.effective_message.reply_text(response)

    async def graph_command(
            self,
            update: Update,
            context: ContextTypes.DEFAULT_TYPE):
        """Commande /graph - À définir selon vos besoins"""
        user = update.effective_user
        info_print(f"📱 Telegram /graph: {user.username}")

        # TODO: Implémenter selon vos besoins
        await update.effective_message.reply_text("🚧 Commande /graph en cours d'implémentation")

    async def vigi_command(
            self,
            update: Update,
            context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /vigi - Afficher la configuration et l'état de la vigilance Météo-France
        
        Affiche:
        - Configuration (département, intervalle, throttle, niveaux d'alerte)
        - État actuel (niveau de vigilance, dernière vérification, dernière alerte)
        """
        user = update.effective_user
        info_print(f"📱 Telegram /vigi: {user.username}")

        # Import config avec valeurs par défaut pour chaque variable
        try:
            import config
            VIGILANCE_ENABLED = getattr(config, 'VIGILANCE_ENABLED', False)
            VIGILANCE_DEPARTEMENT = getattr(config, 'VIGILANCE_DEPARTEMENT', None)
            VIGILANCE_CHECK_INTERVAL = getattr(config, 'VIGILANCE_CHECK_INTERVAL', None)
            VIGILANCE_ALERT_THROTTLE = getattr(config, 'VIGILANCE_ALERT_THROTTLE', None)
            VIGILANCE_ALERT_LEVELS = getattr(config, 'VIGILANCE_ALERT_LEVELS', None)
        except ImportError:
            # Module config non disponible
            VIGILANCE_ENABLED = False
            VIGILANCE_DEPARTEMENT = None
            VIGILANCE_CHECK_INTERVAL = None
            VIGILANCE_ALERT_THROTTLE = None
            VIGILANCE_ALERT_LEVELS = None

        # Si la vigilance est désactivée
        if not VIGILANCE_ENABLED:
            response = "🌦️ VIGILANCE MÉTÉO-FRANCE\n\n❌ Surveillance désactivée"
            await update.effective_message.reply_text(response)
            return

        # Construire la section configuration
        lines = ["🌦️ VIGILANCE MÉTÉO-FRANCE", ""]
        lines.append("📍 Configuration:")

        # Accéder au vigilance_monitor via le message_handler (do this early to get dept)
        vigilance_monitor = self._get_vigilance_monitor()
        
        # Département - prioritize from vigilance_monitor, fallback to config
        # Handle None, empty string, or string "None"
        dept_value = None
        if vigilance_monitor and vigilance_monitor.departement:
            dept_value = vigilance_monitor.departement
        elif VIGILANCE_DEPARTEMENT and str(VIGILANCE_DEPARTEMENT).lower() != 'none':
            dept_value = str(VIGILANCE_DEPARTEMENT)
        
        if dept_value:
            dept_str = dept_value
            if dept_value in DEPARTMENT_NAMES:
                dept_str = f"{dept_value} ({DEPARTMENT_NAMES[dept_value]})"
            lines.append(f"• Département: {dept_str}")
        else:
            lines.append("• Département: Non configuré")

        # Intervalle de vérification (en heures)
        if VIGILANCE_CHECK_INTERVAL:
            interval_hours = VIGILANCE_CHECK_INTERVAL / 3600
            if interval_hours >= 1:
                lines.append(f"• Vérification: toutes les {int(interval_hours)}h")
            else:
                interval_minutes = VIGILANCE_CHECK_INTERVAL / 60
                lines.append(f"• Vérification: toutes les {int(interval_minutes)}min")

        # Throttle alertes
        if VIGILANCE_ALERT_THROTTLE:
            throttle_hours = VIGILANCE_ALERT_THROTTLE / 3600
            if throttle_hours >= 1:
                lines.append(f"• Throttle alertes: {int(throttle_hours)}h")
            else:
                throttle_minutes = VIGILANCE_ALERT_THROTTLE / 60
                lines.append(f"• Throttle alertes: {int(throttle_minutes)}min")

        # Niveaux d'alerte
        if VIGILANCE_ALERT_LEVELS:
            levels_str = ', '.join(VIGILANCE_ALERT_LEVELS)
            lines.append(f"• Niveaux d'alerte: {levels_str}")

        lines.append("")
        lines.append("📊 État actuel:")

        # vigilance_monitor already fetched earlier for département
        if vigilance_monitor and vigilance_monitor.last_color:
            # Niveau actuel
            emoji = VIGILANCE_EMOJI_MAP.get(vigilance_monitor.last_color, '🌦️')
            lines.append(f"{emoji} Niveau: {vigilance_monitor.last_color.upper()}")

            # Dernière vérification
            if vigilance_monitor.last_check_time > 0:
                elapsed = int(time.time() - vigilance_monitor.last_check_time)
                time_str = self._format_elapsed_time(elapsed)
                lines.append(f"🕐 Dernière vérif: {time_str}")

            # Dernière alerte
            if vigilance_monitor.last_alert_time > 0:
                elapsed = int(time.time() - vigilance_monitor.last_alert_time)
                time_str = self._format_elapsed_time(elapsed)
                lines.append(f"📢 Dernière alerte: {time_str}")
        elif vigilance_monitor:
            lines.append("⏳ Pas encore initialisé")
        else:
            lines.append("⏳ Moniteur non disponible")

        response = '\n'.join(lines)
        await update.effective_message.reply_text(response)

    def _get_vigilance_monitor(self):
        """
        Obtenir l'instance du moniteur de vigilance
        
        Returns:
            VigilanceMonitor: Instance du moniteur ou None si non disponible
        """
        try:
            return self.telegram.message_handler.router.utility_handler.vigilance_monitor
        except AttributeError:
            return None

    def _format_elapsed_time(self, seconds: int) -> str:
        """
        Formater un temps écoulé en format lisible
        
        Args:
            seconds: Temps écoulé en secondes
            
        Returns:
            str: Temps formaté (ex: "il y a 15min", "il y a 2h")
        """
        if seconds < 60:
            return f"il y a {seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"il y a {minutes}min"
        else:
            hours = seconds // 3600
            return f"il y a {hours}h"
