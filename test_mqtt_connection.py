#!/usr/bin/env python3
"""
Test script pour vérifier la connexion MQTT et le parsing des messages

Usage:
    python test_mqtt_connection.py

Ce script:
1. Se connecte au serveur MQTT Meshtastic
2. S'abonne aux topics ServiceEnvelope
3. Affiche tous les messages reçus
4. Parse les messages NEIGHBORINFO_APP
5. Affiche les statistiques
"""

import sys
import time
import signal
from collections import defaultdict

# Vérifier les dépendances
try:
    import paho.mqtt.client as mqtt
    print("✅ paho-mqtt disponible")
except ImportError:
    print("❌ paho-mqtt manquant. Installer avec: pip install paho-mqtt")
    sys.exit(1)

try:
    from meshtastic.protobuf import mesh_pb2, portnums_pb2, mqtt_pb2
    print("✅ meshtastic protobuf disponible")
except ImportError:
    print("❌ meshtastic protobuf manquant. Installer avec: pip install meshtastic")
    sys.exit(1)

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    print("✅ cryptography disponible (déchiffrement activé)")
    CRYPTO_AVAILABLE = True
except ImportError:
    print("⚠️  cryptography manquant (déchiffrement désactivé). Installer avec: pip install cryptography")
    CRYPTO_AVAILABLE = False

# Configuration MQTT (à adapter selon config.py)
MQTT_SERVER = "serveurperso.com"
MQTT_PORT = 1883
MQTT_USER = "meshdev"
MQTT_PASSWORD = ""  # À remplir depuis config.py
MQTT_TOPIC_ROOT = "msh"
MQTT_TOPIC_PATTERN = "msh/EU_868/2/e/MediumFast/#"  # Topic spécifique avec wildcard pour capturer tous les gateways

# Statistiques
stats = {
    'messages_total': 0,
    'messages_parseable': 0,
    'messages_neighborinfo': 0,
    'messages_encrypted': 0,
    'messages_decrypted': 0,
    'messages_decryption_failed': 0,
    'messages_other_type': defaultdict(int),
    'nodes_seen': set(),
    'topics_seen': set(),
    'duplicates_filtered': 0
}

# Déduplication: {(packet_id, from_id): timestamp}
seen_packets = {}
DEDUP_WINDOW = 20  # secondes

def signal_handler(sig, frame):
    """Gestion de Ctrl+C pour afficher les stats avant de quitter"""
    print("\n" + "="*60)
    print("📊 STATISTIQUES FINALES")
    print("="*60)
    print(f"Messages totaux reçus: {stats['messages_total']}")
    print(f"Messages parseables (ServiceEnvelope): {stats['messages_parseable']}")
    print(f"Messages NEIGHBORINFO_APP: {stats['messages_neighborinfo']}")
    print(f"Messages chiffrés (encrypted): {stats['messages_encrypted']}")
    if CRYPTO_AVAILABLE:
        print(f"Messages déchiffrés avec succès: {stats['messages_decrypted']}")
        print(f"Échecs de déchiffrement: {stats['messages_decryption_failed']}")
    print(f"Duplicatas filtrés: {stats['duplicates_filtered']}")
    print(f"Nœuds uniques vus: {len(stats['nodes_seen'])}")
    print(f"Topics uniques vus: {len(stats['topics_seen'])}")
    
    if stats['messages_other_type']:
        print("\nTypes de messages reçus:")
        for portnum, count in sorted(stats['messages_other_type'].items(), key=lambda x: x[1], reverse=True):
            print(f"  {portnum}: {count}")
    
    print("\nTopics écoutés:")
    for topic in sorted(stats['topics_seen']):
        print(f"  {topic}")
    
    sys.exit(0)

