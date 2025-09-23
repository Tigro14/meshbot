#!/usr/bin/env python3
"""
Bot Mesh Debug - Version optimisée mémoire avec gestion des noms de nœuds et contexte
"""

import time
import threading
import argparse
import sys
import gc
import json
import os
from datetime import datetime
import meshtastic
import meshtastic.serial_interface
from pubsub import pub

# Configuration
SERIAL_PORT = "/dev/ttyACM0"
LLAMA_HOST = "127.0.0.1"
LLAMA_PORT = 8080

# Configuration ESPHome
ESPHOME_HOST = "192.168.1.27"
ESPHOME_PORT = 80

# Configuration noms de nœuds
NODE_NAMES_FILE = "node_names.json"
NODE_UPDATE_INTERVAL = 300  # 5 minutes

# Configuration nœud distant fixe
REMOTE_NODE_HOST = "192.168.1.38"
REMOTE_NODE_NAME = "tigrog2"

# Configuration affichage des métriques de signal
SHOW_RSSI = False  # Afficher les valeurs RSSI (-85dB)
SHOW_SNR = False   # Afficher les valeurs SNR (SNR:8.5)
COLLECT_SIGNAL_METRICS = True  # Collecter RSSI/SNR pour le tri (même si pas affiché)

# Variable globale pour le mode debug
DEBUG_MODE = False

# Import paresseux pour économiser la mémoire
def lazy_import_requests():
    """Import requests seulement quand nécessaire"""
    global requests
    if 'requests' not in globals():
        import requests
    return requests

def lazy_import_re():
    """Import re seulement quand nécessaire"""
    global re
    if 're' not in globals():
        import re
    return re

def debug_print(message):
    """Affiche seulement en mode debug"""
    if DEBUG_MODE:
        print(f"[DEBUG] {message}", file=sys.stderr, flush=True)

def info_print(message):
    """Affiche toujours (logs importants)"""
    print(f"[INFO] {message}", flush=True)

def conversation_print(message):
    """Log spécial pour les conversations"""
    print(f"[CONVERSATION] {message}", flush=True)

def error_print(message):
    """Log d'erreur"""
    print(f"[ERROR] {message}", file=sys.stderr, flush=True)

