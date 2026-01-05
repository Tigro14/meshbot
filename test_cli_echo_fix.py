#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test pour vérifier que CLIMessageSender a bien la méthode _get_interface()
"""

import sys
import os

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from platforms.cli_server_platform import CLIMessageSender


def test_cli_message_sender_has_get_interface():
    """Vérifier que CLIMessageSender a la méthode _get_interface()"""
    
    # Créer un mock simple pour la plateforme
    class MockCLIPlatform:
        def __init__(self):
            self.node_manager = None
            
        def send_message(self, user_id, message):
            pass
    
    # Créer un mock simple pour l'interface provider
    class MockInterfaceProvider:
        def get_interface(self):
            return self
            
        def sendText(self, text, destinationId=None):
            pass
    
    platform = MockCLIPlatform()
    user_id = 0xC11A0001
    interface_provider = MockInterfaceProvider()
    
    # Créer le CLIMessageSender
    sender = CLIMessageSender(platform, user_id, interface_provider=interface_provider)
    
    # Vérifier que la méthode existe
    assert hasattr(sender, '_get_interface'), "CLIMessageSender doit avoir la méthode _get_interface()"
    
    # Vérifier que la méthode est callable
    assert callable(sender._get_interface), "_get_interface() doit être une méthode appelable"
    
    # Vérifier que la méthode retourne quelque chose
    interface = sender._get_interface()
    assert interface is not None, "_get_interface() doit retourner une interface"
    
    print("✅ Test réussi: CLIMessageSender a la méthode _get_interface()")
    print(f"   Interface retournée: {interface}")
    

def test_cli_message_sender_without_interface_provider():
    """Vérifier que CLIMessageSender fonctionne sans interface_provider (None)"""
    
    class MockCLIPlatform:
        def __init__(self):
            self.node_manager = None
            
        def send_message(self, user_id, message):
            pass
    
    platform = MockCLIPlatform()
    user_id = 0xC11A0001
    
    # Créer le CLIMessageSender sans interface_provider
    sender = CLIMessageSender(platform, user_id)
    
    # Vérifier que la méthode existe
    assert hasattr(sender, '_get_interface'), "CLIMessageSender doit avoir la méthode _get_interface()"
    
    # Vérifier que la méthode retourne None quand pas d'interface_provider
    interface = sender._get_interface()
    assert interface is None, "_get_interface() doit retourner None quand pas d'interface_provider"
    
    print("✅ Test réussi: CLIMessageSender sans interface_provider retourne None")


def test_cli_message_sender_with_direct_interface():
    """Vérifier que CLIMessageSender fonctionne avec une interface directe (pas de get_interface)"""
    
    class MockCLIPlatform:
        def __init__(self):
            self.node_manager = None
            
        def send_message(self, user_id, message):
            pass
    
    # Interface directe (pas de get_interface)
    class MockDirectInterface:
        def sendText(self, text, destinationId=None):
            pass
    
    platform = MockCLIPlatform()
    user_id = 0xC11A0001
    direct_interface = MockDirectInterface()
    
    # Créer le CLIMessageSender avec interface directe
    sender = CLIMessageSender(platform, user_id, interface_provider=direct_interface)
    
    # Vérifier que la méthode retourne l'interface directe
    interface = sender._get_interface()
    assert interface is direct_interface, "_get_interface() doit retourner l'interface directe"
    
    print("✅ Test réussi: CLIMessageSender avec interface directe")


def test_get_short_name():
    """Vérifier que get_short_name() fonctionne"""
    
    class MockCLIPlatform:
        def __init__(self):
            self.node_manager = None
            
        def send_message(self, user_id, message):
            pass
    
    platform = MockCLIPlatform()
    user_id = 0xC11A0001
    
    sender = CLIMessageSender(platform, user_id)
    
    # Tester avec un node_id
    short_name = sender.get_short_name(0x12345678)
    assert short_name == "5678", f"Expected '5678', got '{short_name}'"
    
    print(f"✅ Test réussi: get_short_name() retourne '{short_name}'")


if __name__ == '__main__':
    print("=" * 60)
    print("Test de la correction du bug CLIMessageSender")
    print("=" * 60)
    print()
    
    try:
        test_cli_message_sender_has_get_interface()
        print()
        test_cli_message_sender_without_interface_provider()
        print()
        test_cli_message_sender_with_direct_interface()
        print()
        test_get_short_name()
        print()
        print("=" * 60)
        print("✅ TOUS LES TESTS RÉUSSIS")
        print("=" * 60)
        
    except AssertionError as e:
        print()
        print("=" * 60)
        print(f"❌ TEST ÉCHOUÉ: {e}")
        print("=" * 60)
        sys.exit(1)
    except Exception as e:
        print()
        print("=" * 60)
        print(f"❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        sys.exit(1)
