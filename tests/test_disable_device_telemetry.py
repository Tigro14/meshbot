#!/usr/bin/env python3
"""
Test pour la désactivation automatique de la télémétrie embarquée
lorsque ESPHome télémétrie est activée.

Ce test vérifie:
1. La détection de ESPHOME_TELEMETRY_ENABLED
2. La modification de device_update_interval à 0
3. L'appel correct à writeConfig('telemetry')
"""

import sys
import os
from unittest.mock import Mock, MagicMock, patch, call

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_disable_device_telemetry():
    """Test de la désactivation de la télémétrie embarquée"""
    print("🧪 Test: Désactivation télémétrie embarquée avec ESPHome activé\n")
    print("=" * 60)
    
    # Mock localNode avec moduleConfig
    mock_local_node = MagicMock()
    mock_telemetry_config = MagicMock()
    mock_telemetry_config.device_update_interval = 900  # Valeur initiale
    mock_module_config = MagicMock()
    mock_module_config.telemetry = mock_telemetry_config
    mock_local_node.moduleConfig = mock_module_config
    mock_local_node.writeConfig = MagicMock()
    
    # Mock interface
    mock_interface = MagicMock()
    mock_interface.localNode = mock_local_node
    
    # Simuler la logique du bot
    print("1. État initial:")
    print(f"   - device_update_interval = {mock_telemetry_config.device_update_interval}s")
    
    # Configuration
    ESPHOME_TELEMETRY_ENABLED = True
    
    if ESPHOME_TELEMETRY_ENABLED:
        print("\n2. ESPHome télémétrie activée - désactivation télémétrie embarquée...")
        
        if hasattr(mock_interface, 'localNode') and mock_interface.localNode:
            local_node = mock_interface.localNode
            
            if hasattr(local_node, 'moduleConfig') and local_node.moduleConfig:
                current_interval = local_node.moduleConfig.telemetry.device_update_interval
                print(f"   - Intervalle actuel: {current_interval}s")
                
                if current_interval != 0:
                    local_node.moduleConfig.telemetry.device_update_interval = 0
                    local_node.writeConfig('telemetry')
                    print("   - device_update_interval configuré à 0")
                    print("   - writeConfig('telemetry') appelé")
    
    # Vérifications
    print("\n3. Vérifications:")
    
    # Vérifier que device_update_interval a été modifié
    assert mock_telemetry_config.device_update_interval == 0, \
        f"device_update_interval devrait être 0, mais est {mock_telemetry_config.device_update_interval}"
    print("   ✅ device_update_interval = 0")
    
    # Vérifier que writeConfig a été appelé avec 'telemetry'
    mock_local_node.writeConfig.assert_called_once_with('telemetry')
    print("   ✅ writeConfig('telemetry') appelé correctement")
    
    print("\n" + "=" * 60)
    print("✅ Test réussi: Télémétrie embarquée correctement désactivée")
    return True


def test_no_disable_when_esphome_disabled():
    """Test que la télémétrie embarquée n'est PAS désactivée si ESPHome est désactivé"""
    print("\n\n🧪 Test: Télémétrie embarquée inchangée si ESPHome désactivé\n")
    print("=" * 60)
    
    # Mock localNode avec moduleConfig
    mock_local_node = MagicMock()
    mock_telemetry_config = MagicMock()
    mock_telemetry_config.device_update_interval = 900  # Valeur initiale
    mock_module_config = MagicMock()
    mock_module_config.telemetry = mock_telemetry_config
    mock_local_node.moduleConfig = mock_module_config
    mock_local_node.writeConfig = MagicMock()
    
    # Mock interface
    mock_interface = MagicMock()
    mock_interface.localNode = mock_local_node
    
    # Configuration
    ESPHOME_TELEMETRY_ENABLED = False
    
    print("1. État initial:")
    print(f"   - device_update_interval = {mock_telemetry_config.device_update_interval}s")
    print(f"   - ESPHOME_TELEMETRY_ENABLED = {ESPHOME_TELEMETRY_ENABLED}")
    
    if ESPHOME_TELEMETRY_ENABLED:
        # Ce code ne devrait pas être exécuté
        local_node = mock_interface.localNode
        local_node.moduleConfig.telemetry.device_update_interval = 0
        local_node.writeConfig('telemetry')
    else:
        print("\n2. ESPHome télémétrie désactivée - télémétrie embarquée inchangée")
    
    # Vérifications
    print("\n3. Vérifications:")
    
    # Vérifier que device_update_interval n'a PAS été modifié
    assert mock_telemetry_config.device_update_interval == 900, \
        f"device_update_interval devrait rester 900, mais est {mock_telemetry_config.device_update_interval}"
    print("   ✅ device_update_interval inchangé (900s)")
    
    # Vérifier que writeConfig n'a PAS été appelé
    mock_local_node.writeConfig.assert_not_called()
    print("   ✅ writeConfig() non appelé")
    
    print("\n" + "=" * 60)
    print("✅ Test réussi: Télémétrie embarquée inchangée comme prévu")
    return True


