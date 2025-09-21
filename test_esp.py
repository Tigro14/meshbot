#!/usr/bin/env python3
"""
Script de test pour récupération des données ESPHome - Version ciblée
"""

import requests
import json
import re
from bs4 import BeautifulSoup
from datetime import datetime

# Configuration
ESPHOME_HOST = "192.168.1.27"
ESPHOME_PORT = 80

def extract_esphome_table_data(html_content):
    """Extraction spécifique du tableau ESPHome Name/State"""
    print("=" * 60)
    print("EXTRACTION DU TABLEAU ESPHome")
    print("=" * 60)
    
    soup = BeautifulSoup(html_content, 'html.parser')
    sensors_data = {}
    
    # Chercher la table avec les colonnes Name/State
    tables = soup.find_all('table')
    print(f"Nombre de tables trouvées: {len(tables)}")
    
    for i, table in enumerate(tables):
        print(f"\nAnalyse de la table {i+1}:")
        
        rows = table.find_all('tr')
        if not rows:
            continue
            
        # Vérifier si c'est la bonne table (headers Name/State)
        header_row = rows[0]
        headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
        print(f"  Headers: {headers}")
        
        # Chercher les colonnes Name et State
        name_col = -1
        state_col = -1
        
        for idx, header in enumerate(headers):
            if header.lower() in ['name', 'nom']:
                name_col = idx
            elif header.lower() in ['state', 'value', 'valeur', 'état']:
                state_col = idx
        
        if name_col >= 0 and state_col >= 0:
            print(f"  ✅ Table correspondante trouvée! Name={name_col}, State={state_col}")
            
            # Extraire les données
            for row_idx, row in enumerate(rows[1:], 1):  # Skip header
                cells = row.find_all(['td', 'th'])
                
                if len(cells) > max(name_col, state_col):
                    name = cells[name_col].get_text(strip=True)
                    state = cells[state_col].get_text(strip=True)
                    
                    if name and state:
                        sensors_data[name] = state
                        print(f"    {name}: {state}")
            
            print(f"  Total extraits: {len(sensors_data)} capteurs")
            break
        else:
            print(f"  ❌ Table non correspondante")
    
    return sensors_data

def prioritize_and_format_data(sensors_data):
    """Priorise et formate les données pour Meshtastic"""
    print("\n" + "=" * 60)
    print("FORMATAGE POUR MESHTASTIC")
    print("=" * 60)
    
    if not sensors_data:
        return "Aucune donnée ESPHome"
    
    # Définir les priorités basées sur vos données
    priority_groups = {
        'battery': ['battery voltage', 'battery current'],
        'solar': ['panel power', 'yield today', 'max power today'],
        'environment': ['BME280 Temperature', 'BME280 Relative Humidity', 'BME280 Pressure'],
        'system': ['charging mode', 'error']
    }
    
    # Créer différents formats selon le contexte
    formats = {}
    
    # Format 1: Batterie + Solaire (priorité haute)
    battery_solar = []
    for key, value in sensors_data.items():
        if any(keyword in key.lower() for keyword in ['battery voltage', 'battery current', 'panel power', 'yield today']):
            clean_name = key.replace('battery ', '').replace('BME280 ', '')
            battery_solar.append(f"{clean_name}: {value}")
    
    if battery_solar:
        formats['battery_solar'] = " | ".join(battery_solar[:4])
    
    # Format 2: Environnement
    environment = []
    for key, value in sensors_data.items():
        if 'BME280' in key:
            clean_name = key.replace('BME280 ', '')
            if 'Temperature' in clean_name:
                clean_name = 'Temp'
            elif 'Relative Humidity' in clean_name:
                clean_name = 'Humid'
            elif 'Pressure' in clean_name:
                clean_name = 'Press'
            environment.append(f"{clean_name}: {value}")
    
    if environment:
        formats['environment'] = " | ".join(environment)
    
    # Format 3: Résumé compact (tout en un)
    important_keys = [
        'battery voltage', 'panel power', 'yield today', 
        'BME280 Temperature', 'charging mode'
    ]
    
    compact = []
    for key in important_keys:
        if key in sensors_data:
            value = sensors_data[key]
            if 'battery voltage' in key:
                compact.append(f"Bat: {value}")
            elif 'panel power' in key:
                compact.append(f"Solar: {value}")
            elif 'yield today' in key:
                compact.append(f"Today: {value}")
            elif 'BME280 Temperature' in key:
                compact.append(f"Temp: {value}")
            elif 'charging mode' in key:
                compact.append(f"Mode: {value}")
    
    if compact:
        formats['compact'] = " | ".join(compact)
    
    # Afficher tous les formats
    print("Formats disponibles:")
    for format_name, format_text in formats.items():
        length = len(format_text)
        status = "✅" if length <= 180 else f"❌ ({length} chars)"
        print(f"\n{format_name.upper()} {status}:")
        print(f"  {format_text}")
    
    # Retourner le meilleur format
    best_format = formats.get('compact', formats.get('battery_solar', 'Aucune donnée'))
    
    if len(best_format) > 180:
        best_format = best_format[:177] + "..."
    
    return best_format

