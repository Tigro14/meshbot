#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module de gestion de l'historique ESPHome avec graphiques ASCII
Stocke les valeurs horaires sur 24h pour température, pression, hygrométrie
"""

import json
import os
import time
from datetime import datetime
from utils import debug_print, error_print

class ESPHomeHistory:
    def __init__(self, history_file="esphome_history.json"):
        self.history_file = history_file
        self.history = {
            'temperature': [],  # Liste de {'timestamp': int, 'value': float}
            'pressure': [],
            'humidity': []
        }
        self.load_history()
    
    def load_history(self):
        """Charger l'historique depuis le fichier"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r') as f:
                    self.history = json.load(f)
                debug_print(f"📚 Historique ESPHome chargé: {self._get_stats()}")
            else:
                debug_print("📂 Nouvel historique ESPHome créé")
        except Exception as e:
            error_print(f"Erreur chargement historique ESPHome: {e}")
            self.history = {'temperature': [], 'pressure': [], 'humidity': []}
    
    def save_history(self):
        """Sauvegarder l'historique dans le fichier"""
        try:
            with open(self.history_file, 'w') as f:
                json.dump(self.history, f, indent=2)
            debug_print("💾 Historique ESPHome sauvegardé")
        except Exception as e:
            error_print(f"Erreur sauvegarde historique ESPHome: {e}")
    
    def add_reading(self, temperature=None, pressure=None, humidity=None):
        """
        Ajouter une lecture des capteurs
        Ne stocke que si les valeurs ont changé significativement
        """
        current_time = int(time.time())
        current_hour = current_time - (current_time % 3600)  # Arrondir à l'heure
        
        # Température
        if temperature is not None:
            self._add_value('temperature', current_hour, temperature, threshold=0.5)
        
        # Pression
        if pressure is not None:
            self._add_value('pressure', current_hour, pressure, threshold=1.0)
        
        # Hygrométrie
        if humidity is not None:
            self._add_value('humidity', current_hour, humidity, threshold=1.0)
        
        # Nettoyer les vieilles données
        self.cleanup_old_data()
    
    def _add_value(self, metric, timestamp, value, threshold=0.5):
        """Ajouter une valeur si elle diffère significativement de la dernière"""
        data = self.history[metric]
        
        # Si pas de données ou timestamp différent, ajouter
        if not data or data[-1]['timestamp'] != timestamp:
            # Vérifier si la valeur a significativement changé
            if not data or abs(data[-1]['value'] - value) >= threshold:
                data.append({'timestamp': timestamp, 'value': value})
                debug_print(f"📊 {metric}: {value} ajouté")
    
    def cleanup_old_data(self):
        """Supprimer les données de plus de 24h"""
        cutoff_time = int(time.time()) - (24 * 3600)
        
        for metric in self.history:
            original_len = len(self.history[metric])
            self.history[metric] = [
                entry for entry in self.history[metric]
                if entry['timestamp'] >= cutoff_time
            ]
            removed = original_len - len(self.history[metric])
            if removed > 0:
                debug_print(f"🧹 {metric}: {removed} entrées anciennes supprimées")
    
    def get_sparkline(self, metric, hours=24):
        """
        Générer un graphique ASCII (sparkline) pour une métrique
        
        Args:
            metric: 'temperature', 'pressure' ou 'humidity'
            hours: Nombre d'heures à afficher (défaut: 24)
        
        Returns:
            dict: {
                'sparkline': str,
                'min': float,
                'max': float,
                'current': float,
                'trend': str ('↗', '→', '↘')
            }
        """
        symbols = "▁▂▃▄▅▆▇█"
        
        try:
            # Récupérer les données
            data = self.history.get(metric, [])
            if not data:
                return {
                    'sparkline': '─' * 24,
                    'min': 0,
                    'max': 0,
                    'current': 0,
                    'trend': '?'
                }
            
            # Filtrer par période
            cutoff_time = int(time.time()) - (hours * 3600)
            filtered_data = [
                entry for entry in data
                if entry['timestamp'] >= cutoff_time
            ]
            
            if not filtered_data:
                return {
                    'sparkline': '─' * hours,
                    'min': 0,
                    'max': 0,
                    'current': 0,
                    'trend': '?'
                }
            
            # Extraire les valeurs
            values = [entry['value'] for entry in filtered_data]
            current_value = values[-1]
            min_value = min(values)
            max_value = max(values)
            
            # Calculer la tendance
            if len(values) >= 3:
                recent_avg = sum(values[-3:]) / 3
                older_avg = sum(values[-6:-3]) / 3 if len(values) >= 6 else values[0]
                
                if recent_avg > older_avg + 0.5:
                    trend = '↗'
                elif recent_avg < older_avg - 0.5:
                    trend = '↘'
                else:
                    trend = '→'
            else:
                trend = '?'
            
            # Générer la sparkline
            sparkline = self._generate_sparkline(values, symbols, hours)
            
            return {
                'sparkline': sparkline,
                'min': min_value,
                'max': max_value,
                'current': current_value,
                'trend': trend
            }
            
        except Exception as e:
            error_print(f"Erreur génération sparkline {metric}: {e}")
            return {
                'sparkline': '?' * hours,
                'min': 0,
                'max': 0,
                'current': 0,
                'trend': '?'
            }
    
    def _generate_sparkline(self, values, symbols, target_length):
        """
        Générer la sparkline ASCII
        
        Args:
            values: Liste des valeurs
            symbols: String des symboles (8 niveaux)
            target_length: Longueur cible du graphique
        
        Returns:
            str: Sparkline ASCII
        """
        if not values:
            return '─' * target_length
        
        # Si on a plus de valeurs que nécessaire, sous-échantillonner
        if len(values) > target_length:
            step = len(values) / target_length
            sampled_values = [
                values[int(i * step)] 
                for i in range(target_length)
            ]
        # Si on a moins de valeurs, répéter la dernière
        elif len(values) < target_length:
            sampled_values = values + [values[-1]] * (target_length - len(values))
        else:
            sampled_values = values
        
        # Normaliser les valeurs
        min_val = min(sampled_values)
        max_val = max(sampled_values)
        
        if max_val == min_val:
            # Valeur constante
            return symbols[4] * target_length
        
        sparkline = ""
        for value in sampled_values:
            # Normaliser entre 0 et 1
            normalized = (value - min_val) / (max_val - min_val)
            # Mapper sur les symboles (0-7)
            symbol_index = int(normalized * (len(symbols) - 1))
            symbol_index = max(0, min(len(symbols) - 1, symbol_index))
            sparkline += symbols[symbol_index]
        
        return sparkline
    
    def format_graphs(self, hours=24):
        """
        Formater tous les graphiques pour affichage
        
        Returns:
            str: Message formaté avec tous les graphiques
        """
        try:
            lines = []
            lines.append(f"📈 Évolution ESPHome ({hours}h):")
            lines.append("")
            
            # Température
            temp_data = self.get_sparkline('temperature', hours)
            lines.append(f"🌡️ Température:")
            lines.append(f"{temp_data['sparkline']}")
            lines.append(
                f"Min: {temp_data['min']:.1f}°C | "
                f"Max: {temp_data['max']:.1f}°C | "
                f"Now: {temp_data['current']:.1f}°C {temp_data['trend']}"
            )
            lines.append("")
            
            # Pression
            press_data = self.get_sparkline('pressure', hours)
            lines.append(f"🔽 Pression:")
            lines.append(f"{press_data['sparkline']}")
            lines.append(
                f"Min: {press_data['min']:.0f}hPa | "
                f"Max: {press_data['max']:.0f}hPa | "
                f"Now: {press_data['current']:.0f}hPa {press_data['trend']}"
            )
            lines.append("")
            
            # Hygrométrie
            hum_data = self.get_sparkline('humidity', hours)
            lines.append(f"💧 Hygrométrie:")
            lines.append(f"{hum_data['sparkline']}")
            lines.append(
                f"Min: {hum_data['min']:.0f}% | "
                f"Max: {hum_data['max']:.0f}% | "
                f"Now: {hum_data['current']:.0f}% {hum_data['trend']}"
            )
            
            return "\n".join(lines)
            
        except Exception as e:
            error_print(f"Erreur format graphs: {e}")
            return "❌ Erreur génération graphiques"
    
    def _get_stats(self):
        """Obtenir des statistiques sur l'historique"""
        return " | ".join([
            f"{metric}: {len(self.history[metric])} pts"
            for metric in self.history
        ])
