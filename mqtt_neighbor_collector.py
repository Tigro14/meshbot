"""
Collecteur d'informations de voisinage via MQTT Meshtastic

Ce module se connecte à un serveur MQTT Meshtastic pour recevoir
les paquets NEIGHBORINFO_APP de tous les nœuds du réseau, permettant
de construire une topologie complète au-delà de la portée radio directe.

Configuration required in config.py:
- MQTT_NEIGHBOR_SERVER: MQTT server address
- MQTT_NEIGHBOR_USER: MQTT username
- MQTT_NEIGHBOR_PASSWORD: MQTT password
"""

import time
import json
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
                 persistence = None):
        """
        Initialiser le collecteur MQTT
        
        Args:
            mqtt_server: Adresse du serveur MQTT
            mqtt_port: Port MQTT (défaut: 1883)
            mqtt_user: Utilisateur MQTT (optionnel)
            mqtt_password: Mot de passe MQTT (optionnel)
            mqtt_topic_root: Racine des topics MQTT (défaut: "msh")
            persistence: Instance de TrafficPersistence pour sauvegarder les données
        """
        # Initialiser tous les attributs d'abord (pour éviter AttributeError si désactivé)
        self.mqtt_server = mqtt_server
        self.mqtt_port = mqtt_port
        self.mqtt_user = mqtt_user
        self.mqtt_password = mqtt_password
        self.mqtt_topic_root = mqtt_topic_root
        self.persistence = persistence
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
            
            # S'abonner aux topics de neighbor info
            # Format: msh/+/+/2/json/+/NEIGHBORINFO_APP
            # Wildcard + pour region, channel, et node_id
            topic_pattern = f"{self.mqtt_topic_root}/+/+/2/json/+/NEIGHBORINFO_APP"
            client.subscribe(topic_pattern)
            info_print(f"   Abonné à: {topic_pattern}")
            
            # Optionnel: s'abonner aussi au format protobuf si nécessaire
            # topic_protobuf = f"{self.mqtt_topic_root}/+/+/2/c/+/NEIGHBORINFO_APP"
            # client.subscribe(topic_protobuf)
            
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
        
        Format attendu (JSON):
        {
          "from": 305419896,
          "to": 4294967295,
          "channel": 0,
          "type": "NEIGHBORINFO_APP",
          "sender": "!12345678",
          "payload": {
            "neighborinfo": {
              "nodeId": 305419896,
              "neighbors": [
                {
                  "nodeId": 305419897,
                  "snr": 8.5,
                  "lastRxTime": 1234567890,
                  "nodeBroadcastInterval": 900
                }
              ]
            }
          }
        }
        """
        try:
            self.stats['messages_received'] += 1
            
            # Parser le JSON
            data = json.loads(msg.payload.decode('utf-8'))
            
            # Vérifier que c'est bien un NEIGHBORINFO_APP
            if data.get('type') != 'NEIGHBORINFO_APP':
                return
            
            # Extraire les informations
            from_id = data.get('from')
            sender = data.get('sender')  # Format "!xxxxxxxx"
            payload = data.get('payload', {})
            
            if not payload or 'neighborinfo' not in payload:
                debug_print(f"👥 Payload neighborinfo manquant dans message MQTT")
                return
            
            neighborinfo = payload['neighborinfo']
            node_id = neighborinfo.get('nodeId', from_id)
            neighbors_list = neighborinfo.get('neighbors', [])
            
            if not neighbors_list:
                return
            
            # Formater les données de voisins pour la persistence
            formatted_neighbors = []
            for neighbor in neighbors_list:
                neighbor_data = {
                    'node_id': neighbor.get('nodeId'),
                    'snr': neighbor.get('snr'),
                    'last_rx_time': neighbor.get('lastRxTime'),
                    'node_broadcast_interval': neighbor.get('nodeBroadcastInterval')
                }
                formatted_neighbors.append(neighbor_data)
            
            # Sauvegarder dans la base de données
            if formatted_neighbors:
                # Normaliser l'ID du nœud (int ou string "!xxxxxxxx")
                if isinstance(node_id, int):
                    node_id_str = f"!{node_id:08x}"
                else:
                    node_id_str = node_id if node_id.startswith('!') else f"!{node_id}"
                
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
                
                debug_print(f"👥 MQTT: {len(formatted_neighbors)} voisins pour {node_id_str}")
        
        except json.JSONDecodeError as e:
            error_print(f"👥 Erreur parsing JSON MQTT: {e}")
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
