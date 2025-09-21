#!/usr/bin/env python3
"""
Test exhaustif des endpoints ESPHome pour récupérer les vraies données
"""

import requests
import json
import time
from datetime import datetime

# Configuration
ESPHOME_HOST = "192.168.1.27"
ESPHOME_PORT = 80

def test_basic_endpoints():
    """Test des endpoints de base ESPHome"""
    print("=" * 60)
    print("TEST ENDPOINTS DE BASE")
    print("=" * 60)
    
    basic_endpoints = [
        '/',
        '/api',
        '/api/info', 
        '/api/status',
        '/status',
        '/info',
        '/sensors',
        '/entities'
    ]
    
    for endpoint in basic_endpoints:
        try:
            url = f"http://{ESPHOME_HOST}:{ESPHOME_PORT}{endpoint}"
            response = requests.get(url, timeout=5)
            
            print(f"\n{endpoint}:")
            print(f"  Code: {response.status_code}")
            print(f"  Taille: {len(response.text)} chars")
            
            if response.status_code == 200:
                # Essayer de parser en JSON
                try:
                    data = response.json()
                    print(f"  JSON: Oui ({type(data).__name__})")
                    
                    if isinstance(data, dict):
                        keys = list(data.keys())[:5]
                        print(f"  Clés: {keys}")
                    elif isinstance(data, list) and data:
                        print(f"  Liste de {len(data)} éléments")
                        print(f"  Premier: {data[0]}")
                        
                except json.JSONDecodeError:
                    print(f"  JSON: Non")
                    # Afficher un extrait du contenu
                    preview = response.text[:150].replace('\n', ' ')
                    print(f"  Contenu: {preview}...")
                    
        except Exception as e:
            print(f"\n{endpoint}: Erreur - {e}")

def test_sensor_endpoints():
    """Test des endpoints spécifiques aux capteurs"""
    print("\n" + "=" * 60)
    print("TEST ENDPOINTS CAPTEURS SPÉCIFIQUES")
    print("=" * 60)
    
    # Basé sur votre configuration YAML
    sensor_endpoints = [
        # Capteurs BME280
        '/sensor/bme280_temperature',
        '/sensor/bme280_pressure', 
        '/sensor/bme280_humidity',
        '/sensor/absolute_humidity',
        
        # Capteurs Victron
        '/sensor/battery_voltage',
        '/sensor/battery_current',
        '/sensor/panel_power',
        '/sensor/panel_voltage',
        '/sensor/yield_today',
        '/sensor/yield_total',
        '/sensor/max_power_today',
        
        # Text sensors Victron
        '/text_sensor/charging_mode',
        '/text_sensor/error',
        '/text_sensor/device_type',
        '/text_sensor/device_mode',
        
        # Variations possibles
        '/sensor',
        '/text_sensor',
        '/bme280_temperature',
        '/battery_voltage'
    ]
    
    found_data = {}
    
    for endpoint in sensor_endpoints:
        try:
            url = f"http://{ESPHOME_HOST}:{ESPHOME_PORT}{endpoint}"
            response = requests.get(url, timeout=3)
            
            if response.status_code == 200:
                print(f"\n✅ {endpoint}: Réponse OK")
                
                try:
                    data = response.json()
                    print(f"  JSON: {data}")
                    
                    # Extraire la valeur si possible
                    value = None
                    if isinstance(data, dict):
                        if 'value' in data:
                            value = data['value']
                        elif 'state' in data:
                            value = data['state']
                        elif 'current_value' in data:
                            value = data['current_value']
                    
                    if value is not None:
                        sensor_name = endpoint.split('/')[-1]
                        found_data[sensor_name] = value
                        print(f"  🎯 VALEUR TROUVÉE: {value}")
                    
                except json.JSONDecodeError:
                    print(f"  Contenu texte: {response.text[:100]}")
                    
            else:
                print(f"❌ {endpoint}: Code {response.status_code}")
                
        except Exception as e:
            print(f"❌ {endpoint}: {e}")
    
    return found_data