def decrypt_packet(encrypted_data, packet_id, from_id):
    """
    Déchiffrer un paquet avec la clé par défaut du canal 0 de Meshtastic
    
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
        print(f"❌ Erreur déchiffrement: {e}")
        return None

def on_connect(client, userdata, flags, rc, properties=None):
    """Callback de connexion MQTT"""
    if rc == 0:
        print(f"✅ Connecté au serveur MQTT: {MQTT_SERVER}:{MQTT_PORT}")
        
        # S'abonner au topic configuré (spécifique ou wildcard)
        topic_pattern = MQTT_TOPIC_PATTERN
        result, mid = client.subscribe(topic_pattern)
        
        if result == mqtt.MQTT_ERR_SUCCESS:
            print(f"✅ Abonné à: {topic_pattern}")
            if "+" in topic_pattern:
                print(f"   (Pattern wildcard pour recevoir plusieurs messages)")
            else:
                print(f"   (Topic spécifique - le serveur ne supporte pas les wildcards)")
        else:
            print(f"❌ Échec abonnement au topic: {topic_pattern}")
            print(f"   Code d'erreur: {result}")
        
        print("\n" + "="*60)
        print("🎧 EN ÉCOUTE - Appuyez sur Ctrl+C pour arrêter")
        print("="*60)
        print("⏱️  Attendez quelques secondes pour voir les messages arriver...")
        print()
    else:
        print(f"❌ Échec connexion MQTT: code {rc}")
        sys.exit(1)

def on_subscribe(client, userdata, mid, granted_qos, properties=None):
    """Callback de confirmation d'abonnement"""
    print(f"✅ Abonnement confirmé par le serveur (QoS: {granted_qos})")
    print()

def on_disconnect(client, userdata, rc, properties=None):
    """Callback de déconnexion MQTT"""
    if rc != 0:
        print(f"⚠️ Déconnexion MQTT inattendue: code {rc}")

def on_message(client, userdata, msg):
    """
    Callback de réception de message MQTT
    Parse les ServiceEnvelope protobuf et affiche les informations
    """
    global seen_packets
    
    stats['messages_total'] += 1
    stats['topics_seen'].add(msg.topic)
    
    # Afficher chaque message reçu (debug premier message)
    if stats['messages_total'] == 1:
        print(f"📬 Premier message reçu!")
        print(f"   Topic: {msg.topic}")
        print(f"   Taille payload: {len(msg.payload)} octets")
        print()
    
    # Afficher tous les 10 messages
    if stats['messages_total'] % 10 == 0:
        print(f"📊 {stats['messages_total']} messages reçus jusqu'à présent...")
    
    try:
        # Parser le ServiceEnvelope protobuf
        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.ParseFromString(msg.payload)
        stats['messages_parseable'] += 1
        
        # Vérifier qu'il y a un packet
        if not envelope.HasField('packet'):
            return
        
        packet = envelope.packet
        
        # Accéder au champ 'from' (mot-clé réservé Python, utiliser getattr)
        packet_id = getattr(packet, 'id', 0)
        from_id = getattr(packet, 'from', 0)
        to_id = getattr(packet, 'to', 0)
        
        # Déduplication: vérifier si ce paquet a déjà été traité
        current_time = time.time()
        
        # Nettoyer les anciennes entrées (> 20 secondes)
        expired_keys = []
        for key, timestamp in seen_packets.items():
            if current_time - timestamp > DEDUP_WINDOW:
                expired_keys.append(key)
        
        for key in expired_keys:
            del seen_packets[key]
        
        # Vérifier si ce paquet a déjà été vu
        dedup_key = (packet_id, from_id)
        
        if dedup_key in seen_packets:
            # Duplicate trouvé - le filtrer
            stats['duplicates_filtered'] += 1
            return
        
        # Nouveau paquet, l'enregistrer
        seen_packets[dedup_key] = current_time
        
        # Formater l'ID du nœud
        from_id_str = f"!{from_id:08x}"
        stats['nodes_seen'].add(from_id_str)
        
        # Vérifier si chiffré ou décodé
        if packet.HasField('decoded'):
            # Paquet déjà décodé (non chiffré)
            decoded = packet.decoded
        elif packet.HasField('encrypted'):
            # Paquet chiffré - tenter de déchiffrer
            stats['messages_encrypted'] += 1
            print(f"🔒 Message chiffré de {from_id_str} sur {msg.topic}")
            
            if not CRYPTO_AVAILABLE:
                print(f"   ⚠️  Déchiffrement non disponible (installer cryptography)")
                print()
                return
            
            print(f"🔓 Tentative de déchiffrement avec clé par défaut canal 0...")
            
            encrypted_data = packet.encrypted
            decrypted_data = decrypt_packet(encrypted_data, packet_id, from_id)
            
            if not decrypted_data:
                stats['messages_decryption_failed'] += 1
                print(f"   ❌ Échec du déchiffrement")
                print()
                return
            
            # Parser les données déchiffrées comme un Data protobuf
            try:
                decoded = mesh_pb2.Data()
                decoded.ParseFromString(decrypted_data)
                stats['messages_decrypted'] += 1
                print(f"   ✅ Déchiffré avec succès! Type: {portnums_pb2.PortNum.Name(decoded.portnum)}")
            except Exception as e:
                stats['messages_decryption_failed'] += 1
                print(f"   ❌ Erreur parsing données déchiffrées: {e}")
                print()
                return
        else:
            # Ni decoded ni encrypted
            return
        portnum = decoded.portnum
        portnum_name = portnums_pb2.PortNum.Name(portnum)
        
        stats['messages_other_type'][portnum_name] += 1
        
        # Vérifier si c'est NEIGHBORINFO_APP
        if portnum == portnums_pb2.PortNum.NEIGHBORINFO_APP:
            stats['messages_neighborinfo'] += 1
            
            # Parser le payload NeighborInfo
            try:
                neighbor_info = mesh_pb2.NeighborInfo()
                neighbor_info.ParseFromString(decoded.payload)
                
                node_id = neighbor_info.node_id if neighbor_info.node_id else from_id
                node_id_str = f"!{node_id:08x}"
                neighbor_count = len(neighbor_info.neighbors)
                
                print(f"👥 NEIGHBORINFO de {node_id_str}: {neighbor_count} voisins")
                print(f"   Topic: {msg.topic}")
                
                # Afficher les voisins
                for i, neighbor in enumerate(neighbor_info.neighbors[:5]):  # Max 5 premiers
                    neighbor_id_str = f"!{neighbor.node_id:08x}"
                    print(f"   [{i+1}] {neighbor_id_str} - SNR: {neighbor.snr:.1f} dB")
                
                if len(neighbor_info.neighbors) > 5:
                    print(f"   ... et {len(neighbor_info.neighbors) - 5} autres")
                print()
                
            except Exception as e:
                print(f"❌ Erreur parsing NeighborInfo: {e}")
        else:
            # Afficher les autres types de messages (mode verbeux)
            print(f"📦 Message {portnum_name} de {from_id_str} sur {msg.topic}")
    
    except Exception as e:
        print(f"❌ Erreur parsing ServiceEnvelope: {e}")
        print(f"   Topic: {msg.topic}")
        print(f"   Payload (premiers 50 octets): {msg.payload[:50]}")

