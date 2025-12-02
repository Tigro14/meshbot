#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to verify the Telegram /neighbors wrapper implementation
This is a basic sanity check to ensure the code structure is correct
"""

import sys
import inspect

def test_neighbors_command_exists():
    """Verify that neighbors_command method exists in NetworkCommands"""
    try:
        # Try to import without actually loading telegram dependencies
        import ast
        with open('telegram_bot/commands/network_commands.py', 'r') as f:
            tree = ast.parse(f.read())
        
        # Find the NetworkCommands class
        network_commands_class = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == 'NetworkCommands':
                network_commands_class = node
                break
        
        assert network_commands_class is not None, \
            "NetworkCommands class not found"
        
        # Find the neighbors_command method
        neighbors_method = None
        for item in network_commands_class.body:
            if isinstance(item, ast.AsyncFunctionDef) and item.name == 'neighbors_command':
                neighbors_method = item
                break
        
        assert neighbors_method is not None, \
            "neighbors_command method not found in NetworkCommands"
        
        # Check if it's an async method
        assert isinstance(neighbors_method, ast.AsyncFunctionDef), \
            "neighbors_command should be an async method"
        
        # Check method signature has required parameters
        param_names = [arg.arg for arg in neighbors_method.args.args]
        assert 'self' in param_names, "Method should have 'self' parameter"
        assert 'update' in param_names, "Method should have 'update' parameter"
        assert 'context' in param_names, "Method should have 'context' parameter"
        
        print("✅ neighbors_command method exists and has correct signature")
        return True
    except Exception as e:
        print(f"❌ Error checking neighbors_command: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_handler_registration():
    """Verify that the handler is registered in telegram_integration.py"""
    try:
        with open('telegram_integration.py', 'r') as f:
            content = f.read()
            
        # Check if the CommandHandler is registered
        assert 'CommandHandler("neighbors"' in content, \
            "CommandHandler for 'neighbors' not found in telegram_integration.py"
        
        assert 'self.network_commands.neighbors_command' in content, \
            "neighbors_command handler not properly registered"
        
        print("✅ Handler registration found in telegram_integration.py")
        return True
    except Exception as e:
        print(f"❌ Error checking handler registration: {e}")
        return False

def test_method_implementation():
    """Verify the implementation has required defensive checks"""
    try:
        with open('telegram_bot/commands/network_commands.py', 'r') as f:
            content = f.read()
        
        # Check for authorization check
        assert 'check_authorization' in content and \
               'neighbors_command' in content, \
            "Authorization check not found in neighbors_command"
        
        # Check for traffic_monitor defensive check
        assert 'Traffic monitor non disponible' in content, \
            "Defensive check for traffic_monitor not found"
        
        # Check for info_print logging
        neighbors_start = content.find('async def neighbors_command')
        neighbors_end = content.find('\n    async def', neighbors_start + 1)
        if neighbors_end == -1:
            neighbors_end = len(content)
        neighbors_method = content[neighbors_start:neighbors_end]
        
        assert 'info_print' in neighbors_method, \
            "info_print logging not found in neighbors_command"
        
        # Check for asyncio.to_thread
        assert 'asyncio.to_thread' in neighbors_method, \
            "asyncio.to_thread not used in neighbors_command"
        
        # Check for chunking logic
        assert '4000' in neighbors_method, \
            "4000 char chunking threshold not found"
        
        # Check for compact=False parameter
        assert 'compact=False' in neighbors_method, \
            "compact=False parameter not passed to get_neighbors_report"
        
        print("✅ Method implementation has all required defensive checks")
        return True
    except Exception as e:
        print(f"❌ Error checking method implementation: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Testing Telegram /neighbors wrapper implementation")
    print("=" * 60)
    
    results = []
    
    print("\n1. Testing method existence...")
    results.append(test_neighbors_command_exists())
    
    print("\n2. Testing handler registration...")
    results.append(test_handler_registration())
    
    print("\n3. Testing method implementation...")
    results.append(test_method_implementation())
    
    print("\n" + "=" * 60)
    if all(results):
        print("✅ All tests passed!")
        print("=" * 60)
        return 0
    else:
        print(f"❌ {results.count(False)} test(s) failed")
        print("=" * 60)
        return 1

if __name__ == '__main__':
    sys.exit(main())
