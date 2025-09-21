#!/usr/bin/env python3
"""
Bot Mesh Debug - Version simplifiée pour tester l'IA
"""

import time
import requests
import threading
import re
from datetime import datetime
import meshtastic
import meshtastic.serial_interface
from pubsub import pub

# Configuration
SERIAL_PORT = "/dev/ttyACM0"
LLAMA_HOST = "127.0.0.1"
LLAMA_PORT = 8080

class DebugMeshBot:
    def __init__(self):
        self.interface = None
        self.running = False
        
    def test_llama(self):
        """Test du serveur llama"""
        try:
            print("🧪 Test du serveur llama.cpp...")
            response = requests.get(f"http://{LLAMA_HOST}:{LLAMA_PORT}/health", timeout=3)
            print(f"✅ Serveur répond avec code: {response.status_code}")
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Erreur connexion llama: {e}")
            return False
    
    def clean_ai_response(self, content):
        """Nettoie la réponse de l'IA en supprimant les balises de réflexion"""
        try:
            print(f"🔧 Contenu original avant nettoyage: '{content}'")
            
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
            
            print(f"✅ Contenu après nettoyage: '{content}'")
            return content
            
        except Exception as e:
            print(f"❌ Erreur nettoyage: {e}")
            return content if content else "Erreur"
    
    def query_llama(self, prompt):
        """Requête au serveur llama avec API de chat et prompt système"""
        try:
            print(f"🤖 Envoi à llama.cpp: '{prompt}'")
            
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
            
            print(f"📊 Messages envoyés: {len(data['messages'])} messages")
            
            start_time = time.time()
            
            # Augmenter le timeout à 180s
            response = requests.post(f"http://{LLAMA_HOST}:{LLAMA_PORT}/v1/chat/completions", 
                                   json=data, timeout=180)
            end_time = time.time()
            
            print(f"⏱️  Temps de réponse: {end_time - start_time:.2f}s")
            print(f"📈 Code de réponse HTTP: {response.status_code}")
            
            if response.status_code != 200:
                print(f"❌ Erreur HTTP: {response.text}")
                return "Erreur serveur"
            
            result = response.json()
            print(f"📄 Réponse brute: {result}")
            
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
            print(f"❌ {error_msg}")
            return error_msg
    
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
            
            print(f"\n[{self.format_timestamp()}] 📡 PACKET REÇU:")
            print(f"  From: {packet.get('from', 'N/A')}")
            print(f"  To: {packet.get('to', 'N/A')}")
            print(f"  PKI Encrypted: {packet.get('pkiEncrypted', False)}")
            print(f"  Decoded: {'Oui' if 'decoded' in packet else 'Non'}")
            
            # Vérifier si c'est un message privé (destiné à notre nœud)
            to_id = packet.get('to', 0)
            my_id = None
            
            if hasattr(self.interface, 'localNode') and self.interface.localNode:
                my_id = getattr(self.interface.localNode, 'nodeNum', 0)
                print(f"  Mon ID: {my_id} (0x{my_id:08x})")
            
            # Vérifier si c'est un message privé
            is_private = (to_id == my_id) if my_id else False
            is_broadcast = to_id == 0xFFFFFFFF or to_id == 0  # Adresses de broadcast communes
            
            print(f"  🔒 Message privé: {'Oui' if is_private else 'Non'}")
            print(f"  📢 Message public: {'Oui' if is_broadcast else 'Non'}")
            
            if 'decoded' not in packet:
                print("  ⚠️  Message non décodé (crypté ou erreur)")
                return
            
            decoded = packet['decoded']
            portnum = decoded.get('portnum', '')
            print(f"  Type: {portnum}")
            
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
                
                print(f"  💬 MESSAGE: '{message}'")
                print(f"  👤 SENDER: {sender_id}")
                
                # NOUVELLE LOGIQUE: Traiter SEULEMENT les commandes /bot en privé
                if message.startswith('/bot '):
                    if not is_private:
                        print(f"  🚫 COMMANDE BOT IGNORÉE (message public)")
                        print(f"  💡 Le bot ne répond qu'aux messages privés")
                        return
                    
                    prompt = message[5:].strip()
                    print(f"  🎯 COMMANDE BOT PRIVÉE DÉTECTÉE: '{prompt}'")
                    
                    if prompt:
                        print(f"  🚀 DÉBUT DU TRAITEMENT...")
                        
                        # Traiter avec l'IA
                        response = self.query_llama(prompt)
                        
                        # Limiter pour Meshtastic
                        if len(response) > 200:
                            response = response[:197] + "..."
                        
                        final_response = f"🤖 {response}"
                        
                        print(f"  📤 ENVOI RÉPONSE PRIVÉE à {sender_id}: '{final_response}'")
                        
                        # Tenter plusieurs méthodes pour l'envoi privé
                        try:
                            # Méthode 1: destinationId (nouvelle API)
                            self.interface.sendText(final_response, destinationId=sender_id)
                            print(f"  ✅ RÉPONSE PRIVÉE ENVOYÉE (méthode destinationId)")
                        except Exception as e1:
                            print(f"  ⚠️ Méthode destinationId échouée: {e1}")
                            try:
                                # Méthode 2: dest (ancienne API)  
                                self.interface.sendText(final_response, dest=sender_id)
                                print(f"  ✅ RÉPONSE PRIVÉE ENVOYÉE (méthode dest)")
                            except Exception as e2:
                                print(f"  ⚠️ Méthode dest échouée: {e2}")
                                try:
                                    # Méthode 3: Conversion en format hex
                                    hex_id = f"!{sender_id:08x}"
                                    self.interface.sendText(final_response, destinationId=hex_id)
                                    print(f"  ✅ RÉPONSE PRIVÉE ENVOYÉE (format hex: {hex_id})")
                                except Exception as e3:
                                    print(f"  ❌ Toutes les méthodes privées ont échoué: {e3}")
                                    print(f"  📢 Fallback: envoi public")
                                    self.interface.sendText(f"@{sender_id:08x} {final_response}")
                            
                        print(f"  ✅ Tentative d'envoi privé terminée")
                    else:
                        # Répondre en privé même pour l'usage
                        self.interface.sendText("Usage: /bot <question>", destinationId=sender_id)
                        
                elif message.startswith('/bot ') and not is_private:
                    print(f"  📢 Commande /bot publique ignorée")
                    
                else:
                    print(f"  📝 Message normal (pas /bot): '{message}'")
            
        except Exception as e:
            print(f"❌ Erreur traitement: {e}")
            import traceback
            traceback.print_exc()
    
    def interactive_loop(self):
        """Boucle interactive simplifiée"""
        while self.running:
            try:
                command = input(f"\n[{self.format_timestamp()}] > ")
                
                if command.lower() in ['quit', 'exit', 'q']:
                    self.running = False
                    break
                elif command.startswith('test '):
                    # Test direct de l'IA
                    prompt = command[5:]
                    print(f"🧪 TEST DIRECT LLAMA avec: '{prompt}'")
                    response = self.query_llama(prompt)
                    print(f"📋 Résultat: {response}")
                elif command.startswith('bot '):
                    question = command[4:]
                    bot_command = f"/bot {question}"
                    print(f"📤 Envoi via Meshtastic: '{bot_command}'")
                    self.interface.sendText(bot_command)
                elif command == 'help':
                    print("Commandes:")
                    print("  test <prompt>  - Test direct llama.cpp")
                    print("  bot <question> - Via Meshtastic")
                    print("  quit           - Quitter")
                else:
                    print("Tapez 'help' pour l'aide")
                    
            except KeyboardInterrupt:
                self.running = False
                break
            except Exception as e:
                print(f"Erreur interactive: {e}")
    
    def start(self):
        """Démarrage"""
        print("🚀 Bot Mesh Debug")
        
        # Test llama
        if not self.test_llama():
            print("❌ Impossible de continuer sans llama.cpp")
            return False
        
        try:
            print(f"🔌 Connexion à {SERIAL_PORT}...")
            self.interface = meshtastic.serial_interface.SerialInterface(SERIAL_PORT)
            time.sleep(3)
            
            print("✅ Interface Meshtastic OK")
            
            # Utiliser pubsub au lieu de onReceive
            print("📡 Configuration pubsub...")
            pub.subscribe(self.on_message, "meshtastic.receive")
            
            self.running = True
            
            print("\n" + "="*60)
            print("🎯 MODE DEBUG ACTIF")
            print("Commandes:")
            print("  test salut       - Test direct llama.cpp")
            print("  bot Bonjour IA   - Via Meshtastic + callback")
            print("  quit             - Quitter")
            print("="*60)
            
            # Thread interactif
            threading.Thread(target=self.interactive_loop, daemon=True).start()
            
            # Boucle principale
            while self.running:
                time.sleep(0.1)
                
        except Exception as e:
            print(f"❌ Erreur: {e}")
            return False
    
    def stop(self):
        print("ℹ️ Arrêt...")
        self.running = False
        if self.interface:
            self.interface.close()

def main():
    bot = DebugMeshBot()
    try:
        bot.start()
    except KeyboardInterrupt:
        pass
    finally:
        bot.stop()

if __name__ == "__main__":
    main()
