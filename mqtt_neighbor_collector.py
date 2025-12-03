"""
Collecteur d'informations de voisinage via MQTT Meshtastic

Ce module se connecte à un serveur MQTT Meshtastic pour recevoir
les paquets NEIGHBORINFO_APP de tous les nœuds du réseau, permettant
de construire une topologie complète au-delà de la portée radio directe.

Supporte le format Protobuf ServiceEnvelope (msh/<region>/<channel>/2/e/<gateway>)

Configuration required in config.py:
- MQTT_NEIGHBOR_SERVER: MQTT server address
- MQTT_NEIGHBOR_USER: MQTT username
- MQTT_NEIGHBOR_PASSWORD: MQTT password
"""

import time
import threading
from collections import deque
from typing import Optional, Dict, List, Any
from utils import info_print, error_print, debug_print

# Imports conditionnels
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError as e:
    error_print(f"MQTT Neighbor Collector: paho-mqtt manquant: {e}")
    MQTT_AVAILABLE = False

# Import Meshtastic protobuf
try:
    from meshtastic.protobuf import mesh_pb2, portnums_pb2
    PROTOBUF_AVAILABLE = True
except ImportError as e:
    error_print(f"MQTT Neighbor Collector: meshtastic protobuf manquant: {e}")
    PROTOBUF_AVAILABLE = False


