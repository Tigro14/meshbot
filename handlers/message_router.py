#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Routeur principal des messages et commandes
Orchestre tous les gestionnaires de commandes
"""

from config import DEBUG_MODE
from utils import info_print, debug_print, error_print
from .message_sender import MessageSender
from .command_handlers import (
    AICommands,
    NetworkCommands,
    SystemCommands,
    UtilityCommands
)
from .command_handlers.unified_stats import UnifiedStatsCommands
from .command_handlers.db_commands import DBCommands

class MessageRouter:
    def __init__(self, llama_client, esphome_client, remote_nodes_client,
                 node_manager, context_manager, interface, traffic_monitor=None,
                 bot_start_time=None, blitz_monitor=None, vigilance_monitor=None,
                 broadcast_tracker=None, companion_mode=False, dual_interface_manager=None):

        # Dépendances
        self.node_manager = node_manager
        self.interface = interface
        self.traffic_monitor = traffic_monitor
        self.broadcast_tracker = broadcast_tracker  # Callback pour tracker les broadcasts
        self.companion_mode = companion_mode  # Mode companion (MeshCore sans Meshtastic)
        
        # Commandes supportées en mode companion (non-Meshtastic)
        self.companion_commands = [
            '/bot',      # AI
            '/ia',       # AI (alias français)
            '/weather',  # Météo
            '/rain',     # Graphiques pluie
            '/power',    # ESPHome telemetry
            '/sys',      # Système (CPU, RAM, uptime)
            '/help',     # Aide
            '/blitz',    # Lightning (si activé)
            '/vigilance',# Vigilance météo (si activé)
            '/rebootpi', # Redémarrage Pi (authentifié)
            '/nodesmc'   # Contacts MeshCore (base SQLite, pas Meshtastic)
        ]

        # Message sender (gère envoi et throttling)
        # Pass dual_interface_manager for correct network routing in dual mode
        self.sender = MessageSender(interface, node_manager, dual_interface_manager)

        # Gestionnaires de commandes par domaine
        self.ai_handler = AICommands(llama_client, self.sender, broadcast_tracker=broadcast_tracker)
        self.network_handler = NetworkCommands(remote_nodes_client, self.sender, node_manager, traffic_monitor=traffic_monitor, interface=interface, broadcast_tracker=broadcast_tracker)
        self.system_handler = SystemCommands(interface, node_manager, self.sender, bot_start_time)
        self.utility_handler = UtilityCommands(esphome_client, traffic_monitor, self.sender, node_manager, blitz_monitor, vigilance_monitor, broadcast_tracker=broadcast_tracker)

        # Gestionnaire unifié des statistiques (nouveau système)
        self.unified_stats = UnifiedStatsCommands(traffic_monitor, node_manager, interface) if traffic_monitor else None

        # Gestionnaire des opérations de base de données
        self.db_handler = DBCommands(traffic_monitor, self.sender) if traffic_monitor else None
   
    def process_text_message(self, packet, decoded, message):
        """Point d'entrée principal pour traiter un message texte"""
        sender_id = packet.get('from', 0)
        to_id = packet.get('to', 0)
        my_id = None

        #  Récupérer la vraie interface si on a un serial_manager
        actual_interface = self.interface
        if hasattr(self.interface, 'get_interface'):
            actual_interface = self.interface.get_interface()
            if not actual_interface:
                error_print("❌ Interface non disponible pour traiter le message")
                return

        if hasattr(actual_interface, 'localNode') and actual_interface.localNode:
            my_id = getattr(actual_interface.localNode, 'nodeNum', 0)

        # Check if this is a MeshCore DM (marked by wrapper)
        # MeshCore DMs are always "for us" even if to_id doesn't match my_id
        is_meshcore_dm = packet.get('_meshcore_dm', False)
        is_for_me = is_meshcore_dm or ((to_id == my_id) if my_id else False)
        is_from_me = (sender_id == my_id) if my_id else False
        is_broadcast = to_id in [0xFFFFFFFF, 0]
        sender_info = self.node_manager.get_node_name(sender_id, actual_interface)
        
        # Determine network source from packet
        # In dual mode, packet has 'source' field: 'local', 'tcp', 'tigrog2' (Meshtastic) or 'meshcore'
        packet_source = packet.get('source', 'local')
        is_from_meshcore = (packet_source == 'meshcore')
        is_from_meshtastic = (packet_source in ['local', 'tcp', 'tigrog2'])
        
        # DEBUG: Log message routing decision
        debug_print(f"🔍 [ROUTER-DEBUG] _meshcore_dm={is_meshcore_dm} | is_for_me={is_for_me} | is_broadcast={is_broadcast} | to=0x{to_id:08x} | source={packet_source}")

        # For broadcast messages from MeshCore CHANNEL_MSG_RECV, strip "Sender: " prefix
        # MeshCore includes sender name in text: "Tigro: /echo test"
        # We need just the command: "/echo test"
        # Note: Now that we correctly identify sender_id, we check for any broadcast with prefix pattern
        original_message = message  # Always preserve the original
        if is_broadcast and ': ' in message:
            parts = message.split(': ', 1)
            if len(parts) == 2 and parts[1].startswith('/'):
                message = parts[1]  # Use only the command part
                debug_print(f"🔧 [ROUTER] Stripped sender prefix from Public channel message")
                debug_print(f"   Original: '{original_message}'")
                debug_print(f"   Cleaned:  '{message}'")

        # Gérer commandes broadcast-friendly (echo, my, weather, rain, bot, ia, info, propag, hop)
        broadcast_commands = ['/echo', '/my', '/weather', '/rain', '/bot', '/ia', '/info', '/propag', '/hop']
        is_broadcast_command = any(message.startswith(cmd) for cmd in broadcast_commands)

        # For broadcast messages, allow commands from own node (user on bot's node sending commands)
        # For DM messages, still filter is_from_me to prevent self-messaging
        # Loop prevention for broadcasts is handled by _is_recent_broadcast() in main_bot.py
        if is_broadcast_command and (is_broadcast or is_for_me):
            # Allow if: (1) it's a broadcast (even from own node) OR (2) it's a DM not from self
            if is_broadcast or not is_from_me:
                debug_print(f"🎯 [ROUTER] Broadcast command detected: is_broadcast={is_broadcast}, is_for_me={is_for_me}, is_from_me={is_from_me}")
                if message.startswith('/echo'):
                    info_print(f"ECHO PUBLIC de {sender_info}: '{message}'")
                    debug_print(f"📢 [ROUTER] Calling utility_handler.handle_echo() for Public channel")
                    # Pass original_message to preserve sender name prefix for /echo
                    self.utility_handler.handle_echo(message, sender_id, sender_info, packet, original_message)
                    debug_print(f"✅ [ROUTER] handle_echo() returned")
                elif message.startswith('/my'):
                    info_print(f"MY PUBLIC de {sender_info}")
                    self.network_handler.handle_my(sender_id, sender_info, is_broadcast=is_broadcast)
                elif message.startswith('/weather'):
                    info_print(f"WEATHER PUBLIC de {sender_info}: '{message}'")
                    self.utility_handler.handle_weather(message, sender_id, sender_info, is_broadcast=is_broadcast)
                elif message.startswith('/rain'):
                    info_print(f"RAIN PUBLIC de {sender_info}: '{message}'")
                    self.utility_handler.handle_rain(message, sender_id, sender_info, is_broadcast=is_broadcast)
                elif message.startswith('/bot'):
                    info_print(f"BOT PUBLIC de {sender_info}: '{message}'")
                    self.ai_handler.handle_bot(message, sender_id, sender_info, is_broadcast=is_broadcast)
                elif message.startswith('/ia'):
                    info_print(f"IA PUBLIC de {sender_info}: '{message}'")
                    self.ai_handler.handle_bot(message, sender_id, sender_info, is_broadcast=is_broadcast)
                elif message.startswith('/info'):
                    info_print(f"INFO PUBLIC de {sender_info}: '{message}'")
                    self.network_handler.handle_info(message, sender_id, sender_info, is_broadcast=is_broadcast)
                elif message.startswith('/propag'):
                    info_print(f"PROPAG PUBLIC de {sender_info}: '{message}'")
                    self.network_handler.handle_propag(message, sender_id, sender_info, is_broadcast=is_broadcast)
                elif message.startswith('/hop'):
                    info_print(f"HOP PUBLIC de {sender_info}: '{message}'")
                    self.utility_handler.handle_hop(message, sender_id, sender_info, is_broadcast=is_broadcast)
                return

        # Log messages pour nous
        if is_for_me or DEBUG_MODE:
            info_print(f"MESSAGE REÇU de {sender_info}: '{message}'")

        # Traiter seulement si pour nous
        if not is_for_me:
            return

        # Router la commande avec l'information sur le réseau source
        self._route_command(message, sender_id, sender_info, packet, is_from_meshcore, is_from_meshtastic)
    
    def _route_command(self, message, sender_id, sender_info, packet, is_from_meshcore=False, is_from_meshtastic=True):
        """Router une commande vers le bon gestionnaire"""
        from_id = packet.get('from', 0)
        text_parts = message.split()
        if not text_parts:
            return

        command = text_parts[0].lower()
        
        # En mode companion, filtrer les commandes non supportées
        if self.companion_mode:
            command_supported = any(message.startswith(cmd) for cmd in self.companion_commands)
            if not command_supported:
                info_print(f"⚠️ Commande {command} non supportée en mode companion (Meshtastic requis)")
                self.sender.send_single(
                    f"⚠️ Commande {command} désactivée en mode companion.\nCommandes dispo: {', '.join(self.companion_commands)}",
                    sender_id, sender_info
                )
                return
        
        # ===================================================================
        # NETWORK ISOLATION: Block cross-network commands
        # ===================================================================
        # MeshCore-only commands (cannot be used from Meshtastic)
        meshcore_only_commands = ['/nodesmc', '/trafficmc']
        
        # Meshtastic-only commands (cannot be used from MeshCore)
        # Note: Order matters - check longer commands first to avoid false matches
        # /my REMOVED: Now works with both MT and MC (uses local rx_history, no TCP)
        meshtastic_only_commands = ['/nodemt', '/trafficmt', '/neighbors', '/nodes', '/trace']
        
        # Check if MeshCore command is being called from Meshtastic
        if is_from_meshtastic:
            for mc_cmd in meshcore_only_commands:
                if message.startswith(mc_cmd):
                    info_print(f"🚫 Commande MeshCore {mc_cmd} appelée depuis Meshtastic - BLOQUÉE")
                    self.sender.send_single(
                        f"🚫 {mc_cmd} est réservé au réseau MeshCore.\nUtilisez /nodemt ou /trafficmt pour Meshtastic.",
                        sender_id, sender_info
                    )
                    return
        
        # Check if Meshtastic command is being called from MeshCore
        if is_from_meshcore:
            for mt_cmd in meshtastic_only_commands:
                # Use word boundary check to avoid false matches (e.g., /nodes matching /nodesmc)
                if message == mt_cmd or message.startswith(mt_cmd + ' '):
                    info_print(f"🚫 Commande Meshtastic {mt_cmd} appelée depuis MeshCore - BLOQUÉE")
                    self.sender.send_single(
                        f"🚫 {mt_cmd} est réservé au réseau Meshtastic.\nUtilisez /nodesmc ou /trafficmc pour MeshCore.",
                        sender_id, sender_info
                    )
                    return
        
        # ===================================================================
        
        # Commandes IA
        if message.startswith('/bot'):
            self.ai_handler.handle_bot(message, sender_id, sender_info)
        elif message.startswith('/ia'):
            self.ai_handler.handle_bot(message, sender_id, sender_info)
        
        # Commandes réseau
        elif message.startswith('/my'):
            self.network_handler.handle_my(sender_id, sender_info, is_broadcast=False)
        elif message.startswith('/meshcore'):
            self.network_handler.handle_meshcore(message, sender_id, sender_info)
        elif message.startswith('/nodesmc'):
            self.network_handler.handle_nodesmc(message, sender_id, sender_info)
        elif message.startswith('/nodemt'):
            self.network_handler.handle_nodemt(message, sender_id, sender_info)
        elif message.startswith('/nodes'):  
            self.network_handler.handle_nodes(message, sender_id, sender_info)
        elif message.startswith('/neighbors'):
            self.network_handler.handle_neighbors(message, sender_id, sender_info)
        elif message.startswith('/propag'):
            self.network_handler.handle_propag(message, sender_id, sender_info)
        elif message.startswith('/info'):
            self.network_handler.handle_info(message, sender_id, sender_info)
        elif message.startswith('/keys'):
            self.network_handler.handle_keys(message, sender_id, sender_info)
        
        # ===================================================================
        # Commandes système avec authentification
        # ===================================================================
        elif message.startswith('/sys'):
            self.system_handler.handle_sys(sender_id, sender_info)
        
        elif message.startswith('/rebootpi'):
            # ✅ Parser les arguments et appeler avec vérification d'auth
            parts = message.split()  # ['/rebootpi', 'password']
            response = self.system_handler.handle_reboot_command(from_id, parts)
            self.sender.send_single(response, sender_id, sender_info)
            self.sender.log_conversation(sender_id, sender_info, message, response)
        
        elif message.startswith('/rebootnode'):
            # ✅ Parser les arguments et appeler avec vérification d'auth
            parts = message.split()  # ['/rebootnode', 'node_name', 'password']
            response = self.system_handler.handle_rebootnode_command(from_id, parts)
            self.sender.send_single(response, sender_id, sender_info)
            self.sender.log_conversation(sender_id, sender_info, message, response)

        # ===================================================================

        # ===================================================================
        # Commandes de statistiques unifiées (nouveau système)
        # ===================================================================
        elif message.startswith('/stats'):
            self._handle_unified_stats(message, sender_id, sender_info)

        # ===================================================================
        # Commandes de base de données
        # ===================================================================
        elif message.startswith('/db'):
            self._handle_db(message, sender_id, sender_info)

        # Commandes utilitaires
        elif message.startswith('/power'):
            self.utility_handler.handle_power(sender_id, sender_info)
        elif message.startswith('/weather'):
            self.utility_handler.handle_weather(message, sender_id, sender_info)
        elif message.startswith('/rain'):
            self.utility_handler.handle_rain(message, sender_id, sender_info)
        elif message.startswith('/vigi'):
            self.utility_handler.handle_vigi(sender_id, sender_info)
        elif message.startswith('/graphs'):
            self.utility_handler.handle_graphs(message, sender_id, sender_info)
        elif message.startswith('/trafic'):
            self.utility_handler.handle_trafic(message, sender_id, sender_info)
        elif message.startswith('/top'):
            self.utility_handler.handle_top(message, sender_id, sender_info)
        elif message.startswith('/histo'):  
            self.utility_handler.handle_histo(message, sender_id, sender_info)
        elif message.startswith('/hop'):
            self.utility_handler.handle_hop(message, sender_id, sender_info)
        elif message.startswith('/trace'):  
            self.network_handler.handle_trace(message, sender_id, sender_info, packet)
        elif message.startswith('/packets'):
           self.utility_handler.handle_packets(message, sender_id, sender_info)
        elif message.startswith('/channel_debug'):
            self.utility_handler.handle_channel_debug(sender_id, sender_info)
        elif message.startswith('/legend'):
            self.utility_handler.handle_legend(sender_id, sender_info)
        elif message.startswith('/help') or message.startswith('/?'):
            self.utility_handler.handle_help(sender_id, sender_info, is_from_meshcore=is_from_meshcore)
        
        # Commande inconnue
        else:
            if message.startswith('/'):
                info_print(f"Commande inconnue de {sender_info}: '{message}'")
                self.utility_handler.handle_help(sender_id, sender_info, is_from_meshcore=is_from_meshcore)
            else:
                if DEBUG_MODE:
                    debug_print(f"Message normal reçu: '{message}'")
    
    def _handle_unified_stats(self, message, sender_id, sender_info):
        """
        Gérer la commande /stats [subcommand] [params]
        Nouveau système unifié pour Mesh et Telegram
        """
        # Vérifier que unified_stats est disponible
        if not self.unified_stats:
            self.sender.send_single("❌ Stats non disponibles", sender_id, sender_info)
            return

        # Vérifier throttling
        if not self.sender.check_throttling(sender_id, sender_info):
            return

        # Parser les arguments
        parts = message.split()
        subcommand = parts[1] if len(parts) > 1 else 'global'
        params = parts[2:] if len(parts) > 2 else []

        try:
            # Appeler la business logic unifiée (channel='mesh' pour LoRa)
            response = self.unified_stats.get_stats(
                subcommand=subcommand,
                params=params,
                channel='mesh'  # Adaptation automatique pour LoRa
            )

            # Logger et envoyer
            self.sender.log_conversation(sender_id, sender_info, message, response)
            self.sender.send_chunks(response, sender_id, sender_info)

            info_print(f"✅ Stats '{subcommand}' envoyées à {sender_info}")

        except Exception as e:
            error_print(f"Erreur _handle_unified_stats: {e}")
            import traceback
            error_print(traceback.format_exc())
            self.sender.send_single(f"❌ Erreur: {str(e)[:50]}", sender_id, sender_info)

    def _handle_db(self, message, sender_id, sender_info):
        """
        Gérer la commande /db [subcommand] [params]
        Opérations de base de données unifiées
        """
        # Vérifier que db_handler est disponible
        if not self.db_handler:
            self.sender.send_single("❌ DB non disponible", sender_id, sender_info)
            return

        # Parser les arguments
        parts = message.split()
        params = parts[1:] if len(parts) > 1 else []

        try:
            # Appeler le handler DB (channel='mesh' pour LoRa)
            info_print(f"📊 Commande DB '{' '.join(params)}' de {sender_info}")
            self.db_handler.handle_db(
                sender_id=sender_id,
                sender_info=sender_info,
                params=params,
                channel='mesh'  # Adaptation automatique pour LoRa
            )

            info_print(f"✅ DB '{params[0] if params else 'help'}' traité pour {sender_info}")

        except Exception as e:
            error_print(f"Erreur _handle_db: {e}")
            import traceback
            error_print(traceback.format_exc())
            self.sender.send_single(f"❌ Erreur: {str(e)[:50]}", sender_id, sender_info)

    def cleanup_throttling_data(self):
        """Nettoyer les données de throttling (appelé périodiquement)"""
        self.sender.cleanup_throttling()

    def format_help_telegram(self, user_id=None):
        """Format aide détaillée pour Telegram"""
        help_text = self.utility_handler._format_help_telegram()

        # 🔍 DEBUG
        info_print(f"DEBUG help_text in router length: {len(help_text) if help_text else 'None'}")
        info_print(f"DEBUG help_text in router preview: {help_text[:100] if help_text else 'None'}")

        # Remplacer le placeholder user_id si fourni
        if user_id:
            help_text = help_text.replace("{user_id}", str(user_id))
        else:
            help_text = help_text.replace("\nVotre ID Telegram : {user_id}", "")

        return help_text
