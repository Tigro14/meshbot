#!/usr/bin/env python3
"""
Test to verify the UnboundLocalError fix for pub import

This test ensures that:
1. pub is imported at module level
2. No local pub imports exist inside the start() method
3. pub.subscribe() call will work without UnboundLocalError
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ast
import sys
import os

def test_pub_import_scoping():
    """Test that pub import doesn't cause UnboundLocalError"""
    
    main_bot_path = os.path.join(os.path.dirname(__file__), '..', 'main_bot.py')
    
    with open(main_bot_path, 'r') as f:
        code = f.read()
    
    # Parse the code
    tree = ast.parse(code)
    
    # Check module-level import exists
    module_level_pub_import = False
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == 'pubsub':
            for alias in node.names:
                if alias.name == 'pub':
                    module_level_pub_import = True
                    break
    
    assert module_level_pub_import, "pub should be imported at module level"
    print("✅ Module-level pub import found")
    
    # Find the start method
    start_method = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == 'MeshBot':
            for method in node.body:
                if isinstance(method, ast.FunctionDef) and method.name == 'start':
                    start_method = method
                    break
    
    assert start_method is not None, "Could not find MeshBot.start() method"
    print("✅ Found MeshBot.start() method")
    
    # Check for any import statements within the function
    imports_in_function = []
    for child in ast.walk(start_method):
        if isinstance(child, ast.ImportFrom) and child.module == 'pubsub':
            imports_in_function.append(child.lineno)
    
    assert len(imports_in_function) == 0, \
        f"Found pub imports inside start() at lines: {imports_in_function}. " \
        f"This causes UnboundLocalError!"
    
    print("✅ No local pub imports in start() function")
    
    # Check that pub.subscribe is called
    pub_subscribe_called = False
    for child in ast.walk(start_method):
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Attribute):
                if (isinstance(child.func.value, ast.Name) and 
                    child.func.value.id == 'pub' and 
                    child.func.attr == 'subscribe'):
                    pub_subscribe_called = True
                    break
    
    assert pub_subscribe_called, "pub.subscribe() should be called in start()"
    print("✅ pub.subscribe() is called (and will work without UnboundLocalError)")
    
    print("\n✅ All tests passed! pub import scoping is correct.")
    return True

if __name__ == '__main__':
    try:
        test_pub_import_scoping()
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
