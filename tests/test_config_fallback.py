#!/usr/bin/env python3
"""
Test pour vérifier que config.py fonctionne correctement
avec et sans config_priv.py

Vérifie le fix pour: ImportError: cannot import name 'REBOOT_PASSWORD' from 'config'
"""

import sys
import os
import tempfile
import shutil

def test_config_without_priv():
    """Test que config.py importe sans erreur quand config_priv.py n'existe pas"""
    print("\n=== Test 1: Config sans config_priv.py ===")
    
    # Sauvegarder config_priv.py si présent
    config_priv_exists = os.path.exists('config_priv.py')
    if config_priv_exists:
        shutil.copy('config_priv.py', 'config_priv.py.test_backup')
        os.remove('config_priv.py')
    
    try:
        # Supprimer les modules du cache
        if 'config' in sys.modules:
            del sys.modules['config']
        if 'config_priv' in sys.modules:
            del sys.modules['config_priv']
        
        # Importer config
        import config
        
        # Vérifier que toutes les variables requises sont définies
        required_vars = [
            'TELEGRAM_BOT_TOKEN',
            'TELEGRAM_AUTHORIZED_USERS',
            'TELEGRAM_ALERT_USERS',
            'TELEGRAM_TO_MESH_MAPPING',
            'MQTT_NEIGHBOR_PASSWORD',
            'REBOOT_AUTHORIZED_USERS',
            'REBOOT_PASSWORD',
            'MESH_ALERT_SUBSCRIBED_NODES',
            'CLI_TO_MESH_MAPPING'
        ]
        
        missing = []
        for var in required_vars:
            if not hasattr(config, var):
                missing.append(var)
        
        if missing:
            print(f"❌ Variables manquantes: {missing}")
            return False
        
        print("✅ Toutes les variables sont définies")
        print(f"   REBOOT_PASSWORD = \"{config.REBOOT_PASSWORD}\"")
        return True
        
    finally:
        # Restaurer config_priv.py
        if config_priv_exists and os.path.exists('config_priv.py.test_backup'):
            shutil.move('config_priv.py.test_backup', 'config_priv.py')


def test_config_with_priv():
    """Test que config_priv.py override les valeurs par défaut"""
    print("\n=== Test 2: Config avec config_priv.py ===")
    
    # Sauvegarder config_priv.py si présent
    config_priv_exists = os.path.exists('config_priv.py')
    if config_priv_exists:
        shutil.copy('config_priv.py', 'config_priv.py.test_backup')
    
    # Créer un config_priv.py de test
    test_password = "test_custom_password_123"
    with open('config_priv.py', 'w') as f:
        f.write(f'REBOOT_PASSWORD = "{test_password}"\n')
        f.write('TELEGRAM_BOT_TOKEN = "test_token"\n')
        f.write('TELEGRAM_AUTHORIZED_USERS = [999]\n')
        f.write('TELEGRAM_ALERT_USERS = [888]\n')
        f.write('TELEGRAM_TO_MESH_MAPPING = {}\n')
        f.write('MQTT_NEIGHBOR_PASSWORD = "test_mqtt"\n')
        f.write('REBOOT_AUTHORIZED_USERS = [777]\n')
        f.write('MESH_ALERT_SUBSCRIBED_NODES = [666]\n')
        f.write('CLI_TO_MESH_MAPPING = {}\n')
    
    try:
        # Supprimer les modules du cache
        if 'config' in sys.modules:
            del sys.modules['config']
        if 'config_priv' in sys.modules:
            del sys.modules['config_priv']
        
        # Importer config
        import config
        
        # Vérifier que la valeur custom est utilisée
        if config.REBOOT_PASSWORD == test_password:
            print(f"✅ config_priv.py override fonctionne")
            print(f"   REBOOT_PASSWORD = \"{config.REBOOT_PASSWORD}\"")
            return True
        else:
            print(f"❌ Attendu \"{test_password}\", obtenu \"{config.REBOOT_PASSWORD}\"")
            return False
        
    finally:
        # Nettoyer et restaurer
        if os.path.exists('config_priv.py'):
            os.remove('config_priv.py')
        if config_priv_exists and os.path.exists('config_priv.py.test_backup'):
            shutil.move('config_priv.py.test_backup', 'config_priv.py')


def test_db_commands_import():
    """Test que db_commands.py peut importer REBOOT_PASSWORD"""
    print("\n=== Test 3: Import dans db_commands.py ===")
    
    # Sauvegarder config_priv.py si présent
    config_priv_exists = os.path.exists('config_priv.py')
    if config_priv_exists:
        shutil.copy('config_priv.py', 'config_priv.py.test_backup')
        os.remove('config_priv.py')
    
    try:
        # Supprimer les modules du cache
        if 'config' in sys.modules:
            del sys.modules['config']
        if 'config_priv' in sys.modules:
            del sys.modules['config_priv']
        
        # Ceci est l'import qui échouait avant le fix
        from config import REBOOT_PASSWORD
        
        print(f"✅ Import direct de REBOOT_PASSWORD fonctionne")
        print(f"   REBOOT_PASSWORD = \"{REBOOT_PASSWORD}\"")
        return True
        
    except ImportError as e:
        print(f"❌ ImportError: {e}")
        return False
        
    finally:
        # Restaurer config_priv.py
        if config_priv_exists and os.path.exists('config_priv.py.test_backup'):
            shutil.move('config_priv.py.test_backup', 'config_priv.py')


def main():
    """Exécuter tous les tests"""
    print("=" * 60)
    print("Tests de validation du fix ImportError config.py")
    print("=" * 60)
    
    results = []
    
    results.append(("Config sans config_priv.py", test_config_without_priv()))
    results.append(("Config avec config_priv.py", test_config_with_priv()))
    results.append(("Import REBOOT_PASSWORD", test_db_commands_import()))
    
    print("\n" + "=" * 60)
    print("RÉSUMÉ DES TESTS")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n🎉 Tous les tests ont réussi!")
        return 0
    else:
        print("\n❌ Certains tests ont échoué")
        return 1


if __name__ == '__main__':
    sys.exit(main())
