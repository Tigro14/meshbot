#!/usr/bin/env python3
import traceback
# -*- coding: utf-8 -*-
"""
Gestionnaire des commandes utilitaires
"""

import time
import threading
import subprocess
import os
import json
from utils_weather import get_weather_data, get_rain_graph, get_weather_astro
from config import *
from utils import *

# Constantes pour les délais entre messages
MESSAGE_DELAY_SECONDS = 0.5  # Délai entre les parties d'un message splitté

class UtilityCommands:
    def __init__(self, esphome_client, traffic_monitor, sender, node_manager=None, blitz_monitor=None, vigilance_monitor=None, broadcast_tracker=None):
        self.esphome_client = esphome_client
        self.traffic_monitor = traffic_monitor
        self.sender = sender
        self.node_manager = node_manager
        self.blitz_monitor = blitz_monitor
        self.vigilance_monitor = vigilance_monitor
        self.broadcast_tracker = broadcast_tracker  # Callback pour tracker broadcasts
    
    def handle_power(self, sender_id, sender_info):
        """Gérer la commande /power"""
        info_print(f"Power: {sender_info}")
        
        esphome_data = self.esphome_client.parse_esphome_data()
        self.sender.log_conversation(sender_id, sender_info, "/power", esphome_data)
        self.sender.send_chunks(esphome_data, sender_id, sender_info)
    
    def handle_legend(self, sender_id, sender_info):
        """Gérer la commande /legend"""
        info_print(f"Legend: {sender_info}")
        
        legend_text = self._format_legend()
        self.sender.log_conversation(sender_id, sender_info, "/legend", legend_text)
        self.sender.send_chunks(legend_text, sender_id, sender_info)
    
    def handle_help(self, sender_id, sender_info):
        """Gérer la commande /help"""
        info_print(f"Help: {sender_info}")
        
        try:
            help_text = self._format_help()
            info_print(f"Help text généré: {len(help_text)} caractères")
            self.sender.log_conversation(sender_id, sender_info, "/help", help_text)
            self.sender.send_single(help_text, sender_id, sender_info)
            info_print(f"Help envoyé à {sender_info}")
        except Exception as e:
            error_print(f"Erreur commande /help: {e}")
            self.sender.send_single("Erreur génération aide", sender_id, sender_info)
    
    def handle_graphs_command(self, sender_id, from_id, text_parts):
        """
        Commande /graphs - Graphiques température/pression (version compacte)
        Usage: /graphs [heures]
        """
        from utils import conversation_print, error_print

        try:
            sender_name = self.node_manager.get_node_name(from_id, self.interface)
            conversation_print(f"📊 /graphs demandé par {sender_name}")

            # Parser les arguments
            hours = 12  # Défaut pour Meshtastic
            if len(text_parts) > 1:
                try:
                    requested = int(text_parts[1])
                    hours = max(1, min(24, requested))  # Entre 1 et 24h
                except ValueError:
                    hours = 12

            # Obtenir les graphiques compacts
            graphs = self.esphome_client.get_history_graphs_compact(hours)

            # Envoyer la réponse
            self.sender.send_message(sender_id, graphs)
            conversation_print(f"✅ Graphiques {hours}h envoyés à {sender_name}")

        except Exception as e:
            error_print(f"Erreur /graphs: {e}")
            error_print(traceback.format_exc())
            self.sender.send_message(sender_id, f"Erreur graphs: {str(e)[:30]}")

    def handle_graphs(self, message, sender_id, sender_info): 
        """
        Gérer la commande /graphs - Graphiques température/pressiona  nouvelle version
        Version compacte pour Meshtastic
        """
        info_print(f"Graphs: {sender_info}")
        
        try:
            # Parser les arguments
            parts = message.split()
            hours = 12  # Défaut pour Meshtastic
            
            if len(parts) > 1:
                try:
                    requested = int(parts[1])
                    hours = max(1, min(24, requested))
                except ValueError:
                    hours = 12
            
            # Obtenir les graphiques compacts
            graphs = self.esphome_client.get_history_graphs_compact(hours)
            
            # Log et envoi
            self.sender.log_conversation(sender_id, sender_info, message, graphs)
            self.sender.send_single(graphs, sender_id, sender_info)
            
            info_print(f"✅ Graphiques {hours}h envoyés à {sender_info}")
            
        except Exception as e:
            error_print(f"Erreur /graphs: {e}")
            error_print(traceback.format_exc())
            
            error_msg = f"Erreur graphs: {str(e)[:30]}"
            try:
                self.sender.send_single(error_msg, sender_id, sender_info)
            except:
                pass

    def handle_help_command(self, sender_id, from_id):
        """Aide avec /graphs inclus"""
        help_text = (
            "🤖 Bot Meshtastic-Llama\n\n"
            "Commandes:\n"
            "• /bot <question> - Chat IA\n"
            "• /histo\n"
            "• /my\n"
            "• /legend\n"
            "• /nodes\n"
            "• /power\n"
            "• /sys\n"
            "• /top\n"
            "• /trace\n", 
            "• /help"
        )
        self.sender.send_message(sender_id, help_text)

    def handle_echo(self, message, sender_id, sender_info, packet):
        """
        Gérer la commande /echo - Diffuser un message sur le réseau mesh
        
        IMPORTANT: Uses the shared bot interface to avoid disconnecting the main connection.
        ESP32 only supports ONE TCP connection at a time - creating a new connection
        would disconnect the bot and cause packet loss.
        """

        # Capturer le sender actuel pour le thread (important pour CLI!)
        current_sender = self.sender

        info_print("=" * 60)
        info_print("🔊 HANDLE_ECHO APPELÉ")
        info_print("=" * 60)
        info_print(f"Message brut: '{message}'")
        info_print(f"Sender ID: 0x{sender_id:08x}")
        info_print(f"Sender info: {sender_info}")

        # Anti-doublon
        message_id = f"{sender_id}_{message}_{int(time.time())}"
        info_print(f"Message ID: {message_id}")
        
        if hasattr(current_sender, '_last_echo_id'):
            info_print(f"Last echo ID: {current_sender._last_echo_id}")
            if current_sender._last_echo_id == message_id:
                info_print("⚠️ Echo déjà traité, ignoré")
                return

        current_sender._last_echo_id = message_id
        info_print("✅ Anti-doublon OK")

        echo_text = message[6:].strip()
        info_print(f"Texte extrait: '{echo_text}'")
        info_print(f"Longueur: {len(echo_text)} caractères")

        if not echo_text:
            info_print("❌ Texte vide")
            current_sender.send_single("Usage: /echo <texte>", sender_id, sender_info)
            return
        
        info_print(f"✅ Texte valide: '{echo_text}'")
        
        # Get the shared interface from the sender (uses _get_interface())
        # This avoids creating a new TCP connection which would kill the main bot connection
        interface = current_sender._get_interface()
        
        if interface is None:
            error_print("❌ Interface non disponible pour echo")
            current_sender.send_single("Erreur: interface non disponible", sender_id, sender_info)
            return
        
        try:
            info_print("🔊 ECHO VIA INTERFACE PARTAGÉE")
            
            author_short = current_sender.get_short_name(sender_id)
            echo_response = f"{author_short}: {echo_text}"
            
            info_print(f"📝 Message final: '{echo_response}'")
            info_print(f"   Auteur short: {author_short}")
            info_print(f"   Longueur finale: {len(echo_response)} caractères")
            
            # Vérifier node info
            if hasattr(interface, 'localNode') and interface.localNode:
                node = interface.localNode
                if hasattr(node, 'shortName'):
                    info_print(f"✅ Node connecté: {node.shortName}")
            
            info_print("")
            info_print("📤 ENVOI DU MESSAGE VIA INTERFACE PARTAGÉE...")
            
            # Utiliser l'interface partagée - pas de nouvelle connexion!
            interface.sendText(echo_response)
            info_print("✅ Message envoyé via interface partagée")
            
            # Tracker le broadcast pour la déduplication
            if self.broadcast_tracker:
                self.broadcast_tracker(echo_response)
                info_print("🔖 Broadcast tracké pour déduplication")
            
            info_print("=" * 60)
            info_print("✅ ECHO TERMINÉ")
            info_print("=" * 60)

            current_sender.log_conversation(sender_id, sender_info, message, echo_response)

        except Exception as e:
            error_print("")
            error_print("=" * 60)
            error_print("❌ ERREUR ECHO")
            error_print("=" * 60)
            error_print(f"Exception: {e}")
            error_print(traceback.format_exc())
            error_print("=" * 60)

            try:
                error_response = f"Erreur echo: {str(e)[:30]}"
                current_sender.send_single(error_response, sender_id, sender_info)
            except:
                pass

    def handle_trafic(self, message, sender_id, sender_info):
        """Gérer la commande /trafic"""
        info_print(f"Trafic: {sender_info}")
        
        # Extraire les heures optionnelles
        hours = 8
        parts = message.split()
        if len(parts) > 1:
            try:
                hours = int(parts[1])
                hours = max(1, min(24, hours))
            except ValueError:
                hours = 8
        
        if not self.traffic_monitor:
            self.sender.send_single("❌ Traffic monitor non disponible", sender_id, sender_info)
            return
        
        try:
            #report = self.traffic_monitor.get_traffic_report(hours)
            report = self.traffic_monitor.get_traffic_report_compact(hours)
            self.sender.log_conversation(sender_id, sender_info, 
                                        f"/trafic {hours}" if hours != 8 else "/trafic", 
                                        report)
            self.sender.send_chunks(report, sender_id, sender_info)
        except Exception as e:
            error_msg = f"❌ Erreur trafic: {str(e)[:50]}"
            self.sender.send_single(error_msg, sender_id, sender_info)
    
    def _format_legend(self):
        """Formater la légende des indicateurs"""
        legend_lines = [
            "📶 Indicateurs:",
            "🟢🔵=excellent",
            "🟡🟣=bon", 
            "🟠🟤=faible",
            "🔴⚫=très faible",
            "1er=RSSI 2e=SNR"
        ]
        return "\n".join(legend_lines)

    def handle_weather(self, message, sender_id, sender_info, is_broadcast=False):
        """
        Gérer la commande /weather [rain] [ville]

        Args:
            message: Message complet (ex: "/weather London", "/weather rain Paris")
            sender_id: ID de l'expéditeur
            sender_info: Infos sur l'expéditeur
            is_broadcast: Si True, répondre en broadcast public
        """
        info_print(f"Weather: {sender_info} (broadcast={is_broadcast})")

        # Parser les arguments: /weather [rain|astro|blitz|vigi] [ville] [days]
        parts = message.split()
        subcommand = None
        location = None
        days = 1  # Par défaut: aujourd'hui seulement

        if len(parts) > 1:
            # Vérifier si c'est une sous-commande "rain", "astro", "blitz", ou "vigi"
            if parts[1].lower() in ['rain', 'astro', 'blitz', 'vigi']:
                subcommand = parts[1].lower()

                # Arguments restants après la sous-commande
                remaining = parts[2:]

                # Le dernier argument est un nombre de jours ?
                if remaining and remaining[-1].isdigit():
                    days_arg = int(remaining[-1])
                    if days_arg in [1, 2, 3]:
                        days = days_arg
                        remaining = remaining[:-1]

                # Ce qui reste est la ville (peut avoir des espaces)
                if remaining:
                    location = ' '.join(remaining)
            else:
                # Sinon c'est directement la ville
                location = ' '.join(parts[1:])

        # Si "help"/"aide", afficher l'aide
        if location and location.lower() in ['help', 'aide', '?']:
            help_text = (
                "🌤️ /weather [rain|astro|blitz|vigi] [ville]\n"
                "Ex:\n"
                "/weather → Météo locale\n"
                "/weather Paris\n"
                "/weather rain → Pluie auj.\n"
                "/weather rain 2 → Auj+demain\n"
                "/weather rain 3 → 3 jours\n"
                "/weather rain Paris 2\n"
                "/weather astro → Infos astro\n"
                "/weather astro Paris\n"
                "/weather blitz → Éclairs\n"
                "/weather vigi → VIGILANCE"
            )

            # Log conversation (pour tous les modes)
            self.sender.log_conversation(sender_id, sender_info, "/weather help", help_text)

            # Envoyer selon le mode (broadcast ou direct)
            if is_broadcast:
                self._send_broadcast_via_tigrog2(help_text, sender_id, sender_info, "/weather help")
            else:
                self.sender.send_single(help_text, sender_id, sender_info)
            return

        # Traiter selon la sous-commande
        if subcommand == 'rain':
            # Graphe de précipitations en 2 parties pour meilleure lisibilité
            # - max_hours=20: 20 heures de prévision (40 chars de largeur)
            # - compact_mode=True: Utilisé pour backward compat (non-split mode)
            # - Démarrage à l'heure actuelle pour maximiser l'info future utile
            # - Cache SQLite 1h via traffic_monitor.persistence (RAIN_CACHE_STALE_DURATION)
            # - split_messages=True: retourne (graph, header) pour envoi en 2 messages
            #   * Partie 1: 2 lignes sparkline + échelle horaire (~78 chars)
            #   * Partie 2: Header local seulement (~50 chars)
            persistence = self.traffic_monitor.persistence if self.traffic_monitor else None
            result = get_rain_graph(
                location, 
                days=days, 
                max_hours=20,  # 20h de prévision (40 chars width, ~78 chars graphe complet)
                compact_mode=True,  # Backward compat pour mode non-split
                persistence=persistence, 
                start_at_current_time=True,
                ultra_compact=False,  # Ne pas ultra-compacter maintenant qu'on split en 2 messages
                split_messages=True  # Retourner (graph, header) pour 2 messages
            )
            cmd = f"/weather rain {location} {days}" if location else f"/weather rain {days}"

            # Vérifier si on a un tuple (split_messages=True)
            if isinstance(result, tuple):
                graph, header = result
                
                # Logger les deux parties
                full_text = f"{graph}\n{header}"
                self.sender.log_conversation(sender_id, sender_info, cmd, full_text)

                # Envoyer selon le mode (broadcast ou direct)
                if is_broadcast:
                    # Broadcast public: envoyer le graphe complet (2 lignes + échelle)
                    self._send_broadcast_via_tigrog2(graph, sender_id, sender_info, cmd)
                    # Puis le header
                    time.sleep(MESSAGE_DELAY_SECONDS)
                    self._send_broadcast_via_tigrog2(header, sender_id, sender_info, cmd)
                else:
                    # Réponse privée: envoyer les 2 parties séparément
                    # Partie 1: Graphe complet (2 lignes sparkline + échelle)
                    self.sender.send_single(graph, sender_id, sender_info)
                    
                    # Petit délai entre les messages
                    time.sleep(MESSAGE_DELAY_SECONDS)
                    
                    # Partie 2: Header local seulement
                    self.sender.send_single(header, sender_id, sender_info)
            else:
                # Fallback: mode ancien (backward compat si split_messages=False)
                self.sender.log_conversation(sender_id, sender_info, cmd, result)
                
                if is_broadcast:
                    day_messages = result.split('\n\n')
                    first_day = day_messages[0] if day_messages else result
                    self._send_broadcast_via_tigrog2(first_day, sender_id, sender_info, cmd)
                else:
                    day_messages = result.split('\n\n')
                    for i, day_msg in enumerate(day_messages):
                        if not day_msg.strip():
                            continue
                        self.sender.send_single(day_msg, sender_id, sender_info)
                        if i < len(day_messages) - 1:
                            time.sleep(1)
        elif subcommand == 'astro':
            # Informations astronomiques
            # Cache SQLite 5min via traffic_monitor.persistence
            persistence = self.traffic_monitor.persistence if self.traffic_monitor else None
            weather_data = get_weather_astro(location, persistence=persistence)
            cmd = f"/weather astro {location}" if location else "/weather astro"
            self.sender.log_conversation(sender_id, sender_info, cmd, weather_data)

            # Envoyer selon le mode (broadcast ou direct)
            if is_broadcast:
                self._send_broadcast_via_tigrog2(weather_data, sender_id, sender_info, cmd)
            else:
                self.sender.send_single(weather_data, sender_id, sender_info)
        elif subcommand == 'blitz':
            # Éclairs détectés via Blitzortung
            if self.blitz_monitor and self.blitz_monitor.enabled:
                # Récupérer les éclairs récents
                recent_strikes = self.blitz_monitor.get_recent_strikes()

                if recent_strikes:
                    # Formater le rapport (compact pour LoRa)
                    weather_data = self.blitz_monitor._format_report(recent_strikes, compact=True)
                else:
                    weather_data = f"⚡ Aucun éclair ({self.blitz_monitor.window_minutes}min)"

                cmd = "/weather blitz"
                self.sender.log_conversation(sender_id, sender_info, cmd, weather_data)

                # Envoyer selon le mode (broadcast ou direct)
                if is_broadcast:
                    self._send_broadcast_via_tigrog2(weather_data, sender_id, sender_info, cmd)
                else:
                    self.sender.send_single(weather_data, sender_id, sender_info)
            else:
                weather_data = "⚡ Surveillance éclairs désactivée"
                if is_broadcast:
                    self._send_broadcast_via_tigrog2(weather_data, sender_id, sender_info, "/weather blitz")
                else:
                    self.sender.send_single(weather_data, sender_id, sender_info)
        elif subcommand == 'vigi':
            # État actuel de la vigilance Météo-France
            if self.vigilance_monitor:
                # Obtenir l'état actuel de la vigilance
                vigi_state = self.vigilance_monitor.check_vigilance()

                if vigi_state:
                    # Formater en mode compact pour LoRa
                    vigi_info = self.vigilance_monitor.format_alert_message(vigi_state, compact=True)
                else:
                    # Pas d'info disponible (erreur ou pas encore initialisé)
                    if self.vigilance_monitor.last_color:
                        # Utiliser dernière info connue
                        emoji_map = {
                            'Vert': '✅',
                            'Jaune': '⚠️',
                            'Orange': '🟠',
                            'Rouge': '🔴'
                        }
                        emoji = emoji_map.get(self.vigilance_monitor.last_color, '🌦️')
                        vigi_info = f"{emoji} VIGILANCE {self.vigilance_monitor.last_color.upper()}\nDept {self.vigilance_monitor.departement}"
                    else:
                        vigi_info = f"🌦️ VIGILANCE Dept {self.vigilance_monitor.departement}\nPas encore initialisé"
            else:
                vigi_info = "🌦️ Surveillance VIGILANCE désactivée"

            self.sender.log_conversation(sender_id, sender_info, "/weather vigi", vigi_info)

            # Envoyer selon le mode (broadcast ou direct)
            if is_broadcast:
                self._send_broadcast_via_tigrog2(vigi_info, sender_id, sender_info, "/weather vigi")
            else:
                self.sender.send_single(vigi_info, sender_id, sender_info)
        else:
            # Météo normale - utiliser le cache SQLite si disponible
            persistence = self.traffic_monitor.persistence if self.traffic_monitor else None
            weather_data = get_weather_data(location, persistence=persistence)
            cmd = f"/weather {location}" if location else "/weather"
            self.sender.log_conversation(sender_id, sender_info, cmd, weather_data)

            # Envoyer selon le mode (broadcast ou direct)
            if is_broadcast:
                self._send_broadcast_via_tigrog2(weather_data, sender_id, sender_info, cmd)
            else:
                self.sender.send_single(weather_data, sender_id, sender_info)

    def handle_rain(self, message, sender_id, sender_info, is_broadcast=False):
        """
        Raccourci pour /weather rain [ville] [days]

        Args:
            message: Message complet (ex: "/rain", "/rain Paris", "/rain Paris 3")
            sender_id: ID de l'expéditeur
            sender_info: Infos sur l'expéditeur
            is_broadcast: Si True, répondre en broadcast public
        """
        # Convertir "/rain [args]" en "/weather rain [args]"
        args = message[5:].strip() if len(message) > 5 else ""  # Enlever "/rain"
        weather_message = f"/weather rain {args}".strip()

        # Appeler handle_weather avec le message reformaté
        self.handle_weather(weather_message, sender_id, sender_info, is_broadcast=is_broadcast)

    def handle_vigi(self, sender_id, sender_info):
        """
        Afficher l'état actuel de la vigilance Météo-France (DM uniquement)
        
        Montre:
        - Couleur de vigilance actuelle (Vert/Jaune/Orange/Rouge)
        - Dernière synchronisation (timestamp)
        - Numéro de département

        Args:
            sender_id: ID de l'expéditeur
            sender_info: Infos sur l'expéditeur
        """
        info_print(f"Vigi: {sender_info}")
        
        if not self.vigilance_monitor:
            vigi_info = "🌦️ Surveillance VIGILANCE désactivée"
        else:
            # Emoji selon la couleur
            emoji_map = {
                'Vert': '✅',
                'Jaune': '⚠️',
                'Orange': '🟠',
                'Rouge': '🔴'
            }
            
            if self.vigilance_monitor.last_color:
                emoji = emoji_map.get(self.vigilance_monitor.last_color, '🌦️')
                color = self.vigilance_monitor.last_color
                dept = self.vigilance_monitor.departement
                
                # Calculer le temps depuis la dernière vérification
                if self.vigilance_monitor.last_check_time > 0:
                    elapsed = int(time.time() - self.vigilance_monitor.last_check_time)
                    
                    # Formater le temps écoulé
                    if elapsed < 60:
                        time_str = f"{elapsed}s"
                    elif elapsed < 3600:
                        time_str = f"{elapsed // 60}min"
                    else:
                        time_str = f"{elapsed // 3600}h"
                    
                    vigi_info = f"{emoji} VIGILANCE {color.upper()}\nDept {dept}\nSync: {time_str} ago"
                else:
                    vigi_info = f"{emoji} VIGILANCE {color.upper()}\nDept {dept}\nPas encore synchronisé"
            else:
                vigi_info = f"🌦️ VIGILANCE Dept {self.vigilance_monitor.departement}\nPas encore initialisé"
        
        self.sender.log_conversation(sender_id, sender_info, "/vigi", vigi_info)
        self.sender.send_single(vigi_info, sender_id, sender_info)

    def _format_help(self):
        """Formater l'aide des commandes"""
        help_lines = [
            "/bot IA",
            "/ia IA",
            "/power",
            "/sys",
            "/echo",
            "/nodes",
            "/nodesmc",
            "/nodemt",
            "/neighbors",
            "/propag",
            "/info",
            "/keys",
            "/mqtt",
            "/stats [cmd]",
            "/db [cmd]",
            "/trace",
            "/legend",
            "/weather",
            "/rain",
            "/vigi",
            "/help"
        ]
        return "\n".join(help_lines)

    def _format_help_telegram(self):
        """Format aide détaillée pour Telegram (sans contrainte de taille)"""
        import textwrap
        
        help_text = textwrap.dedent("""
        📖 AIDE COMPLÈTE - BOT MESHTASTIC

        🤖 CHAT IA
        • /bot <question> → Conversation avec l'IA
        • /ia <question> → Alias français de /bot
        • Contexte conversationnel maintenu 30min
        • Réponses plus détaillées possibles sur Telegram vs mesh

        ⚡ SYSTÈME & MONITORING
        • /power - Télémétrie complète
          Batterie, solaire, température, pression, humidité
        • /weather [rain|astro|blitz|vigi] [ville] - Météo & alertes
          /weather → Géolocalisée
          /weather Paris, /weather London, etc.
          /weather rain → Graphe pluie local
          /weather rain Paris → Graphe pluie Paris
          /weather astro → Infos astronomiques
          /weather blitz → Éclairs détectés
          /weather vigi → Info VIGILANCE Météo-France
        • /rain [ville] [days] - Graphe précipitations (alias)
        • /vigi - État VIGILANCE (couleur + dernière sync)
        • /graphs [heures] - Graphiques historiques
          Défaut: 24h, max 48h
        • /sys - Informations système Pi5
          CPU, RAM, load average, uptime

        📡 RÉSEAU MESHTASTIC
        • /nodes - Liste nœuds (auto-détection mode)
        • /nodesmc [page|full] - Liste contacts MeshCore
          /nodesmc → Page 1 (7 contacts)
          /nodesmc 2 → Page 2
          /nodesmc full → Tous les contacts
        • /nodemt - Liste nœuds directs Meshtastic
        • /neighbors [node] - Voisins mesh (topology réseau)
          /neighbors → Tous les voisins (format compact)
          /neighbors tigro → Voisins d'un nœud spécifique
        • /propag [heures] [top] - Plus longues liaisons radio
          /propag → Top 5 liaisons (24h)
          /propag 48 → Top 5 liaisons (48h)
          /propag 24 10 → Top 10 liaisons (24h)
          Rayon: 100km du bot
        • /info <node> - Informations complètes sur un nœud
          /info tigro → Infos détaillées du nœud "tigro"
          /info F547F → Infos du nœud par ID
          Affiche: nom, GPS, distance, signal, stats mesh
          Support broadcast pour partage public
        • /keys [node] - Diagnostiquer les clés publiques PKI
          /keys → État global des clés (toutes les nodes)
          /keys tigro → Vérifier si "tigro" a échangé sa clé
          /keys F547F → Vérifier clé d'un nœud par ID
          Aide à résoudre DM encryptés (Meshtastic 2.7.15+)
          PKI: Chaque nœud a une clé publique/privée unique
        • /mqtt [heures] - Nœuds MQTT entendus directement
          Liste nœuds ayant envoyé NEIGHBORINFO via MQTT
          /mqtt → Tous les nœuds MQTT (48h)
          /mqtt 24 → Nœuds des 24 dernières heures
          Affiche: LongName, ID court, temps écoulé
          Icônes: 🟢 <1h, 🟡 <24h, 🟠 >24h
        • /rx [node] - Voisins & stats MQTT collecteur
          /rx → Statistiques collecteur MQTT
          /rx tigro → Voisins du nœud (via MQTT/radio)
          Collecte données réseau au-delà portée radio
        • /fullnodes [jours] - Liste alphabétique complète
          Défaut: 30j, max 365j, tri par longName
          Exemples:
            /fullnodes → Tous les nœuds (30j)
            /fullnodes 7 → Tous les nœuds (7j)
            /fullnodes tigro → Nœuds contenant "tigro" (30j)
            /fullnodes 7 tigro → Nœuds contenant "tigro" (7j)

        📊 ANALYSE TRAFIC
        • /stats [cmd] [params] - Système unifié de statistiques
          Sous-commandes:
             - global : Vue d'ensemble réseau (défaut)
             - top [h] [n] : Top talkers
             - packets [h] : Distribution types de paquets
             - channel [h] : Utilisation du canal
             - histo [type] [h] : Histogramme temporel
             - traffic [h] : Historique messages publics
             - hop [h] : Top 20 nœuds par hop_start (portée max)
          Raccourcis: g, t, p, ch, h, tr, hop
          Ex: /stats top 24 10, /stats hop 48
        • /trafic [heures] - Historique messages publics
          Défaut: 8h, max 24h, stats détaillées
        • /top [heures] [nombre] - Top talkers (alias)
          Défaut: 24h, top 10
        • /packets [heures] - Distribution paquets (alias)
        • /hop [heures] - Top 20 portée (alias /stats hop)
          Défaut: 24h, max 7j
        • /trace [short_id] - Traceroute mesh
          Analyse chemin, identifie relays
        • /histo [type] [h] - Histogramme (alias)
          Types: all, messages, pos, info

        💾 BASE DE DONNÉES
        • /db [cmd] [params] - Opérations base de données
          Sous-commandes:
             - stats : Statistiques DB (taille, nb entrées)
             - info : Informations détaillées (tables, schema)
             - clean [h] : Nettoyer données anciennes (défaut 48h)
             - vacuum : Optimiser DB (VACUUM)
          Raccourcis: s, i, v
          Ex: /db stats, /db clean 72, /db vacuum

        📢 DIFFUSION
        • /echo <message> - Diffuser sur le réseau
          Préfixe auto, broadcast via votre node
          Ex: /echo Bonjour à tous!

        ℹ️ UTILITAIRES
        • /legend - Légende indicateurs signal
        • /help - Cette aide complète

        🔧 ADMINISTRATION (si autorisé)
        • /rebootpi [mdp] - Redémarrage Pi5
        • /rebootnode [nom] [mdp] - Redémarrage nœud distant
        • /cpu - Monitoring CPU temps réel (10s)

        📋 LIMITES & INFORMATIONS
        • Throttling: 5 commandes/5min par utilisateur
        • Contexte IA: 6 messages max, timeout 30min
        • Historique trafic mesh: 2000 messages, rétention 24h
        • Nœuds distants: filtre 3j par défaut

        💡 ASTUCES
        • Réponses Telegram plus longues que LoRa
        • Contexte partagé entre Telegram et Mesh
        • /trafic 2 pour activité récente
        • /fullnodes 7 pour vue hebdomadaire

        🔐 SÉCURITÉ
        • Accès réservé utilisateurs autorisés
        • Actions tracées dans les logs
        • Redémarrages incluent identité demandeur

        Votre ID Telegram: {user_id}
        """).strip()
    
        return help_text

    def handle_top(self, message, sender_id, sender_info):
        """
        Gérer la commande /top [heures]
        Affiche les top talkers avec TOUS les types de paquets
        """
        info_print(f"Top: {sender_info}")
        
        # Parser les arguments
        parts = message.split()
        hours = 3  # Défaut: 3 heures pour Meshtastic
        
        if len(parts) > 1:
            try:
                requested = int(parts[1])
                hours = max(1, min(24, requested))
            except ValueError:
                hours = 3
        
        if not self.traffic_monitor:
            self.sender.send_single("❌ Traffic monitor non disponible", sender_id, sender_info)
            return
        
        try:
            # Version concise avec types de paquets
            report = self.traffic_monitor.get_quick_stats()
            
            self.sender.log_conversation(sender_id, sender_info, 
                                        f"/top {hours}" if hours != 3 else "/top", 
                                        report)
            self.sender.send_single(report, sender_id, sender_info)
            
        except Exception as e:
            error_msg = f"❌ Erreur top: {str(e)[:50]}"
            self.sender.send_single(error_msg, sender_id, sender_info)
    
    def handle_packets(self, message, sender_id, sender_info):
        """
        Nouvelle commande /packets pour voir la distribution des types
        """
        info_print(f"Packets: {sender_info}")
        
        # Parser les arguments
        parts = message.split()
        hours = 1  # Défaut: 1 heure
        
        if len(parts) > 1:
            try:
                requested = int(parts[1])
                hours = max(1, min(24, requested))
            except ValueError:
                hours = 1
        
        if not self.traffic_monitor:
            self.sender.send_single("❌ Traffic monitor non disponible", sender_id, sender_info)
            return
        
        try:
            # Résumé des types de paquets
            report = self.traffic_monitor.get_packet_type_summary(hours)
            
            self.sender.log_conversation(sender_id, sender_info, 
                                        f"/packets {hours}" if hours != 1 else "/packets", 
                                        report)
            self.sender.send_single(report, sender_id, sender_info)
            
        except Exception as e:
            error_msg = f"❌ Erreur packets: {str(e)[:50]}"
            self.sender.send_single(error_msg, sender_id, sender_info)

    def handle_histo(self, message, sender_id, sender_info):
        """
        Gérer la commande /histo [type] [heures]
        
        Types disponibles: pos, tele, node, text
        Sans argument: vue d'ensemble
        """
        info_print(f"Histo: {sender_info}")
        
        # Parser les arguments
        parts = message.split()
        packet_type = 'ALL'  # Par défaut: vue d'ensemble
        hours = 24
        
        # Argument 1: type de paquet (optionnel)
        if len(parts) > 1:
            packet_type = parts[1].strip().upper()
            # Valider le type
            if packet_type not in ['ALL', 'POS', 'TELE', 'NODE', 'TEXT']:
                error_msg = f"❌ Type inconnu: {parts[1]}\nTypes: pos, tele, node, text"
                self.sender.send_single(error_msg, sender_id, sender_info)
                return
        
        # Argument 2: heures (optionnel)
        if len(parts) > 2:
            try:
                hours = int(parts[2])
                hours = max(1, min(48, hours))  # Entre 1 et 48h
            except ValueError:
                hours = 24
        
        try:
            # Obtenir l'histogramme depuis traffic_monitor (utilise SQLite)
            if packet_type == 'ALL':
                histogram = self.traffic_monitor.get_packet_histogram_overview(hours)
                command_log = "/histo"
            else:
                # Pour les types spécifiques, utiliser get_hourly_histogram
                type_mapping = {
                    'POS': 'pos',
                    'TELE': 'telemetry',
                    'NODE': 'info',
                    'TEXT': 'messages'
                }
                filter_type = type_mapping.get(packet_type, 'all')
                histogram = self.traffic_monitor.get_hourly_histogram(filter_type, hours)
                command_log = f"/histo {packet_type.lower()}"
                if hours != 24:
                    command_log += f" {hours}"

            # Logger et envoyer
            self.sender.log_conversation(sender_id, sender_info, command_log, histogram)
            self.sender.send_single(histogram, sender_id, sender_info)

            info_print(f"✅ Histogram {packet_type} ({hours}h) envoyé à {sender_info}")
            
        except Exception as e:
            error_print(f"Erreur /histo: {e}")
            import traceback
            error_print(traceback.format_exc())
            
            error_msg = f"❌ Erreur: {str(e)[:30]}"
            self.sender.send_single(error_msg, sender_id, sender_info)

    def handle_hop(self, message, sender_id, sender_info, is_broadcast=False):
        """
        Gérer la commande /hop [heures]
        Alias pour /stats hop - affiche les nœuds triés par hop_start (portée max)
        
        Args:
            message: Message complet (ex: "/hop 48")
            sender_id: ID de l'expéditeur
            sender_info: Infos sur l'expéditeur
            is_broadcast: Si True, répondre en broadcast public
        """
        info_print(f"Hop: {sender_info} (broadcast={is_broadcast})")
        
        # Parser les arguments
        parts = message.split()
        hours = 24  # Défaut: 24 heures
        
        if len(parts) > 1:
            try:
                requested = int(parts[1])
                hours = max(1, min(168, requested))  # Entre 1h et 7 jours
            except ValueError:
                hours = 24
        
        if not self.traffic_monitor:
            self.sender.send_single("❌ Traffic monitor non disponible", sender_id, sender_info)
            return
        
        try:
            # Utiliser le système unifié des stats
            from handlers.command_handlers.unified_stats import UnifiedStatsCommands
            
            # Obtenir l'interface via le sender
            interface = None
            if hasattr(self.sender, '_get_interface'):
                try:
                    interface = self.sender._get_interface()
                except:
                    pass
            
            # Créer une instance de UnifiedStatsCommands
            unified_stats = UnifiedStatsCommands(
                self.traffic_monitor, 
                self.node_manager, 
                interface
            )
            
            # Obtenir le rapport
            params = [str(hours)] if hours != 24 else []
            report = unified_stats.get_stats('hop', params, channel='mesh')
            
            cmd = f"/hop {hours}" if hours != 24 else "/hop"
            self.sender.log_conversation(sender_id, sender_info, cmd, report)
            
            # Envoyer selon le mode (broadcast ou direct)
            if is_broadcast:
                self._send_broadcast_via_tigrog2(report, sender_id, sender_info, cmd)
            else:
                self.sender.send_single(report, sender_id, sender_info)
            
            info_print(f"✅ Hop stats ({hours}h) envoyées à {sender_info}")
            
        except Exception as e:
            error_print(f"Erreur /hop: {e}")
            import traceback
            error_print(traceback.format_exc())
            
            error_msg = f"❌ Erreur: {str(e)[:30]}"
            self.sender.send_single(error_msg, sender_id, sender_info)

    def handle_channel_debug(self, sender_id, sender_info):
        """Afficher le rapport de diagnostic des canaux"""
        info_print(f"Channel debug: {sender_info}")
        
        try:
            # Accéder à l'analyseur via le message_handler
            if hasattr(self.sender, 'message_handler'):
                bot = self.sender.message_handler
                if hasattr(bot, '_channel_analyzer'):
                    analyzer = bot._channel_analyzer
                    
                    # Rapport complet
                    report = analyzer.print_diagnostic_report()
                    
                    # Envoyer en plusieurs parties si trop long
                    max_len = 200  # Limite Meshtastic
                    if len(report) > max_len:
                        # Envoyer juste les stats rapides sur mesh
                        quick = analyzer.get_quick_stats()
                        self.sender.send_single(quick, sender_id, sender_info)
                        
                        # Log le rapport complet
                        info_print("RAPPORT COMPLET:")
                        info_print(report)
                    else:
                        self.sender.send_single(report, sender_id, sender_info)
                    
                    self.sender.log_conversation(sender_id, sender_info, 
                                                "/channel_debug", report)
                else:
                    self.sender.send_single("Analyseur non initialisé", 
                                           sender_id, sender_info)
            else:
                self.sender.send_single("Erreur accès analyseur", 
                                       sender_id, sender_info)
                
        except Exception as e:
            error_print(f"Erreur channel_debug: {e}")
            self.sender.send_single(f"Erreur: {str(e)[:50]}",
                                   sender_id, sender_info)

    def _send_broadcast_via_tigrog2(self, message, sender_id, sender_info, command):
        """
        Envoyer un message en broadcast via l'interface partagée

        Note: Utilise l'interface existante au lieu de créer une nouvelle connexion TCP.
        Cela évite les conflits de socket avec la connexion principale.
        
        Note: Ne log PAS la conversation ici - c'est fait par l'appelant avant l'envoi.
        Cela évite les logs en double.
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
            
        except Exception as e:
            error_print(f"❌ Échec broadcast {command}: {e}")
            error_print(traceback.format_exc())            
