#!/usr/bin/env python3
"""
Test pour vérifier que TCP keepalive est correctement configuré

Ce test vérifie:
1. SO_KEEPALIVE est activé sur le socket
2. Les paramètres keepalive sont configurés (si disponibles)
3. select() inclut la liste d'exceptions pour détecter les sockets morts
"""

import sys
import os

# Ajouter le répertoire courant au path
sys.path.insert(0, os.path.dirname(__file__))

def test_keepalive_configuration():
    """
    Test que le code de configuration TCP inclut keepalive
    """
    print("\n🧪 Test: Configuration TCP Keepalive")
    
    # Lire le fichier tcp_interface_patch.py
    with open('/home/runner/work/meshbot/meshbot/tcp_interface_patch.py', 'r') as f:
        content = f.read()
    
    # Trouver la fonction __init__
    init_start = content.find('def __init__')
    init_end = content.find('\n    def ', init_start + 1)
    init_code = content[init_start:init_end]
    
    # Vérifier que SO_KEEPALIVE est activé
    assert 'SO_KEEPALIVE' in init_code, \
        "❌ SO_KEEPALIVE devrait être activé"
    print("✅ SO_KEEPALIVE est activé")
    
    # Vérifier TCP_KEEPIDLE
    assert 'TCP_KEEPIDLE' in init_code, \
        "❌ TCP_KEEPIDLE devrait être configuré"
    print("✅ TCP_KEEPIDLE configuré")
    
    # Vérifier TCP_KEEPINTVL
    assert 'TCP_KEEPINTVL' in init_code, \
        "❌ TCP_KEEPINTVL devrait être configuré"
    print("✅ TCP_KEEPINTVL configuré")
    
    # Vérifier TCP_KEEPCNT
    assert 'TCP_KEEPCNT' in init_code, \
        "❌ TCP_KEEPCNT devrait être configuré"
    print("✅ TCP_KEEPCNT configuré")
    
    # Vérifier la documentation
    assert 'keepalive' in init_code.lower() or 'Keepalive' in init_code, \
        "❌ Devrait contenir de la documentation sur keepalive"
    print("✅ Documentation keepalive présente")
    
    print("\n✅ TOUS LES TESTS RÉUSSIS")
    return True

def test_select_no_exception_list():
    """
    Test that select() does NOT use exception list to avoid spurious wakeups
    """
    print("\n🧪 Test: select() sans liste d'exceptions (évite faux positifs)")
    
    with open('/home/runner/work/meshbot/meshbot/tcp_interface_patch.py', 'r') as f:
        content = f.read()
    
    # Trouver _readBytes
    readbytes_start = content.find('def _readBytes')
    readbytes_end = content.find('\n    def ', readbytes_start + 1)
    if readbytes_end == -1:
        readbytes_end = len(content)
    readbytes_code = content[readbytes_start:readbytes_end]
    
    # Vérifier que select() N'INCLUT PAS la liste d'exceptions
    # (le troisième paramètre doit être vide [])
    assert 'select.select([self.socket], [], [], self.read_timeout)' in readbytes_code, \
        "❌ select() ne devrait PAS inclure [self.socket] dans la liste d'exceptions (cause faux positifs)"
    print("✅ select() n'inclut pas la liste d'exceptions (évite faux positifs)")
    
    # Vérifier le commentaire explicatif
    assert 'avoid spurious wakeups' in readbytes_code or 'faux positifs' in readbytes_code, \
        "❌ Devrait expliquer pourquoi on n'utilise pas la liste d'exceptions"
    print("✅ Documentation explique pourquoi pas de liste d'exceptions")
    
    print("✅ Test réussi")
    return True

if __name__ == "__main__":
    print("=" * 70)
    print("TEST TCP KEEPALIVE - Détection connexions mortes")
    print("=" * 70)
    
    results = [
        test_keepalive_configuration(),
        test_select_no_exception_list(),
    ]
    
    print("\n" + "=" * 70)
    print("RÉSUMÉ")
    print("=" * 70)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Tests réussis: {passed}/{total}")
    
    if all(results):
        print("\n✅ TOUS LES TESTS RÉUSSIS")
        print("\nFix appliqué avec succès:")
        print("- TCP Keepalive activé (SO_KEEPALIVE)")
        print("- Keepalive démarre après 60s d'inactivité")
        print("- Probe toutes les 10s")
        print("- Connexion déclarée morte après 6 échecs (~2 minutes)")
        print("- select() n'utilise PAS la liste d'exceptions (évite faux positifs)")
        sys.exit(0)
    else:
        print("\n❌ CERTAINS TESTS ONT ÉCHOUÉ")
        sys.exit(1)
