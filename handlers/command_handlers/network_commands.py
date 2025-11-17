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
    def __init__(self, remote_nodes_client, sender, node_manager, interface=None, mesh_traceroute=None):
        self.remote_nodes_client = remote_nodes_client
        self.sender = sender
        self.node_manager = node_manager
        self.interface = interface
        self.mesh_traceroute = mesh_traceroute
    
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
        """Gérer la commande /my - infos signal vues par tigrog2"""
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
                    # Réponse publique avec préfixe
                    author_short = current_sender.get_short_name(sender_id)
                    response = f"{author_short}: {response}"
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
        
        threading.Thread(target=get_remote_signal_info, daemon=True).start()
    
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
    
    def _send_broadcast_via_tigrog2(self, message, sender_id, sender_info, command):
        """
        Envoyer un message en broadcast via tigrog2
        
        Note: Exécuté dans un thread séparé pour ne pas bloquer
        """
        def send_broadcast():
            from safe_tcp_connection import broadcast_message
            
            debug_print(f"📡 Broadcast {command} via {REMOTE_NODE_NAME}...")
            success, msg = broadcast_message(REMOTE_NODE_HOST, message)
            
            if success:
                info_print(f"✅ Broadcast {command} diffusé")
                self.sender.log_conversation(sender_id, sender_info, command, message)
            else:
                error_print(f"❌ Échec broadcast {command}: {msg}")
                # Optionnel: notifier l'expéditeur de l'échec
                # self.sender.send_error_notification(sender_id, f"Échec broadcast: {msg}")
        
        # Lancer en arrière-plan
        threading.Thread(target=send_broadcast, daemon=True).start()

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

                target_node_id = target_node['id']

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