def test_alternative_formats():
    """Test de formats d'URL alternatifs"""
    print("\n" + "=" * 60)
    print("TEST FORMATS ALTERNATIFS")
    print("=" * 60)
    
    # Essayer différents formats d'URL
    test_sensor = "battery_voltage"  # Un capteur qu'on sait exister
    
    url_formats = [
        f'/sensor/{test_sensor}',
        f'/sensor/{test_sensor}/state',
        f'/sensor/{test_sensor}/value', 
        f'/api/sensor/{test_sensor}',
        f'/api/states/{test_sensor}',
        f'/{test_sensor}',
        f'/{test_sensor}/state',
        f'/state/{test_sensor}',
        f'/entities/{test_sensor}'
    ]
    
    for url_format in url_formats:
        try:
            url = f"http://{ESPHOME_HOST}:{ESPHOME_PORT}{url_format}"
            response = requests.get(url, timeout=3)
            
            if response.status_code == 200:
                print(f"✅ {url_format}: OK")
                try:
                    data = response.json()
                    print(f"  Données: {data}")
                except:
                    print(f"  Texte: {response.text[:50]}")
            elif response.status_code != 404:  # Ne pas afficher les 404
                print(f"⚠️ {url_format}: Code {response.status_code}")
                
        except:
            continue

def test_bulk_endpoints():
    """Test des endpoints qui retournent plusieurs capteurs"""
    print("\n" + "=" * 60)
    print("TEST ENDPOINTS GROUPÉS")
    print("=" * 60)
    
    bulk_endpoints = [
        '/api/states',
        '/api/sensors', 
        '/states',
        '/sensors',
        '/all',
        '/data',
        '/json',
        '/export'
    ]
    
    for endpoint in bulk_endpoints:
        try:
            url = f"http://{ESPHOME_HOST}:{ESPHOME_PORT}{endpoint}"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                print(f"\n✅ {endpoint}: Réponse OK ({len(response.text)} chars)")
                
                try:
                    data = response.json()
                    print(f"  Type: {type(data).__name__}")
                    
                    if isinstance(data, dict):
                        print(f"  Clés: {list(data.keys())[:10]}")
                        
                        # Chercher des valeurs intéressantes
                        for key, value in data.items():
                            if any(term in str(key).lower() for term in ['battery', 'voltage', 'temperature', 'power']):
                                print(f"    🎯 {key}: {value}")
                                
                    elif isinstance(data, list):
                        print(f"  Liste de {len(data)} éléments")
                        if data:
                            print(f"  Premier élément: {data[0]}")
                            
                except json.JSONDecodeError:
                    # Chercher des patterns dans le texte
                    text = response.text
                    if any(term in text.lower() for term in ['battery', 'voltage', 'temperature']):
                        print(f"  Contient des données capteurs")
                        lines = text.split('\n')[:5]
                        for line in lines:
                            if line.strip():
                                print(f"    {line[:80]}")
                                
        except Exception as e:
            print(f"❌ {endpoint}: {e}")

def format_meshtastic_message(found_data):
    """Formate les données trouvées pour Meshtastic"""
    print("\n" + "=" * 60)
    print("FORMATAGE POUR MESHTASTIC")
    print("=" * 60)
    
    if not found_data:
        print("Aucune donnée à formater")
        return "ESPHome: Aucune donnée"
    
    print(f"Données trouvées: {len(found_data)}")
    for key, value in found_data.items():
        print(f"  {key}: {value}")
    
    # Priorités pour le formatage
    priority_mapping = {
        'battery_voltage': ('Bat', 'V'),
        'battery_current': ('Cur', 'A'),
        'panel_power': ('Sol', 'W'),
        'yield_today': ('Today', 'Wh'),
        'bme280_temperature': ('Temp', 'C'),
        'charging_mode': ('Mode', ''),
        'error': ('Err', '')
    }
    
    parts = []
    for sensor, (short_name, unit) in priority_mapping.items():
        if sensor in found_data:
            value = found_data[sensor]
            if isinstance(value, (int, float)):
                if unit == 'V':
                    formatted = f"{short_name}:{value:.1f}{unit}"
                elif unit == 'A':
                    formatted = f"{short_name}:{value:.2f}{unit}"
                elif unit in ['W', 'Wh']:
                    formatted = f"{short_name}:{value:.0f}{unit}"
                elif unit == 'C':
                    formatted = f"{short_name}:{value:.1f}{unit}"
                else:
                    formatted = f"{short_name}:{value}"
            else:
                # Text sensors
                text_value = str(value)[:8]  # Limiter la longueur
                formatted = f"{short_name}:{text_value}"
            
            parts.append(formatted)
            
            if len(parts) >= 4:  # Limite pour Meshtastic
                break
    
    # Ajouter timestamp
    current_time = time.strftime("%H:%M")
    parts.append(current_time)
    
    result = " | ".join(parts)
    
    # Vérifier la limite Meshtastic
    if len(result) > 180:
        result = result[:177] + "..."
    
    print(f"\nMessage final ({len(result)} caractères):")
    print(f"⚡ {result}")
    
    return result

