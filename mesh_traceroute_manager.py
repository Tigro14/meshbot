#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gestionnaire de traceroute pour le réseau mesh LoRa
Gère les requêtes TRACEROUTE_APP natives Meshtastic et leurs réponses
"""

import time
import threading
from typing import Dict, Optional, Callable
from utils import info_print, error_print, debug_print


class MeshTracerouteManager:
    """
    Gestionnaire de traceroutes mesh natifs via TRACEROUTE_APP

    Contrairement au TracerouteManager Telegram, celui-ci:
    - Gère les traceroutes depuis le mesh LoRa (pas Telegram)
    - Renvoie les réponses au mesh avec format compact (<180 chars)
    - Gère timeout et cleanup automatique
    """

    def __init__(self, node_manager, message_sender):
        """
        Initialiser le gestionnaire de traceroute mesh

        Args:
            node_manager: NodeManager pour résolution de noms
            message_sender: MessageSender pour envoyer réponses
        """
        self.node_manager = node_manager
        self.message_sender = message_sender

        # Traceroutes en attente: target_node_id -> {requester_id, timestamp, requester_info}
        self.pending_traces = {}

        # Timeout pour réponses (60 secondes)
        self.trace_timeout = 60

        # Lock pour thread-safety
        self._lock = threading.Lock()

        info_print("⚡ MeshTracerouteManager initialisé")

    def request_traceroute(self, interface, target_node_id: int,
                          requester_id: int, requester_info: Dict) -> bool:
        """
        Envoyer une requête de traceroute vers un nœud cible

        Args:
            interface: Interface Meshtastic (serial ou TCP)
            target_node_id: ID du nœud à tracer
            requester_id: ID du demandeur (pour réponse)
            requester_info: Infos du demandeur (name, etc.)

        Returns:
            bool: True si requête envoyée, False si erreur
        """
        try:
            # Normaliser les IDs
            target_node_id = target_node_id & 0xFFFFFFFF
            requester_id = requester_id & 0xFFFFFFFF

            # Enregistrer la requête
            with self._lock:
                self.pending_traces[target_node_id] = {
                    'requester_id': requester_id,
                    'requester_info': requester_info,
                    'timestamp': time.time()
                }

            target_name = self.node_manager.get_node_name(target_node_id)
            requester_name = requester_info.get('name', 'Unknown')

            info_print(f"🔍 Traceroute mesh: {requester_name} → {target_name}")
            debug_print(f"   Target: 0x{target_node_id:08x}")
            debug_print(f"   Requester: 0x{requester_id:08x}")

            # Envoyer paquet TRACEROUTE_APP
            # L'API Meshtastic attend un paquet vide ou un RouteDiscovery message
            interface.sendData(
                data=b'',  # Paquet vide pour initier traceroute
                destinationId=target_node_id,
                portNum='TRACEROUTE_APP',
                wantAck=False,  # Pas besoin d'ACK, on attend la réponse
                wantResponse=True  # On veut une réponse
            )

            info_print(f"✅ Paquet TRACEROUTE_APP envoyé vers 0x{target_node_id:08x}")

            # Message de confirmation au requester
            self.message_sender.send_single(
                f"🔍 Traceroute vers {target_name}\n⏳ Attente (max 60s)...",
                requester_id,
                requester_info
            )

            return True

        except Exception as e:
            error_print(f"❌ Erreur envoi traceroute: {e}")

            # Cleanup
            with self._lock:
                if target_node_id in self.pending_traces:
                    del self.pending_traces[target_node_id]

            # Notifier l'erreur
            try:
                self.message_sender.send_single(
                    f"❌ Erreur traceroute: {str(e)[:50]}",
                    requester_id,
                    requester_info
                )
            except:
                pass

            return False

    def handle_traceroute_response(self, packet: Dict) -> bool:
        """
        Traiter une réponse TRACEROUTE_APP reçue du mesh

        Args:
            packet: Paquet Meshtastic reçu

        Returns:
            bool: True si réponse traitée, False sinon
        """
        try:
            from_id = packet.get('from', 0) & 0xFFFFFFFF

            # Vérifier si c'est une réponse attendue
            with self._lock:
                if from_id not in self.pending_traces:
                    debug_print(f"⚠️ Traceroute de 0x{from_id:08x} non attendu")
                    return False

                trace_data = self.pending_traces[from_id].copy()
                del self.pending_traces[from_id]

            requester_id = trace_data['requester_id']
            requester_info = trace_data['requester_info']
            elapsed = time.time() - trace_data['timestamp']

            info_print(f"✅ Réponse traceroute reçue de 0x{from_id:08x} ({elapsed:.1f}s)")

            # Parser les routes aller/retour depuis le paquet
            route_forward, route_back = self._parse_traceroute_packet(packet)

            # Formater et envoyer la réponse
            response = self._format_traceroute_response(
                route_forward=route_forward,
                route_back=route_back,
                target_id=from_id,
                elapsed_time=elapsed,
                compact=True  # Format compact pour LoRa
            )

            self.message_sender.send_chunks(
                response,
                requester_id,
                requester_info
            )

            info_print(f"📤 Réponse traceroute envoyée à 0x{requester_id:08x}")

            return True

        except Exception as e:
            error_print(f"❌ Erreur traitement réponse traceroute: {e}")
            return False

    def _parse_traceroute_packet(self, packet: Dict) -> tuple:
        """
        Parser le paquet TRACEROUTE_APP pour extraire les routes aller et retour

        Args:
            packet: Paquet Meshtastic

        Returns:
            tuple: (route_forward, route_back)
                route_forward: Liste de dicts {node_id, name} pour l'aller
                route_back: Liste de dicts {node_id, name} pour le retour (ou [] si indispo)
        """
        route_forward = []
        route_back = []

        try:
            # Le paquet decoded contient la route
            if 'decoded' not in packet:
                debug_print("⚠️ Paquet sans section 'decoded'")
                return route_forward, route_back

            decoded = packet['decoded']

            # Méthode 1: Route dans RouteDiscovery (protobuf)
            if 'payload' in decoded:
                try:
                    from meshtastic import mesh_pb2

                    # Décoder le RouteDiscovery protobuf
                    route_discovery = mesh_pb2.RouteDiscovery()
                    route_discovery.ParseFromString(decoded['payload'])

                    # Extraire la route aller
                    for node_id in route_discovery.route:
                        node_id_norm = node_id & 0xFFFFFFFF
                        node_name = self.node_manager.get_node_name(node_id_norm)
                        route_forward.append({
                            'node_id': node_id_norm,
                            'name': node_name
                        })

                    debug_print(f"📋 Route aller parsée: {len(route_forward)} hops")
                    for i, hop in enumerate(route_forward):
                        debug_print(f"   {i}. {hop['name']} (0x{hop['node_id']:08x})")

                    # Extraire la route retour si disponible
                    if hasattr(route_discovery, 'route_back') and len(route_discovery.route_back) > 0:
                        for node_id in route_discovery.route_back:
                            node_id_norm = node_id & 0xFFFFFFFF
                            node_name = self.node_manager.get_node_name(node_id_norm)
                            route_back.append({
                                'node_id': node_id_norm,
                                'name': node_name
                            })

                        debug_print(f"📋 Route retour parsée: {len(route_back)} hops")
                        for i, hop in enumerate(route_back):
                            debug_print(f"   {i}. {hop['name']} (0x{hop['node_id']:08x})")

                    return route_forward, route_back

                except ImportError:
                    debug_print("⚠️ mesh_pb2 non disponible")
                except Exception as parse_error:
                    debug_print(f"⚠️ Erreur parsing RouteDiscovery: {parse_error}")

            # Méthode 2: Fallback - analyser hopStart/hopLimit
            if not route_forward:
                # Si pas de route décodée, au moins indiquer origine → destination
                from_id = packet.get('from', 0) & 0xFFFFFFFF
                to_id = packet.get('to', 0) & 0xFFFFFFFF

                route_forward.append({
                    'node_id': from_id,
                    'name': self.node_manager.get_node_name(from_id)
                })

                # Si relayé, indiquer nombre de hops
                hop_limit = packet.get('hopLimit', 0)
                hop_start = packet.get('hopStart', 3)
                hops_taken = hop_start - hop_limit

                if hops_taken > 0:
                    route_forward.append({
                        'node_id': None,
                        'name': f"[{hops_taken} relay(s)]"
                    })

                route_forward.append({
                    'node_id': to_id,
                    'name': self.node_manager.get_node_name(to_id)
                })

                debug_print(f"📋 Route estimée (fallback): {len(route_forward)} hops")

        except Exception as e:
            error_print(f"Erreur parsing route: {e}")

        return route_forward, route_back

    def _format_traceroute_response(self, route_forward: list, route_back: list,
                                    target_id: int, elapsed_time: float,
                                    compact: bool = True) -> str:
        """
        Formater la réponse de traceroute

        Args:
            route_forward: Liste des hops aller [{node_id, name}, ...]
            route_back: Liste des hops retour [{node_id, name}, ...] (ou [] si indispo)
            target_id: ID du nœud cible
            elapsed_time: Temps écoulé en secondes
            compact: True pour format LoRa (<180 chars), False pour détaillé

        Returns:
            str: Message formaté
        """
        target_name = self.node_manager.get_node_name(target_id)

        if compact:
            # Format ultra-compact pour LoRa
            lines = []
            lines.append(f"🔍 Trace→{target_name}")

            if route_forward:
                hops = len(route_forward) - 1  # Nombre de sauts (excluant origine)
                lines.append(f"📏 {hops} hop{'s' if hops != 1 else ''}")

                # Fonction helper pour formater une route
                def format_compact_route(route, prefix=""):
                    if len(route) <= 4:
                        # Route courte: afficher tous les noms
                        return prefix + "→".join([
                            hop['name'].split()[0][:8]  # Premier mot, max 8 chars
                            for hop in route
                        ])
                    else:
                        # Route longue: origine → ... → destination
                        origin = route[0]['name'].split()[0][:8]
                        dest = route[-1]['name'].split()[0][:8]
                        middle = len(route) - 2
                        return f"{prefix}{origin}→[{middle}]→{dest}"

                # Afficher route aller
                lines.append(f"➡️ {format_compact_route(route_forward, '')}")

                # Afficher route retour si disponible
                if route_back and len(route_back) > 0:
                    lines.append(f"⬅️ {format_compact_route(route_back, '')}")

                # Temps
                lines.append(f"⏱️ {elapsed_time:.1f}s")
            else:
                lines.append("❌ Route inconnue")

            return "\n".join(lines)

        else:
            # Format détaillé pour Telegram
            lines = []
            lines.append(f"🔍 Traceroute vers {target_name}")
            lines.append("━" * 30)
            lines.append("")

            if route_forward:
                lines.append(f"📏 Distance: {len(route_forward) - 1} hop(s)")
                lines.append("")

                # Afficher route ALLER
                lines.append("➡️ **Route ALLER:**")
                for i, hop in enumerate(route_forward):
                    hop_name = hop['name']
                    hop_id = hop.get('node_id')

                    if i == 0:
                        icon = "🏁"  # Origine
                    elif i == len(route_forward) - 1:
                        icon = "🎯"  # Destination
                    else:
                        icon = "🔀"  # Relay

                    if hop_id:
                        lines.append(f"{icon} Hop {i}: {hop_name}")
                        lines.append(f"   ID: !{hop_id:08x}")
                    else:
                        lines.append(f"{icon} {hop_name}")

                    if i < len(route_forward) - 1:
                        lines.append("   ⬇️")

                # Afficher route RETOUR si disponible
                if route_back and len(route_back) > 0:
                    lines.append("")
                    lines.append("⬅️ **Route RETOUR:**")
                    for i, hop in enumerate(route_back):
                        hop_name = hop['name']
                        hop_id = hop.get('node_id')

                        if i == 0:
                            icon = "🏁"  # Origine (qui était destination)
                        elif i == len(route_back) - 1:
                            icon = "🎯"  # Destination (qui était origine)
                        else:
                            icon = "🔀"  # Relay

                        if hop_id:
                            lines.append(f"{icon} Hop {i}: {hop_name}")
                            lines.append(f"   ID: !{hop_id:08x}")
                        else:
                            lines.append(f"{icon} {hop_name}")

                        if i < len(route_back) - 1:
                            lines.append("   ⬇️")

                lines.append("")
                lines.append(f"⏱️ Temps: {elapsed_time:.1f}s")
            else:
                lines.append("❌ Route non disponible")
                lines.append("Le nœud a répondu mais la route n'a pas pu être décodée.")

            return "\n".join(lines)

    def cleanup_expired_traces(self):
        """
        Nettoyer les traceroutes expirés (appelé périodiquement)

        Returns:
            int: Nombre de traces nettoyées
        """
        try:
            current_time = time.time()
            expired = []

            with self._lock:
                for target_id, trace_data in self.pending_traces.items():
                    if current_time - trace_data['timestamp'] > self.trace_timeout:
                        expired.append((target_id, trace_data))

                # Supprimer les expirés
                for target_id, _ in expired:
                    del self.pending_traces[target_id]

            # Notifier les requester
            for target_id, trace_data in expired:
                target_name = self.node_manager.get_node_name(target_id)
                requester_id = trace_data['requester_id']
                requester_info = trace_data['requester_info']

                info_print(f"⏱️ Traceroute expiré: {target_name}")

                try:
                    self.message_sender.send_single(
                        f"⏱️ Timeout: {target_name}\nPas de réponse",
                        requester_id,
                        requester_info
                    )
                except Exception as e:
                    debug_print(f"Erreur notification timeout: {e}")

            if expired:
                info_print(f"🧹 {len(expired)} traceroutes expirés nettoyés")

            return len(expired)

        except Exception as e:
            error_print(f"Erreur cleanup_expired_traces: {e}")
            return 0

    def get_status(self) -> str:
        """
        Obtenir le status du gestionnaire de traceroute

        Returns:
            str: Status formaté
        """
        with self._lock:
            pending_count = len(self.pending_traces)

        lines = []
        lines.append("🔍 MeshTracerouteManager:")
        lines.append(f"  Traces en attente: {pending_count}")
        lines.append(f"  Timeout: {self.trace_timeout}s")

        return "\n".join(lines)
