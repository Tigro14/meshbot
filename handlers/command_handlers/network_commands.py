#!/usr/bin/env python3
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
    def __init__(self, remote_nodes_client, sender):
        self.remote_nodes_client = remote_nodes_client
        self.sender = sender
    
    def handle_rx(self, message, sender_id, sender_info):
        """Gérer la commande /rx"""
        # Extraire le numéro de page
        page = 1
        parts = message.split()
        
        if len(parts) > 1:
            page = validate_page_number(parts[1], 999)
        
        info_print(f"RX Page {page}: {sender_info}")
        
        try:
            report = self.remote_nodes_client.get_tigrog2_paginated(page)
            self.sender.log_conversation(sender_id, sender_info, 
                                        f"/rx {page}" if page > 1 else "/rx", 
                                        report)
            self.sender.send_single(report, sender_id, sender_info)
        except Exception as e:
            error_msg = f"Erreur rx page {page}: {str(e)[:50]}"
            self.sender.send_single(error_msg, sender_id, sender_info)
    
    def handle_my(self, sender_id, sender_info, is_broadcast=False):
        """Gérer la commande /my - infos signal vues par tigrog2"""
        info_print(f"My: {sender_info}")
        
        def get_remote_signal_info():
            try:
                remote_nodes = self.remote_nodes_client.get_remote_nodes(REMOTE_NODE_HOST)
                
                if not remote_nodes:
                    response = f"⚠️ {REMOTE_NODE_NAME} inaccessible"
                    self.sender.send_single(response, sender_id, sender_info)
                    return
                
                # Normaliser l'ID
                sender_id_normalized = sender_id & 0xFFFFFFFF
                
                debug_print(f"🔍 Recherche nœud {sender_id_normalized:08x} ({sender_info})")
                debug_print(f"📋 {len(remote_nodes)} nœuds disponibles dans tigrog2")
                
                # Chercher le nœud
                sender_node_data = None
                for node in remote_nodes:
                    node_id_normalized = node['id'] & 0xFFFFFFFF
                    if node_id_normalized == sender_id_normalized:
                        sender_node_data = node
                        debug_print(f"✅ Nœud {sender_info} trouvé dans tigrog2!")
                        break
                
                if sender_node_data:
                    response = self._format_my_response(sender_node_data)
                else:
                    response = self._format_my_not_found(remote_nodes)
                
                if is_broadcast:
                    # Réponse publique avec préfixe
                    author_short = self.sender.get_short_name(sender_id)
                    response = f"{author_short}: {response}"
                    self._send_broadcast_via_tigrog2(response, sender_id, sender_info, "/my")
                else:
                    # Réponse privée
                    self.sender.log_conversation(sender_id, sender_info, "/my", response)
                    self.sender.send_single(response, sender_id, sender_info)
                
            except Exception as e:
                error_print(f"Erreur commande /my: {e}")
                import traceback
                error_print(traceback.format_exc())
                try:
                    error_response = f"⚠️ Erreur: {str(e)[:30]}"
                    self.sender.send_single(error_response, sender_id, sender_info)
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
            debug_print(f"📢 RSSI estimé depuis SNR: {display_rssi}dBm")
        
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
        """Envoyer un message en broadcast via tigrog2"""
        def send_broadcast():
            remote_interface = None
            try:
                debug_print(f"Connexion TCP à tigrog2 pour broadcast {command}...")
                remote_interface = meshtastic.tcp_interface.TCPInterface(
                    hostname=REMOTE_NODE_HOST, 
                    portNumber=4403
                )
                
                # ✅ CRITIQUE : Réduire à 1s
                time.sleep(1)
                
                debug_print(f"Envoi broadcast: '{message[:50]}...'")
                remote_interface.sendText(message)
                
                # ✅ Réduire à 2s au lieu de 4s
                time.sleep(2)
                
                debug_print(f"✅ Broadcast {command} diffusé via tigrog2")
                self.sender.log_conversation(sender_id, sender_info, command, message)
                
            except Exception as e:
                error_print(f"Erreur broadcast {command} via tigrog2: {e}")
            finally:
                # ✅ CRITIQUE : TOUJOURS fermer
                if remote_interface:
                    try:
                        debug_print(f"🔒 Fermeture FORCÉE connexion tigrog2")
                        remote_interface.close()
                        del remote_interface
                        import gc
                        gc.collect()
                    except Exception as close_error:
                        debug_print(f"Erreur fermeture: {close_error}")
        
        threading.Thread(target=send_broadcast, daemon=True).start()

    def handle_trace(self, message, sender_id, sender_info, packet):
        """
        Gérer la commande /trace - Traceroute mesh
        Analyse le chemin du message et identifie les relays potentiels
        """
        info_print(f"Trace: {sender_info}")
        
        def analyze_route():
            try:
                # === ANALYSE DU PACKET ===
                hop_limit = packet.get('hopLimit', 0)
                hop_start = packet.get('hopStart', 5)
                rssi = packet.get('rssi', 0)
                snr = packet.get('snr', 0.0)
                
                # Calculer le nombre de hops effectués
                hops_taken = hop_start - hop_limit
                
                debug_print(f"📊 Trace analysis: hopStart={hop_start}, hopLimit={hop_limit}, hops={hops_taken}")
                
                # === CONSTRUCTION DU RAPPORT ===
                response_parts = []
                response_parts.append(f"🔍 Traceroute → {sender_info}")
                response_parts.append("")
                
                # === CAS 1: DIRECT (0 hop) ===
                if hops_taken == 0:
                    response_parts.append("✅ Liaison DIRECTE")
                    response_parts.append(f"Hops: 0 (direct)")
                    
                    # Signal
                    if rssi != 0 or snr != 0:
                        rssi_icon = get_signal_quality_icon(rssi) if rssi != 0 else "📶"
                        rssi_str = f"{rssi}dBm" if rssi != 0 else "n/a"
                        snr_str = f"SNR:{snr:.1f}dB" if snr != 0 else "SNR:n/a"
                        response_parts.append(f"{rssi_icon} Signal: {rssi_str} | {snr_str}")
                        
                        # Qualité
                        quality = get_signal_quality_description(rssi, snr)
                        response_parts.append(f"📈 Qualité: {quality}")
                        
                        # Distance estimée
                        if rssi != 0 and rssi > -150:
                            distance = estimate_distance_from_rssi(rssi)
                            response_parts.append(f"📏 Distance: ~{distance}")
                    
                    response_parts.append("")
                    response_parts.append(f"Route: {sender_info} ← bot")
                    
                # === CAS 2: RELAYÉ (1+ hops) ===
                else:
                    response_parts.append("🔀 Liaison RELAYÉE")
                    response_parts.append(f"Hops: {hops_taken}")
                    
                    # Signal final
                    if rssi != 0 or snr != 0:
                        rssi_icon = get_signal_quality_icon(rssi) if rssi != 0 else "📶"
                        rssi_str = f"{rssi}dBm" if rssi != 0 else "n/a"
                        snr_str = f"SNR:{snr:.1f}dB" if snr != 0 else "SNR:n/a"
                        response_parts.append(f"{rssi_icon} Signal final: {rssi_str} | {snr_str}")
                    
                    response_parts.append("")
                    
                    # === ANALYSE DE LA TOPOLOGIE ===
                    try:
                        # Récupérer les nœuds de tigrog2
                        remote_nodes = self.remote_nodes_client.get_remote_nodes(REMOTE_NODE_HOST)
                        
                        if remote_nodes:
                            # Chercher le nœud émetteur dans tigrog2
                            sender_id_normalized = sender_id & 0xFFFFFFFF
                            sender_in_tigrog2 = False
                            
                            for node in remote_nodes:
                                node_id_normalized = node['id'] & 0xFFFFFFFF
                                if node_id_normalized == sender_id_normalized:
                                    sender_in_tigrog2 = True
                                    break
                            
                            if sender_in_tigrog2:
                                response_parts.append(f"ℹ️ {sender_info} connu par {REMOTE_NODE_NAME}")
                                response_parts.append("⚠️ Mais messages relayés (pas direct)")
                            else:
                                response_parts.append(f"📡 {sender_info} hors portée {REMOTE_NODE_NAME}")
                            
                            response_parts.append("")
                            
                            # === IDENTIFICATION DES RELAYS POTENTIELS ===
                            response_parts.append("🔍 Relays potentiels:")
                            
                            # Trouver les meilleurs relays
                            potential_relays = find_best_relays(remote_nodes, max_relays=3)
                            
                            if potential_relays:
                                for i, relay in enumerate(potential_relays, 1):
                                    relay_name = truncate_text(relay['name'], 12)
                                    relay_rssi = relay.get('rssi', 0)
                                    relay_snr = relay.get('snr', 0.0)
                                    
                                    relay_icon = get_signal_quality_icon(relay_rssi)
                                    
                                    if relay_rssi != 0:
                                        response_parts.append(
                                            f"  {i}. {relay_icon} {relay_name} "
                                            f"({relay_rssi}dBm, SNR:{relay_snr:.1f})"
                                        )
                                    else:
                                        response_parts.append(f"  {i}. {relay_icon} {relay_name}")
                                
                                response_parts.append("")
                                response_parts.append("Route probable:")
                                if hops_taken == 1:
                                    response_parts.append(
                                        f"{sender_info} → [relay] → bot"
                                    )
                                else:
                                    response_parts.append(
                                        f"{sender_info} → [relay×{hops_taken}] → bot"
                                    )
                            else:
                                response_parts.append("  ❓ Relays non identifiables")
                                response_parts.append(f"  Route: {sender_info} → [mesh×{hops_taken}] → bot")
                        
                        else:
                            response_parts.append("⚠️ Impossible d'analyser la topologie")
                            response_parts.append(f"Route: {sender_info} → [mesh×{hops_taken}] → bot")
                        
                    except Exception as topo_error:
                        debug_print(f"Erreur analyse topologie: {topo_error}")
                        response_parts.append("⚠️ Analyse topologie échouée")
                        response_parts.append(f"Route: {sender_info} → [mesh×{hops_taken}] → bot")
                
                # === FOOTER TECHNIQUE ===
                response_parts.append("")
                response_parts.append(f"📋 Détails:")
                response_parts.append(f"  • hopStart: {hop_start}")
                response_parts.append(f"  • hopLimit: {hop_limit}")
                response_parts.append(f"  • Node ID: !{sender_id:08x}")
                
                # === ASSEMBLAGE ET ENVOI ===
                response = "\n".join(response_parts)
                
                self.sender.log_conversation(sender_id, sender_info, "/trace", response)
                self.sender.send_chunks(response, sender_id, sender_info)
                
                info_print(f"✅ Trace rapport envoyé à {sender_info}")
                
            except Exception as e:
                error_print(f"Erreur commande /trace: {e}")
                import traceback
                error_print(traceback.format_exc())
                try:
                    error_response = f"⚠️ Erreur trace: {str(e)[:30]}"
                    self.sender.send_single(error_response, sender_id, sender_info)
                except:
                    pass
        
        threading.Thread(target=analyze_route, daemon=True).start()

