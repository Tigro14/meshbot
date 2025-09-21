#!/usr/bin/env python3
"""
Test simple pour vérifier que les logs apparaissent dans journalctl
"""

import sys
import time
from datetime import datetime

def test_logs():
    """Test tous les types de logs"""
    
    print("[INFO] Test des logs - début", flush=True)
    print("[ERROR] Test erreur - ceci devrait apparaître", file=sys.stderr, flush=True)
    print("[CONVERSATION] Test conversation - ceci devrait apparaître", flush=True)
    print("[DEBUG] Test debug - ceci devrait apparaître", file=sys.stderr, flush=True)
    
    # Simulation d'une conversation
    print("[CONVERSATION] " + "="*60, flush=True)
    print("[CONVERSATION] USER: Test User (123456)", flush=True)
    print("[CONVERSATION] QUERY: Test question pour vérifier les logs", flush=True)
    print("[CONVERSATION] RESPONSE: Test réponse du bot IA", flush=True)
    print("[CONVERSATION] PROCESSING_TIME: 2.45s", flush=True)
    print("[CONVERSATION] TIMESTAMP: " + datetime.now().isoformat(), flush=True)
    print("[CONVERSATION] " + "="*60, flush=True)
    
    print("[INFO] Test des logs terminé - vérifiez avec journalctl", flush=True)

if __name__ == "__main__":
    print("[INFO] Démarrage du test des logs...", flush=True)
    test_logs()
    print("[INFO] Fin du test", flush=True)

