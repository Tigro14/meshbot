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
    def get_remote_nodes(self, remote_host, remote_port=4403, days_filter=3):
        """Récupérer la liste des nœuds directs (0 hop) d'un nœud distant
        
        Args:
            remote_host: IP du nœud distant
            remote_port: Port TCP (défaut: 4403)
            days_filter: Nombre de jours pour filtrer les nœuds (défaut: 3)
            
        Returns:
            list: Liste de nœuds avec leurs infos, DÉJÀ FILTRÉS PAR DATE
        """
        
        # ✅ AJOUT : Calcul du seuil temporel
        current_time = time.time()
        cutoff_time = current_time - (days_filter * 24 * 3600)
        debug_print(f"Filtre temporel: derniers {days_filter} jours")
        
        # Compteurs pour statistiques
        skipped_by_hops = 0
        skipped_by_date = 0
        skipped_by_metrics = 0
        
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
                            # Concaténer shortName + longName
                            if short_name and long_name:
                                 # Si les deux existent et sont différents
                                if short_name.lower() != long_name.lower():
                                    name = f"{short_name} {long_name}"
                                else:
                                # Si identiques, afficher une seule fois
                                    name = long_name
                            elif long_name:
                                name = long_name
                            elif short_name:
                                name = short_name
                            else:
                                name = f"Node-{id_int:04x}"
                        
                        last_heard = node_info.get('lastHeard', 0)
                        
                        # Collecter les métriques de signal si activé
                        rssi = 0
                        snr = 0.0
                        if COLLECT_SIGNAL_METRICS:
                            rssi = node_info.get('rssi', 0)
                            snr = node_info.get('snr', 0.0)
                        
                        # ✅ AJOUT : FILTRE 2 - VÉRIFIER LA DATE
                        last_heard = node_info.get('lastHeard', 0)
                        
                        if last_heard == 0 or last_heard < cutoff_time:
                            skipped_by_date += 1
                            days_ago = (current_time - last_heard) / 86400 if last_heard > 0 else 999
                            debug_print(f"Nœud {node_id} ignoré (>{days_filter}j: {days_ago:.1f}j)")
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
            debug_print(f"✅ Résultats pour {remote_host} (filtre: {days_filter}j):")
            debug_print(f"   - Nœuds acceptés: {len(node_list)}")
            debug_print(f"   - Ignorés (relayés): {skipped_by_hops}")
            debug_print(f"   - Ignorés (>{days_filter}j): {skipped_by_date}")
            debug_print(f"   - Ignorés (pas de métriques): {skipped_by_metrics}") 

            return node_list
            
        except Exception as e:
            error_print(f"Erreur récupération nœuds distants {remote_host}: {e}")
            return []
        finally:  
            if remote_interface:
                try:
                    debug_print(f"Fermeture connexion {remote_host}")
                except Exception as e:
                    debug_print(f"Erreur fermeture: {e}")

    def get_all_remote_nodes(self, remote_host, remote_port=4403, days_filter=30):
        """Récupérer TOUS les nœuds (directs + relayés) d'un nœud distant
        
        Args:
            remote_host: IP du nœud distant
            remote_port: Port TCP (défaut: 4403)
            days_filter: Nombre de jours pour filtrer (défaut: 30)
            
        Returns:
            list: Liste de TOUS les nœuds (pas de filtre hopsAway)
        """
        # ✅ Calcul du seuil temporel
        current_time = time.time()
        cutoff_time = current_time - (days_filter * 24 * 3600)
        debug_print(f"Filtre temporel TOUS nœuds: derniers {days_filter} jours")
        
        # Compteurs pour statistiques
        skipped_by_date = 0
        skipped_by_no_data = 0
        
        remote_interface = None
        try:
            debug_print(f"Connexion au nœud distant {remote_host}...")
            
            remote_interface = meshtastic.tcp_interface.TCPInterface(
                hostname=remote_host, 
                portNumber=remote_port
            )
            
            time.sleep(2)
            remote_nodes = remote_interface.nodes
            
            # ✅ PAS DE FILTRE hopsAway - on prend tout !
            node_list = []
            for node_id, node_info in remote_nodes.items():
                try:
                    if not isinstance(node_info, dict):
                        continue
                    
                    # ✅ Vérifier qu'on a des données minimales
                    last_heard = node_info.get('lastHeard', 0)
                    if last_heard == 0:
                        skipped_by_no_data += 1
                        debug_print(f"Nœud {node_id} ignoré (pas de lastHeard)")
                        continue
                    
                    # ✅ FILTRE TEMPOREL uniquement
                    if last_heard < cutoff_time:
                        skipped_by_date += 1
                        days_ago = (current_time - last_heard) / 86400
                        debug_print(f"Nœud {node_id} ignoré (>{days_filter}j: {days_ago:.1f}j)")
                        continue
                    
                    # Traiter le node_id
                    if isinstance(node_id, str):
                        if node_id.startswith('!'):
                            clean_id = node_id[1:]
                            id_int = int(clean_id, 16)
                        elif node_id.isdigit():
                            id_int = int(node_id)
                        else:
                            id_int = int(node_id, 16)
                    else:
                        id_int = int(node_id)
                    
                    # Récupérer le nom
                    name = "Unknown"
                    if 'user' in node_info and isinstance(node_info['user'], dict):
                        user = node_info['user']
                        short_name = user.get('shortName', '')
                        long_name = user.get('longName', '')
                        
                        if short_name and long_name:
                            if short_name.lower() != long_name.lower():
                                name = f"{short_name} {long_name}"
                            else:
                                name = long_name
                        elif long_name:
                            name = long_name
                        elif short_name:
                            name = short_name
                        else:
                            name = f"Node-{id_int:04x}"
                    
                    # ✅ Récupérer hopsAway pour info
                    hops_away = node_info.get('hopsAway', 0)
                    
                    # Collecter les métriques
                    node_data = {
                        'id': id_int,
                        'name': name,
                        'last_heard': last_heard,
                        'hops_away': hops_away  # ✅ Ajouter pour affichage
                    }
                    
                    if COLLECT_SIGNAL_METRICS:
                        node_data['rssi'] = node_info.get('rssi', 0)
                        node_data['snr'] = node_info.get('snr', 0.0)
                    
                    node_list.append(node_data)
                    
                    debug_print(f"✅ Nœud accepté: {name} (hops:{hops_away})")
                    
                except Exception as e:
                    debug_print(f"Erreur traitement nœud {node_id}: {e}")
                    continue
            
            remote_interface.close()
            
            # ✅ LOG RÉCAPITULATIF
            debug_print(f"✅ Résultats TOUS nœuds pour {remote_host} (filtre: {days_filter}j):")
            debug_print(f"   - Nœuds acceptés: {len(node_list)}")
            debug_print(f"   - Ignorés (>{days_filter}j): {skipped_by_date}")
            debug_print(f"   - Ignorés (pas de données): {skipped_by_no_data}")
            
            return node_list
            
        except Exception as e:
            error_print(f"Erreur récupération TOUS nœuds {remote_host}: {e}")
            return []
        finally:
            if remote_interface:
                try:
                    debug_print(f"Fermeture connexion {remote_host}")
                except Exception as e:
                    debug_print(f"Erreur fermeture: {e}")

    def get_tigrog2_paginated(self, page=1, days_filter=3):  # ✅ Ajouter paramètre
        """Récupérer et formater les nœuds tigrog2 avec pagination simple"""
        try:
            remote_nodes = self.get_remote_nodes(REMOTE_NODE_HOST, days_filter=days_filter)  # ✅ Passer 
            
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

    def get_all_nodes_alphabetical(self, days_limit=30):
        """Récupérer tous les nœuds triés alphabétiquement avec filtre temporel"""
        try:
            # ✅ Le filtrage par date est DÉJÀ fait dans get_remote_nodes()
            remote_nodes = self.get_all_remote_nodes(
                REMOTE_NODE_HOST, 
                days_filter=days_limit
            )
            
            if not remote_nodes:
                return f"Aucun nœud trouvé sur {REMOTE_NODE_NAME} (<{days_limit}j)"
            
            # ✅ Trier par longName
            def get_sort_key(node):
                name = node.get('name', 'Unknown')
                if ' ' in name:
                    # Extraire le longName (partie après le premier espace)
                    return name.split(' ', 1)[1].lower()
                else:
                    # Sinon, utiliser le nom tel quel
                    return name.lower()
            
            # ✅ CORRECTION : Utiliser remote_nodes au lieu de recent_nodes
            remote_nodes.sort(key=get_sort_key)
            
            # ✅ AJOUT : Définir current_time pour le calcul du temps écoulé
            current_time = time.time()
            
            # Construire la réponse
            lines = []
            lines.append(f"📋 Tous les nœuds de {REMOTE_NODE_NAME} (<{days_limit}j):")
            # ✅ CORRECTION : remote_nodes au lieu de recent_nodes
            lines.append(f"Total: {len(remote_nodes)} nœuds\n")
            
            # ✅ CORRECTION : remote_nodes au lieu de recent_nodes
            for node in remote_nodes:
                name = node.get('name', 'Unknown')
                snr = node.get('snr', 0.0)
                rssi = node.get('rssi', 0)
                last_heard = node.get('last_heard', 0)
                hops_away = node.get('hops_away', 0)  
                
                # Calculer temps écoulé
                elapsed = int(current_time - last_heard) if last_heard > 0 else 0
                if elapsed < 3600:  # < 1h
                    time_str = f"{elapsed//60}m"
                elif elapsed < 86400:  # < 1j
                    time_str = f"{elapsed//3600}h"
                else:
                    time_str = f"{elapsed//86400}j"
                
                # Icône qualité signal basée sur SNR
                if snr >= 10:
                    icon = "🟢"
                elif snr >= 5:
                    icon = "🟡"
                elif snr >= 0:
                    icon = "🟠"
                else:
                    icon = "🔴"
            
                # ✅ AJOUT : Indicateur de hops pour les nœuds relayés
                hops_indicator = ""
                if hops_away > 0:
                    hops_indicator = f" [{hops_away}hop]"  # [1h], [2h], etc.
                
                # ✅ MODIFICATION : Ajouter hops_indicator dans la ligne
#                line = f"{icon} {name}{hops_indicator}"
#                if snr != 0:
#                    line += f" | SNR:{snr:.1f}dB"
#                if rssi != 0:
#                    line += f" | {rssi}dBm"
#                line += f" | {time_str}"
                # ✅ Construire la ligne avec hops_indicator ET node_id pour debug
                line = f"{icon} {name}{hops_indicator} [!{node['id']:08x}]"  # ← AJOUT node_id
                if snr != 0:
                    line += f" | SNR:{snr:.1f}dB"
                if rssi != 0:
                    line += f" | {rssi}dBm"
                line += f" | {time_str}"
                
                lines.append(line)
                        
            return "\n".join(lines)
        
        except Exception as e:
            error_print(f"Erreur get_all_nodes_alphabetical: {e}")
            return f"Erreur: {str(e)[:50]}"
    
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
