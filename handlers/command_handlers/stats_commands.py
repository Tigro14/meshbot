#!/usr/bin/env python3
"""
Gestionnaire des commandes de statistiques
Logique métier réutilisable par mesh ET Telegram
"""

import time
from collections import defaultdict
from utils import error_print, debug_print
import traceback


class StatsCommands:
    """
    Gestionnaire des statistiques réseau Meshtastic
    Fournit des méthodes de génération de rapports réutilisables
    """

    def __init__(self, traffic_monitor, node_manager, interface=None):
        """
        Args:
            traffic_monitor: Instance de TrafficMonitor
            node_manager: Instance de NodeManager
        """
        self.traffic_monitor = traffic_monitor
        self.node_manager = node_manager
        self.interface = interface

    def get_channel_stats(self, hours=24):
        """
        Générer les statistiques d'utilisation du canal par nœud

        Args:
            hours: Période d'analyse en heures (défaut: 24)

        Returns:
            str: Rapport formaté des statistiques de canal
        """
        try:
            if not self.traffic_monitor:
                return "❌ Traffic monitor non disponible"

            tm = self.traffic_monitor

            lines = []
            lines.append(f"📡 STATISTIQUES D'UTILISATION DU CANAL ({hours}h)")
            lines.append("=" * 50)

            # Charger les paquets directement depuis SQLite pour avoir les données les plus récentes
            all_packets = tm.persistence.load_packets(hours=hours, limit=10000)

            # Collecter les données de télémétrie par nœud
            node_channel_data = {}

            for packet in all_packets:
                if packet['packet_type'] == 'TELEMETRY_APP':
                    from_id = packet['from_id']

                    # Extraire les données de télémétrie directement du paquet
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
                return f"📭 Aucune donnée de télémétrie dans les {hours}h"

            # Calculer les moyennes et trier par utilisation du canal
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

            # Trier par utilisation du canal (décroissant)
            node_averages.sort(key=lambda x: x['avg_channel'], reverse=True)

            lines.append(f"\n📊 Nœuds actifs: {len(node_averages)}")
            lines.append("")

            # Afficher les statistiques par nœud
            for i, node_data in enumerate(node_averages, 1):
                name = node_data['name'][:20]
                avg_ch = node_data['avg_channel']
                avg_air = node_data['avg_air']
                samples = node_data['samples']

                # Icône selon le niveau d'utilisation
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

                # Avertissement si utilisation élevée
                if avg_ch > 15:
                    lines.append(f"   ⚠️  Réduire la fréquence des paquets")

                lines.append("")

            # Statistiques globales
            lines.append("=" * 50)
            lines.append("📈 STATISTIQUES GLOBALES:")
            lines.append("")

            total_avg_channel = sum(n['avg_channel'] for n in node_averages) / len(node_averages)
            max_channel = max(n['avg_channel'] for n in node_averages)
            min_channel = min(n['avg_channel'] for n in node_averages)

            lines.append(f"Utilisation moyenne du canal: {total_avg_channel:.1f}%")
            lines.append(f"Utilisation max: {max_channel:.1f}%")
            lines.append(f"Utilisation min: {min_channel:.1f}%")

            # Seuils recommandés
            lines.append("")
            lines.append("📋 SEUILS RECOMMANDÉS:")
            lines.append("  🟢 < 10% : Normal")
            lines.append("  🟡 10-15% : Acceptable")
            lines.append("  🟠 15-25% : Élevé")
            lines.append("  🔴 > 25% : Critique")

            return "\n".join(lines)

        except Exception as e:
            error_print(f"Erreur get_channel_stats: {e}")
            error_print(traceback.format_exc())
            return f"❌ Erreur: {str(e)[:100]}"

    def get_top_talkers(self, hours=24, top_n=10, include_packet_types=True):
        """
        Générer le rapport des top talkers

        Args:
            hours: Période d'analyse en heures
            top_n: Nombre de top nodes à afficher
            include_packet_types: Inclure le détail par type de paquet

        Returns:
            str: Rapport formaté des top talkers
        """
        try:
            if not self.traffic_monitor:
                return "❌ Traffic monitor non disponible"

            return self.traffic_monitor.get_top_talkers_report(
                hours, top_n, include_packet_types
            )

        except Exception as e:
            error_print(f"Erreur get_top_talkers: {e}")
            error_print(traceback.format_exc())
            return f"❌ Erreur: {str(e)[:100]}"

    def get_packet_type_summary(self, hours=24):
        """
        Générer un résumé des types de paquets

        Args:
            hours: Période d'analyse en heures

        Returns:
            str: Résumé formaté des types de paquets
        """
        try:
            if not self.traffic_monitor:
                return "❌ Traffic monitor non disponible"

            return self.traffic_monitor.get_packet_type_summary(hours)

        except Exception as e:
            error_print(f"Erreur get_packet_type_summary: {e}")
            error_print(traceback.format_exc())
            return f"❌ Erreur: {str(e)[:100]}"

    def get_histogram(self, packet_filter='all', hours=24):
        """
        Générer un histogramme de distribution horaire des paquets

        Args:
            packet_filter: Type de paquet ('all', 'messages', 'pos', 'info', 'telemetry', etc.)
            hours: Période d'analyse en heures

        Returns:
            str: Histogramme formaté
        """
        try:
            if not self.traffic_monitor:
                return "❌ Traffic monitor non disponible"

            return self.traffic_monitor.get_hourly_histogram(packet_filter, hours)

        except Exception as e:
            error_print(f"Erreur get_histogram: {e}")
            error_print(traceback.format_exc())
            return f"❌ Erreur: {str(e)[:100]}"

    def get_traffic_report(self, hours=8):
        """
        Générer le rapport de trafic public

        Args:
            hours: Période d'analyse en heures

        Returns:
            str: Rapport formaté du trafic
        """
        try:
            if not self.traffic_monitor:
                return "❌ Traffic monitor non disponible"

            return self.traffic_monitor.get_traffic_report(hours)

        except Exception as e:
            error_print(f"Erreur get_traffic_report: {e}")
            error_print(traceback.format_exc())
            return f"❌ Erreur: {str(e)[:100]}"

    def get_traffic_report_mc(self, hours=8):
        """
        Générer le rapport de trafic public MeshCore

        Args:
            hours: Période d'analyse en heures

        Returns:
            str: Rapport formaté du trafic MeshCore
        """
        try:
            if not self.traffic_monitor:
                return "❌ Traffic monitor non disponible"

            return self.traffic_monitor.get_traffic_report_mc(hours)

        except Exception as e:
            error_print(f"Erreur get_traffic_report_mc: {e}")
            error_print(traceback.format_exc())
            return f"❌ Erreur: {str(e)[:100]}"

    def get_traffic_report_mt(self, hours=8):
        """
        Générer le rapport de trafic public Meshtastic

        Args:
            hours: Période d'analyse en heures

        Returns:
            str: Rapport formaté du trafic Meshtastic
        """
        try:
            if not self.traffic_monitor:
                return "❌ Traffic monitor non disponible"

            return self.traffic_monitor.get_traffic_report_mt(hours)

        except Exception as e:
            error_print(f"Erreur get_traffic_report_mt: {e}")
            error_print(traceback.format_exc())
            return f"❌ Erreur: {str(e)[:100]}"

    def clear_traffic_history(self):
        """
        Efface tout l'historique du trafic (mémoire et SQLite).

        Returns:
            str: Message de confirmation ou d'erreur
        """
        try:
            if not self.traffic_monitor:
                return "❌ Traffic monitor non disponible"

            success = self.traffic_monitor.clear_traffic_history()

            if success:
                return "✅ Historique du trafic effacé avec succès\n\n" \
                       "📭 Toutes les données (mémoire et base de données) ont été supprimées.\n" \
                       "Les statistiques vont recommencer à zéro."
            else:
                return "❌ Erreur lors de l'effacement de l'historique"

        except Exception as e:
            error_print(f"Erreur clear_traffic_history: {e}")
            error_print(traceback.format_exc())
            return f"❌ Erreur: {str(e)[:100]}"

    def get_persistence_stats(self):
        """
        Affiche les statistiques de la base de données de persistance.

        Returns:
            str: Rapport des statistiques de persistance
        """
        try:
            if not self.traffic_monitor:
                return "❌ Traffic monitor non disponible"

            return self.traffic_monitor.get_persistence_stats()

        except Exception as e:
            error_print(f"Erreur get_persistence_stats: {e}")
            error_print(traceback.format_exc())
            return f"❌ Erreur: {str(e)[:100]}"

    def cleanup_old_data(self, hours=48):
        """
        Nettoie les anciennes données de la base de données.

        Args:
            hours: Nombre d'heures de données à conserver

        Returns:
            str: Message de confirmation
        """
        try:
            if not self.traffic_monitor:
                return "❌ Traffic monitor non disponible"

            self.traffic_monitor.cleanup_old_persisted_data(hours)
            return f"✅ Nettoyage effectué\n\nDonnées de plus de {hours}h supprimées."

        except Exception as e:
            error_print(f"Erreur cleanup_old_data: {e}")
            error_print(traceback.format_exc())
            return f"❌ Erreur: {str(e)[:100]}"
