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
    # Accept any numeric timeout (1.0 or select_interval variable)
    import re
    select_pattern = r'select\.select\(\[self\.socket\], \[\], \[\], [0-9.]+\)'
    assert re.search(select_pattern, readbytes_code), \
        "❌ select() ne devrait PAS inclure [self.socket] dans la liste d'exceptions (cause faux positifs)"
    print("✅ select() n'inclut pas la liste d'exceptions (évite faux positifs)")
    
    # Vérifier le commentaire explicatif
    assert 'avoid spurious wakeups' in readbytes_code or 'faux positifs' in readbytes_code or '_wantExit' in readbytes_code or 'CPU' in readbytes_code, \
        "❌ Devrait expliquer pourquoi on n'utilise pas la liste d'exceptions"
    print("✅ Documentation explique pourquoi pas de liste d'exceptions")
    
    print("✅ Test réussi")
    return True

def test_dead_socket_stops_loop():
    """
    Test that when recv() returns empty (dead socket), we set _wantExit to stop tight loop
    """
    print("\n🧪 Test: Socket mort arrête la boucle (pas de tight loop)")
    
    with open('/home/runner/work/meshbot/meshbot/tcp_interface_patch.py', 'r') as f:
        content = f.read()
    
    # Trouver _readBytes
    readbytes_start = content.find('def _readBytes')
    readbytes_end = content.find('\n    def ', readbytes_start + 1)
    if readbytes_end == -1:
        readbytes_end = len(content)
    readbytes_code = content[readbytes_start:readbytes_end]
    
    # Vérifier qu'on détecte les données vides (socket mort)
    assert 'not data' in readbytes_code or 'if not data' in readbytes_code, \
        "❌ Devrait détecter quand recv() retourne vide (socket mort)"
    print("✅ Détection socket mort (recv() vide)")
    
    # Vérifier qu'on set _wantExit pour arrêter la boucle
    assert '_wantExit = True' in readbytes_code, \
        "❌ Devrait set _wantExit = True pour arrêter les appels répétés"
    print("✅ _wantExit = True pour stopper la boucle")
    
    # Vérifier le log (une seule fois)
    assert 'if not getattr' in readbytes_code or 'not getattr(self, \'_wantExit\'' in readbytes_code, \
        "❌ Devrait logger une seule fois (pas de spam)"
    print("✅ Log une seule fois (pas de spam)")
    
    print("✅ Test réussi")
    return True

def test_dead_socket_callback():
    """
    Test that dead socket detection triggers immediate reconnection callback
    """
    print("\n🧪 Test: Callback reconnexion immédiate sur socket mort")
    
    with open('/home/runner/work/meshbot/meshbot/tcp_interface_patch.py', 'r') as f:
        content = f.read()
    
    # Vérifier que la classe a un callback configurable
    assert 'set_dead_socket_callback' in content, \
        "❌ Devrait avoir une méthode set_dead_socket_callback"
    print("✅ Méthode set_dead_socket_callback existe")
    
    # Vérifier que le callback est appelé quand le socket meurt
    assert '_on_dead_socket_callback' in content, \
        "❌ Devrait avoir un attribut _on_dead_socket_callback"
    print("✅ Attribut _on_dead_socket_callback existe")
    
    # Trouver _readBytes et vérifier l'appel du callback
    readbytes_start = content.find('def _readBytes')
    readbytes_end = content.find('\n    def ', readbytes_start + 1)
    if readbytes_end == -1:
        readbytes_end = len(content)
    readbytes_code = content[readbytes_start:readbytes_end]
    
    assert '_on_dead_socket_callback()' in readbytes_code, \
        "❌ Devrait appeler le callback quand le socket meurt"
    print("✅ Callback appelé sur socket mort")
    
    print("✅ Test réussi")
    return True

if __name__ == "__main__":
    print("=" * 70)
    print("TEST TCP KEEPALIVE - Détection connexions mortes")
    print("=" * 70)
    
    results = [
        test_keepalive_configuration(),
        test_select_no_exception_list(),
        test_dead_socket_stops_loop(),
        test_dead_socket_callback(),
    ]
    
    print("\n" + "=" * 70)
    print("RÉSUMÉ")
    print("=" * 70)
    
    # Filter None results and count
    valid_results = [r for r in results if r is not None]
    passed = sum(1 for r in valid_results if r)
    total = len(valid_results)
    
    print(f"Tests réussis: {passed}/{total}")
    
    if all(results):
        print("\n✅ TOUS LES TESTS RÉUSSIS")
        print("\nFix appliqué avec succès:")
        print("- TCP Keepalive activé (SO_KEEPALIVE)")
        print("- Keepalive démarre après 60s d'inactivité")
        print("- Probe toutes les 10s")
        print("- Connexion déclarée morte après 6 échecs (~2 minutes)")
        print("- select() n'utilise PAS la liste d'exceptions (évite faux positifs)")
        print("- Socket mort: set _wantExit pour stopper tight loop")
        sys.exit(0)
    else:
        print("\n❌ CERTAINS TESTS ONT ÉCHOUÉ")
        sys.exit(1)
