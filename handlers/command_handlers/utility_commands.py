#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gestionnaire des commandes utilitaires
"""

import time
import threading
import meshtastic.tcp_interface
from config import *
from utils import *

class UtilityCommands:
    def __init__(self, esphome_client, traffic_monitor, sender):
        self.esphome_client = esphome_client
        self.traffic_monitor = traffic_monitor
        self.sender = sender
    
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
            import traceback
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
            import traceback
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
        # Anti-doublon
        message_id = f"{sender_id}_{message}_{int(time.time())}"
        if hasattr(self.sender, '_last_echo_id') and self.sender._last_echo_id == message_id:
            debug_print("⚠️ Echo déjà traité, ignoré")
            return
        self.sender._last_echo_id = message_id
        
        echo_text = message[6:].strip()
        
        if not echo_text:
            self.sender.send_single("Usage: /echo <texte>", sender_id, sender_info)
            return
        
        info_print(f"Echo via tigrog2: {sender_info} -> '{echo_text}'")
        
    def send_echo_via_tigrog2():
            remote_interface = None
            try:
                debug_print(f"Connexion TCP à tigrog2 pour echo...")
                remote_interface = meshtastic.tcp_interface.TCPInterface(
                    hostname=REMOTE_NODE_HOST, 
                    portNumber=4403
                )
                
                # ✅ Attendre stabilisation
                time.sleep(2)
                
                author_short = self.sender.get_short_name(sender_id)
                echo_response = f"{author_short}: {echo_text}"
                
                debug_print(f"Envoi broadcast: '{echo_response}'")
                # ✅ FIX : Forcer le broadcast explicitement
                # Méthode 1 : destinationId vide ou '^all'
                try:
                    remote_interface.sendText(
                        echo_response,
                        destinationId='^all',  # Broadcast explicite
                        channelIndex=0  # ✅ Canal primaire explicite
                    )
                    info_print("✅ Echo envoyé en broadcast via destinationId='^all sur le canal 0'")
                except Exception as e1:
                    debug_print(f"Échec méthode 1 ('^all'): {e1}")
                    # Méthode 2 : Broadcast ID numérique
                    try:
                        remote_interface.sendText(
                            echo_response,
                            destinationId=0xFFFFFFFF  # Broadcast explicite
                        )
                        info_print("✅ Echo envoyé en broadcast via destinationId=0xFFFFFFFF")
                    except Exception as e2:
                        debug_print(f"Échec méthode 2 (0xFFFFFFFF): {e2}")
                        # Méthode 3 : Sans destinationId (comportement par défaut)
                        remote_interface.sendText(echo_response)
                    info_print("✅ Echo envoyé via sendText() par défaut")

                
                # ✅ Attendre envoi (1s suffit après l'envoi)
                time.sleep(1)
                
                debug_print(f"✅ Echo diffusé via tigrog2: '{echo_response}'")
                self.sender.log_conversation(sender_id, sender_info, message, echo_response)
                
            except Exception as e:
                error_print(f"Erreur echo via tigrog2: {e}")
                try:
                    error_response = f"Erreur echo tigrog2: {str(e)[:30]}"
                    self.sender.send_single(error_response, sender_id, sender_info)
                except:
                    pass
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
    
    def _format_help(self):
        """Formater l'aide des commandes"""
        help_lines = [
            "• /bot IA",
            "• /power",
            "• /sys ",
            "• /echo <msg>",
            "• /nodes",
            "• /top",
            "• /trace",
            "• /packets",
            "• /legend ",
            "• /help"
        ]
        return "\n".join(help_lines)

    def _format_help_telegram(self, user_id=None):
        """Format aide détaillée pour Telegram (sans contrainte de taille)"""
        help_text = """📖 AIDE COMPLÈTE - BOT MESHTASTIC

        🤖 CHAT IA
        Message direct → Conversation avec l'IA
        Contexte conversationnel maintenu 30min
        Réponses détaillées possibles sur Telegram

        ⚡ SYSTÈME & MONITORING
        /power - Télémétrie complète
        → Batterie, solaire, température, pression, humidité
        /sys - Informations système Pi5
        → CPU, RAM, load average, uptime

        📡 RÉSEAU MESHTASTIC
        /nodes - Liste complète des nœuds directs depuis tigrog2 PV
        /fullnodes [jours] - Liste alphabétique complète
        → Par défaut : 30 derniers jours (max 90j)
        → Tri par longName

        📊 ANALYSE TRAFIC
        /trafic [heures] - Historique messages publics
        → Par défaut : 8 dernières heures (max 24h)
        → Statistiques détaillées et top émetteurs
        /trace <node> - Traceroute mesh vers node (id; longname, short, ...)
        → Analyse le chemin des messages
        → Identifie les relays potentiels

        📢 DIFFUSION
        /echo <message> - Diffuser sur le réseau
        → Préfixe automatique avec votre nom court
        → Diffusé via tigrog2 en broadcast
        → Exemple : /echo Bonjour à tous!

        ℹ️ UTILITAIRES
        /legend - Légende des indicateurs de signal
        /help - Cette aide complète

        🔧 ADMINISTRATION (si autorisé)
        /rebootg2 - Redémarrage tigrog2
        → Redémarre le nœud + envoi télémétrie
        /rebootpi - Redémarrage Pi5
        → Redémarrage complet du système
        → Traçabilité complète dans les logs

        📋 LIMITES & INFORMATIONS
        Throttling : 5 commandes/5min par utilisateur
        Contexte IA : 6 messages max, timeout 30min
        Historique trafic : 1000 messages, rétention 24h
        Nœuds distants : filtre 3 jours par défaut

        💡 ASTUCES
        Les réponses Telegram peuvent être plus longues que sur LoRa
        Le contexte conversationnel est partagé entre Telegram et Mesh
        Utilisez /trafic 2 pour voir l'activité récente
        /fullnodes 7 pour une vue hebdomadaire du réseau

        🔐 SÉCURITÉ
        Accès réservé aux utilisateurs autorisés
        Toutes les actions sont tracées dans les logs
        Les redémarrages incluent l'identité du demandeur

        Votre ID Telegram: {}""".format(user_id if user_id else "non disponible")

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

