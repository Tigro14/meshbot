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
import meshtastic.tcp_interface
from utils_weather import get_weather_data
from config import *
from utils import *

class UtilityCommands:
    def __init__(self, esphome_client, traffic_monitor, sender, node_manager=None):
        self.esphome_client = esphome_client
        self.traffic_monitor = traffic_monitor
        self.sender = sender
        self.node_manager = node_manager
    
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
        """Gérer la commande /echo - tigrog2 diffuse dans le mesh"""

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
        info_print("🚀 Lancement thread d'envoi...")
        
        def send_echo_via_tigrog2():
            remote_interface = None
            try:
                info_print("")
                info_print("=" * 60)
                info_print("🔊 THREAD ECHO DÉMARRÉ")
                info_print("=" * 60)
                
                info_print(f"Connexion TCP à {REMOTE_NODE_HOST}:4403...")
                remote_interface = meshtastic.tcp_interface.TCPInterface(
                    hostname=REMOTE_NODE_HOST, 
                    portNumber=4403
                )
                
                info_print("✅ Connexion établie")
                info_print("⏳ Attente stabilisation (5s)...")
                time.sleep(5)
                info_print("✅ Stabilisation OK")

                author_short = current_sender.get_short_name(sender_id)
                echo_response = f"{author_short}: {echo_text}"
                
                info_print(f"📝 Message final: '{echo_response}'")
                info_print(f"   Auteur short: {author_short}")
                info_print(f"   Longueur finale: {len(echo_response)} caractères")
                
                # Vérifier node info
                if hasattr(remote_interface, 'localNode') and remote_interface.localNode:
                    node = remote_interface.localNode
                    if hasattr(node, 'shortName'):
                        info_print(f"✅ Node connecté: {node.shortName}")
                
                info_print("")
                info_print("📤 ENVOI DU MESSAGE...")
                
                # Essayer les 3 méthodes
                success = False
            
                # Méthode 1: Simple
                try:
                    info_print("Méthode 1: sendText() simple")
                    remote_interface.sendText(echo_response)
                    info_print("✅ Méthode 1 exécutée")
                    success = True
                except Exception as e1:
                    error_print(f"❌ Méthode 1 échouée: {e1}")
                
                if not success:
                    # Méthode 2: Avec destinationId
                    try:
                        info_print("Méthode 2: sendText() avec destinationId")
                        remote_interface.sendText(echo_response, destinationId='^all')
                        info_print("✅ Méthode 2 exécutée")
                        success = True
                    except Exception as e2:
                        error_print(f"❌ Méthode 2 échouée: {e2}")
                
                if not success:
                    # Méthode 3: Avec channelIndex
                    try:
                        info_print("Méthode 3: sendText() avec channelIndex")
                        remote_interface.sendText(
                            echo_response,
                            destinationId='^all',
                            channelIndex=0
                        )
                        info_print("✅ Méthode 3 exécutée")
                        success = True
                    except Exception as e3:
                        error_print(f"❌ Méthode 3 échouée: {e3}")
                
                if not success:
                    error_print("❌ TOUTES LES MÉTHODES ONT ÉCHOUÉ")
                    raise Exception("Impossible d'envoyer le message")
                
                info_print("")
                info_print("⏳ Attente transmission (10s)...")
                time.sleep(10)
                info_print("✅ Attente terminée")
                
                info_print("")
                info_print("=" * 60)
                info_print("✅ THREAD ECHO TERMINÉ")
                info_print("=" * 60)

                current_sender.log_conversation(sender_id, sender_info, message, echo_response)

            except Exception as e:
                error_print("")
                error_print("=" * 60)
                error_print("❌ ERREUR DANS THREAD ECHO")
                error_print("=" * 60)
                error_print(f"Exception: {e}")
                error_print(traceback.format_exc())
                error_print("=" * 60)

                try:
                    error_response = f"Erreur echo: {str(e)[:30]}"
                    current_sender.send_single(error_response, sender_id, sender_info)
                except:
                    pass
            finally:
                if remote_interface:
                    try:
                        info_print("🔌 Fermeture connexion...")
                        remote_interface.close()
                        info_print("✅ Connexion fermée")
                    except Exception as e:
                        error_print(f"Erreur fermeture: {e}")
        
        # Lancer le thread
        thread = threading.Thread(target=send_echo_via_tigrog2, daemon=True)
        thread.start()
        info_print(f"✅ Thread lancé: {thread.name}")
        info_print("=" * 60)

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

    def handle_weather(self, message, sender_id, sender_info):
        """
        Gérer la commande /weather [ville]

        Args:
            message: Message complet (ex: "/weather London")
            sender_id: ID de l'expéditeur
            sender_info: Infos sur l'expéditeur
        """
        info_print(f"Weather: {sender_info}")

        # Parser l'argument ville
        parts = message.split(maxsplit=1)
        location = None
        if len(parts) > 1:
            location = parts[1].strip()

        # Si pas de ville ou "help"/"aide", afficher l'aide
        if location and location.lower() in ['help', 'aide', '?']:
            help_text = (
                "🌤️ /weather [ville]\n"
                "Ex:\n"
                "/weather → Météo locale\n"
                "/weather Paris\n"
                "/weather London\n"
                "/weather New York"
            )
            self.sender.send_single(help_text, sender_id, sender_info)
            return

        # Récupérer la météo
        weather_data = get_weather_data(location)

        # Logger et envoyer
        cmd = f"/weather {location}" if location else "/weather"
        self.sender.log_conversation(sender_id, sender_info, cmd, weather_data)
        self.sender.send_single(weather_data, sender_id, sender_info)

    def _format_help(self):
        """Formater l'aide des commandes"""
        help_lines = [
            "/bot IA",
            "/power",
            "/sys",
            "/echo",
            "/annonce",
            "/nodes",
            "/stats [cmd]",
            "/db [cmd]",
            "/top",
            "/trace",
            "/packets",
            "/legend",
            "/weather",
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
        • Contexte conversationnel maintenu 30min
        • Réponses plus détaillées possibles sur Telegram vs mesh

        ⚡ SYSTÈME & MONITORING
        • /power - Télémétrie complète
          Batterie, solaire, température, pression, humidité
        • /weather [ville] - Météo 3 jours
          /weather → Géolocalisée
          /weather Paris, /weather London, etc.
        • /graphs [heures] - Graphiques historiques
          Défaut: 24h, max 48h
        • /sys - Informations système Pi5
          CPU, RAM, load average, uptime

        📡 RÉSEAU MESHTASTIC
        • /nodes - Liste nœuds directs tigrog2
        • /fullnodes [jours] - Liste alphabétique complète
          Défaut: 30j, max 365j, tri par longName

        📊 ANALYSE TRAFIC
        • /stats [cmd] [params] - Système unifié de statistiques
          Sous-commandes:
             - global : Vue d'ensemble réseau (défaut)
             - top [h] [n] : Top talkers
             - packets [h] : Distribution types de paquets
             - channel [h] : Utilisation du canal
             - histo [type] [h] : Histogramme temporel
             - traffic [h] : Historique messages publics
          Raccourcis: g, t, p, ch, h, tr
          Ex: /stats top 24 10, /stats channel 12
        • /trafic [heures] - Historique messages publics
          Défaut: 8h, max 24h, stats détaillées
        • /top [heures] [nombre] - Top talkers (alias)
          Défaut: 24h, top 10
        • /packets [heures] - Distribution paquets (alias)
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
        •echo <message> - Diffuser sur le réseau
          Préfixe auto, broadcast via tigrog2
          Ex: /echo Bonjour à tous!
        •annonce <message> - Diffuser sur le réseaudepuis le bot au lieu du node router

        ℹ️ UTILITAIRES
        • /legend - Légende indicateurs signal
        • /help - Cette aide complète

        🔧 ADMINISTRATION (si autorisé)
        • /rebootg2 [mdp] - Redémarrage tigrog2
        • /rebootpi [mdp] - Redémarrage Pi5
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

    def handle_annonce(self, message, sender_id, sender_info, packet):
        """Gérer la commande /annonce - diffuse depuis le bot local (serial)"""
        
        info_print("=" * 60)
        info_print("📢 HANDLE_ANNONCE APPELÉ")
        info_print("=" * 60)
        info_print(f"Message brut: '{message}'")
        info_print(f"Sender ID: 0x{sender_id:08x}")
        info_print(f"Sender info: {sender_info}")
        
        # Anti-doublon
        message_id = f"{sender_id}_{message}_{int(time.time())}"
        info_print(f"Message ID: {message_id}")
        
        if hasattr(self.sender, '_last_annonce_id'):
            info_print(f"Last annonce ID: {self.sender._last_annonce_id}")
            if self.sender._last_annonce_id == message_id:
                info_print("⚠️ Annonce déjà traitée, ignorée")
                return
        
        self.sender._last_annonce_id = message_id
        info_print("✅ Anti-doublon OK")
        
        annonce_text = message[9:].strip()  # Longueur de "/annonce "
        info_print(f"Texte extrait: '{annonce_text}'")
        info_print(f"Longueur: {len(annonce_text)} caractères")
        
        if not annonce_text:
            info_print("❌ Texte vide")
            self.sender.send_single("Usage: /annonce <texte>", sender_id, sender_info)
            return
    
        info_print(f"✅ Texte valide: '{annonce_text}'")
        
        # Envoyer directement via l'interface série locale
        try:
            author_short = self.sender.get_short_name(sender_id)
            annonce_response = f"{author_short}: {annonce_text}"
            
            info_print(f"📝 Message final: '{annonce_response}'")
            info_print(f"   Auteur short: {author_short}")
            info_print(f"   Longueur finale: {len(annonce_response)} caractères")
            
            # Récupérer l'interface locale
            interface = self.sender._get_interface()
            
            if not interface:
                error_print("❌ Interface locale non disponible")
                self.sender.send_single("Erreur: Interface non disponible", sender_id, sender_info)
                return
            
            info_print("📤 Envoi du message en broadcast...")
            
            # Envoyer en broadcast sur le mesh local
            interface.sendText(annonce_response, destinationId='^all')
            
            info_print("✅ Annonce diffusée depuis le bot local")
            info_print("=" * 60)
            
            # Logger la conversation
            self.sender.log_conversation(sender_id, sender_info, message, annonce_response)
            
        except Exception as e:
            error_print("")
            error_print("=" * 60)
            error_print("❌ ERREUR DANS ANNONCE")
            error_print("=" * 60)
            error_print(f"Exception: {e}")
            error_print(traceback.format_exc())
            error_print("=" * 60)
            
            try:
                error_response = f"Erreur annonce: {str(e)[:30]}"
                self.sender.send_single(error_response, sender_id, sender_info)
            except:
                pass            

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
