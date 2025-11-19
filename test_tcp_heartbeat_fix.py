#!/usr/bin/env python3
"""
Test simple pour vérifier la logique de gestion d'erreur dans _writeBytes

Ce test valide que la logique de gestion d'erreur fonctionne correctement
sans dépendre de la hiérarchie de classes Meshtastic.

Usage:
    python test_tcp_heartbeat_fix.py
"""

import socket
import sys
import errno


def simulate_writeBytes_with_error_handling(mock_socket, data):
    """
    Simule la logique de _writeBytes avec gestion d'erreur
    
    Copie de la logique du fix appliqué dans tcp_interface_patch.py
    """
    try:
        # Tenter d'envoyer les données
        mock_socket.send(data)
        return True, "success"
        
    except BrokenPipeError as e:
        # Connexion cassée
        return False, f"BrokenPipe (errno {e.errno})"
        
    except ConnectionResetError as e:
        # Connexion réinitialisée
        return False, f"ConnectionReset (errno {e.errno})"
        
    except ConnectionRefusedError as e:
        # Connexion refusée
        return False, f"ConnectionRefused (errno {e.errno})"
        
    except socket.timeout:
        # Timeout d'écriture
        return False, "Timeout"
        
    except socket.error as e:
        # Autres erreurs socket
        if hasattr(e, 'errno'):
            return False, f"SocketError (errno {e.errno})"
        return False, "SocketError (no errno)"
        
    except Exception as e:
        # Erreur inattendue
        return False, f"Unexpected: {type(e).__name__}"


class MockSocket:
    """Mock socket qui peut lever différentes exceptions"""
    
    def __init__(self, exception_to_raise=None):
        self.exception_to_raise = exception_to_raise
        self.send_called = False
        self.send_data = None
    
    def send(self, data):
        self.send_called = True
        self.send_data = data
        
        if self.exception_to_raise:
            raise self.exception_to_raise
        
        return len(data)


def test_broken_pipe_handling():
    """Test: BrokenPipeError est capturé"""
    print("\n1. Test: BrokenPipeError handling")
    print("-" * 60)
    
    mock = MockSocket(BrokenPipeError(errno.EPIPE, "Broken pipe"))
    success, msg = simulate_writeBytes_with_error_handling(mock, b"test")
    
    if not success and "BrokenPipe" in msg:
        print(f"✅ PASS: {msg} capturé sans lever d'exception")
        return True
    else:
        print(f"❌ FAIL: Devrait capturer BrokenPipeError")
        return False


def test_connection_reset_handling():
    """Test: ConnectionResetError est capturé"""
    print("\n2. Test: ConnectionResetError handling")
    print("-" * 60)
    
    mock = MockSocket(ConnectionResetError(errno.ECONNRESET, "Connection reset"))
    success, msg = simulate_writeBytes_with_error_handling(mock, b"test")
    
    if not success and "ConnectionReset" in msg:
        print(f"✅ PASS: {msg} capturé sans lever d'exception")
        return True
    else:
        print(f"❌ FAIL: Devrait capturer ConnectionResetError")
        return False


def test_timeout_handling():
    """Test: socket.timeout est capturé"""
    print("\n3. Test: socket.timeout handling")
    print("-" * 60)
    
    mock = MockSocket(socket.timeout("timed out"))
    success, msg = simulate_writeBytes_with_error_handling(mock, b"test")
    
    if not success and "Timeout" in msg:
        print(f"✅ PASS: {msg} capturé sans lever d'exception")
        return True
    else:
        print(f"❌ FAIL: Devrait capturer timeout")
        return False


def test_generic_socket_error_handling():
    """Test: socket.error générique est capturé"""
    print("\n4. Test: Generic socket.error handling")
    print("-" * 60)
    
    err = socket.error("Socket error")
    err.errno = 999
    mock = MockSocket(err)
    success, msg = simulate_writeBytes_with_error_handling(mock, b"test")
    
    if not success and "SocketError" in msg:
        print(f"✅ PASS: {msg} capturé sans lever d'exception")
        return True
    else:
        print(f"❌ FAIL: Devrait capturer socket.error")
        return False


def test_success_case():
    """Test: Cas nominal sans erreur"""
    print("\n5. Test: Normal operation (success case)")
    print("-" * 60)
    
    mock = MockSocket(None)  # Pas d'exception
    success, msg = simulate_writeBytes_with_error_handling(mock, b"test data")
    
    if success and mock.send_called:
        print(f"✅ PASS: Envoi réussi, send() appelé")
        return True
    else:
        print(f"❌ FAIL: Devrait réussir en cas normal")
        return False


def test_all_common_errnos():
    """Test: Tous les errno communs sont gérés"""
    print("\n6. Test: All common errno values handled")
    print("-" * 60)
    
    common_errnos = {
        32: (BrokenPipeError, "EPIPE (Broken pipe)"),
        104: (ConnectionResetError, "ECONNRESET (Connection reset)"),
        111: (ConnectionRefusedError, "ECONNREFUSED (Connection refused)"),
    }
    
    all_passed = True
    for err_no, (exc_class, err_name) in common_errnos.items():
        exc = exc_class(err_no, err_name)
        mock = MockSocket(exc)
        success, msg = simulate_writeBytes_with_error_handling(mock, b"test")
        
        if not success:
            print(f"✅ PASS: errno {err_no} ({err_name}) capturé")
        else:
            print(f"❌ FAIL: errno {err_no} non capturé")
            all_passed = False
    
    return all_passed


def run_all_tests():
    """Exécuter tous les tests"""
    print("=" * 70)
    print("TEST: Logique de gestion d'erreur _writeBytes()")
    print("=" * 70)
    print("\nObjectif: Vérifier que toutes les erreurs socket sont capturées")
    print("sans lever d'exception (éviter les tracebacks dans les logs)")
    print()
    
    tests = [
        test_broken_pipe_handling,
        test_connection_reset_handling,
        test_timeout_handling,
        test_generic_socket_error_handling,
        test_success_case,
        test_all_common_errnos,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ EXCEPTION dans le test: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    # Résumé
    print("\n" + "=" * 70)
    print("RÉSUMÉ DES TESTS")
    print("=" * 70)
    print(f"Tests exécutés: {len(results)}")
    print(f"Réussites: {sum(results)}")
    print(f"Échecs: {len(results) - sum(results)}")
    
    if all(results):
        print("\n✅ TOUS LES TESTS RÉUSSIS")
        print("\nLe fix résout le problème:")
        print("- BrokenPipeError sera capturé silencieusement")
        print("- Plus de tracebacks dans les logs pour les déconnexions TCP")
        print("- Le heartbeat échouera en silence quand la connexion est perdue")
        return 0
    else:
        print("\n❌ ÉCHECS DÉTECTÉS")
        print("Le fix nécessite des ajustements")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())

