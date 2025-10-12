#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module de vérification des conditions système avant requêtes LLM
Vérifie température CPU et tension batterie ESPHome
"""

import subprocess
from utils import debug_print, error_print, lazy_import_requests
from config import (
    LLAMA_BLOCK_ON_LOW_BATTERY,
    LLAMA_BLOCK_ON_HIGH_TEMP,
    LLAMA_MIN_BATTERY_VOLTAGE,
    LLAMA_MAX_CPU_TEMP,
    ESPHOME_HOST
)

class SystemChecks:
    """
    Vérifications système pour protéger contre surcharge
    """
    
    @staticmethod
    def get_cpu_temperature():
        """
        Récupérer la température CPU du Pi
        
        Returns:
            float: Température en °C, ou None si erreur
        """
        try:
            # Méthode 1: vcgencmd (Raspberry Pi)
            try:
                temp_cmd = ['vcgencmd', 'measure_temp']
                temp_result = subprocess.run(
                    temp_cmd,
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                
                if temp_result.returncode == 0:
                    temp_output = temp_result.stdout.strip()
                    if 'temp=' in temp_output:
                        temp_str = temp_output.split('=')[1].replace("'C", "")
                        return float(temp_str)
            except Exception as e:
                debug_print(f"vcgencmd échoué: {e}")
            
            # Méthode 2: /sys/class/thermal/thermal_zone0/temp
            try:
                with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                    temp_millis = int(f.read().strip())
                    return temp_millis / 1000.0
            except Exception as e:
                debug_print(f"Lecture thermal_zone0 échouée: {e}")
            
            return None
            
        except Exception as e:
            error_print(f"Erreur lecture température CPU: {e}")
            return None
    
    @staticmethod
    def get_battery_voltage():
        """
        Récupérer la tension batterie depuis ESPHome
        
        Returns:
            float: Tension en Volts, ou None si erreur
        """
        try:
            requests_module = lazy_import_requests()
            
            # Lecture rapide avec timeout court
            url = f"http://{ESPHOME_HOST}/sensor/battery_voltage"
            response = requests_module.get(url, timeout=2)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if isinstance(data, dict) and 'value' in data:
                        voltage = data['value']
                        debug_print(f"Tension batterie: {voltage}V")
                        return float(voltage)
                except Exception as e:
                    debug_print(f"Parse JSON batterie échoué: {e}")
            
            response.close()
            return None
            
        except Exception as e:
            error_print(f"Erreur lecture batterie: {e}")
            return None
    
    @staticmethod
    def check_llm_conditions():
        """
        Vérifier si les conditions sont OK pour exécuter une requête LLM
        
        Returns:
            tuple: (allowed: bool, reason: str or None)
                - allowed: True si OK, False si bloqué
                - reason: Message d'erreur si bloqué, None si OK
        """
        # === VÉRIFICATION 1: TEMPÉRATURE CPU ===
        if LLAMA_BLOCK_ON_HIGH_TEMP:
            cpu_temp = SystemChecks.get_cpu_temperature()
            
            if cpu_temp is not None:
                debug_print(f"Vérif CPU: {cpu_temp:.1f}°C (max: {LLAMA_MAX_CPU_TEMP}°C)")
                
                if cpu_temp > LLAMA_MAX_CPU_TEMP:
                    reason = (
                        f"🌡️ CPU trop chaud: {cpu_temp:.1f}°C\n"
                        f"Seuil: {LLAMA_MAX_CPU_TEMP}°C\n"
                        f"Requêtes IA désactivées temporairement"
                    )
                    error_print(f"🚫 LLM bloqué: {reason}")
                    return False, reason
            else:
                # Si on ne peut pas lire la température, on autorise (fail-open)
                debug_print("⚠️ Impossible de lire température CPU, autorisation par défaut")
        
        # === VÉRIFICATION 2: TENSION BATTERIE ===
        if LLAMA_BLOCK_ON_LOW_BATTERY:
            battery_voltage = SystemChecks.get_battery_voltage()
            
            if battery_voltage is not None:
                debug_print(f"Vérif batterie: {battery_voltage:.1f}V (min: {LLAMA_MIN_BATTERY_VOLTAGE}V)")
                
                if battery_voltage < LLAMA_MIN_BATTERY_VOLTAGE:
                    reason = (
                        f"🔋 Batterie faible: {battery_voltage:.1f}V\n"
                        f"Seuil: {LLAMA_MIN_BATTERY_VOLTAGE}V\n"
                        f"Requêtes IA désactivées temporairement"
                    )
                    error_print(f"🚫 LLM bloqué: {reason}")
                    return False, reason
            else:
                # Si on ne peut pas lire la tension, on autorise (fail-open)
                debug_print("⚠️ Impossible de lire tension batterie, autorisation par défaut")
        
        # === TOUTES LES CONDITIONS OK ===
        debug_print("✅ Conditions système OK pour LLM")
        return True, None
    
    @staticmethod
    def get_system_status_summary():
        """
        Obtenir un résumé de l'état système (pour debug)
        
        Returns:
            str: Résumé formaté
        """
        cpu_temp = SystemChecks.get_cpu_temperature()
        battery_voltage = SystemChecks.get_battery_voltage()
        
        lines = []
        lines.append("📊 État système:")
        
        if cpu_temp is not None:
            temp_icon = "🟢" if cpu_temp <= LLAMA_MAX_CPU_TEMP else "🔴"
            lines.append(f"  {temp_icon} CPU: {cpu_temp:.1f}°C (max: {LLAMA_MAX_CPU_TEMP}°C)")
        else:
            lines.append("  ⚠️ CPU: Non disponible")
        
        if battery_voltage is not None:
            volt_icon = "🟢" if battery_voltage >= LLAMA_MIN_BATTERY_VOLTAGE else "🔴"
            lines.append(f"  {volt_icon} Batterie: {battery_voltage:.1f}V (min: {LLAMA_MIN_BATTERY_VOLTAGE}V)")
        else:
            lines.append("  ⚠️ Batterie: Non disponible")
        
        allowed, reason = SystemChecks.check_llm_conditions()
        if allowed:
            lines.append("  ✅ Requêtes LLM: AUTORISÉES")
        else:
            lines.append("  🚫 Requêtes LLM: BLOQUÉES")
        
        return "\n".join(lines)
