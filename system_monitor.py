#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module de surveillance système pour alertes Telegram
- Monitoring température CPU
- Monitoring état tigrog2
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
        self.temp_high_since = None  # Timestamp depuis quand la temp est élevée
        self.last_temp_alert = 0  # Timestamp de la dernière alerte temp
        self.temp_alert_cooldown = 1800  # 30 minutes entre alertes temp
        
        # État tigrog2
        self.tigrog2_last_seen = None  # Timestamp dernière connexion réussie
        self.tigrog2_was_online = False  # État précédent
        self.tigrog2_uptime_last = None  # Uptime précédent pour détecter reboot
        self.last_tigrog2_alert = 0  # Timestamp dernière alerte tigrog2
        self.tigrog2_alert_cooldown = 600  # 10 minutes entre alertes tigrog2
    
    def start(self):
        """Démarrer le monitoring en arrière-plan"""
        if self.running:
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        info_print("🔍 Monitoring système démarré")
    
    def stop(self):
        """Arrêter le monitoring"""
        self.running = False
        info_print("🛑 Monitoring système arrêté")
    
    def _monitor_loop(self):
        """Boucle principale de monitoring"""
        # Délai initial pour laisser le système démarrer
        time.sleep(30)
        
        temp_check_counter = 0
        tigrog2_check_counter = 0
        
        while self.running:
            try:
                # Monitoring température
                if TEMP_WARNING_ENABLED:
                    if temp_check_counter >= TEMP_CHECK_INTERVAL:
                        self._check_temperature()
                        temp_check_counter = 0
                    temp_check_counter += 1
                
                # Monitoring tigrog2
                if TIGROG2_MONITORING_ENABLED:
                    if tigrog2_check_counter >= TIGROG2_CHECK_INTERVAL:
                        self._check_tigrog2()
                        tigrog2_check_counter = 0
                    tigrog2_check_counter += 1
                
                time.sleep(1)  # Check toutes les secondes
                
            except Exception as e:
                error_print(f"Erreur boucle monitoring: {e}")
                time.sleep(10)
    
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
                    # Log systemd
                    info_print(f"🚨 TEMPÉRATURE CRITIQUE: {temp_celsius:.1f}°C")
                return
            
            # Température d'avertissement
            if temp_celsius >= TEMP_WARNING_THRESHOLD:
                if self.temp_high_since is None:
                    # Début de température élevée
                    self.temp_high_since = current_time
                    debug_print(f"⚠️ Température élevée détectée: {temp_celsius:.1f}°C")
                else:
                    # Température élevée depuis un certain temps
                    duration = current_time - self.temp_high_since
                    
                    if duration >= TEMP_WARNING_DURATION:
                        # Durée dépassée, envoyer alerte si cooldown passé
                        if current_time - self.last_temp_alert >= self.temp_alert_cooldown:
                            self._send_temperature_alert(temp_celsius, critical=False)
                            self.last_temp_alert = current_time
                            # Log systemd
                            info_print(f"⚠️ TEMPÉRATURE ÉLEVÉE: {temp_celsius:.1f}°C depuis {int(duration/60)}min")
            else:
                # Température normale
                if self.temp_high_since is not None:
                    debug_print(f"✅ Température revenue à la normale: {temp_celsius:.1f}°C")
                    self.temp_high_since = None
            
        except Exception as e:
            error_print(f"Erreur vérification température: {e}")
    
    def _check_tigrog2(self):
        """Vérifier l'état de tigrog2 et alerter si nécessaire"""
        try:
            import meshtastic.tcp_interface
            
            current_time = time.time()
            is_online = False
            current_uptime = None
            
            try:
                # Tenter connexion à tigrog2
                debug_print(f"Vérification tigrog2 ({REMOTE_NODE_HOST})...")
                remote_interface = meshtastic.tcp_interface.TCPInterface(
                    hostname=REMOTE_NODE_HOST,
                    portNumber=4403
                )
                
                time.sleep(3)
                
                # Récupérer l'uptime si possible
                if hasattr(remote_interface, 'localNode'):
                    local_node = remote_interface.localNode
                    # Essayer de récupérer l'uptime (si disponible dans les métadonnées)
                    # Note: Meshtastic ne fournit pas toujours l'uptime directement
                    # On utilise lastHeard comme proxy
                    current_uptime = getattr(local_node, 'lastHeard', None)
                
                remote_interface.close()
                is_online = True
                self.tigrog2_last_seen = current_time
                
            except Exception as e:
                debug_print(f"tigrog2 inaccessible: {e}")
                is_online = False
            
            # Détecter changement d'état
            if is_online and not self.tigrog2_was_online:
                # tigrog2 vient de revenir en ligne
                if TIGROG2_ALERT_ON_REBOOT:
                    if self.tigrog2_last_seen and (current_time - self.tigrog2_last_seen) > 300:
                        # Était offline pendant plus de 5 minutes
                        self._send_tigrog2_alert("back_online")
                        info_print(f"✅ tigrog2 DE RETOUR EN LIGNE après interruption")
                
            elif not is_online and self.tigrog2_was_online:
                # tigrog2 vient de devenir inaccessible
                if TIGROG2_ALERT_ON_DISCONNECT:
                    if current_time - self.last_tigrog2_alert >= self.tigrog2_alert_cooldown:
                        self._send_tigrog2_alert("offline")
                        self.last_tigrog2_alert = current_time
                        info_print(f"⚠️ tigrog2 INACCESSIBLE")
            
            # Détecter redémarrage (changement d'uptime)
            if is_online and self.tigrog2_uptime_last is not None and current_uptime is not None:
                if current_uptime < self.tigrog2_uptime_last:
                    # Uptime a diminué = redémarrage
                    if TIGROG2_ALERT_ON_REBOOT:
                        if current_time - self.last_tigrog2_alert >= self.tigrog2_alert_cooldown:
                            self._send_tigrog2_alert("rebooted")
                            self.last_tigrog2_alert = current_time
                            info_print(f"🔄 tigrog2 A REDÉMARRÉ")
            
            # Mettre à jour les états
            self.tigrog2_was_online = is_online
            self.tigrog2_uptime_last = current_uptime
            
        except Exception as e:
            error_print(f"Erreur vérification tigrog2: {e}")
    
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
            except:
                pass
            
            # Méthode 2: /sys/class/thermal/thermal_zone0/temp
            try:
                with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                    temp_millis = int(f.read().strip())
                    return temp_millis / 1000.0
            except:
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
