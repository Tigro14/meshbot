import base64
import json
import os
from meshtastic import mesh_pb2, mqtt_pb2
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import paho.mqtt.client as mqtt

# ============ CONFIGURATION ============
MQTT_BROKER = "serveurperso.com"
MQTT_PORT = 1883
MQTT_USER = "meshdev"
MQTT_PASS = "large4cats"  
MQTT_TOPIC = "msh/EU_868/2/e/MediumFast/#"

# Fichier des noms de nœuds
NODE_NAMES_FILE = "node_names.json"

# Clés à tester
TEST_KEYS = {
    "default": base64.b64decode("AQ==") + b'\x00' * 31,
    "empty": b'\x00' * 32,
    "ones": b'\x01' * 32,
    # Ajoutez d'autres clés ici si nécessaire
    # "custom": base64.b64decode("VotreCléBase64=="),
}

# Filtrer uniquement certaines clés (mettre None pour tout accepter)
# Exemples: ["default"], ["default", "empty"], None
ALLOWED_KEYS = None  # Changez en ["default"] pour filtrer seulement votre clé

# Debug mode (affiche tous les messages reçus, même non déchiffrés)
DEBUG_MODE = False

# Filtrer par numéro de port (mettre None pour tout accepter)
# Ports courants:
#   1: TEXT_MESSAGE_APP (messages texte)
#   3: POSITION_APP (positions GPS)
#   4: NODEINFO_APP (infos de nœud)
#   67: TELEMETRY_APP (télémétrie/batterie)
# Exemples: [1, 3, 4, 67], [1], None
#ALLOWED_PORTS = [1, 3, 4, 67]  # Changez en None pour voir tous les ports
ALLOWED_PORTS = [1]  # Changez en None pour voir tous les ports

# ============ CHARGEMENT DES NOMS DE NŒUDS ============
NODE_NAMES = {}

def load_node_names():
    """Charge les noms des nœuds depuis le fichier JSON"""
    global NODE_NAMES
    try:
        if os.path.exists(NODE_NAMES_FILE):
            with open(NODE_NAMES_FILE, 'r', encoding='utf-8') as f:
                # Les IDs dans le JSON sont en décimal (string)
                data = json.load(f)
                # Convertir les IDs décimaux en entiers pour la correspondance
                NODE_NAMES = {int(node_id): name for node_id, name in data.items()}
            print(f"✅ {len(NODE_NAMES)} noms de nœuds chargés depuis {NODE_NAMES_FILE}")
        else:
            print(f"⚠️ Fichier {NODE_NAMES_FILE} non trouvé, utilisation des IDs uniquement")
    except Exception as e:
        print(f"❌ Erreur lors du chargement des noms: {e}")

def get_node_name(node_id):
    """Retourne le nom d'un nœud ou son ID en hex si inconnu"""
    if node_id in NODE_NAMES:
        return f"{NODE_NAMES[node_id]} (!{node_id:08x})"
    else:
        return f"!{node_id:08x}"

# ============ DÉCHIFFREMENT ============
def decrypt_message(encrypted_data, packet_id, from_node, psk):
    """Déchiffre un message Meshtastic chiffré avec AES-256-CTR"""
    # Tester différents formats de nonce (16 octets requis pour AES)
    nonce_variants = [
        # V1: packet_id (8 LE) + from (4 LE) + padding (4)
        ("v1_8+4+4", packet_id.to_bytes(8, 'little') + from_node.to_bytes(4, 'little') + b'\x00' * 4),
        
        # V2: packet_id (4 LE) + from (4 LE) + padding (8)
        ("v2_4+4+8", packet_id.to_bytes(4, 'little') + from_node.to_bytes(4, 'little') + b'\x00' * 8),
        
        # V3: from (8 LE) + packet_id (8 LE)
        ("v3_from8+id8", from_node.to_bytes(8, 'little') + packet_id.to_bytes(8, 'little')),
        
        # V4: from (4 LE) + packet_id (4 LE) + padding (8)
        ("v4_from4+id4+8", from_node.to_bytes(4, 'little') + packet_id.to_bytes(4, 'little') + b'\x00' * 8),
        
        # V5: packet_id (8 BE) + from (4 BE) + padding (4)
        ("v5_BE", packet_id.to_bytes(8, 'big') + from_node.to_bytes(4, 'big') + b'\x00' * 4),
    ]
    
    for nonce_name, nonce in nonce_variants:
        try:
            cipher = Cipher(algorithms.AES(psk), modes.CTR(nonce), backend=default_backend())
            decryptor = cipher.decryptor()
            decrypted = decryptor.update(encrypted_data) + decryptor.finalize()
            
            # Tester si c'est du protobuf valide
            try:
                test_data = mesh_pb2.Data()
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    test_data.ParseFromString(decrypted)
                
                # Si on arrive ici, le nonce est bon !
                if DEBUG_MODE:
                    print(f"[DEBUG] ✅ Nonce correct trouvé: {nonce_name}")
                return decrypted
            except:
                # Protobuf invalide, essayer le prochain nonce
                continue
        except:
            continue
    
    return None

