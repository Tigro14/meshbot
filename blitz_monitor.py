"""
Surveillance des éclairs en temps réel via Blitzortung.org

Ce module se connecte au serveur MQTT public de Blitzortung.org
pour recevoir les détections d'éclairs en temps réel et peut
générer des alertes automatiques sur le réseau Meshtastic.

Utilise le serveur MQTT public : blitzortung.ha.sed.pl:1883
"""

import time
import json
import threading
import math
from collections import deque
from typing import Optional, Dict, List, Tuple
from utils import info_print, error_print, debug_print

# Imports conditionnels
try:
    import paho.mqtt.client as mqtt
    import pygeohash as geohash
    MQTT_AVAILABLE = True
except ImportError as e:
    error_print(f"Blitz monitor: dépendances manquantes: {e}")
    MQTT_AVAILABLE = False


class BlitzMonitor:
    """
    Moniteur d'éclairs en temps réel via Blitzortung.org MQTT

    Se connecte au serveur MQTT public et surveille les éclairs
    dans un rayon configurable autour d'une position GPS.
    """

    # Configuration MQTT Blitzortung
    MQTT_HOST = "blitzortung.ha.sed.pl"
    MQTT_PORT = 1883
    MQTT_KEEPALIVE = 60
    MQTT_TOPIC_PREFIX = "blitzortung/1.1"

    def __init__(self, lat: float = None, lon: float = None, radius_km: int = 50,
                 check_interval: int = 900, window_minutes: int = 15,
                 interface = None):
        """
        Initialiser le moniteur d'éclairs

        Args:
            lat: Latitude du point de surveillance (optionnel si interface fourni)
            lon: Longitude du point de surveillance (optionnel si interface fourni)
            radius_km: Rayon de surveillance en km (défaut: 50km)
            check_interval: Intervalle entre vérifications en secondes (défaut: 15min)
            window_minutes: Fenêtre temporelle pour historique (défaut: 15min)
            interface: Interface Meshtastic pour récupérer position auto (optionnel)
        """
        if not MQTT_AVAILABLE:
            error_print("⚡ Blitz monitor: paho-mqtt ou pygeohash non disponible")
            self.enabled = False
            return

        # Tenter de récupérer la position depuis l'interface Meshtastic
        if lat is None or lon is None:
            if interface:
                lat, lon = self._get_position_from_interface(interface)

            if lat is None or lon is None:
                error_print("⚡ Blitz monitor: position GPS non disponible")
                info_print("   Fournir lat/lon en paramètre ou configurer GPS sur le node")
                self.enabled = False
                return

        self.lat = lat
        self.lon = lon
        self.radius_km = radius_km
        self.check_interval = check_interval
        self.window_minutes = window_minutes
        self.enabled = True

        # État interne
        self.strikes = deque(maxlen=1000)  # Éclairs récents
        self.last_check_time = 0
        self.last_strike_count = 0
        self.connected = False

        # Client MQTT
        self.mqtt_client = None
        self.mqtt_thread = None

        # Calculer geohashes pour abonnement
        self.geohashes = self._calculate_geohashes()

        info_print(f"⚡ Blitz monitor initialisé")
        info_print(f"   Position: {lat:.4f}, {lon:.4f}")
        info_print(f"   Rayon: {radius_km}km, Window: {window_minutes}min")
        info_print(f"   Geohashes: {', '.join(self.geohashes)}")

    def _get_position_from_interface(self, interface) -> Tuple[Optional[float], Optional[float]]:
        """
        Récupérer la position GPS du node local depuis l'interface Meshtastic

        Args:
            interface: Interface Meshtastic

        Returns:
            tuple: (latitude, longitude) ou (None, None) si non disponible
        """
        try:
            # Méthode 1: Via localNode
            if hasattr(interface, 'localNode') and interface.localNode:
                local_node = interface.localNode
                my_node_num = getattr(local_node, 'nodeNum', None)

                # Accéder aux nodes via l'interface
                if my_node_num and hasattr(interface, 'nodes') and my_node_num in interface.nodes:
                    node_info = interface.nodes[my_node_num]

                    if isinstance(node_info, dict) and 'position' in node_info:
                        position = node_info['position']
                        if isinstance(position, dict):
                            lat = position.get('latitude') or position.get('latitudeI')
                            lon = position.get('longitude') or position.get('longitudeI')

                            # Conversion si format integer (latitudeI/longitudeI)
                            if lat and abs(lat) > 180:
                                lat = lat / 1e7
                            if lon and abs(lon) > 180:
                                lon = lon / 1e7

                            if lat and lon:
                                debug_print(f"⚡ Position récupérée depuis localNode: {lat:.4f}, {lon:.4f}")
                                return (lat, lon)

            # Méthode 2: Chercher dans tous les nodes (fallback)
            if hasattr(interface, 'nodes'):
                for node_id, node_info in interface.nodes.items():
                    if isinstance(node_info, dict) and 'position' in node_info:
                        position = node_info['position']
                        if isinstance(position, dict):
                            lat = position.get('latitude') or position.get('latitudeI')
                            lon = position.get('longitude') or position.get('longitudeI')

                            if lat and lon:
                                # Conversion si nécessaire
                                if abs(lat) > 180:
                                    lat = lat / 1e7
                                if abs(lon) > 180:
                                    lon = lon / 1e7

                                debug_print(f"⚡ Position récupérée depuis nodes[{node_id}]: {lat:.4f}, {lon:.4f}")
                                return (lat, lon)

        except Exception as e:
            error_print(f"⚡ Erreur récupération position: {e}")

        return (None, None)

    def _calculate_geohashes(self, precision: int = 3) -> List[str]:
        """
        Calculer les geohashes nécessaires pour couvrir le rayon

        Args:
            precision: Précision du geohash (3 = ~150km carré)

        Returns:
            list: Liste des geohashes à surveiller
        """
        # Geohash du point central
        center_hash = geohash.encode(self.lat, self.lon, precision=precision)

        # Pour un rayon de 50km, geohash de précision 3 est suffisant
        # Ajouter les voisins pour couvrir les bords
        # pygeohash a get_adjacent(geohash, direction) où direction = 'top', 'bottom', 'right', 'left'
        neighbors = []
        try:
            # Ajouter les 8 voisins (4 cardinaux + 4 diagonales)
            neighbors.append(geohash.get_adjacent(center_hash, 'top'))
            neighbors.append(geohash.get_adjacent(center_hash, 'bottom'))
            neighbors.append(geohash.get_adjacent(center_hash, 'right'))
            neighbors.append(geohash.get_adjacent(center_hash, 'left'))

            # Diagonales (combiner deux directions)
            top = geohash.get_adjacent(center_hash, 'top')
            neighbors.append(geohash.get_adjacent(top, 'right'))  # NE
            neighbors.append(geohash.get_adjacent(top, 'left'))   # NW

            bottom = geohash.get_adjacent(center_hash, 'bottom')
            neighbors.append(geohash.get_adjacent(bottom, 'right'))  # SE
            neighbors.append(geohash.get_adjacent(bottom, 'left'))   # SW
        except Exception as e:
            error_print(f"⚡ Erreur calcul voisins geohash: {e}")
            # Si erreur, utiliser seulement le centre
            neighbors = []

        all_hashes = [center_hash] + neighbors
        return all_hashes

    def _haversine_distance(self, lat1: float, lon1: float,
                           lat2: float, lon2: float) -> float:
        """
        Calculer la distance en km entre deux points GPS (formule haversine)

        Args:
            lat1, lon1: Coordonnées point 1
            lat2, lon2: Coordonnées point 2

        Returns:
            float: Distance en kilomètres
        """
        R = 6371  # Rayon de la Terre en km

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)

        a = (math.sin(dlat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(dlon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    def _on_mqtt_connect(self, client, userdata, flags, rc, properties=None):
        """Callback de connexion MQTT"""
        if rc == 0:
            self.connected = True
            info_print(f"⚡ Connecté au serveur MQTT Blitzortung")

            # S'abonner aux topics geohash
            for gh in self.geohashes:
                topic = f"{self.MQTT_TOPIC_PREFIX}/{gh}"
                client.subscribe(topic)
                debug_print(f"   Abonné à topic: {topic}")
        else:
            error_print(f"⚡ Échec connexion MQTT: code {rc}")
            self.connected = False

    def _on_mqtt_disconnect(self, client, userdata, rc, properties=None):
        """Callback de déconnexion MQTT"""
        self.connected = False
        if rc != 0:
            error_print(f"⚡ Déconnexion MQTT inattendue: code {rc}")
        else:
            debug_print("⚡ Déconnexion MQTT normale")

    def _on_mqtt_message(self, client, userdata, msg):
        """
        Callback de réception de message MQTT

        Format attendu du payload JSON:
        {
            "lat": 47.123,
            "lon": 6.456,
            "time": 1234567890.123,
            "alt": 0,
            "pol": 1,
            "mds": 5000
        }
        """
        try:
            # Parser le JSON
            data = json.loads(msg.payload.decode('utf-8'))

            strike_lat = data.get('lat')
            strike_lon = data.get('lon')
            strike_time = data.get('time', time.time())

            if strike_lat is None or strike_lon is None:
                return

            # Calculer la distance
            distance = self._haversine_distance(
                self.lat, self.lon,
                strike_lat, strike_lon
            )

            # Si dans le rayon, ajouter à l'historique
            if distance <= self.radius_km:
                strike_info = {
                    'lat': strike_lat,
                    'lon': strike_lon,
                    'time': strike_time,
                    'distance': distance,
                    'polarity': data.get('pol', 0),
                    'altitude': data.get('alt', 0)
                }
                self.strikes.append(strike_info)

                debug_print(f"⚡ Éclair détecté à {distance:.1f}km")

        except json.JSONDecodeError as e:
            error_print(f"⚡ Erreur parsing JSON: {e}")
        except Exception as e:
            error_print(f"⚡ Erreur traitement message: {e}")

    def start_monitoring(self):
        """Démarrer la surveillance MQTT en arrière-plan"""
        if not self.enabled:
            return

        try:
            # Créer le client MQTT
            self.mqtt_client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2
            )

            # Configurer les callbacks
            self.mqtt_client.on_connect = self._on_mqtt_connect
            self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
            self.mqtt_client.on_message = self._on_mqtt_message

            # Se connecter au serveur
            info_print(f"⚡ Connexion à {self.MQTT_HOST}:{self.MQTT_PORT}...")
            self.mqtt_client.connect(
                self.MQTT_HOST,
                self.MQTT_PORT,
                self.MQTT_KEEPALIVE
            )

            # Démarrer la boucle MQTT dans un thread
            self.mqtt_thread = threading.Thread(
                target=self.mqtt_client.loop_forever,
                daemon=True
            )
            self.mqtt_thread.start()

            info_print("⚡ Thread MQTT démarré")

        except Exception as e:
            error_print(f"⚡ Erreur démarrage MQTT: {e}")
            self.enabled = False

    def stop_monitoring(self):
        """Arrêter la surveillance MQTT"""
        if self.mqtt_client:
            self.mqtt_client.disconnect()
            self.mqtt_client.loop_stop()
            info_print("⚡ Surveillance MQTT arrêtée")

    def get_recent_strikes(self, minutes: int = None) -> List[Dict]:
        """
        Obtenir les éclairs récents dans la fenêtre temporelle

        Args:
            minutes: Fenêtre en minutes (défaut: self.window_minutes)

        Returns:
            list: Liste des éclairs dans la fenêtre
        """
        if minutes is None:
            minutes = self.window_minutes

        cutoff_time = time.time() - (minutes * 60)

        recent = [
            strike for strike in self.strikes
            if strike['time'] >= cutoff_time
        ]

        return recent

    def check_and_report(self) -> Optional[str]:
        """
        Vérifier les éclairs récents et générer un rapport

        Returns:
            str: Rapport formaté ou None si pas d'éclairs
        """
        current_time = time.time()

        # Vérifier intervalle
        if current_time - self.last_check_time < self.check_interval:
            return None

        self.last_check_time = current_time

        # Obtenir éclairs récents
        recent = self.get_recent_strikes()
        count = len(recent)

        # Log du check
        info_print(f"⚡ Blitz check: {count} éclairs détectés ({self.window_minutes}min)")

        # Si éclairs détectés, générer rapport
        if count > 0:
            self.last_strike_count = count
            return self._format_report(recent)

        return None

    def _format_report(self, strikes: List[Dict], compact: bool = True) -> str:
        """
        Formater un rapport d'éclairs

        Args:
            strikes: Liste des éclairs
            compact: True pour format court (LoRa), False pour long (Telegram)

        Returns:
            str: Rapport formaté
        """
        count = len(strikes)

        if count == 0:
            return "⚡ Aucun éclair détecté"

        # Trouver le plus proche
        closest = min(strikes, key=lambda s: s['distance'])
        closest_dist = closest['distance']
        closest_time_ago = int(time.time() - closest['time'])

        if compact:
            # Format LoRa court
            lines = [f"⚡ {count} éclairs ({self.window_minutes}min)"]
            lines.append(f"+ proche: {closest_dist:.1f}km")
            if closest_time_ago < 60:
                lines.append(f"il y a {closest_time_ago}s")
            else:
                lines.append(f"il y a {closest_time_ago//60}min")
            return '\n'.join(lines)
        else:
            # Format Telegram détaillé
            lines = [f"⚡ ÉCLAIRS DÉTECTÉS"]
            lines.append(f"{count} éclairs dans les {self.window_minutes} dernières minutes")
            lines.append(f"Rayon de surveillance: {self.radius_km}km")
            lines.append("")
            lines.append(f"Plus proche: {closest_dist:.1f}km il y a {closest_time_ago}s")

            # Stats de distance
            avg_dist = sum(s['distance'] for s in strikes) / count
            lines.append(f"Distance moyenne: {avg_dist:.1f}km")

            return '\n'.join(lines)

    def get_status(self) -> str:
        """
        Obtenir le statut actuel du moniteur

        Returns:
            str: Statut formaté
        """
        if not self.enabled:
            return "⚡ Blitz monitor: Désactivé (dépendances manquantes)"

        recent_count = len(self.get_recent_strikes())
        conn_status = "Connecté" if self.connected else "Déconnecté"

        lines = [
            f"⚡ Blitz Monitor:",
            f"  Status MQTT: {conn_status}",
            f"  Position: {self.lat:.4f}, {self.lon:.4f}",
            f"  Rayon: {self.radius_km}km",
            f"  Éclairs récents ({self.window_minutes}min): {recent_count}",
        ]

        if self.last_strike_count > 0:
            lines.append(f"  Dernier check: {self.last_strike_count} éclairs")

        return '\n'.join(lines)
