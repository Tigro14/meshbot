#!/usr/bin/env python3
"""
Demonstration of the UnboundLocalError bug and fix

BEFORE (BUG): 
- Import pub at module level
- Use pub.subscribe() in function
- Later import pub again locally in same function
- Result: UnboundLocalError

AFTER (FIXED):
- Import pub at module level only
- Use pub.subscribe() in function
- No local import
- Result: Works correctly
"""

def demonstrate_bug():
    """Show what was causing the UnboundLocalError"""
    print("=" * 60)
    print("DEMONSTRATING THE BUG (would fail in production)")
    print("=" * 60)
    
    code_with_bug = '''
from pubsub import pub

def start():
    # This tries to use pub (line ~2190)
    pub.subscribe(callback, "topic")  # UnboundLocalError!
    
    # But later in the function... (line ~2209)
    from pubsub import pub  # Python sees this and makes pub local!
    
    # Use pub here too
    pub.getDefaultTopicMgr()
'''
    
    print("Code with bug:")
    print(code_with_bug)
    print("\nError: UnboundLocalError at pub.subscribe()")
    print("Reason: Python sees 'from pubsub import pub' later in function,")
    print("        so treats pub as local variable throughout entire function")
    print()

def demonstrate_fix():
    """Show how the fix resolves the issue"""
    print("=" * 60)
    print("DEMONSTRATING THE FIX")
    print("=" * 60)
    
    code_fixed = '''
from pubsub import pub

def start():
    # This uses pub (line ~2190)
    pub.subscribe(callback, "topic")  # Works! pub is from module scope
    
    # Later in function... (line ~2209)
    # NO local import! Use module-level pub
    
    # Use pub here too
    pub.getDefaultTopicMgr()  # Also works!
'''
    
    print("Code with fix:")
    print(code_fixed)
    print("\nResult: Works correctly!")
    print("Reason: pub is imported once at module level,")
    print("        accessible throughout entire module")
    print()

if __name__ == '__main__':
    demonstrate_bug()
    demonstrate_fix()
    
    print("=" * 60)
    print("SUMMARY OF FIX")
    print("=" * 60)
    print("✅ Removed: 'from pubsub import pub' at line 2209")
    print("✅ Kept: 'from pubsub import pub' at line 18 (module level)")
    print("✅ Result: pub.subscribe() at line 2190 now works correctly")
    print()
    print("This is a classic Python scoping issue where a later")
    print("assignment/import in a function makes a variable local")
    print("throughout the entire function, even before the assignment.")
