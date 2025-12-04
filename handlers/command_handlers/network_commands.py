#!/usr/bin/env python3
import traceback
# -*- coding: utf-8 -*-
"""
Gestionnaire des commandes réseau et nœuds
"""

import time
import threading
import meshtastic.tcp_interface
from config import *
from utils import *
from .signal_utils import *

class NetworkCommands:
    def __init__(self, remote_nodes_client, sender, node_manager, traffic_monitor=None, interface=None, mesh_traceroute=None, broadcast_tracker=None):
        self.remote_nodes_client = remote_nodes_client
        self.sender = sender
        self.node_manager = node_manager
        self.traffic_monitor = traffic_monitor
        self.interface = interface
        self.mesh_traceroute = mesh_traceroute
        self.broadcast_tracker = broadcast_tracker  # Callback pour tracker broadcasts
    
    def handle_nodes(self, message, sender_id, sender_info):  
        """Gérer la commande /nodes - Liste des nœuds directs avec pagination"""
        
        # Extraire le numéro de page si fourni
        page = 1
        parts = message.split()
        
        if len(parts) > 1:
            try:
                page = int(parts[1])
                page = max(1, page)  # Minimum page 1
            except ValueError:
                page = 1
        
        info_print(f"Nodes page {page}: {sender_info}")
        
        try:
            # Utiliser la pagination
            report = self.remote_nodes_client.get_tigrog2_paginated(page)
            
            # Log avec ou sans page
            command_log = f"/nodes {page}" if page > 1 else "/nodes"
            self.sender.log_conversation(sender_id, sender_info, command_log, report)
            self.sender.send_single(report, sender_id, sender_info)
            
        except Exception as e:
            error_msg = f"Erreur nodes: {str(e)[:50]}"
            self.sender.send_single(error_msg, sender_id, sender_info)

    def handle_my(self, sender_id, sender_info, is_broadcast=False):
        """Gérer la commande /my - Afficher vos signaux vus par votre node"""
        info_print(f"My: {sender_info}")

        # Capturer le sender actuel pour le thread (important pour CLI!)
        current_sender = self.sender

        def get_remote_signal_info():
            try:
                remote_nodes = self.remote_nodes_client.get_remote_nodes(REMOTE_NODE_HOST)
                
                if not remote_nodes:
                    response = f"⚠️ {REMOTE_NODE_NAME} inaccessible"
                    current_sender.send_single(response, sender_id, sender_info)
                    return

                # Normaliser l'ID
                sender_id_normalized = sender_id & 0xFFFFFFFF

                # Chercher le nœud
                sender_node_data = None
                for node in remote_nodes:
                    node_id_normalized = node['id'] & 0xFFFFFFFF
                    if node_id_normalized == sender_id_normalized:
                        sender_node_data = node
                        break

                if sender_node_data:
                    response = self._format_my_response(sender_node_data)
                else:
                    response = self._format_my_not_found(remote_nodes)

                if is_broadcast:
                    # Réponse publique sans préfixe (utilisateur sait déjà qui il est)
                    self._send_broadcast_via_tigrog2(response, sender_id, sender_info, "/my")
                else:
                    # Réponse privée
                    current_sender.log_conversation(sender_id, sender_info, "/my", response)
                    current_sender.send_single(response, sender_id, sender_info)

            except Exception as e:
                error_print(f"Erreur commande /my: {e}")
                error_print(traceback.format_exc())
                try:
                    error_response = f"⚠️ Erreur: {str(e)[:30]}"
                    current_sender.send_single(error_response, sender_id, sender_info)
                except:
                    pass
        
        threading.Thread(target=get_remote_signal_info, daemon=True, name="RemoteSignalInfo").start()
    
    def _format_my_response(self, node_data):
        """Formater la réponse /my pour un nœud trouvé"""
        response_parts = []
        
        rssi = node_data.get('rssi', 0)
        snr = node_data.get('snr', 0.0)
        
        # Estimation RSSI depuis SNR si nécessaire
        display_rssi = rssi
        rssi_estimated = False
        
        if rssi == 0 and snr != 0:
            display_rssi = estimate_rssi_from_snr(snr)
            rssi_estimated = True
        
        # RSSI + SNR
        if display_rssi != 0 or snr != 0:
            rssi_icon = get_signal_quality_icon(display_rssi) if display_rssi != 0 else "📶"
            
            rssi_str = f"~{display_rssi}dBm" if rssi_estimated else f"{display_rssi}dBm" if display_rssi != 0 else "n/a"
            snr_str = f"SNR:{snr:.1f}dB" if snr != 0 else "SNR:n/a"
            response_parts.append(f"{rssi_icon} {rssi_str} {snr_str}")
        else:
            response_parts.append("📶 Signal: n/a")
        
        # Qualité + temps
        quality_desc = get_signal_quality_description(display_rssi, snr)
        last_heard = node_data.get('last_heard', 0)
        if last_heard > 0:
            time_str = format_elapsed_time(last_heard)
            response_parts.append(f"📈 {quality_desc} ({time_str})")
        else:
            response_parts.append(f"📈 {quality_desc}")
        
        distance_shown = False
        if self.node_manager:
            # L'ID du nœud est dans node_data (vient de tigrog2)
            node_id = node_data.get('id')
            if node_id:
                try:
                    gps_distance = self.node_manager.get_node_distance(node_id)
                    if gps_distance:
                        distance_str = self.node_manager.format_distance(gps_distance)
                        response_parts.append(f"📍 {distance_str} de {REMOTE_NODE_NAME} (GPS)")
                        distance_shown = True
                except Exception:
                    pass  # Silent fail, pas critique

        # Si pas de distance GPS, utiliser l'estimation RSSI
        if not distance_shown and display_rssi != 0 and display_rssi > -150:
            distance_est = estimate_distance_from_rssi(display_rssi)
            response_parts.append(f"📍 ~{distance_est} de {REMOTE_NODE_NAME} (estimé)")


        # Distance estimée
        if display_rssi != 0 and display_rssi > -150:
            distance_est = estimate_distance_from_rssi(display_rssi)
            response_parts.append(f"📍 ~{distance_est} de {REMOTE_NODE_NAME}")
        
        # Statut liaison directe
        response_parts.append(f"🎯 Direct → {REMOTE_NODE_NAME}")
        
        return " | ".join(response_parts)
    
    def _format_my_not_found(self, remote_nodes):
        """Formater la réponse /my pour un nœud non trouvé"""
        response_parts = [
            f"⚠️ Pas direct → {REMOTE_NODE_NAME}",
            "🔀 Messages relayés"
        ]
        
        # Suggérer relays potentiels
        potential_relays = find_best_relays(remote_nodes)
        if potential_relays:
            best_relay = potential_relays[0]
            response_parts.append(f"📡 Via réseau mesh")
            response_parts.append(f"   (ex: {truncate_text(best_relay['name'], 8)})")
        else:
            response_parts.append("❓ Route mesh complexe")
        
        return "\n".join(response_parts)
    
    def handle_neighbors(self, message, sender_id, sender_info):
        """
        Gérer la commande /neighbors - Afficher les voisins mesh
        
        Usage:
        - /neighbors : Tous les voisins (format compact pour LoRa)
        - /neighbors <node> : Filtrer par nom/ID de nœud
        """
        info_print(f"Neighbors: {sender_info}")
        
        # Vérifier si traffic_monitor est disponible
        if not self.traffic_monitor:
            error_msg = "⚠️ Traffic monitor non disponible"
            self.sender.send_single(error_msg, sender_id, sender_info)
            return
        
        # Extraire le filtre optionnel
        parts = message.split(maxsplit=1)
        node_filter = parts[1].strip() if len(parts) > 1 else None
        
        # Déterminer le format (compact pour mesh, détaillé pour autres)
        # On suppose que si le sender_info contient 'telegram' ou 'cli', c'est détaillé
        sender_str = str(sender_info).lower()
        compact = 'telegram' not in sender_str and 'cli' not in sender_str
        
        try:
            # Générer le rapport
            report = self.traffic_monitor.get_neighbors_report(
                node_filter=node_filter,
                compact=compact
            )
            
            # Construire la commande pour les logs
            command_log = f"/neighbors {node_filter}" if node_filter else "/neighbors"
            
            # Envoyer la réponse
            self.sender.log_conversation(sender_id, sender_info, command_log, report)
            
            if compact:
                # Pour LoRa, envoyer tel quel (déjà optimisé pour 180 chars)
                self.sender.send_single(report, sender_id, sender_info)
            else:
                # Pour Telegram/CLI, peut être plus long
                self.sender.send_chunks(report, sender_id, sender_info)
            
        except Exception as e:
            error_print(f"Erreur commande /neighbors: {e}")
            error_print(traceback.format_exc())
            error_msg = f"⚠️ Erreur: {str(e)[:30]}"
            self.sender.send_single(error_msg, sender_id, sender_info)
    
    def _send_broadcast_via_tigrog2(self, message, sender_id, sender_info, command):
        """
        Envoyer un message en broadcast via l'interface partagée
        
        Note: Utilise l'interface existante au lieu de créer une nouvelle connexion TCP.
        Cela évite les conflits de socket avec la connexion principale.
        """
        try:
            # Récupérer l'interface partagée (évite de créer une nouvelle connexion TCP)
            interface = self.sender._get_interface()
            
            if interface is None:
                error_print(f"❌ Interface non disponible pour broadcast {command}")
                return
            
            # Tracker le broadcast AVANT l'envoi pour éviter boucle
            if self.broadcast_tracker:
                self.broadcast_tracker(message)
            
            debug_print(f"📡 Broadcast {command} via interface partagée...")
            
            # Utiliser l'interface partagée - PAS de nouvelle connexion TCP!
            interface.sendText(message)
            
            info_print(f"✅ Broadcast {command} diffusé")
            self.sender.log_conversation(sender_id, sender_info, command, message)
            
        except Exception as e:
            error_print(f"❌ Échec broadcast {command}: {e}")
            error_print(traceback.format_exc())

    def handle_trace(self, message, sender_id, sender_info, packet):
        """
        Gérer la commande /trace - Traceroute mesh avec TRACEROUTE_APP natif

        Deux modes disponibles:
        - /trace → Mode passif: analyse le packet reçu (hops, signal)
        - /trace <node_name> → Mode actif: traceroute natif Meshtastic vers le nœud

        Le mode actif utilise TRACEROUTE_APP pour obtenir la route complète.
        """
        info_print(f"Trace: {sender_info}")

        # Parser l'argument (node name ou ID)
        parts = message.split()
        target_node_name = parts[1].strip() if len(parts) > 1 else None

        # Mode actif: traceroute natif vers un nœud spécifique
        if target_node_name:
            info_print(f"🔍 Traceroute actif vers: {target_node_name}")

            # Vérifier si mesh_traceroute est disponible
            try:
                mesh_traceroute = getattr(self, 'mesh_traceroute', None)
                if not mesh_traceroute:
                    # Fallback: utiliser l'ancienne méthode (affichage infos statiques)
                    info_print("⚠️  MeshTracerouteManager non disponible, fallback mode passif")
                    self._handle_trace_passive_target(target_node_name, sender_id, sender_info)
                    return

                # Chercher le node_id du nœud cible
                # Chercher d'abord dans node_manager (SQLite DB) pour éviter les appels TCP inutiles
                matching_nodes = []
                exact_matches = []
                target_search = target_node_name.lower()

                # PRIORITÉ 1: Chercher dans node_manager.node_names (SQLite DB - pas de TCP)
                if self.node_manager and hasattr(self.node_manager, 'node_names'):
                    for node_id, node_data in self.node_manager.node_names.items():
                        node_name = node_data.get('name', '').lower()
                        node_id_hex = f"{node_id:x}".lower()
                        
                        # Vérifier correspondance exacte d'abord
                        if target_search == node_name or target_search == node_id_hex:
                            exact_matches.append({
                                'id': node_id,
                                'name': node_data.get('name', f"Node-{node_id:08x}")
                            })
                        # Sinon correspondance partielle
                        elif target_search in node_name or target_search in node_id_hex:
                            matching_nodes.append({
                                'id': node_id,
                                'name': node_data.get('name', f"Node-{node_id:08x}")
                            })

                # PRIORITÉ 2: Si aucun résultat dans node_manager, chercher via TCP (remote_nodes)
                # Ceci évite les cache miss inutiles quand les nodes sont déjà en DB
                if len(exact_matches) == 0 and len(matching_nodes) == 0:
                    debug_print("🔍 Aucun nœud trouvé dans node_manager, recherche via TCP...")
                    remote_nodes = self.remote_nodes_client.get_remote_nodes(REMOTE_NODE_HOST)
                    if not remote_nodes:
                        self.sender.send_single(f"❌ Nœud '{target_node_name}' introuvable", sender_id, sender_info)
                        return

                    # Chercher dans remote_nodes
                    for node in remote_nodes:
                        node_name = node.get('name', '').lower()
                        node_id_hex = f"{node['id']:x}".lower()

                        # Vérifier correspondance exacte d'abord
                        if target_search == node_name or target_search == node_id_hex:
                            exact_matches.append(node)
                        # Sinon correspondance partielle
                        elif target_search in node_name or target_search in node_id_hex:
                            matching_nodes.append(node)

                # Priorité aux correspondances exactes
                if len(exact_matches) == 1:
                    # Une seule correspondance exacte: utiliser directement
                    target_node = exact_matches[0]
                    target_node_id = target_node['id']
                elif len(exact_matches) > 1:
                    # Plusieurs correspondances exactes: afficher la liste
                    all_matches = exact_matches
                elif len(exact_matches) == 0 and len(matching_nodes) == 1:
                    # Une seule correspondance partielle: utiliser directement
                    target_node = matching_nodes[0]
                    target_node_id = target_node['id']
                elif len(exact_matches) == 0 and len(matching_nodes) > 1:
                    # Plusieurs correspondances partielles: afficher la liste
                    all_matches = matching_nodes
                else:
                    # Aucune correspondance
                    self.sender.send_single(f"❌ Nœud '{target_node_name}' introuvable", sender_id, sender_info)
                    return

                # Si on a défini all_matches, afficher la liste
                if 'all_matches' in locals():
                    max_display = min(5, len(all_matches))
                    response_lines = [f"🔍 Plusieurs nœuds trouvés ({len(all_matches)}):"]
                    
                    for i, node in enumerate(all_matches[:max_display]):
                        node_name = node.get('name', 'Unknown')
                        node_id = node['id']
                        response_lines.append(f"{i+1}. {node_name} (!{node_id:08x})")
                    
                    if len(all_matches) > max_display:
                        response_lines.append(f"... et {len(all_matches) - max_display} autres")
                    
                    response_lines.append("Précisez le nom complet ou l'ID")
                    
                    response = "\n".join(response_lines)
                    self.sender.send_chunks(response, sender_id, sender_info)
                    return

                # Si on arrive ici, target_node et target_node_id sont définis (une seule correspondance)

                # Lancer le traceroute natif
                info_print(f"🚀 Lancement traceroute natif vers 0x{target_node_id:08x}")

                # Besoin de l'interface pour envoyer le paquet
                interface = getattr(self, 'interface', None)
                if not interface:
                    self.sender.send_single("❌ Interface non disponible", sender_id, sender_info)
                    return

                # Envoyer la requête de traceroute
                success = mesh_traceroute.request_traceroute(
                    interface=interface,
                    target_node_id=target_node_id,
                    requester_id=sender_id,
                    requester_info=sender_info
                )

                if not success:
                    self.sender.send_single("❌ Erreur envoi traceroute", sender_id, sender_info)

            except Exception as e:
                error_print(f"❌ Erreur traceroute actif: {e}")
                error_print(traceback.format_exc())
                self.sender.send_single(f"❌ Erreur: {str(e)[:50]}", sender_id, sender_info)

        else:
            # Mode passif: analyser le packet reçu (comportement original)
            self._handle_trace_passive_sender(packet, sender_id, sender_info)

    def _handle_trace_passive_sender(self, packet, sender_id, sender_info):
        """
        Traceroute passif: analyse le paquet reçu pour estimer le chemin

        Args:
            packet: Paquet reçu
            sender_id: ID de l'émetteur
            sender_info: Infos de l'émetteur
        """
        try:
            # Extraire données packet
            hop_limit = packet.get('hopLimit', 0)
            hop_start = packet.get('hopStart', 5)
            rssi = packet.get('rssi', 0)
            snr = packet.get('snr', 0.0)
            hops_taken = hop_start - hop_limit

            # Construire rapport compact
            lines = []
            lines.append(f"🔍 {sender_info}")

            # CAS 1: DIRECT (0 hop)
            if hops_taken == 0:
                lines.append("✅ Direct (0 hop)")

                if rssi != 0 or snr != 0:
                    icon = get_signal_quality_icon(rssi) if rssi != 0 else "📶"
                    rssi_str = f"{rssi}dBm" if rssi != 0 else "n/a"
                    snr_str = f"SNR:{snr:.1f}" if snr != 0 else "n/a"
                    quality = get_signal_quality_description(rssi, snr)
                    lines.append(f"{icon} {rssi_str} {snr_str}")
                    lines.append(f"{quality}")

                    if rssi != 0 and rssi > -150:
                        dist = estimate_distance_from_rssi(rssi)
                        lines.append(f"~{dist}")

            # CAS 2: RELAYÉ (1+ hops)
            else:
                lines.append(f"🔀 Relayé ({hops_taken} hop{'s' if hops_taken > 1 else ''})")

                if rssi != 0 or snr != 0:
                    icon = get_signal_quality_icon(rssi) if rssi != 0 else "📶"
                    rssi_str = f"{rssi}dBm" if rssi != 0 else "n/a"
                    snr_str = f"SNR:{snr:.1f}" if snr != 0 else "n/a"
                    lines.append(f"{icon} {rssi_str} {snr_str}")

                # Analyse topologie
                try:
                    remote_nodes = self.remote_nodes_client.get_remote_nodes(REMOTE_NODE_HOST)

                    if remote_nodes:
                        # Chercher émetteur dans tigrog2
                        sender_id_norm = sender_id & 0xFFFFFFFF
                        in_tigrog2 = any(
                            (node['id'] & 0xFFFFFFFF) == sender_id_norm
                            for node in remote_nodes
                        )

                        if in_tigrog2:
                            lines.append(f"Via {REMOTE_NODE_NAME}")
                        else:
                            lines.append(f"Hors portée {REMOTE_NODE_NAME}")

                        # Top 2 relays potentiels
                        relays = find_best_relays(remote_nodes, max_relays=2)
                        if relays:
                            lines.append("Relays:")
                            for relay in relays:
                                name = truncate_text(relay['name'], 10)
                                r_rssi = relay.get('rssi', 0)
                                r_icon = get_signal_quality_icon(r_rssi)
                                if r_rssi != 0:
                                    lines.append(f"{r_icon}{name}:{r_rssi}dBm")
                                else:
                                    lines.append(f"{r_icon}{name}")
                except Exception:
                    pass  # Silent fail pour topologie

            response = "\n".join(lines)

            self.sender.log_conversation(sender_id, sender_info, "/trace", response)
            self.sender.send_chunks(response, sender_id, sender_info)

            info_print(f"✅ Trace→{sender_info}")

        except Exception as e:
            error_print(f"Erreur /trace passif: {e}")
            try:
                self.sender.send_single(f"⚠️ Erreur trace", sender_id, sender_info)
            except:
                pass

    def _handle_trace_passive_target(self, target_node_name, sender_id, sender_info):
        """
        Traceroute passif vers une cible: affiche infos statiques du nœud

        Args:
            target_node_name: Nom du nœud cible
            sender_id: ID du requester
            sender_info: Infos du requester
        """
        try:
            # Chercher le nœud dans tigrog2
            remote_nodes = self.remote_nodes_client.get_remote_nodes(REMOTE_NODE_HOST)

            if not remote_nodes:
                self.sender.send_single(f"⚠️ {REMOTE_NODE_NAME} inaccessible", sender_id, sender_info)
                return

            # Chercher le nœud par nom (partiel) ou ID
            target_node = None
            target_search = target_node_name.lower()

            for node in remote_nodes:
                node_name = node.get('name', '').lower()
                node_id_hex = f"{node['id']:x}".lower()

                # Correspondance par nom (partiel) ou ID (partiel)
                if target_search in node_name or target_search in node_id_hex:
                    target_node = node
                    break

            if not target_node:
                self.sender.send_single(f"❌ Nœud '{target_node_name}' introuvable", sender_id, sender_info)
                return

            # Afficher les infos du nœud cible (ancien comportement)
            response = self._format_trace_target(target_node)
            self.sender.send_chunks(response, sender_id, sender_info)
            self.sender.log_conversation(sender_id, sender_info, f"/trace {target_node_name}", response)

        except Exception as e:
            error_print(f"Erreur /trace passif cible: {e}")
            self.sender.send_single(f"⚠️ Erreur", sender_id, sender_info)

    def _format_trace_target(self, node_data):
        """
        Formater les infos de traceroute pour un nœud cible

        Args:
            node_data: Données du nœud depuis tigrog2

        Returns:
            str: Rapport formaté
        """
        lines = []

        # Header avec nom du nœud
        node_name = node_data.get('name', 'Unknown')
        node_id = node_data.get('id', 0)
        lines.append(f"🔍 {node_name} (!{node_id:08x})")

        # Signal
        rssi = node_data.get('rssi', 0)
        snr = node_data.get('snr', 0.0)

        # Estimation RSSI depuis SNR si nécessaire
        display_rssi = rssi
        rssi_estimated = False

        if rssi == 0 and snr != 0:
            display_rssi = estimate_rssi_from_snr(snr)
            rssi_estimated = True

        # Afficher signal si disponible
        if display_rssi != 0 or snr != 0:
            icon = get_signal_quality_icon(display_rssi) if display_rssi != 0 else "📶"
            rssi_str = f"~{display_rssi}dBm" if rssi_estimated else f"{display_rssi}dBm" if display_rssi != 0 else "n/a"
            snr_str = f"SNR:{snr:.1f}dB" if snr != 0 else "n/a"
            quality = get_signal_quality_description(display_rssi, snr)

            lines.append(f"{icon} {rssi_str} | {snr_str}")
            lines.append(f"📈 {quality}")

            # Distance estimée
            if display_rssi != 0 and display_rssi > -150:
                distance_est = estimate_distance_from_rssi(display_rssi)
                lines.append(f"📍 ~{distance_est} de {REMOTE_NODE_NAME}")
        else:
            lines.append("📶 Signal: n/a")

        # Statut direct
        lines.append(f"✅ Direct → {REMOTE_NODE_NAME}")

        # Last heard
        last_heard = node_data.get('last_heard', 0)
        if last_heard > 0:
            time_str = format_elapsed_time(last_heard)
            lines.append(f"⏱️ Vu il y a {time_str}")

        # Distance GPS si disponible
        if self.node_manager:
            node_id = node_data.get('id')
            if node_id:
                try:
                    gps_distance = self.node_manager.get_node_distance(node_id)
                    if gps_distance:
                        distance_str = self.node_manager.format_distance(gps_distance)
                        lines.append(f"🌐 {distance_str} (GPS)")
                except Exception:
                    pass  # Silent fail

        return "\n".join(lines)

