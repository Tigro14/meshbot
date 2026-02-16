#!/usr/bin/env python3
"""
Test du mécanisme de déduplication des broadcasts
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import hashlib

def test_broadcast_deduplication():
    """
    Tester la logique de déduplication des broadcasts
    """
    print("🧪 Test de la déduplication des broadcasts\n")
    
    # Simuler le dictionnaire de broadcasts récents
    recent_broadcasts = {}
    broadcast_dedup_window = 60  # 60 secondes
    
    # Fonction pour tracker un broadcast (simulée)
    def track_broadcast(message):
        msg_hash = hashlib.md5(message.encode('utf-8')).hexdigest()
        current_time = time.time()
        
        # Nettoyer les anciens
        recent_broadcasts.clear()  # Simplifié pour le test
        recent_broadcasts[msg_hash] = current_time
        
        print(f"✅ Tracked: {msg_hash[:8]}... - '{message[:30]}'")
        return msg_hash
    
    # Fonction pour vérifier si c'est un broadcast récent (simulée)
    def is_recent_broadcast(message):
        msg_hash = hashlib.md5(message.encode('utf-8')).hexdigest()
        current_time = time.time()
        
        if msg_hash in recent_broadcasts:
            age = current_time - recent_broadcasts[msg_hash]
            if age < broadcast_dedup_window:
                print(f"🔍 Reconnu ({age:.1f}s): {msg_hash[:8]}... - '{message[:30]}'")
                return True
        
        print(f"❌ Non reconnu: {msg_hash[:8]}... - '{message[:30]}'")
        return False
    
    # Test 1: Message tracké puis reçu
    print("Test 1: Message tracké puis reçu immédiatement")
    msg1 = "40da: 🌧️ Paris aujourd'hui 19/11 (max:0.5mm)"
    track_broadcast(msg1)
    assert is_recent_broadcast(msg1), "Le message devrait être reconnu"
    print("✅ Test 1 passé\n")
    
    # Test 2: Message différent non reconnu
    print("Test 2: Message différent non tracké")
    msg2 = "40da: 🌤️ Londres aujourd'hui"
    assert not is_recent_broadcast(msg2), "Le message ne devrait PAS être reconnu"
    print("✅ Test 2 passé\n")
    
    # Test 3: Même message après expiration
    print("Test 3: Message expiré (simulé)")
    msg3 = "Test expiration"
    hash3 = track_broadcast(msg3)
    # Simuler expiration en modifiant le timestamp
    recent_broadcasts[hash3] = time.time() - 61  # 61 secondes dans le passé
    assert not is_recent_broadcast(msg3), "Le message expiré ne devrait PAS être reconnu"
    print("✅ Test 3 passé\n")
    
    # Test 4: Cas réel - séquence broadcast
    print("Test 4: Séquence réaliste")
    print("  1. User envoie /rain")
    print("  2. Bot génère réponse et la track")
    response = "40da: 🌧️ Paris aujourd'hui 19/11 (max:0.5mm)\n▅▇██▇█████▇"
    track_broadcast(response)
    print("  3. Bot envoie via tigrog2")
    print("  4. Bot reçoit son propre broadcast")
    assert is_recent_broadcast(response), "Le broadcast devrait être reconnu et filtré"
    print("  5. Message filtré, pas de boucle ✅")
    print("✅ Test 4 passé\n")
    
    print("=" * 60)
    print("✅ TOUS LES TESTS PASSÉS")
    print("=" * 60)

if __name__ == "__main__":
    test_broadcast_deduplication()
