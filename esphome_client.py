#!/usr/bin/env python3
"""
Client pour l'intégration ESPHome avec historique
"""

import gc
import time
from config import *
from utils import *
from esphome_history import ESPHomeHistory

class ESPHomeClient:
    def __init__(self):
        self.history = ESPHomeHistory()
    
    def parse_esphome_data(self, store_history=True):
        """
        Parse ESPHome - version optimisée mémoire avec historique et retry logic
        
        Args:
            store_history: Si True, enregistre les valeurs dans l'historique
        
        Returns:
            str: Données ESPHome formatées
        """
        max_retries = 2
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                requests_module = lazy_import_requests()
                
                if attempt > 0:
                    debug_print(f"ESPHome tentative {attempt + 1}/{max_retries}...")
                else:
                    debug_print("Récupération ESPHome...")
                
                # Test connectivité minimal avec timeout plus court
                try:
                    response = requests_module.get(f"http://{ESPHOME_HOST}/", timeout=3)
                    if response.status_code != 200:
                        del response
                        if attempt < max_retries - 1:
                            info_print(f"⚠️ ESPHome status {response.status_code}, tentative {attempt + 1}/{max_retries}")
                            time.sleep(retry_delay)
                            continue
                        return "ESPHome inaccessible"
                    del response
                except requests_module.exceptions.Timeout:
                    if attempt < max_retries - 1:
                        info_print(f"⚠️ ESPHome timeout, tentative {attempt + 1}/{max_retries}, retry dans {retry_delay}s...")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    error_print("❌ ESPHome timeout après retries")
                    return "ESPHome timeout"
                except requests_module.exceptions.ConnectionError as e:
                    if attempt < max_retries - 1:
                        info_print(f"⚠️ ESPHome connexion error, tentative {attempt + 1}/{max_retries}")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    error_print(f"❌ ESPHome connexion error: {e}")
                    return "ESPHome inaccessible"
                
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
                            try:
                                data = resp.json()
                            except Exception as e:
                                data = {}
                            if isinstance(data, dict) and 'value' in data:
                                sensor_name = endpoint.split('/')[-1]
                                found_data[sensor_name] = data['value']
                        resp.close()
                    except Exception as e:
                        continue
                
                # ✅ AJOUT : Enregistrer dans l'historique
                if store_history:
                    temp = None
                    press = None
                    hum = None
                    
                    # Extraire température
                    if 'bme280_temperature' in found_data:
                        temp = found_data['bme280_temperature']
                    
                    # Extraire pression
                    if 'bme280_pressure' in found_data:
                        press = found_data['bme280_pressure']
                    
                    # Extraire hygrométrie (relative en priorité)
                    for hum_key in ['bme280_humidity', 'bme280_relative_humidity']:
                        if hum_key in found_data:
                            hum = found_data[hum_key]
                            break
                    
                    # Enregistrer si on a au moins une valeur
                    if temp is not None or press is not None or hum is not None:
                        self.history.add_reading(
                            temperature=temp,
                            pressure=press,
                            humidity=hum
                        )
                        self.history.save_history()
                        debug_print("📊 Historique ESPHome mis à jour")
                
                # Formatage simplifié
                if found_data:
                    parts = []
                    
                    # Batterie combinée
                    if 'battery_voltage' in found_data and 'battery_current' in found_data:
                        parts.append(f"{found_data['battery_voltage']:.1f}V ({found_data['battery_current']:.3f}A)")
                    elif 'battery_voltage' in found_data:
                        parts.append(f"{found_data['battery_voltage']:.1f}V")
                    
                    # Production
                    if 'yield_today' in found_data:
                        parts.append(f"Today:{found_data['yield_today']:.0f}Wh")
                    
                    # Météo
                    if 'bme280_temperature' in found_data:
                        parts.append(f"T:{found_data['bme280_temperature']:.1f}C")
                    
                    if 'bme280_pressure' in found_data:
                        pressure_value = found_data['bme280_pressure']
                        # Convert from Pa to hPa if necessary (ESPHome might return in Pa)
                        if pressure_value > 2000:  # Likely in Pa (100000 Pa ≈ 1000 hPa)
                            pressure_value = pressure_value / 100
                        parts.append(f"P:{pressure_value:.1f}hPa")
                    
                    # Humidité combinée : relative + absolue
                    humidity_relative = None
                    for humidity_key in ['bme280_humidity', 'bme280_relative_humidity']:
                        if humidity_key in found_data:
                            humidity_relative = found_data[humidity_key]
                            break
                    
                    if humidity_relative is not None:
                        humidity_str = f"HR:{humidity_relative:.0f}%"
                        if 'absolute_humidity' in found_data:
                            abs_hum = found_data['absolute_humidity']
                            humidity_str += f"({abs_hum:.1f}g/m³)"
                        parts.append(humidity_str)
                    
                    result = " | ".join(parts[:5])
                    
                    # Nettoyer
                    del found_data, parts
                    gc.collect()
                    
                    debug_print(f"ESPHome: {result}")
                    return truncate_text(result, MAX_MESSAGE_SIZE)
                else:
                    return "ESPHome Online"
                    
            except Exception as e:
                if attempt < max_retries - 1:
                    info_print(f"⚠️ Erreur ESPHome: {type(e).__name__}, tentative {attempt + 1}/{max_retries}")
                    debug_print(f"   Message: {e}")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    error_print(f"❌ Erreur ESPHome après {max_retries} tentatives: {type(e).__name__}")
                    error_print(f"   Message: {e}")
                    return f"ESPHome Error: {str(e)[:30]}"
        
        # Fallback si toutes les tentatives échouent
        return "ESPHome inaccessible"
    
    def get_history_graphs(self, hours=24):
        """Obtenir les graphiques d'historique (version complète pour Telegram)"""
        return self.history.format_graphs(hours)

    def get_history_graphs_compact(self, hours=12):
        """Obtenir les graphiques compacts pour Meshtastic"""
        return self.history.format_graphs_compact(hours)
    
    def get_sensor_values(self):
        """
        Récupérer les valeurs brutes des capteurs ESPHome pour télémétrie avec retry logic
        
        Returns:
            dict: Dictionnaire avec les clés:
                - temperature: Température en °C (ou None)
                - pressure: Pression en hPa (ou None)
                - humidity: Humidité relative en % (ou None)
                - battery_voltage: Tension batterie en V (ou None)
                - battery_current: Intensité batterie en A (ou None)
        """
        max_retries = 2
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                requests_module = lazy_import_requests()
                
                if attempt > 0:
                    debug_print(f"ESPHome télémétrie tentative {attempt + 1}/{max_retries}...")
                else:
                    debug_print("Récupération capteurs ESPHome pour télémétrie...")
                
                # Test connectivité avec timeout
                try:
                    response = requests_module.get(f"http://{ESPHOME_HOST}/", timeout=3)
                    if response.status_code != 200:
                        del response
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            continue
                        return None
                    del response
                except (requests_module.exceptions.Timeout, requests_module.exceptions.ConnectionError) as e:
                    if attempt < max_retries - 1:
                        info_print(f"⚠️ ESPHome télémétrie timeout/error, tentative {attempt + 1}/{max_retries}")
                        debug_print(f"   Message: {e}")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    error_print(f"❌ ESPHome télémétrie inaccessible après {max_retries} tentatives: {type(e).__name__}")
                    debug_print(f"   Message: {e}")
                    return None
                
                result = {
                    'temperature': None,
                    'pressure': None,
                    'humidity': None,
                    'battery_voltage': None,
                    'battery_current': None
                }
                
                # Mapping des endpoints vers les clés du résultat
                endpoints_map = {
                    '/sensor/bme280_temperature': 'temperature',
                    '/sensor/bme280_pressure': 'pressure',
                    '/sensor/bme280_relative_humidity': 'humidity',
                    '/sensor/bme280_humidity': 'humidity',  # Fallback
                    '/sensor/battery_voltage': 'battery_voltage',
                    '/sensor/battery_current': 'battery_current'
                }
                
                # Récupérer chaque capteur
                for endpoint, key in endpoints_map.items():
                    # Skip humidity si déjà trouvé
                    if key == 'humidity' and result['humidity'] is not None:
                        continue
                        
                    try:
                        url = f"http://{ESPHOME_HOST}{endpoint}"
                        resp = requests_module.get(url, timeout=2)
                        
                        if resp.status_code == 200:
                            data = resp.json()
                            if isinstance(data, dict) and 'value' in data:
                                value = data['value']
                                
                                # Note: Meshtastic expects pressure in hPa (hectopascals)
                                # ESPHome typically returns hPa, so no conversion needed
                                # If ESPHome returns Pa (value > 10000), convert to hPa
                                if key == 'pressure' and value is not None:
                                    if value > 10000:  # Likely in Pa (e.g., 101325 Pa)
                                        value = value / 100  # Convert Pa to hPa
                                
                                result[key] = value
                                debug_print(f"📊 {key}: {value}")
                        
                        resp.close()
                    except Exception as e:
                        debug_print(f"Erreur lecture {endpoint}: {e}")
                        continue
                
                # Vérifier qu'on a au moins une valeur
                if all(v is None for v in result.values()):
                    if attempt < max_retries - 1:
                        debug_print("⚠️ Aucune valeur ESPHome trouvée, retry...")
                        time.sleep(retry_delay)
                        continue
                    debug_print("⚠️ Aucune valeur ESPHome trouvée")
                    return None
                
                return result
                
            except Exception as e:
                if attempt < max_retries - 1:
                    info_print(f"⚠️ Erreur récupération capteurs ESPHome: {type(e).__name__}, tentative {attempt + 1}/{max_retries}")
                    debug_print(f"   Message: {e}")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    error_print(f"❌ Erreur récupération capteurs ESPHome après {max_retries} tentatives: {type(e).__name__}")
                    error_print(f"   Message: {e}")
                    return None
        
        return None
