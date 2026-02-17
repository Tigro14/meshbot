#!/usr/bin/env python3
"""
Demo des nouvelles commandes echo
Montre la logique de routage sans dépendances Telegram
"""

import sys
import os

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class MockInterface:
    """Interface simulée pour tests"""
    def __init__(self, interface_type="meshtastic"):
        self.interface_type = interface_type
        self.sent_messages = []
        
    def sendText(self, message, destinationId=None, channelIndex=0):
        """Simuler l'envoi d'un message"""
        self.sent_messages.append({
            'message': message,
            'destination': destinationId,
            'channel': channelIndex
        })
        print(f"📤 [{self.interface_type.upper()}] Sent: '{message}' to channel {channelIndex}")
        if destinationId:
            print(f"   Destination: 0x{destinationId:08x}")


class MockDualInterface:
    """Gestionnaire d'interfaces dual simulé"""
    def __init__(self):
        self.meshtastic_interface = MockInterface("meshtastic")
        self.meshcore_interface = MockInterface("meshcore")
        self._dual_mode = True
        
    def is_dual_mode(self):
        return self._dual_mode
        
    def has_meshtastic(self):
        return self.meshtastic_interface is not None
        
    def has_meshcore(self):
        return self.meshcore_interface is not None
        
    def send_message(self, message, destination, network_source, channelIndex=0):
        """Envoyer un message sur le réseau spécifié"""
        if network_source == "meshtastic":
            self.meshtastic_interface.sendText(message, destination, channelIndex)
            return True
        elif network_source == "meshcore":
            self.meshcore_interface.sendText(message, destination, channelIndex)
            return True
        return False


def demo_send_echo_logic(interface, dual_interface, message, network_type=None):
    """
    Simuler la logique de _send_echo_to_network
    
    Args:
        interface: Interface principale
        dual_interface: Gestionnaire dual (ou None)
        message: Message à envoyer
        network_type: 'meshtastic', 'meshcore', ou None pour auto-detect
    """
    print(f"\n{'='*80}")
    print(f"🔊 DEMO ECHO: network_type={network_type or 'auto'}")
    print(f"{'='*80}")
    
    if not interface:
        print("❌ Interface bot non disponible")
        return "ERROR: No interface"
    
    # ========================================
    # DUAL MODE: Route to specific network
    # ========================================
    if network_type and dual_interface and dual_interface.is_dual_mode():
        print(f"🔍 [DUAL MODE] Active")
        
        if network_type == 'meshtastic':
            if not dual_interface.has_meshtastic():
                print("❌ Réseau Meshtastic non disponible")
                return "ERROR: No Meshtastic"
            print("📍 Routing to Meshtastic network")
            network_source = "meshtastic"
        elif network_type == 'meshcore':
            if not dual_interface.has_meshcore():
                print("❌ Réseau MeshCore non disponible")
                return "ERROR: No MeshCore"
            print("📍 Routing to MeshCore network")
            network_source = "meshcore"
        else:
            print("❌ Type de réseau invalide")
            return "ERROR: Invalid network type"
        
        # Send via dual interface manager
        success = dual_interface.send_message(
            message, 
            0xFFFFFFFF,  # Broadcast destination
            network_source,
            channelIndex=0  # Public channel
        )
        
        if success:
            network_name = "Meshtastic" if network_type == 'meshtastic' else "MeshCore"
            print(f"✅ Message envoyé via {network_name}")
            return f"SUCCESS: {network_name}"
        else:
            print(f"❌ Échec envoi sur réseau {network_type}")
            return f"ERROR: Send failed on {network_type}"
    
    # ========================================
    # SINGLE MODE: Use direct interface
    # ========================================
    print(f"🔍 [SINGLE MODE] Using direct interface")
    
    # Detect interface type
    is_meshcore = 'meshcore' in interface.interface_type.lower()
    
    if is_meshcore:
        print("📍 Interface MeshCore détectée - envoi broadcast sur canal public")
        interface.sendText(message, destinationId=0xFFFFFFFF, channelIndex=0)
        print("✅ Message envoyé via MeshCore")
        return "SUCCESS: MeshCore (single)"
    else:
        print("📍 Interface Meshtastic détectée - envoi broadcast sur canal public")
        interface.sendText(message, channelIndex=0)
        print("✅ Message envoyé via Meshtastic")
        return "SUCCESS: Meshtastic (single)"


