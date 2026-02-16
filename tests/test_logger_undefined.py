#!/usr/bin/env python3
"""
Test to ensure 'logger' is not used without being defined in main_bot.py

This test prevents the NameError: name 'logger' is not defined
that occurred at line 461 when logger.info() was called without
importing or defining logger.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ast
import sys

def test_no_undefined_logger():
    """
    Verify that 'logger' is not used in main_bot.py unless it's properly defined.
    
    This test:
    1. Parses main_bot.py as AST
    2. Checks if 'logger' is imported or defined
    3. Scans for uses of 'logger' (logger.info, logger.debug, etc.)
    4. Fails if logger is used without being defined
    """
    print("🔍 Checking for undefined 'logger' usage in main_bot.py...")
    
    with open('main_bot.py', 'r', encoding='utf-8') as f:
        content = f.read()
        tree = ast.parse(content, filename='main_bot.py')
    
    # Check if logger is imported
    logger_imported = False
    logger_defined = False
    
    for node in ast.walk(tree):
        # Check for: import logging; logger = logging.getLogger()
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == 'logging':
                    print("   Found: import logging")
        
        # Check for: from logging import logger
        if isinstance(node, ast.ImportFrom):
            if node.module == 'logging':
                for alias in node.names:
                    if alias.name == 'logger' or alias.asname == 'logger':
                        logger_imported = True
                        print("   Found: logger imported from logging")
        
        # Check for: logger = ...
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == 'logger':
                    logger_defined = True
                    print("   Found: logger = ...")
    
    # Check if logger is used (logger.info, logger.debug, etc.)
    logger_uses = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == 'logger':
                # Found logger.something
                try:
                    line = node.lineno
                    attr = node.attr
                    logger_uses.append((line, attr))
                except:
                    pass
    
    # Report findings
    if logger_uses:
        print(f"\n⚠️  Found {len(logger_uses)} uses of 'logger':")
        for line, attr in logger_uses:
            print(f"   Line {line}: logger.{attr}()")
    else:
        print("\n✅ No uses of 'logger' found")
    
    # Check if logger is properly defined
    if logger_uses and not (logger_imported or logger_defined):
        print("\n❌ FAIL: 'logger' is used but not imported or defined!")
        print("\nThis will cause: NameError: name 'logger' is not defined")
        print("\nSolution:")
        print("  1. Add: import logging; logger = logging.getLogger(__name__)")
        print("  2. OR use info_print() instead (already imported from utils)")
        sys.exit(1)
    
    if logger_uses and (logger_imported or logger_defined):
        print(f"\n✅ 'logger' is properly defined/imported")
    
    if not logger_uses:
        print("\n✅ No 'logger' usage - using info_print() from utils instead")
    
    print("\n" + "="*70)
    print("✅ Test PASSED: No undefined 'logger' usage")
    print("="*70)

if __name__ == '__main__':
    test_no_undefined_logger()
