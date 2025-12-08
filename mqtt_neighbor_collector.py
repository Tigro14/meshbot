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
    from meshtastic.protobuf import mesh_pb2, portnums_pb2, mqtt_pb2
    PROTOBUF_AVAILABLE = True
except ImportError as e:
    error_print(f"MQTT Neighbor Collector: meshtastic protobuf manquant: {e}")
    PROTOBUF_AVAILABLE = False

# Import cryptography for decryption
try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    CRYPTO_AVAILABLE = True
except ImportError as e:
    error_print(f"MQTT Neighbor Collector: cryptography manquant (déchiffrement désactivé): {e}")
    CRYPTO_AVAILABLE = False


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
                 mqtt_topic_pattern: Optional[str] = None,
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
            mqtt_topic_pattern: Pattern de topic spécifique (optionnel, défaut: wildcard)
                               Ex: "msh/EU_868/2/e/MediumFast" ou "msh/+/+/2/e/+"
            persistence: Instance de TrafficPersistence pour sauvegarder les données
            node_manager: Instance de NodeManager pour calculer les distances (optionnel)
        """
        # Initialiser tous les attributs d'abord (pour éviter AttributeError si désactivé)
        self.mqtt_server = mqtt_server
        self.mqtt_port = mqtt_port
        self.mqtt_user = mqtt_user
        self.mqtt_password = mqtt_password
        self.mqtt_topic_root = mqtt_topic_root
        self.mqtt_topic_pattern = mqtt_topic_pattern  # Peut être None (utilise wildcard par défaut)
        self.persistence = persistence
        self.node_manager = node_manager
        self.enabled = False
        
        # État interne
        self.connected = False
        self.neighbor_updates = deque(maxlen=100)
        
        # Déduplication: dictionnaire {(packet_id, from_id): timestamp}
        # Les mêmes paquets sont répétés par plusieurs gateways
        self._seen_packets = {}
        self._dedup_window = 20  # secondes
        
        self.stats = {
            'messages_received': 0,
            'neighbor_packets': 0,
            'nodes_discovered': set(),
            'last_update': None,
            'duplicates_filtered': 0
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
            # Format: msh/<region>/<channel>/2/e/<gateway_id>
            # Utilise mqtt_topic_pattern si configuré, sinon wildcard par défaut
            if self.mqtt_topic_pattern:
                # Topic spécifique configuré (ex: "msh/EU_868/2/e/MediumFast")
                # Ajouter /# à la fin s'il n'y a pas déjà de wildcard pour capturer tous les gateway IDs
                topic_pattern = self.mqtt_topic_pattern
                if not topic_pattern.endswith('#') and not topic_pattern.endswith('+'):
                    topic_pattern += '/#'  # Capturer tous les messages sous ce channel
                info_print(f"   Abonné à: {topic_pattern} (topic spécifique)")
            else:
                # Wildcard + pour capturer tous les régions/channels/gateways
                topic_pattern = f"{self.mqtt_topic_root}/+/+/2/e/+"
                info_print(f"   Abonné à: {topic_pattern} (pattern wildcard)")
            
            client.subscribe(topic_pattern)
            
        else:
            error_print(f"👥 Échec connexion MQTT: code {rc}")
            self.connected = False
    
    def _on_mqtt_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        """Callback de déconnexion MQTT"""
        self.connected = False
        if reason_code != 0:
            error_print(f"👥 Déconnexion MQTT inattendue: code {reason_code}")
        else:
            debug_print("👥 Déconnexion MQTT normale")
    
    def _decrypt_packet(self, encrypted_data, packet_id, from_id):
        """
        Déchiffrer un paquet avec la clé par défaut du canal 0 de Meshtastic
        
        Meshtastic utilise AES-128-CTR avec:
        - Clé: PSK du canal (défaut canal 0: "1PG7OiApB1nwvP+rz05pAQ==" en base64)
        - Nonce: packet_id (8 octets LE) + from_id (4 octets LE) + block_counter (4 octets zero)
        
        Référence: https://github.com/liamcottle/meshtastic-map/blob/main/src/mqtt.js#L658
        
        Args:
            encrypted_data: Données chiffrées (bytes)
            packet_id: ID du paquet (int)
            from_id: ID de l'émetteur (int)
            
        Returns:
            Données déchiffrées (bytes) ou None si échec
        """
        if not CRYPTO_AVAILABLE:
            return None
        
        try:
            # Clé par défaut du canal 0 de Meshtastic (16 bytes pour AES-128)
            # "1PG7OiApB1nwvP+rz05pAQ==" en base64
            import base64
            psk = base64.b64decode("1PG7OiApB1nwvP+rz05pAQ==")
            
            # Construire le nonce: packet_id (8 octets LE) + from_id (4 octets LE) + block_counter (4 zéros)
            nonce_bytes = packet_id.to_bytes(8, 'little') + from_id.to_bytes(4, 'little')
            nonce = nonce_bytes + b'\x00' * 4  # block_counter = 0
            
            # Créer le déchiffreur AES-128-CTR
            cipher = Cipher(
                algorithms.AES(psk),
                modes.CTR(nonce),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            
            # Déchiffrer
            decrypted = decryptor.update(encrypted_data) + decryptor.finalize()
            
            return decrypted
            
        except Exception as e:
            debug_print(f"👥 Erreur déchiffrement: {e}")
            return None
    
    def _is_duplicate_packet(self, packet_id, from_id):
        """
        Vérifier si un paquet a déjà été vu récemment (déduplication)
        
        Les paquets MQTT sont répétés par plusieurs gateways sur le réseau,
        il faut filtrer les duplicatas sur une fenêtre de 20 secondes.
        
        Args:
            packet_id: ID du paquet
            from_id: ID de l'émetteur
            
        Returns:
            True si duplicate, False sinon
        """
        current_time = time.time()
        
        # Nettoyer les anciennes entrées (> 20 secondes)
        expired_keys = []
        for key, timestamp in self._seen_packets.items():
            if current_time - timestamp > self._dedup_window:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._seen_packets[key]
        
        # Vérifier si ce paquet a déjà été vu
        dedup_key = (packet_id, from_id)
        
        if dedup_key in self._seen_packets:
            # Duplicate trouvé
            return True
        
        # Nouveau paquet, l'enregistrer
        self._seen_packets[dedup_key] = current_time
        return False
    
    def _process_nodeinfo(self, packet, decoded, from_id):
        """
        Traiter un paquet NODEINFO pour extraire et sauvegarder le nom du nœud
        
        Args:
            packet: Paquet MeshPacket protobuf
            decoded: Données décodées (Data protobuf)
            from_id: ID de l'émetteur
        """
        try:
            # Parser le payload User
            user = mesh_pb2.User()
            user.ParseFromString(decoded.payload)
            
            # Extraire les noms
            long_name = user.long_name.strip() if user.long_name else ""
            short_name = user.short_name.strip() if user.short_name else ""
            
            # Utiliser longName en priorité, sinon shortName
            name = long_name or short_name
            
            if name and self.node_manager:
                # Mettre à jour le node_manager avec ce nom
                if from_id not in self.node_manager.node_names:
                    self.node_manager.node_names[from_id] = {
                        'name': name,
                        'lat': None,
                        'lon': None,
                        'alt': None,
                        'last_update': time.time()
                    }
                    debug_print(f"👥 [MQTT] Nouveau nœud: {name} (!{from_id:08x})")
                else:
                    old_name = self.node_manager.node_names[from_id]['name']
                    if old_name != name:
                        self.node_manager.node_names[from_id]['name'] = name
                        debug_print(f"👥 [MQTT] Nœud renommé: {old_name} → {name} (!{from_id:08x})")
                
                # Sauvegarder les noms de nœuds (différé pour éviter trop d'écritures)
                import threading
                threading.Timer(10.0, lambda: self.node_manager.save_node_names()).start()
                
        except Exception as e:
            debug_print(f"👥 Erreur traitement NODEINFO: {e}")
    
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
                envelope = mqtt_pb2.ServiceEnvelope()
                envelope.ParseFromString(msg.payload)
            except Exception as e:
                debug_print(f"👥 Erreur parsing ServiceEnvelope: {e}")
                return
            
            # Vérifier qu'il y a un packet
            if not envelope.HasField('packet'):
                return
            
            packet = envelope.packet
            
            # Extraire les informations du ServiceEnvelope (gateway qui a relayé le paquet)
            gateway_id = getattr(envelope, 'gateway_id', '')
            channel_id = getattr(envelope, 'channel_id', '')
            
            # Extraire l'ID du paquet et de l'émetteur pour déduplication et déchiffrement
            packet_id = getattr(packet, 'id', 0)
            from_id = getattr(packet, 'from', 0)
            
            # Déduplication: vérifier si ce paquet a déjà été traité
            if self._is_duplicate_packet(packet_id, from_id):
                self.stats['duplicates_filtered'] += 1
                return
            
            # Vérifier qu'il y a des données décodées OU chiffrées
            if packet.HasField('decoded'):
                # Paquet déjà décodé (non chiffré)
                decoded = packet.decoded
            elif packet.HasField('encrypted') and CRYPTO_AVAILABLE:
                # Paquet chiffré - tenter de déchiffrer avec la clé par défaut du canal 0
                encrypted_data = packet.encrypted
                decrypted_data = self._decrypt_packet(encrypted_data, packet_id, from_id)
                
                if not decrypted_data:
                    # Échec du déchiffrement
                    return
                
                # Parser les données déchiffrées comme un Data protobuf
                try:
                    decoded = mesh_pb2.Data()
                    decoded.ParseFromString(decrypted_data)
                except Exception as e:
                    return
            else:
                # Ni decoded ni encrypted (ou crypto non disponible)
                return
            
            # Filtrer les paquets à logger: POSITION, TELEMETRY, NEIGHBORINFO et NODEINFO
            # POSITION_APP = 3, NODEINFO_APP = 4, TELEMETRY_APP = 67, NEIGHBORINFO_APP = 71
            portnum = decoded.portnum
            is_loggable = portnum in [
                portnums_pb2.PortNum.POSITION_APP,
                portnums_pb2.PortNum.NODEINFO_APP,
                portnums_pb2.PortNum.TELEMETRY_APP,
                portnums_pb2.PortNum.NEIGHBORINFO_APP
            ]
            
            if is_loggable:
                portnum_names = {
                    portnums_pb2.PortNum.POSITION_APP: "POSITION",
                    portnums_pb2.PortNum.NODEINFO_APP: "NODEINFO",
                    portnums_pb2.PortNum.TELEMETRY_APP: "TELEMETRY",
                    portnums_pb2.PortNum.NEIGHBORINFO_APP: "NEIGHBORINFO"
                }
                portnum_name = portnum_names.get(portnum, f"UNKNOWN({portnum})")
                # Get longname if available from node_manager
                longname = None
                if self.node_manager:
                    longname = self.node_manager.get_node_name(from_id)
                    # If get_node_name returns "Unknown" or a hex ID, don't use it
                    if longname and (longname == "Unknown" or longname.startswith("!")):
                        longname = None
                
                # Get gateway name if available
                gateway_name = None
                if gateway_id and self.node_manager:
                    try:
                        gateway_name = self.node_manager.get_node_name(gateway_id)
                        # If get_node_name returns "Unknown" or a hex ID, use the ID as-is
                        if gateway_name and (gateway_name == "Unknown" or gateway_name.startswith("!")):
                            gateway_name = gateway_id
                    except:
                        gateway_name = gateway_id
                elif gateway_id:
                    gateway_name = gateway_id
                
                # Format log message with "via" information
                via_suffix = f" via {gateway_name}" if gateway_name else ""
                
                if longname:
                    debug_print(f"👥 [MQTT] Paquet {portnum_name} de {from_id:08x} ({longname}){via_suffix}")
                else:
                    debug_print(f"👥 [MQTT] Paquet {portnum_name} de {from_id:08x}{via_suffix}")
            
            # Traiter les paquets NODEINFO pour mettre à jour les noms de nœuds
            if decoded.portnum == portnums_pb2.PortNum.NODEINFO_APP:
                self._process_nodeinfo(packet, decoded, from_id)
                return
            
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
            # Note: 'from' est un mot-clé Python, utiliser getattr
            node_id = neighbor_info.node_id if neighbor_info.node_id else getattr(packet, 'from', 0)
            
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
                
                self.persistence.save_neighbor_info(node_id_str, formatted_neighbors, source='mqtt')
                
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
                    
                    # Obtenir le nom du gateway
                    gateway_name = None
                    if gateway_id and self.node_manager:
                        try:
                            gateway_name = self.node_manager.get_node_name(gateway_id)
                            # If get_node_name returns "Unknown" or a hex ID, use the ID as-is
                            if gateway_name and (gateway_name == "Unknown" or gateway_name.startswith("!")):
                                gateway_name = gateway_id
                        except:
                            gateway_name = gateway_id
                    elif gateway_id:
                        gateway_name = gateway_id
                    
                    # Format du log similaire aux paquets mesh
                    distance_str = ""
                    if distance_km is not None:
                        distance_str = f" [{distance_km:.1f}km]"
                    
                    via_suffix = f" via {gateway_name}" if gateway_name else ""
                    
                    debug_print(f"[MQTT] 👥 NEIGHBORINFO de {node_name}{distance_str}{via_suffix}: {len(formatted_neighbors)} voisins")
                
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
                
                # Se connecter au serveur de manière asynchrone (non-bloquant)
                info_print(f"👥 Connexion à {self.mqtt_server}:{self.mqtt_port}...")
                self.mqtt_client.connect_async(
                    self.mqtt_server,
                    self.mqtt_port,
                    keepalive=60
                )
                
                # Démarrer la boucle MQTT dans un thread avec auto-reconnect
                # loop_start() démarre un thread en arrière-plan (non-bloquant)
                self.mqtt_thread = threading.Thread(
                    target=self._mqtt_loop_with_reconnect,
                    daemon=True,
                    name="MeshMQTT-Neighbors"
                )
                self.mqtt_thread.start()
                
                info_print("👥 Thread MQTT démarré avec auto-reconnect (non-bloquant)")
                
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
    
    def get_directly_heard_nodes(self, hours: int = 48) -> List[Dict[str, Any]]:
        """
        Obtenir la liste des nœuds qui ont été entendus directement via MQTT
        (nœuds qui ont envoyé des paquets NEIGHBORINFO via MQTT)
        
        Args:
            hours: Nombre d'heures à considérer (défaut: 48h)
            
        Returns:
            Liste de dictionnaires avec node_id, longname, et last_heard
            Triée par last_heard (plus récent d'abord)
        """
        if not self.persistence:
            return []
        
        try:
            # Récupérer les données de voisinage depuis la persistance
            neighbors_data = self.persistence.load_neighbors(hours=hours)
            
            if not neighbors_data:
                return []
            
            # Créer un dictionnaire pour suivre le last_heard de chaque nœud
            # Un nœud est "directly heard" s'il apparaît comme node_id (émetteur de NEIGHBORINFO)
            nodes_heard = {}
            
            for node_id, neighbors_list in neighbors_data.items():
                # Le node_id est celui qui a envoyé le NEIGHBORINFO
                # Trouver le timestamp le plus récent parmi ses voisins
                if neighbors_list:
                    latest_timestamp = max(n.get('timestamp', 0) for n in neighbors_list)
                    
                    # Mettre à jour ou ajouter le nœud
                    if node_id not in nodes_heard or latest_timestamp > nodes_heard[node_id]:
                        nodes_heard[node_id] = latest_timestamp
            
            # Convertir en liste avec longname
            result = []
            for node_id, last_heard in nodes_heard.items():
                # Obtenir le nom du nœud via node_manager
                longname = node_id  # Par défaut, utiliser l'ID
                if self.node_manager:
                    try:
                        # Convertir !xxxxxxxx en int pour get_node_name
                        if node_id.startswith('!'):
                            node_id_int = int(node_id[1:], 16)
                            longname = self.node_manager.get_node_name(node_id_int)
                        else:
                            longname = self.node_manager.get_node_name(node_id)
                    except Exception as e:
                        debug_print(f"Erreur récupération nom pour {node_id}: {e}")
                
                result.append({
                    'node_id': node_id,
                    'longname': longname,
                    'last_heard': last_heard
                })
            
            # Trier par last_heard (plus récent d'abord)
            result.sort(key=lambda x: x['last_heard'], reverse=True)
            
            return result
            
        except Exception as e:
            error_print(f"Erreur récupération nœuds MQTT: {e}")
            import traceback
            debug_print(traceback.format_exc())
            return []