class DebugMeshBot:
    def __init__(self):
        self.interface = None
        self.running = False
        # Cache limité pour les réponses
        self._response_cache = {}
        self._max_cache_size = 5
        # Patterns compilés une seule fois
        self._clean_patterns = None
        # Base de noms de nœuds
        self.node_names = {}
        self.update_thread = None
        self._last_node_save = 0
        # Historique des signaux reçus
        self.rx_history = {}  # node_id -> {'name': str, 'rssi': int, 'snr': float, 'last_seen': timestamp, 'count': int}
        self._max_rx_history = 50  # Limiter pour économiser la mémoire
        # Contexte conversationnel par node
        self.conversation_context = {}  # node_id -> [{'role': 'user'/'assistant', 'content': str, 'timestamp': float}]
        self._max_context_messages = 6  # 3 échanges (user + assistant)
        self._context_timeout = 1800  # 30 minutes
        
    def _get_clean_patterns(self):
        """Initialise les patterns regex une seule fois"""
        if self._clean_patterns is None:
            re_module = lazy_import_re()
            self._clean_patterns = [
                re_module.compile(r'<think>.*?</think>', re_module.DOTALL | re_module.IGNORECASE),
                re_module.compile(r'<thinking>.*?</thinking>', re_module.DOTALL | re_module.IGNORECASE)
            ]
        return self._clean_patterns
    
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
    
    def update_node_database(self):
        """Mettre à jour la base de données des nœuds"""
        if not self.interface:
            return
        
        try:
            debug_print("🔄 Mise à jour base de nœuds...")
            updated_count = 0
            
            # Récupérer tous les nœuds connus
            nodes = getattr(self.interface, 'nodes', {})
            
            for node_id, node_info in nodes.items():
                try:
                    if isinstance(node_info, dict) and 'user' in node_info:
                        user_info = node_info['user']
                        if isinstance(user_info, dict):
                            long_name = user_info.get('longName', '').strip()
                            short_name = user_info.get('shortName', '').strip()
                            
                            name = long_name or short_name
                            if name and len(name) > 0:
                                old_name = self.node_names.get(node_id)
                                if old_name != name:
                                    self.node_names[node_id] = name
                                    debug_print(f"📝 {node_id:08x}: '{old_name}' -> '{name}'")
                                    updated_count += 1
                except Exception as e:
                    debug_print(f"Erreur traitement nœud {node_id}: {e}")
                    continue
            
            if updated_count > 0:
                self.save_node_names()
                debug_print(f"✅ {updated_count} nœuds mis à jour")
            else:
                debug_print(f"ℹ️ Base à jour ({len(self.node_names)} nœuds)")
                
        except Exception as e:
            error_print(f"Erreur mise à jour base: {e}")
    
    def get_node_name(self, node_id):
        """Récupérer le nom d'un nœud par son ID"""
        if node_id in self.node_names:
            return self.node_names[node_id]
        
        # Tenter de récupérer depuis l'interface en temps réel
        try:
            if self.interface and hasattr(self.interface, 'nodes'):
                nodes = getattr(self.interface, 'nodes', {})
                if node_id in nodes:
                    node_info = nodes[node_id]
                    if isinstance(node_info, dict) and 'user' in node_info:
                        user_info = node_info['user']
                        if isinstance(user_info, dict):
                            name = user_info.get('longName') or user_info.get('shortName')
                            if name and len(name.strip()) > 0:
                                name = name.strip()
                                self.node_names[node_id] = name
                                # Sauvegarde différée pour nouveaux nœuds
                                threading.Timer(5.0, lambda: self.save_node_names()).start()
                                return name
        except Exception as e:
            debug_print(f"Erreur récupération nom {node_id}: {e}")
        
        return f"Node-{node_id:08x}"
    
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
    
    def get_conversation_context(self, node_id):
        """Récupérer le contexte conversationnel pour unoeud"""
        try:
            if node_id not in self.conversation_context:
                return []
            
            current_time = time.time()
            context = self.conversation_context[node_id]
            
            # Filtrer les messages trop anciens
            valid_context = [
                msg for msg in context 
                if current_time - msg['timestamp'] <= self._context_timeout
            ]
            
            # Mettre à jour si des messages ont été supprimés
            if len(valid_context) != len(context):
                self.conversation_context[node_id] = valid_context
                debug_print(f"🧹 Contexte nettoyé pour {self.get_node_name(node_id)}: {len(valid_context)} messages")
            
            return valid_context
            
        except Exception as e:
            debug_print(f"Erreur contexte: {e}")
            return []
    
    def add_to_context(self, node_id, role, content):
        """Ajouter un message au contexte conversationnel"""
        try:
            current_time = time.time()
            
            if node_id not in self.conversation_context:
                self.conversation_context[node_id] = []
            
            # Ajouter le nouveau message
            message = {
                'role': role,
                'content': content,
                'timestamp': current_time
            }
            
            self.conversation_context[node_id].append(message)
            
            # Limiter la taille du contexte (garder les plus récents)
            if len(self.conversation_context[node_id]) > self._max_context_messages:
                self.conversation_context[node_id] = self.conversation_context[node_id][-self._max_context_messages:]
            
            debug_print(f"📝 Contexte {self.get_node_name(node_id)}: +{role} ({len(self.conversation_context[node_id])} msgs)")
            
        except Exception as e:
            debug_print(f"Erreur ajout contexte: {e}")
    
    def cleanup_old_contexts(self):
        """Nettoyer les contextes trop anciens"""
        try:
            current_time = time.time()
            nodes_to_remove = []
            
            for node_id, context in self.conversation_context.items():
                # Filtrer les messages valides
                valid_messages = [
                    msg for msg in context 
                    if current_time - msg['timestamp'] <= self._context_timeout
                ]
                
                if not valid_messages:
                    # Aucun message valide, supprimer le contexte
                    nodes_to_remove.append(node_id)
                elif len(valid_messages) != len(context):
                    # Certains messages expirés, nettoyer
                    self.conversation_context[node_id] = valid_messages
            
            # Supprimer les contextes vides
            for node_id in nodes_to_remove:
                del self.conversation_context[node_id]
                debug_print(f"🗑️ Contexte supprimé: {self.get_node_name(node_id)}")
                
        except Exception as e:
            debug_print(f"Erreur nettoyage contexte: {e}")
    
    def update_rx_history(self, packet):
        """Mettre à jour l'historique des signaux reçus (DIRECT uniquement - 0 hop)"""
        try:
            from_id = packet.get('from')
            if not from_id or from_id == getattr(getattr(self.interface, 'localNode', None), 'nodeNum', None):
                return  # Ignorer nos propres messages
            
            # FILTRER UNIQUEMENT LES MESSAGES DIRECTS (0 hop)
            hop_limit = packet.get('hopLimit', 0)
            hop_start = packet.get('hopStart', 3)  # Valeur par défaut Meshtastic
            
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
            if len(self.rx_history) > self._max_rx_history:
                # Trier par last_seen et garder les plus récents
                sorted_entries = sorted(self.rx_history.items(), 
                                      key=lambda x: x[1]['last_seen'], 
                                      reverse=True)
                self.rx_history = dict(sorted_entries[:self._max_rx_history])
            
            debug_print(f"📡 RX DIRECT: {node_name} RSSI:{rssi} SNR:{snr:.1f} (0 hop)")
            
        except Exception as e:
            debug_print(f"Erreur mise à jour RX: {e}")
    
    def get_remote_nodes(self, remote_host, remote_port=4403):
        """Récupérer la liste des nœuds directs (0 hop) d'un nœud distant"""
        try:
            debug_print(f"Connexion au nœud distant {remote_host}...")
            
            # Tenter une connexion TCP au nœud distant
            import meshtastic.tcp_interface
            remote_interface = meshtastic.tcp_interface.TCPInterface(hostname=remote_host, portNumber=remote_port)
            
            # Attendre que les données se chargent
            time.sleep(2)
            
            # Récupérer les nœuds
            remote_nodes = remote_interface.nodes
            
            # Formater les résultats - FILTRER SEULEMENT LES NŒUDS DIRECTS
            node_list = []
            for node_id, node_info in remote_nodes.items():
                try:
                    if isinstance(node_info, dict):
                        # VÉRIFIER SI LE NŒUD A ÉTÉ REÇU DIRECTEMENT
                        # Le critère le plus fiable est hopsAway = 0
                        hops_away = node_info.get('hopsAway', None)
                        
                        # Si hopsAway existe, l'utiliser comme critère principal
                        if hops_away is not None:
                            if hops_away > 0:
                                debug_print(f"Nœud {node_id} ignoré (hopsAway={hops_away})")
                                continue
                            else:
                                debug_print(f"Nœud {node_id} accepté (hopsAway={hops_away})")
                        else:
                            # Fallback : utiliser les métriques de signal comme critère
                            rssi = node_info.get('rssi', 0)
                            snr = node_info.get('snr', 0.0)
                            
                            # Si pas de hopsAway ET pas de métriques RSSI, probablement relayé
                            if rssi == 0:
                                debug_print(f"Nœud {node_id} ignoré (pas de hopsAway, pas de RSSI)")
                                continue
                        
                        # Traiter le node_id - peut être string ou int
                        if isinstance(node_id, str):
                            if node_id.startswith('!'):
                                # Format !12345678 - retirer le ! puis convertir hex
                                clean_id = node_id[1:]
                                id_int = int(clean_id, 16)
                            elif node_id.isdigit():
                                # String numérique décimale
                                id_int = int(node_id)
                            else:
                                # Autres cas, essayer conversion hex directe
                                id_int = int(node_id, 16)
                        else:
                            # Déjà un int
                            id_int = int(node_id)
                        # Récupérer le nom - privilégier shortName
                        name = "Unknown"
                        short_name = None
                        if 'user' in node_info and isinstance(node_info['user'], dict):
                            user = node_info['user']
                            short_name = user.get('shortName', '')
                            long_name = user.get('longName', '')
                            
                            # Utiliser shortName en priorité, sinon longName tronqué
                            if short_name:
                                name = short_name
                            elif long_name:
                                name = long_name[:8]  # Tronquer à 8 caractères
                            else:
                                name = f"Node-{id_int:04x}"
                        
                        last_heard = node_info.get('lastHeard', 0)
                        
                        # Collecter les métriques de signal si activé
                        rssi = 0
                        snr = 0.0
                        if COLLECT_SIGNAL_METRICS:
                            rssi = node_info.get('rssi', 0)
                            snr = node_info.get('snr', 0.0)
                        
                        # FILTRE TEMPOREL : ne garder que les nœuds vus dans les 3 derniers jours
                        current_time = time.time()
                        three_days_ago = current_time - (3 * 24 * 3600)  # 3 jours en secondes
                        
                        if last_heard == 0 or last_heard < three_days_ago:
                            debug_print(f"Nœud {node_id} ignoré (trop ancien: {last_heard})")
                            continue
                        
                        node_data = {
                            'id': id_int,
                            'name': name,
                            'last_heard': last_heard
                        }
                        
                        # Ajouter les métriques si collectées
                        if COLLECT_SIGNAL_METRICS:
                            node_data['rssi'] = rssi
                            node_data['snr'] = snr
                        
                        node_list.append(node_data)
                        
                        debug_print(f"✅ Nœud direct: {name} RSSI:{rssi} SNR:{snr:.1f}")
                        
                except Exception as e:
                    debug_print(f"Erreur traitement nœud {node_id}: {e}")
                    continue
            
            remote_interface.close()
            debug_print(f"✅ {len(node_list)} nœuds DIRECTS récupérés de {remote_host}")
            return node_list
            
        except Exception as e:
            error_print(f"Erreur récupération nœuds distants {remote_host}: {e}")
            return []
    
    def format_tigrog2_nodes_report(self, page=1):
        """Formater un rapport des nœuds DIRECTS vus par tigrog2 avec pagination"""
        try:
            remote_nodes = self.get_remote_nodes(REMOTE_NODE_HOST)
            
            if not remote_nodes:
                return f"Aucun nœud direct trouvé sur {REMOTE_NODE_NAME}"
            
            # Trier par qualité de signal si disponible, sinon par dernière réception
            if COLLECT_SIGNAL_METRICS:
                remote_nodes.sort(key=lambda x: (x.get('rssi', -999), x['last_heard']), reverse=True)
            else:
                remote_nodes.sort(key=lambda x: x['last_heard'], reverse=True)
            
            # Calculer la taille moyenne d'une ligne pour déterminer le nombre par page
            sample_line = self._format_node_line(remote_nodes[0] if remote_nodes else {'name': 'Test', 'last_heard': time.time()})
            header_line = f"📡 Nœuds DIRECTS de {REMOTE_NODE_NAME} (<3j) (X/Y):"
            footer_line = "Page X/Y - '/tigrog2 X' pour suite"
            
            # Taille limite Meshtastic (environ 200 caractères sécurisé)
            max_message_size = 180
            base_overhead = len(header_line) + len(footer_line) + 20  # marge sécurité
            available_space = max_message_size - base_overhead
            avg_line_size = len(sample_line) + 1  # +1 pour le \n
            
            nodes_per_page = max(3, available_space // avg_line_size)  # Minimum 3 nœuds
            
            # Calculer la pagination
            total_nodes = len(remote_nodes)
            total_pages = (total_nodes + nodes_per_page - 1) // nodes_per_page
            
            # Valider la page demandée
            if page < 1:
                page = 1
            elif page > total_pages:
                page = total_pages
            
            # Extraire les nœuds pour cette page
            start_idx = (page - 1) * nodes_per_page
            end_idx = min(start_idx + nodes_per_page, total_nodes)
            page_nodes = remote_nodes[start_idx:end_idx]
            
            # Construire le rapport
            lines = []
            
            # Header seulement pour la page 1
            if page == 1:
                lines.append(f"📡 Nœuds DIRECTS de {REMOTE_NODE_NAME} (<3j) ({start_idx+1}-{end_idx}/{total_nodes}):")
            
            for node in page_nodes:
                line = self._format_node_line(node)
                lines.append(line)
            
            # Ajouter info pagination si nécessaire (format simplifié)
            if total_pages > 1:
                if page < total_pages:
                    lines.append(f"{page}/{total_pages}")
                else:
                    lines.append(f"{page}/{total_pages}")
            
            result = "\n".join(lines)
            
            # Vérification finale de taille (sécurité)
            if len(result) > max_message_size:
                # Réduction d'urgence : retirer des nœuds
                reduced_nodes = page_nodes[:max(1, len(page_nodes) - 1)]
                lines = lines[:len(reduced_nodes) + 1]  # Header + nœuds réduits
                if total_pages > 1:
                    lines.append(f"{page}/{total_pages}")
                result = "\n".join(lines)
            
            return result
            
        except Exception as e:
            error_print(f"Erreur format rapport {REMOTE_NODE_NAME}: {e}")
            return f"Erreur récupération {REMOTE_NODE_NAME}: {str(e)[:50]}"
    
    def get_tigrog2_paginated(self, page=1):
        """Récupérer et formater les nœuds tigrog2 avec pagination simple"""
        try:
            remote_nodes = self.get_remote_nodes(REMOTE_NODE_HOST)
            
            if not remote_nodes:
                return "Aucun nœud direct trouvé sur tigrog2"
            
            # Trier
            if COLLECT_SIGNAL_METRICS:
                remote_nodes.sort(key=lambda x: (x.get('rssi', -999), x['last_heard']), reverse=True)
            else:
                remote_nodes.sort(key=lambda x: x['last_heard'], reverse=True)
            
            # Calculer la pagination - plus simple
            nodes_per_page = 8  # Fixe, testé pour fonctionner dans les limites
            total_nodes = len(remote_nodes)
            total_pages = (total_nodes + nodes_per_page - 1) // nodes_per_page
            
            # Valider page
            if page < 1:
                page = 1
            elif page > total_pages:
                page = total_pages
            
            # Extraire nœuds pour cette page
            start_idx = (page - 1) * nodes_per_page
            end_idx = min(start_idx + nodes_per_page, total_nodes)
            page_nodes = remote_nodes[start_idx:end_idx]
            
            # Construire réponse
            lines = []
            
            # Header seulement page 1
            if page == 1:
                lines.append(f"📡 Nœuds DIRECTS de {REMOTE_NODE_NAME} (<3j) ({total_nodes}):")
            
            # Formater chaque nœud
            for node in page_nodes:
                short_name = node['name'][:8] if len(node['name']) > 8 else node['name']
                
                if node['last_heard'] > 0:
                    elapsed = int(time.time() - node['last_heard'])
                    if elapsed < 60:
                        time_str = f"{elapsed}s"
                    elif elapsed < 3600:
                        time_str = f"{elapsed//60}m"
                    elif elapsed < 86400:
                        time_str = f"{elapsed//3600}h"
                    else:
                        time_str = f"{elapsed//86400}j"
                else:
                    time_str = "n/a"
                
                # Indicateur de qualité RSSI
                rssi_icon = "📶"  # Par défaut
                if COLLECT_SIGNAL_METRICS and 'rssi' in node:
                    rssi = node['rssi']
                    if rssi >= -80:
                        rssi_icon = "🟢"
                    elif rssi >= -100:
                        rssi_icon = "🟡"
                    elif rssi >= -120:
                        rssi_icon = "🟠"
                    elif rssi < -120 and rssi != 0:
                        rssi_icon = "🔴"
                
                # Indicateur de qualité SNR
                snr_icon = ""
                if COLLECT_SIGNAL_METRICS and 'snr' in node:
                    snr = node['snr']
                    if snr >= 10:
                        snr_icon = "🔵"    # Excellent SNR
                    elif snr >= 5:
                        snr_icon = "🟣"    # Bon SNR
                    elif snr >= 0:
                        snr_icon = "🟤"    # SNR faible mais positif
                    elif snr < 0 and snr != 0:
                        snr_icon = "⚫"    # SNR négatif
                
                # Format de base : icône RSSI + icône SNR + nom court + temps
                line_parts = [rssi_icon]
                if snr_icon:
                    line_parts.append(snr_icon)
                line_parts.extend([short_name, time_str])
                
                if SHOW_RSSI and COLLECT_SIGNAL_METRICS and 'rssi' in node and node['rssi'] != 0:
                    line_parts.append(f"{node['rssi']}dB")
                
                if SHOW_SNR and COLLECT_SIGNAL_METRICS and 'snr' in node and node['snr'] != 0:
                    line_parts.append(f"SNR:{node['snr']:.1f}")
                
                lines.append(" ".join(line_parts))
            
            # Info pagination si nécessaire
            if total_pages > 1:
                lines.append(f"{page}/{total_pages}")
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"Erreur tigrog2: {str(e)[:30]}"
    
    def format_legend(self):
        """Formater la légende des indicateurs colorés - version compacte"""
        legend_lines = [
            "📶 Indicateurs:",
            "🟢🔵=excellent",
            "🟡🟣=bon", 
            "🟠🟤=faible",
            "🔴⚫=très faible",
            "1er=RSSI 2e=SNR"
        ]
        
        return "\n".join(legend_lines)
    
    def format_help(self):
        """Formater l'aide des commandes disponibles - version compacte"""
        help_lines = [
            "🤖 Commandes bot:",
            "/bot <question>",
            "/power",
            "/rx", 
            "/tigrog2 [page]",
            "/legend",
            "/help"
        ]
        
        return "\n".join(help_lines)
    
    def send_all_tigrog2_pages_simple(self, sender_id, sender_info):
        """Envoyer toutes les pages tigrog2 de façon simple"""
        try:
            # Déterminer nombre de pages
            remote_nodes = self.get_remote_nodes(REMOTE_NODE_HOST)
            if not remote_nodes:
                self.send_single_message("Aucun nœud direct trouvé sur tigrog2", sender_id, sender_info)
                return
            
            nodes_per_page = 8
            total_pages = (len(remote_nodes) + nodes_per_page - 1) // nodes_per_page
            
            debug_print(f"Envoi {total_pages} pages tigrog2 à {sender_info}")
            
            # Envoyer chaque page
            for page in range(1, total_pages + 1):
                report = self.get_tigrog2_paginated(page)
                self.send_single_message(report, sender_id, sender_info)
                
                if page < total_pages:
                    time.sleep(3)
                    
        except Exception as e:
            error_print(f"Erreur envoi pages tigrog2: {e}")
            # Fallback
            fallback = self.get_tigrog2_paginated(1)
            self.send_single_message(fallback, sender_id, sender_info)
        """Envoyer toutes les pages de tigrog2 avec délai entre chaque"""
        try:
            # D'abord déterminer le nombre total de pages
            remote_nodes = self.get_remote_nodes(REMOTE_NODE_HOST)
            if not remote_nodes:
                self.send_single_message("Aucun nœud direct trouvé sur tigrog2", sender_id, sender_info)
                return
            
            # Calculer le nombre de pages
            sample_line = self._format_node_line(remote_nodes[0] if remote_nodes else {'name': 'Test', 'last_heard': time.time()})
            header_line = f"📡 Nœuds DIRECTS de {REMOTE_NODE_NAME} (<3j) (X/Y):"
            
            max_message_size = 180
            base_overhead = len(header_line) + 20  # Pour page 1 avec header
            available_space = max_message_size - base_overhead
            avg_line_size = len(sample_line) + 1
            
            nodes_per_page = max(3, available_space // avg_line_size)
            total_pages = (len(remote_nodes) + nodes_per_page - 1) // nodes_per_page
            
            debug_print(f"Envoi de {total_pages} pages à {sender_info}")
            
            # Envoyer chaque page avec un délai
            for page in range(1, total_pages + 1):
                report = self.format_tigrog2_nodes_report(page)
                self.send_single_message(report, sender_id, sender_info)
                
                # Délai entre les pages (sauf la dernière)
                if page < total_pages:
                    time.sleep(3)  # 3 secondes entre chaque page
                    
            debug_print(f"Toutes les pages envoyées à {sender_info}")
            
        except Exception as e:
            error_print(f"Erreur envoi pages multiples: {e}")
            # Fallback: envoyer juste la page 1
            report = self.format_tigrog2_nodes_report(1)
            self.send_single_message(report, sender_id, sender_info)
        """Formater une ligne de nœud selon la configuration"""
        # Le nom est déjà le shortName ou longName tronqué depuis get_remote_nodes
        short_name = node['name'][:8] if len(node['name']) > 8 else node['name']
        
        # Calculer le temps écoulé
        if node['last_heard'] > 0:
            elapsed = int(time.time() - node['last_heard'])
            if elapsed < 60:
                time_str = f"{elapsed}s"
            elif elapsed < 3600:
                time_str = f"{elapsed//60}m"
            elif elapsed < 86400:
                time_str = f"{elapsed//3600}h"
            else:
                time_str = f"{elapsed//86400}j"
        else:
            time_str = "n/a"
        
        # Indicateur de qualité basé sur RSSI si disponible
        signal_icon = "📶"  # Par défaut
        if COLLECT_SIGNAL_METRICS and 'rssi' in node:
            rssi = node['rssi']
            if rssi >= -80:
                signal_icon = "🟢"
            elif rssi >= -100:
                signal_icon = "🟡"
            elif rssi >= -120:
                signal_icon = "🟠"
            elif rssi < -120 and rssi != 0:
                signal_icon = "🔴"
        
        # Format de base : icône + nom court + temps
        line_parts = [signal_icon, short_name, time_str]
        
        # Ajouter RSSI si activé et disponible
        if SHOW_RSSI and COLLECT_SIGNAL_METRICS and 'rssi' in node:
            rssi = node['rssi']
            if rssi != 0:
                line_parts.append(f"{rssi}dB")
        
        # Ajouter SNR si activé et disponible
        if SHOW_SNR and COLLECT_SIGNAL_METRICS and 'snr' in node:
            snr = node['snr']
            if snr != 0.0:
                line_parts.append(f"SNR:{snr:.1f}")
        
        return " ".join(line_parts)
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
                name = data['name'][:12] if len(data['name']) > 12 else data['name']  # Tronquer nom si trop long
                rssi = data['rssi']
                snr = data['snr']
                count = data['count']
                
                # Indicateur de qualité basé sur RSSI
                if rssi >= -80:
                    signal_icon = "🟢"  # Excellent
                elif rssi >= -100:
                    signal_icon = "🟡"  # Bon
                elif rssi >= -120:
                    signal_icon = "🟠"  # Faible
                else:
                    signal_icon = "🔴"  # Très faible
                
                # Temps depuis dernière réception
                elapsed = int(current_time - data['last_seen'])
                if elapsed < 60:
                    time_str = f"{elapsed}s"
                elif elapsed < 3600:
                    time_str = f"{elapsed//60}m"
                else:
                    time_str = f"{elapsed//3600}h"
                
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
            return f"Erreur génération rapport RX: {str(e)[:30]}"
    
    def periodic_update_thread(self):
        """Thread de mise à jour périodique"""
        while self.running:
            try:
                time.sleep(NODE_UPDATE_INTERVAL)
                if self.running:
                    self.update_node_database()
            except Exception as e:
                error_print(f"Erreur thread mise à jour: {e}")
    
    def list_known_nodes(self):
        """Lister tous les noeuds connus"""
        if not DEBUG_MODE:
            return
            
        print(f"\n📋 oeuds connus ({len(self.node_names)}):")
        print("-" * 60)
        for node_id, name in sorted(self.node_names.items()):
            print(f"  !{node_id:08x} -> {name}")
        print("-" * 60)
        
    def log_conversation(self, sender_id, sender_info, query, response, processing_time=None):
        """Log une conversation complète"""
        try:
            conversation_print("=" * 40)
            conversation_print(f"USER: {sender_info} (!{sender_id:08x})")
            conversation_print(f"QUERY: {query}")
            conversation_print(f"RESPONSE: {response}")
            if processing_time:
                conversation_print(f"TIME: {processing_time:.2f}s")
            conversation_print("=" * 40)
        except Exception as e:
            error_print(f"Erreur logging: {e}")
    
    def get_sender_info(self, sender_id):
        """Obtient les infos du sender avec cache de noms"""
        return self.get_node_name(sender_id)
        
    def test_llama(self):
        """Test du serveur llama - version allégée"""
        try:
            requests_module = lazy_import_requests()
            response = requests_module.get(f"http://{LLAMA_HOST}:{LLAMA_PORT}/health", timeout=3)
            success = response.status_code == 200
            del response
            if success:
                info_print("Serveur llama.cpp connecté")
            return success
        except Exception as e:
            error_print(f"Serveur llama.cpp inaccessible: {e}")
            return False
    
    def clean_ai_response(self, content):
        """Nettoie la réponse de l'IA - version optimisée mémoire"""
        try:
            debug_print(f"Nettoyage: '{content[:50]}...'")
            
            patterns = self._get_clean_patterns()
            for pattern in patterns:
                content = pattern.sub('', content)
            
            # Nettoyage efficace des espaces
            content = ' '.join(content.split())
            
            if not content or len(content.strip()) < 2:
                content = "Pas de réponse"
                
            debug_print(f"Nettoyé: '{content[:50]}...'")
            return content
            
        except Exception as e:
            debug_print(f"Erreur nettoyage: {e}")
            return content if content else "Erreur"
    
    def query_llama(self, prompt, node_id=None):
        """Requête au serveur llama avec contexte conversationnel"""
        try:
            requests_module = lazy_import_requests()
            debug_print(f"Envoi à llama: '{prompt[:30]}...'")
            
            # Construire les messages avec contexte
            messages = [
                {
                    "role": "system",
                    "content": "Tu es un assistant accessible via le réseau Meshtastic en LoRa. Réponds en français, très court, 320 caractères. Maintiens la continuité de la conversation."
                }
            ]
            
            # Ajouter le contexte conversationnel si disponible
            if node_id:
                context = self.get_conversation_context(node_id)
                if context:
                    debug_print(f"📚 Utilise contexte: {len(context)} messages pour {self.get_node_name(node_id)}")
                    # Ajouter les messages du contexte (en gardant l'ordre chronologique)
                    for ctx_msg in context:
                        messages.append({
                            "role": ctx_msg['role'],
                            "content": ctx_msg['content']
                        })
                else:
                    debug_print(f"🆕 Nouvelle conversation pour {self.get_node_name(node_id)}")
            
            # Ajouter la nouvelle question
            messages.append({
                "role": "user",
                "content": prompt
            })
            
            data = {
                "messages": messages,
                "max_tokens": 2000,
                "temperature": 0.7,  # Légèrement plus élevé pour plus de variété
                "top_p": 0.95,
                "top_k": 20
            }
            
            debug_print(f"📊 Messages envoyés: {len(messages)} (dont {len(messages)-2} contexte)")
            
            start_time = time.time()
            response = requests_module.post(f"http://{LLAMA_HOST}:{LLAMA_PORT}/v1/chat/completions", 
                                          json=data, timeout=60)
            end_time = time.time()
            
            debug_print(f"Temps: {end_time - start_time:.2f}s")
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content'].strip() if 'choices' in result else "Pas de réponse"
                
                # Sauvegarder dans le contexte
                if node_id:
                    self.add_to_context(node_id, 'user', prompt)
                    self.add_to_context(node_id, 'assistant', content)
                
                # Libérer immédiatement
                del response, result, data, messages
                gc.collect()
                
                return self.clean_ai_response(content)
            else:
                del response, data, messages
                return "Erreur serveur"
                
        except Exception as e:
            error_msg = f"Erreur IA: {str(e)[:30]}"
            error_print(error_msg)
            return error_msg
    
    def parse_esphome_data(self):
        """Parse ESPHome - version optimisée mémoire"""
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
                        data = resp.json()
                        if 'value' in data:
                            sensor_name = endpoint.split('/')[-1]
                            found_data[sensor_name] = data['value']
                        del data
                    del resp
                except:
                    continue
            
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
                return result[:180] if len(result) <= 180 else result[:177] + "..."
            else:
                return "ESPHome Online"
                
        except Exception as e:
            error_print(f"Erreur ESPHome: {e}")
            return f"ESPHome Error: {str(e)[:30]}"
    
    def send_response_chunks(self, response, sender_id, sender_info):
        """Divise et envoie - version simplifiée"""
        try:
            max_length = 180
            
            if len(response) <= max_length:
                self.send_single_message(response, sender_id, sender_info)
            else:
                # Division simple
                chunks = []
                for i in range(0, len(response), max_length-20):
                    chunk = response[i:i+max_length-20]
                    if i + max_length-20 < len(response):
                        chunk += "..."
                    chunks.append(chunk)
                
                for i, chunk in enumerate(chunks, 1):
                    if len(chunks) > 1:
                        formatted_chunk = f"({i}/{len(chunks)}) {chunk}"
                    else:
                        formatted_chunk = chunk
                    
                    self.send_single_message(formatted_chunk, sender_id, sender_info)
                    if i < len(chunks):
                        time.sleep(2)
                        
        except Exception as e:
            error_print(f"Erreur division: {e}")
            fallback = response[:max_length-3] + "..."
            self.send_single_message(fallback, sender_id, sender_info)
    
    def send_single_message(self, message, sender_id, sender_info):
        """Envoie un message - version simplifiée"""
        try:
            self.interface.sendText(message, destinationId=sender_id)
            debug_print(f"Message → {sender_info}")
        except Exception as e1:
            error_print(f"Échec envoi → {sender_info}: {e1}")
            # Plus de fallback sur 'dest' car ce paramètre n'existe plus
            # Essayer d'autres méthodes si nécessaire
            try:
                # Tentative avec le format hex string
                hex_id = f"!{sender_id:08x}"
                self.interface.sendText(message, destinationId=hex_id)
                debug_print(f"Message → {sender_info} (hex format)")
            except Exception as e2:
                error_print(f"Échec envoi définitif → {sender_info}: {e2}")
    
    def cleanup_cache(self):
        """Nettoyage périodique"""
        if len(self._response_cache) > self._max_cache_size:
            items = list(self._response_cache.items())
            self._response_cache = dict(items[-3:])
        
        # Nettoyage des contextes anciens
        self.cleanup_old_contexts()
        gc.collect()
    
    def format_timestamp(self):
        return datetime.now().strftime("%H:%M:%S")
    
    def on_message(self, packet, interface):
        """Gestionnaire des messages - version optimisée avec noms"""
        try:
            # Mise à jour de la base de nœuds depuis les packets NodeInfo
            self.update_node_from_packet(packet)
            
            # Mise à jour de l'historique RX pour tous les packets
            self.update_rx_history(packet)
            
            # Vérifier si message pour nous
            to_id = packet.get('to', 0)
            from_id = packet.get('from', 0)
            my_id = None
            
            if hasattr(self.interface, 'localNode') and self.interface.localNode:
                my_id = getattr(self.interface.localNode, 'nodeNum', 0)
                debug_print(f"Mon ID détecté: {my_id:08x}")
            else:
                debug_print("ATTENTION: localNode non disponible")
            
            is_for_me = (to_id == my_id) if my_id else False
            is_from_me = (from_id == my_id) if my_id else False
            is_broadcast = to_id in [0xFFFFFFFF, 0]  # Messages broadcast
            
            # CORRECTION: Ne filtrer qu'en mode debug ET seulement si ce n'est pas un message texte
            if DEBUG_MODE:
                debug_print(f"Packet: From:{from_id:08x} To:{to_id:08x} ForMe:{is_for_me} FromMe:{is_from_me} Broadcast:{is_broadcast}")
            
            # Ne traiter que si c'est pour nous, de nous, ou broadcast
            if not (is_for_me or is_from_me or is_broadcast):
                if DEBUG_MODE:
                    debug_print(f"Packet ignoré (pas pour nous)")
                return
            
            if 'decoded' not in packet:
                if DEBUG_MODE:
                    debug_print("Packet non décodé")
                return
            
            decoded = packet['decoded']
            portnum = decoded.get('portnum', '')
            
            # CORRECTION: Ne filtrer que APRÈS avoir vérifié que c'est un TEXT_MESSAGE_APP
            if portnum == 'TEXT_MESSAGE_APP':
                sender_name = self.get_node_name(from_id)
                debug_print(f"Message texte de {sender_name}")
                
                message = ""
                
                if 'text' in decoded:
                    message = decoded['text']
                elif 'payload' in decoded:
                    payload = decoded['payload']
                    if isinstance(payload, bytes):
                        try:
                            message = payload.decode('utf-8')
                        except UnicodeDecodeError:
                            message = payload.decode('utf-8', errors='replace')
                    else:
                        message = str(payload)
                
                sender_id = packet.get('from', 0)
                info_print(f"MESSAGE REÇU de {sender_name}: '{message}' (ForMe:{is_for_me})")
                
                # Traiter les commandes seulement si c'est pour nous
                is_private = is_for_me
                
                # Commandes
                if message.startswith('/bot '):
                    if not is_private:
                        if DEBUG_MODE:
                            debug_print("Commande /bot ignorée (message public)")
                        return
                    
                    prompt = message[5:].strip()
                    sender_info = self.get_sender_info(sender_id)
                    info_print(f"Bot: {sender_info}: '{prompt}'")
                    
                    if prompt:
                        start_time = time.time()
                        response = self.query_llama(prompt, sender_id)  # Passer le node_id pour le contexte
                        end_time = time.time()
                        
                        self.log_conversation(sender_id, sender_info, prompt, response, end_time - start_time)
                        self.send_response_chunks(response, sender_id, sender_info)
                        
                        # Nettoyage après traitement
                        self.cleanup_cache()
                    else:
                        self.interface.sendText("Usage: /bot <question>", destinationId=sender_id)
                        
                elif message.startswith('/power'):
                    if not is_private:
                        if DEBUG_MODE:
                            debug_print("Commande /power ignorée (message public)")
                        return
                    
                    sender_info = self.get_sender_info(sender_id)
                    info_print(f"Power: {sender_info}")
                    
                    esphome_data = self.parse_esphome_data()
                    self.log_conversation(sender_id, sender_info, "/power", esphome_data)
                    self.send_response_chunks(esphome_data, sender_id, sender_info)
                
                elif message.startswith('/tigrog2') or message.startswith('/tigro G2'):
                    if not is_private:
                        if DEBUG_MODE:
                            debug_print("Commande /tigrog2 ignorée (message public)")
                        return
                    
                    # Extraire le numéro de page - gérer les deux formats
                    page = 1
                    parts = message.split()
                    
                    if message.startswith('/tigro G2'):
                        # Format "/tigro G2 2" - la page est le 3ème élément
                        if len(parts) >= 3:
                            try:
                                page = int(parts[2])
                                if page < 1:
                                    page = 1
                            except ValueError:
                                page = 1
                    else:
                        # Format "/tigrog2 2" - la page est le 2ème élément
                        if len(parts) > 1:
                            try:
                                page = int(parts[1])
                                if page < 1:
                                    page = 1
                            except ValueError:
                                page = 1
                    
                    sender_info = self.get_sender_info(sender_id)
                    info_print(f"Tigrog2 Page {page}: {sender_info}")
                    
                    # Utiliser get_tigrog2_paginated qui fonctionne
                    try:
                        report = self.get_tigrog2_paginated(page)
                        self.log_conversation(sender_id, sender_info, f"/tigrog2 {page}" if page > 1 else "/tigrog2", report)
                        self.send_single_message(report, sender_id, sender_info)
                    except Exception as e:
                        error_msg = f"Erreur tigrog2 page {page}: {str(e)[:50]}"
                        self.send_single_message(error_msg, sender_id, sender_info)
                
                elif message.startswith('/rx'):
                    if not is_private:
                        if DEBUG_MODE:
                            debug_print("Commande /rx ignorée (message public)")
                        return
                    
                    sender_info = self.get_sender_info(sender_id)
                    info_print(f"RX Report: {sender_info}")
                    
                    rx_report = self.format_rx_report()
                    self.log_conversation(sender_id, sender_info, "/rx", rx_report)
                    self.send_response_chunks(rx_report, sender_id, sender_info)
                
                elif message.startswith('/legend'):
                    if not is_private:
                        if DEBUG_MODE:
                            debug_print("Commande /legend ignorée (message public)")
                        return
                    
                    sender_info = self.get_sender_info(sender_id)
                    info_print(f"Legend: {sender_info}")
                    
                    legend_text = self.format_legend()
                    self.log_conversation(sender_id, sender_info, "/legend", legend_text)
                    self.send_response_chunks(legend_text, sender_id, sender_info)
                
                elif message.startswith('/help'):
                    if not is_private:
                        if DEBUG_MODE:
                            debug_print("Commande /help ignorée (message public)")
                        return
                    
                    sender_info = self.get_sender_info(sender_id)
                    info_print(f"Help: {sender_info}")
                    
                    try:
                        help_text = self.format_help()
                        info_print(f"Help text généré: {len(help_text)} caractères")
                        self.log_conversation(sender_id, sender_info, "/help", help_text)
                        self.send_single_message(help_text, sender_id, sender_info)
                        info_print(f"Help envoyé à {sender_info}")
                    except Exception as e:
                        error_print(f"Erreur commande /help: {e}")
                        self.send_single_message("Erreur génération aide", sender_id, sender_info)
                else:
                    # Message normal (pas de commande)
                    if DEBUG_MODE:
                        debug_print(f"Message normal reçu: '{message}'")
            else:
                # Autres types de packets (télémétrie, etc.) - juste pour debug
                if DEBUG_MODE and portnum in ['TELEMETRY_APP', 'NODEINFO_APP', 'POSITION_APP']:
                    debug_print(f"Packet {portnum} de {self.get_node_name(from_id)}")
            
        except Exception as e:
            error_print(f"Erreur traitement: {e}")
            import traceback
            error_print(traceback.format_exc())
    
    def interactive_loop(self):
        """Boucle interactive avec gestion des noms"""
        if not DEBUG_MODE:
            return
            
        while self.running:
            try:
                command = input(f"\n[{self.format_timestamp()}] > ")
                
                if command.lower() in ['quit', 'exit', 'q']:
                    self.running = False
                    break
                elif command.startswith('test '):
                    prompt = command[5:]
                    info_print(f"TEST: '{prompt}'")
                    response = self.query_llama(prompt)  # Sans contexte pour les tests
                    info_print(f"→ {response}")
                elif command == 'context':
                    # Nouvelle commande pour voir les contextes actifs
                    info_print("📚 Contextes conversationnels:")
                    if not self.conversation_context:
                        info_print("  Aucun contexte actif")
                    else:
                        for node_id, context in self.conversation_context.items():
                            name = self.get_node_name(node_id)
                            info_print(f"  {name} (!{node_id:08x}): {len(context)} messages")
                elif command.startswith('bot '):
                    question = command[4:]
                    bot_command = f"/bot {question}"
                    info_print(f"Envoi: '{bot_command}'")
                    self.interface.sendText(bot_command)
                elif command == 'power':
                    info_print("TEST ESPHome:")
                    data = self.parse_esphome_data()
                    info_print(f"→ {data}")
                elif command == 'rx':
                    info_print("TEST RX Report:")
                    report = self.format_rx_report()
                    info_print(f"→ {report}")
                elif command == 'legend':
                    info_print("TEST Legend:")
                    legend = self.format_legend()
                    info_print(f"→ {legend}")
                elif command == 'help':
                    info_print("TEST Help:")
                    help_text = self.format_help()
                    info_print(f"→ {help_text}")
                elif command.startswith('config '):
                    # Nouvelle commande pour changer la configuration d'affichage
                    parts = command.split(' ')
                    if len(parts) >= 3:
                        option = parts[1].lower()
                        value = parts[2].lower() == 'true'
                        
                        global SHOW_RSSI, SHOW_SNR, COLLECT_SIGNAL_METRICS
                        if option == 'rssi':
                            SHOW_RSSI = value
                            info_print(f"SHOW_RSSI = {SHOW_RSSI}")
                        elif option == 'snr':
                            SHOW_SNR = value
                            info_print(f"SHOW_SNR = {SHOW_SNR}")
                        elif option == 'collect':
                            COLLECT_SIGNAL_METRICS = value
                            info_print(f"COLLECT_SIGNAL_METRICS = {COLLECT_SIGNAL_METRICS}")
                        else:
                            info_print("Options: rssi, snr, collect")
                    else:
                        info_print(f"Config actuelle - RSSI:{SHOW_RSSI} SNR:{SHOW_SNR} COLLECT:{COLLECT_SIGNAL_METRICS}")
                        info_print("Usage: config <option> <true/false>")
                elif command.startswith('tigrog2'):
                    # Test tigrog2 avec pagination
                    parts = command.split()
                    page = 1
                    
                    if len(parts) > 1:
                        try:
                            page = int(parts[1])
                        except ValueError:
                            page = 1
                    
                    info_print(f"TEST Tigrog2 Page {page}")
                    try:
                        report = self.get_tigrog2_paginated(page)
                        info_print(f"→ {report}")
                    except Exception as e:
                        info_print(f"→ Erreur: {e}")
                elif command.startswith('nodes '):
                    # Test de récupération nœuds distants
                    parts = command.split(' ', 1)
                    if len(parts) > 1:
                        remote_host = parts[1].strip()
                        info_print(f"TEST Remote Nodes: {remote_host}")
                        report = self.format_remote_nodes_report(remote_host)
                        info_print(f"→ {report}")
                    else:
                        info_print("Usage: nodes <IP_du_noeud>")
                elif command == 'nodes':
                    self.list_known_nodes()
                elif command == 'update':
                    self.update_node_database()
                elif command == 'save':
                    self.save_node_names(force=True)
                elif command == 'reload':
                    self.load_node_names()
                elif command == 'mem':
                    # Commande de debug mémoire
                    try:
                        import psutil
                        import os
                        process = psutil.Process(os.getpid())
                        memory_mb = process.memory_info().rss / 1024 / 1024
                        active_contexts = len(self.conversation_context)
                        total_messages = sum(len(ctx) for ctx in self.conversation_context.values())
                        info_print(f"Mémoire: {memory_mb:.1f}MB, Nœuds: {len(self.node_names)}, Contextes: {active_contexts} ({total_messages} msgs)")
                    except:
                        active_contexts = len(self.conversation_context)
                        total_messages = sum(len(ctx) for ctx in self.conversation_context.values())
                        info_print(f"Nœuds: {len(self.node_names)}, Contextes: {active_contexts} ({total_messages} messages)")
                elif command == 'help':
                    print("Commandes:")
                    print("  test <prompt>  - Test llama.cpp")
                    print("  bot <question> - Via Meshtastic")
                    print("  power          - Test ESPHome")
                    print("  rx             - Rapport signaux reçus")
                    print("  legend         - Légende des indicateurs")
                    print("  help           - Cette aide")
                    print("  tigrog2 [page] - Nœuds de tigrog2 (page 1-4)")
                    print("  config         - Voir config affichage")
                    print("  config <opt> <true/false> - Changer config")
                    print("  nodes          - Lister nœuds connus")
                    print("  nodes <IP>     - Nœuds d'un nœud distant")
                    print("  context        - Voir contextes actifs")
                    print("  update         - Mise à jour base nœuds")
                    print("  save           - Sauvegarder base nœuds")
                    print("  reload         - Recharger base nœuds")
                    print("  mem            - Mémoire utilisée")
                    print("  quit           - Quitter")
                else:
                    print("Tapez 'help'")
                    
            except KeyboardInterrupt:
                self.running = False
                break
            except Exception as e:
                info_print(f"Erreur: {e}")
    
    def start(self):
        """Démarrage - version optimisée avec noms"""
        info_print("Bot Meshtastic-Llama avec noms de nœuds")
        
        # Charger la base de nœuds
        self.load_node_names()
        
        # Nettoyage initial
        gc.collect()
        
        if not self.test_llama():
            error_print("llama.cpp requis")
            return False
        
        try:
            info_print(f"Connexion {SERIAL_PORT}...")
            self.interface = meshtastic.serial_interface.SerialInterface(SERIAL_PORT)
            time.sleep(3)
            
            info_print("Interface Meshtastic OK")
            
            # Mise à jour initiale de la base
            self.update_node_database()
            
            pub.subscribe(self.on_message, "meshtastic.receive")
            self.running = True
            
            # Démarrer le thread de mise à jour périodique
            self.update_thread = threading.Thread(target=self.periodic_update_thread, daemon=True)
            self.update_thread.start()
            info_print(f"⏰ Mise à jour périodique démarrée (toutes les {NODE_UPDATE_INTERVAL//60}min)")
            
            if DEBUG_MODE:
                info_print("MODE DEBUG avec noms de nœuds et contexte")
                print(f"Config: RSSI={SHOW_RSSI} SNR={SHOW_SNR} COLLECT={COLLECT_SIGNAL_METRICS}")
                print("\nCommandes: test, bot, power, rx, legend, help, tigrog2, config, nodes, context, update, save, mem, quit")
                threading.Thread(target=self.interactive_loop, daemon=True).start()
            else:
                info_print("Bot en service - '/bot', '/power', '/rx', '/legend', '/help' et '/tigrog2' avec contexte")
            
            # Boucle principale avec nettoyage périodique
            cleanup_counter = 0
            while self.running:
                time.sleep(1)
                cleanup_counter += 1
                if cleanup_counter % 300 == 0:  # Toutes les 5 minutes
                    self.cleanup_cache()
                
        except Exception as e:
            error_print(f"Erreur: {e}")
            return False
    
    def stop(self):
        info_print("Arrêt...")
        self.running = False
        
        # Sauvegarder avant fermeture
        self.save_node_names(force=True)
        
        if self.interface:
            self.interface.close()
        gc.collect()
        info_print("Bot arrêté")

def main():
    global DEBUG_MODE
    
    parser = argparse.ArgumentParser(description='Bot Meshtastic-Llama avec noms')
    parser.add_argument('--debug', '-d', action='store_true', help='Mode debug')
    parser.add_argument('--quiet', '-q', action='store_true', help='Mode silencieux')
    args = parser.parse_args()
    
    DEBUG_MODE = args.debug
    
    if args.quiet:
        class QuietLogger:
            def write(self, msg):
                if 'ERROR' in msg:
                    sys.__stdout__.write(msg)
                    sys.__stdout__.flush()
            def flush(self):
                pass
        sys.stdout = QuietLogger()
    
    # Nettoyage initial
    gc.collect()
    
    bot = DebugMeshBot()
    try:
        bot.start()
    except KeyboardInterrupt:
        if DEBUG_MODE:
            info_print("Interruption")
    finally:
        bot.stop()

if __name__ == "__main__":
    main()
