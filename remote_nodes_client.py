#!/usr/bin/env python3
"""
Client pour la récupération des nœuds distants
VERSION AVEC SafeTCPConnection
"""

import time
from safe_tcp_connection import SafeTCPConnection
from config import *
from utils import (
    debug_print,
    error_print,
    format_elapsed_time,
    get_signal_quality_icon,
    truncate_text,
    validate_page_number
)

class RemoteNodesClient:
    def __init__(self):
        pass
    
    def get_remote_nodes(self, remote_host, remote_port=4403, days_filter=3):
        """Récupérer la liste des nœuds directs (0 hop) d'un nœud distant"""
        
        current_time = time.time()
        cutoff_time = current_time - (days_filter * 24 * 3600)
        debug_print(f"Filtre temporel: derniers {days_filter} jours")
        
        skipped_by_hops = 0
        skipped_by_date = 0
        skipped_by_metrics = 0
        
        try:
            debug_print(f"Connexion au nœud distant {remote_host}...")
            
            # ✅ Utilisation de SafeTCPConnection avec context manager
            with SafeTCPConnection.connect(remote_host, remote_port) as remote_interface:
                time.sleep(2)  # Laisser les données se charger
                remote_nodes = remote_interface.nodes
                
                node_list = []
                for node_id, node_info in remote_nodes.items():
                    try:
                        if isinstance(node_info, dict):
                            hops_away = node_info.get('hopsAway', None)
                            
                            if hops_away is not None:
                                if hops_away > 0:
                                    skipped_by_hops += 1
                                    continue
                            else:
                                position_metrics = node_info.get('position', {})
                                if isinstance(position_metrics, dict):
                                    ground_speed = position_metrics.get('groundSpeed', 0)
                                    if ground_speed == 0:
                                        skipped_by_metrics += 1
                                        continue
                            
                            # Traiter l'ID du nœud
                            if isinstance(node_id, str):
                                if node_id.startswith('!'):
                                    id_int = int(node_id[1:], 16)
                                else:
                                    id_int = int(node_id)
                            else:
                                id_int = int(node_id)
                            
                            # Extraire le nom
                            user_info = node_info.get('user', {})
                            if user_info:
                                shortName = user_info.get('shortName', '???')
                                longName = user_info.get('longName', 'Unknown')
                                name = f"{shortName} {longName}"
                            else:
                                name = f"!{id_int:08x}"
                            
                            last_heard = node_info.get('lastHeard', 0)
                            
                            # Collecter métriques si activé
                            rssi = 0
                            snr = 0.0
                            if COLLECT_SIGNAL_METRICS:
                                rssi = node_info.get('rssi', 0)
                                snr = node_info.get('snr', 0.0)
                            
                            # Filtre temporel
                            if last_heard == 0 or last_heard < cutoff_time:
                                skipped_by_date += 1
                                continue
                            
                            node_data = {
                                'id': id_int,
                                'name': name,
                                'last_heard': last_heard
                            }

                            if COLLECT_SIGNAL_METRICS:
                                node_data['rssi'] = rssi
                                node_data['snr'] = snr
                            
                            node_list.append(node_data)
                            
                    except Exception as e:
                        debug_print(f"Erreur traitement nœud {node_id}: {e}")
                        continue
                
                # ✅ Fermeture automatique grâce au context manager
                
            debug_print(f"✅ Résultats pour {remote_host} (filtre: {days_filter}j):")
            debug_print(f"   - Nœuds acceptés: {len(node_list)}")
            debug_print(f"   - Ignorés (relayés): {skipped_by_hops}")
            debug_print(f"   - Ignorés (>{days_filter}j): {skipped_by_date}")
            debug_print(f"   - Ignorés (pas de métriques): {skipped_by_metrics}")
            
            return node_list
            
        except Exception as e:
            error_print(f"Erreur récupération nœuds distants {remote_host}: {e}")
            return []

    def get_all_remote_nodes(self, remote_host, remote_port=4403, days_filter=30):
        """Récupérer TOUS les nœuds (directs + relayés) d'un nœud distant"""
        
        current_time = time.time()
        cutoff_time = current_time - (days_filter * 24 * 3600)
        debug_print(f"Filtre temporel TOUS nœuds: derniers {days_filter} jours")
        
        skipped_by_date = 0
        skipped_by_no_data = 0
        
        try:
            debug_print(f"Connexion au nœud distant {remote_host}...")
            
            # ✅ Utilisation de SafeTCPConnection avec context manager
            with SafeTCPConnection.connect(remote_host, remote_port) as remote_interface:
                time.sleep(2)  # Laisser les données se charger
                remote_nodes = remote_interface.nodes
                
                node_list = []
                for node_id, node_info in remote_nodes.items():
                    try:
                        if not isinstance(node_info, dict):
                            continue
                        
                        last_heard = node_info.get('lastHeard', 0)
                        if last_heard == 0:
                            skipped_by_no_data += 1
                            continue
                        
                        if last_heard < cutoff_time:
                            skipped_by_date += 1
                            continue
                        
                        # Traiter l'ID
                        if isinstance(node_id, str):
                            if node_id.startswith('!'):
                                id_int = int(node_id[1:], 16)
                            else:
                                id_int = int(node_id)
                        else:
                            id_int = int(node_id)
                        
                        # Extraire le nom
                        user_info = node_info.get('user', {})
                        if user_info:
                            shortName = user_info.get('shortName', '???')
                            longName = user_info.get('longName', 'Unknown')
                            name = f"{shortName} {longName}"
                        else:
                            name = f"!{id_int:08x}"
                        
                        hops_away = node_info.get('hopsAway', None)
                        
                        node_data = {
                            'id': id_int,
                            'name': name,
                            'last_heard': last_heard,
                            'hops_away': hops_away if hops_away is not None else 999
                        }
                        
                        node_list.append(node_data)
                        
                    except Exception as e:
                        debug_print(f"Erreur traitement nœud {node_id}: {e}")
                        continue
                
                # ✅ Fermeture automatique grâce au context manager
                
            debug_print(f"✅ Résultats TOUS nœuds pour {remote_host} (filtre: {days_filter}j):")
            debug_print(f"   - Nœuds acceptés: {len(node_list)}")
            debug_print(f"   - Ignorés (>{days_filter}j): {skipped_by_date}")
            debug_print(f"   - Ignorés (pas de données): {skipped_by_no_data}")
            
            return node_list
            
        except Exception as e:
            error_print(f"Erreur récupération TOUS nœuds {remote_host}: {e}")
            return []

    def get_tigrog2_paginated(self, page=1, days_filter=3):
        """Récupérer et formater les nœuds tigrog2 avec pagination simple"""
        try:
            remote_nodes = self.get_remote_nodes(REMOTE_NODE_HOST, days_filter=days_filter)
            
            if not remote_nodes:
                return f"Aucun nœud direct trouvé sur {REMOTE_NODE_NAME}"
            
            # Tri
            if COLLECT_SIGNAL_METRICS:
                remote_nodes.sort(key=lambda x: (x.get('rssi', -999), x['last_heard']), reverse=True)
            else:
                remote_nodes.sort(key=lambda x: x['last_heard'], reverse=True)
            
            # Pagination
            nodes_per_page = 8
            total_nodes = len(remote_nodes)
            total_pages = (total_nodes + nodes_per_page - 1) // nodes_per_page
            
            page = validate_page_number(page, total_pages)
            
            start_idx = (page - 1) * nodes_per_page
            end_idx = min(start_idx + nodes_per_page, total_nodes)
            page_nodes = remote_nodes[start_idx:end_idx]
            
            lines = []
            
            if page == 1:
                lines.append(f"📡 Nœuds DIRECTS de {REMOTE_NODE_NAME} (<3j) ({total_nodes}):")
            
            for node in page_nodes:
                line = self._format_node_line(node)
                lines.append(line)
            
            if total_pages > 1:
                lines.append(f"{page}/{total_pages}")
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"Erreur {REMOTE_NODE_NAME}: {str(e)[:30]}"

    def get_all_nodes_alphabetical(self, days_limit=30):
        """Récupérer tous les nœuds triés alphabétiquement avec filtre temporel"""
        try:
            remote_nodes = self.get_all_remote_nodes(
                REMOTE_NODE_HOST, 
                days_filter=days_limit
            )
            
            if not remote_nodes:
                return f"Aucun nœud trouvé sur {REMOTE_NODE_NAME} (<{days_limit}j)"
            
            # Fonction de tri
            def get_sort_key(node):
                name = node.get('name', 'Unknown')
                if ' ' in name:
                    # Extraire le longName (après le premier espace)
                    return name.split(' ', 1)[1].lower()
                return name.lower()
            
            remote_nodes.sort(key=get_sort_key)
            
            lines = [f"📡 TOUS les nœuds de {REMOTE_NODE_NAME} (<{days_limit}j) - {len(remote_nodes)} nœuds:\n"]
            
            for node in remote_nodes:
                name = node.get('name', 'Unknown')
                last_heard = node.get('last_heard', 0)
                hops_away = node.get('hops_away', 999)
                
                if last_heard > 0:
                    elapsed_str = format_elapsed_time(last_heard)
                else:
                    elapsed_str = "jamais"
                
                if hops_away == 0:
                    hop_str = "direct"
                elif hops_away == 999:
                    hop_str = "?"
                else:
                    hop_str = f"{hops_away} hop{'s' if hops_away > 1 else ''}"
                
                lines.append(f"• {name} ({hop_str}, {elapsed_str})")
            
            return "\n".join(lines)
            
        except Exception as e:
            error_print(f"Erreur get_all_nodes_alphabetical: {e}")
            import traceback
            error_print(traceback.format_exc())
            return f"Erreur: {str(e)[:100]}"

    def _format_node_line(self, node):
        """Formater une ligne de nœud pour l'affichage"""
        name = node.get('name', 'Unknown')
        
        if COLLECT_SIGNAL_METRICS:
            rssi = node.get('rssi', 0)
            snr = node.get('snr', 0.0)
            icon = get_signal_quality_icon(rssi, snr)
            return f"{icon} {truncate_text(name, 15)}: {rssi}dBm SNR:{snr:.1f}"
        else:
            last_heard = node.get('last_heard', 0)
            elapsed_str = format_elapsed_time(last_heard) if last_heard > 0 else "jamais"
            return f"• {truncate_text(name, 20)} ({elapsed_str})"
