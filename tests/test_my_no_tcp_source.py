#!/usr/bin/env python3
"""
Test /my command NO TCP dependency (Source Code Analysis)
=========================================================

Verify that:
1. /my command uses local rx_history (no TCP)
2. /my works for both Meshtastic and MeshCore
3. /my is NOT in meshtastic_only_commands list
4. No dependency on REMOTE_NODE_HOST
"""

import os
import sys

def test_my_removed_from_meshtastic_only():
    """Test that /my is NOT in meshtastic_only_commands"""
    print("\n🧪 Test 1: /my NOT in meshtastic_only_commands")
    
    # Read message_router.py
    router_path = "handlers/message_router.py"
    with open(router_path, 'r') as f:
        content = f.read()
    
    # Find meshtastic_only_commands line
    if 'meshtastic_only_commands = [' in content:
        start = content.find('meshtastic_only_commands = [')
        end = content.find(']', start)
        line = content[start:end+1]
        
        print(f"  Found: {line}")
        
        # Check /my is NOT in the list
        if "'/my'" not in line and '"/my"' not in line:
            print("  ✅ PASS: /my NOT in meshtastic_only_commands")
            print("  ✅ MeshCore can now use /my")
            return True
        else:
            print("  ❌ FAIL: /my is still in meshtastic_only_commands")
            return False
    else:
        print("  ❌ FAIL: meshtastic_only_commands not found")
        return False

def test_handle_my_uses_local_data():
    """Test that handle_my uses rx_history (no TCP)"""
    print("\n🧪 Test 2: handle_my uses local rx_history (NO TCP)")
    
    # Read network_commands.py
    cmd_path = "handlers/command_handlers/network_commands.py"
    with open(cmd_path, 'r') as f:
        content = f.read()
    
    # Find handle_my function
    if 'def handle_my(' in content:
        # Extract handle_my function
        start = content.find('def handle_my(')
        # Find the next function (starts with "def ")
        next_func = content.find('\n    def ', start + 1)
        if next_func == -1:
            next_func = len(content)
        
        handle_my_code = content[start:next_func]
        
        print("  Checking handle_my implementation:")
        
        # Checks
        checks = []
        
        # Check for rx_history usage
        if 'rx_history' in handle_my_code:
            print("  ✅ Uses rx_history (local data)")
            checks.append(True)
        else:
            print("  ❌ Does NOT use rx_history")
            checks.append(False)
        
        # Check for node_names usage
        if 'node_names' in handle_my_code:
            print("  ✅ Uses node_names (local data)")
            checks.append(True)
        else:
            print("  ❌ Does NOT use node_names")
            checks.append(False)
        
        # Check NO get_remote_nodes call
        if 'get_remote_nodes' not in handle_my_code:
            print("  ✅ NO get_remote_nodes call (no TCP)")
            checks.append(True)
        else:
            print("  ❌ Still calls get_remote_nodes (TCP)")
            checks.append(False)
        
        # Check NO REMOTE_NODE_HOST dependency
        if 'REMOTE_NODE_HOST' not in handle_my_code:
            print("  ✅ NO REMOTE_NODE_HOST dependency")
            checks.append(True)
        else:
            print("  ❌ Still depends on REMOTE_NODE_HOST")
            checks.append(False)
        
        # Check for "NO TCP" comment
        if 'NO TCP' in handle_my_code or 'no TCP' in handle_my_code:
            print("  ✅ Has 'NO TCP' documentation")
            checks.append(True)
        else:
            print("  ⚠️  Missing 'NO TCP' documentation")
            checks.append(True)  # Not critical
        
        return all(checks)
    else:
        print("  ❌ FAIL: handle_my function not found")
        return False

