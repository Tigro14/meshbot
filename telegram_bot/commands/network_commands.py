#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Commandes réseau Telegram : nodes, fullnodes, nodeinfo, rx
"""

from telegram import Update
from telegram.ext import ContextTypes
from telegram_bot.command_base import TelegramCommandBase
from utils import info_print, error_print
import asyncio
import time
import traceback

# Import optionnel de REMOTE_NODE_HOST/NAME avec fallback
try:
    from config import REMOTE_NODE_HOST, REMOTE_NODE_NAME
except ImportError:
    REMOTE_NODE_HOST = None
    REMOTE_NODE_NAME = "RemoteNode"


class NetworkCommands(TelegramCommandBase):
    """Gestionnaire des commandes réseau Telegram"""

    def __init__(self, telegram_integration):
        """
        Initialiser les commandes réseau

        Args:
            telegram_integration: Instance de TelegramIntegration
        """
        super().__init__(telegram_integration)
        self.mesh_commands = telegram_integration.mesh_commands
        self.stats_commands = telegram_integration.stats_commands

    async def rx_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /rx [node_filter] - Afficher les voisins mesh et stats MQTT
        
        Usage:
            /rx                    -> Stats du collecteur MQTT
            /rx tigro              -> Voisins du nœud 'tigro' (via MQTT/radio)
            /rx !16fad3dc          -> Voisins du nœud par ID
        """
        user = update.effective_user
        
        # Vérifier l'autorisation
        if not self.check_authorization(user.id):
            await update.effective_message.reply_text("❌ Non autorisé")
            return
        
        # Extraire le filtre optionnel
        node_filter = None
        if context.args and len(context.args) > 0:
            node_filter = ' '.join(context.args)
        
        # Logger la requête
        if node_filter:
            info_print(f"📱 Telegram /rx {node_filter}: {user.username}")
        else:
            info_print(f"📱 Telegram /rx (stats MQTT): {user.username}")
        
        def get_rx_info():
            try:
                # Cas 1: Pas d'argument -> Stats MQTT
                if not node_filter:
                    # Vérifier si le collecteur MQTT est disponible
                    mqtt_collector = self.message_handler.mqtt_neighbor_collector
                    
                    if mqtt_collector and mqtt_collector.enabled:
                        # Retourner le rapport détaillé du collecteur MQTT
                        return mqtt_collector.get_status_report(compact=False)
                    else:
                        return "❌ Collecteur MQTT de voisins non disponible ou désactivé.\n\nPour l'activer, configurez dans config.py:\n```\nMQTT_NEIGHBOR_ENABLED = True\nMQTT_NEIGHBOR_SERVER = \"serveurperso.com\"\nMQTT_NEIGHBOR_USER = \"meshdev\"\nMQTT_NEIGHBOR_PASSWORD = \"...\"\n```"
                
                # Cas 2: Avec argument -> Voisins du nœud spécifié
                if not self.message_handler.traffic_monitor:
                    return "❌ Traffic monitor non disponible"
                
                # Utiliser la méthode existante get_neighbors_report
                # avec compact=False pour format détaillé Telegram
                return self.message_handler.traffic_monitor.get_neighbors_report(
                    node_filter=node_filter,
                    compact=False
                )
                
            except Exception as e:
                error_print(f"Erreur /rx: {e}")
                error_print(traceback.format_exc())
                return f"❌ Erreur: {str(e)[:200]}"
        
        response = await asyncio.to_thread(get_rx_info)
        await update.effective_message.reply_text(response, parse_mode='Markdown')

    async def nodes_command(self, update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
        """Commande /nodes - Affiche tous les nœuds directs de votre node"""
        user = update.effective_user
        info_print(f"📱 Telegram /nodes: {user.username}")

        def get_nodes_list():
            try:
                # Vérifier que REMOTE_NODE_HOST est configuré
                if not REMOTE_NODE_HOST:
                    return "❌ REMOTE_NODE_HOST non configuré dans config.py"

                nodes = self.message_handler.remote_nodes_client.get_remote_nodes(
                    REMOTE_NODE_HOST)
                if not nodes:
                    return f"❌ Aucun nœud trouvé sur {REMOTE_NODE_NAME}"

                nodes.sort(key=lambda x: x.get('snr') if x.get('snr') is not None else -999, reverse=True)
                lines = [
                    f"📡 Nœuds DIRECTS de {REMOTE_NODE_NAME} ({len(nodes)}):\n"]

                for node in nodes:
                    name = node.get('name', 'Unknown')
                    snr = node.get('snr', 0.0)
                    rssi = node.get('rssi', 0)
                    last_heard = node.get('last_heard', 0)
                    hops_away = node.get('hops_away', 0)

                    elapsed = int(
                        time.time() - last_heard) if last_heard > 0 else 0
                    if elapsed < 60:
                        time_str = f"{elapsed}s"
                    elif elapsed < 3600:
                        time_str = f"{elapsed // 60}m"
                    elif elapsed < 86400:
                        time_str = f"{elapsed // 3600}h"
                    else:
                        time_str = f"{elapsed // 86400}j"

                    icon = "🟢" if snr >= 10 else "🟡" if snr >= 5 else "🟠" if snr >= 0 else "🔴"
                    lines.append(
                        f"{icon} {name}: SNR {snr:.1f}dB ({time_str})")

                return "\n".join(lines)
            except Exception as e:
                return f"❌ Erreur: {str(e)[:100]}"

        response = await asyncio.to_thread(get_nodes_list)
        await update.effective_message.reply_text(response)

    async def nodesmc_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /nodesmc [page|full] - Liste des contacts MeshCore avec pagination
        
        Usage:
            /nodesmc           -> Page 1 des contacts MeshCore (30 derniers jours)
            /nodesmc 2         -> Page 2 des contacts MeshCore (30 derniers jours)
            /nodesmc full      -> Tous les contacts (72 dernières heures)
        """
        user = update.effective_user
        
        # Vérifier l'autorisation
        if not self.check_authorization(user.id):
            await update.effective_message.reply_text("❌ Non autorisé")
            return
        
        # Extraire le numéro de page ou le mode "full" depuis context.args
        page = 1
        full_mode = False
        if context.args and len(context.args) > 0:
            if context.args[0].lower() == 'full':
                full_mode = True
                info_print(f"📱 Telegram /nodesmc FULL: {user.username}")
            else:
                try:
                    page = int(context.args[0])
                    page = max(1, page)  # Minimum page 1
                except ValueError:
                    page = 1
                info_print(f"📱 Telegram /nodesmc (page {page}): {user.username}")
        else:
            info_print(f"📱 Telegram /nodesmc (page {page}): {user.username}")
        
        def get_meshcore_contacts():
            try:
                # Mode FULL utilise 72h (3 jours), mode paginé utilise 30 jours
                days_filter = 3 if full_mode else 30
                # Utiliser la méthode existante qui récupère depuis la base de données
                return self.message_handler.remote_nodes_client.get_meshcore_paginated(
                    page=page, 
                    days_filter=days_filter,
                    full_mode=full_mode
                )
            except Exception as e:
                error_print(f"Erreur get_meshcore_contacts: {e}")
                error_print(traceback.format_exc())
                return f"❌ Erreur: {str(e)[:100]}"
        
        response = await asyncio.to_thread(get_meshcore_contacts)
        await update.effective_message.reply_text(response)

    async def fullnodes_command(
            self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /fullnodes - Liste complète alphabétique des nœuds
        
        Usage:
            /fullnodes [days] [search_expr]
            
        Examples:
            /fullnodes                    -> Tous les nœuds (30 derniers jours)
            /fullnodes 7                  -> Tous les nœuds (7 derniers jours)
            /fullnodes tigro              -> Nœuds contenant 'tigro' (30j)
            /fullnodes 7 tigro            -> Nœuds contenant 'tigro' (7j)
        """
        user = update.effective_user
        if not self.check_authorization(user.id):
            await update.effective_message.reply_text("Non autorisé")
            return

        # Extraire les arguments: [days] [search_expr]
        days = 30
        max_days = 365  # ✅ Limite raisonnable : 1 an
        search_expr = None

        if context.args and len(context.args) > 0:
            # Premier argument: soit un nombre de jours, soit une recherche
            try:
                requested_days = int(context.args[0])
                if requested_days > max_days:
                    # ✅ Informer l'utilisateur si demande excessive
                    await update.effective_message.reply_text(
                        f"⚠️ Maximum {max_days}j autorisé. Utilisation de {max_days}j."
                    )
                    days = max_days
                else:
                    days = max(1, requested_days)
                
                # Si il y a un second argument, c'est la recherche
                if len(context.args) > 1:
                    search_expr = ' '.join(context.args[1:])
            except ValueError:
                # Ce n'est pas un nombre, donc c'est directement une recherche
                search_expr = ' '.join(context.args)
                days = 30

        info_print(f"Telegram /fullnodes ({days}j, search='{search_expr}'): {user.username}")

        def get_full_nodes():
            try:
                return self.message_handler.remote_nodes_client.get_all_nodes_alphabetical(
                    days, search_expr=search_expr)
            except Exception as e:
                error_print(f"Erreur get_full_nodes: {e or 'Unknown error'}")
                error_print(traceback.format_exc())
                return f"Erreur: {str(e)[:100]}"

        response = await asyncio.to_thread(get_full_nodes)

        # Telegram a une limite de 4096 caractères par message
        if len(response) > 4000:
            # Découper en plusieurs messages
            chunks = []
            lines = response.split('\n')
            current_chunk = []
            current_length = 0

            for line in lines:
                line_length = len(line) + 1  # +1 pour le \n
                if current_length + line_length > 4000:
                    chunks.append('\n'.join(current_chunk))
                    current_chunk = [line]
                    current_length = line_length
                else:
                    current_chunk.append(line)
                    current_length += line_length

            if current_chunk:
                chunks.append('\n'.join(current_chunk))

            # Envoyer les chunks
            for i, chunk in enumerate(chunks):
                if i > 0:
                    await asyncio.sleep(1)  # Éviter rate limiting
                await update.effective_message.reply_text(chunk)
        else:
            await update.effective_message.reply_text(response)

    async def nodeinfo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /nodeinfo <nom_partiel_ou_id> [heures]
        Rapport détaillé sur un nœud spécifique

        AMÉLIORATION: Détecte et affiche tous les nœuds avec le même nom
        """
        user = update.effective_user
        if not context.args:
            await update.effective_message.reply_text("Usage: /nodeinfo <nom_ou_id> [heures]\\nEx: /nodeinfo tigrobot\\nEx: /nodeinfo !16fad3dc")
            return

        node_name_partial = context.args[0].lower()
        hours = 24
        if len(context.args) > 1:
            try:
                hours = int(context.args[1])
                hours = max(1, min(168, hours))
            except ValueError:
                hours = 24

        info_print(f"📱 Telegram /nodeinfo {node_name_partial} {hours}h: {user.username}")

        # Utiliser la logique métier partagée
        def get_node_report():
            success, report = self.mesh_commands.get_node_behavior_report(
                node_name_partial, hours
            )
            return report

        response = await asyncio.to_thread(get_node_report)

        # Diviser si trop long
        if len(response) > 4000:
            chunks = [response[i:i+4000] for i in range(0, len(response), 4000)]
            for chunk in chunks:
                await update.effective_message.reply_text(chunk)
                await asyncio.sleep(0.5)
        else:
            await update.effective_message.reply_text(response)

    async def neighbors_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /neighbors [filter] - Afficher les voisins mesh
        
        Usage:
            /neighbors                    -> Tous les voisins
            /neighbors tigro              -> Filtrer par nom de nœud
            /neighbors !16fad3dc          -> Filtrer par ID de nœud
        """
        user = update.effective_user
        
        # Vérifier l'autorisation
        if not self.check_authorization(user.id):
            await update.effective_message.reply_text("❌ Non autorisé")
            return
        
        # Extraire le filtre optionnel depuis context.args
        node_filter = None
        if context.args and len(context.args) > 0:
            node_filter = ' '.join(context.args)
        
        # Logger la requête
        if node_filter:
            info_print(f"📱 Telegram /neighbors {node_filter}: {user.username}")
        else:
            info_print(f"📱 Telegram /neighbors: {user.username}")
        
        def get_neighbors():
            try:
                # Vérifier que traffic_monitor est disponible (defensive)
                if not self.message_handler.traffic_monitor:
                    return "⚠️ Traffic monitor non disponible"
                
                # Appeler get_neighbors_report avec compact=False pour Telegram
                return self.message_handler.traffic_monitor.get_neighbors_report(
                    node_filter=node_filter,
                    compact=False
                )
            except Exception as e:
                error_print(f"Erreur get_neighbors: {e or 'Unknown error'}")
                error_print(traceback.format_exc())
                # Retourner un message d'erreur tronqué
                return f"❌ Erreur: {str(e)[:100]}"
        
        # Exécuter dans un thread pour ne pas bloquer
        response = await asyncio.to_thread(get_neighbors)
        
        # Chunking similaire à fullnodes_command (4000 caractères)
        if len(response) > 4000:
            # Découper en plusieurs messages
            chunks = []
            lines = response.split('\n')
            current_chunk = []
            current_length = 0
            
            for line in lines:
                line_length = len(line) + 1  # +1 pour le \n
                if current_length + line_length > 4000:
                    chunks.append('\n'.join(current_chunk))
                    current_chunk = [line]
                    current_length = line_length
                else:
                    current_chunk.append(line)
                    current_length += line_length
            
            if current_chunk:
                chunks.append('\n'.join(current_chunk))
            
            # Envoyer les chunks
            for i, chunk in enumerate(chunks):
                if i > 0:
                    await asyncio.sleep(1)  # Éviter rate limiting
                await update.effective_message.reply_text(chunk)
        else:
            await update.effective_message.reply_text(response)

    async def mqtt_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /mqtt - Afficher tous les nœuds entendus directement via MQTT
        
        Liste les nœuds qui ont envoyé des paquets NEIGHBORINFO via MQTT,
        avec leur LongName et leur dernière heure d'écoute.
        
        Usage:
            /mqtt          -> Tous les nœuds MQTT (48h)
            /mqtt 24       -> Nœuds MQTT des 24 dernières heures
        """
        user = update.effective_user
        
        # Vérifier l'autorisation
        if not self.check_authorization(user.id):
            await update.effective_message.reply_text("❌ Non autorisé")
            return
        
        # Extraire le nombre d'heures optionnel
        hours = 48  # Défaut: 48 heures
        if context.args and len(context.args) > 0:
            try:
                hours = int(context.args[0])
                hours = max(1, min(168, hours))  # Entre 1h et 7 jours
            except ValueError:
                await update.effective_message.reply_text("❌ Usage: /mqtt [heures]\nExemple: /mqtt 24")
                return
        
        # Logger la requête
        info_print(f"📱 Telegram /mqtt ({hours}h): {user.username}")
        
        def get_mqtt_nodes():
            try:
                # Vérifier si le collecteur MQTT est disponible
                mqtt_collector = self.message_handler.mqtt_neighbor_collector
                
                if not mqtt_collector or not mqtt_collector.enabled:
                    return "❌ Collecteur MQTT de voisins non disponible ou désactivé.\n\nPour l'activer, configurez dans config.py:\n```\nMQTT_NEIGHBOR_ENABLED = True\nMQTT_NEIGHBOR_SERVER = \"serveurperso.com\"\nMQTT_NEIGHBOR_USER = \"meshdev\"\nMQTT_NEIGHBOR_PASSWORD = \"...\"\n```"
                
                # Récupérer la liste des nœuds entendus via MQTT
                nodes = mqtt_collector.get_directly_heard_nodes(hours=hours)
                
                if not nodes:
                    return f"ℹ️ Aucun nœud MQTT entendu dans les {hours} dernières heures.\n\nLe collecteur MQTT est actif mais n'a pas encore reçu de paquets NEIGHBORINFO."
                
                # Formater la réponse
                lines = [
                    f"📡 Nœuds MQTT entendus directement ({len(nodes)} nœuds, {hours}h)\n"
                ]
                
                # Statut de connexion
                status = "Connecté 🟢" if mqtt_collector.connected else "Déconnecté 🔴"
                lines.append(f"Statut MQTT: {status}\n")
                
                # Liste des nœuds
                for i, node in enumerate(nodes, 1):
                    node_id = node['node_id']
                    longname = node['longname']
                    last_heard = node['last_heard']
                    
                    # Calculer le temps écoulé depuis la dernière écoute
                    elapsed = int(time.time() - last_heard) if last_heard > 0 else 0
                    if elapsed < 60:
                        time_str = f"{elapsed}s"
                    elif elapsed < 3600:
                        time_str = f"{elapsed // 60}m"
                    elif elapsed < 86400:
                        time_str = f"{elapsed // 3600}h"
                    else:
                        time_str = f"{elapsed // 86400}j"
                    
                    # Icône basée sur le temps écoulé
                    if elapsed < 3600:  # < 1h
                        icon = "🟢"
                    elif elapsed < 86400:  # < 24h
                        icon = "🟡"
                    else:
                        icon = "🟠"
                    
                    # Formatter: numéro, icône, nom, ID court, temps
                    # Extraire l'ID court (derniers 4 caractères hex)
                    short_id = node_id[-4:] if node_id.startswith('!') else node_id
                    
                    lines.append(f"{i}. {icon} {longname} ({short_id}) - {time_str}")
                
                return "\n".join(lines)
                
            except Exception as e:
                error_print(f"Erreur /mqtt: {e}")
                error_print(traceback.format_exc())
                return f"❌ Erreur: {str(e)[:200]}"
        
        # Exécuter dans un thread pour ne pas bloquer
        response = await asyncio.to_thread(get_mqtt_nodes)
        
        # Envoyer la réponse (sans Markdown pour éviter les erreurs de parsing)
        await update.effective_message.reply_text(response)

    async def keys_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /keys [node] - Vérifier l'état des clés publiques PKI
        
        Diagnostic pour les problèmes de DM encryptés dans Meshtastic 2.7.15+.
        Affiche l'état de l'échange de clés publiques PKI entre les nœuds.
        
        Usage:
            /keys              -> État global des clés (tous les nœuds)
            /keys tigro        -> Vérifier si 'tigro' a échangé sa clé
            /keys a76f40da     -> Vérifier clé d'un nœud par ID
        """
        # Log IMMEDIATELY when command is called
        info_print(f"🚨 DEBUG /keys: Command handler CALLED! update={update is not None}, context={context is not None}")
        
        try:
            user = update.effective_user
            info_print(f"🚨 DEBUG /keys: User ID={user.id}, Username={user.username}")
            
            # Vérifier l'autorisation
            if not self.check_authorization(user.id):
                info_print(f"🚨 DEBUG /keys: Authorization FAILED for user {user.id}")
                await update.effective_message.reply_text("❌ Non autorisé")
                return
            
            info_print(f"🚨 DEBUG /keys: Authorization OK for user {user.id}")
        except Exception as e:
            error_print(f"🚨 DEBUG /keys: Exception in command entry: {e}")
            error_print(traceback.format_exc())
            raise
        
        # Extraire le nom de nœud optionnel
        node_name = None
        if context.args and len(context.args) > 0:
            node_name = ' '.join(context.args)
        
        # Logger la requête
        if node_name:
            info_print(f"📱 Telegram /keys {node_name}: {user.username}")
        else:
            info_print(f"📱 Telegram /keys: {user.username}")
        
        def get_keys_info():
            try:
                info_print(f"🔍 DEBUG /keys: Starting get_keys_info() for node_name={node_name}")
                
                # Vérifier que network_handler est disponible
                # Le network_handler est dans le router du message_handler
                if not hasattr(self.message_handler, 'router'):
                    error_print(f"❌ DEBUG /keys: message_handler has no 'router' attribute")
                    return "❌ Network handler non disponible (pas de router)"
                
                if not hasattr(self.message_handler.router, 'network_handler'):
                    error_print(f"❌ DEBUG /keys: router has no 'network_handler' attribute")
                    return "❌ Network handler non disponible (pas de network_handler)"
                
                network_handler = self.message_handler.router.network_handler
                info_print(f"✅ DEBUG /keys: network_handler found")
                
                # Appeler directement les méthodes internes (sans threading)
                # Format détaillé pour Telegram (compact=False)
                if node_name:
                    info_print(f"🔍 DEBUG /keys: Calling _check_node_keys('{node_name}', compact=False)")
                    response = network_handler._check_node_keys(node_name, compact=False)
                    info_print(f"✅ DEBUG /keys: _check_node_keys returned: type={type(response).__name__}, len={len(response) if response else 'None'}")
                    info_print(f"✅ DEBUG /keys: Response preview: '{response[:100] if response else 'None'}'")
                else:
                    info_print(f"🔍 DEBUG /keys: Calling _check_all_keys(compact=False)")
                    response = network_handler._check_all_keys(compact=False)
                    info_print(f"✅ DEBUG /keys: _check_all_keys returned: type={type(response).__name__}, len={len(response) if response else 'None'}")
                
                info_print(f"✅ DEBUG /keys: Got response (len={len(response) if response else 'None'})")
                return response
                    
            except Exception as e:
                error_print(f"❌ Erreur /keys: {e}")
                error_print(traceback.format_exc())
                return f"❌ Erreur: {str(e)[:200]}"
        
        # Exécuter dans un thread pour ne pas bloquer
        info_print(f"🔍 DEBUG /keys: Calling asyncio.to_thread(get_keys_info)")
        response = await asyncio.to_thread(get_keys_info)
        
        # Envoyer la réponse
        info_print(f"📤 DEBUG /keys: Sending response (len={len(response) if response else 'None'})")
        info_print(f"📤 DEBUG /keys: Response preview: {response[:100] if response else 'None'}")
        
        try:
            if not response:
                error_print(f"❌ DEBUG /keys: Response is empty or None!")
                await update.effective_message.reply_text("❌ Erreur: Pas de réponse générée")
            else:
                await update.effective_message.reply_text(response)
                info_print(f"✅ DEBUG /keys: Response sent successfully")
        except Exception as e:
            error_print(f"❌ DEBUG /keys: Exception while sending response: {e}")
            error_print(traceback.format_exc())
            try:
                await update.effective_message.reply_text(f"❌ Erreur d'envoi: {str(e)[:100]}")
            except:
                pass

    async def propag_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /propag - Afficher les plus longues liaisons radio
        
        Affiche les liaisons radio les plus longues détectées dans le réseau mesh,
        triées par distance GPS entre les nœuds.
        
        Usage:
            /propag          -> Top 5 liaisons des dernières 24h
            /propag 48       -> Top 5 liaisons des dernières 48h
            /propag 24 10    -> Top 10 liaisons des dernières 24h
        """
        user = update.effective_user
        
        # DEBUG: Log au tout début pour vérifier que la méthode est appelée
        info_print(f"🔍 DEBUG: propag_command appelée par user {user.id} ({user.username})")
        
        # Vérifier l'autorisation
        if not self.check_authorization(user.id):
            info_print(f"⚠️ DEBUG: User {user.id} NON autorisé pour /propag")
            await update.effective_message.reply_text("❌ Non autorisé")
            return
        
        # Parser les arguments
        hours = 24
        top_n = 5
        
        if context.args:
            try:
                if len(context.args) >= 1:
                    hours = int(context.args[0])
                    hours = max(1, min(72, hours))  # Limiter entre 1 et 72h
                if len(context.args) >= 2:
                    top_n = int(context.args[1])
                    top_n = max(1, min(10, top_n))  # Limiter entre 1 et 10
            except ValueError:
                await update.effective_message.reply_text(
                    "❌ Usage: /propag [heures] [top_n]\n"
                    "Exemples:\n"
                    "  /propag          → Top 5 (24h)\n"
                    "  /propag 48       → Top 5 (48h)\n"
                    "  /propag 24 10    → Top 10 (24h)"
                )
                return
        
        # Logger la requête
        info_print(f"📱 Telegram /propag ({hours}h, top {top_n}): {user.username}")
        
        def get_propag_report():
            try:
                # Vérifier si le traffic monitor est disponible
                if not self.message_handler.traffic_monitor:
                    return "❌ Traffic monitor non disponible"
                
                # Générer le rapport (format détaillé pour Telegram)
                return self.message_handler.traffic_monitor.get_propagation_report(
                    hours=hours,
                    top_n=top_n,
                    max_distance_km=100,  # Rayon de 100km
                    compact=False  # Format détaillé pour Telegram
                )
                
            except Exception as e:
                error_print(f"Erreur /propag: {e}")
                error_print(traceback.format_exc())
                return f"❌ Erreur: {str(e)[:200]}"
        
        # Exécuter dans un thread pour ne pas bloquer
        response = await asyncio.to_thread(get_propag_report)
        
        # Envoyer la réponse
        await update.effective_message.reply_text(response)
