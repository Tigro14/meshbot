#!/usr/bin/env python3
"""
Client pour la récupération des nœuds distants
"""

import time
import meshtastic.tcp_interface
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

    def get_remote_nodes(self, remote_host, remote_port=4403):
        """Récupérer la liste des nœuds directs (0 hop) d'un nœud distant"""
        remote_interface = None  # ✅ Initialiser
        try:
            debug_print(f"Connexion au nœud distant {remote_host}...")
            
            # Tenter une connexion TCP au nœud distant
            remote_interface = meshtastic.tcp_interface.TCPInterface(
                hostname=remote_host, 
                portNumber=remote_port
            )
            
            # Attendre que les données se chargent
            time.sleep(2)
            
            # Récupérer les nœuds
            remote_nodes = remote_interface.nodes
            
            # Formater les résultats - FILTRER SEULEMENT LES NŒUDS DIRECTS
            node_list = []
            for node_id, node_info in remote_nodes.items():
                try:
                    if isinstance(node_info, dict):
                        # VÉRIFIER SI LE NŒUD A ÉTÉ REÇU DIRECTEMENT
                        # Le critère le plus fiable est hopsAway = 0
                        hops_away = node_info.get('hopsAway', None)
                        
                        # Si hopsAway existe, l'utiliser comme critère principal
                        if hops_away is not None:
                            if hops_away > 0:
                                debug_print(f"Nœud {node_id} ignoré (hopsAway={hops_away})")
                                continue
                            else:
                                debug_print(f"Nœud {node_id} accepté (hopsAway={hops_away})")
                        else:
                            # Fallback : Si pas de hopsAway, être plus tolérant avec RSSI
                            # Un RSSI peut être 0 pour diverses raisons techniques
                            rssi = node_info.get('rssi', 0)
                            snr = node_info.get('snr', 0.0)
                            
                            # Accepter si on a au moins SNR ou si last_heard récent
                            last_heard = node_info.get('lastHeard', 0)
                            current_time = time.time()
                            is_recent = (current_time - last_heard) < 3600  # 1 heure
                            
                            if rssi == 0 and snr == 0.0 and not is_recent:
                                debug_print(f"Nœud {node_id} ignoré (pas de hopsAway, pas de métriques, pas récent)")
                                continue
                            else:
                                debug_print(f"Nœud {node_id} accepté (RSSI:{rssi}, SNR:{snr}, recent:{is_recent})")
                        
                        # Traiter le node_id - peut être string ou int
                        if isinstance(node_id, str):
                            if node_id.startswith('!'):
                                # Format !12345678 - retirer le ! puis convertir hex
                                clean_id = node_id[1:]
                                id_int = int(clean_id, 16)
                            elif node_id.isdigit():
                                # String numérique décimale
                                id_int = int(node_id)
                            else:
                                # Autres cas, essayer conversion hex directe
                                id_int = int(node_id, 16)
                        else:
                            # Déjà un int
                            id_int = int(node_id)
                        
                        # Récupérer le nom - privilégier shortName
                        name = "Unknown"
                        short_name = None
                        if 'user' in node_info and isinstance(node_info['user'], dict):
                            user = node_info['user']
                            short_name = user.get('shortName', '')
                            long_name = user.get('longName', '')
                            
                            # Utiliser shortName en priorité, sinon longName tronqué
                            if short_name:
                                name = short_name
                            elif long_name:
                                name = long_name[:8]  # Tronquer à 8 caractères
                            else:
                                name = f"Node-{id_int:04x}"
                        
                        last_heard = node_info.get('lastHeard', 0)
                        
                        # Collecter les métriques de signal si activé
                        rssi = 0
                        snr = 0.0
                        if COLLECT_SIGNAL_METRICS:
                            rssi = node_info.get('rssi', 0)
                            snr = node_info.get('snr', 0.0)
                        
                        # FILTRE TEMPOREL : ne garder que les nœuds vus dans les 3 derniers jours
                        current_time = time.time()
                        three_days_ago = current_time - (3 * 24 * 3600)  # 3 jours en secondes
                        
                        if last_heard == 0 or last_heard < three_days_ago:
                            debug_print(f"Nœud {node_id} ignoré (trop ancien: {last_heard})")
                            continue
                        
                        node_data = {
                            'id': id_int,
                            'name': name,
                            'last_heard': last_heard
                        }
                        
                        # Ajouter les métriques si collectées
                        if COLLECT_SIGNAL_METRICS:
                            node_data['rssi'] = rssi
                            node_data['snr'] = snr
                        
                        node_list.append(node_data)
                        
                        debug_print(f"✅ Nœud direct: {name} RSSI:{rssi} SNR:{snr:.1f}")
                        
                except Exception as e:
                    debug_print(f"Erreur traitement nœud {node_id}: {e}")
                    continue
            
            remote_interface.close()
            debug_print(f"✅ {len(node_list)} nœuds DIRECTS récupérés de {remote_host}")
            return node_list
            
        except Exception as e:
            error_print(f"Erreur récupération nœuds distants {remote_host}: {e}")
            return []
        finally:  # ✅ AJOUTER ce bloc
            if remote_interface:
                try:
                    debug_print(f"Fermeture connexion {remote_host}")
                    remote_interface.close()
                except Exception as e:
                    debug_print(f"Erreur fermeture: {e}")
    
    def get_tigrog2_paginated(self, page=1):
        """Récupérer et formater les nœuds tigrog2 avec pagination simple"""
        try:
            remote_nodes = self.get_remote_nodes(REMOTE_NODE_HOST)
            
            if not remote_nodes:
                return f"Aucun nœud direct trouvé sur {REMOTE_NODE_NAME}"
            
            # Trier
            if COLLECT_SIGNAL_METRICS:
                remote_nodes.sort(key=lambda x: (x.get('rssi', -999), x['last_heard']), reverse=True)
            else:
                remote_nodes.sort(key=lambda x: x['last_heard'], reverse=True)
            
            # Calculer la pagination - plus simple
            nodes_per_page = 8  # Fixe, testé pour fonctionner dans les limites
            total_nodes = len(remote_nodes)
            total_pages = (total_nodes + nodes_per_page - 1) // nodes_per_page
            
            # Valider page
            page = validate_page_number(page, total_pages)
            
            # Extraire nœuds pour cette page
            start_idx = (page - 1) * nodes_per_page
            end_idx = min(start_idx + nodes_per_page, total_nodes)
            page_nodes = remote_nodes[start_idx:end_idx]
            
            # Construire réponse
            lines = []
            
            # Header seulement page 1
            if page == 1:
                lines.append(f"📡 Nœuds DIRECTS de {REMOTE_NODE_NAME} (<3j) ({total_nodes}):")
            
            # Formater chaque nœud
            for node in page_nodes:
                line = self._format_node_line(node)
                lines.append(line)
            
            # Info pagination si nécessaire
            if total_pages > 1:
                lines.append(f"{page}/{total_pages}")
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"Erreur {REMOTE_NODE_NAME}: {str(e)[:30]}"
    
    def _format_node_line(self, node):
        """Formater une ligne de nœud selon la configuration"""
        short_name = truncate_text(node['name'], 8)
        
        # Calculer le temps écoulé
        time_str = format_elapsed_time(node['last_heard'])
        
        # Indicateur de qualité RSSI
        rssi_icon = get_signal_quality_icon(node.get('rssi', 0))
        
        # Indicateur de qualité SNR
        snr_icon = get_signal_quality_icon(node.get('snr', 0.0))
        
        # Format de base : icône RSSI + icône SNR + nom court + temps
        line_parts = [rssi_icon]
        if snr_icon:
            line_parts.append(snr_icon)
        line_parts.extend([short_name, time_str])
        
        if SHOW_RSSI and COLLECT_SIGNAL_METRICS and 'rssi' in node and node['rssi'] != 0:
            line_parts.append(f"{node['rssi']}dB")
        
        if SHOW_SNR and COLLECT_SIGNAL_METRICS and 'snr' in node and node['snr'] != 0:
            line_parts.append(f"SNR:{node['snr']:.1f}")
        
        return " ".join(line_parts)
