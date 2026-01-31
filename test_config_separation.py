#!/usr/bin/env python3
"""
Test script to verify config separation works correctly
"""
import sys
import os

def test_config_import_without_priv():
    """Test that config.py.sample can be imported without config.priv.py"""
    print("=" * 60)
    print("TEST 1: Import config without config.priv.py")
    print("=" * 60)
    
    # Temporarily rename config.py.sample to config.py
    if os.path.exists('config.py'):
        os.rename('config.py', 'config.py.backup')
    os.rename('config.py.sample', 'config.py')
    
    # Ensure config_priv doesn't exist
    if os.path.exists('config_priv.py'):
        os.rename('config_priv.py', 'config_priv.py.backup')
    
    try:
        # Try importing config
        import config
        
        # Check that default values are set
        assert hasattr(config, 'TELEGRAM_BOT_TOKEN'), "Missing TELEGRAM_BOT_TOKEN"
        assert hasattr(config, 'REBOOT_PASSWORD'), "Missing REBOOT_PASSWORD"
        assert hasattr(config, 'MQTT_NEIGHBOR_PASSWORD'), "Missing MQTT_NEIGHBOR_PASSWORD"
        assert hasattr(config, 'TELEGRAM_AUTHORIZED_USERS'), "Missing TELEGRAM_AUTHORIZED_USERS"
        
        print("✅ Config imported successfully without config.priv.py")
        print(f"   TELEGRAM_BOT_TOKEN = {config.TELEGRAM_BOT_TOKEN}")
        print(f"   REBOOT_PASSWORD = {config.REBOOT_PASSWORD}")
        print(f"   MQTT_NEIGHBOR_PASSWORD = {config.MQTT_NEIGHBOR_PASSWORD}")
        print(f"   TELEGRAM_AUTHORIZED_USERS = {config.TELEGRAM_AUTHORIZED_USERS}")
        
    except Exception as e:
        print(f"❌ Failed to import config: {e}")
        return False
    finally:
        # Restore files
        os.rename('config.py', 'config.py.sample')
        if os.path.exists('config.py.backup'):
            os.rename('config.py.backup', 'config.py')
        if os.path.exists('config_priv.py.backup'):
            os.rename('config_priv.py.backup', 'config_priv.py')
    
    return True

def test_config_import_with_priv():
    """Test that config.py imports from config_priv.py when it exists"""
    print("\n" + "=" * 60)
    print("TEST 2: Import config with config.priv.py")
    print("=" * 60)
    
    # Temporarily rename config.py.sample to config.py
    if os.path.exists('config.py'):
        os.rename('config.py', 'config.py.backup')
    os.rename('config.py.sample', 'config.py')
    
    # Rename config.priv.py.sample to config_priv.py
    if os.path.exists('config_priv.py'):
        os.rename('config_priv.py', 'config_priv.py.backup')
    os.rename('config.priv.py.sample', 'config_priv.py')
    
    try:
        # Clear any cached imports
        if 'config' in sys.modules:
            del sys.modules['config']
        if 'config_priv' in sys.modules:
            del sys.modules['config_priv']
        
        # Try importing config
        import config
        
        # Check that values from config_priv are imported
        assert hasattr(config, 'TELEGRAM_BOT_TOKEN'), "Missing TELEGRAM_BOT_TOKEN"
        assert hasattr(config, 'REBOOT_PASSWORD'), "Missing REBOOT_PASSWORD"
        assert hasattr(config, 'MQTT_NEIGHBOR_PASSWORD'), "Missing MQTT_NEIGHBOR_PASSWORD"
        
        print("✅ Config imported successfully with config_priv.py")
        print(f"   TELEGRAM_BOT_TOKEN = {config.TELEGRAM_BOT_TOKEN}")
        print(f"   REBOOT_PASSWORD = {config.REBOOT_PASSWORD}")
        print(f"   MQTT_NEIGHBOR_PASSWORD = {config.MQTT_NEIGHBOR_PASSWORD}")
        
    except Exception as e:
        print(f"❌ Failed to import config: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Restore files
        os.rename('config.py', 'config.py.sample')
        os.rename('config_priv.py', 'config.priv.py.sample')
        if os.path.exists('config.py.backup'):
            os.rename('config.py.backup', 'config.py')
        if os.path.exists('config_priv.py.backup'):
            os.rename('config_priv.py.backup', 'config_priv.py')
    
    return True

def test_no_duplicates():
    """Test that there are no duplicate parameter definitions"""
    print("\n" + "=" * 60)
    print("TEST 3: Check for duplicate parameters")
    print("=" * 60)
    
    # Read config.py.sample
    with open('config.py.sample', 'r') as f:
        lines = f.readlines()
    
    # Extract parameter names
    params = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            param = line.split('=')[0].strip()
            if param and param[0].isupper():
                params.append(param)
    
    # Check for duplicates
    duplicates = [p for p in set(params) if params.count(p) > 1]
    
    if duplicates:
        print(f"❌ Found duplicate parameters: {duplicates}")
        for dup in duplicates:
            print(f"\n   {dup} appears in lines:")
            for i, line in enumerate(lines, 1):
                if line.strip().startswith(dup + ' =') or line.strip().startswith(dup + '='):
                    print(f"      Line {i}: {line.rstrip()}")
        return False
    else:
        print(f"✅ No duplicate parameters found")
        print(f"   Total unique parameters: {len(set(params))}")
    
    return True

def test_sensitive_params_not_in_config():
    """Test that sensitive parameters are not in config.py.sample"""
    print("\n" + "=" * 60)
    print("TEST 4: Verify sensitive params are not in config.py.sample")
    print("=" * 60)
    
    with open('config.py.sample', 'r') as f:
        content = f.read()
    
    # These should NOT be defined in config.py.sample (except as comments or in fallback)
    sensitive_patterns = [
        'TELEGRAM_BOT_TOKEN = "',
        'REBOOT_PASSWORD = "',
        'MQTT_NEIGHBOR_PASSWORD = "',
        'TELEGRAM_AUTHORIZED_USERS = [',
        'REBOOT_AUTHORIZED_USERS = [',
        'MESH_ALERT_SUBSCRIBED_NODES = [',
        'CLI_TO_MESH_MAPPING = {'
    ]
    
    issues = []
    for pattern in sensitive_patterns:
        # Count occurrences (should be in fallback only)
        count = content.count(pattern)
        if count > 1:
            issues.append(f"{pattern}: found {count} times (expected 1 in fallback)")
    
    if issues:
        print("❌ Found sensitive parameters outside fallback:")
        for issue in issues:
            print(f"   {issue}")
        return False
    else:
        print("✅ All sensitive parameters properly isolated")
    
    return True

if __name__ == "__main__":
    os.chdir('/home/runner/work/meshbot/meshbot')
    
    all_passed = True
    all_passed &= test_config_import_without_priv()
    all_passed &= test_config_import_with_priv()
    all_passed &= test_no_duplicates()
    all_passed &= test_sensitive_params_not_in_config()
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 60)
    
    sys.exit(0 if all_passed else 1)