def generate_bot_function(found_data):
    """Génère la fonction pour le bot basée sur les données trouvées"""
    print("\n" + "=" * 60)
    print("FONCTION POUR LE BOT")
    print("=" * 60)
    
    if not found_data:
        print("Aucune donnée trouvée - fonction de base recommandée")
        return
    
    # Identifier les endpoints qui fonctionnent
    working_endpoints = []
    for sensor in found_data.keys():
        working_endpoints.append(f'/sensor/{sensor}')
    
    function_code = f'''def parse_esphome_data(self):
    """Parse l'interface ESPHome - Version optimisée basée sur tests"""
    import time
    
    try:
        # Test connectivité de base
        response = requests.get(f"http://{ESPHOME_HOST}/", timeout=5)
        if response.status_code != 200:
            return "ESPHome inaccessible"
        
        found_data = {{}}
        
        # Endpoints qui fonctionnent (trouvés lors des tests)
        working_endpoints = {working_endpoints}
        
        for endpoint in working_endpoints:
            try:
                url = f"http://{ESPHOME_HOST}{{endpoint}}"
                resp = requests.get(url, timeout=2)
                if resp.status_code == 200:
                    data = resp.json()
                    if 'value' in data:
                        sensor_name = endpoint.split('/')[-1]
                        found_data[sensor_name] = data['value']
            except:
                continue
        
        # Formatage pour Meshtastic
        if found_data:
            parts = []
            
            # Priorités
            if 'battery_voltage' in found_data:
                parts.append(f"Bat:{{found_data['battery_voltage']:.1f}}V")
            if 'battery_current' in found_data:
                parts.append(f"Cur:{{found_data['battery_current']:.2f}}A")
            if 'panel_power' in found_data:
                parts.append(f"Sol:{{found_data['panel_power']:.0f}}W")
            if 'yield_today' in found_data:
                parts.append(f"Today:{{found_data['yield_today']:.0f}}Wh")
            if 'bme280_temperature' in found_data:
                parts.append(f"T:{{found_data['bme280_temperature']:.1f}}C")
            
            current_time = time.strftime("%H:%M")
            parts.append(current_time)
            
            result = " | ".join(parts[:5])
            return result[:180] if len(result) <= 180 else result[:177] + "..."
        else:
            return f"ESPHome Online | {{time.strftime('%H:%M')}}"
            
    except Exception as e:
        return f"ESPHome Error: {{str(e)[:30]}}"'''
    
    print("Fonction optimisée:")
    print("-" * 40)
    print(function_code)

def main():
    print("TEST EXHAUSTIF DES ENDPOINTS ESPHome")
    print(f"Host: {ESPHOME_HOST}:{ESPHOME_PORT}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Tests des différents endpoints
    test_basic_endpoints()
    found_sensor_data = test_sensor_endpoints()
    test_alternative_formats()
    test_bulk_endpoints()
    
    # Formatage final
    if found_sensor_data:
        formatted_message = format_meshtastic_message(found_sensor_data)
        generate_bot_function(found_sensor_data)
    else:
        print("\n❌ Aucune donnée de capteur trouvée")
        print("💡 Recommandation: utiliser une fonction de connectivité de base")

if __name__ == "__main__":
    main()
