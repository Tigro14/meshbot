#!/usr/bin/env python3
"""
Client pour l'intégration ESPHome avec historique
"""

import gc
from config import *
from utils import *
from esphome_history import ESPHomeHistory

class ESPHomeClient:
    def __init__(self):
        self.history = ESPHomeHistory()
    
    def parse_esphome_data(self, store_history=True):
        """
        Parse ESPHome - version optimisée mémoire avec historique
        
        Args:
            store_history: Si True, enregistre les valeurs dans l'historique
        
        Returns:
            str: Données ESPHome formatées
        """
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
                        try:
                            data = resp.json()
                        except Exception:
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
            error_print(f"Erreur ESPHome: {e}")
            return f"ESPHome Error: {str(e)[:30]}"
    
    def get_history_graphs(self, hours=24):
        """Obtenir les graphiques d'historique (version complète pour Telegram)"""
        return self.history.format_graphs(hours)

    def get_history_graphs_compact(self, hours=12):
        """Obtenir les graphiques compacts pour Meshtastic"""
        return self.history.format_graphs_compact(hours)
