import base64
import json
import os
from datetime import datetime
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

NODE_NAMES_FILE = "node_names.json"
OUTPUT_FILE = "node_positions.json"
STATS_INTERVAL = 60  # Afficher les stats toutes les 60 secondes

# Clés à tester
TEST_KEYS = {
    "default": base64.b64decode("AQ==") + b'\x00' * 31,
    "empty": b'\x00' * 32,
    "ones": b'\x01' * 32,
}

# ============ DONNÉES GLOBALES ============
NODE_NAMES = {}
NODE_DATA = {}  # {node_id: {"name": ..., "position": ..., "last_seen": ..., "telemetry": ...}}
MESSAGE_COUNT = 0
LAST_STATS_TIME = datetime.now()

# ============ CHARGEMENT DES NOMS ============
def load_node_names():
    global NODE_NAMES
    try:
        if os.path.exists(NODE_NAMES_FILE):
            with open(NODE_NAMES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                NODE_NAMES = {int(node_id): name for node_id, name in data.items()}
            print(f"✅ {len(NODE_NAMES)} noms de nœuds chargés")
        else:
            print(f"⚠️  Fichier {NODE_NAMES_FILE} non trouvé")
    except Exception as e:
        print(f"❌ Erreur lors du chargement: {e}")

# ============ SAUVEGARDE DES DONNÉES ============
def save_node_data():
    try:
        output = {}
        for node_id, data in NODE_DATA.items():
            node_hex = f"{node_id:08x}"
            output[node_hex] = {
                "name": data.get("name", f"!{node_hex}"),
                "position": data.get("position"),
                "last_seen": data.get("last_seen"),
                "telemetry": data.get("telemetry"),
                "message_count": data.get("message_count", 0)
            }
        
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"💾 Données sauvegardées dans {OUTPUT_FILE}")
    except Exception as e:
        print(f"❌ Erreur sauvegarde: {e}")

# ============ STATISTIQUES ============
def print_stats():
    global LAST_STATS_TIME
    
    now = datetime.now()
    if (now - LAST_STATS_TIME).seconds < STATS_INTERVAL:
        return
    
    LAST_STATS_TIME = now
    
    print(f"\n{'='*60}")
    print(f"📊 STATISTIQUES - {now.strftime('%H:%M:%S')}")
    print(f"{'='*60}")
    print(f"Messages reçus: {MESSAGE_COUNT}")
    print(f"Nœuds connus dans JSON: {len(NODE_NAMES)}")
    print(f"Nœuds détectés sur MQTT: {len(NODE_DATA)}")
    
    # Compter les nœuds avec position
    nodes_with_position = sum(1 for d in NODE_DATA.values() if d.get("position"))
    print(f"Nœuds avec position GPS: {nodes_with_position}")
    
    # Top 5 des nœuds les plus actifs
    if NODE_DATA:
        sorted_nodes = sorted(NODE_DATA.items(), 
                            key=lambda x: x[1].get("message_count", 0), 
                            reverse=True)[:5]
        print(f"\n🔝 Top 5 nœuds actifs:")
        for node_id, data in sorted_nodes:
            name = data.get("name", f"!{node_id:08x}")
            count = data.get("message_count", 0)
            last_seen = data.get("last_seen", "jamais")
            print(f"  {name}: {count} messages (vu: {last_seen})")
    
    print(f"{'='*60}\n")
    
    # Sauvegarder périodiquement
    save_node_data()

# ============ DÉCHIFFREMENT ============
def decrypt_message(encrypted_data, packet_id, from_node, psk):
    nonce_variants = [
        ("v1", packet_id.to_bytes(8, 'little') + from_node.to_bytes(4, 'little') + b'\x00' * 4),
        ("v2", packet_id.to_bytes(4, 'little') + from_node.to_bytes(4, 'little') + b'\x00' * 8),
        ("v3", from_node.to_bytes(8, 'little') + packet_id.to_bytes(8, 'little')),
    ]
    
    for nonce_name, nonce in nonce_variants:
        try:
            cipher = Cipher(algorithms.AES(psk), modes.CTR(nonce), backend=default_backend())
            decryptor = cipher.decryptor()
            decrypted = decryptor.update(encrypted_data) + decryptor.finalize()
            
            test_data = mesh_pb2.Data()
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                test_data.ParseFromString(decrypted)
            
            return decrypted
        except:
            continue
    
    return None

