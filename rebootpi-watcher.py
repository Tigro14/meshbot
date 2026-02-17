#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Daemon de surveillance pour redémarrage Pi via bot Meshtastic
Utilise /dev/shm (tmpfs RAM) pour survivre aux filesystems read-only

Alternative Python au script shell rebootpi-watcher.sh
Plus robuste et plus facile à maintenir que la version bash
"""

import sys
import time
import subprocess
import signal
import os

# Import du module semaphore
# Note: In production, install the bot as a package or ensure PYTHONPATH is set
# For systemd service, use WorkingDirectory to point to bot directory
try:
    from reboot_semaphore import RebootSemaphore
except ImportError:
    # Fallback: If module not in PATH, try to find it relative to script location
    # This is for development/testing only - production should use proper paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    from reboot_semaphore import RebootSemaphore

LOG_FILE = "/var/log/bot-reboot.log"
CHECK_INTERVAL = 5  # Vérifier toutes les 5 secondes

# Flag pour shutdown gracieux
shutdown_flag = False

def log_message(message):
    """Écrire un message dans le log"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}\n"
    
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(log_line)
    except Exception as e:
        # Fallback sur stderr si impossible d'écrire dans le log
        print(log_line, file=sys.stderr)
        print(f"Erreur écriture log: {e}", file=sys.stderr)
    
    # Aussi afficher sur stdout pour systemd journal
    print(log_line.rstrip())

def handle_signal(signum, frame):
    """Gérer les signaux pour shutdown gracieux"""
    global shutdown_flag
    log_message(f"Signal {signum} reçu - arrêt gracieux...")
    shutdown_flag = True

def execute_reboot():
    """
    Exécuter le redémarrage du système
    Essaie plusieurs méthodes par ordre de préférence
    """
    log_message("Exécution du redémarrage Pi...")
    
    # Lire les infos de reboot pour déterminer le type de reboot
    info = RebootSemaphore.get_reboot_info()
    is_io_health_failure = False
    
    if info and 'IOHealthWatchdog' in info:
        is_io_health_failure = True
        log_message("⚠️ REBOOT DÉCLENCHÉ PAR WATCHDOG I/O")
        log_message("   Utilisation de la séquence SysRq REISUB pour reboot sûr")
    
    # Si c'est une défaillance I/O, utiliser directement SysRq
    # car le filesystem peut être en lecture seule
    if is_io_health_failure:
        execute_sysrq_reboot()
        return
    
    # Sinon, pour les reboots utilisateur, essayer les méthodes standards d'abord
    # Méthode 1: systemctl (recommandé pour systemd)
    try:
        subprocess.run(['systemctl', 'reboot'], check=True, timeout=5)
        return  # Si ça marche, on n'ira pas plus loin
    except Exception as e:
        log_message(f"systemctl reboot échoué: {e}")
    
    # Méthode 2: shutdown
    try:
        subprocess.run(['shutdown', '-r', '+1', 'Redémarrage via bot'], check=True, timeout=5)
        return
    except Exception as e:
        log_message(f"shutdown échoué: {e}")
    
    # Méthode 3: reboot direct
    try:
        subprocess.run(['/sbin/reboot'], check=True, timeout=5)
        return
    except Exception as e:
        log_message(f"reboot direct échoué: {e}")
    
    # Méthode 4: SysRq (dernière chance)
    log_message("Toutes les méthodes standard ont échoué, utilisation de SysRq...")
    execute_sysrq_reboot()

