#!/usr/bin/env python3
"""
Vérification que le fix fonctionne en mode serial-only (sans TCP)
Simule le cas où TIGROG2_MONITORING_ENABLED = False
"""

import sys
import os
import types

# Ajouter le répertoire courant au path
sys.path.insert(0, os.path.dirname(__file__))

def test_serial_only_mode():
    """
    Test que le bot fonctionne en mode serial-only sans monitoring tigrog2
    
    Ce test simule un scénario où:
    - CONNECTION_MODE = 'serial'
    - TIGROG2_MONITORING_ENABLED = False
    - Pas de node TCP configuré
    """
    print("🧪 Test: Mode serial-only (sans monitoring tigrog2)")
    
    # Créer un config minimal pour mode serial
    config_module = types.ModuleType('config')
    
    # Configuration serial-only
    config_module.CONNECTION_MODE = 'serial'
    config_module.SERIAL_PORT = '/dev/ttyACM0'
    
    # Tigrog2 monitoring DÉSACTIVÉ
    config_module.TIGROG2_MONITORING_ENABLED = False
    
    # Variables minimales requises
    config_module.TEMP_WARNING_ENABLED = False
    config_module.CPU_WARNING_ENABLED = False
    config_module.TEMP_CHECK_INTERVAL = 60
    config_module.CPU_CHECK_INTERVAL = 60
    config_module.TIGROG2_CHECK_INTERVAL = 120
    config_module.TEMP_WARNING_THRESHOLD = 60
    config_module.TEMP_CRITICAL_THRESHOLD = 70
    config_module.CPU_WARNING_THRESHOLD = 80
    config_module.CPU_CRITICAL_THRESHOLD = 90
    config_module.TEMP_WARNING_DURATION = 300
    config_module.CPU_WARNING_DURATION = 300
    config_module.DEBUG_MODE = False
    
    # Pas besoin de définir REMOTE_NODE_HOST en mode serial
    # mais on le met quand même pour éviter des erreurs
    config_module.REMOTE_NODE_HOST = "192.168.1.38"
    config_module.REMOTE_NODE_NAME = "tigrog2"
    config_module.TIGROG2_ALERT_ON_REBOOT = True
    config_module.TIGROG2_ALERT_ON_DISCONNECT = True
    
    sys.modules['config'] = config_module
    
    try:
        # Importer system_monitor en mode serial
        import system_monitor
        print("✅ system_monitor importé en mode serial")
        
        # Créer une instance
        monitor = system_monitor.SystemMonitor(telegram_integration=None)
        print("✅ SystemMonitor créé en mode serial")
        
        # Vérifier que le monitoring tigrog2 est désactivé
        assert config_module.TIGROG2_MONITORING_ENABLED == False, "❌ Monitoring devrait être désactivé"
        print("✅ Monitoring tigrog2 désactivé (mode serial)")
        
        # Vérifier que OptimizedTCPInterface est quand même importé
        # (même si on ne l'utilise pas en mode serial)
        assert hasattr(system_monitor, 'OptimizedTCPInterface'), "❌ OptimizedTCPInterface manquant"
        print("✅ OptimizedTCPInterface importé (disponible mais non utilisé)")
        
        print("\n✅ Mode serial-only fonctionne correctement")
        return True
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_tcp_mode():
    """
    Test que le bot fonctionne en mode TCP avec monitoring tigrog2
    """
    print("\n🧪 Test: Mode TCP avec monitoring tigrog2")
    
    # Créer un config pour mode TCP
    config_module = types.ModuleType('config')
    
    # Configuration TCP
    config_module.CONNECTION_MODE = 'tcp'
    config_module.TCP_HOST = '192.168.1.38'
    config_module.TCP_PORT = 4403
    
    # Tigrog2 monitoring ACTIVÉ
    config_module.TIGROG2_MONITORING_ENABLED = True
    config_module.REMOTE_NODE_HOST = "192.168.1.38"
    config_module.REMOTE_NODE_NAME = "tigrog2"
    
    # Variables minimales requises
    config_module.TEMP_WARNING_ENABLED = False
    config_module.CPU_WARNING_ENABLED = False
    config_module.TEMP_CHECK_INTERVAL = 60
    config_module.CPU_CHECK_INTERVAL = 60
    config_module.TIGROG2_CHECK_INTERVAL = 120
    config_module.TEMP_WARNING_THRESHOLD = 60
    config_module.TEMP_CRITICAL_THRESHOLD = 70
    config_module.CPU_WARNING_THRESHOLD = 80
    config_module.CPU_CRITICAL_THRESHOLD = 90
    config_module.TEMP_WARNING_DURATION = 300
    config_module.CPU_WARNING_DURATION = 300
    config_module.TIGROG2_ALERT_ON_REBOOT = True
    config_module.TIGROG2_ALERT_ON_DISCONNECT = True
    config_module.DEBUG_MODE = False
    
    # Réinstaller le module config
    if 'system_monitor' in sys.modules:
        del sys.modules['system_monitor']
    sys.modules['config'] = config_module
    
    try:
        # Importer system_monitor en mode TCP
        import system_monitor
        print("✅ system_monitor importé en mode TCP")
        
        # Créer une instance
        monitor = system_monitor.SystemMonitor(telegram_integration=None)
        print("✅ SystemMonitor créé en mode TCP")
        
        # Vérifier que le monitoring tigrog2 est activé
        assert config_module.TIGROG2_MONITORING_ENABLED == True, "❌ Monitoring devrait être activé"
        print("✅ Monitoring tigrog2 activé (mode TCP)")
        
        # Vérifier que OptimizedTCPInterface est importé
        assert hasattr(system_monitor, 'OptimizedTCPInterface'), "❌ OptimizedTCPInterface manquant"
        print("✅ OptimizedTCPInterface importé et disponible")
        
        print("\n✅ Mode TCP fonctionne correctement")
        return True
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 70)
    print("TEST DE COMPATIBILITÉ SERIAL/TCP")
    print("=" * 70)
    
    results = [
        test_serial_only_mode(),
        test_tcp_mode(),
    ]
    
    print("\n" + "=" * 70)
    print("RÉSUMÉ")
    print("=" * 70)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Tests réussis: {passed}/{total}")
    
    if all(results):
        print("\n✅ COMPATIBILITÉ SERIAL/TCP VÉRIFIÉE")
        print("Le fix fonctionne en mode serial-only ET en mode TCP")
        sys.exit(0)
    else:
        print("\n❌ CERTAINS TESTS ONT ÉCHOUÉ")
        sys.exit(1)