def main():
    """Fonction principale de demo"""
    print("=" * 80)
    print("🧪 DEMO: Nouvelles commandes echo")
    print("=" * 80)
    print()
    print("Cette demo montre la logique de routage des commandes /echo, /echomt, /echomc")
    print()
    
    # ========================================
    # SCÉNARIO 1: Mode single (Meshtastic seul)
    # ========================================
    print("\n" + "=" * 80)
    print("📋 SCÉNARIO 1: Mode single (Meshtastic seul)")
    print("=" * 80)
    
    meshtastic_interface = MockInterface("meshtastic")
    
    # Test /echo en mode single
    result = demo_send_echo_logic(
        interface=meshtastic_interface,
        dual_interface=None,
        message="Tigro: test message",
        network_type=None  # Auto-detect
    )
    print(f"\n📊 Résultat: {result}")
    
    # ========================================
    # SCÉNARIO 2: Mode single (MeshCore seul)
    # ========================================
    print("\n" + "=" * 80)
    print("📋 SCÉNARIO 2: Mode single (MeshCore seul)")
    print("=" * 80)
    
    meshcore_interface = MockInterface("meshcore")
    
    # Test /echo en mode single MeshCore
    result = demo_send_echo_logic(
        interface=meshcore_interface,
        dual_interface=None,
        message="Tigro: test message",
        network_type=None  # Auto-detect
    )
    print(f"\n📊 Résultat: {result}")
    
    # ========================================
    # SCÉNARIO 3: Mode dual - /echo (auto)
    # ========================================
    print("\n" + "=" * 80)
    print("📋 SCÉNARIO 3: Mode dual - /echo (auto, utilise primary)")
    print("=" * 80)
    
    dual_interface = MockDualInterface()
    primary_interface = dual_interface.meshtastic_interface
    
    # Test /echo en mode dual (utilise l'interface primary)
    result = demo_send_echo_logic(
        interface=primary_interface,
        dual_interface=None,  # /echo n'utilise pas dual routing
        message="Tigro: test message",
        network_type=None
    )
    print(f"\n📊 Résultat: {result}")
    
    # ========================================
    # SCÉNARIO 4: Mode dual - /echomt
    # ========================================
    print("\n" + "=" * 80)
    print("📋 SCÉNARIO 4: Mode dual - /echomt (force Meshtastic)")
    print("=" * 80)
    
    # Test /echomt en mode dual
    result = demo_send_echo_logic(
        interface=primary_interface,
        dual_interface=dual_interface,
        message="Tigro: test message",
        network_type='meshtastic'
    )
    print(f"\n📊 Résultat: {result}")
    
    # ========================================
    # SCÉNARIO 5: Mode dual - /echomc
    # ========================================
    print("\n" + "=" * 80)
    print("📋 SCÉNARIO 5: Mode dual - /echomc (force MeshCore)")
    print("=" * 80)
    
    # Test /echomc en mode dual
    result = demo_send_echo_logic(
        interface=primary_interface,
        dual_interface=dual_interface,
        message="Tigro: test message",
        network_type='meshcore'
    )
    print(f"\n📊 Résultat: {result}")
    
    # ========================================
    # RÉSUMÉ
    # ========================================
    print("\n" + "=" * 80)
    print("✅ RÉSUMÉ DE LA DEMO")
    print("=" * 80)
    print()
    print("1. ✅ Mode single Meshtastic: /echo utilise l'interface Meshtastic")
    print("2. ✅ Mode single MeshCore: /echo utilise l'interface MeshCore")
    print("3. ✅ Mode dual /echo: Utilise l'interface principale (Meshtastic)")
    print("4. ✅ Mode dual /echomt: Force l'envoi sur Meshtastic")
    print("5. ✅ Mode dual /echomc: Force l'envoi sur MeshCore")
    print()
    print("🎯 AVANTAGES:")
    print("   • Plus besoin de REMOTE_NODE_HOST")
    print("   • Utilise l'interface partagée du bot (serial ou TCP)")
    print("   • Support du mode dual avec routage explicite")
    print("   • Pas de création de nouvelle connexion TCP")
    print()


if __name__ == "__main__":
    main()
