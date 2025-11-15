#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Commandes statistiques Telegram : stats, top, packets, histo, trafic
"""

from telegram import Update
from telegram.ext import ContextTypes
from telegram_bot.command_base import TelegramCommandBase
from utils import info_print, error_print
import asyncio
import time
from datetime import datetime


class StatsCommands(TelegramCommandBase):
    """Gestionnaire des commandes statistiques Telegram"""

    async def trafic_command(self, update: Update,
                              context: ContextTypes.DEFAULT_TYPE):
        """Commande /trafic pour historique messages publics"""
        user = update.effective_user
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return

        hours = 8
        if context.args and len(context.args) > 0:
            try:
                hours = int(context.args[0])
                hours = max(1, min(24, hours))
            except ValueError:
                hours = 8

        info_print(f"📱 Telegram /trafic {hours}h: {user.username}")

        # Utiliser la logique métier partagée (business_stats, pas stats_commands)
        response = await asyncio.to_thread(
            self.telegram.business_stats.get_traffic_report,
            hours
        )
        await update.message.reply_text(response)

    async def stats_command(self, update: Update,
                             context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /stats - Statistiques globales du réseau
        """
        user = update.effective_user
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return

        info_print(f"📱 Telegram /stats: {user.username}")

        def get_global_stats():
            try:
                if not self.message_handler.traffic_monitor:
                    return "❌ Traffic monitor non disponible"

                tm = self.message_handler.traffic_monitor

                lines = []
                lines.append("📊 **STATISTIQUES RÉSEAU MESH**")
                lines.append("=" * 40)

                # Messages dernières 24h
                msg_24h = tm.get_message_count(24)
                msg_1h = tm.get_message_count(1)
                msg_total = len(tm.public_messages)

                lines.append(f"\n**📨 Messages:**")
                lines.append(f"• Dernière heure: {msg_1h}")
                lines.append(f"• Dernières 24h: {msg_24h}")
                lines.append(f"• En mémoire: {msg_total}")

                # Nœuds actifs
                active_nodes_1h = set()
                active_nodes_24h = set()
                current_time = time.time()

                for msg in tm.public_messages:
                    if msg['timestamp'] >= current_time - 3600:
                        active_nodes_1h.add(msg['from_id'])
                    if msg['timestamp'] >= current_time - 86400:
                        active_nodes_24h.add(msg['from_id'])

                lines.append(f"\n**👥 Nœuds actifs:**")
                lines.append(f"• Dernière heure: {len(active_nodes_1h)}")
                lines.append(f"• Dernières 24h: {len(active_nodes_24h)}")
                lines.append(
                    f"• Total connus: {len(self.node_manager.node_names)}")

                # ✅ FIX : Vérifier que les stats existent avant de les afficher
                if hasattr(tm, 'global_stats'):
                    busiest_hour = tm.global_stats.get('busiest_hour')
                    quietest_hour = tm.global_stats.get('quietest_hour')

                    if busiest_hour and quietest_hour:
                        lines.append(f"\n⏰ Patterns:")
                        lines.append(f"• Heure de pointe: {busiest_hour}")
                        lines.append(f"• Heure creuse: {quietest_hour}")

                # Top 3 des dernières heures
                quick_stats = tm.get_quick_stats()
                if quick_stats and "TOP" in quick_stats:
                    lines.append(f"\n**🏆 Actifs récents (3h):**")
                    for line in quick_stats.split('\n')[1:]:  # Skip header
                        lines.append(f"• {line}")

                # Uptime du monitoring
                uptime_seconds = current_time - \
                    tm.global_stats.get('last_reset', current_time)
                uptime_hours = int(uptime_seconds / 3600)
                lines.append(f"\n**🕐 Monitoring:**")
                lines.append(f"• Uptime: {uptime_hours}h")
                last_reset_time = datetime.fromtimestamp(
                    tm.global_stats.get('last_reset', 0)).strftime('%Y-%m-%d %H:%M')
                lines.append(f"• Dernière réinitialisation: {last_reset_time}")

                return "\n".join(lines)

            except Exception as e:
                error_print(f"Erreur stats globales: {e or 'Unknown error'}")
                return f"❌ Erreur: {str(e)[:100]}"

        response = await asyncio.to_thread(get_global_stats)
        await update.message.reply_text(response, parse_mode='Markdown')

    async def top_command(self, update: Update,
                           context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /top [heures] [nombre]
        Version améliorée avec tous les types de paquets
        """
        user = update.effective_user
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return

        # Parser les arguments
        hours = 24
        top_n = 10

        args = context.args
        if args and len(args) > 0:
            try:
                hours = int(args[0])
                hours = max(1, min(168, hours))
            except ValueError:
                hours = 24

        if args and len(args) > 1:
            try:
                top_n = int(args[1])
                top_n = max(3, min(20, top_n))
            except ValueError:
                top_n = 10

        info_print(f"📱 Telegram /top {hours}h top{top_n}: {user.username}")

        # Message d'attente
        await update.message.reply_text(f"📊 Calcul des statistiques complètes ({hours}h)...")

        # Utiliser la logique métier partagée (business_stats, pas stats_commands)
        def get_detailed_stats():
            # Rapport détaillé avec types de paquets
            report = self.telegram.business_stats.get_top_talkers(hours, top_n, include_packet_types=True)

            # Ajouter le résumé des types de paquets
            packet_summary = self.telegram.business_stats.get_packet_type_summary(hours)
            if packet_summary:
                report += "\n\n" + packet_summary

            return report

        response = await asyncio.to_thread(get_detailed_stats)

        # Si le message est trop long, le diviser
        if len(response) > 4000:
            sections = response.split('\n\n')
            current_msg = ""

            for section in sections:
                if len(current_msg) + len(section) + 2 < 4000:
                    if current_msg:
                        current_msg += "\n\n"
                    current_msg += section
                else:
                    if current_msg:
                        await update.message.reply_text(current_msg)
                        await asyncio.sleep(0.5)
                    current_msg = section

            if current_msg:
                await update.message.reply_text(current_msg)
        else:
            await update.message.reply_text(response)

    async def packets_command(self, update: Update,
                               context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /packets [heures]
        Affiche la distribution des types de paquets
        """
        user = update.effective_user
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return

        hours = 1
        if context.args and len(context.args) > 0:
            try:
                hours = int(context.args[0])
                hours = max(1, min(168, hours))
            except ValueError:
                hours = 1

        info_print(f"📱 Telegram /packets {hours}h: {user.username}")

        # Utiliser la logique métier partagée (business_stats, pas stats_commands)
        def get_packet_stats():
            try:
                # Résumé détaillé des types
                summary = self.telegram.business_stats.get_packet_type_summary(hours)

                # Ajouter les stats réseau
                tm = self.message_handler.traffic_monitor
                if not tm:
                    return summary

                lines = [summary, "\n🌐 **Statistiques réseau:**"]
                lines.append(f"• Paquets directs: {tm.network_stats['packets_direct']}")
                lines.append(f"• Paquets relayés: {tm.network_stats['packets_relayed']}")

                if tm.network_stats['max_hops_seen'] > 0:
                    lines.append(f"• Max hops vus: {tm.network_stats['max_hops_seen']}")

                if tm.network_stats['avg_rssi'] != 0:
                    lines.append(f"• RSSI moyen: {tm.network_stats['avg_rssi']:.1f}dBm")

                if tm.network_stats['avg_snr'] != 0:
                    lines.append(f"• SNR moyen: {tm.network_stats['avg_snr']:.1f}dB")

                # Total de données
                total_kb = tm.global_packet_stats['total_bytes'] / 1024
                lines.append(f"\n📊 **Volume total:**")
                lines.append(f"• {tm.global_packet_stats['total_packets']} paquets")
                lines.append(f"• {total_kb:.1f}KB de données")

                return "\n".join(lines)

            except Exception as e:
                error_print(f"Erreur packet stats: {e or 'Unknown error'}")
                return f"❌ Erreur: {str(e)[:100]}"

        response = await asyncio.to_thread(get_packet_stats)
        await update.message.reply_text(response)

    async def histo_command(self, update: Update,
                             context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /histo [type] [heures] - Histogrammes de paquets

        Usage:
            /histo           - Vue d'ensemble
            /histo pos       - Détails POSITION
            /histo tele      - Détails TELEMETRY
            /histo node      - Détails NODEINFO
            /histo text      - Détails TEXT
            /histo pos 12    - POSITION sur 12h
        """
        user = update.effective_user
        if not self.check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return

        # Parser les arguments
        args = context.args
        packet_type = 'ALL'  # Par défaut: vue d'ensemble
        hours = 24

        # Argument 1: type de paquet (optionnel)
        if args and len(args) > 0:
            packet_type = args[0].strip().upper()
            # Valider le type
            if packet_type not in ['ALL', 'POS', 'TELE', 'NODE', 'TEXT']:
                await update.message.reply_text(
                    f"❌ Type inconnu: {args[0]}\n"
                    f"Types disponibles: pos, tele, node, text"
                )
                return

        # Argument 2: heures (optionnel)
        if args and len(args) > 1:
            try:
                hours = int(args[1])
                hours = max(1, min(48, hours))  # Entre 1 et 48h
            except ValueError:
                hours = 24

        info_print(
            f"📱 Telegram /histo {packet_type} {hours}h: {user.username}")

        def get_histogram():
            """Fonction synchrone pour obtenir l'histogramme"""
            try:
                # Mapping des types courts vers les filtres traffic_monitor
                type_mapping = {
                    'ALL': 'all',
                    'POS': 'pos',
                    'TELE': 'telemetry',
                    'NODE': 'info',
                    'TEXT': 'messages'
                }

                filter_type = type_mapping.get(packet_type, 'all')

                # Utiliser traffic_monitor qui charge depuis SQLite
                return self.traffic_monitor.get_hourly_histogram(
                    packet_filter=filter_type,
                    hours=hours
                )
            except Exception as e:
                error_print(f"Erreur get_histogram: {e}")
                import traceback
                error_print(traceback.format_exc())
                return f"❌ Erreur: {str(e)[:50]}"

        # Exécuter dans un thread séparé
        try:
            histogram = await asyncio.to_thread(get_histogram)
            message = update.edited_message or update.message
            if not message:
                return
            await update.message.reply_text(histogram)

        except Exception as e:
            error_print(f"Erreur /histo: {e}")
            import traceback
            error_print(traceback.format_exc())
            message = update.edited_message or update.message
            if not message:
                return
            await update.message.reply_text(f"❌ Erreur: {str(e)[:50]}")
