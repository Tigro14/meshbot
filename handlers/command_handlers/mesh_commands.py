#!/usr/bin/env python3
"""
Gestionnaire des commandes mesh Meshtastic
Logique métier réutilisable par mesh ET Telegram
"""

from utils import error_print, debug_print
import traceback


class MeshCommands:
    """
    Gestionnaire des commandes liées au réseau mesh
    Fournit des méthodes de génération de rapports sur les nœuds
    """

    def __init__(self, traffic_monitor, node_manager):
        """
        Args:
            traffic_monitor: Instance de TrafficMonitor
            node_manager: Instance de NodeManager
        """
        self.traffic_monitor = traffic_monitor
        self.node_manager = node_manager

    def get_nodes_list(self, node_source='remote'):
        """
        Obtenir la liste des nœuds avec leurs statistiques

        Args:
            node_source: Source des nœuds ('remote' ou 'local')

        Returns:
            str: Liste formatée des nœuds
        """
        try:
            if not self.traffic_monitor:
                return "❌ Traffic monitor non disponible"

            return self.traffic_monitor.get_nodes_list(source=node_source)

        except Exception as e:
            error_print(f"Erreur get_nodes_list: {e}")
            error_print(traceback.format_exc())
            return f"❌ Erreur: {str(e)[:100]}"

    def get_full_nodes_info(self, hours=24):
        """
        Obtenir les informations détaillées de tous les nœuds

        Args:
            hours: Période d'analyse en heures

        Returns:
            str: Rapport détaillé formaté
        """
        try:
            if not self.traffic_monitor:
                return "❌ Traffic monitor non disponible"

            return self.traffic_monitor.get_all_nodes_info(hours)

        except Exception as e:
            error_print(f"Erreur get_full_nodes_info: {e}")
            error_print(traceback.format_exc())
            return f"❌ Erreur: {str(e)[:100]}"

    def get_node_behavior_report(self, node_identifier, hours=24):
        """
        Obtenir le rapport de comportement d'un nœud spécifique

        Args:
            node_identifier: Nom partiel, nom complet, ou ID du nœud
            hours: Période d'analyse en heures

        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            if not self.traffic_monitor:
                return (False, "❌ Traffic monitor non disponible")

            tm = self.traffic_monitor

            # Parser l'identifiant (peut être un nom ou un ID hex)
            target_id = None
            node_name_partial = node_identifier.lower()

            # Essayer de parser comme ID hexadécimal
            if node_name_partial.startswith('!'):
                try:
                    target_id = int(node_name_partial[1:], 16)
                    debug_print(f"🔍 Recherche par ID hex: !{target_id:08x}")
                except ValueError:
                    pass
            elif node_name_partial.startswith('0x'):
                try:
                    target_id = int(node_name_partial, 16)
                    debug_print(f"🔍 Recherche par ID hex: 0x{target_id:08x}")
                except ValueError:
                    pass

            # Rechercher le nœud
            matching_nodes = []

            if target_id is not None:
                # Recherche par ID exact
                target_id = target_id & 0xFFFFFFFF
                if target_id in self.node_manager.node_names:
                    name = self.node_manager.node_names[target_id]
                    if isinstance(name, dict):
                        name = name.get('name', 'Unknown')
                    matching_nodes.append((target_id, name))
                else:
                    return (False, f"❌ Nœud !{target_id:08x} introuvable")
            else:
                # Recherche par nom
                for node_id, name in self.node_manager.node_names.items():
                    if isinstance(name, dict):
                        name = name.get('name', '')
                    if node_name_partial in name.lower():
                        matching_nodes.append((node_id, name))

            if not matching_nodes:
                return (False, f"❌ Aucun nœud trouvé pour '{node_identifier}'")

            # Si plusieurs nœuds trouvés
            if len(matching_nodes) > 1:
                unique_names = set(name for _, name in matching_nodes)

                if len(unique_names) == 1:
                    # ALERTE: Tous les nœuds ont le même nom
                    import time
                    result = f"⚠️ ALERTE: {len(matching_nodes)} nœuds distincts portent le même nom!\n\n"
                    result += f"📛 Nom commun: {matching_nodes[0][1]}\n\n"
                    result += "🔍 Utilisez l'ID hexadécimal complet:\n\n"

                    for node_id, name in matching_nodes:
                        node_packets = [p for p in tm.all_packets
                                      if p['from_id'] == node_id
                                      and p['timestamp'] >= time.time() - (hours * 3600)]
                        packet_count = len(node_packets)

                        result += f"• !{node_id:08x} ({packet_count} paquets en {hours}h)\n"
                        result += f"  Commande: /nodeinfo !{node_id:08x}\n\n"

                    return (True, result)
                else:
                    # Noms différents
                    result = f"📋 {len(matching_nodes)} nœuds trouvés:\n\n"
                    for node_id, name in matching_nodes[:5]:
                        result += f"- {name} (!{node_id:08x})\n"
                    if len(matching_nodes) > 5:
                        result += f"\n... et {len(matching_nodes) - 5} autres\n"
                    result += "\nPrécisez le nom ou utilisez l'ID complet"
                    return (True, result)

            # Un seul nœud trouvé - générer le rapport
            node_id, name = matching_nodes[0]
            report = tm.get_node_behavior_report(node_id, hours)
            return (True, report)

        except Exception as e:
            error_print(f"Erreur get_node_behavior_report: {e}")
            error_print(traceback.format_exc())
            return (False, f"❌ Erreur: {str(e)[:100]}")

    def get_rx_stats(self, hours=1):
        """
        Obtenir les statistiques de réception (RSSI/SNR)

        Args:
            hours: Période d'analyse en heures

        Returns:
            str: Statistiques RX formatées
        """
        try:
            if not self.node_manager:
                return "❌ Node manager non disponible"

            return self.node_manager.get_rx_report(hours)

        except Exception as e:
            error_print(f"Erreur get_rx_stats: {e}")
            error_print(traceback.format_exc())
            return f"❌ Erreur: {str(e)[:100]}"
