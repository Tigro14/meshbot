#!/usr/bin/env python3
"""
Test de l'API native ESPHome (port 6053)
"""

import asyncio
import aioesphomeapi
import requests
import json
from datetime import datetime

# Configuration
ESPHOME_HOST = "192.168.1.27"
ESPHOME_PORT = 6053
API_KEY = "9KfuXXxUI+8z26N+dc1X5pFhgnKj6KA1d4matApCVAA="

async def test_native_api():
    """Test de l'API native ESPHome"""
    print("=" * 60)
    print("TEST API NATIVE ESPHome")
    print("=" * 60)
    
    try:
        # Créer une connexion à l'API native
        api = aioesphomeapi.APIClient(ESPHOME_HOST, ESPHOME_PORT, API_KEY)
        
        print(f"Connexion à {ESPHOME_HOST}:{ESPHOME_PORT}")
        
        # Se connecter
        await api.connect(login=True)
        print("✅ Connexion réussie à l'API native")
        
        # Récupérer les informations du device
        device_info = await api.device_info()
        print(f"Device: {device_info.name}")
        print(f"Version: {device_info.esphome_version}")
        
        # Lister toutes les entités
        entities = await api.list_entities_services()
        print(f"\nEntités trouvées: {len(entities[0])}")
        
        sensors_data = {}
        
        for entity in entities[0]:
            if hasattr(entity, 'name') and hasattr(entity, 'key'):
                entity_name = entity.name
                print(f"  - {entity_name} (Type: {type(entity).__name__})")
                
                # Récupérer l'état de l'entité
                try:
                    states = await api.subscribe_states(lambda state: None)
                    # Cette méthode nécessite une approche différente
                except:
                    pass
        
        await api.disconnect()
        
    except Exception as e:
        print(f"❌ Erreur API native: {e}")
        print("💡 L'API native nécessite la vraie clé de chiffrement")

def test_web_server_endpoints():
    """Test des endpoints du serveur web ESPHome"""
    print("\n" + "=" * 60)
    print("TEST ENDPOINTS WEB SERVER")
    print("=" * 60)
    
    # Avec l'interface moderne, essayons des endpoints spécifiques
    endpoints = [
        '/text_sensor',
        '/sensor', 
        '/binary_sensor',
        '/switch',
        '/light',
        '/fan',
        '/climate',
        '/cover',
        '/number',
        '/select',
        '/button'
    ]
    
    found_data = {}
    
    for endpoint in endpoints:
        try:
            url = f"http://{ESPHOME_HOST}/{endpoint.lstrip('/')}"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                print(f"✅ {endpoint}: {len(response.text)} caractères")
                
                # Essayer de parser en JSON
                try:
                    data = response.json()
                    if isinstance(data, dict):
                        for key, value in data.items():
                            if any(term in str(key).lower() for term in ['temp', 'voltage', 'current', 'power', 'humidity', 'pressure', 'bme', 'battery']):
                                found_data[f"{endpoint}_{key}"] = value
                                print(f"    🎯 {key}: {value}")
                except:
                    # Pas du JSON, chercher des patterns dans le texte
                    if any(term in response.text.lower() for term in ['bme280', 'battery', 'voltage', 'temperature']):
                        print(f"    📝 Contient des données utiles: {response.text[:100]}...")
            else:
                print(f"❌ {endpoint}: Code {response.status_code}")
                
        except Exception as e:
            print(f"❌ {endpoint}: {e}")
    
    return found_data

async def simple_state_reader():
    """Lecteur d'état simple pour ESPHome"""
    print("\n" + "=" * 60) 
    print("LECTEUR D'ÉTAT SIMPLE")
    print("=" * 60)
    
    # SANS clé de chiffrement - juste pour tester la connectivité
    try:
        api = aioesphomeapi.APIClient(ESPHOME_HOST, ESPHOME_PORT, "")
        await api.connect(login=False)  # Sans authentification
        
        device_info = await api.device_info()
        print(f"Device accessible: {device_info.name}")
        
        await api.disconnect()
        
    except Exception as e:
        print(f"Connexion impossible sans authentification: {e}")

def main():
    print("TEST COMPLET ESPHome API")
    print(f"Host: {ESPHOME_HOST}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test des endpoints web
    web_data = test_web_server_endpoints()
    
    if web_data:
        print(f"\n📊 Données trouvées via web: {len(web_data)}")
        for key, value in web_data.items():
            print(f"  {key}: {value}")
    
    # Test API native (nécessite la vraie clé)
    print(f"\n💡 Pour tester l'API native, remplacez API_KEY par votre vraie clé")
    print(f"💡 Installation requise: pip install aioesphomeapi")
    
    # Essayer quand même sans auth
    try:
        asyncio.run(simple_state_reader())
    except ImportError:
        print("❌ aioesphomeapi non installé")
        print("   Installez avec: pip install aioesphomeapi")
    except Exception as e:
        print(f"❌ Test API native échoué: {e}")

if __name__ == "__main__":
    main()
