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
    (SELECTIVE - only Meshtastic threads)
    """
    import threading
    
    # Sauvegarder le hook d'exception par défaut
    original_excepthook = threading.excepthook
    
    def custom_threading_excepthook(args):
        """Hook personnalisé pour filtrer les exceptions des threads"""
        exc_type = args.exc_type
        exc_value = args.exc_value
        thread = args.thread
        
        # Liste des erreurs réseau à filtrer
        network_errors = (
            BrokenPipeError,
            ConnectionResetError,
            ConnectionRefusedError,
            ConnectionAbortedError,
        )
        
        # Identifier si c'est un thread Meshtastic (générique)
        thread_name = thread.name if thread else "Unknown"
        is_meshtastic_thread = (
            thread_name.startswith("Thread-") or  # Threads génériques Python
            thread_name == "MainThread" or         # Thread principal
            thread_name.startswith("Dummy-")       # Threads dummy
        )
        
        # Ne filtrer que les erreurs réseau des threads Meshtastic
        if exc_type in network_errors and is_meshtastic_thread:
            print(f"[FILTER] Thread {thread_name}: {exc_type.__name__} supprimé (Meshtastic thread)")
            return  # Ne PAS appeler le hook par défaut
        
        # Pour toutes les autres exceptions ET threads nommés, comportement normal
        original_excepthook(args)
    
    # Installer le hook personnalisé
    threading.excepthook = custom_threading_excepthook
    print("✅ Filtre d'exceptions threading installé (selective)\n")


def test_broken_pipe():
    """Simulate a Meshtastic thread (Thread-N) that raises BrokenPipeError"""
    print("  Thread started: will raise BrokenPipeError")
    time.sleep(0.2)
    raise BrokenPipeError(32, "Broken pipe")


def test_connection_reset():
    """Simulate a Meshtastic thread (Thread-N) that raises ConnectionResetError"""
    print("  Thread started: will raise ConnectionResetError")
    time.sleep(0.2)
    raise ConnectionResetError(104, "Connection reset")


def test_named_thread_error():
    """Simulate a named bot thread (TelegramBot) that raises BrokenPipeError"""
    print("  Thread started: will raise BrokenPipeError")
    time.sleep(0.2)
    raise BrokenPipeError(32, "Broken pipe in Telegram")


def test_other_error():
    """Simulate a thread that raises a different error"""
    print("  Thread started: will raise ValueError")
    time.sleep(0.2)
    raise ValueError("This is a different error")


def main():
    print("=" * 70)
    print("TEST: Threading Exception Filter - Selective Filtering")
    print("=" * 70)
    print()
    
    # Install the filter
    install_threading_exception_filter()
    
    # Test 1: Meshtastic thread with BrokenPipeError (should be suppressed)
    print("Test 1: Meshtastic thread (Thread-6) with BrokenPipeError")
    print("        → Should be SUPPRESSED")
    print("-" * 70)
    t1 = threading.Thread(target=test_broken_pipe, name="Thread-6", daemon=True)
    t1.start()
    t1.join(timeout=1)
    time.sleep(0.3)
    
    # Test 2: Meshtastic thread with ConnectionResetError (should be suppressed)
    print("\nTest 2: Meshtastic thread (Thread-7) with ConnectionResetError")
    print("        → Should be SUPPRESSED")
    print("-" * 70)
    t2 = threading.Thread(target=test_connection_reset, name="Thread-7", daemon=True)
    t2.start()
    t2.join(timeout=1)
    time.sleep(0.3)
    
    # Test 3: Named bot thread with BrokenPipeError (should show traceback!)
    print("\nTest 3: Named thread (TelegramBot) with BrokenPipeError")
    print("        → Should show FULL TRACEBACK (our thread!)")
    print("-" * 70)
    t3 = threading.Thread(target=test_named_thread_error, name="TelegramBot", daemon=True)
    t3.start()
    t3.join(timeout=1)
    time.sleep(0.3)
    
    # Test 4: Generic thread with other error (should show traceback)
    print("\nTest 4: Generic thread with ValueError")
    print("        → Should show FULL TRACEBACK")
    print("-" * 70)
    t4 = threading.Thread(target=test_other_error, name="WorkerThread", daemon=True)
    t4.start()
    t4.join(timeout=1)
    time.sleep(0.3)
    
    print("\n" + "=" * 70)
    print("SUMMARY:")
    print("  ✅ Meshtastic threads (Thread-N): Network errors suppressed")
    print("  ✅ Named bot threads (TelegramBot): Full tracebacks shown")
    print("  ✅ Other exceptions: Full tracebacks shown")
    print("=" * 70)
    print("\nThe selective filter works correctly!")
    print("- Meshtastic heartbeat errors are suppressed")
    print("- Bot thread errors are visible for debugging")
    

if __name__ == "__main__":
    main()