def main():
    """Point d'entrée du script"""
    global MQTT_PASSWORD
    
    print("="*60)
    print("🔍 TEST CONNEXION MQTT MESHTASTIC")
    print("="*60)
    print(f"Serveur: {MQTT_SERVER}:{MQTT_PORT}")
    print(f"Utilisateur: {MQTT_USER}")
    print(f"Topic: {MQTT_TOPIC_PATTERN}")
    print("="*60 + "\n")
    
    # Vérifier que le mot de passe est configuré
    if not MQTT_PASSWORD:
        print("⚠️ MQTT_PASSWORD non configuré!")
        print("Éditez ce script et ajoutez le mot de passe depuis config.py")
        print()
        MQTT_PASSWORD_input = input("Entrez le mot de passe MQTT (ou Enter pour continuer sans): ")
        if MQTT_PASSWORD_input:
            MQTT_PASSWORD = MQTT_PASSWORD_input
    
    # Configurer le handler de signal pour Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    # Créer le client MQTT
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    
    # Configurer l'authentification
    if MQTT_USER and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
        print(f"✅ Authentification configurée (user: {MQTT_USER})")
    
    # Configurer les callbacks
    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    
    # Se connecter au serveur
    try:
        print(f"🔌 Connexion à {MQTT_SERVER}:{MQTT_PORT}...")
        client.connect(MQTT_SERVER, MQTT_PORT, keepalive=60)
        
        # Démarrer la boucle (bloquant)
        client.loop_forever()
        
    except KeyboardInterrupt:
        signal_handler(None, None)
    except Exception as e:
        print(f"❌ Erreur: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
