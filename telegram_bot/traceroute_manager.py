#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gestionnaire de traceroute pour Telegram
Gère les requêtes de traceroute et les réponses
"""

from telegram import Update
from telegram.ext import ContextTypes
from utils import info_print, error_print, debug_print
from safe_tcp_connection import SafeTCPConnection
import time
import asyncio
import traceback
import threading

# Import optionnel de REMOTE_NODE_HOST avec fallback
try:
    from config import REMOTE_NODE_HOST
except ImportError:
    REMOTE_NODE_HOST = None

# Import Meshtastic protobuf pour traceroute natif
try:
    from meshtastic import mesh_pb2
    MESHTASTIC_PROTOBUF_AVAILABLE = True
except ImportError:
    MESHTASTIC_PROTOBUF_AVAILABLE = False
    print("⚠️ Modules protobuf Meshtastic non disponibles")


class TracerouteManager:
    """Gestionnaire centralisé pour les traceroutes Telegram/Meshtastic"""

    def __init__(self, telegram_integration):
        """
        Initialiser le gestionnaire de traceroute

        Args:
            telegram_integration: Instance de TelegramIntegration
        """
        self.telegram = telegram_integration
        self.pending_traces = {}  # node_id -> {'telegram_chat_id': int, 'timestamp': float, 'short_name': str}
        self.trace_timeout = 45  # 45 secondes

    def _find_node_by_short_name(self, identifier):
        """
        Trouver le node_id d'un nœud par plusieurs méthodes:
        - Short name: "tigro"
        - Long name: "tigro Tigro Network"
        - Hex ID: "3c7c", "!3c7c", "0x3c7c", "a76f40da", "!a76f40da"
        - Decimal ID: "15484", "2807920858"

        Returns:
            int: node_id si trouvé, None sinon
        """
        identifier = identifier.strip()
        identifier_lower = identifier.lower()

        # === ÉTAPE 1 : Détection si c'est un ID numérique ===
        node_id_candidate = None

        # Format: !hex (ex: !3c7c ou !a76f40da)
        if identifier.startswith('!'):
            try:
                node_id_candidate = int(identifier[1:], 16)
                debug_print(
                    f"🔍 Format détecté: Hex avec ! → 0x{node_id_candidate:08x}")
            except ValueError:
                pass

        # Format: 0xhex (ex: 0x3c7c)
        elif identifier_lower.startswith('0x'):
            try:
                node_id_candidate = int(identifier, 16)
                debug_print(
                    f"🔍 Format détecté: Hex avec 0x → 0x{node_id_candidate:08x}")
            except ValueError:
                pass

        # Format: hex pur (ex: 3c7c ou a76f40da)
        elif len(identifier) in [4, 8] and all(c in '0123456789abcdefABCDEF' for c in identifier):
            try:
                node_id_candidate = int(identifier, 16)
                debug_print(
                    f"🔍 Format détecté: Hex pur → 0x{node_id_candidate:08x}")
            except ValueError:
                pass

        # Format: decimal (ex: 15484 ou 2807920858)
        elif identifier.isdigit():
            try:
                node_id_candidate = int(identifier)
                debug_print(
                    f"🔍 Format détecté: Décimal → 0x{node_id_candidate:08x}")
            except ValueError:
                pass

        # === ÉTAPE 2 : Si c'est un ID, vérifier qu'il existe ===
        if node_id_candidate is not None:
            # Normaliser (32 bits)
            node_id_candidate = node_id_candidate & 0xFFFFFFFF

            # Vérifier dans la base locale
            if node_id_candidate in self.telegram.node_manager.node_names:
                node_name = self.telegram.node_manager.node_names[node_id_candidate]
                info_print(
                    f"✅ Nœud trouvé par ID: {node_name} (!{node_id_candidate:08x})")
                return node_id_candidate

            # Vérifier dans l'interface
            try:
                if hasattr(self.telegram.message_handler.interface, 'nodes'):
                    nodes = self.telegram.message_handler.interface.nodes

                    for node_id, node_info in nodes.items():
                        # Normaliser node_id de l'interface
                        if isinstance(node_id, str):
                            if node_id.startswith('!'):
                                node_id_int = int(node_id[1:], 16) & 0xFFFFFFFF
                            else:
                                node_id_int = int(node_id, 16) & 0xFFFFFFFF
                        else:
                            node_id_int = int(node_id) & 0xFFFFFFFF

                        if node_id_int == node_id_candidate:
                            # Récupérer le nom
                            node_name = "Unknown"
                            if isinstance(node_info,
                                          dict) and 'user' in node_info:
                                user_info = node_info['user']
                                if isinstance(user_info, dict):
                                    node_name = user_info.get('longName') or user_info.get(
                                        'shortName') or "Unknown"

                            info_print(
                                f"✅ Nœud trouvé par ID dans interface: {node_name} (!{node_id_candidate:08x})")
                            return node_id_candidate
            except Exception as e:
                debug_print(f"Erreur recherche ID dans interface: {e}")

            # ID fourni mais nœud n'existe pas
            debug_print(
                f"⚠️ ID 0x{node_id_candidate:08x} fourni mais nœud inconnu")
            # Retourner quand même l'ID (peut être un nœud hors ligne mais
            # valide)
            info_print(
                f"ℹ️ Utilisation de l'ID 0x{node_id_candidate:08x} (nœud peut être hors ligne)")
            return node_id_candidate

        # === ÉTAPE 3 : Recherche par nom (short ou long) ===
        # 3.1. Chercher dans la base locale
        for node_id, full_name in self.telegram.node_manager.node_names.items():
            # Gérer le cas où node_names contient des dicts au lieu de strings
            if isinstance(full_name, dict):
                # Extraire le nom du dict (priorité: longName > shortName > str(dict))
                full_name = full_name.get('longName') or full_name.get('shortName') or str(full_name)

            # S'assurer que full_name est bien une string
            if not isinstance(full_name, str):
                continue

            full_name_lower = full_name.lower()

            # Extraire le short name (première partie avant espace)
            node_short = full_name.split()[0].lower(
            ) if ' ' in full_name else full_name_lower

            # Match sur short name OU long name
            if node_short == identifier_lower or full_name_lower == identifier_lower:
                info_print(
                    f"✅ Nœud trouvé par nom dans base locale: {full_name} (!{node_id:08x})")
                return node_id

            # Match partiel sur long name (contient)
            if identifier_lower in full_name_lower and len(identifier) >= 3:
                info_print(
                    f"✅ Nœud trouvé par nom partiel: {full_name} (!{node_id:08x})")
                return node_id

        # 3.2. Chercher dans l'interface en temps réel
        try:
            if hasattr(self.telegram.message_handler.interface, 'nodes'):
                nodes = self.telegram.message_handler.interface.nodes

                for node_id, node_info in nodes.items():
                    if isinstance(node_info, dict) and 'user' in node_info:
                        user_info = node_info['user']
                        if isinstance(user_info, dict):
                            short = user_info.get(
                                'shortName', '').lower().strip()
                            long_name = user_info.get(
                                'longName', '').lower().strip()

                            # Match exact
                            if short == identifier_lower or long_name == identifier_lower:
                                # Convertir node_id
                                if isinstance(node_id, str):
                                    if node_id.startswith('!'):
                                        node_id_int = int(
                                            node_id[1:], 16) & 0xFFFFFFFF
                                    else:
                                        node_id_int = int(
                                            node_id, 16) & 0xFFFFFFFF
                                else:
                                    node_id_int = int(node_id) & 0xFFFFFFFF

                                display_name = long_name or short
                                info_print(
                                    f"✅ Nœud trouvé par nom dans interface: {display_name} (!{node_id_int:08x})")
                                return node_id_int

                            # Match partiel
                            if len(identifier) >= 3 and (
                                    identifier_lower in short or identifier_lower in long_name):
                                if isinstance(node_id, str):
                                    if node_id.startswith('!'):
                                        node_id_int = int(
                                            node_id[1:], 16) & 0xFFFFFFFF
                                    else:
                                        node_id_int = int(
                                            node_id, 16) & 0xFFFFFFFF
                                else:
                                    node_id_int = int(node_id) & 0xFFFFFFFF

                                display_name = long_name or short
                                info_print(
                                    f"✅ Nœud trouvé par nom partiel dans interface: {display_name} (!{node_id_int:08x})")
                                return node_id_int
        except Exception as e:
            debug_print(f"Erreur recherche nom dans interface: {e}")

        # === ÉTAPE 4 : Rien trouvé ===
        debug_print(f"❌ Nœud '{identifier}' introuvable")
        return None

    def cleanup_expired_traces(self):
        """Nettoyer les traces expirées (appelé périodiquement)"""
        try:
            current_time = time.time()
            expired = []

            for node_id, trace_data in self.pending_traces.items():
                if current_time - trace_data['timestamp'] > self.trace_timeout:
                    expired.append(node_id)

            for node_id in expired:
                trace_data = self.pending_traces[node_id]
                info_print(f"⏱️ Trace expirée pour {trace_data['full_name']}")

                # Notifier l'utilisateur Telegram
                try:
                    asyncio.run_coroutine_threadsafe(
                        self.telegram.application.bot.send_message(
                            chat_id=trace_data['telegram_chat_id'],
                            text=f"⏱️ Timeout: Pas de réponse de {trace_data['full_name']}\n"
                            f"Le nœud est peut-être hors ligne ou hors de portée."
                        ),
                        self.telegram.loop
                    ).result(timeout=5)
                except Exception as e:
                    error_print(
                        f"Erreur notification timeout: {e or 'Unknown error'}")

                del self.pending_traces[node_id]

            if expired:
                debug_print(f"🧹 {len(expired)} traces expirées nettoyées")

        except Exception as e:
            error_print(
                f"Erreur cleanup_expired_traces: {e or 'Unknown error'}")

    def handle_trace_response(self, from_id, message_text):
        """
        Traiter une réponse de traceroute depuis le mesh
        """
        try:
            # Early return: no traces pending to match against
            if not self.pending_traces:
                return False
            
            # Vérifier si c'est une réponse attendue
            if from_id not in self.pending_traces:
                debug_print(f"handle_trace_response: from_id 0x{from_id:08x} not in pending_traces")
                return False

            debug_print(f"handle_trace_response: from_id 0x{from_id:08x} found in pending_traces")

            # Vérifier que le message ressemble à un traceroute
            trace_indicators = [
                "Traceroute",
                "🔍",
                "Hops:",
                "Route:",
                "Signal:",
                "hopStart:",
                "hopLimit:"
            ]

            matches = [ind for ind in trace_indicators if ind in message_text]
            debug_print(f"handle_trace_response: {len(matches)} trace indicators found")

            if not matches:
                debug_print(f"handle_trace_response: message has no trace indicators")
                return False

            # C'est bien une réponse de trace !
            trace_data = self.pending_traces[from_id]
            chat_id = trace_data['telegram_chat_id']
            node_name = trace_data['full_name']
            elapsed_time = time.time() - trace_data['timestamp']

            info_print(f"🎯 Traceroute reçu de {node_name} ({elapsed_time:.1f}s)")

            # Envoyer la réponse à Telegram
            try:
                asyncio.run_coroutine_threadsafe(
                    self.telegram.application.bot.send_message(
                        chat_id=chat_id,
                        text=f"📊 Traceroute de {node_name}\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"{message_text}\n\n"
                        f"⏱️ Temps de réponse: {elapsed_time:.1f}s"
                    ),
                    self.telegram.loop
                ).result(timeout=10)

            except Exception as send_error:
                error_print(
                    f"Erreur envoi Telegram: {send_error or 'Unknown error'}")

            # Supprimer la trace de la liste des pending
            del self.pending_traces[from_id]

            return True

        except Exception as e:
            error_print(
                f"Erreur dans handle_trace_response: {e or 'Unknown error'}")
            error_print(traceback.format_exc())
            return False

    def test_trace_system(self):
        """
        Tester le système de traceroute
        À appeler depuis le debug interface ou au démarrage
        """
        info_print("=" * 60)
        info_print("🧪 TEST SYSTÈME TRACEROUTE")
        info_print("=" * 60)

        # Test 1: Telegram disponible
        info_print("Test 1: Telegram disponible")
        info_print(f"   running: {self.telegram.running}")
        info_print(f"   application: {self.telegram.application is not None}")
        info_print(f"   loop: {self.telegram.loop is not None}")

        # Test 2: Message handler disponible
        info_print("Test 2: Message handler")
        info_print(f"   message_handler: {self.telegram.message_handler is not None}")
        if self.telegram.message_handler:
            info_print(
                f"   interface: {self.telegram.message_handler.interface is not None}")

        # Test 3: Node manager
        info_print("Test 3: Node manager")
        info_print(f"   node_manager: {self.telegram.node_manager is not None}")
        if self.telegram.node_manager:
            info_print(f"   Nœuds connus: {len(self.telegram.node_manager.node_names)}")

        # Test 4: Pending traces
        info_print("Test 4: Pending traces")
        info_print(f"   Dict initialisé: {hasattr(self, 'pending_traces')}")
        info_print(f"   Traces actuelles: {len(self.pending_traces)}")

        # Test 5: Timeout
        info_print("Test 5: Configuration")
        info_print(f"   trace_timeout: {self.trace_timeout}s")

        info_print("=" * 60)
        info_print("✅ Test système terminé")
        info_print("=" * 60)

    async def _trace_command(self, update: Update,
                             context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /trace [short_id] - Traceroute mesh actif
        VERSION AVEC FIX THREAD

        Note: Pas de vérification d'autorisation - /trace est accessible à tous
        """
        user = update.effective_user
        info_print(f"📱 Telegram /trace: {user.username or user.first_name}")

        # Vérifier si un short_id est fourni
        args = context.args

        if not args or len(args) == 0:
            # === MODE PASSIF : Trace depuis bot vers utilisateur ===
            mesh_identity = self.telegram._get_mesh_identity(user.id)

            if mesh_identity:
                node_id = mesh_identity['node_id']
                display_name = mesh_identity['display_name']
            else:
                node_id = user.id & 0xFFFFFFFF
                display_name = user.username or user.first_name

            response_parts = []
            response_parts.append(f"🔍 Traceroute Telegram → {display_name}")
            response_parts.append("")
            response_parts.append("✅ Connexion DIRECTE")
            response_parts.append("📱 Via: Internet/Telegram")
            response_parts.append("🔒 Protocol: HTTPS/TLS")
            response_parts.append("")
            response_parts.append(f"Route: Telegram → bot")
            response_parts.append("")
            response_parts.append("ℹ️ Note:")
            response_parts.append("Les commandes Telegram ne passent")
            response_parts.append("pas par le réseau mesh LoRa.")
            response_parts.append("")
            response_parts.append("💡 Astuce:")
            response_parts.append("Utilisez /trace <short_id> pour tracer")
            response_parts.append("depuis un nœud mesh vers le bot.")

            await update.message.reply_text("\n".join(response_parts))
            return

        # === MODE ACTIF : Trace depuis nœud mesh vers bot ===
        target_short_name = args[0].strip()

        info_print(f"🎯 Traceroute actif demandé vers: {target_short_name}")

        # ===================================================================
        # FIX: Créer une fonction séparée au lieu d'une nested function
        # pour éviter les problèmes de scope dans le thread
        # ===================================================================

        info_print("🔄 Préparation du thread...")

        try:
            # Lancer dans un thread avec wrapper
            trace_thread = threading.Thread(
                target=self._execute_active_trace_wrapper,
                args=(
                    target_short_name,
                    update.effective_chat.id,
                    user.username),
                daemon=True,
                name=f"Traceroute-{target_short_name}"
            )

            info_print("▶️  Lancement du thread...")
            trace_thread.start()
            info_print("✅ Thread lancé avec succès")

        except Exception as thread_error:
            error_print(f"❌ ERREUR lancement thread: {thread_error}")
            error_print(traceback.format_exc())
            await update.message.reply_text(f"❌ Erreur technique: {str(thread_error)[:100]}")

    def _execute_active_trace(self, target_short_name, chat_id, username):
        """Traceroute avec timeout approprié"""
        try:
            # Vérifier que REMOTE_NODE_HOST est configuré
            if not REMOTE_NODE_HOST:
                asyncio.run_coroutine_threadsafe(
                    self.telegram.application.bot.send_message(
                        chat_id=chat_id,
                        text="❌ REMOTE_NODE_HOST non configuré dans config.py"
                    ),
                    self.telegram.loop
                ).result(timeout=5)
                return

            info_print("=" * 60)
            info_print("🚀 Traceroute NATIF Meshtastic démarré")
            info_print(f"   Target: {target_short_name}")
            info_print("=" * 60)

            # 1. Trouver le node_id
            info_print("🔍 Étape 1: Recherche du node_id...")

            try:
                target_node_id = self._find_node_by_short_name(
                    target_short_name)
            except Exception as find_error:
                error_print(f"❌ ERREUR _find_node_by_short_name: {find_error}")
                error_print(traceback.format_exc())

                try:
                    asyncio.run_coroutine_threadsafe(
                        self.telegram.application.bot.send_message(
                            chat_id=chat_id,
                            text=f"❌ Erreur recherche nœud: {str(find_error)[:100]}"
                        ),
                        self.telegram.loop
                    ).result(timeout=5)
                except BaseException:
                    pass
                return

            # Check if node was found BEFORE trying to use node_id
            if not target_node_id:
                error_print(f"❌ Nœud '{target_short_name}' introuvable")
                asyncio.run_coroutine_threadsafe(
                    self.telegram.application.bot.send_message(
                        chat_id=chat_id,
                        text=f"❌ Nœud '{target_short_name}' introuvable\n"
                        f"Utilisez /nodes pour voir la liste"
                    ),
                    self.telegram.loop
                ).result(timeout=5)
                return

            target_full_name = self.telegram.node_manager.get_node_name(target_node_id)
            info_print(f"✅ Nœud trouvé: {target_full_name}")
            info_print(
                f"   Node ID: 0x{target_node_id:08x} ({target_node_id})")

            info_print(f"✅ Trace enregistrée")
            # Enregistrer la trace
            self.pending_traces[target_node_id] = {
                'telegram_chat_id': chat_id,
                'timestamp': time.time(),
                'full_name': f"{target_short_name} (!{target_node_id:08x})"
            }

            # Lancer le traceroute avec timeout plus long
            with SafeTCPConnection(REMOTE_NODE_HOST, wait_time=2, timeout=45) as remote_interface:
                trace_msg = f"/trace !{target_node_id:08x}"
                remote_interface.sendText(trace_msg)

                # Message de confirmation
                asyncio.run_coroutine_threadsafe(
                    self.telegram.application.bot.send_message(
                        chat_id=chat_id,
                        text=f"🎯 Traceroute lancé vers {target_short_name}\n"
                        f"⏳ Attente réponse (max 60s)..."
                    ),
                    self.telegram.loop
                ).result(timeout=5)

        except Exception as e:
            error_print(f"Erreur trace active: {e or 'Unknown error'}")
            asyncio.run_coroutine_threadsafe(
                self.telegram.application.bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ Erreur technique: {str(e)[:100]}"
                ),
                self.telegram.loop
            ).result(timeout=5)

    def _execute_active_trace_wrapper(
            self, target_short_name, chat_id, username):
        """
        Wrapper pour execute_active_trace qui capture TOUTES les exceptions
        Fonction de classe (pas nested) pour éviter les problèmes de scope
        """
        info_print("=" * 60)
        info_print("🚀 _execute_active_trace_wrapper démarré")
        info_print(f"   Target: {target_short_name}")
        info_print(f"   Chat ID: {chat_id}")
        info_print(f"   User: {username}")
        info_print("=" * 60)

        try:
            self._execute_active_trace(target_short_name, chat_id, username)
        except Exception as e:
            error_print(
                f"Erreur non catchée dans wrapper trace: {e or 'Unknown error'}")
            error_print(traceback.format_exc())

            # Notifier l'utilisateur
            try:
                asyncio.run_coroutine_threadsafe(
                    self.telegram.application.bot.send_message(
                        chat_id=chat_id,
                        text=f"❌ Erreur interne: {str(e)[:100]}"
                    ),
                    self.telegram.loop
                ).result(timeout=5)
            except Exception as e:
                error_print("❌ Impossible de notifier l'utilisateur")

    def handle_traceroute_response(self, packet, decoded):
        """
        Traiter une réponse TRACEROUTE_APP native Meshtastic
        """
        try:
            from_id = packet.get('from', 0)

            info_print(f"🔍 Traitement TRACEROUTE_APP de 0x{from_id:08x}")

            # Vérifier si c'est une réponse attendue
            if from_id not in self.pending_traces:
                info_print(f"⚠️  Traceroute de 0x{from_id:08x} non attendu")
                return

            trace_data = self.pending_traces[from_id]
            chat_id = trace_data['telegram_chat_id']
            node_name = trace_data['full_name']

            info_print(
                f"✅ Réponse de traceroute attendue trouvée: {node_name}")

            # Parser la réponse traceroute
            route = []

            # Le payload contient la route sous forme de RouteDiscovery
            # protobuf
            if 'payload' in decoded:
                payload = decoded['payload']

                try:
                    # Décoder le protobuf RouteDiscovery
                    from meshtastic import mesh_pb2
                    route_discovery = mesh_pb2.RouteDiscovery()
                    route_discovery.ParseFromString(payload)

                    info_print(f"📋 Route découverte:")
                    for i, node_id in enumerate(route_discovery.route):
                        node_name_route = self.telegram.node_manager.get_node_name(
                            node_id)
                        route.append({
                            'node_id': node_id,
                            'name': node_name_route,
                            'position': i
                        })
                        info_print(
                            f"   {i}. {node_name_route} (!{node_id:08x})")

                except Exception as parse_error:
                    error_print(
                        f"❌ Erreur parsing RouteDiscovery: {parse_error}")
                    # Fallback: afficher le payload brut
                    info_print(f"Payload brut: {payload.hex()}")

            # Construire le message pour Telegram
            if route:
                route_parts = []
                route_parts.append(f"📊 **Traceroute vers {node_name}**")
                route_parts.append(f"━━━━━━━━━━━━━━━━━━━━")
                route_parts.append("")
                route_parts.append(f"🎯 Route complète ({len(route)} nœuds):")
                route_parts.append("")

                for i, hop in enumerate(route):
                    hop_name = hop['name']
                    hop_id = hop['node_id']

                    if i == 0:
                        icon = "🏁"  # Départ (bot)
                    elif i == len(route) - 1:
                        icon = "🎯"  # Arrivée (destination)
                    else:
                        icon = "🔀"  # Relay intermédiaire

                    route_parts.append(f"{icon} **Hop {i}:** {hop_name}")
                    route_parts.append(f"   ID: `!{hop_id:08x}`")

                    if i < len(route) - 1:
                        route_parts.append("   ⬇️")

                route_parts.append("")
                route_parts.append(f"📏 **Distance:** {len(route) - 1} hop(s)")

                elapsed = time.time() - trace_data['timestamp']
                route_parts.append(f"⏱️ **Temps:** {elapsed:.1f}s")

                telegram_message = "\n".join(route_parts)
            else:
                # Pas de route décodée
                telegram_message = (
                    f"📊 **Traceroute vers {node_name}**\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"⚠️ Route non décodable\n"
                    f"Le nœud a répondu mais le format n'est pas standard.\n\n"
                    f"ℹ️ Cela peut arriver avec certaines versions du firmware."
                )

            # Envoyer à Telegram
            info_print(f"📤 Envoi du traceroute à Telegram...")
            try:
                asyncio.run_coroutine_threadsafe(
                    self.telegram.application.bot.send_message(
                        chat_id=chat_id,
                        text=telegram_message,
                        parse_mode='Markdown'
                    ),
                    self.telegram.loop
                ).result(timeout=10)
            except Exception as send_error:
                error_print(f"Erreur envoi Telegram: {send_error}")

            info_print(f"✅ Traceroute envoyé à Telegram")

            # Supprimer la trace
            del self.pending_traces[from_id]
            info_print(f"🧹 Trace supprimée")

        except Exception as e:
            error_print(
                f"Erreur handle_traceroute_response;: {e or 'Unknown error'}")
            error_print(traceback.format_exc())
