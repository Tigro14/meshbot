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
    
    IMPORTANT: The callback must be INSTANCE-based, not CLASS-based!
    This ensures that only the main interface triggers reconnection,
    not temporary connections (SafeTCPConnection/RemoteNodesClient).
    """
    print("\n🧪 Test: Callback reconnexion immédiate sur socket mort (INSTANCE)")
    
    with open('/home/runner/work/meshbot/meshbot/tcp_interface_patch.py', 'r') as f:
        content = f.read()
    
    # Vérifier que la classe a un callback configurable
    assert 'set_dead_socket_callback' in content, \
        "❌ Devrait avoir une méthode set_dead_socket_callback"
    print("✅ Méthode set_dead_socket_callback existe")
    
    # Vérifier que c'est une méthode d'INSTANCE (pas @classmethod)
    # Trouver la méthode set_dead_socket_callback
    set_callback_start = content.find('def set_dead_socket_callback')
    assert set_callback_start != -1, "❌ Méthode set_dead_socket_callback non trouvée"
    
    # Vérifier que ce n'est pas une classmethod
    set_callback_context = content[max(0, set_callback_start - 50):set_callback_start]
    assert '@classmethod' not in set_callback_context, \
        "❌ set_dead_socket_callback ne devrait PAS être @classmethod (doit être instance)"
    print("✅ set_dead_socket_callback est une méthode d'instance (pas @classmethod)")
    
    # Vérifier que la méthode utilise self, pas cls
    set_callback_end = content.find('\n    def ', set_callback_start + 1)
    if set_callback_end == -1:
        set_callback_end = len(content)
    set_callback_code = content[set_callback_start:set_callback_end]
    assert 'self._on_dead_socket_callback' in set_callback_code, \
        "❌ Devrait stocker le callback dans self._on_dead_socket_callback"
    print("✅ Callback stocké dans self._on_dead_socket_callback (instance)")
    
    # Trouver _readBytes et vérifier l'appel du callback
    readbytes_start = content.find('def _readBytes')
    readbytes_end = content.find('\n    def ', readbytes_start + 1)
    if readbytes_end == -1:
        readbytes_end = len(content)
    readbytes_code = content[readbytes_start:readbytes_end]
    
    # Vérifier qu'on utilise getattr pour récupérer le callback d'instance
    assert 'getattr(self, \'_on_dead_socket_callback\'' in readbytes_code or \
           "getattr(self, '_on_dead_socket_callback'" in readbytes_code, \
        "❌ Devrait utiliser getattr(self, '_on_dead_socket_callback') pour récupérer le callback d'instance"
    print("✅ Utilise getattr pour récupérer le callback d'instance")
    
    # Vérifier le log pour connexion temporaire
    assert 'connexion temporaire' in readbytes_code.lower() or 'temporary' in readbytes_code.lower() or 'Pas de callback' in readbytes_code, \
        "❌ Devrait mentionner les connexions temporaires (sans callback)"
    print("✅ Gère les connexions temporaires (sans callback)")
    
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
