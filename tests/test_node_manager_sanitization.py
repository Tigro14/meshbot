#!/usr/bin/env python3
"""
Test d'intégration pour la sanitisation des noms de nœuds.
Vérifie que NodeManager utilise correctement clean_node_name() pour
filtrer les tentatives d'injection SQL et XSS.
"""

import sys
import os
import json
import tempfile

# Create minimal config for testing
config_module = type(sys)('config')
config_module.DEBUG_MODE = False
config_module.NODE_NAMES_FILE = '/tmp/test_node_names.json'
sys.modules['config'] = config_module

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from node_manager import NodeManager
from utils import clean_node_name

def test_node_manager_sanitization():
    """Test that NodeManager properly sanitizes node names"""
    
    print("=" * 80)
    print("TEST D'INTÉGRATION: NodeManager avec sanitisation")
    print("=" * 80)
    print()
    
    # Create a temporary node names file
    temp_file = '/tmp/test_node_names.json'
    if os.path.exists(temp_file):
        os.remove(temp_file)
    
    # Create NodeManager instance
    manager = NodeManager(interface=None)
    
    # Test cases: simulate packets with malicious names
    test_packets = [
        {
            'name': 'Normal Node 🐅',
            'decoded': {
                'portnum': 'NODEINFO_APP',
                'user': {
                    'longName': 'Normal Node 🐅',
                    'shortName': '🐅',
                    'hwModel': 'T-BEAM'
                }
            },
            'from': 0x12345678,
            'expected_name': 'Normal Node 🐅',
            'expected_short': '🐅',
            'description': 'Valid name with emoji'
        },
        {
            'name': "Evil'; DROP TABLE nodes;--",
            'decoded': {
                'portnum': 'NODEINFO_APP',
                'user': {
                    'longName': "Evil'; DROP TABLE nodes;--",
                    'shortName': 'EVIL',
                    'hwModel': 'HACKER'
                }
            },
            'from': 0x87654321,
            'expected_name': 'Evil DROP TABLE nodes--',
            'expected_short': 'EVIL',
            'description': 'SQL injection attempt'
        },
        {
            'name': '<script>alert("XSS")</script>',
            'decoded': {
                'portnum': 'NODEINFO_APP',
                'user': {
                    'longName': '<script>alert("XSS")</script>',
                    'shortName': '💀',
                    'hwModel': 'ATTACK'
                }
            },
            'from': 0xDEADBEEF,
            'expected_name': 'scriptalertXSSscript',
            'expected_short': '💀',
            'description': 'XSS attack attempt'
        },
        {
            'name': '🏠 Home<img src=x>',
            'decoded': {
                'portnum': 'NODEINFO_APP',
                'user': {
                    'longName': '🏠 Home<img src=x>',
                    'shortName': '🏠',
                    'hwModel': 'ESP32'
                }
            },
            'from': 0xCAFEBABE,
            'expected_name': '🏠 Homeimg srcx',
            'expected_short': '🏠',
            'description': 'HTML tag with emoji'
        },
    ]
    
    passed = 0
    failed = 0
    
    for test in test_packets:
        print(f"Test: {test['description']}")
        print(f"  Input name: {test['name']!r}")
        
        # Process the packet
        manager.update_node_from_packet(test)
        
        # Get the stored name
        node_id = test['from']
        if node_id in manager.node_names:
            stored_name = manager.node_names[node_id]['name']
            stored_short = manager.node_names[node_id]['shortName']
            
            name_ok = stored_name == test['expected_name']
            short_ok = stored_short == test['expected_short']
            
            if name_ok and short_ok:
                print(f"  ✅ PASS")
                print(f"     Stored name:  {stored_name!r}")
                print(f"     Stored short: {stored_short!r}")
                passed += 1
            else:
                print(f"  ❌ FAIL")
                print(f"     Expected name:  {test['expected_name']!r}")
                print(f"     Got name:       {stored_name!r}")
                print(f"     Expected short: {test['expected_short']!r}")
                print(f"     Got short:      {stored_short!r}")
                failed += 1
        else:
            print(f"  ❌ FAIL: Node not stored")
            failed += 1
        
        print()
    
    # Clean up
    if os.path.exists(temp_file):
        os.remove(temp_file)
    
    print("=" * 80)
    print(f"RÉSULTATS: {passed} passés, {failed} échoués sur {passed + failed} tests")
    print("=" * 80)
    print()
    
    return failed == 0


def test_persistence():
    """Test that sanitized names are properly saved and loaded"""
    
    print("=" * 80)
    print("TEST DE PERSISTANCE: Sauvegarde et chargement")
    print("=" * 80)
    print()
    
    temp_file = '/tmp/test_node_names_persist.json'
    if os.path.exists(temp_file):
        os.remove(temp_file)
    
    # Override the config
    import config
    original_file = config.NODE_NAMES_FILE
    config.NODE_NAMES_FILE = temp_file
    
    # Create manager and add some nodes with malicious names
    manager1 = NodeManager(interface=None)
    manager1.node_names[0x11111111] = {
        'name': clean_node_name("Test<script>"),
        'shortName': clean_node_name("TST"),
        'hwModel': 'T1',
        'lat': None,
        'lon': None,
        'alt': None,
        'last_update': None
    }
    manager1.node_names[0x22222222] = {
        'name': clean_node_name("Node'; DROP--"),
        'shortName': clean_node_name("🔥"),
        'hwModel': 'T2',
        'lat': None,
        'lon': None,
        'alt': None,
        'last_update': None
    }
    
    # Save
    manager1.save_node_names(force=True)
    
    # Load in new manager
    manager2 = NodeManager(interface=None)
    manager2.load_node_names()
    
    # Verify
    success = True
    if 0x11111111 in manager2.node_names:
        name = manager2.node_names[0x11111111]['name']
        if name == 'Testscript':
            print(f"✅ PASS: Node 1 name properly sanitized: {name!r}")
        else:
            print(f"❌ FAIL: Node 1 name incorrect: {name!r}")
            success = False
    else:
        print("❌ FAIL: Node 1 not found")
        success = False
    
    if 0x22222222 in manager2.node_names:
        name = manager2.node_names[0x22222222]['name']
        if name == 'Node DROP--':
            print(f"✅ PASS: Node 2 name properly sanitized: {name!r}")
        else:
            print(f"❌ FAIL: Node 2 name incorrect: {name!r}")
            success = False
    else:
        print("❌ FAIL: Node 2 not found")
        success = False
    
    # Clean up
    if os.path.exists(temp_file):
        os.remove(temp_file)
    config.NODE_NAMES_FILE = original_file
    
    print()
    return success


if __name__ == "__main__":
    # Run tests
    test1_ok = test_node_manager_sanitization()
    test2_ok = test_persistence()
    
    if test1_ok and test2_ok:
        print("=" * 80)
        print("✅ TOUS LES TESTS SONT PASSÉS")
        print("=" * 80)
        sys.exit(0)
    else:
        print("=" * 80)
        print("❌ CERTAINS TESTS ONT ÉCHOUÉ")
        print("=" * 80)
        sys.exit(1)
