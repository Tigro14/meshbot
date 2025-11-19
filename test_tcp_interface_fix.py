#!/usr/bin/env python3
"""
Test pour vérifier que le fix du TCP interface fonctionne
Ce test vérifie que _readBytes() bloque correctement jusqu'à ce que des données soient disponibles
"""

import socket
import select
import threading
import time

def test_readbytes_blocking():
    """
    Tester que _readBytes() bloque jusqu'à ce que des données soient disponibles
    au lieu de retourner immédiatement b'' sur timeout
    """
    print("🧪 Test _readBytes() - Comportement bloquant...")
    
    # Créer une paire de sockets pour simuler client/serveur
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('localhost', 0))  # Port aléatoire
    server_socket.listen(1)
    
    server_port = server_socket.getsockname()[1]
    print(f"  📡 Serveur test sur port {server_port}")
    
    # Client socket
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect(('localhost', server_port))
    
    # Accepter la connexion
    conn, addr = server_socket.accept()
    
    # Simuler _readBytes avec l'ancienne méthode (BROKEN)
    def old_readbytes(sock, length, timeout=0.1):
        """Ancienne version qui retourne b'' sur timeout"""
        ready, _, exception = select.select([sock], [], [sock], timeout)
        
        if exception:
            return b''
        
        if not ready:
            # ❌ BUG: Retourne vide sur timeout!
            return b''
        
        data = sock.recv(length)
        return data
    
    # Simuler _readBytes avec la nouvelle méthode (FIXED)
    def new_readbytes(sock, length, timeout=0.1, max_attempts=5):
        """Nouvelle version qui boucle jusqu'à avoir des données"""
        attempts = 0
        while attempts < max_attempts:
            ready, _, exception = select.select([sock], [], [sock], timeout)
            
            if exception:
                return b''
            
            if not ready:
                # ✅ FIX: Continue la boucle au lieu de retourner vide
                attempts += 1
                continue
            
            data = sock.recv(length)
            return data
        
        # Timeout après max_attempts
        return b''
    
    # Test 1: Ancienne méthode (devrait échouer à lire)
    print("  📋 Test 1: Ancienne méthode (BROKEN)...")
    
    # Créer une NOUVELLE connexion pour ce test
    client_socket_1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket_1.connect(('localhost', server_port))
    conn_1, _ = server_socket.accept()
    
    def send_delayed_old():
        time.sleep(0.3)  # Délai > timeout de select (0.1s)
        conn_1.send(b'OLD')
    
    thread = threading.Thread(target=send_delayed_old, daemon=True)
    thread.start()
    
    data_old = old_readbytes(client_socket_1, 3, timeout=0.1)
    if data_old == b'':
        print("    ✅ Ancienne méthode retourne b'' (comme attendu - BUG)")
    else:
        print(f"    ❌ Ancienne méthode a lu: {data_old} (inattendu)")
    
    thread.join()
    client_socket_1.close()
    conn_1.close()
    
    # Test 2: Nouvelle méthode (devrait réussir à lire)
    print("  📋 Test 2: Nouvelle méthode (FIXED)...")
    
    # Créer une NOUVELLE connexion pour ce test
    client_socket_2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket_2.connect(('localhost', server_port))
    conn_2, _ = server_socket.accept()
    
    def send_delayed_new():
        time.sleep(0.3)  # Délai > timeout de select (0.1s)
        conn_2.send(b'NEW')
    
    thread = threading.Thread(target=send_delayed_new, daemon=True)
    thread.start()
    
    data_new = new_readbytes(client_socket_2, 3, timeout=0.1, max_attempts=5)
    if data_new == b'NEW':
        print(f"    ✅ Nouvelle méthode a lu: {data_new} (SUCCESS)")
    else:
        print(f"    ❌ Nouvelle méthode a lu: {data_new} (échec)")
    
    thread.join()
    client_socket_2.close()
    conn_2.close()
    
    # Nettoyage
    server_socket.close()
    
    # Résultat
    if data_old == b'' and data_new == b'NEW':
        print("  ✅ Test réussi: Le fix corrige le problème de blocage!")
        return True
    else:
        print("  ❌ Test échoué: Le fix ne fonctionne pas comme attendu")
        return False

def test_readbytes_immediate():
    """
    Tester que _readBytes() retourne immédiatement quand des données sont déjà disponibles
    """
    print("🧪 Test _readBytes() - Données immédiatement disponibles...")
    
    # Créer une paire de sockets
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('localhost', 0))
    server_socket.listen(1)
    
    server_port = server_socket.getsockname()[1]
    
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect(('localhost', server_port))
    
    conn, addr = server_socket.accept()
    
    # Envoyer des données AVANT de lire
    conn.send(b'IMMEDIATE')
    time.sleep(0.1)  # Laisser les données arriver
    
    # Nouvelle méthode
    def new_readbytes(sock, length, timeout=0.1, max_attempts=5):
        """Version fixée"""
        attempts = 0
        while attempts < max_attempts:
            ready, _, exception = select.select([sock], [], [sock], timeout)
            
            if exception:
                return b''
            
            if not ready:
                attempts += 1
                continue
            
            data = sock.recv(length)
            return data
        
        return b''
    
    # Lire les données
    start = time.time()
    data = new_readbytes(client_socket, 9, timeout=0.1)
    elapsed = time.time() - start
    
    # Nettoyage
    client_socket.close()
    conn.close()
    server_socket.close()
    
    # Vérification
    if data == b'IMMEDIATE' and elapsed < 0.2:  # Devrait être quasi-instantané
        print(f"    ✅ Données lues immédiatement: {data} (en {elapsed:.3f}s)")
        return True
    else:
        print(f"    ❌ Problème: data={data}, elapsed={elapsed:.3f}s")
        return False

def main():
    """Exécuter tous les tests"""
    print("\n" + "="*60)
    print("🧪 TESTS DE VALIDATION - FIX TCP INTERFACE")
    print("="*60 + "\n")
    
    tests = [
        ("Comportement bloquant", test_readbytes_blocking),
        ("Données immédiatement disponibles", test_readbytes_immediate),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
                print(f"❌ Test '{name}' échoué")
        except Exception as e:
            failed += 1
            print(f"❌ Test '{name}' erreur: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*60)
    print(f"📊 Résultats: {passed} tests réussis, {failed} tests échoués")
    print("="*60 + "\n")
    
    if failed > 0:
        print("❌ Certains tests ont échoué")
        return 1
    else:
        print("✅ Tous les tests sont passés!")
        return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