# ============ TRAITEMENT DES NŒUDS ============
def update_node_data(node_id, data_type, data):
    global NODE_DATA
    
    # Ignorer les nœuds non présents dans node_names.json
    if node_id not in NODE_NAMES:
        return
    
    if node_id not in NODE_DATA:
        NODE_DATA[node_id] = {
            "name": NODE_NAMES[node_id],
            "message_count": 0
        }
    
    NODE_DATA[node_id]["message_count"] += 1
    NODE_DATA[node_id]["last_seen"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if data_type == "position":
        NODE_DATA[node_id]["position"] = data
        print(f"📍 {NODE_NAMES[node_id]} - Position: {data['lat']:.6f}, {data['lon']:.6f}")
    
    elif data_type == "nodeinfo":
        print(f"👤 {NODE_NAMES[node_id]} - NodeInfo: {data['long_name']} ({data['short_name']})")
    
    elif data_type == "telemetry":
        NODE_DATA[node_id]["telemetry"] = data
        battery = data.get('battery_level', 'N/A')
        print(f"🔋 {NODE_NAMES[node_id]} - Batterie: {battery}%")

# ============ CALLBACK MQTT ============
def on_message(client, userdata, msg):
    global MESSAGE_COUNT
    MESSAGE_COUNT += 1
    
    try:
        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.ParseFromString(msg.payload)
        
        if not envelope.HasField("packet"):
            return
        
        mesh_packet = envelope.packet
        from_id = getattr(mesh_packet, 'from_', getattr(mesh_packet, 'from'))
        to_id = mesh_packet.to
        packet_id = mesh_packet.id
        
        payload_type = mesh_packet.WhichOneof("payload_variant")
        
        # Traiter les messages décodés
        if payload_type == "decoded":
            data = mesh_packet.decoded
            portnum = data.portnum
            
            if portnum == 3:  # POSITION_APP
                position = mesh_pb2.Position()
                position.ParseFromString(data.payload)
                lat = position.latitude_i / 1e7
                lon = position.longitude_i / 1e7
                update_node_data(from_id, "position", {"lat": lat, "lon": lon})
            
            elif portnum == 4:  # NODEINFO_APP
                nodeinfo = mesh_pb2.User()
                nodeinfo.ParseFromString(data.payload)
                update_node_data(from_id, "nodeinfo", {
                    "long_name": nodeinfo.long_name,
                    "short_name": nodeinfo.short_name
                })
            
            elif portnum == 67:  # TELEMETRY_APP
                telemetry = mesh_pb2.Telemetry()
                telemetry.ParseFromString(data.payload)
                if telemetry.HasField("device_metrics"):
                    update_node_data(from_id, "telemetry", {
                        "battery_level": telemetry.device_metrics.battery_level
                    })
        
        # Traiter les messages chiffrés
        elif payload_type == "encrypted":
            encrypted_data = mesh_packet.encrypted
            
            for key_name, test_psk in TEST_KEYS.items():
                decrypted = decrypt_message(encrypted_data, packet_id, from_id, test_psk)
                if decrypted:
                    try:
                        data = mesh_pb2.Data()
                        import warnings
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore")
                            data.ParseFromString(decrypted)
                        
                        if data.portnum == 3:  # Position
                            position = mesh_pb2.Position()
                            position.ParseFromString(data.payload)
                            lat = position.latitude_i / 1e7
                            lon = position.longitude_i / 1e7
                            update_node_data(from_id, "position", {"lat": lat, "lon": lon})
                        
                        elif data.portnum == 4:  # NodeInfo
                            nodeinfo = mesh_pb2.User()
                            nodeinfo.ParseFromString(data.payload)
                            update_node_data(from_id, "nodeinfo", {
                                "long_name": nodeinfo.long_name,
                                "short_name": nodeinfo.short_name
                            })
                        
                        elif data.portnum == 67:  # Telemetry
                            telemetry = mesh_pb2.Telemetry()
                            telemetry.ParseFromString(data.payload)
                            if telemetry.HasField("device_metrics"):
                                update_node_data(from_id, "telemetry", {
                                    "battery_level": telemetry.device_metrics.battery_level
                                })
                        
                        break
                    except:
                        continue
        
        # Afficher les stats périodiquement
        print_stats()
    
    except Exception as e:
        pass  # Ignorer les erreurs silencieusement

# ============ CONNEXION MQTT ============
def on_connect(client, userdata, flags, rc, properties=None):
    print(f"✅ Connecté au broker MQTT")
    client.subscribe(MQTT_TOPIC)
    print(f"📡 Abonné à {MQTT_TOPIC}")
    print(f"🎯 Collecte des positions des nœuds connus...")
    print(f"📊 Stats affichées toutes les {STATS_INTERVAL} secondes\n")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.on_connect = on_connect
client.on_message = on_message

print(f"🚀 Démarrage du tracker Meshtastic\n")
load_node_names()
print(f"\nConnexion à {MQTT_BROKER}:{MQTT_PORT}...")
client.connect(MQTT_BROKER, MQTT_PORT, 60)

try:
    client.loop_forever()
except KeyboardInterrupt:
    print(f"\n\n🛑 Arrêt du tracker...")
    save_node_data()
    print(f"✅ Données finales sauvegardées dans {OUTPUT_FILE}")
