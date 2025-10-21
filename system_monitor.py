#!/usr/bin/env python3
import traceback
# -*- coding: utf-8 -*-
"""
Module de surveillance système pour alertes Telegram
- Monitoring température CPU
- Monitoring CPU du bot
- Monitoring état tigrog2
✅ VERSION COMPLÈTE AVEC TOUTES LES MÉTHODES
"""

import time
import threading
import subprocess
from config import *
from utils import *

class SystemMonitor:
    def __init__(self, telegram_integration=None):
        self.telegram_integration = telegram_integration
        self.running = False
        self.monitor_thread = None
        
        # État température
        self.temp_high_since = None
        self.last_temp_alert = 0
        self.temp_alert_cooldown = 1800  # 30 minutes

        # État CPU
        self.cpu_high_since = None
        self.last_cpu_alert = 0
        self.cpu_alert_cooldown = 1800  # 30 minutes
        self.process = None
         
        # État tigrog2
        self.tigrog2_last_seen = None
        self.tigrog2_was_online = False
        self.tigrog2_uptime_last = None
        self.last_tigrog2_alert = 0
        self.tigrog2_alert_cooldown = 600  # 10 minutes
    
    def start(self):
        """Démarrer le monitoring en arrière-plan"""
        if self.running:
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        info_print("📊 Monitoring système démarré")
    
    def stop(self):
        """Arrêter le monitoring"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        info_print("🛑 Monitoring système arrêté")
    
    def _monitor_loop(self):
        """Boucle principale de monitoring - ✅ VERSION CORRIGÉE"""
        # Délai initial pour laisser le système démarrer
        info_print("⏳ Monitoring système : délai initial 30s...")
        time.sleep(30)
        
        # ✅ CORRECTION : Initialiser TOUS les compteurs
        temp_check_counter = 0
        cpu_check_counter = 0  # ← CRITIQUE : était manquant
        tigrog2_check_counter = 0
        
        info_print("✅ Monitoring système : boucle démarrée")
        
        while self.running:
            try:
                # Monitoring température
                if TEMP_WARNING_ENABLED:
                    if temp_check_counter >= TEMP_CHECK_INTERVAL:
                        self._check_temperature()
                        temp_check_counter = 0
                    temp_check_counter += 1

                # Monitoring CPU
                if CPU_WARNING_ENABLED:
                    if cpu_check_counter >= CPU_CHECK_INTERVAL:
                        self._check_cpu()
                        cpu_check_counter = 0
                    cpu_check_counter += 1

                # Monitoring tigrog2
                if TIGROG2_MONITORING_ENABLED:
                    if tigrog2_check_counter >= TIGROG2_CHECK_INTERVAL:
                        self._check_tigrog2()
                        tigrog2_check_counter = 0
                    tigrog2_check_counter += 1
                
                # Sleep 30 secondes entre chaque itération
                time.sleep(30)
                
            except Exception as e:
                error_print(f"Erreur boucle monitoring: {e}")
                error_print(traceback.format_exc())
                # Sleep même en cas d'erreur pour éviter boucle folle
                time.sleep(10)
        
        info_print("🛑 Boucle monitoring terminée")
    
    def _check_temperature(self):
        """Vérifier la température CPU et alerter si nécessaire"""
        try:
            temp_celsius = self._get_cpu_temperature()
            
            if temp_celsius is None:
                return
            
            current_time = time.time()
            
            # Température critique
            if temp_celsius >= TEMP_CRITICAL_THRESHOLD:
                if current_time - self.last_temp_alert >= self.temp_alert_cooldown:
                    self._send_temperature_alert(temp_celsius, critical=True)
                    self.last_temp_alert = current_time
                    info_print(f"🚨 TEMPÉRATURE CRITIQUE: {temp_celsius:.1f}°C")
                return
            
            # Température d'avertissement
            if temp_celsius >= TEMP_WARNING_THRESHOLD:
                if self.temp_high_since is None:
                    self.temp_high_since = current_time
                    debug_print(f"⚠️ Température élevée détectée: {temp_celsius:.1f}°C")
                else:
                    duration = current_time - self.temp_high_since
                    
                    if duration >= TEMP_WARNING_DURATION:
                        if current_time - self.last_temp_alert >= self.temp_alert_cooldown:
                            self._send_temperature_alert(temp_celsius, critical=False)
                            self.last_temp_alert = current_time
                            info_print(f"⚠️ TEMPÉRATURE ÉLEVÉE: {temp_celsius:.1f}°C depuis {int(duration/60)}min")
            else:
                if self.temp_high_since is not None:
                    debug_print(f"✅ Température revenue à la normale: {temp_celsius:.1f}°C")
                    self.temp_high_since = None
            
        except Exception as e:
            error_print(f"Erreur vérification température: {e}")

    def _check_cpu(self):
        """Vérifier l'utilisation CPU du bot et alerter si nécessaire"""
        try:
            # Initialiser psutil.Process si nécessaire
            if self.process is None:
                try:
                    import psutil
                    import os
                    self.process = psutil.Process(os.getpid())
                    debug_print("✅ psutil.Process initialisé pour monitoring CPU")
                except ImportError:
                    error_print("❌ Module psutil non installé - monitoring CPU désactivé")
                    # Désactiver le monitoring CPU si psutil absent
                    import config
                    config.CPU_WARNING_ENABLED = False
                    return
            
            # Obtenir l'utilisation CPU (moyenne sur 1 seconde)
            cpu_percent = self.process.cpu_percent(interval=1.0)
            
            if cpu_percent is None:
                return
            
            current_time = time.time()
            
            # CPU critique
            if cpu_percent >= CPU_CRITICAL_THRESHOLD:
                if current_time - self.last_cpu_alert >= self.cpu_alert_cooldown:
                    self._send_cpu_alert(cpu_percent, critical=True)
                    self.last_cpu_alert = current_time
                    info_print(f"🚨 CPU CRITIQUE: {cpu_percent:.1f}%")
                return
            
            # CPU d'avertissement
            if cpu_percent >= CPU_WARNING_THRESHOLD:
                if self.cpu_high_since is None:
                    self.cpu_high_since = current_time
                    debug_print(f"⚠️ CPU élevé détecté: {cpu_percent:.1f}%")
                else:
                    duration = current_time - self.cpu_high_since
                    
                    if duration >= CPU_WARNING_DURATION:
                        if current_time - self.last_cpu_alert >= self.cpu_alert_cooldown:
                            self._send_cpu_alert(cpu_percent, critical=False)
                            self.last_cpu_alert = current_time
                            info_print(f"⚠️ CPU ÉLEVÉ: {cpu_percent:.1f}% depuis {int(duration/60)}min")
            else:
                if self.cpu_high_since is not None:
                    debug_print(f"✅ CPU revenu à la normale: {cpu_percent:.1f}%")
                    self.cpu_high_since = None
            
        except Exception as e:
            error_print(f"Erreur vérification CPU: {e}")
            error_print(traceback.format_exc())

    def _check_tigrog2(self):
        """Vérifier l'état de tigrog2 et alerter si nécessaire"""
        try:
            import meshtastic.tcp_interface
            
            current_time = time.time()
            is_online = False
            current_uptime = None
            
            try:
                debug_print(f"Vérification tigrog2 ({REMOTE_NODE_HOST})...")
                remote_interface = meshtastic.tcp_interface.TCPInterface(
                    hostname=REMOTE_NODE_HOST,
                    portNumber=4403
                )
                
                time.sleep(1)
                
                if hasattr(remote_interface, 'localNode'):
                    local_node = remote_interface.localNode
                    current_uptime = getattr(local_node, 'lastHeard', None)
                
                remote_interface.close()
                is_online = True
                self.tigrog2_last_seen = current_time
                
            except Exception as e:
                debug_print(f"tigrog2 inaccessible: {e}")
                is_online = False
            
            # Détecter changement d'état
            if is_online and not self.tigrog2_was_online:
                if TIGROG2_ALERT_ON_REBOOT:
                    if self.tigrog2_last_seen and (current_time - self.tigrog2_last_seen) > 300:
                        self._send_tigrog2_alert("back_online")
                        info_print(f"✅ tigrog2 DE RETOUR EN LIGNE après interruption")
                
            elif not is_online and self.tigrog2_was_online:
                if TIGROG2_ALERT_ON_DISCONNECT:
                    if current_time - self.last_tigrog2_alert >= self.tigrog2_alert_cooldown:
                        self._send_tigrog2_alert("offline")
                        self.last_tigrog2_alert = current_time
                        info_print(f"⚠️ tigrog2 INACCESSIBLE")
            
            # Détecter redémarrage
            if is_online and self.tigrog2_uptime_last is not None and current_uptime is not None:
                if current_uptime < self.tigrog2_uptime_last:
                    if TIGROG2_ALERT_ON_REBOOT:
                        if current_time - self.last_tigrog2_alert >= self.tigrog2_alert_cooldown:
                            self._send_tigrog2_alert("rebooted")
                            self.last_tigrog2_alert = current_time
                            info_print(f"🔄 tigrog2 A REDÉMARRÉ")
            
            self.tigrog2_was_online = is_online
            self.tigrog2_uptime_last = current_uptime
            
        except Exception as e:
            error_print(f"Erreur vérification tigrog2: {str(e) if e else 'Unknown error'}")
    
    def _get_cpu_temperature(self):
        """Récupérer la température CPU"""
        try:
            # Méthode 1: vcgencmd (Raspberry Pi)
            try:
                temp_cmd = ['vcgencmd', 'measure_temp']
                temp_result = subprocess.run(temp_cmd, 
                                           capture_output=True, 
                                           text=True, 
                                           timeout=5)
                
                if temp_result.returncode == 0:
                    temp_output = temp_result.stdout.strip()
                    if 'temp=' in temp_output:
                        temp_str = temp_output.split('=')[1].replace("'C", "")
                        return float(temp_str)
            except Exception as e:
                pass
            
            # Méthode 2: /sys/class/thermal/thermal_zone0/temp
            try:
                with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                    temp_millis = int(f.read().strip())
                    return temp_millis / 1000.0
            except Exception as e:
                pass
            
            return None
            
        except Exception as e:
            debug_print(f"Erreur lecture température: {e}")
            return None
    
    def _send_temperature_alert(self, temperature, critical=False):
        """Envoyer une alerte température via Telegram"""
        try:
            if not self.telegram_integration:
                return
            
            if critical:
                emoji = "🔥"
                level = "CRITIQUE"
                message = (
                    f"{emoji} ALERTE TEMPÉRATURE {level}\n\n"
                    f"🌡️ CPU: {temperature:.1f}°C\n"
                    f"⚠️ Seuil critique: {TEMP_CRITICAL_THRESHOLD}°C\n\n"
                    f"Action recommandée: Vérifier le système immédiatement!"
                )
            else:
                emoji = "⚠️"
                level = "ÉLEVÉE"
                duration_min = int((time.time() - self.temp_high_since) / 60)
                message = (
                    f"{emoji} Alerte Température {level}\n\n"
                    f"🌡️ CPU: {temperature:.1f}°C\n"
                    f"📊 Seuil: {TEMP_WARNING_THRESHOLD}°C\n"
                    f"⏱️ Durée: {duration_min} minutes\n\n"
                    f"Surveillance en cours..."
                )
            
            self.telegram_integration.send_alert(message)
            
        except Exception as e:
            error_print(f"Erreur envoi alerte température: {e}")

    def _send_cpu_alert(self, cpu_percent, critical=False):
        """Envoyer une alerte CPU via Telegram"""
        try:
            if not self.telegram_integration:
                return
            
            # Informations supplémentaires
            try:
                threads = len(self.process.threads())
                memory_mb = self.process.memory_info().rss / 1024 / 1024
            except Exception as e:
                threads = "N/A"
                memory_mb = 0
            
            if critical:
                emoji = "🔥"
                level = "CRITIQUE"
                message = (
                    f"{emoji} ALERTE CPU {level}\n\n"
                    f"⚡ Utilisation: {cpu_percent:.1f}%\n"
                    f"⚠️ Seuil critique: {CPU_CRITICAL_THRESHOLD}%\n"
                    f"🧵 Threads: {threads}\n"
                    f"💾 RAM: {memory_mb:.0f}MB\n\n"
                    f"Action recommandée: Vérifier le bot immédiatement!\n"
                    f"Causes possibles:\n"
                    f"• Boucle infinie\n"
                    f"• Polling Telegram trop agressif\n"
                    f"• Problème réseau Meshtastic"
                )
            else:
                emoji = "⚠️"
                level = "ÉLEVÉE"
                duration_min = int((time.time() - self.cpu_high_since) / 60)
                message = (
                    f"{emoji} Alerte CPU {level}\n\n"
                    f"⚡ Utilisation: {cpu_percent:.1f}%\n"
                    f"📊 Seuil: {CPU_WARNING_THRESHOLD}%\n"
                    f"⏱️ Durée: {duration_min} minutes\n"
                    f"🧵 Threads: {threads}\n"
                    f"💾 RAM: {memory_mb:.0f}MB\n\n"
                    f"Surveillance en cours...\n"
                    f"Tip: Vérifier les logs pour identifier la cause"
                )
            
            self.telegram_integration.send_alert(message)
            
        except Exception as e:
            error_print(f"Erreur envoi alerte CPU: {e}")

    def _send_tigrog2_alert(self, alert_type):
        """Envoyer une alerte tigrog2 via Telegram"""
        try:
            if not self.telegram_integration:
                return
            
            if alert_type == "offline":
                message = (
                    f"⚠️ Alerte {REMOTE_NODE_NAME}\n\n"
                    f"🔴 Statut: INACCESSIBLE\n"
                    f"🌐 Host: {REMOTE_NODE_HOST}\n"
                    f"⏱️ Détection: {time.strftime('%H:%M:%S')}\n\n"
                    f"Vérification en cours..."
                )
            
            elif alert_type == "back_online":
                message = (
                    f"✅ {REMOTE_NODE_NAME} de retour\n\n"
                    f"🟢 Statut: EN LIGNE\n"
                    f"🌐 Host: {REMOTE_NODE_HOST}\n"
                    f"⏱️ Rétabli: {time.strftime('%H:%M:%S')}\n\n"
                    f"Connexion rétablie avec succès."
                )
            
            elif alert_type == "rebooted":
                message = (
                    f"🔄 {REMOTE_NODE_NAME} redémarré\n\n"
                    f"🔵 Événement: REDÉMARRAGE DÉTECTÉ\n"
                    f"🌐 Host: {REMOTE_NODE_HOST}\n"
                    f"⏱️ Détection: {time.strftime('%H:%M:%S')}\n\n"
                    f"Le nœud a redémarré."
                )
            else:
                return
            
            self.telegram_integration.send_alert(message)
            
        except Exception as e:
            error_print(f"Erreur envoi alerte tigrog2: {e}")
