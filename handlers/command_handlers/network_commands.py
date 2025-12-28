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
                
                # Nettoyer l'input utilisateur:
                # - Enlever les espaces
                # - Enlever le préfixe ! (convention Meshtastic pour les IDs)
                # - Enlever le suffixe ) (du copy-paste depuis les suggestions du bot)
                target_search = target_node_name.strip().lower()
                target_search = target_search.lstrip('!')
                target_search = target_search.rstrip(')')

                # PRIORITÉ 1: Chercher dans node_manager.node_names (SQLite DB - pas de TCP)
                if self.node_manager and hasattr(self.node_manager, 'node_names'):
                    for node_id, node_data in self.node_manager.node_names.items():
                        node_name = node_data.get('name', '').lower()
                        # Support both formats: with and without leading zeros
                        node_id_hex = f"{node_id:x}".lower()  # Without padding (e.g., "de3331e")
                        node_id_hex_padded = f"{node_id:08x}".lower()  # With padding (e.g., "0de3331e")
                        
                        # Vérifier correspondance exacte d'abord
                        if target_search == node_name or target_search == node_id_hex or target_search == node_id_hex_padded:
                            exact_matches.append({
                                'id': node_id,
                                'name': node_data.get('name', f"Node-{node_id:08x}")
                            })
                        # Sinon correspondance partielle
                        elif target_search in node_name or target_search in node_id_hex or target_search in node_id_hex_padded:
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
                        # Support both formats: with and without leading zeros
                        node_id_hex = f"{node['id']:x}".lower()  # Without padding
                        node_id_hex_padded = f"{node['id']:08x}".lower()  # With padding

                        # Vérifier correspondance exacte d'abord
                        if target_search == node_name or target_search == node_id_hex or target_search == node_id_hex_padded:
                            exact_matches.append(node)
                        # Sinon correspondance partielle
                        elif target_search in node_name or target_search in node_id_hex or target_search in node_id_hex_padded:
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
            
            # Nettoyer l'input utilisateur (même logique que handle_trace actif)
            target_search = target_node_name.strip().lower()
            target_search = target_search.lstrip('!')
            target_search = target_search.rstrip(')')

            for node in remote_nodes:
                node_name = node.get('name', '').lower()
                # Support both formats: with and without leading zeros
                node_id_hex = f"{node['id']:x}".lower()  # Without padding
                node_id_hex_padded = f"{node['id']:08x}".lower()  # With padding

                # Correspondance par nom (partiel) ou ID (partiel)
                if target_search in node_name or target_search in node_id_hex or target_search in node_id_hex_padded:
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
    
    def handle_propag(self, message, sender_id, sender_info, is_broadcast=False):
        """
        Gérer la commande /propag - Afficher les plus longues liaisons radio
        
        Usage:
            /propag [hours] [top_n]
            
        Exemples:
            /propag          → Top 5 liaisons des dernières 24h
            /propag 48       → Top 5 liaisons des dernières 48h
            /propag 24 10    → Top 10 liaisons des dernières 24h
        
        Args:
            message: Message complet (ex: "/propag", "/propag 48", "/propag 24 10")
            sender_id: ID de l'expéditeur
            sender_info: Infos sur l'expéditeur
            is_broadcast: Si True, répondre en broadcast public
        """
        if not self.traffic_monitor:
            error_msg = "❌ TrafficMonitor non disponible"
            if is_broadcast:
                self._send_broadcast_via_tigrog2(error_msg, sender_id, sender_info, "/propag")
            else:
                self.sender.send_single(error_msg, sender_id, sender_info)
            return
        
        info_print(f"Propag: {sender_info} (broadcast={is_broadcast})")
        
        # Parser les arguments
        parts = message.split()
        hours = 24
        top_n = 5
        
        try:
            if len(parts) >= 2:
                hours = int(parts[1])
                hours = max(1, min(72, hours))  # Limiter entre 1 et 72h
            if len(parts) >= 3:
                top_n = int(parts[2])
                top_n = max(1, min(10, top_n))  # Limiter entre 1 et 10
        except ValueError:
            error_msg = "❌ Usage: /propag [hours] [top_n]"
            if is_broadcast:
                self._send_broadcast_via_tigrog2(error_msg, sender_id, sender_info, "/propag")
            else:
                self.sender.send_single(error_msg, sender_id, sender_info)
            return
        
        # Déterminer le format (compact pour mesh/broadcast, détaillé pour Telegram/CLI)
        sender_str = str(sender_info).lower()
        compact = is_broadcast or ('telegram' not in sender_str and 'cli' not in sender_str)
        
        try:
            # Générer le rapport
            report = self.traffic_monitor.get_propagation_report(
                hours=hours,
                top_n=top_n,
                max_distance_km=100,  # Rayon de 100km comme spécifié
                compact=compact
            )
            
            # Construire la commande pour les logs
            if hours != 24 or top_n != 5:
                command_log = f"/propag {hours} {top_n}"
            else:
                command_log = "/propag"
            
            # Envoyer la réponse
            if is_broadcast:
                # Réponse publique via broadcast
                self._send_broadcast_via_tigrog2(report, sender_id, sender_info, command_log)
            else:
                # Réponse privée
                self.sender.log_conversation(sender_id, sender_info, command_log, report)
                
                if compact:
                    # Pour LoRa, envoyer tel quel (déjà optimisé pour 180 chars)
                    self.sender.send_single(report, sender_id, sender_info)
                else:
                    # Pour Telegram/CLI, peut être plus long
                    self.sender.send_chunks(report, sender_id, sender_info)
            
        except Exception as e:
            error_print(f"Erreur commande /propag: {e}")
            error_print(traceback.format_exc())
            error_msg = f"⚠️ Erreur: {str(e)[:30]}"
            if is_broadcast:
                self._send_broadcast_via_tigrog2(error_msg, sender_id, sender_info, "/propag")
            else:
                self.sender.send_single(error_msg, sender_id, sender_info)
    
    def handle_info(self, message, sender_id, sender_info, is_broadcast=False):
        """
        Gérer la commande /info <node> - Afficher les informations complètes d'un nœud
        
        Usage:
            /info <node_name> ou /info <node_id>
        
        Exemples:
            /info tigro
            /info F547F
            /info !12345678
        
        Informations affichées:
            - Nom du nœud (longName, shortName, hwModel)
            - Position GPS (latitude, longitude, altitude)
            - Distance depuis le bot (GPS ou estimée)
            - Signal (RSSI, SNR, qualité)
            - Dernière réception (last heard)
            - Statistiques mesh (paquets, types, télémétrie)
        
        Format adaptatif:
            - Compact pour mesh (≤180 chars)
            - Détaillé pour Telegram/CLI
        """
        info_print(f"Info: {sender_info}")
        
        # Parser le nom/ID du nœud
        parts = message.split(maxsplit=1)
        if len(parts) < 2:
            error_msg = "Usage: /info <node_name>"
            self.sender.send_single(error_msg, sender_id, sender_info)
            return
        
        target_node_name = parts[1].strip()
        
        # Déterminer le format (compact pour mesh, détaillé pour autres)
        sender_str = str(sender_info).lower()
        compact = 'telegram' not in sender_str and 'cli' not in sender_str
        
        # Capturer le sender actuel pour le thread (important pour CLI!)
        current_sender = self.sender
        
        def get_node_info():
            try:
                # Chercher le nœud par nom ou ID
                target_node = self._find_node(target_node_name)
                
                if not target_node:
                    error_msg = f"❌ Nœud '{target_node_name}' introuvable"
                    current_sender.send_single(error_msg, sender_id, sender_info)
                    return
                
                # Récupérer les statistiques mesh du nœud
                node_stats = None
                if self.traffic_monitor:
                    node_id = target_node.get('id')
                    if node_id and hasattr(self.traffic_monitor, 'node_packet_stats'):
                        node_stats = self.traffic_monitor.node_packet_stats.get(node_id)
                
                # Formater la réponse selon le format
                if compact:
                    response = self._format_info_compact(target_node, node_stats)
                else:
                    response = self._format_info_detailed(target_node, node_stats)
                
                # Envoyer la réponse
                if is_broadcast:
                    # Réponse publique en broadcast
                    self._send_broadcast_via_tigrog2(response, sender_id, sender_info, f"/info {target_node_name}")
                else:
                    # Réponse privée
                    command_log = f"/info {target_node_name}"
                    current_sender.log_conversation(sender_id, sender_info, command_log, response)
                    
                    if compact:
                        current_sender.send_single(response, sender_id, sender_info)
                    else:
                        current_sender.send_chunks(response, sender_id, sender_info)
                
                info_print(f"✅ Info '{target_node_name}' envoyée à {sender_info}")
                
            except Exception as e:
                error_print(f"Erreur commande /info: {e}")
                error_print(traceback.format_exc())
                error_msg = f"⚠️ Erreur: {str(e)[:30]}"
                current_sender.send_single(error_msg, sender_id, sender_info)
        
        # Lancer dans un thread pour ne pas bloquer
        threading.Thread(target=get_node_info, daemon=True, name="NodeInfo").start()
    
    def _find_node(self, search_term):
        """
        Chercher un nœud par nom ou ID
        
        Args:
            search_term: Nom du nœud ou ID (partiel ou complet)
        
        Returns:
            dict: Données du nœud trouvé, ou None si non trouvé
        """
        # Nettoyer l'input utilisateur
        target_search = search_term.strip().lower()
        target_search = target_search.lstrip('!')
        target_search = target_search.rstrip(')')
        
        matching_nodes = []
        exact_matches = []
        
        # PRIORITÉ 1: Chercher dans node_manager.node_names (SQLite DB - pas de TCP)
        if self.node_manager and hasattr(self.node_manager, 'node_names'):
            for node_id, node_data in self.node_manager.node_names.items():
                node_name = node_data.get('name', '').lower()
                node_id_hex = f"{node_id:x}".lower()
                node_id_hex_padded = f"{node_id:08x}".lower()
                
                # Vérifier correspondance exacte
                if target_search == node_name or target_search == node_id_hex or target_search == node_id_hex_padded:
                    # Enrichir avec l'ID numérique
                    result = node_data.copy()
                    result['id'] = node_id
                    exact_matches.append(result)
                # Correspondance partielle
                elif target_search in node_name or target_search in node_id_hex or target_search in node_id_hex_padded:
                    result = node_data.copy()
                    result['id'] = node_id
                    matching_nodes.append(result)
        
        # PRIORITÉ 2: Si aucun résultat local, chercher via TCP (remote_nodes)
        if len(exact_matches) == 0 and len(matching_nodes) == 0:
            debug_print(f"🔍 Aucun nœud trouvé localement, recherche via TCP...")
            remote_nodes = self.remote_nodes_client.get_remote_nodes(REMOTE_NODE_HOST)
            if remote_nodes:
                for node in remote_nodes:
                    node_name = node.get('name', '').lower()
                    node_id_hex = f"{node['id']:x}".lower()
                    node_id_hex_padded = f"{node['id']:08x}".lower()
                    
                    if target_search == node_name or target_search == node_id_hex or target_search == node_id_hex_padded:
                        exact_matches.append(node)
                    elif target_search in node_name or target_search in node_id_hex or target_search in node_id_hex_padded:
                        matching_nodes.append(node)
        
        # PRIORITÉ 3: Si toujours aucun résultat, chercher dans interface.nodes (en mémoire)
        # Ceci permet de trouver les nœuds détectés par la radio mais pas encore dans la base de données
        if len(exact_matches) == 0 and len(matching_nodes) == 0:
            if self.interface and hasattr(self.interface, 'nodes'):
                nodes = getattr(self.interface, 'nodes', {})
                for node_id, node_info in nodes.items():
                    if not isinstance(node_info, dict):
                        continue
                    
                    # Convertir node_id en int si string
                    if isinstance(node_id, str):
                        try:
                            if node_id.startswith('!'):
                                node_id_int = int(node_id[1:], 16)
                            else:
                                node_id_int = int(node_id, 16) if 'x' not in node_id else int(node_id, 0)
                        except ValueError:
                            continue
                    else:
                        node_id_int = node_id
                    
                    # Get node name from user info
                    user_info = node_info.get('user', {}) if isinstance(node_info, dict) else {}
                    node_name = (user_info.get('longName') or user_info.get('shortName') or f"Node-{node_id_int:08x}").lower()
                    node_id_hex = f"{node_id_int:x}".lower()
                    node_id_hex_padded = f"{node_id_int:08x}".lower()
                    
                    if target_search == node_name or target_search == node_id_hex or target_search == node_id_hex_padded:
                        result = {'name': user_info.get('longName') or user_info.get('shortName') or f"Node-{node_id_int:08x}", 'id': node_id_int}
                        exact_matches.append(result)
                    elif target_search in node_name or target_search in node_id_hex or target_search in node_id_hex_padded:
                        result = {'name': user_info.get('longName') or user_info.get('shortName') or f"Node-{node_id_int:08x}", 'id': node_id_int}
                        matching_nodes.append(result)
        
        # Retourner le résultat
        if len(exact_matches) == 1:
            return exact_matches[0]
        elif len(exact_matches) == 0 and len(matching_nodes) == 1:
            return matching_nodes[0]
        elif len(exact_matches) > 1 or len(matching_nodes) > 1:
            # Ambiguïté: retourner le premier (ou on pourrait lister les options)
            all_matches = exact_matches if exact_matches else matching_nodes
            debug_print(f"⚠️ Plusieurs nœuds correspondent à '{search_term}', utilisation du premier")
            return all_matches[0]
        
        return None
    
    def _format_info_compact(self, node_data, node_stats=None):
        """
        Formater les infos du nœud de manière compacte pour mesh (≤180 chars)
        
        Args:
            node_data: Données du nœud
            node_stats: Statistiques mesh optionnelles
        
        Returns:
            str: Rapport compact
        """
        parts = []
        
        # Nom du nœud
        node_name = node_data.get('name', 'Unknown')
        node_id = node_data.get('id', 0)
        parts.append(f"ℹ️ {truncate_text(node_name, 15)} (!{node_id:08x})")
        
        # Position GPS si disponible
        lat = node_data.get('lat') or node_data.get('latitude')
        lon = node_data.get('lon') or node_data.get('longitude')
        alt = node_data.get('alt') or node_data.get('altitude')
        
        if lat is not None and lon is not None:
            parts.append(f"📍 {lat:.4f},{lon:.4f}")
            if alt is not None:
                parts.append(f"⛰️ {int(alt)}m")
        else:
            parts.append("📍 GPS n/a")
        
        # Distance GPS depuis le bot
        if self.node_manager and node_id:
            try:
                gps_distance = self.node_manager.get_node_distance(node_id)
                if gps_distance:
                    distance_str = self.node_manager.format_distance(gps_distance)
                    parts.append(f"↔️ {distance_str}")
            except Exception:
                pass
        
        # Hops (distance réseau)
        hops_away = node_data.get('hops_away')
        if hops_away is not None:
            if hops_away == 0:
                parts.append("✅ Direct")
            else:
                parts.append(f"🔀 {hops_away}hop{'s' if hops_away > 1 else ''}")
        
        # Signal (RSSI/SNR) si disponible
        rssi = node_data.get('rssi', 0)
        snr = node_data.get('snr', 0.0)
        
        if rssi != 0 or snr != 0:
            icon = get_signal_quality_icon(snr) if snr != 0 else "📶"
            rssi_str = f"{rssi}dB" if rssi != 0 else ""
            snr_str = f"SNR{snr:.1f}" if snr != 0 else ""
            signal_parts = [s for s in [rssi_str, snr_str] if s]
            if signal_parts:
                parts.append(f"{icon} {' '.join(signal_parts)}")
        
        # Last heard
        last_heard = node_data.get('last_heard', 0)
        if last_heard > 0:
            time_str = format_elapsed_time(last_heard)
            parts.append(f"⏱️ {time_str}")
        
        # Stats mesh (compactes)
        if node_stats:
            total_packets = node_stats.get('total_packets', 0)
            if total_packets > 0:
                parts.append(f"📊 {total_packets}pkt")
        
        # Assembler en une seule ligne compacte
        return " | ".join(parts)
    
    def _format_info_detailed(self, node_data, node_stats=None):
        """
        Formater les infos du nœud de manière détaillée pour Telegram/CLI
        
        Args:
            node_data: Données du nœud
            node_stats: Statistiques mesh optionnelles
        
        Returns:
            str: Rapport détaillé
        """
        lines = []
        
        # === HEADER ===
        node_name = node_data.get('name', 'Unknown')
        node_id = node_data.get('id', 0)
        lines.append(f"ℹ️ INFORMATIONS NŒUD")
        lines.append(f"━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"📛 Nom: {node_name}")
        lines.append(f"🆔 ID: !{node_id:08x} (0x{node_id:08x})")
        
        # ShortName et HwModel si disponibles
        short_name = node_data.get('shortName')
        hw_model = node_data.get('hwModel')
        if short_name:
            lines.append(f"🏷️ Short: {short_name}")
        if hw_model:
            lines.append(f"🖥️ Model: {hw_model}")
        
        lines.append("")
        
        # === POSITION GPS ===
        lat = node_data.get('lat') or node_data.get('latitude')
        lon = node_data.get('lon') or node_data.get('longitude')
        alt = node_data.get('alt') or node_data.get('altitude')
        
        if lat is not None and lon is not None:
            lines.append("📍 POSITION GPS")
            lines.append(f"   Latitude: {lat:.6f}")
            lines.append(f"   Longitude: {lon:.6f}")
            if alt is not None:
                lines.append(f"   Altitude: {int(alt)}m")
            
            # Distance GPS depuis le bot
            if self.node_manager and node_id:
                try:
                    gps_distance = self.node_manager.get_node_distance(node_id)
                    if gps_distance:
                        distance_str = self.node_manager.format_distance(gps_distance)
                        lines.append(f"   Distance: {distance_str}")
                except Exception:
                    pass
            
            lines.append("")
        else:
            lines.append("📍 POSITION GPS: Non disponible")
            lines.append("")
        
        # === SIGNAL ===
        rssi = node_data.get('rssi', 0)
        snr = node_data.get('snr', 0.0)
        
        if rssi != 0 or snr != 0:
            lines.append("📶 SIGNAL")
            
            # Estimation RSSI depuis SNR si nécessaire
            display_rssi = rssi
            rssi_estimated = False
            if rssi == 0 and snr != 0:
                display_rssi = estimate_rssi_from_snr(snr)
                rssi_estimated = True
            
            if display_rssi != 0:
                rssi_str = f"~{display_rssi}dBm" if rssi_estimated else f"{display_rssi}dBm"
                quality = get_signal_quality_description(display_rssi, snr)
                icon = get_signal_quality_icon(snr) if snr != 0 else "📶"
                lines.append(f"   RSSI: {rssi_str} {icon}")
                lines.append(f"   Qualité: {quality}")
            
            if snr != 0:
                lines.append(f"   SNR: {snr:.1f} dB")
            
            # Distance estimée depuis RSSI
            if display_rssi != 0 and display_rssi > -150:
                distance_est = estimate_distance_from_rssi(display_rssi)
                lines.append(f"   Distance (est): {distance_est}")
            
            lines.append("")
        
        # === HOPS (DISTANCE RÉSEAU) ===
        hops_away = node_data.get('hops_away')
        if hops_away is not None:
            lines.append("🔀 DISTANCE RÉSEAU")
            if hops_away == 0:
                lines.append("   ✅ Connexion directe (0 hop)")
                lines.append("   Le nœud est dans la portée radio directe")
            else:
                lines.append(f"   🔀 Relayé ({hops_away} hop{'s' if hops_away > 1 else ''})")
                lines.append(f"   Le message passe par {hops_away} nœud{'s' if hops_away > 1 else ''} intermédiaire{'s' if hops_away > 1 else ''}")
            lines.append("")
        
        # === DERNIÈRE RÉCEPTION ===
        last_heard = node_data.get('last_heard', 0)
        if last_heard > 0:
            time_str = format_elapsed_time(last_heard)
            lines.append(f"⏱️ DERNIÈRE RÉCEPTION: {time_str}")
            lines.append("")
        
        # === STATISTIQUES MESH ===
        if node_stats:
            lines.append("📊 STATISTIQUES MESH")
            
            total_packets = node_stats.get('total_packets', 0)
            lines.append(f"   Paquets totaux: {total_packets}")
            
            # Stats par type
            by_type = node_stats.get('by_type', {})
            if by_type:
                lines.append("   Types de paquets:")
                # Top 5 types
                sorted_types = sorted(by_type.items(), key=lambda x: x[1], reverse=True)
                for pkt_type, count in sorted_types[:5]:
                    # Safe attribute access with fallback
                    type_name = pkt_type
                    if self.traffic_monitor and hasattr(self.traffic_monitor, 'packet_type_names'):
                        type_name = self.traffic_monitor.packet_type_names.get(pkt_type, pkt_type)
                    lines.append(f"     • {type_name}: {count}")
            
            # Stats télémétrie
            telemetry = node_stats.get('telemetry_stats', {})
            if telemetry and telemetry.get('count', 0) > 0:
                lines.append("   Télémétrie:")
                if telemetry.get('last_battery') is not None:
                    lines.append(f"     • Batterie: {telemetry['last_battery']}%")
                if telemetry.get('last_voltage') is not None:
                    lines.append(f"     • Voltage: {telemetry['last_voltage']:.2f}V")
            
            # First/last seen
            first_seen = node_stats.get('first_seen')
            last_seen = node_stats.get('last_seen')
            if first_seen:
                first_str = format_elapsed_time(first_seen)
                lines.append(f"   Premier vu: {first_str}")
            if last_seen:
                last_str = format_elapsed_time(last_seen)
                lines.append(f"   Dernier vu: {last_str}")
        
        return "\n".join(lines)
    
    def handle_keys(self, message, sender_id, sender_info):
        """
        Gérer la commande /keys - Diagnostiquer l'état des clés publiques
        
        Cette commande aide à résoudre les problèmes de messages DM encryptés
        dans Meshtastic 2.7.15+ qui nécessite l'échange de clés publiques PKI.
        
        Usage:
            /keys [node_name]
            
        Sans argument: Affiche l'état global des clés
        Avec nom de nœud: Vérifie si ce nœud a échangé sa clé publique
        
        Exemples:
            /keys
            /keys tigro
            /keys F547F
        """
        info_print(f"Keys: {sender_info}")
        
        # Parser le nom/ID du nœud optionnel
        parts = message.split(maxsplit=1)
        target_node_name = parts[1].strip() if len(parts) > 1 else None
        
        # Déterminer le format (compact pour mesh, détaillé pour autres)
        sender_str = str(sender_info).lower()
        compact = 'telegram' not in sender_str and 'cli' not in sender_str
        
        # Capturer le sender actuel pour le thread (important pour CLI!)
        current_sender = self.sender
        
        def check_keys():
            try:
                if target_node_name:
                    # Vérifier les clés d'un nœud spécifique
                    response = self._check_node_keys(target_node_name, compact)
                else:
                    # Afficher l'état global des clés
                    response = self._check_all_keys(compact)
                
                # Envoyer la réponse
                command_log = f"/keys {target_node_name}" if target_node_name else "/keys"
                current_sender.log_conversation(sender_id, sender_info, command_log, response)
                
                if compact:
                    current_sender.send_single(response, sender_id, sender_info)
                else:
                    current_sender.send_chunks(response, sender_id, sender_info)
                
                info_print(f"✅ Keys info envoyée à {sender_info}")
                
            except Exception as e:
                error_print(f"Erreur commande /keys: {e}")
                error_print(traceback.format_exc())
                error_msg = f"⚠️ Erreur: {str(e)[:30]}"
                current_sender.send_single(error_msg, sender_id, sender_info)
        
        # Lancer dans un thread pour ne pas bloquer
        threading.Thread(target=check_keys, daemon=True, name="KeysCheck").start()
    
    def _check_node_keys(self, search_term, compact=False):
        """
        Vérifier les clés publiques d'un nœud spécifique
        
        Args:
            search_term: Nom du nœud ou ID
            compact: Si True, format court pour mesh (≤180 chars)
            
        Returns:
            str: Rapport sur les clés du nœud
        """
        # Chercher le nœud
        target_node = self._find_node(search_term)
        
        if not target_node:
            return f"❌ Nœud '{search_term}' introuvable"
        
        node_name = target_node.get('name', 'Unknown')
        node_id = target_node.get('id')
        
        if not node_id:
            return f"❌ ID du nœud '{node_name}' introuvable"
        
        # Vérifier si l'interface est disponible
        if not self.interface or not hasattr(self.interface, 'nodes'):
            return "⚠️ Interface non disponible"
        
        # Vérifier les clés dans interface.nodes - essayer plusieurs formats de clés
        # interface.nodes peut utiliser différents formats: int, str, "!hex", "hex"
        nodes = getattr(self.interface, 'nodes', {})
        node_info = None
        search_keys = [node_id, str(node_id), f"!{node_id:08x}", f"{node_id:08x}"]
        
        debug_print(f"DEBUG /keys {search_term}: Trying keys {search_keys[:2]}... for node_id={node_id}")
        
        for key in search_keys:
            if key in nodes:
                node_info = nodes[key]
                debug_print(f"DEBUG /keys {search_term}: FOUND with key={key} (type={type(key).__name__})")
                break
        
        if node_info is None:
            debug_print(f"DEBUG /keys {search_term}: NOT FOUND in interface.nodes with any key format")
        
        if not node_info:
            # Le nœud est connu (dans node_manager) mais pas dans interface.nodes
            # Cela signifie que l'interface n'a pas reçu de NODEINFO de ce nœud
            if compact:
                return f"⚠️ {node_name}: Pas de NODEINFO reçu"
            else:
                lines = []
                lines.append(f"⚠️ Nœud {node_name} (0x{node_id:08x})")
                lines.append("")
                lines.append("ℹ️ Statut:")
                lines.append("   • Nœud connu (messages reçus)")
                lines.append("   • NODEINFO non reçu par l'interface")
                lines.append("   • Clé publique non disponible")
                lines.append("")
                lines.append("💡 Solution:")
                lines.append("   1. Attendre réception automatique NODEINFO")
                lines.append("   2. Ou demander NODEINFO:")
                lines.append(f"      meshtastic --request-telemetry --dest {node_id:08x}")
                lines.append("")
                lines.append("⚠️ Sans NODEINFO:")
                lines.append("   • Pas d'accès à la clé publique")
                lines.append("   • DM resteront encryptés si envoyés")
                return "\n".join(lines)
        
        # Extraire les informations utilisateur
        user_info = node_info.get('user', {}) if isinstance(node_info, dict) else {}
        # Try both field names: 'public_key' (protobuf) and 'publicKey' (dict)
        public_key = None
        if isinstance(user_info, dict):
            public_key = user_info.get('public_key') or user_info.get('publicKey')
        
        if compact:
            # Format court pour mesh
            if public_key:
                key_preview = public_key[:8] if isinstance(public_key, str) else "présente"
                return f"✅ {node_name}: Clé OK ({key_preview}...)"
            else:
                return f"❌ {node_name}: Pas de clé publique"
        else:
            # Format détaillé pour Telegram/CLI
            lines = []
            lines.append(f"🔑 État des clés pour: {node_name}")
            lines.append(f"   Node ID: 0x{node_id:08x}")
            lines.append("")
            
            if public_key:
                lines.append("✅ Clé publique: PRÉSENTE")
                if isinstance(public_key, str):
                    # Afficher preview de la clé
                    lines.append(f"   Preview: {public_key[:16]}...")
                    lines.append(f"   Longueur: {len(public_key)} chars")
                elif isinstance(public_key, bytes):
                    lines.append(f"   Type: bytes")
                    lines.append(f"   Longueur: {len(public_key)} bytes")
                lines.append("")
                lines.append("✅ Vous POUVEZ:")
                lines.append("   • Recevoir des DM de ce nœud")
                lines.append("   • Échanger des messages encryptés PKI")
            else:
                lines.append("❌ Clé publique: MANQUANTE")
                lines.append("")
                lines.append("⚠️ Vous NE POUVEZ PAS:")
                lines.append("   • Recevoir des DM de ce nœud")
                lines.append("   • Les DM apparaîtront comme ENCRYPTED")
                lines.append("")
                lines.append("💡 Solution:")
                lines.append("   1. Attendre l'échange automatique de clés")
                lines.append("   2. Demander un NODEINFO au nœud:")
                lines.append(f"      meshtastic --request-telemetry --dest {node_id:08x}")
                lines.append("   3. Vérifier que le nœud est en 2.5.0+")
            
            return "\n".join(lines)
    
    def _check_all_keys(self, compact=False):
        """
        Vérifier l'état des clés publiques pour les nœuds vus dans le trafic
        
        Affiche uniquement les nœuds qui ont été vus dans le trafic récent (48h)
        mais n'ont pas de clé publique disponible localement.
        
        Args:
            compact: Si True, format court pour mesh (≤180 chars)
            
        Returns:
            str: Rapport sur les nœuds sans clés
        """
        # Vérifier si l'interface est disponible
        if not self.interface or not hasattr(self.interface, 'nodes'):
            return "⚠️ Interface non disponible"
        
        # Obtenir les nœuds vus dans le trafic récent (depuis traffic_monitor)
        nodes_in_traffic = set()
        if self.traffic_monitor:
            try:
                # Obtenir les paquets des dernières 48h
                packets = self.traffic_monitor.persistence.load_packets(hours=48)
                for packet in packets:
                    from_id = packet.get('from_id')
                    if from_id:
                        nodes_in_traffic.add(from_id)
            except Exception as e:
                debug_print(f"⚠️ Erreur lecture trafic: {e}")
        
        if not nodes_in_traffic:
            return "⚠️ Aucun trafic récent détecté"
        
        # Vérifier les clés dans interface.nodes pour les nœuds vus
        nodes = getattr(self.interface, 'nodes', {})
        nodes_without_keys = []
        nodes_with_keys_count = 0
        
        # CRITICAL DEBUG: Log interface.nodes state when /keys runs
        debug_print(f"DEBUG /keys: interface.nodes has {len(nodes)} entries")
        debug_print(f"DEBUG /keys: Checking {len(nodes_in_traffic)} nodes from traffic")
        if len(nodes) > 0:
            sample_keys = list(nodes.keys())[:3]
            debug_print(f"DEBUG /keys: Sample node IDs in interface.nodes: {sample_keys}")
            for node_key in sample_keys:
                node_info = nodes[node_key]
                if isinstance(node_info, dict):
                    user_info = node_info.get('user', {})
                    if isinstance(user_info, dict):
                        has_key = user_info.get('public_key') or user_info.get('publicKey')
                        debug_print(f"DEBUG /keys: Node {node_key} has key: {bool(has_key)}")
        
        # DEBUG: Log first few nodes being checked
        debug_count = 0
        
        for node_id in nodes_in_traffic:
            # Normaliser node_id (peut être int ou string)
            # IMPORTANT: Traffic DB stores node IDs as decimal TEXT, not hex!
            if isinstance(node_id, str):
                try:
                    if node_id.startswith('!'):
                        # Format "!a2e175ac" → hex parsing
                        node_id_int = int(node_id[1:], 16)
                    elif 'x' in node_id.lower():
                        # Format "0xa2e175ac" → hex parsing
                        node_id_int = int(node_id, 0)
                    else:
                        # Format "2732684716" → decimal string from DB
                        node_id_int = int(node_id)
                except ValueError:
                    continue
            else:
                node_id_int = node_id
            
            # Chercher dans interface.nodes - essayer plusieurs formats de clés
            node_info = None
            search_keys = [node_id_int, str(node_id_int), f"!{node_id_int:08x}", f"{node_id_int:08x}"]
            
            # DEBUG: Log first 3 searches
            if debug_count < 3:
                debug_print(f"DEBUG /keys: Searching for node_id={node_id} (int={node_id_int})")
                debug_print(f"DEBUG /keys: Trying keys: {search_keys}")
                debug_count += 1
            
            for key in search_keys:
                if key in nodes:
                    node_info = nodes[key]
                    if debug_count <= 3:
                        debug_print(f"DEBUG /keys: FOUND with key={key}")
                    break
            
            if debug_count <= 3 and node_info is None:
                debug_print(f"DEBUG /keys: NOT FOUND in interface.nodes")
            
            if node_info and isinstance(node_info, dict):
                user_info = node_info.get('user', {})
                if isinstance(user_info, dict):
                    # Try both field names: 'public_key' (protobuf) and 'publicKey' (dict)
                    public_key = user_info.get('public_key') or user_info.get('publicKey')
                    node_name = user_info.get('longName') or user_info.get('shortName') or f"Node-{node_id_int:08x}"
                    
                    if public_key:
                        nodes_with_keys_count += 1
                    else:
                        # Nœud vu mais sans clé publique
                        nodes_without_keys.append((node_id_int, node_name))
                else:
                    # user info malformed - treat as no key
                    node_name = self.node_manager.get_node_name(node_id_int) if self.node_manager else f"Node-{node_id_int:08x}"
                    nodes_without_keys.append((node_id_int, node_name))
            else:
                # Nœud vu dans le trafic mais pas dans interface.nodes
                # Récupérer le nom depuis node_manager ou traffic_monitor
                node_name = self.node_manager.get_node_name(node_id_int) if self.node_manager else f"Node-{node_id_int:08x}"
                nodes_without_keys.append((node_id_int, node_name))
        
        total_seen = len(nodes_in_traffic)
        
        # Détecter si on est en mode TCP avec interface.nodes vide
        tcp_mode_empty = (len(nodes) < 5 and total_seen > 20)
        
        if compact:
            # Format ultra-court pour mesh
            if nodes_without_keys:
                return f"🔑 Vus: {total_seen}. {len(nodes_without_keys)} sans clés"
            else:
                return f"✅ {total_seen} nœuds vus, tous avec clés"
        else:
            # Format détaillé pour Telegram/CLI
            lines = []
            lines.append("🔑 État des clés publiques PKI")
            lines.append("   (Nœuds vus dans les 48h)")
            lines.append("")
            lines.append(f"Nœuds actifs: {total_seen}")
            lines.append(f"✅ Avec clé publique: {nodes_with_keys_count}")
            lines.append(f"❌ Sans clé publique: {len(nodes_without_keys)}")
            lines.append("")
            
            # CRITICAL: Add firmware version warning if NO keys found at all
            if nodes_with_keys_count == 0 and len(nodes_without_keys) > 0:
                lines.append("⚠️ AUCUNE CLÉ PUBLIQUE DÉTECTÉE")
                lines.append("")
                lines.append("Causes possibles:")
                lines.append("   1. 🔴 Firmware < 2.5.0 (pas de PKI)")
                lines.append("      → Les nœuds doivent être en 2.5.0+ pour PKI")
                lines.append("      → Vérifier: meshtastic --info | grep firmware")
                lines.append("")
                lines.append("   2. ⚙️ PKI désactivé dans les paramètres")
                lines.append("      → Activer dans: Settings → Security → PKI")
                lines.append("")
                lines.append("   3. ⏳ Échange de clés pas encore complété")
                lines.append("      → Attendre 15-30 min après démarrage")
                lines.append("")
                lines.append("   4. 📦 NODEINFO pas encore reçus")
                lines.append("      → En mode TCP, attendre les broadcasts")
                lines.append("")
                lines.append("🔍 Pour diagnostiquer:")
                lines.append("   • Activer DEBUG_MODE=True dans config.py")
                lines.append("   • Chercher logs: 'NODEINFO sans champ public_key'")
                lines.append("   • Si présent → firmware < 2.5.0 ou PKI off")
                lines.append("")
                return "\n".join(lines)
            
            # Avertissement spécial pour mode TCP avec interface.nodes vide
            if tcp_mode_empty:
                lines.append("⚠️ LIMITATION MODE TCP DÉTECTÉE")
                lines.append("")
                lines.append("Le bot se connecte via TCP mais interface.nodes est vide.")
                lines.append("En mode TCP, les clés ne sont disponibles qu'après")
                lines.append("réception des paquets NODEINFO (15-30 min par nœud).")
                lines.append("")
                lines.append("🔍 Vérification:")
                lines.append("   Les clés existent probablement dans la base de")
                lines.append("   données du nœud Meshtastic (vérifier avec:")
                lines.append("   meshtastic --host <ip> --nodes)")
                lines.append("")
                lines.append("💡 Solutions:")
                lines.append("   1. Attendre les broadcasts NODEINFO automatiques")
                lines.append("   2. Demander NODEINFO pour nœuds importants:")
                lines.append("      meshtastic --host <ip> --request-telemetry --dest <id>")
                lines.append("   3. Connexion série (accès DB immédiat)")
                lines.append("")
                lines.append("📖 Documentation:")
                lines.append("   Voir TCP_PKI_KEYS_LIMITATION.md pour détails")
                lines.append("")
            
            if nodes_without_keys:
                lines.append("⚠️ Nœuds sans clé publique:")
                lines.append("   (Vous ne pouvez PAS recevoir leurs DM)")
                lines.append("")
                
                # Trier par nom
                nodes_without_keys.sort(key=lambda x: x[1])
                
                # Limiter à 15 nœuds pour ne pas surcharger
                for node_id, node_name in nodes_without_keys[:15]:
                    lines.append(f"   • {node_name} (!{node_id:08x})")
                
                if len(nodes_without_keys) > 15:
                    lines.append(f"   ... et {len(nodes_without_keys) - 15} autres")
                
                lines.append("")
                lines.append("💡 Solutions:")
                lines.append("   • Attendre échange automatique (15-30 min)")
                lines.append("   • Demander NODEINFO manuel:")
                lines.append("     meshtastic --request-telemetry --dest <node_id>")
                lines.append("")
                lines.append("📖 Plus d'info:")
                lines.append("   /keys <node_name> pour un nœud spécifique")
            else:
                lines.append("✅ Tous les nœuds actifs ont échangé leurs clés!")
                lines.append("")
                lines.append("Vous pouvez recevoir des DM de tous les nœuds actifs.")
            
            return "\n".join(lines)

