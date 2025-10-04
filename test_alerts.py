#!/usr/bin/env python3
"""
Script de test pour le système d'alertes Telegram
ATTENTION: Envoie de vraies alertes aux utilisateurs configurés!
"""

import sys
import time
import asyncio

# Import de la configuration
sys.path.insert(0, '/home/dietpi/bot')  # Ajustez selon votre installation
from config import *
from utils import *

def test_telegram_connection():
    """Test 1: Vérifier la connexion Telegram"""
    print("=" * 60)
    print("TEST 1: Connexion Telegram")
    print("=" * 60)
    
    try:
        from telegram_integration import TelegramIntegration, TELEGRAM_AVAILABLE
        
        if not TELEGRAM_AVAILABLE:
            print("❌ ÉCHEC: Module python-telegram-bot non installé")
            return False
        
        print(f"✅ Module Telegram disponible")
        print(f"📱 Token configuré: {'Oui' if TELEGRAM_BOT_TOKEN != 'YOUR_TELEGRAM_BOT_TOKEN' else 'Non'}")
        print(f"👥 Utilisateurs alertes: {TELEGRAM_ALERT_USERS if TELEGRAM_ALERT_USERS else TELEGRAM_AUTHORIZED_USERS}")
        
        return True
        
    except Exception as e:
        print(f"❌ ÉCHEC: {e}")
        return False

def test_temperature_reading():
    """Test 2: Lecture température CPU"""
    print("\n" + "=" * 60)
    print("TEST 2: Lecture Température CPU")
    print("=" * 60)
    
    try:
        import subprocess
        
        # Méthode 1: vcgencmd
        print("\n🔍 Tentative vcgencmd...")
        try:
            temp_cmd = ['vcgencmd', 'measure_temp']
            temp_result = subprocess.run(temp_cmd, 
                                       capture_output=True, 
                                       text=True, 
                                       timeout=5)
            
            if temp_result.returncode == 0:
                temp_output = temp_result.stdout.strip()
                if 'temp=' in temp_output:
                    temp_str = temp_output.split('=')[1].replace("'C", "")
                    temp_celsius = float(temp_str)
                    print(f"✅ vcgencmd: {temp_celsius}°C")
                    
                    # Vérifier les seuils
                    print(f"\n📊 Seuils configurés:")
                    print(f"   ⚠️  Warning: {TEMP_WARNING_THRESHOLD}°C")
                    print(f"   🔥 Critical: {TEMP_CRITICAL_THRESHOLD}°C")
                    
                    if temp_celsius >= TEMP_CRITICAL_THRESHOLD:
                        print(f"   🚨 STATUT: CRITIQUE!")
                    elif temp_celsius >= TEMP_WARNING_THRESHOLD:
                        print(f"   ⚠️  STATUT: Élevée")
                    else:
                        print(f"   ✅ STATUT: Normale")
                    
                    return True
        except Exception as e:
            print(f"⚠️  vcgencmd échoué: {e}")
        
        # Méthode 2: /sys/class/thermal
        print("\n🔍 Tentative /sys/class/thermal...")
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp_millis = int(f.read().strip())
                temp_celsius = temp_millis / 1000.0
                print(f"✅ thermal_zone0: {temp_celsius:.1f}°C")
                return True
        except Exception as e:
            print(f"❌ thermal_zone0 échoué: {e}")
        
        print("❌ ÉCHEC: Impossible de lire la température")
        return False
        
    except Exception as e:
        print(f"❌ ÉCHEC: {e}")
        return False

def test_tigrog2_connection():
    """Test 3: Connexion tigrog2"""
    print("\n" + "=" * 60)
    print("TEST 3: Connexion tigrog2")
    print("=" * 60)
    
    try:
        import meshtastic.tcp_interface
        
        print(f"\n🔍 Tentative connexion à {REMOTE_NODE_HOST}:4403...")
        
        try:
            remote_interface = meshtastic.tcp_interface.TCPInterface(
                hostname=REMOTE_NODE_HOST,
                portNumber=4403
            )
            
            time.sleep(3)
            
            # Vérifier la connexion
            if hasattr(remote_interface, 'localNode'):
                local_node = remote_interface.localNode
                node_num = getattr(local_node, 'nodeNum', 'Unknown')
                print(f"✅ Connecté à tigrog2")
                print(f"   📡 Node ID: {node_num:08x}" if isinstance(node_num, int) else f"   📡 Node: {node_num}")
            else:
                print(f"⚠️  Connecté mais localNode non disponible")
            
            remote_interface.close()
            print(f"✅ Connexion fermée proprement")
            return True
            
        except Exception as e:
            print(f"❌ ÉCHEC connexion: {e}")
            return False
            
    except Exception as e:
        print(f"❌ ÉCHEC: {e}")
        return False

