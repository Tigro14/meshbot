import base64
from meshtastic import mesh_pb2, mqtt_pb2
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
import paho.mqtt.client as mqtt

# ============ CONFIGURATION ============
MQTT_BROKER = "serveurperso.com"
MQTT_PORT = 1883
MQTT_USER = "meshdev"
MQTT_PASS = "large4cats"  
MQTT_TOPIC = "msh/EU_868/2/e/MediumFast/#"

# Clé par défaut (AQ== en base64 = 0x01 en hex)
PSK_KEY = b'\x01' + b'\x00' * 31  # 1 suivi de 31 zéros

# ============ DÉCHIFFREMENT ============
def decrypt_message(encrypted_data, packet_id, from_node, psk):
    """Déchiffre un message Meshtastic chiffré avec ChaCha20-Poly1305"""
    try:
        # Construction du nonce (96 bits = 12 octets)
        # Format: packet_id (32 bits) + from_node (32 bits) + padding (32 bits = 0)
        nonce = packet_id.to_bytes(8, 'little') + from_node.to_bytes(4, 'little')
        
        cipher = ChaCha20Poly1305(psk)
        decrypted = cipher.decrypt(nonce, encrypted_data, None)
        return decrypted
    except Exception as e:
        print(f"❌ Erreur de déchiffrement: {e}")
        return None

# ============ CALLBACK MQTT ============
def on_message(client, userdata, msg):
    print(f"\n{'='*60}")
    print(f"📨 Message sur {msg.topic}")
    print(f"Taille: {len(msg.payload)} octets")
    
    try:
        # 1. Décoder le ServiceEnvelope
        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.ParseFromString(msg.payload)
        
        if not envelope.HasField("packet"):
            print("⚠️ Pas de paquet MeshPacket")
            return
        
        mesh_packet = envelope.packet
        
        # 2. Afficher les infos du paquet
        from_id = getattr(mesh_packet, 'from_', getattr(mesh_packet, 'from'))
        to_id = mesh_packet.to
        packet_id = mesh_packet.id
 
        print(f"De: !{from_id:08x}, Vers: !{to_id:08x}")
        print(f"ID: {packet_id}, Canal: {envelope.channel_id}, Hop: {mesh_packet.hop_limit}")
        
        # 3. Vérifier le type de payload
        payload_type = mesh_packet.WhichOneof("payload_variant")
        print(f"Type: {payload_type}")
        
        if payload_type == "decoded":
            # ===== MESSAGE DÉCHIFFRÉ =====
            data = mesh_packet.decoded
            portnum = data.portnum
            
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
            print(f"🔒 Message chiffré ({len(encrypted_data)} octets)")
            
            # Tenter de déchiffrer
            decrypted = decrypt_message(encrypted_data, packet_id, from_id, PSK_KEY)
            
            if decrypted:
                # Décoder le Data déchiffré
                data = mesh_pb2.Data()
                data.ParseFromString(decrypted)
                
                if data.portnum == 1:  # Texte
                    text = data.payload.decode('utf-8', errors='replace')
                    print(f"🔓 Texte déchiffré: {text}")
                elif data.portnum == 3:  # Position
                    position = mesh_pb2.Position()
                    position.ParseFromString(data.payload)
                    lat = position.latitude_i / 1e7
                    lon = position.longitude_i / 1e7
                    print(f"🔓 Position déchiffrée: {lat:.6f}, {lon:.6f}")
                else:
                    print(f"🔓 Port {data.portnum}: {data.payload.hex()[:50]}...")
        
        else:
            print(f"⚠️ Type inconnu: {payload_type}")
    
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

# ============ CONNEXION MQTT ============
def on_connect(client, userdata, flags, rc, properties=None):
    print(f"✅ Connecté au broker (code {rc})")
    client.subscribe(MQTT_TOPIC)
    print(f"📡 Abonné à {MQTT_TOPIC}")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.on_connect = on_connect
client.on_message = on_message

print(f"Connexion à {MQTT_BROKER}:{MQTT_PORT}...")
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_forever()

