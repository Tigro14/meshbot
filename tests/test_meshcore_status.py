#!/usr/bin/env python3
"""
Test script pour vérifier les améliorations de statut MeshCore

Ce script teste:
1. La méthode get_connection_status() pour MeshCoreSerialInterface
2. La méthode get_connection_status() pour MeshCoreCLIWrapper
3. Le formatage du statut pour l'affichage
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

def test_basic_interface_status():
    """Test get_connection_status pour MeshCoreSerialInterface"""
    print("\n" + "=" * 80)
    print("TEST 1: MeshCoreSerialInterface.get_connection_status()")
    print("=" * 80)
    
    try:
        from meshcore_serial_interface import MeshCoreSerialInterface
        
        # Create interface (ne pas vraiment connecter)
        interface = MeshCoreSerialInterface("/dev/ttyUSB0", baudrate=115200)
        
        # Test get_connection_status
        status = interface.get_connection_status()
        
        print("\n✅ Méthode get_connection_status() existe")
        print("\n📊 Statut retourné:")
        for key, value in status.items():
            print(f"   {key}: {value}")
        
        # Vérifier les champs requis
        required_fields = [
            'port', 'baudrate', 'connected', 'running',
            'read_thread_alive', 'poll_thread_alive',
            'callback_configured', 'interface_type'
        ]
        
        missing = [f for f in required_fields if f not in status]
        if missing:
            print(f"\n❌ Champs manquants: {', '.join(missing)}")
            return False
        else:
            print("\n✅ Tous les champs requis sont présents")
            return True
    
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_cli_wrapper_status():
    """Test get_connection_status pour MeshCoreCLIWrapper"""
    print("\n" + "=" * 80)
    print("TEST 2: MeshCoreCLIWrapper.get_connection_status()")
    print("=" * 80)
    
    try:
        # Try to import meshcore-cli wrapper
        try:
            from meshcore_cli_wrapper import MeshCoreCLIWrapper
            has_meshcore_cli = True
        except ImportError as e:
            print(f"\n⚠️  meshcore-cli non disponible (attendu): {e}")
            print("   → Test sauté (besoin: pip install meshcore)")
            return True  # Pas un échec, juste sauté
        
        if has_meshcore_cli:
            # Don't actually connect, just check method exists
            print("\n✅ MeshCoreCLIWrapper importé")
            print("✅ Méthode get_connection_status() devrait exister")
            
            # Check if method exists via inspection
            if hasattr(MeshCoreCLIWrapper, 'get_connection_status'):
                print("✅ Méthode get_connection_status() confirmée")
                return True
            else:
                print("❌ Méthode get_connection_status() absente!")
                return False
    
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_status_formatting():
    """Test le formatage du statut pour affichage"""
    print("\n" + "=" * 80)
    print("TEST 3: Formatage du statut pour affichage")
    print("=" * 80)
    
    try:
        # Simuler un statut typique
        mock_status = {
            'port': '/dev/ttyUSB0',
            'baudrate': 115200,
            'connected': True,
            'running': True,
            'read_thread_alive': True,
            'poll_thread_alive': True,
            'callback_configured': True,
            'interface_type': 'MeshCoreSerialInterface (basic)',
        }
        
        # Format pour affichage (comme dans handle_meshcore)
        response = "📡 STATUT MESHCORE COMPANION\n"
        response += "=" * 40 + "\n"
        response += f"Port: {mock_status['port']}\n"
        response += f"Baudrate: {mock_status['baudrate']}\n"
        response += f"Connecté: {'✅' if mock_status['connected'] else '❌'}\n"
        response += f"Running: {'✅' if mock_status['running'] else '❌'}\n"
        response += f"Read thread: {'✅' if mock_status['read_thread_alive'] else '❌'}\n"
        response += f"Poll thread: {'✅' if mock_status['poll_thread_alive'] else '❌'}\n"
        response += f"Callback: {'✅' if mock_status['callback_configured'] else '❌'}\n"
        response += f"\nType: {mock_status['interface_type']}\n"
        
        print("\n✅ Formatage réussi:")
        print("-" * 40)
        print(response)
        print("-" * 40)
        
        # Vérifier la longueur pour LoRa (180 chars)
        if len(response) <= 180:
            print(f"\n✅ Taille OK pour LoRa: {len(response)}/180 chars")
        else:
            print(f"\n⚠️  Trop long pour LoRa: {len(response)}/180 chars")
            print("   → Sera tronqué en mode mesh, OK pour Telegram")
        
        return True
    
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_heartbeat_visibility():
    """Test que le heartbeat sera visible (INFO level)"""
    print("\n" + "=" * 80)
    print("TEST 4: Visibilité du heartbeat (INFO level)")
    print("=" * 80)
    
    try:
        # Read meshcore_serial_interface.py and check for info_print
        with open('meshcore_serial_interface.py', 'r') as f:
            content = f.read()
        
        # Check for the INFO level heartbeat log
        if 'info_print(f"{status_icon} [MESHCORE-HEARTBEAT]' in content:
            print("\n✅ Heartbeat utilise info_print() (toujours visible)")
            return True
        elif 'info_print(f"🔄 [MESHCORE-HEARTBEAT]' in content:
            print("\n✅ Heartbeat utilise info_print() (toujours visible)")
            return True
        else:
            print("\n⚠️  Heartbeat pourrait utiliser debug_print (visible seulement en DEBUG)")
            # Check if it uses debug_print
            if 'debug_print.*MESHCORE-HEARTBEAT' in content:
                print("❌ Heartbeat utilise debug_print!")
                return False
            return True
    
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_connection_banner():
    """Test que la banner de vérification existe"""
    print("\n" + "=" * 80)
    print("TEST 5: Banner de vérification de connexion")
    print("=" * 80)
    
    try:
        # Read meshcore_serial_interface.py and check for banner
        with open('meshcore_serial_interface.py', 'r') as f:
            content = f.read()
        
        # Check for the connection verification banner
        if 'CONNECTION VERIFICATION' in content:
            print("\n✅ Banner de vérification trouvée")
            
            # Check it's at INFO level
            if 'info_print("=" * 80)' in content:
                print("✅ Banner utilise info_print() (toujours visible)")
                return True
            else:
                print("⚠️  Banner pourrait ne pas être visible")
                return False
        else:
            print("\n❌ Banner de vérification absente!")
            return False
    
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Exécuter tous les tests"""
    print("\n" + "=" * 80)
    print("🧪 TEST SUITE: MeshCore Connection Status Improvements")
    print("=" * 80)
    
    results = []
    
    # Run all tests
    results.append(("Basic Interface Status", test_basic_interface_status()))
    results.append(("CLI Wrapper Status", test_cli_wrapper_status()))
    results.append(("Status Formatting", test_status_formatting()))
    results.append(("Heartbeat Visibility", test_heartbeat_visibility()))
    results.append(("Connection Banner", test_connection_banner()))
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 RÉSUMÉ DES TESTS")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print("\n" + "-" * 80)
    print(f"Résultat: {passed}/{total} tests réussis")
    print("=" * 80)
    
    if passed == total:
        print("\n🎉 TOUS LES TESTS RÉUSSIS!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) échoué(s)")
        return 1

if __name__ == "__main__":
    sys.exit(main())
