#!/usr/bin/env python3
"""
Simple syntax check for /info command implementation
"""

import ast
import sys

def check_syntax(filename):
    """Check Python syntax of a file"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            source = f.read()
        
        ast.parse(source)
        print(f"✅ {filename}: Syntax OK")
        return True
    except SyntaxError as e:
        print(f"❌ {filename}: Syntax Error at line {e.lineno}")
        print(f"   {e.msg}")
        return False
    except Exception as e:
        print(f"⚠️ {filename}: Error - {e}")
        return False


def check_command_in_help(filename):
    """Check if /info is in help text"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check both help formats
        if '"/info"' in content or "'/info'" in content:
            print(f"✅ {filename}: /info command found in help")
            return True
        else:
            print(f"⚠️ {filename}: /info command NOT found in help")
            return False
    except Exception as e:
        print(f"❌ {filename}: Error - {e}")
        return False


def check_routing(filename):
    """Check if /info is routed"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if "message.startswith('/info')" in content:
            print(f"✅ {filename}: /info routing found")
            return True
        else:
            print(f"⚠️ {filename}: /info routing NOT found")
            return False
    except Exception as e:
        print(f"❌ {filename}: Error - {e}")
        return False


def check_handler(filename):
    """Check if handle_info method exists"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if "def handle_info(" in content:
            print(f"✅ {filename}: handle_info() method found")
            
            # Check for key features
            features = {
                "compact format": "_format_info_compact" in content,
                "detailed format": "_format_info_detailed" in content,
                "node search": "_find_node" in content,
                "broadcast support": "is_broadcast" in content,
                "threading": "threading.Thread" in content,
            }
            
            for feature, found in features.items():
                if found:
                    print(f"   ✓ Has {feature}")
                else:
                    print(f"   ⚠️ Missing {feature}")
            
            return all(features.values())
        else:
            print(f"❌ {filename}: handle_info() method NOT found")
            return False
    except Exception as e:
        print(f"❌ {filename}: Error - {e}")
        return False


def check_broadcast_commands(filename):
    """Check if /info is in broadcast commands list"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Look for broadcast_commands array
        if "'/info '" in content and "broadcast_commands" in content:
            print(f"✅ {filename}: /info in broadcast commands")
            return True
        else:
            print(f"⚠️ {filename}: /info NOT in broadcast commands or list not found")
            return False
    except Exception as e:
        print(f"❌ {filename}: Error - {e}")
        return False


def main():
    """Run all checks"""
    print("="*60)
    print("CHECKING /info COMMAND IMPLEMENTATION")
    print("="*60)
    
    files_to_check = [
        "handlers/command_handlers/network_commands.py",
        "handlers/message_router.py",
        "handlers/command_handlers/utility_commands.py",
    ]
    
    results = []
    
    # Syntax checks
    print("\n1. SYNTAX CHECKS")
    print("-"*60)
    for filepath in files_to_check:
        results.append(check_syntax(filepath))
    
    # Feature checks
    print("\n2. HANDLER IMPLEMENTATION")
    print("-"*60)
    results.append(check_handler("handlers/command_handlers/network_commands.py"))
    
    print("\n3. COMMAND ROUTING")
    print("-"*60)
    results.append(check_routing("handlers/message_router.py"))
    
    print("\n4. BROADCAST SUPPORT")
    print("-"*60)
    results.append(check_broadcast_commands("handlers/message_router.py"))
    
    print("\n5. HELP TEXT")
    print("-"*60)
    results.append(check_command_in_help("handlers/command_handlers/utility_commands.py"))
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if all(results):
        print("\n✅ ALL CHECKS PASSED")
        return 0
    else:
        print("\n⚠️ SOME CHECKS FAILED - Review output above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