def test_esphome_extraction():
    """Test complet d'extraction"""
    print("TEST D'EXTRACTION ESPHome")
    print(f"Host: {ESPHOME_HOST}:{ESPHOME_PORT}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Récupérer la page
        print(f"\nConnexion à http://{ESPHOME_HOST}:{ESPHOME_PORT}/")
        response = requests.get(f"http://{ESPHOME_HOST}:{ESPHOME_PORT}/", timeout=10)
        
        if response.status_code != 200:
            print(f"❌ Erreur HTTP: {response.status_code}")
            return
        
        print(f"✅ Connexion réussie ({len(response.text)} caractères)")
        
        # Extraire les données
        sensors_data = extract_esphome_table_data(response.text)
        
        if sensors_data:
            print(f"\n📊 DONNÉES EXTRAITES ({len(sensors_data)} capteurs):")
            for name, value in sensors_data.items():
                print(f"  {name}: {value}")
            
            # Formater pour Meshtastic
            final_message = prioritize_and_format_data(sensors_data)
            
            print(f"\n🚀 MESSAGE FINAL POUR MESHTASTIC:")
            print(f"⚡ {final_message}")
            print(f"📏 Longueur: {len(final_message)} caractères")
            
        else:
            print("❌ Aucune donnée extraite")
            
    except Exception as e:
        print(f"❌ Erreur: {e}")

# Fonction utilisable dans votre bot
def get_esphome_power_data():
    """Fonction simplifiée pour intégration dans le bot"""
    try:
        response = requests.get(f"http://{ESPHOME_HOST}:{ESPHOME_PORT}/", timeout=10)
        
        if response.status_code != 200:
            return "ESPHome inaccessible"
        
        soup = BeautifulSoup(response.text, 'html.parser')
        sensors_data = {}
        
        # Extraction du tableau Name/State
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            if not rows:
                continue
                
            headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(['th', 'td'])]
            
            if 'name' in headers and 'state' in headers:
                name_col = headers.index('name')
                state_col = headers.index('state')
                
                for row in rows[1:]:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) > max(name_col, state_col):
                        name = cells[name_col].get_text(strip=True)
                        state = cells[state_col].get_text(strip=True)
                        if name and state:
                            sensors_data[name] = state
                break
        
        # Formatage compact
        important = []
        key_mapping = {
            'battery voltage': 'Bat',
            'panel power': 'Solar', 
            'yield today': 'Today',
            'BME280 Temperature': 'Temp',
            'charging mode': 'Mode'
        }
        
        for full_key, short_key in key_mapping.items():
            if full_key in sensors_data:
                important.append(f"{short_key}: {sensors_data[full_key]}")
        
        result = " | ".join(important[:5])
        return result[:180] if len(result) <= 180 else result[:177] + "..."
        
    except Exception as e:
        return f"Erreur ESPHome: {str(e)[:50]}"

if __name__ == "__main__":
    # Test autonome
    test_esphome_extraction()
    
    # Test de la fonction pour le bot
    print("\n" + "=" * 60)
    print("TEST FONCTION BOT")
    print("=" * 60)
    bot_result = get_esphome_power_data()
    print(f"Résultat bot: {bot_result}")