# ============ CALLBACK MQTT ============
def on_message(client, userdata, msg):
    try:
        if DEBUG_MODE:
            print(f"\n[DEBUG] Message reçu sur {msg.topic} - {len(msg.payload)} octets")
        
        # 1. Décoder le ServiceEnvelope
        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.ParseFromString(msg.payload)
        
        if not envelope.HasField("packet"):
            if DEBUG_MODE:
                print("[DEBUG] Pas de paquet MeshPacket, ignoré")
            return
        
        mesh_packet = envelope.packet
        
        # 2. Extraire les infos du paquet
        from_id = getattr(mesh_packet, 'from_', getattr(mesh_packet, 'from'))
        to_id = mesh_packet.to
        packet_id = mesh_packet.id
        
        # 3. Vérifier le type de payload
        payload_type = mesh_packet.WhichOneof("payload_variant")
        
        if DEBUG_MODE:
            print(f"[DEBUG] Type: {payload_type}, From: !{from_id:08x}")
        
        if payload_type == "decoded":
            # ===== MESSAGE DÉCHIFFRÉ =====
            data = mesh_packet.decoded
            portnum = data.portnum
            
            # Filtrer par port si activé
            if ALLOWED_PORTS is not None and portnum not in ALLOWED_PORTS:
                if DEBUG_MODE:
                    print(f"[DEBUG] Port {portnum} ignoré par le filtre")
                return
            
            print(f"\n{'='*60}")
            print(f"📨 Message sur {msg.topic}")
            print(f"De: {get_node_name(from_id)}")
            print(f"Vers: !{to_id:08x}")
            print(f"ID: {packet_id}, Canal: {envelope.channel_id}, Hop: {mesh_packet.hop_limit}")
            
            if portnum == 1:  # TEXT_MESSAGE_APP
                text = data.payload.decode('utf-8', errors='replace')
                print(f"📝 Texte: {text}")
            
            elif portnum == 3:  # POSITION_APP
                position = mesh_pb2.Position()
                position.ParseFromString(data.payload)
                lat = position.latitude_i / 1e7
                lon = position.longitude_i / 1e7
                print(f"📍 Position: {lat:.6f}, {lon:.6f}")
            
            elif portnum == 4:  # NODEINFO_APP
                nodeinfo = mesh_pb2.User()
                nodeinfo.ParseFromString(data.payload)
                print(f"👤 Node: {nodeinfo.long_name} ({nodeinfo.short_name})")
            
            elif portnum == 67:  # TELEMETRY_APP
                telemetry = mesh_pb2.Telemetry()
                telemetry.ParseFromString(data.payload)
                if telemetry.HasField("device_metrics"):
                    print(f"🔋 Batterie: {telemetry.device_metrics.battery_level}%")
            
            else:
                print(f"Port {portnum}: {data.payload.hex()[:50]}...")
        
        elif payload_type == "encrypted":
            # ===== MESSAGE CHIFFRÉ =====
            encrypted_data = mesh_packet.encrypted
            
            # Tester différentes clés
            message_decoded = False
            successful_key = None
            decoded_data = None
            
            for key_name, test_psk in TEST_KEYS.items():
                # Si filtre activé, ignorer les clés non autorisées
                if ALLOWED_KEYS is not None and key_name not in ALLOWED_KEYS:
                    if DEBUG_MODE:
                        print(f"[DEBUG] Clé {key_name} ignorée par le filtre")
                    continue
                    
                decrypted = decrypt_message(encrypted_data, packet_id, from_id, test_psk)
                if decrypted:
                    try:
                        data = mesh_pb2.Data()
                        # Ignorer les warnings de parsing partiel
                        import warnings
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore")
                            data.ParseFromString(decrypted)
                        
                        if DEBUG_MODE:
                            print(f"[DEBUG] Déchiffré avec succès avec clé: {key_name}")
                        
                        message_decoded = True
                        successful_key = key_name
                        decoded_data = data
                        break  # Clé trouvée, sortir de la boucle
                    except Exception as parse_error:
                        # Cette clé ne fonctionne pas, essayer la suivante
                        if DEBUG_MODE:
                            print(f"[DEBUG] Clé {key_name} - erreur de parsing: {parse_error}")
                        continue
            
            # Afficher uniquement si déchiffré avec succès
            if message_decoded:
                # Filtrer par port si activé
                if ALLOWED_PORTS is not None and decoded_data.portnum not in ALLOWED_PORTS:
                    if DEBUG_MODE:
                        print(f"[DEBUG] Port {decoded_data.portnum} ignoré par le filtre")
                    return
                
                print(f"\n{'='*60}")
                print(f"📨 Message sur {msg.topic}")
                print(f"De: {get_node_name(from_id)}")
                print(f"Vers: !{to_id:08x}")
                print(f"ID: {packet_id}, Canal: {envelope.channel_id}, Hop: {mesh_packet.hop_limit}")
                print(f"🔒 Message chiffré ({len(encrypted_data)} octets)")
                print(f"✅ Clé: {successful_key}")
                
                # Traiter le message déchiffré
                if decoded_data.portnum == 1:  # Texte
                    text = decoded_data.payload.decode('utf-8', errors='replace')
                    print(f"🔓 Texte: {text}")
                elif decoded_data.portnum == 3:  # Position
                    position = mesh_pb2.Position()
                    position.ParseFromString(decoded_data.payload)
                    lat = position.latitude_i / 1e7
                    lon = position.longitude_i / 1e7
                    print(f"🔓 Position: {lat:.6f}, {lon:.6f}")
                elif decoded_data.portnum == 4:  # NodeInfo
                    nodeinfo = mesh_pb2.User()
                    nodeinfo.ParseFromString(decoded_data.payload)
                    print(f"🔓 Node: {nodeinfo.long_name} ({nodeinfo.short_name})")
                elif decoded_data.portnum == 67:  # Telemetry
                    telemetry = mesh_pb2.Telemetry()
                    telemetry.ParseFromString(decoded_data.payload)
                    if telemetry.HasField("device_metrics"):
                        print(f"🔓 Batterie: {telemetry.device_metrics.battery_level}%")
                else:
                    # Afficher plus de détails pour les ports inconnus
                    port_names = {
                        0: "UNKNOWN_APP", 1: "TEXT_MESSAGE_APP", 2: "REMOTE_HARDWARE_APP",
                        3: "POSITION_APP", 4: "NODEINFO_APP", 5: "ROUTING_APP",
                        6: "ADMIN_APP", 7: "TEXT_MESSAGE_COMPRESSED_APP", 8: "WAYPOINT_APP",
                        9: "AUDIO_APP", 10: "DETECTION_SENSOR_APP", 32: "REPLY_APP",
                        33: "IP_TUNNEL_APP", 34: "PAXCOUNTER_APP", 64: "SERIAL_APP",
                        65: "STORE_FORWARD_APP", 66: "RANGE_TEST_APP", 67: "TELEMETRY_APP",
                        68: "ZPS_APP", 69: "SIMULATOR_APP", 71: "TRACEROUTE_APP",
                        72: "NEIGHBORINFO_APP", 73: "ATAK_PLUGIN", 256: "PRIVATE_APP",
                        257: "ATAK_FORWARDER", 511: "MAX"
                    }
                    port_name = port_names.get(decoded_data.portnum, f"UNKNOWN_{decoded_data.portnum}")
                    print(f"🔓 Port {decoded_data.portnum} ({port_name})")
                    print(f"   Payload (hex): {decoded_data.payload.hex()[:100]}...")
                    print(f"   Payload (len): {len(decoded_data.payload)} octets")
            # Si filtre désactivé et aucune clé ne fonctionne, afficher l'erreur
            elif ALLOWED_KEYS is None:
                print(f"\n{'='*60}")
                print(f"📨 Message sur {msg.topic}")
                print(f"De: {get_node_name(from_id)}")
                print(f"Vers: !{to_id:08x}")
                print(f"🔒 Message chiffré ({len(encrypted_data)} octets)")
                print("❌ Aucune clé ne fonctionne")
    
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

# ============ CONNEXION MQTT ============
def on_connect(client, userdata, flags, rc, properties=None):
    print(f"✅ Connecté au broker (code {rc})")
    client.subscribe(MQTT_TOPIC)
    print(f"📡 Abonné à {MQTT_TOPIC}")
    
    if ALLOWED_KEYS is not None and len(ALLOWED_KEYS) > 0:
        print(f"🔑 Filtrage clés : {', '.join(ALLOWED_KEYS)}")
    else:
        print(f"🔓 Pas de filtrage de clés")
    
    if ALLOWED_PORTS is not None and len(ALLOWED_PORTS) > 0:
        port_names = {1: "Texte", 3: "Position", 4: "NodeInfo", 67: "Télémétrie"}
        port_list = [f"{p} ({port_names.get(p, '?')})" for p in ALLOWED_PORTS]
        print(f"📊 Filtrage ports : {', '.join(port_list)}")
    else:
        print(f"📊 Pas de filtrage de ports")
    
    if DEBUG_MODE:
        print(f"🐛 Mode debug activé")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.on_connect = on_connect
client.on_message = on_message

print(f"Connexion à {MQTT_BROKER}:{MQTT_PORT}...")
load_node_names()  # Charger les noms des nœuds
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_forever()
