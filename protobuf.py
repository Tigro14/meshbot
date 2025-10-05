from meshtastic import mesh_pb2, mqtt_pb2, portnums_pb2
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
#from meshtastic.util import decode_text
import paho.mqtt.client as mqtt
import json

# Configuration MQTT (remplacez par votre broker)
MQTT_BROKER = "serveurperso.com"  # Ex: "localhost" ou "test.mosquitto.org"
MQTT_PORT = 1883
MQTT_USER = "meshdev" # Si authentification: "utilisateur"
MQTT_PASSWORD = "large4cats"  # Si authentification: "motdepasse"
#MQTT_TOPIC = "msh/2/#"  # Topic Meshtastic (tous les canaux)
MQTT_TOPIC = "msh/EU_868/2/e/MediumFast/#"  # Topic Meshtastic (tous les canaux)
# Clé du canal (à récupérer depuis votre configuration Meshtastic)
PSK_KEY = bytes.fromhex("1PG7OiApB1nwvP+rz05pAQ==")  # Exemple (base64 décodé)


# Callback quand un message est reçu
from meshtastic import mesh_pb2

from meshtastic import mesh_pb2, mqtt_pb2

def on_message(client, userdata, msg):
    print(f"\n--- Message sur {msg.topic} ---")
    print(f"Payload (hex): {msg.payload.hex()[:100]}...")  # Affiche les 100 premiers caractères
    
    try:
        # 1. Décoder le ServiceEnvelope (enveloppe MQTT)
        envelope = mqtt_pb2.ServiceEnvelope()
        envelope.ParseFromString(msg.payload)
        
        print(f"Canal: {envelope.channel_id}")
        print(f"Gateway ID: {envelope.gateway_id}")
        
        # 2. Extraire le MeshPacket
        if envelope.HasField("packet"):
            mesh_packet = envelope.packet
            
            # 3. Afficher les informations du paquet
            print(f"De: !{mesh_packet.from_:08x}, Vers: !{mesh_packet.to:08x}")
            print(f"ID: {mesh_packet.id}, Hop limit: {mesh_packet.hop_limit}")
            
            # 4. Vérifier le type de payload
            payload_type = mesh_packet.WhichOneof("payload_variant")
            print(f"Type de payload: {payload_type}")
            
            if payload_type == "decoded":
                # Message déchiffré
                data = mesh_packet.decoded
                portnum = data.portnum
                
                print(f"Port: {portnum}")
                
                # Traiter selon le type de données
                if portnum == 1:  # TEXT_MESSAGE_APP
                    try:
                        text = data.payload.decode('utf-8', errors='replace')
                        print(f"📝 Texte: {text}")
                    except:
                        print(f"Texte (hex): {data.payload.hex()}")
                
                elif portnum == 3:  # POSITION_APP
                    try:
                        position = mesh_pb2.Position()
                        position.ParseFromString(data.payload)
                        lat = position.latitude_i / 1e7
                        lon = position.longitude_i / 1e7
                        alt = position.altitude
                        print(f"📍 Position: lat={lat:.6f}, lon={lon:.6f}, alt={alt}m")
                    except Exception as e:
                        print(f"Erreur position: {e}")
                
                elif portnum == 4:  # NODEINFO_APP
                    try:
                        nodeinfo = mesh_pb2.User()
                        nodeinfo.ParseFromString(data.payload)
                        print(f"👤 Node: {nodeinfo.long_name} ({nodeinfo.short_name})")
                        print(f"   Hardware: {nodeinfo.hw_model}")
                    except Exception as e:
                        print(f"Erreur nodeinfo: {e}")
                
                elif portnum == 67:  # TELEMETRY_APP
                    try:
                        telemetry = mesh_pb2.Telemetry()
                        telemetry.ParseFromString(data.payload)
                        if telemetry.HasField("device_metrics"):
                            metrics = telemetry.device_metrics
                            print(f"🔋 Batterie: {metrics.battery_level}%, Voltage: {metrics.voltage}V")
                    except Exception as e:
                        print(f"Erreur télémétrie: {e}")
                
                else:
                    print(f"Port {portnum} non géré (payload: {data.payload.hex()[:50]}...)")
            
            elif payload_type == "encrypted":
                print("🔒 Message chiffré (clé requise)")
                print(f"   Encrypted bytes: {len(mesh_packet.encrypted)} octets")
            
            else:
                print(f"⚠️ Type de payload inconnu: {payload_type}")
        
        else:
            print("Pas de paquet MeshPacket dans l'enveloppe")
    
    except Exception as e:
        print(f"❌ Erreur de décodage: {e}")
        import traceback
        traceback.print_exc()


def decrypt_payload(encrypted_data, nonce, psk):
    cipher = ChaCha20Poly1305(psk)
    return cipher.decrypt(nonce, encrypted_data, None)

# Configuration du client MQTT
#client = mqtt.Client()
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)  # API moderne

if MQTT_USER and MQTT_PASSWORD:
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

client.on_message = on_message

# Connexion au broker
print(f"Connexion à {MQTT_BROKER}:{MQTT_PORT}...")
client.connect(MQTT_BROKER, MQTT_PORT, 60)

# Abonnement au topic Meshtastic
client.subscribe(MQTT_TOPIC)
print(f"Abonné à {MQTT_TOPIC}")

# Boucle principale pour écouter les messages
try:
    client.loop_forever()
except KeyboardInterrupt:
    print("Arrêt du client MQTT...")
    client.disconnect()

