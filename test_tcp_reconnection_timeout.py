#!/usr/bin/env python3
"""
Test pour vérifier que la reconnexion TCP fonctionne correctement

Ce test vérifie:
1. La reconnexion TCP est NON-BLOQUANTE (pas de join())
2. Utilise un thread daemon en arrière-plan
3. Ne re-souscrit pas à pubsub (évite les duplications)
4. Un moniteur de santé TCP séparé détecte les silences
"""

import sys
import os

# Ajouter le répertoire courant au path
sys.path.insert(0, os.path.dirname(__file__))

def test_reconnection_is_non_blocking():
    """
    Test que la reconnexion TCP est complètement non-bloquante
    """
    print("\n🧪 Test: Reconnexion TCP non-bloquante")
    
    # Lire le fichier main_bot.py
    with open('/home/runner/work/meshbot/meshbot/main_bot.py', 'r') as f:
        content = f.read()
    
    # Trouver la fonction _reconnect_tcp_interface
    reconnect_start = content.find('def _reconnect_tcp_interface')
    reconnect_end = content.find('\n    def ', reconnect_start + 1)
    reconnect_code = content[reconnect_start:reconnect_end]
    
    # Vérifier que la fonction utilise threading
    assert 'threading.Thread' in reconnect_code, \
        "❌ La fonction devrait utiliser threading.Thread"
    print("✅ Utilise threading.Thread")
    
    # Vérifier que c'est un thread daemon (ne bloque pas l'arrêt)
    assert 'daemon=True' in reconnect_code, \
        "❌ Le thread devrait être daemon"
    print("✅ Thread daemon (ne bloque pas l'arrêt)")
    
    # Vérifier qu'on n'appelle PAS join() (reconnexion non-bloquante)
    assert '.join(' not in reconnect_code, \
        "❌ La fonction ne devrait PAS appeler join() (doit être non-bloquante)"
    print("✅ Pas de join() - reconnexion non-bloquante")
    
    # Vérifier que return False immédiatement
    assert 'return False' in reconnect_code, \
        "❌ Devrait retourner False immédiatement"
    print("✅ Retourne False immédiatement")
    
    # Vérifier qu'il n'y a pas de pub.subscribe() CALL dans la reconnexion (évite duplications)
    # (le mot peut apparaître dans les commentaires, on cherche l'appel réel)
    import re
    # Chercher "pub.subscribe(" qui est un appel réel, pas juste la mention dans un commentaire
    actual_subscribe_call = re.search(r'^\s+pub\.subscribe\(', reconnect_code, re.MULTILINE)
    assert actual_subscribe_call is None, \
        "❌ Ne devrait PAS appeler pub.subscribe() (cause des duplications)"
    print("✅ Pas d'appel pub.subscribe()")
    
    print("\n✅ TOUS LES TESTS RÉUSSIS")
    return True

def test_tcp_health_monitor_exists():
    """
    Test que le moniteur de santé TCP rapide existe
    """
    print("\n🧪 Test: Moniteur santé TCP existe")
    
    with open('/home/runner/work/meshbot/meshbot/main_bot.py', 'r') as f:
        content = f.read()
    
    # Vérifier que la fonction tcp_health_monitor_thread existe
    assert 'def tcp_health_monitor_thread' in content, \
        "❌ La fonction tcp_health_monitor_thread devrait exister"
    print("✅ tcp_health_monitor_thread existe")
    
    # Vérifier les constantes de configuration
    assert 'TCP_HEALTH_CHECK_INTERVAL' in content, \
        "❌ TCP_HEALTH_CHECK_INTERVAL devrait exister"
    print("✅ TCP_HEALTH_CHECK_INTERVAL configuré")
    
    assert 'TCP_SILENT_TIMEOUT' in content, \
        "❌ TCP_SILENT_TIMEOUT devrait exister"
    print("✅ TCP_SILENT_TIMEOUT configuré")
    
    # Vérifier que _last_packet_time est utilisé
    assert '_last_packet_time' in content, \
        "❌ _last_packet_time devrait être utilisé"
    print("✅ _last_packet_time pour tracking")
    
    print("✅ Test réussi")
    return True

if __name__ == "__main__":
    print("=" * 70)
    print("TEST FIX TCP NON-BLOCKING - Éviter freeze lors de reconnexion")
    print("=" * 70)
    
    results = [
        test_reconnection_is_non_blocking(),
        test_tcp_health_monitor_exists(),
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
        print("- Reconnexion TCP complètement non-bloquante")
        print("- Thread daemon en arrière-plan")
        print("- Pas de re-souscription pubsub (évite duplications)")
        print("- Moniteur santé TCP séparé (détecte silences)")
        sys.exit(0)
    else:
        print("\n❌ CERTAINS TESTS ONT ÉCHOUÉ")
        sys.exit(1)

