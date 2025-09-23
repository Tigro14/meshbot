#!/usr/bin/env python3
"""
Gestionnaire des nœuds et de leurs informations
"""

import json
import os
import time
import threading
import gc
from config import *
from utils import *

class NodeManager:
    def __init__(self):
        self.node_names = {}
        self._last_node_save = 0
        self.rx_history = {}  # node_id -> {'name': str, 'rssi': int, 'snr': float, 'last_seen': timestamp, 'count': int}
    
    def load_node_names(self):
        """Charger la base de noms depuis le fichier"""
        try:
            if os.path.exists(NODE_NAMES_FILE):
                with open(NODE_NAMES_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Convertir les clés string en int
                    self.node_names = {int(k): v for k, v in data.items() if k.isdigit()}
                debug_print(f"📚 {len(self.node_names)} noms de nœuds chargés")
            else:
                debug_print("📂 Nouvelle base de noms créée")
                self.node_names = {}
        except Exception as e:
            error_print(f"Erreur chargement noms: {e}")
            self.node_names = {}
    
    def save_node_names(self, force=False):
        """Sauvegarder la base de noms (avec throttling)"""
        try:
            current_time = time.time()
            # Sauvegarder seulement toutes les 60s sauf si forcé
            if not force and (current_time - self._last_node_save) < 60:
                return
            
            # Convertir les clés int en string pour JSON
            data = {str(k): v for k, v in self.node_names.items()}
            with open(NODE_NAMES_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._last_node_save = current_time
            debug_print(f"💾 Base sauvegardée ({len(self.node_names)} nœuds)")
        except Exception as e:
            error_print(f"Erreur sauvegarde noms: {e}")
    
    def get_node_name(self, node_id, interface=None):
        """Récupérer le nom d'un nœud par son ID"""
        if node_id in self.node_names:
            return self.node_names[node_id]
        
        # Tenter de récupérer depuis l'interface en temps réel
        try:
            if interface and hasattr(interface, 'nodes'):
                nodes = getattr(interface, 'nodes', {})
                if node_id in nodes:
                    node_info = nodes[node_id]
                    if isinstance(node_info, dict) and 'user' in node_info:
                        user_info = node_info['user']
                        if isinstance(user_info, dict):
                            name = user_info.get('longName') or user_info.get('shortName')
                            if name and len(name.strip()) > 0:
                                name = clean_node_name(name)
                                self.node_names[node_id] = name
                                # Sauvegarde différée pour nouveaux nœuds
                                threading.Timer(5.0, lambda: self.save_node_names()).start()
                                return name
        except Exception as e:
            debug_print(f"Erreur récupération nom {node_id}: {e}")
        
        return f"Node-{node_id:08x}"
    
    def update_node_database(self, interface):
        """Mettre à jour la base de données des nœuds"""
        if not interface:
            return
        
        try:
            debug_print("🔄 Mise à jour base de nœuds...")
            updated_count = 0
            
            # Récupérer tous les nœuds connus
            nodes = getattr(interface, 'nodes', {})
            
            for node_id, node_info in nodes.items():
                try:
                    # Convertir node_id en entier si c'est une string
                    if isinstance(node_id, str):
                        if node_id.startswith('!'):
                            # Format !16fad3dc - retirer le ! puis convertir hex
                            clean_id = node_id[1:]
                            node_id_int = int(clean_id, 16)
                        else:
                            # Autres formats string
                            try:
                                node_id_int = int(node_id, 16)
                            except ValueError:
                                node_id_int = int(node_id)  # Fallback décimal
                    else:
                        # Déjà un int
                        node_id_int = int(node_id)
                    
                    if isinstance(node_info, dict) and 'user' in node_info:
                        user_info = node_info['user']
                        if isinstance(user_info, dict):
                            long_name = user_info.get('longName', '').strip()
                            short_name = user_info.get('shortName', '').strip()
                            
                            name = long_name or short_name
                            if name and len(name) > 0:
                                old_name = self.node_names.get(node_id_int)
                                if old_name != name:
                                    self.node_names[node_id_int] = name
                                    debug_print(f"🔄 {node_id_int:08x}: '{old_name}' -> '{name}'")
                                    updated_count += 1
                except Exception as e:
                    # Utiliser la représentation string pour le debug si conversion échoue
                    debug_print(f"Erreur traitement nœud {node_id}: {e}")
                    continue
            
            if updated_count > 0:
                self.save_node_names()
                debug_print(f"✅ {updated_count} nœuds mis à jour")
            else:
                debug_print(f"ℹ️ Base à jour ({len(self.node_names)} nœuds)")
                
        except Exception as e:
            error_print(f"Erreur mise à jour base: {e}")
    
    def update_node_from_packet(self, packet):
        """Mettre à jour la base de nœuds depuis un packet reçu"""
        try:
            if 'decoded' in packet and packet['decoded'].get('portnum') == 'NODEINFO_APP':
                node_id = packet.get('from')
                decoded = packet['decoded']
                
                if 'user' in decoded and node_id:
                    user_info = decoded['user']
                    long_name = user_info.get('longName', '').strip()
                    short_name = user_info.get('shortName', '').strip()
                    
                    name = long_name or short_name
                    if name and len(name) > 0:
                        old_name = self.node_names.get(node_id)
                        if old_name != name:
                            self.node_names[node_id] = name
                            debug_print(f"📱 Nouveau: {name} ({node_id:08x})")
                            # Sauvegarde différée
                            threading.Timer(10.0, lambda: self.save_node_names()).start()
        except Exception as e:
            debug_print(f"Erreur traitement NodeInfo: {e}")
    
    def update_rx_history(self, packet):
        """Mettre à jour l'historique des signaux reçus (DIRECT uniquement - 0 hop)"""
        try:
            from_id = packet.get('from')
            if not from_id:
                return
            
            # FILTRER UNIQUEMENT LES MESSAGES DIRECTS (0 hop)
            hop_limit = packet.get('hopLimit', 0)
            hop_start = packet.get('hopStart', 5)  # Valeur configurée pour ce réseau
            
            # Calculer le nombre de hops effectués
            hops_taken = hop_start - hop_limit
            
            # Ne traiter que les messages reçus directement (0 hop)
            if hops_taken > 0:
                debug_print(f"🔄 Ignoré (relayé {hops_taken} hop): {self.get_node_name(from_id)}")
                return
            
            # Extraire les informations de signal (uniquement pour direct)
            rssi = packet.get('rssi', 0)
            snr = packet.get('snr', 0.0)
            current_time = time.time()
            
            # Obtenir le nom du nœud
            node_name = self.get_node_name(from_id)
            
            # Mettre à jour l'historique
            if from_id in self.rx_history:
                entry = self.rx_history[from_id]
                entry['rssi'] = rssi
                entry['snr'] = snr
                entry['last_seen'] = current_time
                entry['count'] += 1
                entry['name'] = node_name  # Mettre à jour le nom si changé
            else:
                self.rx_history[from_id] = {
                    'name': node_name,
                    'rssi': rssi,
                    'snr': snr,
                    'last_seen': current_time,
                    'count': 1
                }
            
            # Limiter la taille de l'historique (garder les plus récents)
            if len(self.rx_history) > MAX_RX_HISTORY:
                # Trier par last_seen et garder les plus récents
                sorted_entries = sorted(self.rx_history.items(), 
                                      key=lambda x: x[1]['last_seen'], 
                                      reverse=True)
                self.rx_history = dict(sorted_entries[:MAX_RX_HISTORY])
            
            debug_print(f"📡 RX DIRECT: {node_name} RSSI:{rssi} SNR:{snr:.1f} (0 hop)")
            
        except Exception as e:
            debug_print(f"Erreur mise à jour RX: {e}")
    
    def format_rx_report(self):
        """Formater le rapport des nœuds reçus"""
        try:
            if not self.rx_history:
                return "Aucun nœud reçu récemment"
            
            current_time = time.time()
            recent_nodes = []
            
            # Filtrer les nœuds vus dans les dernières 30 minutes
            for node_id, data in self.rx_history.items():
                if current_time - data['last_seen'] <= 1800:  # 30 minutes
                    recent_nodes.append((node_id, data))
            
            if not recent_nodes:
                return "Aucun nœud récent (30min)"
            
            # Trier par force du signal (RSSI descendant)
            recent_nodes.sort(key=lambda x: x[1]['rssi'], reverse=True)
            
            # Formater le rapport
            lines = []
            lines.append(f"📡 Nœuds DIRECTS ({len(recent_nodes)}):")
            
            for node_id, data in recent_nodes[:10]:  # Limiter à 10 pour la taille du message
                name = truncate_text(data['name'], 12)
                rssi = data['rssi']
                snr = data['snr']
                count = data['count']
                
                # Indicateur de qualité basé sur RSSI
                signal_icon = get_signal_quality_icon(rssi)
                
                # Temps depuis dernière réception
                time_str = format_elapsed_time(data['last_seen'])
                
                line = f"{signal_icon} {name}: {rssi}dBm SNR:{snr:.1f} ({count}x) {time_str}"
                lines.append(line)
            
            if len(recent_nodes) > 10:
                lines.append(f"... et {len(recent_nodes) - 10} autres")
            
            result = "\n".join(lines)
            
            # Limiter la taille totale du message
            if len(result) > 500:
                # Prendre seulement les 5 premiers
                lines_short = lines[:6]  # Header + 5 nœuds
                if len(recent_nodes) > 5:
                    lines_short.append(f"... et {len(recent_nodes) - 5} autres")
                result = "\n".join(lines_short)
            
            return result
            
        except Exception as e:
            error_print(f"Erreur format RX: {e}")
            return f"Erreur génération rapport RX: {truncate_text(str(e), 30)}"
    
    def list_known_nodes(self):
        """Lister tous les nœuds connus"""
        if not DEBUG_MODE:
            return
            
        print(f"\n📋 Nœuds connus ({len(self.node_names)}):")
        print("-" * 60)
        for node_id, name in sorted(self.node_names.items()):
            print(f"  !{node_id:08x} -> {name}")
        print("-" * 60)
    
    def cleanup_old_rx_history(self):
        """Nettoyer l'historique RX ancien"""
        try:
            current_time = time.time()
            cutoff_time = current_time - 3600  # 1 heure
            
            to_remove = []
            for node_id, data in self.rx_history.items():
                if data['last_seen'] < cutoff_time:
                    to_remove.append(node_id)
            
            for node_id in to_remove:
                del self.rx_history[node_id]
            
            if to_remove:
                debug_print(f"🧹 {len(to_remove)} entrées RX anciennes supprimées")
                
        except Exception as e:
            debug_print(f"Erreur nettoyage RX: {e}")
