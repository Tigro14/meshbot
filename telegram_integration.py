#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module d'intégration Telegram dans le bot Meshtastic - VERSION REFACTORISÉE
Gère l'API Telegram avec architecture modulaire
"""

import time
import threading
import traceback
import asyncio
from config import *
from utils import *

# Import Telegram (optionnel)
try:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    info_print("Module python-telegram-bot non installé")

# Import des gestionnaires de commandes
from telegram_bot.commands import (
    BasicCommands,
    SystemCommands,
    NetworkCommands,
    StatsCommands,
    UtilityCommands,
    MeshCommands,
    AICommands,
    TraceCommands,
    AdminCommands,
    DBCommandsTelegram
)

# Import de la logique métier pour les stats (alias pour éviter conflit)
from handlers.command_handlers.stats_commands import StatsCommands as BusinessStatsCommands
from handlers.command_handlers.unified_stats import UnifiedStatsCommands

# Import des gestionnaires spécialisés
from telegram_bot.traceroute_manager import TracerouteManager
from telegram_bot.alert_manager import AlertManager


class TelegramIntegration:
    """
    Classe principale d'intégration Telegram
    Orchestre tous les gestionnaires de commandes
    """

    def __init__(self, message_handler, node_manager, context_manager):
        """
        Initialiser l'intégration Telegram

        Args:
            message_handler: Gestionnaire de messages Meshtastic
            node_manager: Gestionnaire de nœuds
            context_manager: Gestionnaire de contexte pour l'IA
        """
        if not TELEGRAM_AVAILABLE:
            raise ImportError(
                "python-telegram-bot requis. Installez: pip3 install python-telegram-bot")

        # Références aux composants principaux
        self.message_handler = message_handler
        self.node_manager = node_manager
        self.context_manager = context_manager

        # État du bot
        self.running = False
        self.telegram_thread = None
        self.application = None
        self.loop = None

        # Initialiser les gestionnaires de commandes (APRÈS que self soit complet)
        self._init_command_handlers()

        # Initialiser les gestionnaires spécialisés
        self.traceroute_manager = TracerouteManager(self)
        self.alert_manager = AlertManager(self)

        info_print("✅ TelegramIntegration initialisé avec architecture modulaire")

    def _init_command_handlers(self):
        """Initialiser tous les gestionnaires de commandes"""
        # IMPORTANT: Ordre de création respecte les dépendances
        # Les commandes sans dépendances d'abord
        self.basic_commands = BasicCommands(self)
        self.system_commands = SystemCommands(self)

        # Créer l'instance de la logique métier pour les stats
        # (utilisée par les commandes Telegram pour accéder aux méthodes de génération de rapports)
        self.business_stats = BusinessStatsCommands(
            traffic_monitor=self.message_handler.traffic_monitor,
            node_manager=self.node_manager,
            interface=self.message_handler.interface
        )

        # Créer le système unifié de statistiques (nouveau)
        self.unified_stats = UnifiedStatsCommands(
            traffic_monitor=self.message_handler.traffic_monitor,
            node_manager=self.node_manager,
            interface=self.message_handler.interface
        )

        # Créer le wrapper Telegram pour les commandes stats
        self.stats_commands = StatsCommands(self)

        self.mesh_commands = MeshCommands(self)
        self.utility_commands = UtilityCommands(self)
        self.ai_commands = AICommands(self)
        self.trace_commands = TraceCommands(self)
        self.admin_commands = AdminCommands(self)
        self.db_commands = DBCommandsTelegram(self)

        # NetworkCommands doit être créé APRÈS mesh_commands et stats_commands
        # car il en dépend dans son __init__
        self.network_commands = NetworkCommands(self)

    def start(self):
        """Démarrer le bot Telegram dans un thread séparé"""
        if self.running:
            return

        self.running = True
        self.telegram_thread = threading.Thread(
            target=self._run_telegram_bot, daemon=True)
        self.telegram_thread.start()
        info_print("🤖 Bot Telegram démarré en thread séparé")

    def stop(self):
        """Arrêter le bot Telegram"""
        self.running = False
        if self.loop and self.application:
            try:
                asyncio.run_coroutine_threadsafe(
                    self._shutdown(),
                    self.loop).result(timeout=5)
            except Exception as e:
                error_print(f"Erreur arrêt Telegram: {e}")
        info_print("🛑 Bot Telegram arrêté")

    def _get_mesh_identity(self, telegram_user_id):
        """
        Obtenir l'identité Meshtastic correspondant à un utilisateur Telegram

        Args:
            telegram_user_id: ID Telegram de l'utilisateur

        Returns:
            dict: {'node_id': int, 'short_name': str, 'display_name': str}
                  ou None si pas de mapping
        """
        if telegram_user_id in TELEGRAM_TO_MESH_MAPPING:
            return TELEGRAM_TO_MESH_MAPPING[telegram_user_id]
        return None

    def _run_telegram_bot(self):
        """Thread principal du bot Telegram"""
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self._start_telegram_bot())
        except Exception as e:
            error_print(f"Erreur thread Telegram: {e}")
            error_print(traceback.format_exc())
        finally:
            if self.loop:
                self.loop.close()

    async def _start_telegram_bot(self):
        """Démarrer l'application Telegram"""
        try:
            info_print("Initialisation bot Telegram...")

            self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

            # Enregistrer tous les handlers de commandes
            self._register_command_handlers()

            # Gestionnaire d'erreurs
            self.application.add_error_handler(self._error_handler)

            # Démarrer l'application
            await self.application.initialize()
            await self.application.start()

            info_print("Bot Telegram en écoute (polling optimisé)...")

            await self.application.updater.start_polling(
                poll_interval=5.0,
                timeout=30,
                read_timeout=180,
                write_timeout=180,
                connect_timeout=180,
                pool_timeout=180,
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )

            # Boucle d'attente avec nettoyage
            cleanup_counter = 0
            while self.running:
                await asyncio.sleep(60)
                cleanup_counter += 1
                if cleanup_counter % 6 == 0:  # Toutes les 6 minutes
                    self.traceroute_manager.cleanup_expired_traces()

            # Arrêter proprement
            info_print("Arrêt du polling Telegram...")
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()

        except Exception as e:
            error_print(f"Erreur démarrage Telegram: {e}")
            error_print(traceback.format_exc())

    def _register_command_handlers(self):
        """Enregistrer tous les handlers de commandes"""
        info_print("Enregistrement des handlers de commandes...")

        # Commandes basiques
        self.application.add_handler(CommandHandler("start", self.basic_commands.start_command))
        self.application.add_handler(CommandHandler("help", self.basic_commands.help_command))
        self.application.add_handler(CommandHandler("legend", self.basic_commands.legend_command))
        self.application.add_handler(CommandHandler("health", self.basic_commands.health_command))

        # Commandes système
        self.application.add_handler(CommandHandler("sys", self.system_commands.sys_command))
        self.application.add_handler(CommandHandler("cpu", self.system_commands.cpu_command))
        self.application.add_handler(CommandHandler("rebootpi", self.system_commands.rebootpi_command))
        self.application.add_handler(CommandHandler("rebootg2", self.system_commands.rebootg2_command))

        # Commandes réseau
        self.application.add_handler(CommandHandler("nodes", self.network_commands.nodes_command))
        self.application.add_handler(CommandHandler("fullnodes", self.network_commands.fullnodes_command))
        self.application.add_handler(CommandHandler("nodeinfo", self.network_commands.nodeinfo_command))
        self.application.add_handler(CommandHandler("rx", self.network_commands.rx_command))

        # Commandes statistiques
        self.application.add_handler(CommandHandler("stats", self.stats_commands.stats_command))
        self.application.add_handler(CommandHandler("top", self.stats_commands.top_command))
        self.application.add_handler(CommandHandler("packets", self.stats_commands.packets_command))
        self.application.add_handler(CommandHandler("histo", self.stats_commands.histo_command))
        self.application.add_handler(CommandHandler("trafic", self.stats_commands.trafic_command))

        # Commandes utilitaires
        self.application.add_handler(CommandHandler("power", self.utility_commands.power_command))
        self.application.add_handler(CommandHandler("weather", self.utility_commands.weather_command))
        self.application.add_handler(CommandHandler("rain", self.utility_commands.rain_command))
        self.application.add_handler(CommandHandler("graphs", self.utility_commands.graphs_command))

        # Commandes mesh
        self.application.add_handler(CommandHandler("echo", self.mesh_commands.echo_command))
        self.application.add_handler(CommandHandler("annonce", self.mesh_commands.annonce_command))

        # Commandes IA
        self.application.add_handler(CommandHandler("bot", self.ai_commands.bot_command))
        self.application.add_handler(CommandHandler("clearcontext", self.ai_commands.clearcontext_command))

        # Commandes traceroute
        self.application.add_handler(CommandHandler("trace", self.trace_commands.trace_command))

        # Commandes admin
        self.application.add_handler(CommandHandler("channel_stats", self.admin_commands.channel_stats_command))
        self.application.add_handler(CommandHandler("cleartraffic", self.admin_commands.cleartraffic_command))
        self.application.add_handler(CommandHandler("db", self.admin_commands.db_command))
        self.application.add_handler(CommandHandler("dbstats", self.admin_commands.dbstats_command))
        self.application.add_handler(CommandHandler("cleanup", self.admin_commands.cleanup_command))

        # Commandes DB
        self.application.add_handler(CommandHandler("db", self.db_commands.db_command))

        info_print(f"✅ {len(self.application.handlers[0])} handlers enregistrés")

    async def _error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Gestionnaire d'erreurs global"""
        try:
            error_print(f"❌ Erreur Telegram: {context.error}")
            error_print(traceback.format_exc())

            if update and hasattr(update, 'effective_message'):
                try:
                    await update.effective_message.reply_text(
                        "❌ Erreur lors de l'exécution de la commande"
                    )
                except Exception as e:
                    error_print(f"Impossible d'envoyer le message d'erreur: {e}")
        except Exception as e:
            error_print(f"Erreur dans error_handler: {e}")

    async def _shutdown(self):
        """Arrêter proprement le bot"""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()

    # ===== MÉTHODES PUBLIQUES POUR LES GESTIONNAIRES =====

    def send_alert(self, message):
        """
        Envoyer une alerte aux utilisateurs autorisés
        Délègue au AlertManager

        Args:
            message: Message d'alerte à envoyer
        """
        self.alert_manager.send_alert(message)

    def cleanup_expired_traces(self):
        """
        Nettoyer les traces expirées
        Délègue au TracerouteManager
        """
        self.traceroute_manager.cleanup_expired_traces()

    def handle_trace_response(self, from_id, message_text):
        """
        Gérer une réponse de traceroute texte
        Délègue au TracerouteManager

        Args:
            from_id: ID du nœud qui répond
            message_text: Texte de la réponse
        """
        self.traceroute_manager.handle_trace_response(from_id, message_text)

    def handle_traceroute_response(self, packet, decoded):
        """
        Gérer une réponse de traceroute native (protobuf)
        Délègue au TracerouteManager

        Args:
            packet: Paquet Meshtastic
            decoded: Données décodées
        """
        self.traceroute_manager.handle_traceroute_response(packet, decoded)

    def get_node_behavior_report(self, node_id, hours=24):
        """
        Obtenir un rapport de comportement d'un nœud
        (Gardé pour compatibilité - peut-être utilisé ailleurs)

        Args:
            node_id: ID du nœud
            hours: Nombre d'heures d'historique

        Returns:
            str: Rapport formaté
        """
        try:
            current_time = time.time()
            cutoff_time = current_time - (hours * 3600)

            # Obtenir les paquets récents de ce nœud
            node_packets = [
                p for p in self.message_handler.traffic_monitor.all_packets
                if p.get('from_id') == node_id and p.get('timestamp', 0) > cutoff_time
            ]

            if not node_packets:
                return f"📊 Aucune donnée pour le nœud {hex(node_id)} sur les {hours} dernières heures"

            # Statistiques de base
            total_packets = len(node_packets)
            packet_types = {}
            for p in node_packets:
                ptype = p.get('packet_type', 'UNKNOWN')
                packet_types[ptype] = packet_types.get(ptype, 0) + 1

            # Formater le rapport
            report = f"📊 Comportement nœud {hex(node_id)} ({hours}h)\n\n"
            report += f"Total paquets: {total_packets}\n\n"
            report += "Types de paquets:\n"
            for ptype, count in sorted(packet_types.items(), key=lambda x: x[1], reverse=True):
                report += f"  {ptype}: {count}\n"

            return report

        except Exception as e:
            error_print(f"Erreur get_node_behavior_report: {e}")
            return f"❌ Erreur lors de la génération du rapport: {str(e)}"
