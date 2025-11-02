#!/usr/bin/env python3
"""
Bot Mesh - Version refactorisée
Point d'entrée principal
"""

import argparse
import sys
import gc
from config import DEBUG_MODE
from utils import info_print
from main_bot import MeshBot

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
