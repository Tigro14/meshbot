#!/usr/bin/env python3
"""
Script de validation du mode MeshCore Companion
Vérifie que le bot peut démarrer dans les différents modes
"""

import sys
import os

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Tester que tous les imports fonctionnent"""
    print("🔍 Test des imports...")
    
    try:
        from meshcore_serial_interface import MeshCoreSerialInterface, MeshCoreStandaloneInterface
        print("  ✅ meshcore_serial_interface")
    except ImportError as e:
        print(f"  ❌ meshcore_serial_interface: {e}")
        return False
    
    try:
        # Mock meshtastic avant d'importer handlers
        import sys
        from unittest.mock import MagicMock
        sys.modules['meshtastic'] = MagicMock()
        sys.modules['meshtastic.tcp_interface'] = MagicMock()
        sys.modules['meshtastic.serial_interface'] = MagicMock()
        
        from handlers.message_router import MessageRouter
        print("  ✅ handlers.message_router (avec mocks)")
    except ImportError as e:
        print(f"  ❌ handlers.message_router: {e}")
        return False
    
    try:
        from message_handler import MessageHandler
        print("  ✅ message_handler")
    except ImportError as e:
        print(f"  ❌ message_handler: {e}")
        return False
    
    return True

def test_standalone_interface():
    """Tester l'interface standalone"""
    print("\n🔍 Test interface standalone...")
    
    try:
        from meshcore_serial_interface import MeshCoreStandaloneInterface
        
        interface = MeshCoreStandaloneInterface()
        print(f"  ✅ Interface créée")
        print(f"     NodeNum: {interface.localNode.nodeNum:#x}")
        
        # Test sendText
        result = interface.sendText("test", 0x12345678)
        print(f"  ✅ sendText: {result} (attendu: False)")
        
        interface.close()
        print(f"  ✅ Interface fermée")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_meshcore_interface():
    """Tester l'interface MeshCore (création uniquement, pas de connexion)"""
    print("\n🔍 Test interface MeshCore...")
    
    try:
        from meshcore_serial_interface import MeshCoreSerialInterface
        
        # Créer l'interface sans connexion réelle
        interface = MeshCoreSerialInterface("/dev/ttyUSB0")
        print(f"  ✅ Interface créée")
        print(f"     Port: {interface.port}")
        print(f"     Baudrate: {interface.baudrate}")
        print(f"     NodeNum: {interface.localNode.nodeNum:#x}")
        
        # Note: On ne teste pas connect() car le port n'existe probablement pas
        print(f"  ℹ️  Connexion non testée (port physique requis)")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_companion_mode_router():
    """Tester le router en mode companion"""
    print("\n🔍 Test MessageRouter en mode companion...")
    
    try:
        # Mock meshtastic modules
        import sys
        from unittest.mock import MagicMock
        sys.modules['meshtastic'] = MagicMock()
        sys.modules['meshtastic.tcp_interface'] = MagicMock()
        sys.modules['meshtastic.serial_interface'] = MagicMock()
        
        from handlers.message_router import MessageRouter
        from unittest.mock import Mock
        
        # Mock des dépendances
        llama_client = Mock()
        esphome_client = Mock()
        remote_nodes_client = Mock()
        node_manager = Mock()
        context_manager = Mock()
        interface = Mock()
        traffic_monitor = Mock()
        
        # Créer un router en mode companion
        router = MessageRouter(
            llama_client=llama_client,
            esphome_client=esphome_client,
            remote_nodes_client=remote_nodes_client,
            node_manager=node_manager,
            context_manager=context_manager,
            interface=interface,
            traffic_monitor=traffic_monitor,
            companion_mode=True
        )
        
        print(f"  ✅ Router créé en mode companion")
        print(f"     Mode companion: {router.companion_mode}")
        print(f"     Commandes supportées: {len(router.companion_commands)}")
        
        for cmd in router.companion_commands:
            print(f"       - {cmd}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_config_options():
    """Vérifier que les nouvelles options de config existent"""
    print("\n🔍 Test options de configuration...")
    
    try:
        from config import MESHTASTIC_ENABLED, MESHCORE_ENABLED, MESHCORE_SERIAL_PORT
        
        print(f"  ✅ MESHTASTIC_ENABLED: {MESHTASTIC_ENABLED}")
        print(f"  ✅ MESHCORE_ENABLED: {MESHCORE_ENABLED}")
        print(f"  ✅ MESHCORE_SERIAL_PORT: {MESHCORE_SERIAL_PORT}")
        
        return True
        
    except ImportError as e:
        print(f"  ❌ Options manquantes: {e}")
        print(f"  ℹ️  Vérifier que config.py est à jour avec config.py.sample")
        return False

def main():
    """Point d'entrée principal"""
    print("=" * 60)
    print("VALIDATION MODE MESHCORE COMPANION")
    print("=" * 60)
    
    results = []
    
    # Tester les imports
    results.append(("Imports", test_imports()))
    
    # Tester l'interface standalone
    results.append(("Interface Standalone", test_standalone_interface()))
    
    # Tester l'interface MeshCore
    results.append(("Interface MeshCore", test_meshcore_interface()))
    
    # Tester le router en mode companion
    results.append(("MessageRouter Companion", test_companion_mode_router()))
    
    # Tester les options de config
    results.append(("Options Config", test_config_options()))
    
    # Résumé
    print("\n" + "=" * 60)
    print("RÉSUMÉ")
    print("=" * 60)
    
    total = len(results)
    passed = sum(1 for _, result in results if result)
    failed = total - passed
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print("\n" + "=" * 60)
    print(f"TOTAL: {passed}/{total} tests passés")
    
    if failed > 0:
        print(f"⚠️  {failed} test(s) échoué(s)")
        return 1
    else:
        print("✅ Tous les tests passent!")
        return 0

if __name__ == '__main__':
    sys.exit(main())
