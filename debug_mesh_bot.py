#!/usr/bin/env python3
"""
Bot Mesh Debug - Version simplifiée pour tester l'IA avec ESPHome
"""

import time
import requests
import threading
import argparse
import sys
import re
import socket
from datetime import datetime
import meshtastic
import meshtastic.serial_interface
from pubsub import pub

# Configuration
SERIAL_PORT = "/dev/ttyACM0"
LLAMA_HOST = "127.0.0.1"
LLAMA_PORT = 8080

# Configuration ESPHome
ESPHOME_HOST = "192.168.1.27"
ESPHOME_PORT = 80

# Variable globale pour le mode debug
DEBUG_MODE = False

def debug_print(message):
    """Affiche seulement en mode debug"""
    if DEBUG_MODE:
        print(f"[DEBUG] {message}", file=sys.stderr, flush=True)

def info_print(message):
    """Affiche toujours (logs importants)"""
    print(f"[INFO] {message}", flush=True)

def conversation_print(message):
    """Log spécial pour les conversations"""
    print(f"[CONVERSATION] {message}", flush=True)

def error_print(message):
    """Log d'erreur"""
    print(f"[ERROR] {message}", file=sys.stderr, flush=True)

class DebugMeshBot:
    def __init__(self):
        self.interface = None
        self.running = False
        
    def log_conversation(self, sender_id, sender_info, query, response, processing_time=None):
        """Log une conversation complète dans systemd journal"""
        try:
            conversation_print("=" * 60)
            conversation_print(f"USER: {sender_info}")
            conversation_print(f"QUERY: {query}")
            conversation_print(f"RESPONSE: {response}")
            if processing_time:
                conversation_print(f"PROCESSING_TIME: {processing_time:.2f}s")
            conversation_print(f"TIMESTAMP: {datetime.now().isoformat()}")
            conversation_print("=" * 60)
            
            debug_print("Conversation loggée dans systemd journal")
            
        except Exception as e:
            error_print(f"Erreur logging conversation: {e}")
    
    def get_sender_info(self, sender_id):
        """Obtient les infos du sender pour les logs"""
        sender_info = f"ID:{sender_id}"
        
        try:
            if hasattr(self.interface, 'nodes') and self.interface.nodes:
                node_info = self.interface.nodes.get(sender_id, {})
                user = node_info.get('user', {})
                if user.get('longName'):
                    sender_info = f"{user['longName']} ({sender_id})"
                elif user.get('shortName'):
                    sender_info = f"{user['shortName']} ({sender_id})"
        except Exception:
            pass
        
        return sender_info
        
    def test_llama(self):
        """Test du serveur llama"""
        try:
            debug_print("Test du serveur llama.cpp...")
            response = requests.get(f"http://{LLAMA_HOST}:{LLAMA_PORT}/health", timeout=3)
            if response.status_code == 200:
                info_print("Serveur llama.cpp connecté")
                return True
            else:
                info_print(f"Serveur llama.cpp répond avec code: {response.status_code}")
                return False
        except Exception as e:
            error_print(f"Serveur llama.cpp inaccessible: {e}")
            return False
    
    def clean_ai_response(self, content):
        """Nettoie la réponse de l'IA en supprimant les balises de réflexion"""
        try:
            debug_print(f"Contenu original avant nettoyage: '{content}'")
            
            # Supprimer seulement les balises de réflexion principales
            patterns_to_remove = [
                r'<think>.*?</think>',
                r'<thinking>.*?</thinking>'
            ]
            
            for pattern in patterns_to_remove:
                content = re.sub(pattern, '', content, flags=re.DOTALL | re.IGNORECASE)
            
            # Nettoyer les espaces multiples
            content = re.sub(r'\s+', ' ', content).strip()
            
            # Si vraiment vide, message simple
            if not content or len(content.strip()) < 2:
                content = "Pas de réponse"
            
            debug_print(f"Contenu après nettoyage: '{content}'")
            return content
            
        except Exception as e:
            debug_print(f"Erreur nettoyage: {e}")
            return content if content else "Erreur"
    
    def query_llama(self, prompt):
        """Requête au serveur llama avec API de chat et prompt système"""
        try:
            debug_print(f"Envoi à llama.cpp: '{prompt}'")
            
            data = {
                "messages": [
                    {
                        "role": "system",
                        "content": "Tu es un assistant accessible via le réseau Meshtastic en LoRa. Tu dois répondre en français de manière très courte, claire et efficace. Utilise seulement quelques mots ou phrases, avec un maximum de 200 caractères par réponse. Ne commence jamais ta réponse par des balises de réflexion."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 32000,
                "temperature": 0.6,
                "top_p": 0.95,
                "top_k": 20
            }
            
            debug_print(f"Messages envoyés: {len(data['messages'])} messages")
            
            start_time = time.time()
            
            # Timeout à 180s
            response = requests.post(f"http://{LLAMA_HOST}:{LLAMA_PORT}/v1/chat/completions", 
                                   json=data, timeout=180)
            end_time = time.time()
            
            debug_print(f"Temps de réponse: {end_time - start_time:.2f}s")
            debug_print(f"Code de réponse HTTP: {response.status_code}")
            
            if response.status_code != 200:
                error_print(f"Erreur HTTP: {response.text}")
                return "Erreur serveur"
            
            result = response.json()
            debug_print(f"Réponse brute: {result}")
            
            # Extraire le contenu de la réponse du chat
            if 'choices' in result and len(result['choices']) > 0:
                content = result['choices'][0]['message']['content'].strip()
            else:
                content = "Pas de réponse"
            
            # Nettoyer le contenu avec la nouvelle fonction
            content = self.clean_ai_response(content)
            
            return content
            
        except Exception as e:
            error_msg = f"Erreur IA: {str(e)}"
            error_print(error_msg)
            return error_msg
    
    def parse_esphome_data(self):
        """Parse l'interface ESPHome - Version optimisée basée sur tests"""
        import time
        
        try:
            debug_print("Récupération des données ESPHome...")
            
            # Test connectivité de base
            response = requests.get(f"http://{ESPHOME_HOST}/", timeout=5)
            if response.status_code != 200:
                return "ESPHome inaccessible"
            
            found_data = {}
            
            # Endpoints qui fonctionnent (trouvés lors des tests)
            working_endpoints = [
                '/sensor/bme280_temperature', '/sensor/bme280_pressure', 
                '/sensor/absolute_humidity', '/sensor/battery_voltage', 
                '/sensor/battery_current', '/sensor/panel_power', 
                '/sensor/panel_voltage', '/sensor/yield_today', 
                '/sensor/yield_total', '/sensor/max_power_today', 
                '/text_sensor/charging_mode', '/text_sensor/error'
            ]
            
            # Essayer aussi l'humidité relative (même si 404 dans le test précédent)
            working_endpoints.append('/sensor/bme280_humidity')
            working_endpoints.append('/sensor/bme280_relative_humidity')
            
            for endpoint in working_endpoints:
                try:
                    url = f"http://{ESPHOME_HOST}{endpoint}"
                    resp = requests.get(url, timeout=2)
                    if resp.status_code == 200:
                        data = resp.json()
                        if 'value' in data:
                            sensor_name = endpoint.split('/')[-1]
                            found_data[sensor_name] = data['value']
                except:
                    continue
            
            # Formatage pour Meshtastic avec données BME280 étendues
            if found_data:
                parts = []
                
                # Version 1: Priorité énergétique (batterie + production)
                energy_parts = []
                
                # Combiner tension et courant de batterie dans un format compact
                if 'battery_voltage' in found_data and 'battery_current' in found_data:
                    voltage = found_data['battery_voltage']
                    current = found_data['battery_current']
                    energy_parts.append(f"{voltage:.1f}V ({current:.2f}A)")
                elif 'battery_voltage' in found_data:
                    # Si seulement la tension est disponible
                    energy_parts.append(f"{found_data['battery_voltage']:.1f}V")
                elif 'battery_current' in found_data:
                    # Si seulement le courant est disponible
                    energy_parts.append(f"{found_data['battery_current']:.2f}A")
                
                if 'yield_today' in found_data:
                    energy_parts.append(f"Today:{found_data['yield_today']:.0f}Wh")
                
                # Version 2: Priorité météo (BME280 complet)
                weather_parts = []
                if 'bme280_temperature' in found_data:
                    weather_parts.append(f"T:{found_data['bme280_temperature']:.1f}C")
                if 'bme280_pressure' in found_data:
                    # Retirer "hPa" - la valeur ~1000 est reconnaissable
                    weather_parts.append(f"P:{found_data['bme280_pressure']:.0f}")
                
                # Pour l'humidité, essayer les différents noms possibles
                humidity_value = None
                for humidity_key in ['bme280_humidity', 'bme280_relative_humidity']:
                    if humidity_key in found_data:
                        humidity_value = found_data[humidity_key]
                        break
                
                if humidity_value is not None:
                    # Combiner humidité relative et absolue dans le même champ
                    humidity_str = f"H:{humidity_value:.0f}%"
                    if 'absolute_humidity' in found_data:
                        abs_hum = found_data['absolute_humidity']
                        humidity_str += f"({abs_hum:.1f}g/m³)"
                    weather_parts.append(humidity_str)
                
                # Stratégie de formatage intelligent (sans timestamp)
                # Essayer version complète d'abord
                all_parts = energy_parts + weather_parts
                full_result = " | ".join(all_parts)
                
                if len(full_result) <= 180:
                    # Tout rentre, parfait !
                    result = full_result
                    debug_print(f"Format complet: {result}")
                else:
                    # Trop long, versions alternatives
                    
                    # Version A: Énergie + température
                    temp_part = []
                    if 'bme280_temperature' in found_data:
                        temp_part = [f"T:{found_data['bme280_temperature']:.1f}C"]
                    version_a = energy_parts + temp_part
                    version_a_str = " | ".join(version_a)
                    
                    # Version B: Énergie + météo complet (avec humidité combinée)
                    version_b = energy_parts + weather_parts
                    version_b_str = " | ".join(version_b)
                    
                    # Version C: Météo complète + batterie simplifiée
                    battery_simple = []
                    if 'battery_voltage' in found_data:
                        battery_simple = [f"{found_data['battery_voltage']:.1f}V"]
                    version_c = battery_simple + weather_parts
                    version_c_str = " | ".join(version_c)
                    
                    # Choisir la meilleure version qui rentre
                    if len(version_b_str) <= 180:
                        result = version_b_str
                        debug_print(f"Format météo complet: {result}")
                    elif len(version_a_str) <= 180:
                        result = version_a_str
                        debug_print(f"Format énergie + température: {result}")
                    elif len(version_c_str) <= 180:
                        result = version_c_str
                        debug_print(f"Format météo + batterie: {result}")
                    else:
                        # Fallback: version la plus courte
                        voltage_part = []
                        if 'battery_voltage' in found_data:
                            voltage_part = [f"{found_data['battery_voltage']:.1f}V"]
                        temp_part = []
                        if 'bme280_temperature' in found_data:
                            temp_part = [f"T:{found_data['bme280_temperature']:.1f}C"]
                        short_parts = voltage_part + temp_part
                        result = " | ".join(short_parts)
                        debug_print(f"Format court: {result}")
                
                debug_print(f"Données ESPHome formatées ({len(result)} chars): {result}")
                return result[:180] if len(result) <= 180 else result[:177] + "..."
            else:
                return f"ESPHome Online"
                
        except Exception as e:
            error_print(f"Erreur ESPHome: {e}")
            return f"ESPHome Error: {str(e)[:30]}"
    
    def send_response_chunks(self, response, sender_id, sender_info):
        """Divise et envoie la réponse en plusieurs messages si nécessaire"""
        try:
            max_length = 180  # Limite pour Meshtastic
            
            if len(response) <= max_length:
                # Message court, envoi direct
                debug_print(f"ENVOI RÉPONSE PRIVÉE à {sender_id}: '{response}'")
                self.send_single_message(response, sender_id, sender_info)
            else:
                # Message long, diviser en chunks
                # Essayer de diviser aux points ou virgules d'abord
                sentences = re.split(r'[.!?]\s+', response)
                chunks = []
                current_chunk = ""
                
                for sentence in sentences:
                    if len(current_chunk + sentence) < max_length:
                        current_chunk += sentence + ". "
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = sentence + ". "
                
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
                # Si pas de phrases détectées, diviser brutalement
                if len(chunks) == 1 and len(chunks[0]) > max_length:
                    chunks = []
                    for i in range(0, len(response), max_length-20):
                        chunk = response[i:i+max_length-20]
                        if i + max_length-20 < len(response):
                            chunk += "..."
                        chunks.append(chunk)
                
                # Envoyer chaque chunk avec numérotation
                total_chunks = len(chunks)
                for i, chunk in enumerate(chunks, 1):
                    if total_chunks > 1:
                        formatted_chunk = f"({i}/{total_chunks}) {chunk}"
                    else:
                        formatted_chunk = chunk
                    
                    debug_print(f"ENVOI CHUNK {i}/{total_chunks} à {sender_id}: '{formatted_chunk}'")
                    self.send_single_message(formatted_chunk, sender_id, sender_info)
                    
                    # Délai entre les messages pour éviter la surcharge
                    if i < total_chunks:
                        time.sleep(2)
                        
        except Exception as e:
            error_print(f"Erreur division réponse: {e}")
            # Fallback: envoyer tronqué
            fallback = response[:max_length-3] + "..."
            self.send_single_message(fallback, sender_id, sender_info)
    
    def send_single_message(self, message, sender_id, sender_info):
        """Envoie un seul message avec gestion d'erreur"""
        try:
            self.interface.sendText(message, destinationId=sender_id)
            info_print(f"Message envoyé à {sender_info}")
        except Exception as e1:
            debug_print(f"Méthode destinationId échouée: {e1}")
            try:
                self.interface.sendText(message, dest=sender_id)
                info_print(f"Message envoyé à {sender_info} (méthode alternative)")
            except Exception as e2:
                error_print(f"Impossible d'envoyer le message à {sender_info}: {e2}")
                conversation_print(f"ÉCHEC_ENVOI - USER: {sender_info} - MESSAGE: {message} - ERROR: {e2}")
    
    def format_timestamp(self):
        return datetime.now().strftime("%H:%M:%S")
    
    def on_message(self, packet, interface):
        """Gestionnaire des messages - Version debug avec messages privés uniquement"""
        try:
            # Filtrer silencieusement les paquets de télémétrie pour nettoyer les logs
            if 'decoded' in packet:
                portnum = packet['decoded'].get('portnum', '')
                if portnum in ['TELEMETRY_APP', 'NODEINFO_APP', 'POSITION_APP', 'ROUTING_APP']:
                    return  # Ignorer silencieusement ces paquets
            
            # Vérifier si c'est un message qui nous concerne
            to_id = packet.get('to', 0)
            from_id = packet.get('from', 0)
            my_id = None
            
            if hasattr(self.interface, 'localNode') and self.interface.localNode:
                my_id = getattr(self.interface.localNode, 'nodeNum', 0)
            
            # Filtrer: ne traiter que les messages pour nous ou de nous
            is_for_me = (to_id == my_id)
            is_from_me = (from_id == my_id)
            is_broadcast = (to_id == 0xFFFFFFFF or to_id == 0)
            
            # En mode debug, ne montrer que les packets qui nous concernent
            if DEBUG_MODE and not (is_for_me or is_from_me):
                return  # Ignorer silencieusement les autres packets
            
            debug_print(f"\n[{self.format_timestamp()}] PACKET REÇU:")
            debug_print(f"  From: {from_id}")
            debug_print(f"  To: {to_id}")
            debug_print(f"  PKI Encrypted: {packet.get('pkiEncrypted', False)}")
            debug_print(f"  Decoded: {'Oui' if 'decoded' in packet else 'Non'}")
            debug_print(f"  Mon ID: {my_id} (0x{my_id:08x})")
            
            # Vérifier si c'est un message privé
            is_private = is_for_me
            
            debug_print(f"  Message privé: {'Oui' if is_private else 'Non'}")
            debug_print(f"  Message public: {'Oui' if is_broadcast else 'Non'}")
            
            if 'decoded' not in packet:
                debug_print("  Message non décodé (crypté ou erreur)")
                return
            
            decoded = packet['decoded']
            portnum = decoded.get('portnum', '')
            debug_print(f"  Type: {portnum}")
            
            if portnum == 'TEXT_MESSAGE_APP':
                # Gérer les différents formats de message
                message = ""
                
                if 'text' in decoded:
                    message = decoded['text']
                elif 'payload' in decoded:
                    payload = decoded['payload']
                    if isinstance(payload, bytes):
                        try:
                            message = payload.decode('utf-8')
                        except UnicodeDecodeError:
                            message = payload.decode('utf-8', errors='replace')
                    else:
                        message = str(payload)
                
                sender_id = packet.get('from', 0)
                
                debug_print(f"  MESSAGE: '{message}'")
                debug_print(f"  SENDER: {sender_id}")
                
                # LOGIQUE: Traiter SEULEMENT les commandes /bot et /power en privé
                if message.startswith('/bot '):
                    if not is_private:
                        debug_print("  COMMANDE BOT IGNORÉE (message public)")
                        return
                    
                    prompt = message[5:].strip()
                    sender_info = self.get_sender_info(sender_id)
                    info_print(f"Commande reçue de {sender_info}: '{prompt}'")
                    
                    if prompt:
                        debug_print("  DÉBUT DU TRAITEMENT...")
                        
                        # Traiter avec l'IA et mesurer le temps
                        start_time = time.time()
                        response = self.query_llama(prompt)
                        end_time = time.time()
                        processing_time = end_time - start_time
                        
                        # Logger la conversation complète dans systemd journal
                        self.log_conversation(sender_id, sender_info, prompt, response, processing_time)
                        
                        # Diviser la réponse si elle est trop longue
                        self.send_response_chunks(response, sender_id, sender_info)
                            
                    else:
                        usage_msg = "Usage: /bot <question>"
                        self.interface.sendText(usage_msg, destinationId=sender_id)
                        
                elif message.startswith('/power'):
                    if not is_private:
                        debug_print("  COMMANDE POWER IGNORÉE (message public)")
                        return
                    
                    sender_info = self.get_sender_info(sender_id)
                    info_print(f"Commande power reçue de {sender_info}")
                    
                    debug_print("  DÉBUT RÉCUPÉRATION ESPHome...")
                    
                    # Récupérer les données ESPHome
                    esphome_data = self.parse_esphome_data()
                    
                    # Logger la commande
                    self.log_conversation(sender_id, sender_info, "/power", esphome_data)
                    
                    # Diviser la réponse si elle est trop longue
                    self.send_response_chunks(esphome_data, sender_id, sender_info)
                    
                else:
                    debug_print(f"  Message normal: '{message}'")
            
        except Exception as e:
            error_print(f"Erreur traitement: {e}")
            if DEBUG_MODE:
                import traceback
                traceback.print_exc()
    
    def interactive_loop(self):
        """Boucle interactive simplifiée"""
        if not DEBUG_MODE:
            return
            
        while self.running:
            try:
                command = input(f"\n[{self.format_timestamp()}] > ")
                
                if command.lower() in ['quit', 'exit', 'q']:
                    self.running = False
                    break
                elif command.startswith('test '):
                    # Test direct de l'IA
                    prompt = command[5:]
                    info_print(f"TEST DIRECT LLAMA avec: '{prompt}'")
                    response = self.query_llama(prompt)
                    info_print(f"Résultat: {response}")
                elif command.startswith('bot '):
                    question = command[4:]
                    bot_command = f"/bot {question}"
                    info_print(f"Envoi via Meshtastic: '{bot_command}'")
                    self.interface.sendText(bot_command)
                elif command == 'power':
                    info_print("TEST ESPHome:")
                    data = self.parse_esphome_data()
                    info_print(f"Résultat: {data}")
                elif command == 'help':
                    print("Commandes:")
                    print("  test <prompt>  - Test direct llama.cpp")
                    print("  bot <question> - Via Meshtastic")
                    print("  power          - Test ESPHome")
                    print("  quit           - Quitter")
                else:
                    print("Tapez 'help' pour l'aide")
                    
            except KeyboardInterrupt:
                self.running = False
                break
            except Exception as e:
                info_print(f"Erreur interactive: {e}")
    
    def start(self):
        """Démarrage"""
        info_print("Démarrage Bot Meshtastic-Llama")
        
        # Test llama
        if not self.test_llama():
            error_print("Impossible de continuer sans llama.cpp")
            return False
        
        try:
            info_print(f"Connexion à {SERIAL_PORT}...")
            self.interface = meshtastic.serial_interface.SerialInterface(SERIAL_PORT)
            time.sleep(3)
            
            info_print("Interface Meshtastic initialisée")
            
            # Utiliser pubsub au lieu de onReceive
            debug_print("Configuration pubsub...")
            pub.subscribe(self.on_message, "meshtastic.receive")
            
            self.running = True
            
            if DEBUG_MODE:
                info_print("MODE DEBUG ACTIF")
                print("\n" + "="*60)
                print("Commandes:")
                print("  test salut       - Test direct llama.cpp")
                print("  bot Bonjour IA   - Via Meshtastic + callback")
                print("  power            - Test ESPHome")
                print("  quit             - Quitter")
                print("="*60)
                
                # Thread interactif
                threading.Thread(target=self.interactive_loop, daemon=True).start()
            else:
                info_print("Bot en service - Écoute des commandes privées '/bot ...' et '/power'")
            
            # Boucle principale
            while self.running:
                time.sleep(1)
                
        except Exception as e:
            error_print(f"Erreur: {e}")
            if DEBUG_MODE:
                import traceback
                traceback.print_exc()
            return False
    
    def stop(self):
        info_print("Arrêt du bot...")
        self.running = False
        if self.interface:
            self.interface.close()
        info_print("Bot arrêté")

def main():
    global DEBUG_MODE
    
    # Parser les arguments
    parser = argparse.ArgumentParser(description='Bot Meshtastic-Llama')
    parser.add_argument('--debug', '-d', action='store_true', help='Mode debug verbose')
    parser.add_argument('--quiet', '-q', action='store_true', help='Mode silencieux (erreurs seulement)')
    args = parser.parse_args()
    
    DEBUG_MODE = args.debug
    
    if args.quiet:
        # Mode silencieux
        class QuietLogger:
            def write(self, msg):
                if 'ERROR' in msg or 'ERREUR' in msg:
                    sys.__stdout__.write(msg)
                    sys.__stdout__.flush()
            def flush(self):
                pass
        sys.stdout = QuietLogger()
    
    bot = DebugMeshBot()
    try:
        bot.start()
    except KeyboardInterrupt:
        if DEBUG_MODE:
            info_print("Interruption clavier")
    finally:
        bot.stop()

if __name__ == "__main__":
    main()
