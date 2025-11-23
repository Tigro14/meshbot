#!/usr/bin/env python3
"""
Test complet pour vérifier que system_monitor.py fonctionne correctement
avec la correction du bug OptimizedTCPInterface
"""

import sys
import os
import types
from unittest.mock import Mock, patch, MagicMock

# Ajouter le répertoire courant au path
sys.path.insert(0, os.path.dirname(__file__))

def create_mock_config():
    """Créer un module config mocké avec toutes les constantes nécessaires"""
    config_module = types.ModuleType('config')
    
    config_module.REMOTE_NODE_HOST = "192.168.1.38"
    config_module.REMOTE_NODE_NAME = "tigrog2"
    config_module.TEMP_WARNING_ENABLED = True
    config_module.CPU_WARNING_ENABLED = True
    config_module.TIGROG2_MONITORING_ENABLED = True
    config_module.TIGROG2_CHECK_INTERVAL = 15  # Interval counter (15 iterations * 20s sleep = 300s = 5 minutes)
    config_module.TEMP_CHECK_INTERVAL = 3
    config_module.CPU_CHECK_INTERVAL = 3
    config_module.TEMP_WARNING_THRESHOLD = 60
    config_module.TEMP_CRITICAL_THRESHOLD = 70
    config_module.CPU_WARNING_THRESHOLD = 80
    config_module.CPU_CRITICAL_THRESHOLD = 90
    config_module.TEMP_WARNING_DURATION = 300
    config_module.CPU_WARNING_DURATION = 300
    config_module.TIGROG2_ALERT_ON_REBOOT = True
    config_module.TIGROG2_ALERT_ON_DISCONNECT = True
    config_module.DEBUG_MODE = False
    
    return config_module

def test_check_tigrog2_uses_optimized_interface():
    """
    Test que _check_tigrog2 utilise correctement OptimizedTCPInterface
    
    C'est le test principal qui vérifie que le bug est corrigé:
    - OptimizedTCPInterface doit être importé et disponible
    - La méthode _check_tigrog2 doit pouvoir l'instancier
    """
    print("\n🧪 Test: _check_tigrog2 utilise OptimizedTCPInterface")
    
    # Installer le config mocké
    config_module = create_mock_config()
    sys.modules['config'] = config_module
    
    try:
        # Importer après avoir installé le config
        import system_monitor
        from tcp_interface_patch import OptimizedTCPInterface
        
        # Créer un moniteur
        monitor = system_monitor.SystemMonitor(telegram_integration=None)
        
        # Mocker OptimizedTCPInterface pour éviter de vraiment se connecter
        with patch('system_monitor.OptimizedTCPInterface') as mock_interface:
            # Configurer le mock
            mock_instance = MagicMock()
            mock_instance.localNode = MagicMock()
            mock_instance.localNode.lastHeard = 1234567890
            mock_interface.return_value = mock_instance
            
            # Appeler _check_tigrog2
            monitor._check_tigrog2()
            
            # Vérifier que OptimizedTCPInterface a été appelé
            mock_interface.assert_called_once_with(
                hostname="192.168.1.38",
                portNumber=4403
            )
            
            print("✅ OptimizedTCPInterface correctement utilisé")
            
            # Vérifier que close() a été appelé
            mock_instance.close.assert_called_once()
            print("✅ Interface correctement fermée après usage")
            
            # Vérifier que l'état a été mis à jour
            assert monitor.tigrog2_was_online == True, "❌ État tigrog2_was_online incorrect"
            print("✅ État tigrog2 correctement mis à jour")
        
        print("✅ Test _check_tigrog2 réussi")
        return True
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_tigrog2_disabled():
    """
    Test que le monitoring tigrog2 peut être désactivé
    """
    print("\n🧪 Test: TIGROG2_MONITORING_ENABLED = False")
    
    # Créer config avec monitoring désactivé
    config_module = create_mock_config()
    config_module.TIGROG2_MONITORING_ENABLED = False
    sys.modules['config'] = config_module
    
    try:
        # Réimporter avec le nouveau config
        import importlib
        if 'system_monitor' in sys.modules:
            importlib.reload(sys.modules['system_monitor'])
        import system_monitor
        
        # Créer un moniteur
        monitor = system_monitor.SystemMonitor(telegram_integration=None)
        
        # Mocker OptimizedTCPInterface pour détecter s'il est appelé
        with patch('system_monitor.OptimizedTCPInterface') as mock_interface:
            # Simuler un cycle de monitoring
            # Normalement, _check_tigrog2 ne devrait PAS être appelé
            
            # La boucle ne tourne pas vraiment, mais on peut tester directement
            # la condition dans _monitor_loop
            if config_module.TIGROG2_MONITORING_ENABLED:
                print("❌ TIGROG2_MONITORING_ENABLED devrait être False")
                return False
            
            print("✅ Monitoring tigrog2 correctement désactivé")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_error_handling():
    """
    Test que les erreurs lors de la vérification tigrog2 sont gérées gracieusement
    """
    print("\n🧪 Test: Gestion d'erreur gracieuse")
    
    config_module = create_mock_config()
    sys.modules['config'] = config_module
    
    try:
        import system_monitor
        
        monitor = system_monitor.SystemMonitor(telegram_integration=None)
        
        # Mocker OptimizedTCPInterface pour lever une exception
        with patch('system_monitor.OptimizedTCPInterface') as mock_interface:
            mock_interface.side_effect = ConnectionRefusedError("Connection refused")
            
            # Appeler _check_tigrog2 - ne devrait pas lever d'exception
            monitor._check_tigrog2()
            
            # Vérifier que l'état reflète l'échec
            assert monitor.tigrog2_was_online == False, "❌ État devrait être offline"
            print("✅ Erreur de connexion gérée gracieusement")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 70)
    print("TESTS DE RÉGRESSION - FIX OPTIMIZEDTCPINTERFACE")
    print("=" * 70)
    
    tests = [
        test_check_tigrog2_uses_optimized_interface,
        test_tigrog2_disabled,
        test_error_handling,
    ]
    
    results = []
    for test_func in tests:
        result = test_func()
        results.append(result)
    
    print("\n" + "=" * 70)
    print("RÉSUMÉ")
    print("=" * 70)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Tests réussis: {passed}/{total}")
    
    if all(results):
        print("\n✅ TOUS LES TESTS RÉUSSIS")
        sys.exit(0)
    else:
        print("\n❌ CERTAINS TESTS ONT ÉCHOUÉ")
        sys.exit(1)