class MQTTNeighborCollector:
    """
    Collecteur de données de voisinage via MQTT Meshtastic
    
    Se connecte à un serveur MQTT Meshtastic et collecte les paquets
    NEIGHBORINFO_APP de tous les nœuds pour enrichir la base de données
    de topologie réseau.
    """
    
    def __init__(self, 
                 mqtt_server: str,
                 mqtt_port: int = 1883,
                 mqtt_user: Optional[str] = None,
                 mqtt_password: Optional[str] = None,
                 mqtt_topic_root: str = "msh",
                 persistence = None,
                 node_manager = None):
        """
        Initialiser le collecteur MQTT
        
        Args:
            mqtt_server: Adresse du serveur MQTT
            mqtt_port: Port MQTT (défaut: 1883)
            mqtt_user: Utilisateur MQTT (optionnel)
            mqtt_password: Mot de passe MQTT (optionnel)
            mqtt_topic_root: Racine des topics MQTT (défaut: "msh")
            persistence: Instance de TrafficPersistence pour sauvegarder les données
            node_manager: Instance de NodeManager pour calculer les distances (optionnel)
        """
        # Initialiser tous les attributs d'abord (pour éviter AttributeError si désactivé)
        self.mqtt_server = mqtt_server
        self.mqtt_port = mqtt_port
        self.mqtt_user = mqtt_user
        self.mqtt_password = mqtt_password
        self.mqtt_topic_root = mqtt_topic_root
        self.persistence = persistence
        self.node_manager = node_manager
        self.enabled = False
        
        # État interne
        self.connected = False
        self.neighbor_updates = deque(maxlen=100)
        self.stats = {
            'messages_received': 0,
            'neighbor_packets': 0,
            'nodes_discovered': set(),
            'last_update': None
        }
        
        # Client MQTT
        self.mqtt_client = None
        self.mqtt_thread = None
        
        # Vérifications de pré-requis
        if not MQTT_AVAILABLE:
            error_print("👥 MQTT Neighbor Collector: paho-mqtt non disponible")
            return
        
        if not PROTOBUF_AVAILABLE:
            error_print("👥 MQTT Neighbor Collector: meshtastic protobuf non disponible")
            return
            
        if not persistence:
            error_print("👥 MQTT Neighbor Collector: persistence non fournie")
            return
        
        # Tout est OK, activer le collecteur
        self.enabled = True
        
        info_print(f"👥 MQTT Neighbor Collector initialisé")
        info_print(f"   Serveur: {mqtt_server}:{mqtt_port}")
        info_print(f"   Topic root: {mqtt_topic_root}")
    
    def _on_mqtt_connect(self, client, userdata, flags, rc, properties=None):
        """Callback de connexion MQTT"""
        if rc == 0:
            self.connected = True
            info_print(f"👥 Connecté au serveur MQTT Meshtastic")
            
            # S'abonner au topic ServiceEnvelope (protobuf)
            # Format: msh/<region>/<channel>/2/e/<gateway>
            # Wildcard + pour capturer tous les régions/channels/gateways
            topic_pattern = f"{self.mqtt_topic_root}/+/+/2/e/+"
            client.subscribe(topic_pattern)
            info_print(f"   Abonné à: {topic_pattern} (ServiceEnvelope protobuf)")
            
        else:
            error_print(f"👥 Échec connexion MQTT: code {rc}")
            self.connected = False
    
    def _on_mqtt_disconnect(self, client, userdata, rc, properties=None):
        """Callback de déconnexion MQTT"""
        self.connected = False
        if rc != 0:
            error_print(f"👥 Déconnexion MQTT inattendue: code {rc}")
        else:
            debug_print("👥 Déconnexion MQTT normale")
    
    def _on_mqtt_message(self, client, userdata, msg):
        """
        Callback de réception de message MQTT
        
        Format attendu (Protobuf ServiceEnvelope):
        ServiceEnvelope contient:
        - packet: MeshPacket (from, to, decoded/encrypted)
        - channel_id: string
        - gateway_id: string
        
        MeshPacket.decoded contient:
        - portnum: PortNum enum (NEIGHBORINFO_APP = 71)
        - payload: bytes (NeighborInfo protobuf)
        
        NeighborInfo contient:
        - node_id: uint32
        - neighbors: repeated Neighbor
          - node_id: uint32
          - snr: float
          - last_rx_time: uint32
          - node_broadcast_interval_secs: uint32
        """
        try:
            self.stats['messages_received'] += 1
            
            # Parser le ServiceEnvelope protobuf
            try:
                envelope = mesh_pb2.ServiceEnvelope()
                envelope.ParseFromString(msg.payload)
            except Exception as e:
                debug_print(f"👥 Erreur parsing ServiceEnvelope: {e}")
                return
            
            # Vérifier qu'il y a un packet
            if not envelope.HasField('packet'):
                return
            
            packet = envelope.packet
            
            # Vérifier qu'il y a des données décodées (pas chiffrées)
            if not packet.HasField('decoded'):
                # Paquet chiffré, on ne peut pas le traiter
                return
            
            decoded = packet.decoded
            
            # Vérifier que c'est un paquet NEIGHBORINFO_APP
            if decoded.portnum != portnums_pb2.PortNum.NEIGHBORINFO_APP:
                return
            
            # Parser le payload NeighborInfo
            try:
                neighbor_info = mesh_pb2.NeighborInfo()
                neighbor_info.ParseFromString(decoded.payload)
            except Exception as e:
                debug_print(f"👥 Erreur parsing NeighborInfo: {e}")
                return
            
            # Extraire l'ID du nœud qui rapporte ses voisins
            # Utiliser node_id de NeighborInfo, ou packet.from en fallback
            node_id = neighbor_info.node_id if neighbor_info.node_id else packet.from_
            
            if not node_id:
                return
            
            # Extraire la liste des voisins
            neighbors_list = neighbor_info.neighbors
            
            if not neighbors_list:
                return
            
            # Formater les données de voisins pour la persistence
            formatted_neighbors = []
            for neighbor in neighbors_list:
                neighbor_data = {
                    'node_id': neighbor.node_id,
                    'snr': neighbor.snr,
                    'last_rx_time': neighbor.last_rx_time,
                    'node_broadcast_interval': neighbor.node_broadcast_interval_secs
                }
                formatted_neighbors.append(neighbor_data)
            
            # Sauvegarder dans la base de données
            if formatted_neighbors:
                # Normaliser l'ID du nœud (int vers string "!xxxxxxxx")
                node_id_str = f"!{node_id:08x}"
                
                self.persistence.save_neighbor_info(node_id_str, formatted_neighbors)
                
                # Mettre à jour les statistiques
                self.stats['neighbor_packets'] += 1
                self.stats['nodes_discovered'].add(node_id_str)
                self.stats['last_update'] = time.time()
                
                # Ajouter à l'historique
                update_info = {
                    'timestamp': time.time(),
                    'node_id': node_id_str,
                    'neighbor_count': len(formatted_neighbors),
                    'topic': msg.topic
                }
                self.neighbor_updates.append(update_info)
                
                # Log DEBUG avec filtre de distance (<100km)
                # Calculer la distance du nœud si node_manager disponible
                should_log = True
                distance_km = None
                
                if self.node_manager:
                    try:
                        # Obtenir la position du nœud
                        node_data = self.node_manager.get_node_data(node_id)
                        if node_data and 'latitude' in node_data and 'longitude' in node_data:
                            node_lat = node_data['latitude']
                            node_lon = node_data['longitude']
                            
                            # Obtenir la position de référence (bot)
                            ref_pos = self.node_manager.get_reference_position()
                            if ref_pos and ref_pos[0] != 0 and ref_pos[1] != 0:
                                ref_lat, ref_lon = ref_pos
                                distance_km = self.node_manager.haversine_distance(
                                    ref_lat, ref_lon, node_lat, node_lon
                                )
                                
                                # Filtrer: seulement afficher si <100km
                                if distance_km >= 100:
                                    should_log = False
                    except Exception as e:
                        # En cas d'erreur de calcul, on affiche quand même
                        debug_print(f"👥 Erreur calcul distance pour {node_id_str}: {e}")
                
                # Afficher le log de debug si pas filtré
                if should_log:
                    # Obtenir le nom du nœud
                    node_name = node_id_str
                    if self.node_manager:
                        try:
                            node_name = self.node_manager.get_node_name(node_id)
                        except:
                            pass
                    
                    # Format du log similaire aux paquets mesh
                    distance_str = ""
                    if distance_km is not None:
                        distance_str = f" [{distance_km:.1f}km]"
                    
                    debug_print(f"[MQTT] 👥 NEIGHBORINFO de {node_name}{distance_str}: {len(formatted_neighbors)} voisins")
                
                # Log original plus concis (toujours affiché si DEBUG_MODE=False)
                debug_print(f"👥 MQTT: {len(formatted_neighbors)} voisins pour {node_id_str}")
        
        except Exception as e:
            error_print(f"👥 Erreur traitement message MQTT: {e}")
            import traceback
            debug_print(traceback.format_exc())
    
    def start_monitoring(self):
        """Démarrer la collecte MQTT en arrière-plan avec retry logic"""
        if not self.enabled:
            return
        
        max_retries = 3
        retry_delay = 5  # secondes
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    info_print(f"👥 Tentative de connexion MQTT {attempt + 1}/{max_retries}...")
                
                # Créer le client MQTT
                self.mqtt_client = mqtt.Client(
                    callback_api_version=mqtt.CallbackAPIVersion.VERSION2
                )
                
                # Configurer l'authentification si fournie
                if self.mqtt_user and self.mqtt_password:
                    self.mqtt_client.username_pw_set(self.mqtt_user, self.mqtt_password)
                    debug_print(f"👥 Authentification MQTT configurée (user: {self.mqtt_user})")
                
                # Configurer les callbacks
                self.mqtt_client.on_connect = self._on_mqtt_connect
                self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
                self.mqtt_client.on_message = self._on_mqtt_message
                
                # Configurer automatic reconnection
                self.mqtt_client.reconnect_delay_set(min_delay=1, max_delay=120)
                
                # Se connecter au serveur avec timeout
                info_print(f"👥 Connexion à {self.mqtt_server}:{self.mqtt_port}...")
                self.mqtt_client.connect(
                    self.mqtt_server,
                    self.mqtt_port,
                    keepalive=60
                )
                
                # Démarrer la boucle MQTT dans un thread avec auto-reconnect
                self.mqtt_thread = threading.Thread(
                    target=self._mqtt_loop_with_reconnect,
                    daemon=True,
                    name="MeshMQTT-Neighbors"
                )
                self.mqtt_thread.start()
                
                info_print("👥 Thread MQTT démarré avec auto-reconnect")
                
                # Succès - sortir de la boucle de retry
                return
            
            except OSError as e:
                # Erreurs réseau (connexion refusée, timeout, etc.)
                error_type = type(e).__name__
                if attempt < max_retries - 1:
                    error_print(f"⚠️ Erreur connexion MQTT ({error_type}): {e}")
                    error_print(f"   Nouvelle tentative dans {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    error_print(f"❌ Échec connexion MQTT après {max_retries} tentatives:")
                    error_print(f"   Serveur: {self.mqtt_server}:{self.mqtt_port}")
                    error_print(f"   Erreur: {e}")
                    self.enabled = False
            
            except Exception as e:
                # Autres erreurs
                error_print(f"❌ Erreur démarrage MQTT: {e}")
                import traceback
                debug_print(traceback.format_exc())
                
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    self.enabled = False
    
    def _mqtt_loop_with_reconnect(self):
        """
        Boucle MQTT avec gestion automatique des reconnexions
        
        Cette méthode est exécutée dans un thread séparé et maintient
        la connexion MQTT active avec reconnexion automatique en cas de perte.
        """
        while True:
            try:
                # loop_forever gère automatiquement les reconnexions
                # grâce à reconnect_delay_set configuré précédemment
                self.mqtt_client.loop_forever()
                
            except Exception as e:
                error_print(f"👥 Erreur boucle MQTT: {e}")
                error_print(f"   Tentative de reconnexion dans 30s...")
                time.sleep(30)
                
                # Tenter de se reconnecter
                try:
                    self.mqtt_client.reconnect()
                except Exception as reconnect_error:
                    error_print(f"👥 Échec reconnexion: {reconnect_error}")
                    time.sleep(60)  # Attendre plus longtemps avant de réessayer
    
    def stop_monitoring(self):
        """Arrêter la collecte MQTT"""
        if self.mqtt_client:
            self.mqtt_client.disconnect()
            self.mqtt_client.loop_stop()
            info_print("👥 Collecte MQTT arrêtée")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Obtenir les statistiques de collecte
        
        Returns:
            dict: Statistiques de collecte
        """
        return {
            'connected': self.connected,
            'messages_received': self.stats['messages_received'],
            'neighbor_packets': self.stats['neighbor_packets'],
            'nodes_discovered': len(self.stats['nodes_discovered']),
            'last_update': self.stats['last_update']
        }
    
    def get_status_report(self, compact: bool = True) -> str:
        """
        Générer un rapport de statut
        
        Args:
            compact: Format compact pour LoRa ou détaillé pour Telegram
            
        Returns:
            str: Rapport formaté
        """
        stats = self.get_stats()
        
        if compact:
            # Format court pour LoRa
            status = "🟢" if stats['connected'] else "🔴"
            lines = [
                f"👥 MQTT Neighbors {status}",
                f"Messages: {stats['messages_received']}",
                f"Packets: {stats['neighbor_packets']}",
                f"Nœuds: {stats['nodes_discovered']}"
            ]
            return " | ".join(lines)
        else:
            # Format détaillé pour Telegram
            status = "Connecté 🟢" if stats['connected'] else "Déconnecté 🔴"
            lines = [
                "👥 **MQTT Neighbor Collector**",
                f"Statut: {status}",
                f"Serveur: {self.mqtt_server}:{self.mqtt_port}",
                "",
                "📊 **Statistiques**",
                f"• Messages reçus: {stats['messages_received']}",
                f"• Paquets neighbor: {stats['neighbor_packets']}",
                f"• Nœuds découverts: {stats['nodes_discovered']}",
            ]
            
            if stats['last_update']:
                last_update_str = time.strftime(
                    "%H:%M:%S",
                    time.localtime(stats['last_update'])
                )
                lines.append(f"• Dernière MAJ: {last_update_str}")
            
            return "\n".join(lines)
