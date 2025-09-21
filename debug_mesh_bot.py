#!/usr/bin/env python3
"""
Bot Mesh Debug - Version optimisée mémoire
"""

import time
import threading
import argparse
import sys
import gc
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

# Import paresseux pour économiser la mémoire
def lazy_import_requests():
    """Import requests seulement quand nécessaire"""
    global requests
    if 'requests' not in globals():
        import requests
    return requests

def lazy_import_re():
    """Import re seulement quand nécessaire"""
    global re
    if 're' not in globals():
        import re
    return re

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
        # Cache limité pour les réponses
        self._response_cache = {}
        self._max_cache_size = 5
        # Patterns compilés une seule fois
        self._clean_patterns = None
        
    def _get_clean_patterns(self):
        """Initialise les patterns regex une seule fois"""
        if self._clean_patterns is None:
            re_module = lazy_import_re()
            self._clean_patterns = [
                re_module.compile(r'<think>.*?</think>', re_module.DOTALL | re_module.IGNORECASE),
                re_module.compile(r'<thinking>.*?</thinking>', re_module.DOTALL | re_module.IGNORECASE)
            ]
        return self._clean_patterns
        
    def log_conversation(self, sender_id, sender_info, query, response, processing_time=None):
        """Log une conversation complète - version allégée"""
        try:
            conversation_print("=" * 40)
            conversation_print(f"USER: {sender_info}")
            conversation_print(f"QUERY: {query}")
            conversation_print(f"RESPONSE: {response}")
            if processing_time:
                conversation_print(f"TIME: {processing_time:.2f}s")
            conversation_print("=" * 40)
        except Exception as e:
            error_print(f"Erreur logging: {e}")
    
    def get_sender_info(self, sender_id):
        """Obtient les infos du sender - version simplifiée"""
        sender_info = f"ID:{sender_id}"
        try:
            if hasattr(self.interface, 'nodes') and self.interface.nodes:
                node_info = self.interface.nodes.get(sender_id, {})
                user = node_info.get('user', {})
                if user.get('longName'):
                    sender_info = f"{user['longName']}"
                elif user.get('shortName'):
                    sender_info = f"{user['shortName']}"
        except Exception:
            pass
        return sender_info
        
    def test_llama(self):
        """Test du serveur llama - version allégée"""
        try:
            requests_module = lazy_import_requests()
            response = requests_module.get(f"http://{LLAMA_HOST}:{LLAMA_PORT}/health", timeout=3)
            success = response.status_code == 200
            del response
            if success:
                info_print("Serveur llama.cpp connecté")
            return success
        except Exception as e:
            error_print(f"Serveur llama.cpp inaccessible: {e}")
            return False
    
    def clean_ai_response(self, content):
        """Nettoie la réponse de l'IA - version optimisée mémoire"""
        try:
            debug_print(f"Nettoyage: '{content[:50]}...'")
            
            patterns = self._get_clean_patterns()
            for pattern in patterns:
                content = pattern.sub('', content)
            
            # Nettoyage efficace des espaces
            content = ' '.join(content.split())
            
            if not content or len(content.strip()) < 2:
                content = "Pas de réponse"
                
            debug_print(f"Nettoyé: '{content[:50]}...'")
            return content
            
        except Exception as e:
            debug_print(f"Erreur nettoyage: {e}")
            return content if content else "Erreur"
    
    def query_llama(self, prompt):
        """Requête au serveur llama - version optimisée mémoire"""
        try:
            requests_module = lazy_import_requests()
            debug_print(f"Envoi à llama: '{prompt[:30]}...'")
            
            data = {
                "messages": [
                    {
                        "role": "system",
                        "content": "Réponds en français, très court, max 200 caractères."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 500,  # Réduit de 32000 à 500
                "temperature": 0.6,
                "top_p": 0.95,
                "top_k": 20
            }
            
            start_time = time.time()
            response = requests_module.post(f"http://{LLAMA_HOST}:{LLAMA_PORT}/v1/chat/completions", 
                                          json=data, timeout=60)
            end_time = time.time()
            
            debug_print(f"Temps: {end_time - start_time:.2f}s")
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content'].strip() if 'choices' in result else "Pas de réponse"
                
                # Libérer immédiatement
                del response, result, data
                gc.collect()
                
                return self.clean_ai_response(content)
            else:
                del response, data
                return "Erreur serveur"
                
        except Exception as e:
            error_msg = f"Erreur IA: {str(e)[:30]}"
            error_print(error_msg)
            return error_msg
    
    def parse_esphome_data(self):
        """Parse ESPHome - version optimisée mémoire"""
        try:
            requests_module = lazy_import_requests()
            debug_print("Récupération ESPHome...")
            
            # Test connectivité minimal
            response = requests_module.get(f"http://{ESPHOME_HOST}/", timeout=5)
            if response.status_code != 200:
                del response
                return "ESPHome inaccessible"
            del response
            
            found_data = {}
            
            # Endpoints essentiels seulement
            essential_endpoints = [
                '/sensor/battery_voltage', '/sensor/battery_current',
                '/sensor/yield_today', '/sensor/bme280_temperature',
                '/sensor/bme280_pressure', '/sensor/absolute_humidity',
                '/sensor/bme280_humidity', '/sensor/bme280_relative_humidity'
            ]
            
            # Traiter un par un pour limiter la mémoire
            for endpoint in essential_endpoints:
                try:
                    url = f"http://{ESPHOME_HOST}{endpoint}"
                    resp = requests_module.get(url, timeout=2)
                    if resp.status_code == 200:
                        data = resp.json()
                        if 'value' in data:
                            sensor_name = endpoint.split('/')[-1]
                            found_data[sensor_name] = data['value']
                        del data
                    del resp
                except:
                    continue
            
            # Formatage simplifié
            if found_data:
                parts = []
                
                # Batterie combinée
                if 'battery_voltage' in found_data and 'battery_current' in found_data:
                    parts.append(f"{found_data['battery_voltage']:.1f}V ({found_data['battery_current']:.2f}A)")
                elif 'battery_voltage' in found_data:
                    parts.append(f"{found_data['battery_voltage']:.1f}V")
                
                # Production
                if 'yield_today' in found_data:
                    parts.append(f"Today:{found_data['yield_today']:.0f}Wh")
                
                # Météo
                if 'bme280_temperature' in found_data:
                    parts.append(f"T:{found_data['bme280_temperature']:.1f}C")
                
                if 'bme280_pressure' in found_data:
                    parts.append(f"P:{found_data['bme280_pressure']:.0f}")
                
                # Humidité combinée : relative + absolue
                humidity_relative = None
                for humidity_key in ['bme280_humidity', 'bme280_relative_humidity']:
                    if humidity_key in found_data:
                        humidity_relative = found_data[humidity_key]
                        break
                
                if humidity_relative is not None:
                    humidity_str = f"H:{humidity_relative:.0f}%"
                    if 'absolute_humidity' in found_data:
                        abs_hum = found_data['absolute_humidity']
                        humidity_str += f"({abs_hum:.1f}g/m³)"
                    parts.append(humidity_str)
                
                result = " | ".join(parts[:5])
                
                # Nettoyer
                del found_data, parts
                gc.collect()
                
                debug_print(f"ESPHome: {result}")
                return result[:180] if len(result) <= 180 else result[:177] + "..."
            else:
                return "ESPHome Online"
                
        except Exception as e:
            error_print(f"Erreur ESPHome: {e}")
            return f"ESPHome Error: {str(e)[:30]}"
    
    def send_response_chunks(self, response, sender_id, sender_info):
        """Divise et envoie - version simplifiée"""
        try:
            max_length = 180
            
            if len(response) <= max_length:
                self.send_single_message(response, sender_id, sender_info)
            else:
                # Division simple
                chunks = []
                for i in range(0, len(response), max_length-20):
                    chunk = response[i:i+max_length-20]
                    if i + max_length-20 < len(response):
                        chunk += "..."
                    chunks.append(chunk)
                
                for i, chunk in enumerate(chunks, 1):
                    if len(chunks) > 1:
                        formatted_chunk = f"({i}/{len(chunks)}) {chunk}"
                    else:
                        formatted_chunk = chunk
                    
                    self.send_single_message(formatted_chunk, sender_id, sender_info)
                    if i < len(chunks):
                        time.sleep(2)
                        
        except Exception as e:
            error_print(f"Erreur division: {e}")
            fallback = response[:max_length-3] + "..."
            self.send_single_message(fallback, sender_id, sender_info)
    
    def send_single_message(self, message, sender_id, sender_info):
        """Envoie un message - version simplifiée"""
        try:
            self.interface.sendText(message, destinationId=sender_id)
            debug_print(f"Message → {sender_info}")
        except Exception as e1:
            try:
                self.interface.sendText(message, dest=sender_id)
                debug_print(f"Message → {sender_info} (alt)")
            except Exception as e2:
                error_print(f"Échec envoi → {sender_info}: {e2}")
    
    def cleanup_cache(self):
        """Nettoyage périodique"""
        if len(self._response_cache) > self._max_cache_size:
            items = list(self._response_cache.items())
            self._response_cache = dict(items[-3:])
        gc.collect()
    
    def format_timestamp(self):
        return datetime.now().strftime("%H:%M:%S")
    
    def on_message(self, packet, interface):
        """Gestionnaire des messages - version optimisée"""
        try:
            # Filtrer télémétrie
            if 'decoded' in packet:
                portnum = packet['decoded'].get('portnum', '')
                if portnum in ['TELEMETRY_APP', 'NODEINFO_APP', 'POSITION_APP', 'ROUTING_APP']:
                    return
            
            # Vérifier si message pour nous
            to_id = packet.get('to', 0)
            from_id = packet.get('from', 0)
            my_id = None
            
            if hasattr(self.interface, 'localNode') and self.interface.localNode:
                my_id = getattr(self.interface.localNode, 'nodeNum', 0)
            
            is_for_me = (to_id == my_id)
            is_from_me = (from_id == my_id)
            
            if DEBUG_MODE and not (is_for_me or is_from_me):
                return
            
            debug_print(f"Packet: From:{from_id} To:{to_id}")
            
            is_private = is_for_me
            
            if 'decoded' not in packet:
                return
            
            decoded = packet['decoded']
            portnum = decoded.get('portnum', '')
            
            if portnum == 'TEXT_MESSAGE_APP':
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
                debug_print(f"Message: '{message}' from {sender_id}")
                
                # Commandes
                if message.startswith('/bot '):
                    if not is_private:
                        return
                    
                    prompt = message[5:].strip()
                    sender_info = self.get_sender_info(sender_id)
                    info_print(f"Bot: {sender_info}: '{prompt}'")
                    
                    if prompt:
                        start_time = time.time()
                        response = self.query_llama(prompt)
                        end_time = time.time()
                        
                        self.log_conversation(sender_id, sender_info, prompt, response, end_time - start_time)
                        self.send_response_chunks(response, sender_id, sender_info)
                        
                        # Nettoyage après traitement
                        self.cleanup_cache()
                    else:
                        self.interface.sendText("Usage: /bot <question>", destinationId=sender_id)
                        
                elif message.startswith('/power'):
                    if not is_private:
                        return
                    
                    sender_info = self.get_sender_info(sender_id)
                    info_print(f"Power: {sender_info}")
                    
                    esphome_data = self.parse_esphome_data()
                    self.log_conversation(sender_id, sender_info, "/power", esphome_data)
                    self.send_response_chunks(esphome_data, sender_id, sender_info)
            
        except Exception as e:
            error_print(f"Erreur traitement: {e}")
    
    def interactive_loop(self):
        """Boucle interactive - version allégée"""
        if not DEBUG_MODE:
            return
            
        while self.running:
            try:
                command = input(f"\n[{self.format_timestamp()}] > ")
                
                if command.lower() in ['quit', 'exit', 'q']:
                    self.running = False
                    break
                elif command.startswith('test '):
                    prompt = command[5:]
                    info_print(f"TEST: '{prompt}'")
                    response = self.query_llama(prompt)
                    info_print(f"→ {response}")
                elif command.startswith('bot '):
                    question = command[4:]
                    bot_command = f"/bot {question}"
                    info_print(f"Envoi: '{bot_command}'")
                    self.interface.sendText(bot_command)
                elif command == 'power':
                    info_print("TEST ESPHome:")
                    data = self.parse_esphome_data()
                    info_print(f"→ {data}")
                elif command == 'mem':
                    # Commande de debug mémoire
                    try:
                        import psutil
                        import os
                        process = psutil.Process(os.getpid())
                        memory_mb = process.memory_info().rss / 1024 / 1024
                        info_print(f"Mémoire: {memory_mb:.1f}MB")
                    except:
                        info_print("psutil non disponible")
                elif command == 'help':
                    print("Commandes:")
                    print("  test <prompt>  - Test llama.cpp")
                    print("  bot <question> - Via Meshtastic")
                    print("  power          - Test ESPHome")
                    print("  mem            - Mémoire utilisée")
                    print("  quit           - Quitter")
                else:
                    print("Tapez 'help'")
                    
            except KeyboardInterrupt:
                self.running = False
                break
            except Exception as e:
                info_print(f"Erreur: {e}")
    
    def start(self):
        """Démarrage - version optimisée"""
        info_print("Bot Meshtastic-Llama (optimisé)")
        
        # Nettoyage initial
        gc.collect()
        
        if not self.test_llama():
            error_print("llama.cpp requis")
            return False
        
        try:
            info_print(f"Connexion {SERIAL_PORT}...")
            self.interface = meshtastic.serial_interface.SerialInterface(SERIAL_PORT)
            time.sleep(3)
            
            info_print("Interface Meshtastic OK")
            
            pub.subscribe(self.on_message, "meshtastic.receive")
            self.running = True
            
            if DEBUG_MODE:
                info_print("MODE DEBUG")
                print("\nCommandes: test, bot, power, mem, quit")
                threading.Thread(target=self.interactive_loop, daemon=True).start()
            else:
                info_print("Bot en service - '/bot' et '/power'")
            
            # Boucle principale avec nettoyage périodique
            cleanup_counter = 0
            while self.running:
                time.sleep(1)
                cleanup_counter += 1
                if cleanup_counter % 300 == 0:  # Toutes les 5 minutes
                    self.cleanup_cache()
                
        except Exception as e:
            error_print(f"Erreur: {e}")
            return False
    
    def stop(self):
        info_print("Arrêt...")
        self.running = False
        if self.interface:
            self.interface.close()
        gc.collect()
        info_print("Bot arrêté")

def main():
    global DEBUG_MODE
    
    parser = argparse.ArgumentParser(description='Bot Meshtastic-Llama')
    parser.add_argument('--debug', '-d', action='store_true', help='Mode debug')
    parser.add_argument('--quiet', '-q', action='store_true', help='Mode silencieux')
    args = parser.parse_args()
    
    DEBUG_MODE = args.debug
    
    if args.quiet:
        class QuietLogger:
            def write(self, msg):
                if 'ERROR' in msg:
                    sys.__stdout__.write(msg)
                    sys.__stdout__.flush()
            def flush(self):
                pass
        sys.stdout = QuietLogger()
    
    # Nettoyage initial
    gc.collect()
    
    bot = DebugMeshBot()
    try:
        bot.start()
    except KeyboardInterrupt:
        if DEBUG_MODE:
            info_print("Interruption")
    finally:
        bot.stop()

if __name__ == "__main__":
    main()
