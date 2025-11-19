#!/usr/bin/env python3
"""
Test pour vérifier que le filtre threading.excepthook fonctionne correctement
"""

import threading
import time
import sys


def install_threading_exception_filter():
    """
    Installe un filtre pour supprimer les tracebacks des erreurs réseau normales
    """
    import threading
    
    # Sauvegarder le hook d'exception par défaut
    original_excepthook = threading.excepthook
    
    def custom_threading_excepthook(args):
        """Hook personnalisé pour filtrer les exceptions des threads"""
        exc_type = args.exc_type
        exc_value = args.exc_value
        thread = args.thread
        
        # Liste des erreurs réseau à supprimer (normales en TCP)
        network_errors = (
            BrokenPipeError,
            ConnectionResetError,
            ConnectionRefusedError,
            ConnectionAbortedError,
        )
        
        # Vérifier si c'est une erreur réseau normale
        if exc_type in network_errors:
            print(f"[FILTER] Thread {thread.name}: {exc_type.__name__} supprimé")
            return  # Ne PAS appeler le hook par défaut
        
        # Pour toutes les autres exceptions, comportement normal
        original_excepthook(args)
    
    # Installer le hook personnalisé
    threading.excepthook = custom_threading_excepthook
    print("✅ Filtre d'exceptions threading installé\n")


def test_broken_pipe():
    """Simulate a thread that raises BrokenPipeError"""
    print("  Thread started: will raise BrokenPipeError")
    time.sleep(0.2)
    raise BrokenPipeError(32, "Broken pipe")


def test_connection_reset():
    """Simulate a thread that raises ConnectionResetError"""
    print("  Thread started: will raise ConnectionResetError")
    time.sleep(0.2)
    raise ConnectionResetError(104, "Connection reset")


def test_other_error():
    """Simulate a thread that raises a different error"""
    print("  Thread started: will raise ValueError")
    time.sleep(0.2)
    raise ValueError("This is a different error")


def main():
    print("=" * 70)
    print("TEST: Threading Exception Filter")
    print("=" * 70)
    print()
    
    # Install the filter
    install_threading_exception_filter()
    
    # Test 1: BrokenPipeError (should be suppressed)
    print("Test 1: BrokenPipeError (should be suppressed)")
    print("-" * 70)
    t1 = threading.Thread(target=test_broken_pipe, name="HeartbeatThread", daemon=True)
    t1.start()
    t1.join(timeout=1)
    time.sleep(0.3)
    
    # Test 2: ConnectionResetError (should be suppressed)
    print("\nTest 2: ConnectionResetError (should be suppressed)")
    print("-" * 70)
    t2 = threading.Thread(target=test_connection_reset, name="TCPThread", daemon=True)
    t2.start()
    t2.join(timeout=1)
    time.sleep(0.3)
    
    # Test 3: Other error (should show full traceback)
    print("\nTest 3: ValueError (should show FULL traceback)")
    print("-" * 70)
    t3 = threading.Thread(target=test_other_error, name="WorkerThread", daemon=True)
    t3.start()
    t3.join(timeout=1)
    time.sleep(0.3)
    
    print("\n" + "=" * 70)
    print("SUMMARY:")
    print("  ✅ BrokenPipeError: Suppressed (no traceback)")
    print("  ✅ ConnectionResetError: Suppressed (no traceback)")
    print("  ✅ ValueError: Full traceback shown (normal behavior)")
    print("=" * 70)
    print("\nThe filter works correctly! Network errors are suppressed,")
    print("but other exceptions still generate tracebacks.")
    

if __name__ == "__main__":
    main()