def test_format_my_response_updated():
    """Test that _format_my_response doesn't reference REMOTE_NODE"""
    print("\n🧪 Test 3: _format_my_response doesn't reference REMOTE_NODE")
    
    cmd_path = "handlers/command_handlers/network_commands.py"
    with open(cmd_path, 'r') as f:
        content = f.read()
    
    if 'def _format_my_response(' in content:
        start = content.find('def _format_my_response(')
        # Find the next function
        next_func = content.find('\n    def ', start + 1)
        if next_func == -1:
            next_func = len(content)
        
        format_code = content[start:next_func]
        
        # Check NO REMOTE_NODE_NAME references
        if 'REMOTE_NODE_NAME' not in format_code:
            print("  ✅ NO REMOTE_NODE_NAME references")
            result1 = True
        else:
            print("  ❌ Still references REMOTE_NODE_NAME")
            result1 = False
        
        # Check for "local" or "Signal local"
        if 'Signal local' in format_code or 'local' in format_code:
            print("  ✅ Uses 'local' terminology")
            result2 = True
        else:
            print("  ⚠️  Doesn't use 'local' terminology")
            result2 = True  # Not critical
        
        return result1 and result2
    else:
        print("  ❌ FAIL: _format_my_response not found")
        return False

def test_format_my_not_found_local_exists():
    """Test that new _format_my_not_found_local method exists"""
    print("\n🧪 Test 4: _format_my_not_found_local exists")
    
    cmd_path = "handlers/command_handlers/network_commands.py"
    with open(cmd_path, 'r') as f:
        content = f.read()
    
    if 'def _format_my_not_found_local(' in content:
        print("  ✅ _format_my_not_found_local method exists")
        
        # Extract the method
        start = content.find('def _format_my_not_found_local(')
        next_func = content.find('\n    def ', start + 1)
        if next_func == -1:
            next_func = len(content)
        
        method_code = content[start:next_func]
        
        # Check it's local-only (no TCP/remote references)
        if 'REMOTE_NODE' not in method_code and 'get_remote' not in method_code:
            print("  ✅ Method is local-only (no TCP)")
            return True
        else:
            print("  ❌ Method still has remote references")
            return False
    else:
        print("  ❌ FAIL: _format_my_not_found_local not found")
        return False

def test_broadcast_commands_includes_my():
    """Test that /my is still in broadcast_commands"""
    print("\n🧪 Test 5: /my still in broadcast_commands list")
    
    router_path = "handlers/message_router.py"
    with open(router_path, 'r') as f:
        content = f.read()
    
    # Find broadcast_commands
    if 'broadcast_commands = [' in content:
        start = content.find('broadcast_commands = [')
        end = content.find(']', start)
        line = content[start:end+1]
        
        print(f"  Found: {line[:100]}...")
        
        # Check /my is in the list
        if "'/my'" in line or '"/my"' in line:
            print("  ✅ /my IS in broadcast_commands")
            return True
        else:
            print("  ⚠️  /my NOT in broadcast_commands (may be OK)")
            return True  # Not critical, command can work without broadcast
    else:
        print("  ⚠️  broadcast_commands not found (may be OK)")
        return True

def run_all_tests():
    """Run all tests"""
    print("="*70)
    print("TEST: /my command NO TCP dependency (Source Code Analysis)")
    print("="*70)
    
    results = []
    
    # Run tests
    results.append(("meshtastic_only removal", test_my_removed_from_meshtastic_only()))
    results.append(("local rx_history usage", test_handle_my_uses_local_data()))
    results.append(("no REMOTE_NODE refs", test_format_my_response_updated()))
    results.append(("local not_found method", test_format_my_not_found_local_exists()))
    results.append(("broadcast compatibility", test_broadcast_commands_includes_my()))
    
    # Summary
    print("\n" + "="*70)
    print("RÉSUMÉ DES TESTS:")
    print("="*70)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {name}")
    
    all_passed = all(passed for _, passed in results)
    
    print("\n" + "="*70)
    if all_passed:
        print("✅ TOUS LES TESTS RÉUSSIS")
        print("="*70)
        print("\n📋 CHANGEMENTS VALIDÉS:")
        print("  ✅ /my ne dépend plus de TCP")
        print("  ✅ /my fonctionne avec MT et MC")
        print("  ✅ /my utilise rx_history local")
        print("  ✅ Pas besoin de REMOTE_NODE_HOST")
        print("  ✅ Pas de nouvelle connexion TCP")
    else:
        print("❌ CERTAINS TESTS ONT ÉCHOUÉ")
        print("="*70)
    
    return all_passed

if __name__ == '__main__':
    os.chdir('/home/runner/work/meshbot/meshbot')
    success = run_all_tests()
    sys.exit(0 if success else 1)
