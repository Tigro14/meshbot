#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Commandes mesh Telegram : echo, echomt, echomc
"""

from telegram import Update
from telegram.ext import ContextTypes
from telegram_bot.command_base import TelegramCommandBase
from utils import info_print, error_print, debug_print
import asyncio
import time
import threading


class MeshCommands(TelegramCommandBase):
    """Gestionnaire des commandes mesh Telegram"""

    def _send_echo_to_network(self, message, network_type=None):
        """
        Envoyer un message echo sur le réseau mesh via l'interface partagée du bot.
        Évite de créer une nouvelle connexion TCP qui tuerait la connexion principale.
        
        Args:
            message: Message formaté à envoyer (ex: "Tigro: test")
            network_type: Type de réseau ciblé ('meshtastic', 'meshcore', ou None pour auto-detect)
            
        Returns:
            str: Message de résultat (succès ou erreur)
        """
        try:
            if not self.interface:
                return "❌ Interface bot non disponible"
            
            debug_print(f"📤 Envoi echo via interface partagée: '{message}'")
            debug_print(f"   Network type: {network_type or 'auto-detect'}")
            
            # ========================================
            # DUAL MODE: Route to specific network
            # ========================================
            if network_type and self.dual_interface and self.dual_interface.is_dual_mode():
                from dual_interface_manager import NetworkSource
                
                if network_type == 'meshtastic':
                    if not self.dual_interface.has_meshtastic():
                        return "❌ Réseau Meshtastic non disponible"
                    network_source = NetworkSource.MESHTASTIC
                    debug_print("🔍 [DUAL MODE] Routing to Meshtastic network")
                elif network_type == 'meshcore':
                    if not self.dual_interface.has_meshcore():
                        return "❌ Réseau MeshCore non disponible"
                    network_source = NetworkSource.MESHCORE
                    debug_print("🔍 [DUAL MODE] Routing to MeshCore network")
                else:
                    return "❌ Type de réseau invalide"
                
                # Send via dual interface manager (broadcast on public channel)
                success = self.dual_interface.send_message(
                    message, 
                    0xFFFFFFFF,  # Broadcast destination
                    network_source,
                    channelIndex=0  # Public channel
                )
                
                if success:
                    network_name = "Meshtastic" if network_type == 'meshtastic' else "MeshCore"
                    info_print(f"✅ Message envoyé via {network_name}")
                    return f"✅ Echo diffusé sur {network_name}: {message}"
                else:
                    error_print(f"❌ Échec envoi sur réseau {network_type}")
                    return f"❌ Échec envoi sur réseau {network_type}"
            
            # ========================================
            # SINGLE MODE: Use direct interface
            # ========================================
            # Detect interface type to handle MeshCore vs Meshtastic differences
            is_meshcore = hasattr(self.interface, '__class__') and 'MeshCore' in self.interface.__class__.__name__
            
            if is_meshcore:
                # MeshCore: Send as broadcast (0xFFFFFFFF) on public channel (channelIndex=0)
                debug_print("🔍 Interface MeshCore détectée - envoi broadcast sur canal public")
                self.interface.sendText(message, destinationId=0xFFFFFFFF, channelIndex=0)
                info_print("✅ Message envoyé via MeshCore (broadcast, canal public)")
                return f"✅ Echo diffusé (MeshCore): {message}"
            else:
                # Meshtastic: Broadcast on public channel (channelIndex=0 is default)
                debug_print("🔍 Interface Meshtastic détectée - envoi broadcast sur canal public")
                self.interface.sendText(message, channelIndex=0)
                info_print("✅ Message envoyé via Meshtastic (broadcast, canal public)")
                return f"✅ Echo diffusé (Meshtastic): {message}"
                
        except Exception as e:
            error_print(f"❌ Erreur sendText via interface: {e}")
            import traceback
            error_print(traceback.format_exc())
            return f"❌ Échec envoi: {str(e)[:50]}"

    async def _execute_echo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE, network_type=None):
        """
        Logique commune pour toutes les commandes echo
        
        Args:
            update: Update Telegram
            context: Context Telegram
            network_type: 'meshtastic', 'meshcore', ou None pour auto-detect
        """
        user = update.effective_user
        
        if not context.args:
            cmd_name = "/echo" if network_type is None else f"/echo{network_type[:2]}"
            await update.effective_message.reply_text(f"Usage: {cmd_name} <message>")
            return

        echo_text = ' '.join(context.args)
        cmd_desc = "auto" if network_type is None else network_type
        info_print(f"📱 Telegram /echo ({cmd_desc}): {user.username} -> '{echo_text}'")

        # Message de confirmation immédiat
        status_msg = await update.effective_message.reply_text("📤 Envoi en cours...")

        def send_echo():
            try:
                # Utiliser le mapping Telegram → Meshtastic
                mesh_identity = self.get_mesh_identity(user.id)

                if mesh_identity:
                    prefix = mesh_identity['short_name']
                    info_print(f"🔄 Echo avec identité mappée: {prefix}")
                else:
                    username = user.username or user.first_name
                    prefix = username[:4]
                    info_print(f"⚠️ Echo sans mapping: {prefix}")

                message = f"{prefix}: {echo_text}"
                
                # Envoyer via l'interface partagée
                return self._send_echo_to_network(message, network_type)

            except Exception as e:
                error_print(f"❌ Exception send_echo: {e}")
                import traceback
                error_print(traceback.format_exc())
                return f"❌ Erreur echo: {str(e)[:50]}"

        # Exécuter la fonction dans un thread
        def execute_and_reply():
            try:
                result = send_echo()

                # Envoyer le résultat via l'event loop de Telegram
                asyncio.run_coroutine_threadsafe(
                    status_msg.edit_text(result),
                    self.telegram.loop
                ).result(timeout=5)

            except Exception as e:
                error_print(f"❌ Erreur execute_and_reply: {e}")
                try:
                    asyncio.run_coroutine_threadsafe(
                        status_msg.edit_text(f"❌ Erreur: {str(e)[:50]}"),
                        self.telegram.loop
                    ).result(timeout=5)
                except BaseException:
                    pass

        # Lancer dans un thread
        thread = threading.Thread(target=execute_and_reply, daemon=True, name=f"TelegramEcho-{cmd_desc}")
        thread.start()
        info_print(f"✅ Thread echo lancé: {thread.name}")

    async def echo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /echo <message> - Diffuser sur le mesh (réseau actuel)
        
        Utilise l'interface partagée du bot (serial ou TCP selon configuration).
        Ne nécessite plus REMOTE_NODE_HOST.
        En mode dual, utilise le réseau principal (Meshtastic).
        """
        await self._execute_echo_command(update, context, network_type=None)

    async def echomt_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /echomt <message> - Diffuser sur le réseau Meshtastic
        
        Commande spécifique pour cibler explicitement le réseau Meshtastic.
        Utile en mode dual pour forcer l'envoi sur Meshtastic.
        En mode single, identique à /echo.
        """
        await self._execute_echo_command(update, context, network_type='meshtastic')

    async def echomc_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Commande /echomc <message> - Diffuser sur le réseau MeshCore
        
        Commande spécifique pour cibler explicitement le réseau MeshCore.
        Utile en mode dual pour forcer l'envoi sur MeshCore.
        En mode single MeshCore, identique à /echo.
        """
        await self._execute_echo_command(update, context, network_type='meshcore')
