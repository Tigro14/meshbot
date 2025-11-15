#!/usr/bin/env python3
"""
Commandes de statistiques unifiées - Business Logic
Accessible depuis Mesh ET Telegram avec adaptation automatique
"""

import time
from collections import defaultdict
from utils import error_print, debug_print
import traceback


class UnifiedStatsCommands:
    """
    Gestionnaire unifié des statistiques réseau Meshtastic
    Centralise toute la business logic pour éviter la duplication
    Adapte automatiquement les réponses selon le canal (Mesh vs Telegram)
    """

    def __init__(self, traffic_monitor, node_manager, interface):
        """
        Args:
            traffic_monitor: Instance de TrafficMonitor
            node_manager: Instance de NodeManager
        """
        self.traffic_monitor = traffic_monitor
        self.node_manager = node_manager
        self.interface = interface

    def get_stats(self, subcommand='global', params=None, channel='mesh'):
        """
        Point d'entrée unifié pour toutes les statistiques

        Args:
            subcommand: Type de stats (global, top, packets, channel, histo, traffic)
            params: Paramètres additionnels (liste de strings)
            channel: 'mesh' ou 'telegram' pour adaptation automatique

        Returns:
            str: Rapport formaté selon le canal
        """
        params = params or []

        try:
            if subcommand in ['', 'global', 'g']:
                return self.get_global_stats(params, channel)
            elif subcommand in ['top', 't']:
                return self.get_top_talkers(params, channel)
            elif subcommand in ['packets', 'p', 'pkt']:
                return self.get_packet_summary(params, channel)
            elif subcommand in ['channel', 'ch', 'c']:
                return self.get_channel_stats(params, channel)
            elif subcommand in ['histo', 'h', 'histogram']:
                return self.get_histogram(params, channel)
            elif subcommand in ['traffic', 'trafic', 'tr']:
                return self.get_traffic_history(params, channel)
            else:
                return self.get_help(channel)

        except Exception as e:
            error_print(f"Erreur get_stats({subcommand}): {e}")
            error_print(traceback.format_exc())
            return f"❌ Erreur: {str(e)[:100]}"

    def get_help(self, channel='mesh'):
        """Afficher l'aide des sous-commandes"""
        if channel == 'mesh':
            return (
                "📊 /stats [cmd]\n"
                "g=global t=top p=packets\n"
                "ch=channel h=histo\n"
                "Ex: /stats t 12"
            )
        else:  # telegram
            return """📊 **COMMANDES STATS**

**Syntaxe:** `/stats [sous-commande] [paramètres]`

**Sous-commandes:**
• `global` - Vue d'ensemble réseau (défaut)
• `top [hours] [n]` - Top talkers
• `packets [hours]` - Distribution types de paquets
• `channel [hours]` - Utilisation du canal
• `histo [type] [hours]` - Histogramme temporel
• `traffic [hours]` - Historique messages

**Raccourcis:** g, t, p, ch, h, tr

**Exemples:**
• `/stats` → Vue globale
• `/stats top 24 10` → Top 10 sur 24h
• `/stats channel 12` → Canal sur 12h
• `/stats h pos 6` → Histo positions 6h

**Aliases (compatibilité):**
`/top`, `/packets`, `/histo` fonctionnent toujours!
"""

    def get_global_stats(self, params, channel='mesh'):
        """
        Statistiques globales du réseau

        Args:
            params: [] (pas de params pour global)
            channel: 'mesh' ou 'telegram'
        """
        if not self.traffic_monitor:
            return "❌ Traffic monitor non disponible"

        tm = self.traffic_monitor

        try:
            if channel == 'mesh':
                # Version ultra-compacte pour LoRa (180 chars max)
                msg_24h = tm.get_message_count(24)
                msg_1h = tm.get_message_count(1)

                # Nodes actifs
                active_1h = len(self._get_active_nodes(1))
                active_24h = len(self._get_active_nodes(24))

                # Top 3
                top_stats = tm.get_quick_stats()
                if top_stats and "\n" in top_stats:
                    top_line = top_stats.split('\n')[1] if len(top_stats.split('\n')) > 1 else ""
                    top_short = top_line[:40] if top_line else ""
                else:
                    top_short = ""

                return f"📊({24}h) {msg_24h}msg {active_24h}n 🏆{top_short}"

            else:  # telegram - version détaillée
                lines = []
                lines.append("📊 **STATISTIQUES RÉSEAU MESH**")
                lines.append("=" * 40)

                # Messages
                msg_24h = tm.get_message_count(24)
                msg_1h = tm.get_message_count(1)
                msg_total = len(tm.public_messages)

                lines.append("\n**📨 Messages:**")
                lines.append(f"• Dernière heure: {msg_1h}")
                lines.append(f"• Dernières 24h: {msg_24h}")
                lines.append(f"• En mémoire: {msg_total}")

                # Nœuds actifs
                active_1h = self._get_active_nodes(1)
                active_24h = self._get_active_nodes(24)

                lines.append(f"\n**👥 Nœuds actifs:**")
                lines.append(f"• Dernière heure: {len(active_1h)}")
                lines.append(f"• Dernières 24h: {len(active_24h)}")
                lines.append(f"• Total connus: {len(self.node_manager.node_names)}")

                # Top 3 actifs récents
                quick_stats = tm.get_quick_stats()
                if quick_stats:
                    lines.append(f"\n**🏆 Top actifs (3h):**")
                    for line in quick_stats.split('\n')[1:4]:  # Top 3
                        if line.strip():
                            lines.append(f"• {line}")

                # Uptime monitoring
                if hasattr(tm, 'global_stats'):
                    current_time = time.time()
                    uptime_seconds = current_time - tm.global_stats.get('last_reset', current_time)
                    uptime_hours = int(uptime_seconds / 3600)
                    lines.append(f"\n**🕐 Monitoring:**")
                    lines.append(f"• Uptime: {uptime_hours}h")

                return "\n".join(lines)

        except Exception as e:
            error_print(f"Erreur global_stats: {e}")
            return f"❌ Erreur: {str(e)[:100]}"

    def get_top_talkers(self, params, channel='mesh'):
        """
        Top talkers avec tous les types de paquets

        Args:
            params: [hours, nombre] optionnels
            channel: 'mesh' ou 'telegram'
        """
        if not self.traffic_monitor:
            return "❌ Traffic monitor non disponible"

        # Paramètres par défaut selon le canal
        if channel == 'mesh':
            default_hours = 3
            default_n = 5
        else:
            default_hours = 24
            default_n = 10

        # Parser les paramètres
        hours = default_hours
        top_n = default_n

        if len(params) > 0:
            try:
                hours = int(params[0])
                hours = max(1, min(168, hours))
            except ValueError:
                pass

        if len(params) > 1:
            try:
                top_n = int(params[1])
                top_n = max(1, min(20, top_n))
            except ValueError:
                pass

        try:
            return self.traffic_monitor.get_top_talkers_report(
                hours, top_n,
                include_packet_types=(channel == 'telegram')  # Détails seulement sur Telegram
            )
        except Exception as e:
            error_print(f"Erreur top_talkers: {e}")
            return f"❌ Erreur: {str(e)[:100]}"

    def get_packet_summary(self, params, channel='mesh'):
        """
        Distribution des types de paquets

        Args:
            params: [hours] optionnel
            channel: 'mesh' ou 'telegram'
        """
        if not self.traffic_monitor:
            return "❌ Traffic monitor non disponible"

        # Paramètre par défaut selon le canal
        hours = 1 if channel == 'mesh' else 24

        if len(params) > 0:
            try:
                hours = int(params[0])
                hours = max(1, min(168, hours))
            except ValueError:
                pass

        try:
            return self.traffic_monitor.get_packet_type_summary(hours)
        except Exception as e:
            error_print(f"Erreur packet_summary: {e}")
            return f"❌ Erreur: {str(e)[:100]}"

    def get_channel_stats(self, params, channel='mesh'):
        """
        Utilisation du canal (Channel Utilization)

        Args:
            params: [hours] optionnel
            channel: 'mesh' ou 'telegram'
        """
        if not self.traffic_monitor:
            return "❌ Traffic monitor non disponible"

        hours = 24
        if len(params) > 0:
            try:
                hours = int(params[0])
                hours = max(1, min(168, hours))
            except ValueError:
                pass

        try:
            # Mettre à jour la base de noms depuis l'interface pour avoir les LongName
            if self.interface:
                try:
                    self.node_manager.update_node_database(self.interface)
                    debug_print("📋 Base de noms mise à jour pour /stats channel")
                except Exception as e:
                    debug_print(f"⚠️ Erreur mise à jour noms: {e}")

            tm = self.traffic_monitor

            lines = []
            lines.append(f"📡 CANAL ({hours}h)")

            if channel == 'mesh':
                lines.append("=" * 15)  # Version compacte pour mesh
            else:
                lines.append("=" * 50)

            # Charger les paquets de télémétrie
            all_packets = tm.persistence.load_packets(hours=hours, limit=10000)

            # Collecter les données de télémétrie par nœud
            node_channel_data = {}

            for packet in all_packets:
                if packet['packet_type'] == 'TELEMETRY_APP':
                    from_id = packet['from_id']

                    # Convertir from_id en int si c'est une string
                    if isinstance(from_id, str):
                        try:
                            # Si c'est un ID hex comme "!12345678"
                            if from_id.startswith('!'):
                                from_id = int(from_id[1:], 16)
                            else:
                                # ID décimal en string
                                from_id = int(from_id)
                        except (ValueError, AttributeError):
                            debug_print(f"⚠️ ID invalide ignoré: {from_id}")
                            continue

                    if 'telemetry' in packet and packet['telemetry'] is not None:
                        telemetry = packet['telemetry']
                        ch_util = telemetry.get('channel_util')
                        air_util = telemetry.get('air_util')

                        if ch_util is not None:
                            if from_id not in node_channel_data:
                                node_channel_data[from_id] = {
                                    'channel_utils': [],
                                    'air_utils': [],
                                    'name': self.node_manager.get_node_name(from_id, interface=self.interface)
                                }

                            node_channel_data[from_id]['channel_utils'].append(ch_util)
                            if air_util is not None:
                                node_channel_data[from_id]['air_utils'].append(air_util)

            if not node_channel_data:
                return f"📭 Aucune télémétrie canal ({hours}h)"

            # Calculer moyennes et trier
            node_averages = []
            for node_id, data in node_channel_data.items():
                avg_channel = sum(data['channel_utils']) / len(data['channel_utils'])
                avg_air = sum(data['air_utils']) / len(data['air_utils']) if data['air_utils'] else 0
                node_averages.append({
                    'id': node_id,
                    'name': data['name'],
                    'avg_channel': avg_channel,
                    'avg_air': avg_air,
                    'samples': len(data['channel_utils'])
                })

            node_averages.sort(key=lambda x: x['avg_channel'], reverse=True)

            # Afficher selon le canal
            if channel == 'mesh':
                # Version ultra-compacte pour LoRa (pagination 180 chars)
                total_avg = sum(n['avg_channel'] for n in node_averages) / len(node_averages)

                # Compter la distribution par niveau
                count_crit = len([n for n in node_averages if n['avg_channel'] > 25])
                count_high = len([n for n in node_averages if 15 < n['avg_channel'] <= 25])
                count_norm = len([n for n in node_averages if 10 < n['avg_channel'] <= 15])
                count_low = len([n for n in node_averages if n['avg_channel'] <= 10])

                # Synthèse globale
                lines.append(f"Moy:{total_avg:.1f}% | {len(node_averages)}n")

                # Distribution compacte
                distrib_parts = []
                if count_crit > 0:
                    distrib_parts.append(f"{count_crit}🔴")
                if count_high > 0:
                    distrib_parts.append(f"{count_high}🟡")
                if count_norm > 0:
                    distrib_parts.append(f"{count_norm}🟢")
                if count_low > 0:
                    distrib_parts.append(f"{count_low}⚪")

                if distrib_parts:
                    lines.append(" ".join(distrib_parts))

                # Top 3 nœuds (ultra-compact)
                lines.append("---")
                for i, node_data in enumerate(node_averages[:3], 1):
                    name = node_data['name'][:8]  # Nom encore plus court
                    avg_ch = node_data['avg_channel']

                    # Icône selon niveau
                    if avg_ch > 25:
                        icon = "🔴"
                    elif avg_ch > 15:
                        icon = "🟡"
                    elif avg_ch > 10:
                        icon = "🟢"
                    else:
                        icon = "⚪"

                    lines.append(f"{i}.{icon}{name}:{avg_ch:.1f}%")

                # Alerte si moyenne élevée
                if total_avg > 15:
                    lines.append("⚠️ Canal chargé")
                elif total_avg > 10:
                    lines.append("✓ Canal OK")

            else:  # telegram - version détaillée
                lines.append(f"\n📊 Nœuds actifs: {len(node_averages)}")
                lines.append("")

                for i, node_data in enumerate(node_averages, 1):
                    name = node_data['name'][:20]
                    avg_ch = node_data['avg_channel']
                    avg_air = node_data['avg_air']
                    samples = node_data['samples']

                    # Icône et statut
                    if avg_ch > 25:
                        icon = "🔴"
                        status = "CRITIQUE"
                    elif avg_ch > 15:
                        icon = "🟡"
                        status = "ÉLEVÉ"
                    elif avg_ch > 10:
                        icon = "🟢"
                        status = "NORMAL"
                    else:
                        icon = "⚪"
                        status = "FAIBLE"

                    lines.append(f"{i}. {icon} {name}")
                    lines.append(f"   Canal: {avg_ch:.1f}% ({status})")
                    if avg_air > 0:
                        lines.append(f"   Air TX: {avg_air:.1f}%")
                    lines.append(f"   Échantillons: {samples}")

                    if avg_ch > 15:
                        lines.append("   ⚠️ Réduire fréquence paquets")

                    lines.append("")

                # Stats globales
                lines.append("=" * 50)
                lines.append("📈 GLOBALES:")
                total_avg = sum(n['avg_channel'] for n in node_averages) / len(node_averages)
                max_ch = max(n['avg_channel'] for n in node_averages)
                min_ch = min(n['avg_channel'] for n in node_averages)
                lines.append(f"Moy: {total_avg:.1f}%")
                lines.append(f"Max: {max_ch:.1f}%")
                lines.append(f"Min: {min_ch:.1f}%")

                lines.append("\n📋 SEUILS:")
                lines.append("🟢 <10% Normal")
                lines.append("🟡 10-15% Acceptable")
                lines.append("🟠 15-25% Élevé")
                lines.append("🔴 >25% Critique")

            return "\n".join(lines)

        except Exception as e:
            error_print(f"Erreur channel_stats: {e}")
            error_print(traceback.format_exc())
            return f"❌ Erreur: {str(e)[:100]}"

    def get_histogram(self, params, channel='mesh'):
        """
        Histogramme temporel des paquets

        Args:
            params: [type, hours] optionnels
            channel: 'mesh' ou 'telegram'
        """
        if not self.traffic_monitor:
            return "❌ Traffic monitor non disponible"

        # Parser les paramètres
        packet_type = None
        hours = 12 if channel == 'mesh' else 24

        if len(params) > 0:
            ptype_arg = params[0].lower()
            type_mapping = {
                'pos': 'POSITION_APP',
                'position': 'POSITION_APP',
                'text': 'TEXT_MESSAGE_APP',
                'msg': 'TEXT_MESSAGE_APP',
                'message': 'TEXT_MESSAGE_APP',
                'node': 'NODEINFO_APP',
                'info': 'NODEINFO_APP',
                'tele': 'TELEMETRY_APP',
                'telemetry': 'TELEMETRY_APP'
            }
            packet_type = type_mapping.get(ptype_arg)

        if len(params) > 1:
            try:
                hours = int(params[1])
                hours = max(1, min(168, hours))
            except ValueError:
                pass

        try:
            return self.traffic_monitor.get_histogram_report(
                hours=hours,
                packet_type=packet_type
            )
        except Exception as e:
            error_print(f"Erreur histogram: {e}")
            return f"❌ Erreur: {str(e)[:100]}"

    def get_traffic_history(self, params, channel='mesh'):
        """
        Historique des messages publics

        Args:
            params: [hours] optionnel
            channel: 'mesh' ou 'telegram'
        """
        # Pas disponible sur Mesh (trop long)
        if channel == 'mesh':
            return "❌ /stats traffic: Telegram seulement"

        if not self.traffic_monitor:
            return "❌ Traffic monitor non disponible"

        hours = 8
        if len(params) > 0:
            try:
                hours = int(params[0])
                hours = max(1, min(24, hours))
            except ValueError:
                pass

        try:
            # Charger les messages publics
            all_packets = self.traffic_monitor.persistence.load_public_messages(hours=hours, limit=50)

            if not all_packets:
                return f"📭 Aucun message public ({hours}h)"

            lines = []
            lines.append(f"💬 **MESSAGES PUBLICS ({hours}h)**")
            lines.append("=" * 50)
            lines.append(f"\n{len(all_packets)} message(s):\n")

            for packet in all_packets:
                from datetime import datetime
                ts = datetime.fromtimestamp(packet['timestamp']).strftime('%H:%M')
                sender = packet['sender_name'] or 'Unknown'
                message = packet['message'] or ''

                # Tronquer si trop long
                if len(message) > 60:
                    message = message[:60] + "..."

                lines.append(f"**{ts}** {sender}:")
                lines.append(f"  {message}")
                lines.append("")

            return "\n".join(lines)

        except Exception as e:
            error_print(f"Erreur traffic_history: {e}")
            return f"❌ Erreur: {str(e)[:100]}"

    # Méthodes utilitaires privées

    def _get_active_nodes(self, hours):
        """Obtenir les nœuds actifs sur une période"""
        active_nodes = set()
        current_time = time.time()
        cutoff = current_time - (hours * 3600)

        for msg in self.traffic_monitor.public_messages:
            if msg['timestamp'] >= cutoff:
                active_nodes.add(msg['from_id'])

        return active_nodes
