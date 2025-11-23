#!/usr/bin/env python3
"""
Test pour vérifier que system_monitor.py importe correctement OptimizedTCPInterface
Fix pour: https://github.com/Tigro14/meshbot/issues/XXX
"""

import sys
import os

# Ajouter le répertoire courant au path
sys.path.insert(0, os.path.dirname(__file__))

def test_system_monitor_imports():
    """
    Teste que system_monitor.py peut être importé sans erreur
    
    Vérifie notamment que OptimizedTCPInterface est correctement importé
    """
    print("🧪 Test: Vérification des imports de system_monitor.py")
    
    # Créer un config minimal pour permettre l'import
    import types
    config_module = types.ModuleType('config')
    
    # Définir les constantes minimales nécessaires
    config_module.REMOTE_NODE_HOST = "192.168.1.38"
    config_module.REMOTE_NODE_NAME = "tigrog2"
    config_module.TEMP_WARNING_ENABLED = False
    config_module.CPU_WARNING_ENABLED = False
    config_module.TIGROG2_MONITORING_ENABLED = True
    config_module.TIGROG2_CHECK_INTERVAL = 120
    config_module.TEMP_CHECK_INTERVAL = 60
    config_module.CPU_CHECK_INTERVAL = 60
    config_module.TEMP_WARNING_THRESHOLD = 60
    config_module.TEMP_CRITICAL_THRESHOLD = 70
    config_module.CPU_WARNING_THRESHOLD = 80
    config_module.CPU_CRITICAL_THRESHOLD = 90
    config_module.TEMP_WARNING_DURATION = 300
    config_module.CPU_WARNING_DURATION = 300
    config_module.TIGROG2_ALERT_ON_REBOOT = True
    config_module.TIGROG2_ALERT_ON_DISCONNECT = True
    config_module.DEBUG_MODE = False
    
    sys.modules['config'] = config_module
    
    try:
        # Tenter d'importer system_monitor
        import system_monitor
        print("✅ system_monitor importé avec succès")
        
        # Vérifier que la classe SystemMonitor existe
        assert hasattr(system_monitor, 'SystemMonitor'), "❌ Classe SystemMonitor manquante"
        print("✅ Classe SystemMonitor trouvée")
        
        # Vérifier que OptimizedTCPInterface est importé
        assert hasattr(system_monitor, 'OptimizedTCPInterface'), "❌ OptimizedTCPInterface non importé"
        print("✅ OptimizedTCPInterface importé correctement")
        
        # Créer une instance (sans telegram_integration)
        monitor = system_monitor.SystemMonitor(telegram_integration=None)
        print("✅ Instance SystemMonitor créée")
        
        # Vérifier les attributs de base
        assert hasattr(monitor, 'running'), "❌ Attribut 'running' manquant"
        assert hasattr(monitor, 'monitor_thread'), "❌ Attribut 'monitor_thread' manquant"
        assert hasattr(monitor, '_check_tigrog2'), "❌ Méthode '_check_tigrog2' manquante"
        print("✅ Tous les attributs de base présents")
        
        print("\n✅ TOUS LES TESTS RÉUSSIS")
        return True
        
    except ImportError as e:
        print(f"❌ Erreur d'import: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_system_monitor_imports()
    sys.exit(0 if success else 1)
