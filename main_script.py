#!/usr/bin/env python3
"""
Bot Mesh - Version refactorisée
Point d'entrée principal
"""

import argparse
import sys
import gc
import logging
from config import DEBUG_MODE
from utils import info_print
from main_bot import MeshBot

def setup_logging():
    """Configure Python logging pour supprimer les logs verbeux"""
    # Supprimer les logs INFO de httpx (utilisé par python-telegram-bot)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    
    # Supprimer les logs INFO de telegram.ext (trop verbeux)
    # On garde WARNING et ERROR seulement
    logging.getLogger('telegram.ext').setLevel(logging.WARNING)
    
    # Configurer le format de base pour les autres logs
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def setup_quiet_mode():
    """Configure le mode silencieux"""
    class QuietLogger:
        def write(self, msg):
            if 'ERROR' in msg:
                sys.__stdout__.write(msg)
                sys.__stdout__.flush()
        def flush(self):
            pass
    sys.stdout = QuietLogger()

def main():
    """Point d'entrée principal"""
    global DEBUG_MODE
    
    parser = argparse.ArgumentParser(description='Bot Meshtastic-Llama modulaire')
    parser.add_argument('--debug', '-d', action='store_true', help='Mode debug')
    parser.add_argument('--quiet', '-q', action='store_true', help='Mode silencieux')
    args = parser.parse_args()
    
    # Configuration globale
    import config
    config.DEBUG_MODE = args.debug
    DEBUG_MODE = args.debug
    
    # Configurer le logging Python (supprimer httpx/telegram verbeux)
    setup_logging()
    
    if args.quiet:
        setup_quiet_mode()
    
    # Nettoyage initial
    gc.collect()
    
    bot = MeshBot()
    try:
        success = bot.start()
        if not success:
            return 1
    except KeyboardInterrupt:
        if DEBUG_MODE:
            info_print("Interruption")
    finally:
        bot.stop()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
