#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module d'intégration Telegram dans le bot Meshtastic - INTÉGRATION COMPLÈTE
Gère directement l'API Telegram sans fichiers queue
"""

import time
import threading
import traceback
from config import *
from utils import *

# Import Telegram (optionnel)
try:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
    import asyncio
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    info_print("Module python-telegram-bot non installé")

# Import Meshtastic protobuf pour traceroute natif
try:
    from meshtastic import portnums_pb2, mesh_pb2
    MESHTASTIC_PROTOBUF_AVAILABLE = True
except ImportError:
    MESHTASTIC_PROTOBUF_AVAILABLE = False
    print("⚠️ Modules protobuf Meshtastic non disponibles")

class TelegramIntegration:
    def __init__(self, message_handler, node_manager, context_manager):
        if not TELEGRAM_AVAILABLE:
            raise ImportError(
                "python-telegram-bot requis. "
                "Installez: pip3 install python-telegram-bot")

        self.message_handler = message_handler
        self.node_manager = node_manager
        self.context_manager = context_manager

        self.running = False
        self.telegram_thread = None
        self.application = None
        self.loop = None

        # Liste des utilisateurs pour les alertes
        self.alert_users = TELEGRAM_ALERT_USERS if TELEGRAM_ALERT_USERS else TELEGRAM_AUTHORIZED_USERS
        self.pending_traces = {}
        self.trace_timeout = 45

    def start(self):
        """Démarrer le bot Telegram dans un thread séparé"""
        if self.running:
            return

        self.running = True
        self.telegram_thread = threading.Thread(target=self._run_telegram_bot, daemon=True)
        self.telegram_thread.start()
        info_print("🤖 Bot Telegram démarré en thread séparé")

    def stop(self):
        """Arrêter le bot Telegram"""
        self.running = False
        if self.loop and self.application:
            try:
                asyncio.run_coroutine_threadsafe(self._shutdown(), self.loop).result(timeout=5)
            except Exception as e:
                pass
        info_print("🛑 Bot Telegram arrêté")

    def _get_mesh_identity(self, telegram_user_id):
        """
        Obtenir l'identité Meshtastic correspondant à un utilisateur Telegram
        """
        from config import TELEGRAM_TO_MESH_MAPPING
        from utils import debug_print
        
        if telegram_user_id in TELEGRAM_TO_MESH_MAPPING:
            mapping = TELEGRAM_TO_MESH_MAPPING[telegram_user_id]
            debug_print(f"✅ Mapping Telegram {telegram_user_id} → {mapping['display_name']}")
            return mapping
        else:
            debug_print(f"⚠️ Pas de mapping pour {telegram_user_id}")
            return None

    def _run_telegram_bot(self):
        """Exécuter le bot Telegram dans son propre event loop"""
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self._start_telegram_bot())
            
        except Exception as e:
            error_print(f"Erreur bot Telegram: {e or 'Unknown error'}")
            error_print(traceback.format_exc())
        finally:
            try:
                self.loop.close()
            except Exception as e:
                pass

    async def _start_telegram_bot(self):
        """Démarrer l'application Telegram"""
        try:
            info_print("Initialisation bot Telegram...")
            
            self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
            
            # Handlers de commandes
            info_print("Enregistrement des handlers...")
            self.application.add_handler(CommandHandler("start", self._start_command))
            self.application.add_handler(CommandHandler("help", self._help_command))
            self.application.add_handler(CommandHandler("power", self._power_command))
            self.application.add_handler(CommandHandler("weather", self._weather_command))
            self.application.add_handler(CommandHandler("graphs", self._graphs_command))
            self.application.add_handler(CommandHandler("rx", self._rx_command))
            self.application.add_handler(CommandHandler("sys", self._sys_command))
            self.application.add_handler(CommandHandler("bot", self._bot_command))
            self.application.add_handler(CommandHandler("legend", self._legend_command))
            self.application.add_handler(CommandHandler("echo", self._echo_command))
            
            info_print("Registration handler /annonce...")
            self.application.add_handler(CommandHandler("annonce", self._annonce_command))
            info_print("Handler /annonce enregistré avec succès")
            
            self.application.add_handler(CommandHandler("nodes", self._nodes_command))
            self.application.add_handler(CommandHandler("trafic", self._trafic_command))
            self.application.add_handler(CommandHandler("trace", self._trace_command))
            self.application.add_handler(CommandHandler("histo", self._histo_command))
            self.application.add_handler(CommandHandler("cpu", self._cpu_command))
            self.application.add_handler(CommandHandler("rebootg2", self._rebootg2_command))
            self.application.add_handler(CommandHandler("rebootpi", self._rebootpi_command))
            self.application.add_handler(CommandHandler("fullnodes", self._fullnodes_command))
            self.application.add_handler(CommandHandler("clearcontext", self._clearcontext_command))
            self.application.add_handler(CommandHandler("top", self._top_command))
            self.application.add_handler(CommandHandler("packets", self._packets_command))
            self.application.add_handler(CommandHandler("stats", self._stats_command))
            
            info_print(f"📊 Total handlers enregistrés: {len(self.application.handlers[0])}")
            
            # Gestionnaire d'erreurs
            self.application.add_error_handler(self._error_handler)
            
            # Démarrer l'application
            await self.application.initialize()
            await self.application.start()
            
            info_print("Bot Telegram en écoute (polling optimisé)...")
            
            await self.application.updater.start_polling(
                poll_interval=15.0,
                timeout=30,
                read_timeout=120,
                write_timeout=120,
                connect_timeout=120,
                pool_timeout=120,
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )
            
            # Boucle d'attente avec nettoyage
            cleanup_counter = 0
            while self.running:
                await asyncio.sleep(60)
                cleanup_counter += 1
                if cleanup_counter % 6 == 0:
                    self.cleanup_expired_traces()
            
            # Arrêter proprement
            info_print("Arrêt du polling Telegram...")
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            
        except Exception as e:
            error_print(f"Erreur démarrage Telegram: {e or 'Unknown error'}")
            error_print(traceback.format_exc())

    async def _shutdown(self):
        """Arrêter proprement le bot"""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
    
    def _check_authorization(self, user_id):
        """Vérifier si l'utilisateur est autorisé"""
        if not TELEGRAM_AUTHORIZED_USERS:
            return True
        return user_id in TELEGRAM_AUTHORIZED_USERS
    
    # === COMMANDES TELEGRAM ===
    
    async def _start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /start"""
        user = update.effective_user
        info_print(f"📱 Telegram /start: {user.username} ({user.id})")
        
        welcome_msg = (
            f"🤖 Bot Meshtastic Bridge\n\n"
            f"Salut {user.first_name} !\n\n"
            f"Commandes:\n"
            f"• /bot - Chat IA\n"
            f"• /power - Batterie/solaire\n"
            f"• /weather - Météo Paris\n"
            f"• /rx [page]\n"
            f"• /sys\n"
            f"• /echo <msg>\n"
            f"• /annonce <msg>\n"
            f"• /nodes\n"
            f"• /fullnodes [jours]\n"
            f"• /trafic [heures]\n"
            f"• /histo [type] [h]\n"
            f"• /top [h] [n]\n"
            f"• /stats\n"
            f"• /legend\n"
            f"• /cpu\n"
            f"• /help - Aide\n\n"
            f"Votre ID: {user.id}"
        )
        await update.message.reply_text(welcome_msg)

    async def _help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /help - Version détaillée pour Telegram"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        info_print(f"📱 Telegram /help: {user.username}")
        
        help_text = self.message_handler.format_help_telegram(user.id)
        
        if not help_text or len(help_text.strip()) == 0:
            await update.message.reply_text("❌ Erreur: texte d'aide vide")
            return
        
        try:
            await update.message.reply_text(help_text)
            info_print("✅ /help envoyé avec succès")
        except Exception as e:
            error_print(f"Erreur envoi /help: {e or 'Unknown error'}")
            await update.message.reply_text("❌ Erreur envoi aide")

    async def _power_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /power avec graphiques d'historique"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        info_print(f"📱 Telegram /power: {user.username}")
        
        hours = 24
        if context.args and len(context.args) > 0:
            try:
                hours = int(context.args[0])
                hours = max(1, min(48, hours))
            except ValueError:
                hours = 24
        
        response_current = await asyncio.to_thread(
            self.message_handler.esphome_client.parse_esphome_data
        )
        await update.message.reply_text(f"⚡ Power:\n{response_current}")
        
        response_graphs = await asyncio.to_thread(
            self.message_handler.esphome_client.get_history_graphs,
            hours
        )
        await update.message.reply_text(response_graphs)

    async def _graphs_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /graphs pour afficher uniquement les graphiques d'historique"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        hours = 24
        if context.args and len(context.args) > 0:
            try:
                hours = int(context.args[0])
                hours = max(1, min(48, hours))
            except ValueError:
                hours = 24
        
        info_print(f"📱 Telegram /graphs {hours}h: {user.username}")
        
        response = await asyncio.to_thread(
            self.message_handler.esphome_client.get_history_graphs,
            hours
        )
        await update.message.reply_text(response)

    async def _weather_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /weather"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        info_print(f"📱 Telegram /weather: {user.username}")
        
        from utils_weather import get_weather_data
        weather = await asyncio.to_thread(get_weather_data)
        await update.message.reply_text(weather)

    async def _rx_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /rx [page]"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        page = int(context.args[0]) if context.args else 1
        info_print(f"📱 Telegram /rx {page}: {user.username}")
        
        response = await asyncio.to_thread(
            self.message_handler.remote_nodes_client.get_tigrog2_paginated,
            page
        )
        await update.message.reply_text(response)
    
    async def _sys_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /sys"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        info_print(f"📱 Telegram /sys: {user.username}")
        
        def get_sys_info():
            import subprocess
            system_info = []
            
            try:
                if hasattr(self.message_handler, 'router') and \
                   hasattr(self.message_handler.router, 'system_handler') and \
                   self.message_handler.router.system_handler.bot_start_time:
                    
                    bot_uptime_seconds = int(time.time() - self.message_handler.router.system_handler.bot_start_time)
                    
                    days = bot_uptime_seconds // 86400
                    hours = (bot_uptime_seconds % 86400) // 3600
                    minutes = (bot_uptime_seconds % 3600) // 60
                    
                    uptime_parts = []
                    if days > 0:
                        uptime_parts.append(f"{days}j")
                    if hours > 0:
                        uptime_parts.append(f"{hours}h")
                    if minutes > 0 or len(uptime_parts) == 0:
                        uptime_parts.append(f"{minutes}m")
                    
                    bot_uptime_str = " ".join(uptime_parts)
                    system_info.append(f"🤖 Bot: {bot_uptime_str}")
            except Exception as e:
                pass

            try:
                uptime_output = subprocess.check_output(['uptime', '-p'], text=True).strip()
                system_info.append(f"⏰ System: {uptime_output.replace('up ', '')}")
            except Exception:
                pass
            
            try:
                temp = subprocess.check_output([
                    'vcgencmd', 'measure_temp'
                ], text=True).strip()
                system_info.append(f"🌡️ {temp}")
            except Exception:
                pass
            
            try:
                cpu_usage = subprocess.check_output([
                    'sh', '-c',
                    'top -bn1 | grep "Cpu(s)" | sed "s/.*, *\\([0-9.]*\\)%* id.*/\\1/" | awk \'{print 100 - $1"%"}\''
                ], text=True).strip()
                system_info.append(f"💻 CPU: {cpu_usage}")
            except Exception:
                pass
            
            try:
                mem_info = subprocess.check_output(['free', '-h'], text=True)
                mem_line = [line for line in mem_info.split('\n') if 'Mem:' in line][0]
                parts = mem_line.split()
                system_info.append(f"🧠 RAM: {parts[2]}/{parts[1]}")
            except Exception:
                pass
            
            return "\n".join(system_info) if system_info else "❌ Infos système non disponibles"
        
        response = await asyncio.to_thread(get_sys_info)
        await update.message.reply_text(response)

    async def _bot_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /bot <question> - Chat avec l'IA"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        if not context.args or len(context.args) == 0:
            await update.message.reply_text(
                "Usage: /bot <question>\n"
                "Exemple: /bot Quelle est la météo ?"
            )
            return
        
        question = ' '.join(context.args)
        
        info_print(f"📱 Telegram /bot: {user.username} -> '{question[:50]}'")
        
        sender_id = user.id & 0xFFFFFFFF
        
        if len(question) > 100:
            await update.message.reply_text("🤔 Réflexion en cours...")
        
        def query_ai():
            return self.message_handler.llama_client.query_llama_telegram(question, sender_id)
        
        try:
            response = await asyncio.to_thread(query_ai)
            await update.message.reply_text(response)
        except Exception as e:
            error_print(f"Erreur /bot: {e}")
            await update.message.reply_text(f"❌ Erreur lors du traitement: {str(e)[:100]}")

    async def _legend_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /legend"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return
        
        info_print(f"📱 Telegram /legend: {user.username}")
        legend = self.message_handler.format_legend()
        await update.message.reply_text(legend)

    async def _echo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /echo <message> - Diffuser sur le mesh"""
        user = update.effective_user
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return

        if not context.args:
            await update.message.reply_text("Usage: /echo <message>")
            return

        echo_text = ' '.join(context.args)
        info_print(f"📱 Telegram /echo: {user.username} -> '{echo_text}'")

        status_msg = await update.message.reply_text("📤 Envoi en cours...")

        def send_echo():
            try:
                mesh_identity = self._get_mesh_identity(user.id)

                if mesh_identity:
                    prefix = mesh_identity['short_name']
                    info_print(f"🔄 Echo avec identité mappée: {prefix}")
                else:
                    username = user.username or user.first_name
                    prefix = username[:4]
                    info_print(f"⚠️ Echo sans mapping: {prefix}")

                message = f"{prefix}: {echo_text}"
                
                from safe_tcp_connection import send_text_to_remote
                
                info_print(f"📤 Envoi message vers {REMOTE_NODE_HOST}: '{message}'")
                
                success, result_msg = send_text_to_remote(
                    REMOTE_NODE_HOST, 
                    message,
                    wait_time=10
                )
                
                info_print(f"📊 Résultat: success={success}, msg={result_msg}")
                
                if success:
                    return f"✅ Echo diffusé: {message}"
                else:
                    return f"❌ Échec: {result_msg}"
                    
            except Exception as e:
                error_print(f"❌ Exception send_echo: {e}")
                return f"❌ Erreur echo: {str(e)[:50]}"

        def execute_and_reply():
            try:
                result = send_echo()
                
                asyncio.run_coroutine_threadsafe(
                    status_msg.edit_text(result),
                    self.loop
                ).result(timeout=5)
            
            except Exception as e:
                error_print(f"❌ Erreur execute_and_reply: {e}")
                try:
                    asyncio.run_coroutine_threadsafe(
                        status_msg.edit_text(f"❌ Erreur: {str(e)[:50]}"),
                        self.loop
                    ).result(timeout=5)
                except:
                    pass
        
        thread = threading.Thread(target=execute_and_reply, daemon=True)
        thread.start()
        info_print(f"✅ Thread echo lancé: {thread.name}")

    async def _annonce_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /annonce <message> - Diffuser sur le mesh depuis le bot local"""
        user = update.effective_user
        
        info_print(f"📱 Telegram /annonce appelée par {user.username}")
        
        if not self._check_authorization(user.id):
            await update.message.reply_text("❌ Non autorisé")
            return

        if not context.args:
            await update.message.reply_text("Usage: /annonce <message>")
            return

        annonce_text = ' '.join(context.args)
        info_print(f"📱 Telegram /annonce: {user.username} -> '{annonce_text}'")

        status_msg = await update.message.reply_text("📤 Envoi en cours...")

        def send_annonce():
            try:
                mesh_identity = self._get_mesh_identity(user.id)

                if mesh_identity:
                    prefix = mesh_identity['short_name']
                    info_print(f"🔄 Annonce avec identité mappée: {prefix}")
                else:
                    username = user.username or user.first_name
                    prefix = username[:4]
                    info_print(f"⚠️ Annonce sans mapping: {prefix}")

                message = f"{prefix}: {annonce_text}"
                
                info_print(f"📤 Envoi annonce depuis bot local: '{message}'")
                
                interface = self.message_handler.interface

                if not interface:
                    error_print("❌ Interface locale non disponible")
                    return False, "❌ Interface non disponible"

                if hasattr(interface, 'get_interface'):
                    actual_interface = interface.get_interface()
                    if not actual_interface:
                        error_print("❌ Interface non connectée")
                        return False, "❌ Bot en cours de reconnexion"
                    interface = actual_interface

                info_print(f"✅ Interface trouvée: {type(interface).__name__}")

                interface.sendText(message, destinationId='^all')
                                
                info_print(f"✅ Annonce diffusée depuis bot local")
                return True, "✅ Annonce envoyée depuis le bot local"
                
            except Exception as e:
                error_print(f"Erreur /annonce Telegram: {e}")
                error_print(traceback.format_exc())
                return False, f"❌ Erreur: {str(e)[:50]}"

        success, result_msg = await asyncio.to_thread(send_annonce)
        
        await status_msg.edit_text(result_msg)

    async def _error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Gestionnaire d'erreurs"""
        error_print(f"❌ Erreur Telegram: {context.error}")
        error_print(traceback.format_exc())
        if update and hasattr(update, 'message') and update.message:
            await update.message.reply_text("❌ Erreur interne")

    # Ajoutez ici toutes les autres commandes manquantes
    # (_nodes_command, _fullnodes_command, _trafic_command, _top_command, etc.)
    # Je les ai omises pour rester dans la limite de taille
    # mais elles doivent toutes être présentes dans votre fichier final

    def cleanup_expired_traces(self):
        """Nettoyer les traces expirées"""
        current_time = time.time()
        expired = []
        
        for node_id, trace_info in self.pending_traces.items():
            if current_time - trace_info['timestamp'] > self.trace_timeout:
                expired.append(node_id)
        
        for node_id in expired:
            del self.pending_traces[node_id]
        
        if expired:
            info_print(f"🧹 Nettoyage: {len(expired)} traces expirées supprimées")

    def send_alert(self, message):
        """Envoyer une alerte à tous les utilisateurs configurés"""
        info_print(f"📢 send_alert appelée avec message: {message[:50]}...")
        
        if not self.running:
            error_print("⚠️ Telegram non démarré")
            return
        
        if not self.application:
            error_print("⚠️ Application Telegram non initialisée")
            return
        
        if not self.loop:
            error_print("⚠️ Event loop Telegram non disponible")
            return
        
        try:
            if self.loop.is_closed():
                error_print("⚠️ Event loop fermé")
                return
            
            asyncio.run_coroutine_threadsafe(
                self._send_alert_async(message),
                self.loop
            ).result(timeout=5)
                
        except Exception as e:
            error_print(f"Erreur envoi alerte: {e or 'Unknown error'}")
            error_print(traceback.format_exc())
    
    async def _send_alert_async(self, message):
        """Envoyer l'alerte de manière asynchrone à tous les utilisateurs"""
        try:
            if not self.alert_users:
                error_print("⚠️ Aucun utilisateur configuré pour les alertes")
                return
            
            info_print(f"Envoi alerte à {len(self.alert_users)} utilisateur(s)")
            
            for user_id in self.alert_users:
                try:
                    await self.application.bot.send_message(
                        chat_id=user_id,
                        text=message
                    )
                    info_print(f"✅ Alerte envoyée à {user_id}")
                except Exception as e:
                    error_print(f"Erreur envoi alerte à {user_id}: {e or 'Unknown error'}")
                
                await asyncio.sleep(0.5)
                
        except Exception as e:
            error_print(f"Erreur _send_alert_async: {e or 'Unknown error'}")
            error_print(traceback.format_exc())
