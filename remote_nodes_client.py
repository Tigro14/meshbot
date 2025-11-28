#!/usr/bin/env python3
"""
Client pour la récupération des nœuds distants

⚠️ ESP32 LIMITATION:
ESP32 Meshtastic nodes only support ONE TCP connection at a time.
This client MUST use the shared interface when connecting to the same
host as the main bot connection. Creating a new connection would kill
the main bot connection and cause packet loss.

USAGE:
    client = RemoteNodesClient()
    client.set_interface(main_interface)  # Share the main bot's interface
    nodes = client.get_remote_nodes(host, port, days_filter)
"""

import time
import threading
from config import *
from utils import (
    debug_print,
    error_print,
    info_print,
    format_elapsed_time,
    get_signal_quality_icon,
    truncate_text,
    validate_page_number
)

class RemoteNodesClient:
    def __init__(self, interface=None, connection_mode=None, tcp_host=None):
        """
        Initialize the RemoteNodesClient
        
        Args:
            interface: Shared Meshtastic interface to reuse
            connection_mode: 'serial' or 'tcp' (from config if None)
            tcp_host: TCP host IP (from config if None)
        """
        self.node_manager = None
        self.interface = interface  # Interface principale à réutiliser (single-node mode)
        
        # Config values - prefer passed values, fall back to globals
        self._connection_mode = connection_mode
        self._tcp_host = tcp_host
        
        # ✅ AJOUT: Système de cache pour éviter connexions répétées
        self._cache = {}           # Stockage des résultats
        self._cache_ttl = 60       # Cache valide 60 secondes
        self._cache_stats = {      # Statistiques pour monitoring
            'hits': 0,
            'misses': 0,
            'last_cleanup': time.time()
        }

        # Démarrer un thread de nettoyage
        self._cleanup_thread = threading.Thread(target=self._cache_cleanup_loop, daemon=True, name="CacheCleanup")
        self._cleanup_thread.start()
    
    def _get_connection_mode(self):
        """Get connection mode from config or constructor"""
        if self._connection_mode is not None:
            return self._connection_mode.lower()
        return globals().get('CONNECTION_MODE', 'serial').lower()
    
    def _get_tcp_host(self):
        """Get TCP host from config or constructor"""
        if self._tcp_host is not None:
            return self._tcp_host
        return globals().get('TCP_HOST', '')
    
    def _must_use_shared_interface(self, remote_host):
        """
        Check if shared interface MUST be used for this host
        
        ESP32 only supports ONE TCP connection - must use shared interface
        when connecting to the same host as main bot connection.
        
        Args:
            remote_host: The host we want to connect to
            
        Returns:
            bool: True if shared interface MUST be used, False if new connection allowed
        """
        connection_mode = self._get_connection_mode()
        tcp_host = self._get_tcp_host()
        return (connection_mode == 'tcp' and 
                tcp_host == remote_host and 
                self.interface is not None)

    def set_node_manager(self, node_manager):
        """Définir le node_manager après l'initialisation"""
        self.node_manager = node_manager
    
    def set_interface(self, interface):
        """Définir l'interface Meshtastic principale à réutiliser"""
        self.interface = interface

    def _cache_cleanup_loop(self):
        """Nettoyer le cache toutes les 5 minutes"""
        while True:
            time.sleep(300)  # 5 minutes
            self._cleanup_cache()
    
    def _cleanup_cache(self):
        """Supprimer les entrées expirées du cache"""
        now = time.time()
        expired_keys = [
            key for key, data in self._cache.items()
            if now - data['timestamp'] > self._cache_ttl
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            debug_print(f"🧹 Cache nettoyé : {len(expired_keys)} entrées expirées")
        
        self._cache_stats['last_cleanup'] = now

    def _cache_get(self, key):
        """
        Récupérer une valeur du cache si elle existe et est valide
        
        Args:
            key: Clé du cache (généralement "host:port:days")
        
        Returns:
            list ou None: Les données cachées ou None si expiré/inexistant
        """
        if key not in self._cache:
            self._cache_stats['misses'] += 1
            return None
        
        cached_data = self._cache[key]
        current_time = time.time()
        
        # Vérifier si le cache est expiré
        if current_time - cached_data['timestamp'] > self._cache_ttl:
            debug_print(f"💾 Cache expiré pour {key}")
            del self._cache[key]
            self._cache_stats['misses'] += 1
            return None
        
        # Cache valide
        self._cache_stats['hits'] += 1
        age = current_time - cached_data['timestamp']
        debug_print(f"✅ Cache hit pour {key} (âge: {age:.1f}s)")
        
        return cached_data['data']


    def _cache_set(self, key, data):
        """
        Stocker des données dans le cache
        
        Args:
            key: Clé du cache
            data: Données à stocker
        """
        self._cache[key] = {
            'data': data,
            'timestamp': time.time()
        }
        
        debug_print(f"💾 Cache mis à jour pour {key} ({len(data)} éléments)")
        
        # Nettoyage automatique si trop d'entrées
        if len(self._cache) > 50:
            self._cleanup_cache()


    def _cleanup_cache(self):
        """
        Nettoyer les entrées expirées du cache
        """
        current_time = time.time()
        expired_keys = []
        
        for key, cached_data in self._cache.items():
            if current_time - cached_data['timestamp'] > self._cache_ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            debug_print(f"🧹 Cache nettoyé : {len(expired_keys)} entrées expirées")
        
        self._cache_stats['last_cleanup'] = current_time


    def get_cache_stats(self):
        """
        Obtenir les statistiques du cache
        
        Returns:
            dict: Statistiques (hits, misses, size, hit_rate)
        """
        total_requests = self._cache_stats['hits'] + self._cache_stats['misses']
        hit_rate = (self._cache_stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'hits': self._cache_stats['hits'],
            'misses': self._cache_stats['misses'],
            'size': len(self._cache),
            'hit_rate': f"{hit_rate:.1f}%",
            'last_cleanup': self._cache_stats['last_cleanup']
        }

    def get_remote_nodes(self, remote_host, remote_port=4403, days_filter=3):
        """
        Récupérer les nœuds distants d'un node Meshtastic
        
        ⚠️ ESP32 LIMITATION:
        ESP32 only supports ONE TCP connection at a time. This method MUST use
        the shared interface when connecting to the same host as the main bot
        connection. Creating a new connection would kill the main bot connection.
        
        Args:
            remote_host: IP address of the Meshtastic node
            remote_port: TCP port (default 4403)
            days_filter: Filter nodes seen in the last N days
            
        Returns:
            list: List of node dictionaries
        """
        cache_key = f"{remote_host}:{remote_port}:{days_filter}"

        # Vérifier le cache d'abord (TTL: 60 secondes)
        cached_nodes = self._cache_get(cache_key)
        if cached_nodes is not None:
            debug_print(f"💾 Cache hit pour {cache_key}: {len(cached_nodes)} nœuds")
            return cached_nodes

        current_time = time.time()
        cutoff_time = current_time - (days_filter * 24 * 3600)
        debug_print(f"Filtre temporel: derniers {days_filter} jours")

        skipped_by_hops = 0
        skipped_by_date = 0
        skipped_by_metrics = 0
        
        # Check if shared interface MUST be used (ESP32 single-connection limitation)
        must_use_shared = self._must_use_shared_interface(remote_host)
        
        if must_use_shared:
            debug_print(f"♻️ OBLIGATOIRE: Réutilisation interface partagée (même host TCP: {remote_host})")
        
        # Retry logic pour connexion TCP (only for different hosts)
        max_retries = 1 if must_use_shared else 2
        retry_delay = 3

        for attempt in range(max_retries):
            try:
                # ✅ RÉUTILISER l'interface principale si disponible (single-node mode)
                if self.interface is not None:
                    # Vérifier que l'interface correspond au host/port demandé
                    interface_host = getattr(self.interface, 'hostname', None)
                    if interface_host == remote_host or must_use_shared:
                        debug_print(f"♻️ Réutilisation interface principale pour {remote_host}")
                        remote_interface = self.interface
                        close_interface = False
                    else:
                        # Different host - check if we're allowed to create new connection
                        connection_mode = self._get_connection_mode()
                        tcp_host = self._get_tcp_host()
                        if connection_mode == 'tcp':
                            # In TCP mode, warn about creating separate connection
                            info_print(f"⚠️ Création connexion TCP séparée vers {remote_host} (host différent de {tcp_host})")
                        if attempt > 0:
                            debug_print(f"🔗 Connexion TCP à {remote_host} (tentative {attempt + 1}/{max_retries})...")
                        else:
                            debug_print(f"🔗 Connexion TCP à {remote_host}... (host différent)")
                        from safe_tcp_connection import SafeTCPConnection
                        remote_interface = SafeTCPConnection(remote_host, remote_port, wait_time=2).__enter__()
                        close_interface = True
                else:
                    # No interface set - we must create one
                    if must_use_shared:
                        # This shouldn't happen in normal operation
                        error_print(f"❌ Interface non disponible mais mode TCP actif - impossible de requêter {remote_host}")
                        return []
                    
                    if attempt > 0:
                        debug_print(f"🔗 Connexion TCP à {remote_host} (tentative {attempt + 1}/{max_retries})...")
                    else:
                        debug_print(f"🔗 Connexion TCP à {remote_host}... (pas d'interface partagée)")
                    from safe_tcp_connection import SafeTCPConnection
                    remote_interface = SafeTCPConnection(remote_host, remote_port, wait_time=2).__enter__()
                    close_interface = True
                
                try:
                    # Récupérer les nœuds
                    remote_nodes = remote_interface.nodes
                    
                    # Formater les résultats - FILTRER SEULEMENT LES NŒUDS DIRECTS
                    node_list = []
                    for node_id, node_info in remote_nodes.items():
                        try:
                            if isinstance(node_info, dict):
                                # VÉRIFIER SI LE NŒUD A ÉTÉ REÇU DIRECTEMENT
                                hops_away = node_info.get('hopsAway', None)
                                
                                if hops_away is not None:
                                    if hops_away > 0:
                                        skipped_by_hops += 1
                                        continue
                                    else:
                                        debug_print(f"Nœud direct accepté: {node_id}")
                                
                                # Vérifier la date
                                last_heard = node_info.get('lastHeard', 0)
                                if last_heard < cutoff_time:
                                    skipped_by_date += 1
                                    continue
                                
                                # Convertir node_id
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
                                
                                hops_away = node_info.get('hopsAway', 0)
                                
                                node_data = {
                                    'id': id_int,
                                    'name': name,
                                    'last_heard': last_heard,
                                    'hops_away': hops_away
                                }
                                
                                if COLLECT_SIGNAL_METRICS:
                                    node_data['rssi'] = node_info.get('rssi', 0)
                                    node_data['snr'] = node_info.get('snr', 0.0)
                                
                                node_list.append(node_data)
                                
                        except Exception as node_error:
                            debug_print(f"Erreur parsing nœud {node_id}: {node_error}")
                            continue
                    
                    debug_print(f"   - Nœuds acceptés: {len(node_list)}")
                    debug_print(f"   - Ignorés (relayés): {skipped_by_hops}")
                    debug_print(f"   - Ignorés (>{days_filter}j): {skipped_by_date}")
                    debug_print(f"   - Ignorés (pas de métriques): {skipped_by_metrics}")

                    # ✅ ÉTAPE 3: Mettre en cache
                    self._cache_set(cache_key, node_list)
                    
                    return node_list
                
                finally:
                    # Fermer uniquement si nous avons créé une nouvelle connexion
                    if close_interface:
                        try:
                            remote_interface.__exit__(None, None, None)
                        except:
                            pass
                
                # Si on arrive ici, la connexion a réussi - sortir de la boucle
                break
                
            except OSError as e:
                # Erreurs réseau (connexion refusée, timeout, etc.)
                if attempt < max_retries - 1:
                    info_print(f"⚠️ Erreur récupération nœuds distants {remote_host}, tentative {attempt + 1}/{max_retries}")
                    debug_print(f"   Type: {type(e).__name__}")
                    debug_print(f"   Message: {e}")
                    debug_print(f"   Nouvelle tentative dans {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    error_print(f"❌ Erreur récupération nœuds distants {remote_host} après {max_retries} tentatives:")
                    error_print(f"   Type: {type(e).__name__}")
                    error_print(f"   Message: {e}")
                    return []
                    
            except Exception as e:
                # Autres erreurs
                if attempt < max_retries - 1:
                    info_print(f"⚠️ Erreur nœuds distants {remote_host}, tentative {attempt + 1}/{max_retries}")
                    debug_print(f"   Type: {type(e).__name__}")
                    debug_print(f"   Message: {e}")
                    debug_print(f"   Nouvelle tentative dans {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    error_print(f"❌ Erreur récupération nœuds distants {remote_host} après {max_retries} tentatives:")
                    error_print(f"   Type: {type(e).__name__}")
                    error_print(f"   Message: {e}")
                    import traceback
                    debug_print(traceback.format_exc())
                    return []
        
        return []

    def get_all_remote_nodes(self, remote_host, remote_port=4403, days_filter=30):
        """
        Récupérer TOUS les nœuds (directs + relayés) d'un nœud distant
        
        ⚠️ ESP32 LIMITATION:
        ESP32 only supports ONE TCP connection at a time. This method MUST use
        the shared interface when connecting to the same host as the main bot
        connection.
        """
        
        current_time = time.time()
        cutoff_time = current_time - (days_filter * 24 * 3600)
        debug_print(f"Filtre temporel TOUS nœuds: derniers {days_filter} jours")
        
        skipped_by_date = 0
        skipped_by_no_data = 0
        
        # Check if shared interface MUST be used (ESP32 single-connection limitation)
        must_use_shared = self._must_use_shared_interface(remote_host)
        
        remote_interface = None
        close_interface = False
        
        try:
            # Determine which interface to use
            if must_use_shared or (self.interface is not None and 
                                   getattr(self.interface, 'hostname', None) == remote_host):
                debug_print(f"♻️ Réutilisation interface partagée pour {remote_host}")
                remote_interface = self.interface
                close_interface = False
            else:
                if must_use_shared:
                    error_print(f"❌ Interface non disponible mais mode TCP actif - impossible de requêter {remote_host}")
                    return []
                debug_print(f"Connexion au nœud distant {remote_host}...")
                from safe_tcp_connection import SafeTCPConnection
                remote_interface = SafeTCPConnection(remote_host, remote_port).__enter__()
                close_interface = True
                time.sleep(2)  # Laisser les données se charger (seulement pour nouvelle connexion)
            
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
            
            debug_print(f"✅ Résultats TOUS nœuds pour {remote_host} (filtre: {days_filter}j):")
            debug_print(f"   - Nœuds acceptés: {len(node_list)}")
            debug_print(f"   - Ignorés (>{days_filter}j): {skipped_by_date}")
            debug_print(f"   - Ignorés (pas de données): {skipped_by_no_data}")
            
            return node_list
            
        except Exception as e:
            error_print(f"Erreur récupération TOUS nœuds {remote_host}: {e}")
            return []
        finally:
            # Fermer la connexion seulement si on l'a créée
            if close_interface and remote_interface is not None:
                try:
                    remote_interface.__exit__(None, None, None)
                except:
                    pass

    def get_tigrog2_paginated(self, page=1, days_filter=3):
        """
        Récupérer et formater les nœuds directs avec pagination
        
        Note: Nom de fonction legacy, utilise REMOTE_NODE_NAME/HOST du config
        """
        try:
            remote_nodes = self.get_remote_nodes(REMOTE_NODE_HOST, days_filter=days_filter)
            
            if not remote_nodes:
                return f"Aucun nœud direct trouvé sur {REMOTE_NODE_NAME}"
            
            # ✅ TRI PAR SNR (du meilleur au pire)
            if COLLECT_SIGNAL_METRICS:
                # Tri par SNR décroissant (meilleur signal en premier)
                remote_nodes.sort(key=lambda x: x.get('snr', -999), reverse=True)
                # ou par RSSI : remote_nodes.sort(key=lambda x: (x.get('rssi', -999), x['last_heard']), reverse=True)
            else:
                # Sans métriques, trier par temps (plus récent en premier)
                remote_nodes.sort(key=lambda x: x['last_heard'], reverse=True)
            
            # Pagination
            nodes_per_page = 7
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
        """Formater une ligne de nœud pour l'affichage - FORMAT ULTRA-COMPACT pour mesh"""
        try:
            name = node.get('name', 'Unknown')

            # Extraire seulement le shortName (partie avant l'espace)
            if ' ' in name:
                name = name.split(' ', 1)[0]  # Prendre uniquement le shortName

            # Tronquer à 14 caractères max
            name = truncate_text(name, 14, suffix="")

            last_heard = node.get('last_heard', 0)
            elapsed_str = format_elapsed_time(last_heard) if last_heard > 0 else "?"

            # ✅ CALCUL DE DISTANCE GPS
            distance_str = ""
            if self.node_manager:
                node_id = node.get('id')
                if node_id:
                    try:
                        distance = self.node_manager.get_node_distance(node_id)
                        if distance:
                            distance_str = f" {self.node_manager.format_distance(distance)}"
                    except Exception as e:
                        debug_print(f"Erreur distance nœud {node_id:08x}: {e}")

            # Format ultra-compact pour mesh avec distance
            if COLLECT_SIGNAL_METRICS:
                rssi = node.get('rssi', 0)
                snr = node.get('snr', 0.0)

                if rssi != 0 or snr != 0:
                    # Icône basée sur SNR ou RSSI
                    if snr != 0:
                        icon = "🟢" if snr >= 10 else "🟡" if snr >= 5 else "🟠" if snr >= 0 else "🔴"
                        return f"{icon}{name} {snr:.0f}dB {elapsed_str}{distance_str}"
                    elif rssi != 0:
                        icon = "🟢" if rssi >= -80 else "🟡" if rssi >= -100 else "🟠" if rssi >= -110 else "🔴"
                        return f"{icon}{name} {rssi}dBm {elapsed_str}{distance_str}"

            # Format sans métriques - encore plus compact
            return f"• {name} {elapsed_str}{distance_str}"

        except Exception as e:
            error_print(f"Erreur _format_node_line: {e}")
            return "• Err"
