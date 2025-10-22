#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module de gestion de l'historique des paquets Meshtastic avec graphiques ASCII
Stocke les compteurs horaires par type de paquet sur 24h
"""

import json
import os
import time
from datetime import datetime
from collections import defaultdict
from utils import debug_print, error_print

class PacketHistory:
    def __init__(self, history_file="packet_history.json"):
        self.history_file = history_file
        # Structure: {'TEXT_MESSAGE_APP': [{'timestamp': int, 'count': int}], ...}
        self.history = defaultdict(list)
        
        # Noms courts pour l'affichage
        self.type_labels = {
            'TEXT_MESSAGE_APP': 'TEXT',
            'NODEINFO_APP': 'NODE',
            'POSITION_APP': 'POS',
            'TELEMETRY_APP': 'TELE',
            'ROUTING_APP': 'ROUT',
            'ADMIN_APP': 'ADMN',
            'TRACEROUTE_APP': 'TRAC',
            'UNKNOWN_APP': 'UNK'
        }
        
        self.load_history()
    
    def load_history(self):
        """Charger l'historique depuis le fichier"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r') as f:
                    loaded = json.load(f)
                    # Convertir en defaultdict
                    self.history = defaultdict(list, loaded)
                debug_print(f"📚 Historique paquets chargé: {self._get_stats()}")
            else:
                debug_print("📂 Nouvel historique paquets créé")
        except Exception as e:
            error_print(f"Erreur chargement historique paquets: {e}")
            self.history = defaultdict(list)
    
    def save_history(self):
        """Sauvegarder l'historique dans le fichier"""
        try:
            with open(self.history_file, 'w') as f:
                # Convertir defaultdict en dict pour JSON
                json.dump(dict(self.history), f, indent=2)
            debug_print("💾 Historique paquets sauvegardé")
        except Exception as e:
            error_print(f"Erreur sauvegarde historique paquets: {e}")
    
    def add_packet(self, packet_type):
        """
        Enregistrer un paquet
        Incrémente le compteur de l'heure actuelle pour ce type
        
        Args:
            packet_type: Type de paquet (ex: 'TEXT_MESSAGE_APP')
        """
        current_time = int(time.time())
        current_hour = current_time - (current_time % 3600)  # Arrondir à l'heure
        
        # Obtenir ou créer l'entrée pour cette heure
        data = self.history[packet_type]
        
        if data and data[-1]['timestamp'] == current_hour:
            # Incrémenter le compteur de l'heure actuelle
            data[-1]['count'] += 1
        else:
            # Nouvelle heure
            data.append({'timestamp': current_hour, 'count': 1})
        
        # Nettoyer les vieilles données (>48h)
        self.cleanup_old_data()
    
    def cleanup_old_data(self):
        """Supprimer les données de plus de 48 heures"""
        current_time = int(time.time())
        cutoff_time = current_time - (48 * 3600)
        
        for packet_type in list(self.history.keys()):
            self.history[packet_type] = [
                entry for entry in self.history[packet_type]
                if entry['timestamp'] >= cutoff_time
            ]
            
            # Supprimer le type s'il n'y a plus de données
            if not self.history[packet_type]:
                del self.history[packet_type]
    
    def get_sparkline(self, packet_type, hours=24):
        """
        Générer un sparkline pour un type de paquet
        
        Args:
            packet_type: Type de paquet
            hours: Nombre d'heures à afficher
            
        Returns:
            dict: {
                'sparkline': str,
                'min': int,
                'max': int,
                'current': int,
                'total': int,
                'trend': str (↗️/↘️/→)
            }
        """
        try:
            current_time = int(time.time())
            start_time = current_time - (hours * 3600)
            
            # Récupérer les données de la période
            data = self.history.get(packet_type, [])
            period_data = [
                entry for entry in data
                if entry['timestamp'] >= start_time
            ]
            
            if not period_data:
                return {
                    'sparkline': '─' * 24,
                    'min': 0,
                    'max': 0,
                    'current': 0,
                    'total': 0,
                    'trend': '─'
                }
            
            # Créer un tableau avec une valeur par heure
            hourly_counts = [0] * hours
            for entry in period_data:
                hour_offset = int((entry['timestamp'] - start_time) / 3600)
                if 0 <= hour_offset < hours:
                    hourly_counts[hour_offset] = entry['count']
            
            # Stats
            total = sum(hourly_counts)
            max_count = max(hourly_counts)
            min_count = min(hourly_counts)
            current = hourly_counts[-1] if hourly_counts else 0
            
            # Tendance (comparer dernière heure vs moyenne des 3 précédentes)
            if len(hourly_counts) >= 4:
                recent_avg = sum(hourly_counts[-4:-1]) / 3
                if current > recent_avg * 1.2:
                    trend = '↗️'
                elif current < recent_avg * 0.8:
                    trend = '↘️'
                else:
                    trend = '→'
            else:
                trend = '─'
            
            # Générer le sparkline
            sparkline = self._create_sparkline(hourly_counts)
            
            return {
                'sparkline': sparkline,
                'min': min_count,
                'max': max_count,
                'current': current,
                'total': total,
                'trend': trend
            }
            
        except Exception as e:
            error_print(f"Erreur sparkline {packet_type}: {e}")
            return {
                'sparkline': '?' * 24,
                'min': 0,
                'max': 0,
                'current': 0,
                'total': 0,
                'trend': '?'
            }
    
    def _create_sparkline(self, values):
        """
        Créer un sparkline ASCII à partir de valeurs
        Utilise les mêmes caractères qu'ESPHome
        """
        if not values or max(values) == 0:
            return '▁' * len(values)
        
        # Symboles de sparkline (du plus bas au plus haut)
        symbols = '▁▂▃▄▅▆▇█'
        
        min_val = 0  # Toujours partir de 0 pour les compteurs
        max_val = max(values)
        
        sparkline = ''
        for value in values:
            if max_val == min_val:
                sparkline += symbols[0]
            else:
                # Normaliser entre 0 et 1
                normalized = (value - min_val) / (max_val - min_val)
                # Mapper sur les symboles (0-7)
                symbol_index = int(normalized * (len(symbols) - 1))
                symbol_index = max(0, min(len(symbols) - 1, symbol_index))
                sparkline += symbols[symbol_index]
        
        return sparkline
    
    def format_compact(self, hours=24):
        """
        Formater un rapport compact avec sparklines pour tous les types
        Format similaire à /graphs mais pour les paquets
        
        Args:
            hours: Nombre d'heures à afficher
            
        Returns:
            str: Rapport formaté
        """
        try:
            lines = []
            lines.append(f"📦 Paquets ({hours}h):")
            lines.append("")
            
            # Obtenir tous les types actifs, triés par total
            active_types = []
            for packet_type in self.history.keys():
                data = self.get_sparkline(packet_type, hours)
                if data['total'] > 0:
                    active_types.append((packet_type, data))
            
            # Trier par total décroissant
            active_types.sort(key=lambda x: x[1]['total'], reverse=True)
            
            if not active_types:
                return "📦 Aucun paquet enregistré"
            
            # Afficher chaque type avec son sparkline
            for packet_type, data in active_types:
                label = self.type_labels.get(packet_type, packet_type[:4].upper())
                
                lines.append(f"{label}:")
                lines.append(f"{data['sparkline']}")
                lines.append(
                    f"Min:{data['min']} | "
                    f"Max:{data['max']} | "
                    f"Now:{data['current']} {data['trend']} | "
                    f"Tot:{data['total']}"
                )
                lines.append("")
            
            # Total global
            total_packets = sum(d['total'] for _, d in active_types)
            lines.append(f"📊 Total: {total_packets} paquets")
            
            return "\n".join(lines)
            
        except Exception as e:
            error_print(f"Erreur format compact: {e}")
            return "❌ Erreur génération rapport"
    
    def format_summary(self, hours=24):
        """
        Formater un résumé ultra-compact (pour Meshtastic)
        Une ligne par type avec total et tendance
        
        Args:
            hours: Nombre d'heures
            
        Returns:
            str: Résumé formaté
        """
        try:
            lines = []
            lines.append(f"📦 Paquets {hours}h:")
            
            # Obtenir tous les types actifs
            active_types = []
            for packet_type in self.history.keys():
                data = self.get_sparkline(packet_type, hours)
                if data['total'] > 0:
                    active_types.append((packet_type, data))
            
            # Trier par total décroissant
            active_types.sort(key=lambda x: x[1]['total'], reverse=True)
            
            if not active_types:
                return "📦 Aucun paquet"
            
            # Afficher chaque type sur une ligne
            total_packets = 0
            for packet_type, data in active_types[:6]:  # Max 6 types
                label = self.type_labels.get(packet_type, packet_type[:4].upper())
                lines.append(f"{label}:{data['total']}{data['trend']}")
                total_packets += data['total']
            
            if len(active_types) > 6:
                remaining = sum(d['total'] for _, d in active_types[6:])
                total_packets += remaining
                lines.append(f"Autres:{remaining}")
            
            lines.append(f"Total:{total_packets}")
            
            return "\n".join(lines)
            
        except Exception as e:
            error_print(f"Erreur format summary: {e}")
            return "❌ Erreur"
    
    def _get_stats(self):
        """Obtenir des statistiques sur l'historique"""
        return " | ".join([
            f"{self.type_labels.get(ptype, ptype[:4])}: {len(data)} pts"
            for ptype, data in self.history.items()
        ])
    
    def get_type_percentage(self, hours=24):
        """
        Obtenir le pourcentage de chaque type de paquet
        
        Returns:
            dict: {packet_type: percentage}
        """
        try:
            type_totals = {}
            total = 0
            
            for packet_type in self.history.keys():
                data = self.get_sparkline(packet_type, hours)
                type_totals[packet_type] = data['total']
                total += data['total']
            
            if total == 0:
                return {}
            
            percentages = {
                ptype: (count / total) * 100
                for ptype, count in type_totals.items()
            }
            
            return percentages
            
        except Exception as e:
            error_print(f"Erreur calcul pourcentages: {e}")
            return {}