def test_send_alert():
    """Test 4: Envoyer une alerte de test"""
    print("\n" + "=" * 60)
    print("TEST 4: Envoi Alerte Test")
    print("=" * 60)
    
    print("\n⚠️  ATTENTION: Ce test va envoyer une VRAIE alerte Telegram!")
    print(f"   Destinataires: {TELEGRAM_ALERT_USERS if TELEGRAM_ALERT_USERS else TELEGRAM_AUTHORIZED_USERS}")
    
    response = input("\n Voulez-vous continuer? (oui/non): ")
    if response.lower() not in ['oui', 'yes', 'o', 'y']:
        print("❌ Test annulé par l'utilisateur")
        return False
    
    try:
        print("\n🚀 Démarrage du bot Telegram...")
        
        # Créer une instance minimale pour le test
        from telegram_integration import TelegramIntegration
        
        # Mock des dépendances
        class MockHandler:
            pass
        
        class MockManager:
            pass
        
        telegram = TelegramIntegration(
            MockHandler(),
            MockManager(),
            MockManager()
        )
        
        print("✅ Instance Telegram créée")
        print("⏳ Démarrage (10 secondes)...")
        
        # Démarrer le bot
        telegram.start()
        time.sleep(10)
        
        # Envoyer l'alerte de test
        test_message = (
            "🧪 ALERTE TEST - Système de Monitoring\n\n"
            f"⏱️  Timestamp: {time.strftime('%H:%M:%S')}\n"
            f"📍 Source: Script de test\n"
            f"✅ Configuration:\n"
            f"   • Temp warning: {TEMP_WARNING_THRESHOLD}°C\n"
            f"   • Temp critical: {TEMP_CRITICAL_THRESHOLD}°C\n"
            f"   • tigrog2: {REMOTE_NODE_HOST}\n\n"
            "Si vous recevez ce message, le système d'alertes fonctionne correctement! ✅"
        )
        
        print(f"\n📤 Envoi de l'alerte...")
        telegram.send_alert(test_message)
        
        print("✅ Alerte envoyée")
        print("⏳ Attente envoi (5 secondes)...")
        time.sleep(5)
        
        # Arrêter le bot
        print("🛑 Arrêt du bot...")
        telegram.stop()
        time.sleep(2)
        
        print("\n✅ TEST RÉUSSI")
        print("📱 Vérifiez Telegram pour confirmer la réception")
        return True
        
    except Exception as e:
        print(f"❌ ÉCHEC: {e}")
        import traceback
        print(traceback.format_exc())
        return False

def main():
    """Exécuter tous les tests"""
    print("\n" + "=" * 60)
    print("🧪 SUITE DE TESTS - SYSTÈME D'ALERTES TELEGRAM")
    print("=" * 60)
    print(f"\n📋 Configuration:")
    print(f"   • Mode debug: {DEBUG_MODE}")
    print(f"   • Alertes temp: {TEMP_WARNING_ENABLED}")
    print(f"   • Alertes tigrog2: {TIGROG2_MONITORING_ENABLED}")
    
    results = {}
    
    # Test 1: Connexion Telegram
    results['telegram'] = test_telegram_connection()
    
    # Test 2: Température
    if TEMP_WARNING_ENABLED:
        results['temperature'] = test_temperature_reading()
    else:
        print("\n⚠️  SKIP: Alertes température désactivées")
        results['temperature'] = None
    
    # Test 3: tigrog2
    if TIGROG2_MONITORING_ENABLED:
        results['tigrog2'] = test_tigrog2_connection()
    else:
        print("\n⚠️  SKIP: Monitoring tigrog2 désactivé")
        results['tigrog2'] = None
    
    # Test 4: Envoi alerte (optionnel)
    if results['telegram']:
        results['alert'] = test_send_alert()
    else:
        print("\n⚠️  SKIP: Envoi alerte (Telegram non fonctionnel)")
        results['alert'] = None
    
    # Résumé
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ DES TESTS")
    print("=" * 60)
    
    for test_name, result in results.items():
        if result is None:
            status = "⊘  SKIP"
        elif result:
            status = "✅ OK"
        else:
            status = "❌ ÉCHEC"
        print(f"   {status} {test_name.capitalize()}")
    
    # Verdict final
    tested = [r for r in results.values() if r is not None]
    if tested and all(tested):
        print("\n✅ TOUS LES TESTS RÉUSSIS")
        return 0
    elif any(tested):
        print("\n⚠️  CERTAINS TESTS ONT ÉCHOUÉ")
        return 1
    else:
        print("\n❌ TOUS LES TESTS ONT ÉCHOUÉ")
        return 2

if __name__ == "__main__":
    sys.exit(main())
