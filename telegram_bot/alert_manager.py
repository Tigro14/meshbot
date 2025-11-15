#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gestionnaire d'alertes pour Telegram
Envoie des alertes aux utilisateurs autorisés
"""

from telegram import Update
from utils import info_print, error_print, debug_print
from config import TELEGRAM_ALERT_USERS, TELEGRAM_AUTHORIZED_USERS
import asyncio
import traceback


class AlertManager:
    """Gestionnaire centralisé pour les alertes Telegram"""

    def __init__(self, telegram_integration):
        self.telegram = telegram_integration
        self.alert_users = TELEGRAM_ALERT_USERS if TELEGRAM_ALERT_USERS else TELEGRAM_AUTHORIZED_USERS

    def send_alert(self, message):
        """
        Envoyer une alerte à tous les utilisateurs configurés
        Cette méthode peut être appelée depuis n'importe quel thread
        """
        info_print(f"📢 send_alert appelée avec message: {message[:50]}...")

        if not self.telegram.running:
            error_print("⚠️ Telegram non démarré (running=False)")
            return

        if not self.telegram.application:
            error_print("⚠️ Application Telegram non initialisée")
            return

        if not self.telegram.loop:
            error_print("⚠️ Event loop Telegram non disponible")
            return

        try:
            # Vérifier que l'event loop est toujours actif
            if self.telegram.loop.is_closed():
                error_print("⚠️ Event loop fermé")
                return

            # Créer une tâche asynchrone pour envoyer l'alerte
            future = asyncio.run_coroutine_threadsafe(
                self._send_alert_async(message),
                self.telegram.loop
            ).result(timeout=5)

            # Attendre le résultat (avec timeout)
            try:
                future.result(timeout=10)
                info_print("✅ Alerte envoyée avec succès")
            except Exception as e:
                error_print(f"Erreur attente résultat: {e or 'Unknown error'}")

        except Exception as e:
            error_print(f"Erreur envoi alerte: {e or 'Unknown error'}")
            error_print(traceback.format_exc())

    async def _send_alert_async(self, message):
        """Envoyer l'alerte de manière asynchrone à tous les utilisateurs"""
        try:
            debug_print(f"_send_alert_async démarré")

            if not self.alert_users:
                error_print("⚠️ Aucun utilisateur configuré pour les alertes")
                error_print(f"TELEGRAM_ALERT_USERS={TELEGRAM_ALERT_USERS}")
                error_print(
                    f"TELEGRAM_AUTHORIZED_USERS={TELEGRAM_AUTHORIZED_USERS}")
                return

            info_print(
                f"Envoi alerte à {len(self.alert_users)} utilisateur(s)")

            for user_id in self.alert_users:
                try:
                    debug_print(f"Envoi à {user_id}...")
                    await self.telegram.application.bot.send_message(
                        chat_id=user_id,
                        text=message
                    )
                    info_print(f"✅ Alerte envoyée à {user_id}")
                except Exception as e:
                    error_print(
                        f"Erreur envoie alerte à {user_id}: {
                            e or 'Unknown error'}")

                # Petit délai entre les envois pour éviter rate limiting
                await asyncio.sleep(0.5)

            debug_print("_send_alert_async terminé")

        except Exception as e:
            error_print(f"Erreur _send_alert_async: {e or 'Unknown error'}")
            error_print(traceback.format_exc())