def execute_sysrq_reboot():
    """
    Exécuter un reboot sécurisé via la séquence SysRq REISUB
    
    Séquence REISUB (Raising Elephants Is So Utterly Boring):
    - R: unRaw      - Reprendre le contrôle du clavier
    - E: tErminate  - Envoyer SIGTERM à tous les processus (shutdown gracieux)
    - I: kIll       - Envoyer SIGKILL à tous les processus restants
    - S: Sync       - Synchroniser tous les filesystems montés
    - U: Unmount    - Remonter tous les filesystems en lecture seule
    - B: reBoot     - Redémarrer immédiatement
    
    Cette séquence assure un reboot propre même si le filesystem est corrompu
    ou en lecture seule, ce qui est critique pour les défaillances I/O.
    """
    log_message("═══════════════════════════════════════")
    log_message("🔴 EXÉCUTION SÉQUENCE SYSRQ REISUB")
    log_message("═══════════════════════════════════════")
    
    try:
        # Activer SysRq
        log_message("1. Activation SysRq...")
        with open('/proc/sys/kernel/sysrq', 'w') as f:
            f.write('1')
        
        # R: unRaw (reprendre contrôle clavier)
        log_message("2. SysRq-R: unRaw (reprendre contrôle)")
        with open('/proc/sysrq-trigger', 'w') as f:
            f.write('r')
        time.sleep(1)
        
        # E: tErminate (SIGTERM à tous les processus)
        log_message("3. SysRq-E: tErminate (SIGTERM)")
        with open('/proc/sysrq-trigger', 'w') as f:
            f.write('e')
        time.sleep(2)  # Laisser le temps aux processus de se terminer
        
        # I: kIll (SIGKILL aux processus restants)
        log_message("4. SysRq-I: kIll (SIGKILL)")
        with open('/proc/sysrq-trigger', 'w') as f:
            f.write('i')
        time.sleep(2)
        
        # S: Sync (synchroniser filesystems)
        log_message("5. SysRq-S: Sync (synchronisation FS)")
        with open('/proc/sysrq-trigger', 'w') as f:
            f.write('s')
        time.sleep(3)  # Important: laisser le temps pour sync
        
        # U: Unmount (remontage lecture seule)
        log_message("6. SysRq-U: Unmount (remontage RO)")
        with open('/proc/sysrq-trigger', 'w') as f:
            f.write('u')
        time.sleep(2)
        
        # B: reBoot (redémarrage immédiat)
        log_message("7. SysRq-B: reBoot (REDÉMARRAGE)")
        log_message("═══════════════════════════════════════")
        with open('/proc/sysrq-trigger', 'w') as f:
            f.write('b')
        
        # Si on arrive ici, le reboot n'a pas fonctionné
        time.sleep(5)
        log_message("❌ SysRq reboot n'a pas fonctionné!")
        
    except Exception as e:
        log_message(f"❌ Erreur lors de la séquence SysRq: {e}")
        log_message("Tentative de sync + reboot direct...")
        try:
            # Dernier recours: sync + reboot immédiat
            subprocess.run(['sync'], timeout=5)
            with open('/proc/sysrq-trigger', 'w') as f:
                f.write('b')
        except Exception as e2:
            log_message(f"❌ Échec total du reboot: {e2}")

def main():
    """Boucle principale du watcher"""
    global shutdown_flag
    
    # Configurer les handlers de signaux
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    
    log_message("Démarrage du watcher de redémarrage Pi")
    log_message(f"Intervalle de vérification: {CHECK_INTERVAL}s")
    log_message(f"Utilise /dev/shm (tmpfs) pour survivre aux FS read-only")
    
    while not shutdown_flag:
        try:
            # Vérifier si un redémarrage a été demandé
            if RebootSemaphore.check_reboot_signal():
                log_message("Signal de redémarrage détecté via sémaphore (/dev/shm)")
                
                # Récupérer et logger les informations
                info = RebootSemaphore.get_reboot_info()
                if info:
                    log_message("Informations de redémarrage:")
                    for line in info.split('\n'):
                        if line.strip():
                            log_message(f"  {line}")
                
                # Nettoyer le signal
                RebootSemaphore.clear_reboot_signal()
                
                # Exécuter le redémarrage
                execute_reboot()
                
                # Si on arrive ici, le reboot a échoué
                log_message("ERREUR: Toutes les méthodes de reboot ont échoué!")
                # Attendre un peu avant de réessayer
                time.sleep(30)
            
            # Attendre avant la prochaine vérification
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            log_message("Interruption clavier - arrêt...")
            break
        except Exception as e:
            log_message(f"Erreur dans la boucle principale: {e}")
            # Continuer malgré l'erreur
            time.sleep(CHECK_INTERVAL)
    
    log_message("Arrêt du watcher de redémarrage Pi")
    return 0

if __name__ == "__main__":
    # Vérifier qu'on tourne en root (nécessaire pour reboot)
    if os.geteuid() != 0:
        print("ERREUR: Ce script doit être exécuté en root", file=sys.stderr)
        print("Utilisez: sudo python3 rebootpi-watcher.py", file=sys.stderr)
        sys.exit(1)
    
    sys.exit(main())