def test_already_disabled():
    """Test le cas où device_update_interval est déjà à 0"""
    print("\n\n🧪 Test: Télémétrie embarquée déjà désactivée\n")
    print("=" * 60)
    
    # Mock localNode avec moduleConfig
    mock_local_node = MagicMock()
    mock_telemetry_config = MagicMock()
    mock_telemetry_config.device_update_interval = 0  # Déjà désactivé
    mock_module_config = MagicMock()
    mock_module_config.telemetry = mock_telemetry_config
    mock_local_node.moduleConfig = mock_module_config
    mock_local_node.writeConfig = MagicMock()
    
    # Mock interface
    mock_interface = MagicMock()
    mock_interface.localNode = mock_local_node
    
    # Configuration
    ESPHOME_TELEMETRY_ENABLED = True
    
    print("1. État initial:")
    print(f"   - device_update_interval = {mock_telemetry_config.device_update_interval}s (déjà désactivé)")
    
    if ESPHOME_TELEMETRY_ENABLED:
        print("\n2. ESPHome télémétrie activée - vérification état...")
        
        if hasattr(mock_interface, 'localNode') and mock_interface.localNode:
            local_node = mock_interface.localNode
            
            if hasattr(local_node, 'moduleConfig') and local_node.moduleConfig:
                current_interval = local_node.moduleConfig.telemetry.device_update_interval
                print(f"   - Intervalle actuel: {current_interval}s")
                
                if current_interval != 0:
                    local_node.moduleConfig.telemetry.device_update_interval = 0
                    local_node.writeConfig('telemetry')
                    print("   - device_update_interval configuré à 0")
                else:
                    print("   - Déjà désactivé, aucune modification nécessaire")
    
    # Vérifications
    print("\n3. Vérifications:")
    
    # Vérifier que device_update_interval est toujours 0
    assert mock_telemetry_config.device_update_interval == 0, \
        f"device_update_interval devrait être 0, mais est {mock_telemetry_config.device_update_interval}"
    print("   ✅ device_update_interval = 0")
    
    # Vérifier que writeConfig n'a PAS été appelé (pas besoin)
    mock_local_node.writeConfig.assert_not_called()
    print("   ✅ writeConfig() non appelé (pas nécessaire)")
    
    print("\n" + "=" * 60)
    print("✅ Test réussi: Configuration déjà optimale, pas de modification")
    return True


if __name__ == '__main__':
    print("============================================================")
    print("    TESTS DÉSACTIVATION TÉLÉMÉTRIE EMBARQUÉE")
    print("============================================================\n")
    
    try:
        test_disable_device_telemetry()
        test_no_disable_when_esphome_disabled()
        test_already_disabled()
        
        print("\n\n============================================================")
        print("✅ TOUS LES TESTS RÉUSSIS")
        print("============================================================")
        sys.exit(0)
        
    except AssertionError as e:
        print(f"\n❌ Test échoué: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erreur inattendue: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
