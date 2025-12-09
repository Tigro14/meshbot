#!/usr/bin/env python3
"""
Gestionnaire des nœuds avec positions GPS et calcul de distances
VERSION AMÉLIORÉE avec stockage des coordonnées
"""

import json
import os
import time
import threading
import gc
from config import *
from utils import *
from math import radians, cos, sin, asin, sqrt

class NodeManager:
    def __init__(self, interface=None):
        self.node_names = {}
        self._last_node_save = 0
        self.rx_history = {}
        self.interface = interface
        from collections import deque
        self.packet_type_counts = {
            'POSITION_APP': deque(maxlen=24),
            'TELEMETRY_APP': deque(maxlen=24),
            'NODEINFO_APP': deque(maxlen=24),
            'TEXT_MESSAGE_APP': deque(maxlen=24)
        }
        self.last_packet_hour = None
        
        # Position du bot (à récupérer depuis config.py)
        try:
            from config import BOT_POSITION
            self.bot_position = BOT_POSITION
        except ImportError:
            self.bot_position = None
            debug_print("⚠️ BOT_POSITION non défini dans config.py")
    
    def set_interface(self, interface):
        """Définir l'interface Meshtastic"""
        self.interface = interface
    
    def haversine_distance(self, lat1, lon1, lat2, lon2):
        """
        Calculer la distance entre deux points GPS en utilisant la formule de Haversine
        Retourne la distance en kilomètres
        """
        # Convertir en radians
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        
        # Formule de Haversine
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        
        # Rayon de la Terre en km
        r = 6371
        
        return c * r
    
    def format_distance(self, distance_km):
        """
        Formater la distance de manière lisible
        """
        if distance_km < 1:
            return f"{int(distance_km * 1000)}m"
        elif distance_km < 10:
            return f"{distance_km:.1f}km"
        else:
            return f"{int(distance_km)}km"
    
    def load_node_names(self):
        """Charger la base de noms et positions depuis le fichier"""
        try:
            if os.path.exists(NODE_NAMES_FILE):
                with open(NODE_NAMES_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # Nouvelle structure: {node_id: {name, lat, lon, alt, last_update}}
                    # Compatibilité avec l'ancienne structure: {node_id: name}
                    self.node_names = {}
                    for k, v in data.items():
                        if not k.isdigit():
                            continue
                        node_id = int(k)
                        
                        if isinstance(v, str):
                            # Ancien format: juste le nom
                            self.node_names[node_id] = {
                                'name': v,
                                'shortName': None,
                                'hwModel': None,
                                'lat': None,
                                'lon': None,
                                'alt': None,
                                'last_update': None
                            }
                        elif isinstance(v, dict):
                            # Nouveau format: dict avec toutes les infos
                            self.node_names[node_id] = {
                                'name': v.get('name', f"Node-{node_id:08x}"),
                                'shortName': v.get('shortName'),
                                'hwModel': v.get('hwModel'),
                                'lat': v.get('lat'),
                                'lon': v.get('lon'),
                                'alt': v.get('alt'),
                                'last_update': v.get('last_update')
                            }
                        
                debug_print(f"📚 {len(self.node_names)} noms de nœuds chargés")
            else:
                debug_print("📂 Nouvelle base de noms créée")
                self.node_names = {}
        except Exception as e:
            error_print(f"Erreur chargement noms: {e}")
            self.node_names = {}
    
    def save_node_names(self, force=False):
        """Sauvegarder la base de noms et positions (avec throttling)"""
        try:
            current_time = time.time()
            # Sauvegarder seulement toutes les 60s sauf si forcé
            if not force and (current_time - self._last_node_save) < 60:
                return
            
            # Convertir les clés int en string pour JSON
            data = {str(k): v for k, v in self.node_names.items()}
            with open(NODE_NAMES_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._last_node_save = current_time
            debug_print(f"💾 Base sauvegardée ({len(self.node_names)} nœuds)")
        except Exception as e:
            error_print(f"Erreur sauvegarde noms: {e}")
    
    def get_node_name(self, node_id, interface=None):
        """Récupérer le nom d'un nœud par son ID"""
        # Return fallback name when node_id is None (e.g., when node lookup fails)
        if node_id is None:
            return "Unknown"
        
        if node_id in self.node_names:
            return self.node_names[node_id]['name']
        
        # Tenter de récupérer depuis l'interface en temps réel
        try:
            if interface and hasattr(interface, 'nodes'):
                nodes = getattr(interface, 'nodes', {})
                if node_id in nodes:
                    node_info = nodes[node_id]
                    if isinstance(node_info, dict) and 'user' in node_info:
                        user_info = node_info['user']
                        if isinstance(user_info, dict):
                            name = user_info.get('longName') or user_info.get('shortName')
                            if name and len(name.strip()) > 0:
                                name = clean_node_name(name)
                                # Créer l'entrée si elle n'existe pas
                                if node_id not in self.node_names:
                                    self.node_names[node_id] = {
                                        'name': name,
                                        'shortName': None,
                                        'hwModel': None,
                                        'lat': None,
                                        'lon': None,
                                        'alt': None,
                                        'last_update': None
                                    }
                                else:
                                    self.node_names[node_id]['name'] = name
                                # Sauvegarde différée pour nouveaux nœuds
                                threading.Timer(5.0, lambda: self.save_node_names()).start()
                                return name
        except Exception as e:
            debug_print(f"Erreur récupération nom {node_id}: {e}")

        # Générer un nom par défaut selon le type de node_id
        if isinstance(node_id, str):
            # Si c'est déjà une chaîne (ex: "!12345678"), l'utiliser tel quel
            return node_id
        else:
            # Si c'est un int, formater en hex
            return f"Node-{node_id:08x}"
    
    def get_node_data(self, node_id):
        """
        Récupérer les données complètes d'un nœud (position, nom, etc.)
        
        Args:
            node_id: ID du nœud (int)
            
        Returns:
            dict avec 'latitude', 'longitude', 'altitude', 'name', 'last_update'
            ou None si le nœud n'existe pas ou n'a pas de position
        """
        if node_id not in self.node_names:
            return None
        
        node_data = self.node_names[node_id]
        
        # Retourner None si pas de position GPS
        if node_data.get('lat') is None or node_data.get('lon') is None:
            return None
        
        # Mapper les clés internes (lat/lon) vers le format attendu (latitude/longitude)
        return {
            'latitude': node_data['lat'],
            'longitude': node_data['lon'],
            'altitude': node_data.get('alt'),
            'name': node_data.get('name'),
            'last_update': node_data.get('last_update')
        }
    
    def get_reference_position(self):
        """
        Obtenir la position de référence (position du bot)
        
        Returns:
            tuple (latitude, longitude) ou None si pas de position configurée
        """
        if self.bot_position is None:
            return None
        
        # BOT_POSITION est déjà un tuple (lat, lon)
        return self.bot_position
    
    def get_node_distance(self, node_id, reference_lat=None, reference_lon=None):
        """
        Calculer la distance jusqu'à un nœud
        Si reference_lat/lon non fournis, utilise la position du bot
        Retourne None si pas de position disponible
        """
        if node_id not in self.node_names:
            return None
        
        node_data = self.node_names[node_id]
        node_lat = node_data.get('lat')
        node_lon = node_data.get('lon')
        
        if node_lat is None or node_lon is None:
            return None
        
        # Utiliser la référence fournie ou la position du bot
        if reference_lat is None or reference_lon is None:
            if self.bot_position is None:
                return None
            reference_lat, reference_lon = self.bot_position
        
        return self.haversine_distance(reference_lat, reference_lon, node_lat, node_lon)
    
    def update_node_position(self, node_id, lat, lon, alt=None):
        """
        Mettre à jour la position d'un nœud
        """
        if node_id not in self.node_names:
            # Créer l'entrée si elle n'existe pas
            default_name = node_id if isinstance(node_id, str) else f"Node-{node_id:08x}"
            self.node_names[node_id] = {
                'name': default_name,
                'shortName': None,
                'hwModel': None,
                'lat': lat,
                'lon': lon,
                'alt': alt,
                'last_update': time.time()
            }
        else:
            # Mettre à jour la position
            self.node_names[node_id]['lat'] = lat
            self.node_names[node_id]['lon'] = lon
            self.node_names[node_id]['alt'] = alt
            self.node_names[node_id]['last_update'] = time.time()
        
        debug_print(f"📍 Position mise à jour pour {node_id:08x}: {lat:.5f}, {lon:.5f}")
    
    def update_node_database(self, interface):
        """Mettre à jour la base de données des nœuds"""
        if not interface:
            return
        
        try:
            debug_print("🔄 Mise à jour base de nœuds...")
            updated_count = 0
            
            # Récupérer tous les nœuds connus
            nodes = getattr(interface, 'nodes', {})
            
            for node_id, node_info in nodes.items():
                try:
                    # Convertir node_id en entier si c'est une string
                    if isinstance(node_id, str):
                        if node_id.startswith('!'):
                            clean_id = node_id[1:]
                            node_id_int = int(clean_id, 16)
                        else:
                            try:
                                node_id_int = int(node_id, 16)
                            except ValueError:
                                node_id_int = int(node_id)
                    else:
                        node_id_int = int(node_id)
                    
                    # Mise à jour du nom
                    if isinstance(node_info, dict) and 'user' in node_info:
                        user_info = node_info['user']
                        if isinstance(user_info, dict):
                            long_name = user_info.get('longName', '').strip()
                            short_name_raw = user_info.get('shortName', '').strip()
                            hw_model = user_info.get('hwModel', '').strip()
                            
                            # Sanitize names to prevent SQL injection and XSS
                            name = clean_node_name(long_name or short_name_raw)
                            short_name = clean_node_name(short_name_raw) if short_name_raw else None
                            
                            if name and len(name) > 0:
                                # Initialiser l'entrée si nécessaire
                                if node_id_int not in self.node_names:
                                    self.node_names[node_id_int] = {
                                        'name': name,
                                        'shortName': short_name,
                                        'hwModel': hw_model if hw_model else None,
                                        'lat': None,
                                        'lon': None,
                                        'alt': None,
                                        'last_update': None
                                    }
                                    updated_count += 1
                                elif self.node_names[node_id_int]['name'] != name:
                                    old_name = self.node_names[node_id_int]['name']
                                    self.node_names[node_id_int]['name'] = name
                                    # Also update shortName and hwModel
                                    self.node_names[node_id_int]['shortName'] = short_name
                                    self.node_names[node_id_int]['hwModel'] = hw_model or None
                                    debug_print(f"🔄 {node_id_int:08x}: '{old_name}' -> '{name}'")
                                    updated_count += 1
                    
                    # Mise à jour de la position si disponible
                    if isinstance(node_info, dict) and 'position' in node_info:
                        position = node_info['position']
                        if isinstance(position, dict):
                            lat = position.get('latitude')
                            lon = position.get('longitude')
                            alt = position.get('altitude')
                            
                            if lat is not None and lon is not None:
                                # Vérifier si la position a changé
                                if node_id_int not in self.node_names:
                                    self.node_names[node_id_int] = {
                                        'name': f"Node-{node_id_int:08x}",
                                        'shortName': None,
                                        'hwModel': None,
                                        'lat': lat,
                                        'lon': lon,
                                        'alt': alt,
                                        'last_update': time.time()
                                    }
                                    updated_count += 1
                                else:
                                    old_lat = self.node_names[node_id_int].get('lat')
                                    old_lon = self.node_names[node_id_int].get('lon')
                                    
                                    # Mise à jour si nouvelle position ou position différente
                                    if old_lat != lat or old_lon != lon:
                                        self.node_names[node_id_int]['lat'] = lat
                                        self.node_names[node_id_int]['lon'] = lon
                                        self.node_names[node_id_int]['alt'] = alt
                                        self.node_names[node_id_int]['last_update'] = time.time()
                                        debug_print(f"📍 Position mise à jour: {node_id_int:08x}")
                                        updated_count += 1
                
                except Exception as e:
                    debug_print(f"Erreur traitement nœud {node_id}: {e}")
                    continue
            
            if updated_count > 0:
                self.save_node_names()
                debug_print(f"✅ {updated_count} nœuds mis à jour")
            else:
                debug_print(f"ℹ️ Base à jour ({len(self.node_names)} nœuds)")
                
        except Exception as e:
            error_print(f"Erreur mise à jour base: {e}")
    
    def format_rx_report(self):
        """Générer un rapport des nœuds reçus récemment avec distances"""
        try:
            # Filtrer les nœuds récents (30 dernières minutes)
            recent_cutoff = time.time() - 1800
            recent_nodes = [
                (node_id, data) for node_id, data in self.rx_history.items()
                if data['last_seen'] > recent_cutoff
            ]
            
            if not recent_nodes:
                return "Aucun nœud récent (30min)"
            
            # Trier par qualité SNR (descendant)
            recent_nodes.sort(key=lambda x: x[1]['snr'], reverse=True)
            
            # Formater le rapport
            lines = []
            lines.append(f"📡 Nœuds DIRECTS ({len(recent_nodes)}):")
            
            for node_id, data in recent_nodes[:10]:
                name = truncate_text(data['name'], 12)
                snr = data['snr']
                count = data['count']
                
                # Indicateur de qualité basé sur SNR
                signal_icon = get_signal_quality_icon(snr)
                
                # Temps depuis dernière réception
                time_str = format_elapsed_time(data['last_seen'])
                
                # Distance si disponible
                distance = self.get_node_distance(node_id)
                distance_str = f" {self.format_distance(distance)}" if distance else ""
                
                line = f"{signal_icon} {name}: SNR:{snr:.1f}dB ({count}x) {time_str}{distance_str}"
                lines.append(line)
            
            if len(recent_nodes) > 10:
                lines.append(f"... et {len(recent_nodes) - 10} autres")
            
            result = "\n".join(lines)
            
            # Limiter la taille totale du message
            if len(result) > 500:
                lines_short = lines[:6]
                if len(recent_nodes) > 5:
                    lines_short.append(f"... et {len(recent_nodes) - 5} autres")
                result = "\n".join(lines_short)
            
            return result
            
        except Exception as e:
            error_print(f"Erreur format RX: {e}")
            return f"Erreur génération rapport RX: {truncate_text(str(e), 30)}"
    
    def update_node_from_packet(self, packet):
        """Mettre à jour la base de nœuds depuis un packet reçu (NODEINFO_APP)"""
        try:
            if 'decoded' in packet and packet['decoded'].get('portnum') == 'NODEINFO_APP':
                node_id = packet.get('from')
                decoded = packet['decoded']
                
                if 'user' in decoded and node_id:
                    user_info = decoded['user']
                    long_name = user_info.get('longName', '').strip()
                    short_name_raw = user_info.get('shortName', '').strip()
                    hw_model = user_info.get('hwModel', '').strip()
                    
                    # Sanitize names to prevent SQL injection and XSS
                    name = clean_node_name(long_name or short_name_raw)
                    short_name = clean_node_name(short_name_raw) if short_name_raw else None
                    
                    if name and len(name) > 0:
                        # Initialiser l'entrée si elle n'existe pas
                        if node_id not in self.node_names:
                            self.node_names[node_id] = {
                                'name': name,
                                'shortName': short_name,
                                'hwModel': hw_model if hw_model else None,
                                'lat': None,
                                'lon': None,
                                'alt': None,
                                'last_update': None
                            }
                            debug_print(f"📱 Nouveau: {name} ({node_id:08x})")
                        else:
                            old_name = self.node_names[node_id]['name']
                            if old_name != name:
                                self.node_names[node_id]['name'] = name
                                debug_print(f"📱 Renommé: {old_name} → {name} ({node_id:08x})")
                            # Always update shortName and hwModel even if name didn't change
                            self.node_names[node_id]['shortName'] = short_name
                            self.node_names[node_id]['hwModel'] = hw_model or None
                        
                        # Sauvegarde différée
                        threading.Timer(10.0, lambda: self.save_node_names()).start()
        except Exception as e:
            debug_print(f"Erreur traitement NodeInfo: {e}")

    def update_rx_history(self, packet):
        """Mettre à jour l'historique des signaux reçus (DIRECT uniquement - 0 hop) - SNR UNIQUEMENT"""
        try:
            from_id = packet.get('from')
            if not from_id:
                return
            
            # FILTRER UNIQUEMENT LES MESSAGES DIRECTS (0 hop)
            hop_limit = packet.get('hopLimit', 0)
            hop_start = packet.get('hopStart', 5)
            hops_taken = hop_start - hop_limit
            
            # Extraire SNR (essayer plusieurs clés)
            snr = packet.get('snr', packet.get('rxSnr', 0.0))
            
            # Obtenir le nom
            name = self.get_node_name(from_id, self.interface if hasattr(self, 'interface') else None)
        
            # Mettre à jour l'historique RX
            if from_id not in self.rx_history:
                self.rx_history[from_id] = {
                    'name': name,
                    'snr': snr,
                    'last_seen': time.time(),
                    'count': 1
                }
            else:
                # Moyenne mobile du SNR
                old_snr = self.rx_history[from_id]['snr']
                count = self.rx_history[from_id]['count']
                new_snr = (old_snr * count + snr) / (count + 1)
                
                self.rx_history[from_id]['snr'] = new_snr
                self.rx_history[from_id]['last_seen'] = time.time()
                self.rx_history[from_id]['count'] += 1
                self.rx_history[from_id]['name'] = name
            
            # Limiter la taille de l'historique
            if len(self.rx_history) > MAX_RX_HISTORY:
                # Supprimer les plus anciens
                sorted_by_time = sorted(self.rx_history.items(), key=lambda x: x[1]['last_seen'])
                for old_node_id, _ in sorted_by_time[:len(self.rx_history) - MAX_RX_HISTORY]:
                    del self.rx_history[old_node_id]
                    
        except Exception as e:
            debug_print(f"Erreur MAJ RX history: {e}")
    
    def track_packet_type(self, packet):
        """Suivre les types de paquets par heure pour l'histogramme"""
        try:
            if 'decoded' not in packet:
                return
            
            packet_type = packet['decoded'].get('portnum', 'UNKNOWN_APP')
            
            # Ne suivre que certains types
            if packet_type not in self.packet_type_counts:
                return
            
            # Obtenir l'heure actuelle
            current_hour = time.strftime('%Y-%m-%d %H:00')
            
            # Si c'est une nouvelle heure, ajouter un nouveau slot
            if self.last_packet_hour != current_hour:
                self.last_packet_hour = current_hour
                for ptype in self.packet_type_counts:
                    self.packet_type_counts[ptype].append(0)
            
            # Incrémenter le compteur pour cette heure
            if len(self.packet_type_counts[packet_type]) > 0:
                self.packet_type_counts[packet_type][-1] += 1
                
        except Exception as e:
            debug_print(f"Erreur track_packet_type: {e}")
    
    def list_known_nodes(self):
        """Lister tous les nœuds connus avec leurs positions"""
        if not DEBUG_MODE:
            return
            
        print(f"\n📋 Nœuds connus ({len(self.node_names)}):")
        print("-" * 80)
        for node_id, node_data in sorted(self.node_names.items()):
            name = node_data['name']
            lat = node_data.get('lat')
            lon = node_data.get('lon')
            
            position_str = ""
            if lat and lon:
                position_str = f" @ {lat:.5f}, {lon:.5f}"
                distance = self.get_node_distance(node_id)
                if distance:
                    position_str += f" ({self.format_distance(distance)})"
            
            print(f"  !{node_id:08x} = {name}{position_str}")
        print()


    def format_rx_report(self):
        """Formater le rapport des nœuds reçus - SNR UNIQUEMENT"""
        try:
            if not self.rx_history:
                return "Aucun nœud reçu récemment"
            
            current_time = time.time()
            recent_nodes = []
            
            # Filtrer les nœuds vus dans les dernières 30 minutes
            for node_id, data in self.rx_history.items():
                if current_time - data['last_seen'] <= 1800:  # 30 minutes
                    recent_nodes.append((node_id, data))
            
            if not recent_nodes:
                return "Aucun nœud récent (30min)"
            
            # Trier par qualité SNR (descendant)
            recent_nodes.sort(key=lambda x: x[1]['snr'], reverse=True)
            
            # Formater le rapport
            lines = []
            lines.append(f"📡 Nœuds DIRECTS ({len(recent_nodes)}):")
            
            for node_id, data in recent_nodes[:10]:  # Limiter à 10 pour la taille du message
                name = truncate_text(data['name'], 12)
                snr = data['snr']
                count = data['count']
                
                # Indicateur de qualité basé sur SNR UNIQUEMENT
                signal_icon = get_signal_quality_icon(snr)
                
                # Temps depuis dernière réception
                time_str = format_elapsed_time(data['last_seen'])
                
                line = f"{signal_icon} {name}: SNR:{snr:.1f}dB ({count}x) {time_str}"
                lines.append(line)
            
            if len(recent_nodes) > 10:
                lines.append(f"... et {len(recent_nodes) - 10} autres")
            
            result = "\n".join(lines)
            
            # Limiter la taille totale du message
            if len(result) > 500:
                # Prendre seulement les 5 premiers
                lines_short = lines[:6]  # Header + 5 nœuds
                if len(recent_nodes) > 5:
                    lines_short.append(f"... et {len(recent_nodes) - 5} autres")
                result = "\n".join(lines_short)
            
            return result
            
        except Exception as e:
            error_print(f"Erreur format RX: {e}")
            return f"Erreur génération rapport RX: {truncate_text(str(e), 30)}"
    
    def list_known_nodes(self):
        """Lister tous les nœuds connus"""
        if not DEBUG_MODE:
            return
            
        print(f"\n📋 Nœuds connus ({len(self.node_names)}):")
        print("-" * 60)
        for node_id, name in sorted(self.node_names.items()):
            print(f"  !{node_id:08x} -> {name}")
        print("-" * 60)
    
    def cleanup_old_rx_history(self):
        """Nettoyer l'historique RX ancien"""
        try:
            current_time = time.time()
            cutoff_time = current_time - 3600  # 1 heure
            
            to_remove = []
            for node_id, data in self.rx_history.items():
                if data['last_seen'] < cutoff_time:
                    to_remove.append(node_id)
            
            for node_id in to_remove:
                del self.rx_history[node_id]
            
            if to_remove:
                debug_print(f"🧹 {len(to_remove)} entrées RX anciennes supprimées")
                
        except Exception as e:
            debug_print(f"Erreur nettoyage RX: {e}")

    def get_packet_histogram_single(self, packet_type='ALL', hours=24):
        """
        Générer un histogramme pour un type de paquet spécifique

        Args:
            packet_type: 'POS', 'TELE', 'NODE', 'TEXT' ou 'ALL' pour vue d'ensemble
            hours: Nombre d'heures à analyser (défaut 24)

        Returns:
            str: Histogramme formaté pour un seul type ou vue d'ensemble
        """
        try:
            if not hasattr(self, 'packet_type_counts'):
                return "❌ Historique non disponible"

            current_time = time.time()
            cutoff_time = current_time - (hours * 3600)

            # Symboles pour le graphique ASCII
            symbols = "▁▂▃▄▅▆▇█"

            # Types de paquets avec leurs labels
            packet_types = {
                'POS': 'POSITION_APP',
                'TELE': 'TELEMETRY_APP',
                'NODE': 'NODEINFO_APP',
                'TEXT': 'TEXT_MESSAGE_APP'
            }

            # Si ALL, retourner vue d'ensemble compacte
            if packet_type.upper() == 'ALL':
                return self._format_histogram_overview(packet_types, cutoff_time, hours)

            # Vérifier que le type demandé existe
            packet_type_upper = packet_type.upper()
            if packet_type_upper not in packet_types:
                return f"❌ Type inconnu: {packet_type}\nTypes: pos, tele, node, text"

            # Obtenir les données pour ce type
            portnum = packet_types[packet_type_upper]

            if portnum not in self.packet_type_counts:
                return f"📦 {packet_type_upper}: Aucune donnée"

            # Filtrer les données dans la fenêtre temporelle
            data_points = [
                count for timestamp, count in self.packet_type_counts[portnum]
                if timestamp >= cutoff_time
            ]

            if not data_points:
                return f"📦 {packet_type_upper}: Aucune donnée ({hours}h)"

            # Générer la sparkline
            sparkline = self._generate_sparkline(data_points, symbols, 24)

            # Statistiques
            total = sum(data_points)
            min_val = min(data_points)
            max_val = max(data_points)
            current = data_points[-1] if data_points else 0

            # Tendance (comparer les 3 derniers points)
            if len(data_points) >= 3:
                recent = data_points[-3:]
                if recent[-1] > recent[-2]:
                    trend = "↗️"
                elif recent[-1] < recent[-2]:
                    trend = "↘️"
                else:
                    trend = "→"
            else:
                trend = "→"

            # Formater la réponse
            lines = [
                f"📦 {packet_type_upper} ({hours}h):",
                sparkline,
                f"Min:{min_val} | Max:{max_val} | Now:{current} {trend} | Tot:{total}"
            ]

            return "\n".join(lines)

        except Exception as e:
            error_print(f"Erreur histogram single: {e}")
            return f"❌ Erreur: {str(e)[:30]}"

    def _format_histogram_overview(self, packet_types, cutoff_time, hours):
        """
        Formater une vue d'ensemble compacte de tous les types
        """
        try:
            lines = [f"📦 Paquets ({hours}h):"]
            total_all = 0

            for short_name, portnum in packet_types.items():
                if portnum not in self.packet_type_counts:
                    continue

                # Filtrer les données
                data_points = [
                    count for timestamp, count in self.packet_type_counts[portnum]
                    if timestamp >= cutoff_time
                ]

                if data_points:
                    total = sum(data_points)
                    total_all += total
                    lines.append(f"{short_name}: {total}")

            lines.append(f"📊 Total: {total_all} paquets")
            lines.append("")
            lines.append("Détails: /histo <type>")
            lines.append("Types: pos, tele, node, text")

            return "\n".join(lines)

        except Exception as e:
            return f"❌ Erreur: {str(e)[:30]}"

    def _generate_sparkline(self, values, symbols, target_length=24):
        """
        Générer une sparkline ASCII

        Args:
            values: Liste des valeurs
            symbols: String des symboles (8 niveaux)
            target_length: Longueur cible du graphique

        Returns:
            str: Sparkline ASCII
        """
        if not values:
            return '─' * target_length

        # Sous-échantillonner si nécessaire
        if len(values) > target_length:
            step = len(values) / target_length
            sampled_values = [
                values[int(i * step)]
                for i in range(target_length)
            ]
        elif len(values) < target_length:
            # Répéter la dernière valeur
            sampled_values = values + [values[-1]] * (target_length - len(values))
        else:
            sampled_values = values

        # Normaliser les valeurs
        min_val = min(sampled_values)
        max_val = max(sampled_values)

        if max_val == min_val:
            # Valeur constante
            return symbols[4] * target_length

        sparkline = ""
        for value in sampled_values:
            # Normaliser entre 0 et 1
            normalized = (value - min_val) / (max_val - min_val)
            # Mapper sur les symboles (0-7)
            symbol_index = int(normalized * (len(symbols) - 1))
            symbol_index = max(0, min(len(symbols) - 1, symbol_index))
            sparkline += symbols[symbol_index]

        return sparkline

    def track_packet_type(self, packet):
        """
        Enregistrer le type de paquet pour les statistiques /histo
        Compte les paquets par heure
        """
        try:
            if 'decoded' not in packet:
                return

            portnum = packet['decoded'].get('portnum', '')

            # Seulement les types qu'on veut traquer
            if portnum not in self.packet_type_counts:
                return

            current_time = time.time()
            current_hour = int(current_time // 3600)

            # Initialiser le compteur horaire si nécessaire
            if self.last_packet_hour != current_hour:
                self.last_packet_hour = current_hour

                # Ajouter un nouveau point pour la nouvelle heure
                for ptype in self.packet_type_counts:
                    self.packet_type_counts[ptype].append((current_time, 0))

            # Incrémenter le compteur pour ce type
            if self.packet_type_counts[portnum]:
                last_time, last_count = self.packet_type_counts[portnum][-1]
                self.packet_type_counts[portnum][-1] = (last_time, last_count + 1)
            else:
                self.packet_type_counts[portnum].append((current_time, 1))

            #debug_print(f"📊 Packet tracké: {portnum}")

        except Exception as e:
            debug_print(f"Erreur track_packet_type: {e}")
