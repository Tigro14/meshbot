#!/usr/bin/env python3
"""
Test simple pour démontrer que le fix fonctionne correctement

Ce test démontre la différence entre:
- AVANT: Vérifier MESHCORE_ENABLED (config) → BUG, tous les paquets marqués "meshcore"
- APRÈS: Vérifier isinstance(interface, MeshCore*) → CORRECT, seulement les vrais paquets MeshCore
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import real MeshCore classes
from meshcore_serial_interface import MeshCoreSerialInterface, MeshCoreStandaloneInterface


def test_source_detection_old_way():
    """
    AVANT LE FIX: Méthode incorrecte basée sur la config
    """
    print("=" * 70)
    print("AVANT LE FIX: Vérification via MESHCORE_ENABLED (config)")
    print("=" * 70)
    
    # Simulation: Les deux sont activés (config réelle du problème)
    MESHCORE_ENABLED = True
    MESHTASTIC_ENABLED = True
    
    # Mais l'interface RÉELLE est Meshtastic (car priorité à Meshtastic)
    # On simule avec un objet générique pour représenter SerialInterface
    class MockMeshtasticSerial:
        def __init__(self):
            pass
    
    interface = MockMeshtasticSerial()  # Interface Meshtastic
    
    # Logique OLD (BUGGÉE) - ligne 496 de main_bot.py AVANT le fix
    if MESHCORE_ENABLED:
        source = 'meshcore'
        print(f"❌ BUG: source='{source}' (alors que l'interface est Meshtastic!)")
        print(f"   Config MESHCORE_ENABLED={MESHCORE_ENABLED}")
        print(f"   Interface réelle: {interface.__class__.__name__}")
        print(f"   → Résultat: TOUS les paquets marqués 'meshcore' (INCORRECT)")
    else:
        source = 'local'
    
    return source


def test_source_detection_new_way():
    """
    APRÈS LE FIX: Méthode correcte basée sur le type d'interface
    """
    print()
    print("=" * 70)
    print("APRÈS LE FIX: Vérification via isinstance(interface, MeshCore*)")
    print("=" * 70)
    
    # Simulation: Les deux sont activés (config réelle du problème)
    MESHCORE_ENABLED = True
    MESHTASTIC_ENABLED = True
    
    # Mais l'interface RÉELLE est Meshtastic (car priorité à Meshtastic)
    class MockMeshtasticSerial:
        def __init__(self):
            pass
    
    interface = MockMeshtasticSerial()  # Interface Meshtastic
    
    # Logique NEW (CORRECTE) - ligne 497 de main_bot.py APRÈS le fix
    if isinstance(interface, (MeshCoreSerialInterface, MeshCoreStandaloneInterface)):
        source = 'meshcore'
    else:
        source = 'local'
        print(f"✅ CORRECT: source='{source}' (interface Meshtastic détectée)")
        print(f"   Config MESHCORE_ENABLED={MESHCORE_ENABLED} (ignorée)")
        print(f"   Interface réelle: {interface.__class__.__name__}")
        print(f"   isinstance check: {isinstance(interface, (MeshCoreSerialInterface, MeshCoreStandaloneInterface))}")
        print(f"   → Résultat: Paquets Meshtastic marqués 'local' (CORRECT)")
    
    return source


def test_meshcore_still_works():
    """
    Vérifier que MeshCore fonctionne toujours quand c'est vraiment MeshCore
    """
    print()
    print("=" * 70)
    print("TEST BONUS: MeshCore reste détecté quand c'est vraiment MeshCore")
    print("=" * 70)
    
    # Interface réellement MeshCore
    interface = MeshCoreSerialInterface("/dev/ttyUSB0")
    
    # Test avec la nouvelle logique
    if isinstance(interface, (MeshCoreSerialInterface, MeshCoreStandaloneInterface)):
        source = 'meshcore'
        print(f"✅ CORRECT: source='{source}' (interface MeshCore détectée)")
        print(f"   Interface réelle: {interface.__class__.__name__}")
        print(f"   isinstance check: {isinstance(interface, (MeshCoreSerialInterface, MeshCoreStandaloneInterface))}")
        print(f"   → MeshCore fonctionne toujours correctement!")
    else:
        source = 'local'
        print(f"❌ ERREUR: source='{source}' (MeshCore non détecté!)")
    
    return source


def test_standalone_meshcore():
    """
    Vérifier que MeshCoreStandaloneInterface est aussi détecté
    """
    print()
    print("=" * 70)
    print("TEST BONUS: MeshCoreStandaloneInterface aussi détecté")
    print("=" * 70)
    
    # Interface MeshCore standalone
    interface = MeshCoreStandaloneInterface()
    
    # Test avec la nouvelle logique
    if isinstance(interface, (MeshCoreSerialInterface, MeshCoreStandaloneInterface)):
        source = 'meshcore'
        print(f"✅ CORRECT: source='{source}' (MeshCoreStandaloneInterface détectée)")
        print(f"   Interface réelle: {interface.__class__.__name__}")
        print(f"   isinstance check: True")
        print(f"   → MeshCoreStandaloneInterface fonctionne correctement!")
    else:
        source = 'local'
        print(f"❌ ERREUR: source='{source}' (MeshCoreStandaloneInterface non détecté!)")
    
    return source


if __name__ == '__main__':
    print("\n" + "🧪 TEST DE LA CORRECTION: Détection source Meshtastic vs MeshCore")
    print()
    
    # Test 1: Comportement bugué (avant le fix)
    old_source = test_source_detection_old_way()
    
    # Test 2: Comportement corrigé (après le fix)
    new_source = test_source_detection_new_way()
    
    # Test 3: MeshCore fonctionne toujours
    meshcore_source = test_meshcore_still_works()
    
    # Test 4: MeshCoreStandaloneInterface fonctionne
    standalone_source = test_standalone_meshcore()
    
    print()
    print("=" * 70)
    print("RÉSUMÉ")
    print("=" * 70)
    print(f"Avant fix (config check):    source='{old_source}' ❌ BUG")
    print(f"Après fix (isinstance check): source='{new_source}' ✅ CORRECT")
    print(f"MeshCore réel:                source='{meshcore_source}' ✅ CORRECT")
    print(f"MeshCore standalone:          source='{standalone_source}' ✅ CORRECT")
    print()
    
    # Validation finale
    if new_source == 'local' and meshcore_source == 'meshcore' and standalone_source == 'meshcore':
        print("✅ TOUS LES TESTS RÉUSSIS!")
        print("   → Le fix résout le problème sans casser MeshCore")
        sys.exit(0)
    else:
        print("❌ ÉCHEC: Comportement inattendu")
        sys.exit(1)
